# -*- coding: utf-8 -*-
"""
数据库表结构定义与迁移脚本。
基于 后续开发需求说明书.md 的表设计，结合当前采集流程定制。

新建数据库：data/icv_news.db（与 news.db 并存过渡）
"""
import json
import os
import sqlite3
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD_DB = os.path.join(BASE, "data", "news.db")
NEW_DB = os.path.join(BASE, "data", "icv_news.db")

# ============================================================
# 表结构定义
# ============================================================

SCHEMA = """
-- 1. 新闻文章主表（合并原有 news + public_accounts）
-- source_type 枚举：gov / media / enterprise / wechat
-- category 枚举：政策法规 / 标准动态 / 投融资动态 / 技术动态 / 项目动态 / 行业动态
CREATE TABLE IF NOT EXISTS articles (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    title         TEXT    NOT NULL,
    source        TEXT,               -- 来源名称（盖世汽车 / 深圳商报（公众号））
    source_type   TEXT    DEFAULT 'media',  -- 来源类型
    url           TEXT    UNIQUE,      -- 真实链接（去重 key）
    url_original  TEXT,                -- 原始链接（公众号的中转链等）
    publish_date  DATE,                -- 发布日期
    collected_at  DATETIME,            -- 采集时间
    category      TEXT,                -- 分类名称
    summary       TEXT,                -- AI 摘要（300 字）
    full_content  TEXT,                -- 正文全文/前1000字（防止原文失效）
    is_wechat     INTEGER DEFAULT 0,   -- 是否来自微信公众号
    window        TEXT,                -- 采集窗口（如 2026-07-09）
    importance    INTEGER DEFAULT 0,   -- 重要性评分 1-5（0=未评分）
    keywords      TEXT                 -- 关键词标签 JSON 数组
);

-- 2. 采集运行日志（替代 last_update.json）
CREATE TABLE IF NOT EXISTS collect_log (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    run_date            DATE,          -- 运行日期
    version             TEXT,          -- 版本号（v1/v2…）
    window              TEXT,          -- 采集窗口
    total_articles      INTEGER,       -- 总文章数
    total_public_accounts INTEGER,     -- 其中公众号文章数
    categories          TEXT,          -- JSON：各分类计数
    source_summary      TEXT,          -- 数据来源说明
    note                TEXT,          -- 备注
    status              TEXT DEFAULT 'ok',
    error_msg           TEXT,
    created_at          DATETIME
);

-- 3. 索引
CREATE INDEX IF NOT EXISTS idx_articles_category ON articles(category);
CREATE INDEX IF NOT EXISTS idx_articles_publish_date ON articles(publish_date);
CREATE INDEX IF NOT EXISTS idx_articles_window ON articles(window);
CREATE INDEX IF NOT EXISTS idx_collect_log_run_date ON collect_log(run_date);
"""

# ============================================================
# SQL 检查辅助
# ============================================================

def table_exists(conn, name):
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def row_count(conn, table):
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

# ============================================================
# 建库
# ============================================================

def create_database():
    """创建新数据库 icv_news.db"""
    conn = sqlite3.connect(NEW_DB)
    conn.executescript(SCHEMA)
    conn.commit()
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    print(f"[OK] 数据库已创建: {NEW_DB}")
    for t in tables:
        print(f"  表 {t[0]}: {row_count(conn, t[0])} 条")
    conn.close()
    return True


# ============================================================
# 从旧数据库迁移
# ============================================================

CAT_MAP = {
    "cat-policy":     "政策法规",
    "cat-standards":  "标准动态",
    "cat-investment": "投融资动态",
    "cat-technology": "技术动态",
    "cat-projects":   "项目动态",
    "cat-industry":   "行业动态",
}

def migrate_from_old():
    """从 news.db 迁移数据到 icv_news.db。"""
    if not os.path.exists(OLD_DB):
        print("[SKIP] news.db 不存在，无可迁移数据")
        return

    old = sqlite3.connect(OLD_DB)
    new = sqlite3.connect(NEW_DB)
    new.executescript(SCHEMA)

    # --- 迁移 articles ---
    news_rows = old.execute(
        "SELECT title, source, date, summary, window, collected_at, cat FROM news"
    ).fetchall()

    migrated = 0
    for title, source, date, summary, window, collected_at, cat in news_rows:
        category = CAT_MAP.get(cat, cat)  # 如果 cat 已经是中文名就直接用
        # 判断 source_type
        source_type = "media"
        if source:
            if any(kw in source for kw in ["工信部", "公安部", "交通", "标准", "国标"]):
                source_type = "gov"
            elif "公众号" in source:
                source_type = "wechat"
            elif any(kw in source for kw in ["华为", "小鹏", "蔚来", "百度", "小马", "地平线"]):
                source_type = "enterprise"

        try:
            new.execute(
                """INSERT OR IGNORE INTO articles
                   (title, source, source_type, url, url_original, publish_date, collected_at,
                    category, summary, full_content, is_wechat, window, importance, keywords)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (title, source, source_type, f"legacy_{title[:20]}",
                 None, date, collected_at, category, summary, summary,
                 1 if source_type == "wechat" else 0, window, 0, None)
            )
            migrated += 1
        except Exception as e:
            print(f"  [WARN] 迁移失败: {title[:20]} — {e}")

    # --- 迁移 public_accounts ---
    gzh_rows = old.execute(
        "SELECT title, account, real_url, url, date, summary, keyword, collected_at FROM public_accounts"
    ).fetchall()

    gzh_migrated = 0
    for title, account, real_url, orig_url, date, summary, keyword, collected_at in gzh_rows:
        try:
            new.execute(
                """INSERT OR IGNORE INTO articles
                   (title, source, source_type, url, url_original, publish_date, collected_at,
                    category, summary, full_content, is_wechat, window, importance, keywords)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (title, f"{account}（公众号）", "wechat",
                 real_url or orig_url, orig_url, date, collected_at,
                 "投融资动态" if "融资" in title else "技术动态",
                 summary, summary, 1, None, 0,
                 json.dumps([keyword], ensure_ascii=False) if keyword else None)
            )
            gzh_migrated += 1
        except Exception as e:
            print(f"  [WARN] 公众号迁移失败: {title[:20]} — {e}")

    new.commit()

    total = row_count(new, "articles")
    old.close()
    new.close()
    print(f"\n[DONE] 迁移完成:")
    print(f"  articles: 迁移 {migrated} 条 + 公众号 {gzh_migrated} 条 = {total} 条")


# ============================================================
# 今日最新数据导入（从 news_index.json 写 collect_log）
# ============================================================

def import_latest(data):
    """将 news_index.json 的数据写入 articles + collect_log。"""
    conn = sqlite3.connect(NEW_DB)
    conn.executescript(SCHEMA)

    window = data.get("window", "")
    collected_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    inserted = 0

    for item in data.get("news", []):
        title = item.get("title", "")
        url = item.get("url", "")
        url_original = item.get("url_original") or item.get("url", "")
        source = item.get("source", "")
        category = item.get("name", "")
        summary = item.get("summary", "")
        date = item.get("date", "")

        # 推测 source_type 和 is_wechat
        source_type = "media"
        is_wechat = 0
        if source:
            if any(kw in source for kw in ["工信部", "公安部", "交通", "标准委"]):
                source_type = "gov"
            elif "公众号" in source:
                source_type = "wechat"
                is_wechat = 1
            elif any(kw in source for kw in ["华为", "小鹏", "蔚来", "百度", "小马", "地平线"]):
                source_type = "enterprise"

        try:
            conn.execute(
                """INSERT OR IGNORE INTO articles
                   (title, source, source_type, url, url_original, publish_date, collected_at,
                    category, summary, full_content, is_wechat, window)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (title, source, source_type, url, url_original, date, collected_at,
                 category, summary, summary, is_wechat, window)
            )
            if conn.total_changes:
                inserted += 1
        except sqlite3.IntegrityError:
            pass

    # 写 collect_log
    categories = data.get("category_counts", {})
    # 统计公众号数
    gzh_count = sum(1 for n in data.get("news", [])
                    if n.get("source", "").endswith("（公众号）"))

    conn.execute(
        """INSERT INTO collect_log
           (run_date, version, window, total_articles, total_public_accounts,
            categories, source_summary, note, status, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            datetime.now().strftime("%Y-%m-%d"),
            data.get("version", ""),
            window,
            data.get("total_news", 0),
            gzh_count,
            json.dumps(categories, ensure_ascii=False),
            data.get("source", ""),
            data.get("note", ""),
            "ok",
            collected_at,
        )
    )
    conn.commit()

    total = row_count(conn, "articles")
    conn.close()
    print(f"[OK] 最新数据导入完成:")
    print(f"  articles 新增 {inserted} 条，累计 {total} 条")
    print(f"  collect_log 已记录")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "migrate":
        # 从旧库迁移
        create_database()
        migrate_from_old()
    elif len(sys.argv) > 1 and sys.argv[1] == "create":
        create_database()
    else:
        print("用法:")
        print("  python db_schema.py create    — 仅建库（空 icv_news.db）")
        print("  python db_schema.py migrate   — 建库 + 从 news.db 迁移历史数据")
