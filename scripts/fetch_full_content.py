# -*- coding: utf-8 -*-
"""
从原文链接抓取正文全文，写入 icv_news.db 的 full_content 字段。
支持两种模式：
  1) backfill：扫描 DB 中 full_content == summary 的旧数据，逐条补抓
  2) batch：从 news_index.json 中提取 URL，抓取后写入 DB

用法：
  python scripts/fetch_full_content.py backfill [--limit N]   # 补抓历史（最多N条）
  python scripts/fetch_full_content.py batch                   # 抓 news_index.json 中的新文章
"""
import json
import os
import re
import sys
import time
import sqlite3
from datetime import datetime
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(BASE, "data", "icv_news.db")
IDX = os.path.join(BASE, "data", "news_index.json")

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/120.0.0.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}
TIMEOUT = 15
MAX_CONTENT = 2000  # 最多存 2000 字
FETCH_GAP = 1.5     # 每次请求间隔（秒）


def extract_text(html, url):
    """从 HTML 中提取正文文本。"""
    soup = BeautifulSoup(html, "html.parser")
    # 移除无用标签
    for tag in soup(["script", "style", "nav", "footer", "header",
                      "aside", "iframe", "noscript", "meta", "link"]):
        tag.decompose()
    # 尝试按正文容器提取
    candidates = []
    for selector in ["article", ".article-content", ".article", ".content",
                     "#content", "#article", ".post-content", ".news-content",
                     ".main-content", ".detail-content", ".rich_media_content",
                     "#js_content", ".article-body"]:
        el = soup.select_one(selector)
        if el:
            candidates.append(el.get_text(separator="\n", strip=True))
    if not candidates:
        # 兜底：取 body 文本
        body = soup.find("body")
        candidates.append(body.get_text(separator="\n", strip=True) if body else "")
    text = max(candidates, key=len) if candidates else ""
    # 清理空白
    text = re.sub(r"\s+", " ", text).strip()
    return text[:MAX_CONTENT]


def fetch_url(url):
    """抓取一个 URL，返回正文文本。失败返回空字符串。"""
    if not url or url.startswith("legacy_"):
        return ""
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        r.encoding = r.apparent_encoding or "utf-8"
        if r.status_code == 200:
            text = extract_text(r.text, url)
            if len(text) > 50:
                return text
        return ""
    except Exception as e:
        print(f"    [WARN] 请求失败: {e}")
        return ""


def update_db(conn, article_id, full_content):
    """更新 articles 表的 full_content。"""
    conn.execute(
        "UPDATE articles SET full_content = ? WHERE id = ? AND full_content != ?",
        (full_content, article_id, full_content)
    )
    return conn.total_changes > 0


def mode_backfill(limit=50):
    """扫描 DB 中 full_content == summary 的数据，补抓正文。"""
    conn = sqlite3.connect(DB)
    rows = conn.execute(
        """SELECT id, url, title, summary, full_content
           FROM articles
           WHERE full_content = summary
              OR full_content IS NULL
              OR length(full_content) < 100
           ORDER BY id DESC
           LIMIT ?""",
        (limit,)
    ).fetchall()
    print(f"[INFO] 待抓取 {len(rows)} 条")
    updated = 0
    for i, (aid, url, title, summary, _fc) in enumerate(rows, 1):
        print(f"  [{i}/{len(rows)}] #{aid} {title[:30]}...", end=" ")
        sys.stdout.flush()
        text = fetch_url(url)
        if text:
            update_db(conn, aid, text)
            updated += 1
            print(f"OK ({len(text)}字)")
        else:
            # 抓不到就保留原摘要
            print("SKIP (抓不到)")
        if i < len(rows):
            time.sleep(FETCH_GAP)
    conn.commit()
    total = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    fetched = conn.execute(
        "SELECT COUNT(*) FROM articles WHERE full_content != summary AND length(full_content) > 100"
    ).fetchone()[0]
    conn.close()
    print(f"\n[DONE] 更新 {updated} 条，当前 {fetched}/{total} 条有独立正文")


def mode_batch():
    """从 news_index.json 抓取新文章的正文，写入 DB。"""
    if not os.path.exists(IDX):
        print("[SKIP] news_index.json 不存在")
        return
    data = json.load(open(IDX, encoding="utf-8"))
    conn = sqlite3.connect(DB)
    updated = 0
    for item in data.get("news", []):
        url = item.get("url", "")
        title = item.get("title", "")
        # 查 DB 中是否已有
        row = conn.execute(
            "SELECT id, full_content FROM articles WHERE url = ?",
            (url,)
        ).fetchone()
        if not row:
            continue
        aid, existing_fc = row
        # 如果已有长正文就跳过
        if existing_fc and len(existing_fc) > 100:
            continue
        print(f"  [{title[:30]}]...", end=" ")
        sys.stdout.flush()
        text = fetch_url(url)
        if text:
            update_db(conn, aid, text)
            updated += 1
            print(f"OK ({len(text)}字)")
        else:
            print("SKIP")
        time.sleep(FETCH_GAP)
    conn.commit()
    conn.close()
    print(f"\n[DONE] batch 更新 {updated} 条")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法:")
        print("  python scripts/fetch_full_content.py backfill [--limit N]")
        print("  python scripts/fetch_full_content.py batch")
        sys.exit(1)

    mode = sys.argv[1]
    if mode == "backfill":
        limit = 50
        if "--limit" in sys.argv:
            idx = sys.argv.index("--limit")
            if idx + 1 < len(sys.argv):
                limit = int(sys.argv[idx + 1])
        mode_backfill(limit)
    elif mode == "batch":
        mode_batch()
    else:
        print(f"未知模式: {mode}")
