# -*- coding: utf-8 -*-
"""
智能网联汽车 — 本周核心周报生成器
用法:
  python scripts/generate_weekly.py                    # 生成本周周报
  python scripts/generate_weekly.py 2026-07-06 2026-07-10  # 指定日期范围
"""
import json
import os
import sqlite3
import sys
from datetime import date, datetime, timedelta

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(BASE, "data", "icv_news.db")
OUT_DIR = os.path.join(BASE, "reports", "weekly")

WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

def first_paragraph(text, max_len=150):
    """提取第一句作为概要，在句号处断开"""
    if not text:
        return ""
    for sep in "。！？":
        idx = text.find(sep)
        if 10 <= idx <= max_len:
            return text[:idx + 1]
    if len(text) > max_len:
        cut = text[:max_len]
        for sep in "，；、":
            idx = cut.rfind(sep)
            if idx >= max_len * 0.4:
                return cut[:idx] + "。"
        return cut.rstrip("，、；：， ") + "。"
    return text

CAT_COLORS = {
    "政策法规": "#c0392b", "标准动态": "#2980b9", "投融资动态": "#d4a843",
    "技术动态": "#27ae60", "项目动态": "#8e44ad", "行业动态": "#e67e22",
}
CAT_ICONS = {
    "政策法规": "📜", "标准动态": "⚙️", "投融资动态": "⭐",
    "技术动态": "⚡", "项目动态": "🔧", "行业动态": "📈",
}


def load_weekly_data(date_from, date_to):
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    articles = conn.execute(
        """SELECT DISTINCT title, source, source_type, category, publish_date,
                  importance, summary, full_content, url, is_wechat, overview
           FROM articles
           WHERE publish_date >= ? AND publish_date <= ?
           ORDER BY importance DESC, publish_date DESC""",
        (date_from, date_to)
    ).fetchall()

    # 按分类分组
    cat_groups = {}
    for r in articles:
        cat = r["category"]
        if cat not in cat_groups:
            cat_groups[cat] = []
        cat_groups[cat].append(dict(r))

    conn.close()
    return {
        "total": len(articles),
        "categories": {c: len(v) for c, v in sorted(cat_groups.items(), key=lambda x: -len(x[1]))},
        "cat_groups": cat_groups,
        "articles": [dict(r) for r in articles],
        "date_from": date_from,
        "date_to": date_to,
    }


def render(data):
    from_ = data["date_from"]
    to_ = data["date_to"]
    week_label = f"{from_} ~ {to_}"

    # 格式化日期显示
    d1 = datetime.strptime(from_, "%Y-%m-%d")
    d2 = datetime.strptime(to_, "%Y-%m-%d")
    date_range_str = f"{d1.year}年{d1.month}月{d1.day}日-{d2.month}月{d2.day}日"

    # 生成统计标签
    total = data["total"]
    cat_count = len(data["categories"])
    cats_sorted = sorted(data["categories"].items(), key=lambda x: -x[1])
    chips = []
    for cat_name, cnt in cats_sorted:
        color = CAT_COLORS.get(cat_name, "#94a3b8")
        chips.append(f'<span class="stat-chip" style="color:{color}">{cat_name} {cnt}</span>')
    chips_html = "".join(chips)

    # 按分类生成新闻区块
    cat_order = ["政策法规", "标准动态", "投融资动态", "技术动态", "项目动态", "行业动态"]
    sections_html = ""
    for cat in cat_order:
        items = data["cat_groups"].get(cat, [])
        if not items:
            continue
        color = CAT_COLORS.get(cat, "#94a3b8")
        icon = CAT_ICONS.get(cat, "📌")
        count = min(len(items), 5)

        articles_html = ""
        for i, a in enumerate(items[:5]):  # 每类最多5条
            summary = first_paragraph(a.get("summary", ""), 100)
            url = a['url']
            articles_html += f"""
        <article class="article-card">
          <span class="article-num">{i+1}</span>
          <div class="article-body">
            <h4 class="article-title"><a href="{url}" target="_blank" rel="noopener noreferrer">{a['title']}</a></h4>
            <div class="article-meta">
              <span class="article-source">{a['source']}</span>
              <span class="article-date">{a['publish_date']}</span>
            </div>
            {f'<p class="article-summary">{summary}</p>' if summary else ''}
          </div>
        </article>"""

        sections_html += f"""
    <div class="cat-section">
      <div class="cat-header">
        <span class="cat-icon">{icon}</span>
        <h3 class="cat-title" style="color:{color}">{cat}</h3>
        <span class="cat-count">{count} 条</span>
      </div>
      {articles_html}
    </div>"""

    # 生成概览 — 扁平列表
    overview_lines = []
    for cat in cat_order:
        items = data["cat_groups"].get(cat, [])
        if not items:
            continue
        overview_lines.append(f'      <div class="overview-cat-title">{cat}</div>')
        for a in items[:5]:
            overview = a.get("overview") or a["title"]
            overview_lines.append(f'      <li>{overview}</li>')
    overview_html = "\n".join(overview_lines)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>智能网联汽车 · 本周核心周报</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=Outfit:wght@300;400;500;600;700&family=Noto+Sans+SC:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
:root{{
  --bg:#f8f6f2;--surface:#fff;--accent:#c27803;
  --accent-dim:rgba(194,120,3,0.10);--accent-light:rgba(194,120,3,0.04);
  --text:#1f1b16;--text-secondary:#6b6258;--text-muted:#a89f94;
  --border:#e8e2d9;--border-light:#ddd6cb;
  --radius-sm:6px;--radius-md:10px;--radius-lg:14px;
  --font-display:'DM Serif Display',serif;--font-sans:'Outfit',sans-serif;
  --font-body:'Noto Sans SC','Outfit',sans-serif;
  --shadow-sm:0 1px 2px rgba(31,27,22,0.05);--shadow-hover:0 4px 16px rgba(31,27,22,0.08);
}}
html{{font-size:16px;scroll-behavior:smooth;-webkit-font-smoothing:antialiased}}
body{{font-family:var(--font-body);background:var(--bg);color:var(--text);line-height:1.7}}
.container{{max-width:880px;margin:0 auto;padding:0 24px}}

/* Hero */
.hero{{padding:40px 0 24px}}
.hero-badge{{
  display:inline-flex;align-items:center;gap:6px;
  padding:4px 14px;border-radius:100px;
  background:var(--accent-dim);border:1px solid rgba(194,120,3,0.18);
  font-family:var(--font-sans);font-size:0.7rem;font-weight:600;
  color:var(--accent);letter-spacing:2px;text-transform:uppercase;
  margin-bottom:12px;
}}
.hero-badge-dot{{width:5px;height:5px;border-radius:50%;background:var(--accent)}}
.hero-title{{
  font-family:var(--font-display);font-size:clamp(1.3rem,3.5vw,1.8rem);
  color:var(--text);font-weight:400;line-height:1.3;margin-bottom:6px;
}}
.hero-meta{{font-size:0.82rem;color:var(--text-muted);margin-bottom:14px}}
.stat-summary{{display:flex;gap:6px;flex-wrap:wrap;justify-content:center}}
.stat-chip{{
  padding:3px 12px;border-radius:100px;
  background:var(--accent-light);border:1px solid var(--border);
  font-family:var(--font-sans);font-size:0.7rem;color:var(--text-secondary);
}}

/* 概览 */
.overview-section{{padding:20px 0 8px;border-bottom:1px solid var(--border);margin-bottom:4px}}
.overview-header{{display:flex;align-items:center;gap:10px;margin-bottom:8px}}
.overview-title{{font-family:var(--font-display);font-size:1rem;font-weight:600;color:var(--text);letter-spacing:0.2px}}
.overview-line{{flex:1;height:1px;background:linear-gradient(90deg,var(--border),transparent)}}
.overview-cat-title{{font-family:var(--font-sans);font-size:0.82rem;font-weight:600;color:var(--text);margin-top:6px;margin-bottom:1px}}
.overview-list{{list-style:none;padding:0;margin:0}}
.overview-list li{{font-size:0.8rem;color:var(--text-secondary);line-height:1.55;padding-left:14px;position:relative}}
.overview-list li::before{{content:'';position:absolute;left:3px;top:7px;width:4px;height:4px;border-radius:50%;background:var(--text-muted)}}

/* 分类新闻 */
.section{{padding:24px 0 8px}}
.section-header{{display:flex;align-items:center;gap:8px;margin-bottom:12px;padding-bottom:8px;border-bottom:1px solid var(--border)}}
.section-icon{{font-size:15px}}
.section-title{{font-family:var(--font-sans);font-size:0.9rem;font-weight:600;color:var(--text);letter-spacing:0.2px}}
.cat-section{{margin-bottom:24px}}
.cat-header{{display:flex;align-items:center;gap:8px;margin-bottom:10px;padding-bottom:8px;border-bottom:1px solid var(--border)}}
.cat-icon{{font-size:15px;flex-shrink:0}}
.cat-title{{font-family:var(--font-sans);font-size:0.9rem;font-weight:600;letter-spacing:0.2px}}
.cat-count{{font-family:var(--font-sans);font-size:0.65rem;font-weight:500;color:var(--text-muted);background:var(--bg);padding:2px 10px;border-radius:100px;margin-left:auto}}

/* 文章卡片 */
.article-card{{display:flex;gap:12px;padding:12px 14px;background:var(--surface);border:1px solid var(--border);margin-bottom:8px;border-radius:var(--radius-md);transition:all 0.2s ease;position:relative;overflow:hidden}}
.article-card:hover{{border-color:transparent;box-shadow:var(--shadow-hover)}}
.article-card::before{{content:'';position:absolute;left:0;top:0;bottom:0;width:3px;opacity:0;transition:opacity 0.2s;border-radius:0 2px 2px 0}}
.article-card:hover::before{{opacity:1}}
.article-num{{font-family:var(--font-sans);font-size:0.8rem;font-weight:600;color:var(--text-muted);min-width:22px;text-align:center;padding-top:1px;flex-shrink:0}}
.article-body{{flex:1;min-width:0}}
.article-title{{font-size:0.88rem;font-weight:500;color:var(--text);line-height:1.5;margin-bottom:2px}}
.article-title a{{color:inherit;text-decoration:none}}
.article-title a:hover{{color:var(--accent)}}
.article-meta{{display:flex;align-items:center;gap:8px;flex-wrap:wrap;font-size:0.72rem;color:var(--text-muted);margin-bottom:4px}}
.article-source{{}}
.article-date{{font-family:var(--font-sans)}}
.article-summary{{font-size:0.78rem;color:var(--text-secondary);line-height:1.6;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}}

/* Footer */
.footer{{text-align:center;padding:24px 0 32px;border-top:1px solid var(--border)}}
.footer p{{font-size:0.7rem;color:var(--text-muted)}}

@media(max-width:640px){{
  .hero{{padding:28px 0 16px}}
  .container{{padding:0 16px}}
  .article-card{{padding:10px 12px}}
  .article-title{{font-size:0.85rem}}
}}
</style>
</head>
<body>

<div class="container">

  <!-- Hero -->
  <header class="hero">
    <div class="hero-badge"><span class="hero-badge-dot"></span>周报</div>
    <h1 class="hero-title">智能网联汽车新闻</h1>
    <p class="hero-meta"><span class="hero-date">{date_range_str}</span></p>
    <div class="stat-summary">{chips_html}</div>
  </header>

  <!-- 本周概览 -->
  <div class="overview-section">
    <div class="overview-header">
      <h2 class="overview-title">本周概览</h2>
      <div class="overview-line"></div>
    </div>
    <div class="overview-list">
      {overview_html}
    </div>
  </div>

  <!-- 本周重要新闻 -->
  <div class="section">
    <div class="section-header">
      <span class="section-icon">🔥</span>
      <h2 class="section-title">本周重要新闻</h2>
      <div class="overview-line" style="flex:1;height:1px;background:linear-gradient(90deg,var(--border),transparent)"></div>
    </div>
    {sections_html}
  </div>

  <!-- Footer -->
  <footer class="footer">
    <p>智能网联汽车新闻自动化监测 · 每周核心周报</p>
  </footer>

</div>

</body>
</html>"""
    return html


def main():
    if len(sys.argv) >= 3:
        date_from = sys.argv[1]
        date_to = sys.argv[2]
    else:
        today = date.today()
        monday = today - timedelta(days=today.weekday())
        date_from = monday.isoformat()
        date_to = today.isoformat()

    data = load_weekly_data(date_from, date_to)
    if data["total"] < 3:
        date_from = (date.today() - timedelta(days=7)).isoformat()
        date_to = date.today().isoformat()
        data = load_weekly_data(date_from, date_to)

    os.makedirs(OUT_DIR, exist_ok=True)
    html = render(data)
    # 用 date_to 所在的周作为文件名，而不是今天
    d = datetime.strptime(date_to, "%Y-%m-%d").date()
    week_num = d.isocalendar()[1]
    out_path = os.path.join(OUT_DIR, f"{d.year}-W{week_num:02d}.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[OK] 周报已生成 -> {out_path}")
    print(f"  范围: {data['date_from']} ~ {data['date_to']}, 共 {data['total']} 条")


if __name__ == "__main__":
    main()
