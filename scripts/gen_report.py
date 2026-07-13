# -*- coding: utf-8 -*-
"""
日报生成脚本 — 从 SQLite 数据库读取数据。
用法：
  python gen_report.py <报告日期> <版本号> [窗口日期]
示例：
  python gen_report.py 2026-07-10 v1
  python gen_report.py 2026-07-10 v2 2026-07-09
"""
import os
import re
import sqlite3
import sys
from datetime import date, timedelta

BASE = r"E:\trae_solo\自动化监测智能网联汽车新闻"
TEMPLATE = os.path.join(BASE, "templates", "daily_template.html")
DB = os.path.join(BASE, "data", "icv_news.db")

WEEKDAYS = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日']

# 类别配置：(class_name, display_name, icon, accent_color)
CATS = [
    ("cat-policy",     "政策法规",  "&#9878;", "#c0392b"),
    ("cat-standards",  "标准动态",  "&#9881;", "#2980b9"),
    ("cat-investment", "投融资动态", "&#9733;", "#d4a843"),
    ("cat-technology",  "技术动态",  "&#9889;", "#27ae60"),
    ("cat-projects",   "项目动态",  "&#9874;", "#8e44ad"),
    ("cat-industry",   "行业动态",  "&#128200;","#e67e22"),
]

CAT_NAME_TO_CLS = {name: cls for cls, name, _, _ in CATS}
CAT_NAME_TO_COLOR = {name: color for _, name, _, color in CATS}


def first_paragraph(text, max_len=150):
    """提取第一句作为概要，在句号处断开"""
    if not text:
        return ""
    # 优先找句号
    for sep in "。！？":
        idx = text.find(sep)
        if 10 <= idx <= max_len:
            return text[:idx + 1]
    # 句号太远或没有 → 在最近的逗号/分号处断开
    if len(text) > max_len:
        cut = text[:max_len]
        for sep in "，；、":
            idx = cut.rfind(sep)
            if idx >= max_len * 0.4:
                return cut[:idx] + "。"
        return cut.rstrip("，、；：， ") + "。"
    return text


def load_from_db(window_date):
    """从数据库加载指定采集窗口的所有文章"""
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT title, source, category, publish_date, summary, overview, importance, url
           FROM articles
           WHERE window = ?
           ORDER BY importance DESC, category, publish_date DESC""",
        (window_date,)
    ).fetchall()
    conn.close()

    # 按分类分组
    cat_groups = {}
    for r in rows:
        cat_name = r["category"] or "其他"
        if cat_name not in cat_groups:
            cat_groups[cat_name] = []
        cat_groups[cat_name].append({
            "title": r["title"],
            "source": r["source"],
            "date": r["publish_date"],
            "summary": r["summary"] or "",
            "overview": r["overview"] or "",
            "url": r["url"],
            "importance": r["importance"] or 0,
        })

    # 统计各类别数量
    category_counts = {name: len(items) for name, items in cat_groups.items()}

    return {
        "total_news": len(rows),
        "category_counts": category_counts,
        "cat_groups": cat_groups,
    }


def build_stats_chips(data):
    """生成统计标签 <span class="stat-chip"></span>（仅显示各分类计数，不重复总条数）"""
    counts = data["category_counts"]
    chips = []
    for _, cat_name, _, color in CATS:
        cnt = counts.get(cat_name, 0)
        if cnt > 0:
            chips.append(f'<span class="stat-chip" style="color:{color}">{cat_name} {cnt}</span>')
    return "".join(chips)


def build_sections(data, window):
    """生成分类新闻区块"""
    cat_groups = data["cat_groups"]
    sections = []

    for cat_cls, cat_name, icon, color in CATS:
        items = cat_groups.get(cat_name, [])
        cnt = len(items)

        sections.append(f'\n  <!-- {cat_name} -->')
        sections.append(f'  <section class="cat-section {cat_cls}" aria-label="{cat_name}">')
        sections.append(f'    <div class="cat-header">')
        sections.append(f'      <span class="cat-icon">{icon}</span>')
        sections.append(f'      <h2 class="cat-title" style="color:{color}">{cat_name}</h2>')
        sections.append(f'      <span class="cat-count">{cnt} 条</span>')
        sections.append(f'    </div>')

        if not items:
            sections.append(f'    <div style="padding:32px 0;text-align:center;color:var(--text-muted);font-size:13px;background:var(--surface);border-radius:var(--radius-md);border:1px dashed var(--border);">本期采集窗口内（{window}）暂无更新</div>')
        else:
            for i, item in enumerate(items, 1):
                title = item["title"]
                url = item["url"]
                source = item["source"]
                date_str = item["date"]
                summary = first_paragraph(item["summary"])
                sections.append(f'    <article class="article-card">')
                sections.append(f'      <span class="article-num">{i}</span>')
                sections.append(f'      <div class="article-body">')
                sections.append(f'        <h3 class="article-title"><a href="{url}" target="_blank" rel="noopener noreferrer">{title}</a></h3>')
                sections.append(f'        <div class="article-meta">')
                sections.append(f'          <span>{source}</span>')
                sections.append(f'          <span class="hero-meta-div" style="width:3px;height:3px;border-radius:50%;background:var(--border);flex-shrink:0;display:inline-block"></span>')
                sections.append(f'          <span>{date_str}</span>')
                sections.append(f'        </div>')
                sections.append(f'        <p class="article-summary">{summary}</p>')
                sections.append(f'      </div>')
                sections.append(f'    </article>')

        sections.append(f'  </section>')

    return "\n".join(sections)


def main():
    if len(sys.argv) < 3:
        print("用法: python gen_report.py <报告日期> <版本号> [窗口日期]")
        print("示例: python gen_report.py 2026-07-10 v1")
        sys.exit(1)

    report_date = sys.argv[1]
    version = sys.argv[2]
    window = sys.argv[3] if len(sys.argv) > 3 else ""

    # 解析日期
    dt = date.fromisoformat(report_date)
    weekday = WEEKDAYS[dt.weekday()]
    if not window:
        # 所有日期统一：显示前一天采集的数据
        # 7月1日→6月30日采集, 7月2日→7月1日采集, ...
        window = (dt - timedelta(days=1)).isoformat()

    # 从数据库加载数据（按采集窗口匹配）
    data = load_from_db(window)
    total = data["total_news"]

    # 读取模板
    with open(TEMPLATE, encoding="utf-8") as f:
        html = f.read()

    # 替换日期和总数
    date_str = f"{dt.year}年{dt.month}月{dt.day}日 {weekday}"
    html = html.replace(
        '<span class="hero-date" id="hero-date">2026年7月6日 星期一</span>',
        f'<span class="hero-date" id="hero-date">{date_str}</span>'
    )
    html = html.replace(
        '<span id="hero-count">共 0 条资讯</span>',
        f'<span id="hero-count">共 {total} 条资讯</span>'
    )

    # 替换统计标签
    chips_html = build_stats_chips(data)
    html = html.replace('<div class="stat-summary"></div>', f'<div class="stat-summary">{chips_html}</div>')

    # 替换主体内容
    sections_html = build_sections(data, window)
    main_pattern = r'(<main[^>]*>.*?<div class="container">).*?(</div>\s*</main>)'
    html = re.sub(main_pattern, lambda m: m.group(1) + "\n" + sections_html + "\n" + m.group(2), html, flags=re.DOTALL)

    out_dir = os.path.join(BASE, "reports", "daily")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{report_date}_{version}.html")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[OK] 日报已生成 -> {out_path}")
    print(f"  date={report_date}, window={window}, total={total}, version={version}")
    print(f"  counts: {data['category_counts']}")


if __name__ == "__main__":
    main()
