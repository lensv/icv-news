# -*- coding: utf-8 -*-
"""
将 data/news_index.json 的数据导入 icv_news.db（新统一数据库）。
- 写入 articles 表（按 url 去重）
- 写入 collect_log 表（记录本次采集运行日志）

用法：
  python scripts/import_news_to_db.py
"""
import json
import os
import shutil
import sqlite3
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IDX = os.path.join(BASE, "data", "news_index.json")
DB = os.path.join(BASE, "data", "icv_news.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    title         TEXT    NOT NULL,
    source        TEXT,
    source_type   TEXT    DEFAULT 'media',
    url           TEXT    UNIQUE,
    url_original  TEXT,
    publish_date  DATE,
    collected_at  DATETIME,
    category      TEXT,
    summary       TEXT,
    full_content  TEXT,
    is_wechat     INTEGER DEFAULT 0,
    window        TEXT,
    importance    INTEGER DEFAULT 0,
    keywords      TEXT,
    overview      TEXT,
    is_deleted    INTEGER DEFAULT 0,
    needs_review  INTEGER DEFAULT 0,
    review_reason TEXT
);
CREATE TABLE IF NOT EXISTS collect_log (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    run_date            DATE,
    version             TEXT,
    window              TEXT,
    total_articles      INTEGER,
    total_public_accounts INTEGER,
    categories          TEXT,
    source_summary      TEXT,
    note                TEXT,
    status              TEXT DEFAULT 'ok',
    error_msg           TEXT,
    created_at          DATETIME
);
CREATE INDEX IF NOT EXISTS idx_articles_url ON articles(url);
CREATE INDEX IF NOT EXISTS idx_articles_category ON articles(category);
CREATE INDEX IF NOT EXISTS idx_articles_publish_date ON articles(publish_date);
"""


def guess_source_type(source):
    if not source:
        return "media", 0
    if "公众号" in source:
        return "wechat", 1
    if any(kw in source for kw in ["工信部", "公安部", "交通", "标准委",
                                    "国标", "国务院", "网信办"]):
        return "gov", 0
    if any(kw in source for kw in ["华为", "小鹏", "蔚来", "百度",
                                    "小马", "地平线", "东风", "上汽"]):
        return "enterprise", 0
    return "media", 0


def main():
    with open(IDX, encoding="utf-8") as f:
        data = json.load(f)

    window = data.get("window", "")
    collected_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = sqlite3.connect(DB)
    conn.executescript(SCHEMA)

    # ---- 写入 articles（带源优先级检查）----
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from source_priority import source_tier

    inserted = 0
    replaced = 0
    skipped_tier = 0
    for item in data.get("news", []):
        title = item.get("title", "")
        url = item.get("url", "")
        url_original = item.get("url_original") or item.get("url", "")
        source = item.get("source", "")
        category = item.get("name") or item.get("cat", "")
        summary = item.get("summary", "")
        date = item.get("date", "")
        overview = item.get("overview", "")
        window = item.get("window", "") or data.get("window", "")

        source_type, is_wechat = guess_source_type(source)
        new_tier = source_tier(source, url)

        # 查重：同 title+window 时，比较来源梯队
        if title and window:
            existing = conn.execute(
                "SELECT id, source, url FROM articles WHERE title = ? AND window = ? AND is_deleted = 0",
                (title, window)
            ).fetchone()
            if existing:
                ex_tier = source_tier(existing["source"], existing["url"])
                if new_tier >= ex_tier:
                    # 新来源不如已存在的，跳过
                    skipped_tier += 1
                    continue
                else:
                    # 新来源更优：软删除旧的
                    conn.execute(
                        "INSERT INTO articles_deleted_audit (id,title,source,url,category,publish_date,window,deleted_at,delete_reason,original_row_json) "
                        "SELECT id,title,source,url,category,publish_date,window,datetime('now','localtime'),"
                        "'REPLACED_BY_TIER1: 被更高梯队源替换',json_object('title',title,'source',source,'url',url) "
                        "FROM articles WHERE id = ?",
                        (existing["id"],)
                    )
                    conn.execute("UPDATE articles SET is_deleted = 1 WHERE id = ?", (existing["id"],))
                    replaced += 1

        try:
            conn.execute(
                """INSERT OR IGNORE INTO articles
                   (title, source, source_type, url, url_original, publish_date, collected_at,
                    category, summary, full_content, is_wechat, window, overview)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (title, source, source_type, url, url_original, date, collected_at,
                 category, summary, summary, is_wechat, window, overview)
            )
            if conn.total_changes and conn.execute("SELECT changes()").fetchone()[0]:
                inserted += 1
        except sqlite3.IntegrityError:
            pass

    if skipped_tier or replaced:
        print(f"  [tier-priority] 新增 {inserted}，替换 {replaced} 旧记录，跳过 {skipped_tier} 低梯队")

    # ---- 写入 collect_log ----
    categories = data.get("category_counts", {})
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

    total = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    conn.close()

    print(f"导入完成：articles 新增 {inserted} 条，跳过(已存在) {len(data.get('news',[])) - inserted} 条。")
    print(f"数据库累计：{total} 条  ->  {DB}")

    # ---- 自动补摘要 ----
    from fill_missing_summaries import main as fill_summaries
    sys.argv = [sys.argv[0]]
    if window:
        sys.argv += ["--window", window]
    fill_summaries()

    # ---- URL 健康检查（自动软删除失效链接）----
    print("\n[STEP] URL 健康检查...")
    from check_urls_health import run as check_urls
    sys.argv = [sys.argv[0]]
    if window:
        sys.argv += ["--window", window, "--soft-delete-broken"]
    else:
        sys.argv += ["--soft-delete-broken"]
    try:
        check_urls()
    except SystemExit:
        pass  # check_urls_health 在有失效时 sys.exit(1)
    except Exception as e:
        print(f"[WARN] URL 检查异常: {e}")

    # ---- 生成每日快照 ----
    version = data.get("version", "")
    today = datetime.now().strftime("%Y-%m-%d")
    snapshot_name = f"icv_news_{today}_{version}.db"
    snapshot_path = os.path.join(os.path.dirname(DB), snapshot_name)
    try:
        shutil.copy2(DB, snapshot_path)
        print(f"快照已保存: {snapshot_path}")
    except Exception as e:
        print(f"[WARN] 快照保存失败: {e}")


if __name__ == "__main__":
    main()
