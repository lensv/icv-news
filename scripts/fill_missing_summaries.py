# -*- coding: utf-8 -*-
"""
填充缺失摘要 — 对 full_content 或 overview 为空的文章从已有数据生成摘要。
在每日采集流程的 import_news_to_db 之后调用，确保入库文章都有摘要。

用法:
  python scripts/fill_missing_summaries.py [--window YYYY-MM-DD]
"""
import os, sys, sqlite3, re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(BASE, "data", "icv_news.db")


def extract_summary(text, max_chars=200):
    """从正文提取前200字作为摘要"""
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= max_chars:
        return text
    # 截断到完整句子
    cut = text[:max_chars]
    last_punct = max(cut.rfind("。"), cut.rfind("！"), cut.rfind("？"), cut.rfind("."))
    if last_punct > 50:
        return cut[:last_punct + 1]
    return cut + "…"


def main():
    window = None
    if "--window" in sys.argv:
        idx = sys.argv.index("--window")
        window = sys.argv[idx + 1]

    conn = sqlite3.connect(DB)
    where = "WHERE is_deleted = 0 AND (summary IS NULL OR summary = '')"
    params = []
    if window:
        where += " AND window = ?"
        params.append(window)

    rows = conn.execute(
        f"SELECT id, title, summary, full_content, overview FROM articles {where}",
        params
    ).fetchall()

    if not rows:
        print("[OK] 无缺失摘要的文章")
        conn.close()
        return

    print(f"[INFO] {len(rows)} 条文章缺失摘要，自动生成中…")
    updated = 0
    deleted = 0
    for aid, title, summary, full_content, overview in rows:
        text = full_content or overview or ""
        new_summary = extract_summary(text)
        if new_summary:
            conn.execute("UPDATE articles SET summary = ? WHERE id = ?", (new_summary, aid))
            updated += 1
            print(f"  ✅ #{aid} {title[:30]}… OK ({len(new_summary)}字)")
        else:
            # 无内容可生成摘要 → 软删除文章（疑似假新闻/无效来源）
            conn.execute(
                "INSERT INTO articles_deleted_audit (id,title,source,url,category,publish_date,window,deleted_at,delete_reason,original_row_json) "
                "SELECT id,title,source,url,category,publish_date,window,datetime('now','localtime'),"
                "'NO_SUMMARY: 无法从正文/概览生成摘要，疑似无效新闻来源',"
                "json_object('title',title,'source',source,'url',url) "
                "FROM articles WHERE id = ?",
                (aid,)
            )
            conn.execute("UPDATE articles SET is_deleted = 1 WHERE id = ?", (aid,))
            deleted += 1
            print(f"  ❌ #{aid} {title[:30]}… 已删除（无正文也无概览）")

    conn.commit()
    conn.close()
    print(f"\n[DONE] 填充 {updated} 条摘要，删除 {deleted} 条无效新闻")


if __name__ == "__main__":
    main()
