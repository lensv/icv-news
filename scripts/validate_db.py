# -*- coding: utf-8 -*-
"""
数据库质量验证脚本。
检查：重复文章、空分类、分类分布异常、未分类文件、publish_date 为空。
用法: python scripts/validate_db.py
退出码: 0=正常, 1=有问题
"""
import json, os, sqlite3, sys
from datetime import date, timedelta

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(BASE, "data", "icv_news.db")

def validate():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    issues = []

    # 1. 重复检查
    dups = conn.execute("""
        SELECT SUBSTR(title,1,40) as t, COUNT(*) as c 
        FROM articles WHERE is_deleted = 0 
        GROUP BY t HAVING c > 1
    """).fetchall()
    if dups:
        issues.append(f"发现 {len(dups)} 组重复文章")
        for t, c in dups[:5]:
            issues.append(f"  ({c}x) {t}...")

    # 2. 空分类检查
    empty = conn.execute(
        "SELECT COUNT(*) FROM articles WHERE is_deleted = 0 AND (category IS NULL OR category = '')"
    ).fetchone()[0]
    if empty:
        issues.append(f"发现 {empty} 条空分类文章")

    # 3. 行业动态比例过高检查 (>30% 告警)
    total = conn.execute("SELECT COUNT(*) FROM articles WHERE is_deleted = 0").fetchone()[0]
    industry = conn.execute(
        "SELECT COUNT(*) FROM articles WHERE is_deleted = 0 AND category = '行业动态'"
    ).fetchone()[0]
    if total > 10 and industry / total > 0.30:
        issues.append(f"行业动态占比过高: {industry}/{total} = {industry/total:.1%}")

    # 4. 未分类文件存在检查
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    unclassified_path = os.path.join(BASE, "data", f"unclassified_{yesterday}.json")
    if os.path.exists(unclassified_path):
        with open(unclassified_path, encoding="utf-8") as f:
            uc = json.load(f)
        issues.append(f"有 {len(uc) if isinstance(uc, list) else '?'} 条未分类文章待审核: {unclassified_path}")

    # 5. publish_date 为空检查
    null_date = conn.execute(
        "SELECT COUNT(*) FROM articles WHERE is_deleted = 0 AND (publish_date IS NULL OR publish_date = '')"
    ).fetchone()[0]
    if null_date:
        issues.append(f"发现 {null_date} 条 missing publish_date")

    # 6. 摘要缺失检查
    missing_summary = conn.execute(
        "SELECT COUNT(*) FROM articles WHERE is_deleted = 0 AND (summary IS NULL OR summary = '')"
    ).fetchone()[0]
    if missing_summary:
        issues.append(f"发现 {missing_summary} 条缺失摘要")

    # 7. 分类分布统计
    if total > 0:
        print(f"\n总有效文章: {total}")
        cats = conn.execute(
            "SELECT category, COUNT(*) as cnt FROM articles WHERE is_deleted = 0 GROUP BY category ORDER BY cnt DESC"
        ).fetchall()
        for r in cats:
            print(f"  {r['category']}: {r['cnt']} ({r['cnt']/total*100:.0f}%)")

    conn.close()

    if issues:
        print("\n⚠ 发现问题:")
        for i in issues:
            print(f"  {i}")
        return False
    else:
        print("\n✅ 数据库验证通过，无异常")
        return True

if __name__ == "__main__":
    ok = validate()
    sys.exit(0 if ok else 1)
