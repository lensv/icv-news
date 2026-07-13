# -*- coding: utf-8 -*-
"""
概览文本生成器。
从新闻标题/摘要中提炼简短的概览条目，写入 news_index.json 和数据库。

用法:
  python scripts/generate_overview.py              # 处理所有新闻
  python scripts/generate_overview.py --only-null   # 只处理 overview 为空的数据
"""
import json
import os
import re
import sqlite3
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON_PATH = os.path.join(BASE, "data", "news_index.json")
DB_PATH = os.path.join(BASE, "data", "icv_news.db")


def generate_overview(title, source, summary):
    """
    用完整的标题作为一句话概览，不做截断。
    标题本身就是对新闻内容的一句话总结。
    """
    title = (title or "").strip()
    if not title:
        return "（暂无标题）"
    return title


def update_json(item, overview):
    """更新 news_index.json 的单个条目"""
    item["overview"] = overview
    return item


def update_db(url, overview):
    """更新数据库的 overview 字段"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE articles SET overview = ? WHERE url = ?", (overview, url))
    conn.commit()
    conn.close()


def process(only_null=False, force=False):
    # 读取 JSON
    with open(JSON_PATH, encoding="utf-8") as f:
        data = json.load(f)

    news = data.get("news", [])
    json_count = 0

    for item in news:
        if only_null and item.get("overview"):
            continue

        overview = generate_overview(
            item.get("title", ""),
            item.get("source", ""),
            item.get("summary", "")
        )
        item["overview"] = overview

        url = item.get("url", "")
        if url:
            update_db(url, overview)
        json_count += 1

    # 写回 JSON
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # 处理数据库中不在 JSON 的条目（历史数据）
    conn = sqlite3.connect(DB_PATH)
    if force:
        db_cursor = conn.execute(
            "SELECT url, title, source, summary FROM articles"
        )
    else:
        db_cursor = conn.execute(
            "SELECT url, title, source, summary FROM articles WHERE overview IS NULL"
        )
    db_rows = db_cursor.fetchall()
    db_count = 0
    for url, title, source, summary in db_rows:
        overview = generate_overview(title or "", source or "", summary or "")
        conn.execute("UPDATE articles SET overview = ? WHERE url = ?", (overview, url))
        db_count += 1
    conn.commit()
    conn.close()

    print(f"[OK] 已处理 {json_count + db_count} 条新闻的概览文本")
    print(f"  JSON: {json_count} 条, 数据库: {db_count} 条")
    print(f"  总计: {len(news)} 条 (JSON) + {db_count} 条 (数据库)")

    # 打印样本
    conn2 = sqlite3.connect(DB_PATH)
    samples = conn2.execute(
        "SELECT overview FROM articles WHERE overview IS NOT NULL LIMIT 6"
    ).fetchall()
    conn2.close()
    print(f"\n  样本:")
    for row in samples:
        print(f"  • {row[0]}")


if __name__ == "__main__":
    only_null = "--only-null" in sys.argv
    force = "--force" in sys.argv
    process(only_null=only_null, force=force)
