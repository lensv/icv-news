# -*- coding: utf-8 -*-
"""
生成 GitHub Pages 静态 index.html
- 从 DB 读取所有 is_deleted=0 的文章
- 按日期 (window) 分组为日报
- 按 ISO 周 (周一~周日) 分组为周报
- 烘焙到 HTML 模板中，部署后无需后端即可显示
"""
import datetime
import json
import os
import re
import sqlite3
import sys
from collections import defaultdict

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(BASE, "data", "icv_news.db")
TEMPLATE = os.path.join(BASE, "web", "static_index_template.html")
OUTPUT = os.path.join(BASE, "reports", "index.html")

CAT_ORDER = ['政策法规', '标准动态', '投融资动态', '技术动态', '项目动态', '行业动态']


def fetch_all():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT title, source, source_type, url, publish_date, window,
               category, summary, importance, overview
        FROM articles
        WHERE is_deleted = 0
        ORDER BY publish_date DESC, id ASC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def build_daily(articles):
    """按 window 分组（window = 前一天采集日期 = 日报要展示的日期）"""
    daily = {}
    for a in articles:
        wd = a.get('window') or a.get('publish_date') or ''
        if not wd:
            continue
        daily.setdefault(wd, []).append(a)
    out = {}
    for wd, items in daily.items():
        cats = defaultdict(int)
        for a in items:
            c = a.get('category') or ''
            cats[c] += 1
        out[wd] = {
            'total': len(items),
            'categories': dict(cats),
            'articles': items,
        }
    return out


def build_weekly(articles):
    """按 ISO 周分组（周一~周日）"""
    by_monday = defaultdict(list)
    for a in articles:
        wd = a.get('window') or a.get('publish_date') or ''
        if not wd:
            continue
        try:
            d = datetime.datetime.strptime(wd, "%Y-%m-%d")
        except ValueError:
            continue
        monday = d - datetime.timedelta(days=d.weekday())
        by_monday[monday.strftime("%Y-%m-%d")].append(a)
    out = {}
    for monday, items in by_monday.items():
        cats = defaultdict(int)
        for a in items:
            c = a.get('category') or ''
            cats[c] += 1
        sunday_dt = datetime.datetime.strptime(monday, "%Y-%m-%d") + datetime.timedelta(days=6)
        sunday = sunday_dt.strftime("%Y-%m-%d")
        out[monday] = {
            'week_start': monday,
            'week_end': sunday,
            'total': len(items),
            'categories': dict(cats),
            'articles': items,
        }
    return out


def render_html(daily, weekly):
    with open(TEMPLATE, encoding="utf-8") as f:
        tmpl = f.read()
    data = {'daily': daily, 'weekly': weekly}
    data_json = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    out = tmpl.replace('__INJECTED_DATA__', data_json)
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        f.write(out)
    print(f"生成: {OUTPUT}")
    print(f"  日报: {len(daily)} 天")
    print(f"  周报: {len(weekly)} 周")
    print(f"  今日: {datetime.date.today()}")


if __name__ == "__main__":
    articles = fetch_all()
    daily = build_daily(articles)
    weekly = build_weekly(articles)
    render_html(daily, weekly)
