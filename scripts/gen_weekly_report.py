# -*- coding: utf-8 -*-
"""
周报HTML生成器。
用法：
    python scripts/gen_weekly_report.py [--week-start 2026-07-06] [--force]
输出：reports/weekly/YYYY-MM-DD（周一日期）.html
"""
import argparse
import os
import sqlite3
import sys
from datetime import date, datetime, timedelta

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(BASE, "data", "icv_news.db")
OUT_DIR = os.path.join(BASE, "reports", "weekly")

CAT_ORDER = ["政策法规", "标准动态", "投融资动态", "技术动态", "项目动态", "行业动态"]
CAT_LABELS = {
    "政策法规": "📜 政策法规", "标准动态": "📏 标准动态",
    "投融资动态": "💰 投融资动态", "技术动态": "🔧 技术动态",
    "项目动态": "🏗️ 项目动态", "行业动态": "📊 行业动态"
}


def get_week_range(monday: date):
    """返回 (周一, 周日) 的日期元组"""
    return monday, monday + timedelta(days=6)


def load_articles(monday: date):
    """从 DB 加载指定周的文章，按重要性降序排列"""
    sunday = monday + timedelta(days=6)
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT * FROM articles
        WHERE is_deleted=0
          AND publish_date >= ? AND publish_date <= ?
        ORDER BY importance DESC, publish_date DESC
    """, (monday.isoformat(), sunday.isoformat())).fetchall()
    conn.close()
    return rows


def load_past_weeks():
    """列出已存在的往期周报文件，按日期降序"""
    if not os.path.isdir(OUT_DIR):
        return []
    weeks = []
    for fname in sorted(os.listdir(OUT_DIR), reverse=True):
        if fname.endswith(".html"):
            d = fname.replace(".html", "")
            try:
                date.fromisoformat(d)
                weeks.append(d)
            except ValueError:
                pass
    return weeks


def generate_html(monday: date, articles: list):
    """生成周报 HTML 字符串"""
    sunday = monday + timedelta(days=6)
    week_label = f"{monday.isoformat()} ~ {sunday.isoformat()}"
    total = len(articles)

    # 分类聚合
    by_cat = {}
    for a in articles:
        c = a["category"] or "行业动态"
        by_cat.setdefault(c, []).append(a)

    # 排序分类
    ordered_cats = [c for c in CAT_ORDER if c in by_cat] + [c for c in by_cat if c not in CAT_ORDER]

    # 统计
    cat_counts = {c: len(v) for c, v in by_cat.items()}

    # 往期回顾
    past = load_past_weeks()
    past_items = ""
    for w in past:
        past_items += f'<li class="past-week-item" data-week="{w}">{w} 周报</li>\n'

    # 概览文本：提取重要性最高的3-5条
    top_articles = sorted(articles, key=lambda a: a["importance"], reverse=True)[:5]
    overview_items = ""
    for i, a in enumerate(top_articles):
        title = a["title"]
        overview_items += f"<li>{title}</li>\n"

    # 分类新闻
    cat_sections = ""
    for cat in ordered_cats:
        items = by_cat[cat][:8]  # 每类最多8条
        cat_sections += f'<section class="week-section">\n'
        cat_sections += f'<h2 class="section-title">{CAT_LABELS.get(cat, cat)}（{len(items)}条）</h2>\n'
        for a in items:
            summary = (a["summary"] or "")[:200]
            url = a["url"] or "#"
            cat_sections += f'<article class="article-card">\n'
            cat_sections += f'  <h3 class="article-title"><a href="{url}" target="_blank" rel="noopener noreferrer">{a["title"]}</a></h3>\n'
            cat_sections += f'  <div class="article-meta">{a["source"]} · {a["publish_date"]}</div>\n'
            if summary:
                cat_sections += f'  <p class="article-summary">{summary}</p>\n'
            cat_sections += f'</article>\n'
        cat_sections += f'</section>\n'

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>周报 | 智能网联汽车新闻动态</title>
<style>
:root {{
  --bg: #f5f7fa; --bg-card: #fff; --color-text: #1a1a2e; --color-text-secondary: #555;
  --color-text-muted: #999; --color-border: #e0e0e0; --color-accent: #2563eb;
  --radius: 12px; --font-sans: 'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif;
}}
* {{ box-sizing:border-box;margin:0;padding:0 }}
body {{ font-family:var(--font-sans);background:var(--bg);color:var(--color-text);line-height:1.6 }}
.container {{ max-width:860px;margin:0 auto;padding:32px 20px }}
.hero {{ background:linear-gradient(135deg,#1e3a5f,#2563eb);color:#fff;padding:40px 32px;border-radius:var(--radius);margin-bottom:24px }}
.hero h1 {{ font-size:1.75rem;margin-bottom:8px }}
.hero .sub {{ opacity:0.85;font-size:0.95rem }}
.stats {{ display:flex;gap:16px;flex-wrap:wrap;margin-bottom:24px }}
.stat {{ background:var(--bg-card);border-radius:var(--radius);padding:16px 20px;flex:1;min-width:120px;text-align:center;border:1px solid var(--color-border) }}
.stat .num {{ font-size:1.6rem;font-weight:700;color:var(--color-accent) }}
.stat .label {{ font-size:0.8rem;color:var(--color-text-muted);margin-top:4px }}
.section-title {{ font-size:1.15rem;font-weight:700;margin:24px 0 12px;color:#1e3a5f;border-left:4px solid #2563eb;padding-left:12px }}
.overview {{ background:var(--bg-card);border-radius:var(--radius);padding:20px 24px;border:1px solid var(--color-border);margin-bottom:20px }}
.overview h2 {{ font-size:1.1rem;margin-bottom:12px }}
.overview ul {{ padding-left:20px }}
.overview li {{ margin-bottom:6px;font-size:0.92rem;color:var(--color-text-secondary) }}
.article-card {{ background:var(--bg-card);border-radius:var(--radius);padding:16px 20px;border:1px solid var(--color-border);margin-bottom:10px;transition:box-shadow .2s }}
.article-card:hover {{ box-shadow:0 4px 12px rgba(0,0,0,.08);border-color:#2563eb }}
.article-title {{ font-size:0.95rem;font-weight:600;margin-bottom:4px }}
.article-title a {{ color:var(--color-text);text-decoration:none }}
.article-title a:hover {{ color:#2563eb }}
.article-meta {{ font-size:0.78rem;color:var(--color-text-muted);margin-bottom:4px }}
.article-summary {{ font-size:0.82rem;color:var(--color-text-secondary);line-height:1.55 }}
.past-weeks {{ background:var(--bg-card);border-radius:var(--radius);padding:16px 20px;border:1px solid var(--color-border);margin-top:32px }}
.past-weeks h2 {{ font-size:1.05rem;margin-bottom:10px }}
.past-weeks ul {{ list-style:none;padding:0 }}
.past-weeks li {{ padding:8px 12px;border-radius:6px;cursor:pointer;font-size:0.9rem;color:#2563eb }}
.past-weeks li:hover {{ background:#eef2ff }}
</style>
</head>
<body>
<div class="container">

<header class="hero">
  <h1>📋 智能网联汽车 · 周报</h1>
  <div class="sub">{week_label}</div>
</header>

<div class="stats">
  <div class="stat"><div class="num">{total}</div><div class="label">本周资讯</div></div>
  <div class="stat"><div class="num">{len(ordered_cats)}</div><div class="label">覆盖分类</div></div>
  <div class="stat"><div class="num">{len([a for a in articles if a['importance']>=4])}</div><div class="label">重要资讯(≥4)</div></div>
</div>

<section class="overview">
  <h2>📌 本周概览</h2>
  <ul>{overview_items}</ul>
</section>

<section>
  <h2 class="section-title">📰 本周重要新闻</h2>
  {cat_sections}
</section>

<section class="past-weeks">
  <h2>📚 往期回顾</h2>
  <ul>{past_items}</ul>
</section>

</div>
</body>
</html>"""
    return html


def generate(monday: date, force: bool = False):
    """生成周报并保存到文件"""
    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, f"{monday.isoformat()}.html")

    if os.path.exists(out_path) and not force:
        print(f"[SKIP] 已存在: {out_path}")
        return out_path

    articles = load_articles(monday)
    if not articles:
        print(f"[WARN] {monday.isoformat()} 周无数据，不生成周报")
        return None

    html = generate_html(monday, articles)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    total = len(articles)
    print(f"[OK] 周报已生成 -> {out_path}（{total}条）")
    return out_path


def get_this_week_monday() -> date:
    """获取本周一的日期"""
    today = date.today()
    return today - timedelta(days=today.weekday())


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="生成智能网联汽车新闻周报")
    p.add_argument("--week-start", help="周一日期 (如 2026-07-06)", default=None)
    p.add_argument("--force", action="store_true", help="强制覆盖已有报告")
    args = p.parse_args()

    if args.week_start:
        monday = date.fromisoformat(args.week_start)
    else:
        monday = get_this_week_monday()

    generate(monday, force=args.force)
