# -*- coding: utf-8 -*-
"""
将 data/public_accounts.json 的公众号文章归档：
1) 写入 data/news_index.json 顶层 public_accounts 键（与官方 news 数组并列，不污染5类计数）；
2) 入库 data/news.db 的 public_accounts 表（real_url UNIQUE 去重，可反复运行）。
用法：
  python scripts/import_public_accounts.py
"""
import json
import os
import sqlite3
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")
IDX = os.path.join(DATA, "news_index.json")
GZH = os.path.join(DATA, "public_accounts.json")
DB = os.path.join(BASE, "data", "news.db")


def main():
    gzh = json.load(open(GZH, encoding="utf-8"))
    items = gzh.get("items", [])

    # 1) 更新 news_index.json
    idx = json.load(open(IDX, encoding="utf-8"))
    idx["public_accounts"] = items
    idx["public_accounts_count"] = len(items)
    idx["public_accounts_window"] = gzh.get("window", "")
    with open(IDX, "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, indent=2)

    # 2) 入库 news.db
    conn = sqlite3.connect(DB)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS public_accounts (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            account      TEXT,
            title        TEXT,
            real_url     TEXT UNIQUE,
            url          TEXT,
            date         TEXT,
            summary      TEXT,
            keyword      TEXT,
            collected_at TEXT
        )
        """
    )
    ca = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    inserted = 0
    for it in items:
        try:
            conn.execute(
                """INSERT OR IGNORE INTO public_accounts
                   (account, title, real_url, url, date, summary, keyword, collected_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    it.get("account"),
                    it.get("title"),
                    it.get("real_url") or it.get("url"),
                    it.get("url"),
                    it.get("date"),
                    it.get("summary"),
                    it.get("keyword"),
                    ca,
                ),
            )
            if conn.total_changes and conn.execute("SELECT changes()").fetchone()[0]:
                inserted += 1
        except sqlite3.IntegrityError:
            pass
    conn.commit()
    total = conn.execute("SELECT COUNT(*) FROM public_accounts").fetchone()[0]
    conn.close()
    print(f"news_index.json 已加 public_accounts({len(items)} 条)")
    print(f"news.db.public_accounts 新增 {inserted} 条，累计 {total} 条")


if __name__ == "__main__":
    main()
