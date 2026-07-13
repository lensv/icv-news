# -*- coding: utf-8 -*-
"""
智能网联汽车新闻 — Web 查询界面
Flask 后端，提供 API + 前端页面
"""
import csv
import io
import json
import os
import sqlite3
from datetime import date, datetime, timedelta

from flask import Flask, jsonify, request, render_template, send_file

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(BASE, "data", "icv_news.db")

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True


def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


# ============================================================
# API Routes
# ============================================================

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/stats")
def api_stats():
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    # 分类分布
    cats = conn.execute(
        "SELECT category, COUNT(*) as cnt FROM articles GROUP BY category ORDER BY cnt DESC"
    ).fetchall()
    # 来源分布
    sources = conn.execute(
        "SELECT source_type, COUNT(*) as cnt FROM articles GROUP BY source_type ORDER BY cnt DESC"
    ).fetchall()
    # 评分分布
    scores = conn.execute(
        "SELECT importance, COUNT(*) as cnt FROM articles WHERE importance > 0 GROUP BY importance ORDER BY importance DESC"
    ).fetchall()
    # 日期范围
    date_range = conn.execute(
        "SELECT MIN(publish_date), MAX(publish_date) FROM articles"
    ).fetchone()
    # 公众号数量
    wechat = conn.execute(
        "SELECT COUNT(*) FROM articles WHERE is_wechat = 1"
    ).fetchone()[0]
    conn.close()

    return jsonify({
        "total": total,
        "categories": {r["category"]: r["cnt"] for r in cats},
        "sources": {r["source_type"]: r["cnt"] for r in sources},
        "scores": {r["importance"]: r["cnt"] for r in scores},
        "date_from": date_range[0] or "",
        "date_to": date_range[1] or "",
        "wechat_count": wechat,
    })


@app.route("/api/articles")
def api_articles():
    category = request.args.get("category", "")
    keyword = request.args.get("keyword", "")
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")
    source_type = request.args.get("source_type", "")
    min_importance = request.args.get("min_importance", "")
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 20))
    sort = request.args.get("sort", "collected_at")
    order = request.args.get("order", "DESC")

    where = []
    params = []

    if category:
        where.append("category = ?")
        params.append(category)
    if keyword:
        where.append("(title LIKE ? OR summary LIKE ? OR source LIKE ?)")
        kw = f"%{keyword}%"
        params.extend([kw, kw, kw])
    if date_from:
        where.append("publish_date >= ?")
        params.append(date_from)
    if date_to:
        where.append("publish_date <= ?")
        params.append(date_to)
    if source_type:
        where.append("source_type = ?")
        params.append(source_type)
    if min_importance:
        where.append("importance >= ?")
        params.append(int(min_importance))

    valid_sort = {"publish_date", "collected_at", "importance", "publish_date"}
    if sort not in valid_sort:
        sort = "collected_at"
    if order.upper() not in ("ASC", "DESC"):
        order = "DESC"

    where_clause = " AND ".join(where) if where else "1=1"

    conn = get_db()
    total = conn.execute(
        f"SELECT COUNT(*) FROM articles WHERE {where_clause}", params
    ).fetchone()[0]
    offset = (page - 1) * per_page
    rows = conn.execute(
        f"SELECT id, title, source, source_type, url, publish_date, collected_at, "
        f"category, summary, full_content, is_wechat, importance, window "
        f"FROM articles WHERE {where_clause} "
        f"ORDER BY {sort} {order} LIMIT ? OFFSET ?",
        params + [per_page, offset],
    ).fetchall()

    articles = []
    for r in rows:
        articles.append({
            "id": r["id"],
            "title": r["title"],
            "source": r["source"],
            "source_type": r["source_type"],
            "url": r["url"],
            "publish_date": r["publish_date"],
            "collected_at": r["collected_at"],
            "category": r["category"],
            "summary": r["summary"],
            "full_content": r["full_content"] if r["full_content"] and len(r["full_content"]) > 100 else "",
            "is_wechat": bool(r["is_wechat"]),
            "importance": r["importance"],
            "window": r["window"],
        })
    conn.close()

    return jsonify({
        "articles": articles,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": max(1, (total + per_page - 1) // per_page),
    })


@app.route("/api/charts/category")
def api_charts_category():
    conn = get_db()
    rows = conn.execute(
        "SELECT category, COUNT(*) as cnt FROM articles GROUP BY category ORDER BY cnt DESC"
    ).fetchall()
    conn.close()
    return jsonify({
        "labels": [r["category"] for r in rows],
        "values": [r["cnt"] for r in rows],
    })


@app.route("/api/charts/trend")
def api_charts_trend():
    conn = get_db()
    rows = conn.execute(
        "SELECT publish_date, COUNT(*) as cnt FROM articles "
        "WHERE publish_date IS NOT NULL "
        "GROUP BY publish_date ORDER BY publish_date"
    ).fetchall()
    conn.close()
    return jsonify({
        "labels": [r["publish_date"] for r in rows],
        "values": [r["cnt"] for r in rows],
    })


@app.route("/api/charts/source")
def api_charts_source():
    """来源类型分布。固定 4 类，缺失的补 0，便于对比。"""
    label_map = {"media": "行业媒体", "wechat": "微信公众号", "enterprise": "企业官方", "gov": "政府机构"}
    conn = get_db()
    rows = conn.execute(
        "SELECT source_type, COUNT(*) as cnt FROM articles GROUP BY source_type"
    ).fetchall()
    conn.close()

    counts = {r["source_type"]: r["cnt"] for r in rows}
    labels = []
    values = []
    for key in label_map:
        labels.append(label_map[key])
        values.append(counts.get(key, 0))

    return jsonify({"labels": labels, "values": values})


@app.route("/api/reports")
def api_reports():
    """扫描 reports/ 目录，返回按类型分组的报告列表。"""
    report_dir = os.path.join(BASE, "reports")
    result = {"daily": [], "weekly": [], "monthly": []}

    # 日报
    daily_dir = os.path.join(report_dir, "daily")
    if os.path.isdir(daily_dir):
        for fname in sorted(os.listdir(daily_dir), reverse=True):
            if not fname.endswith(".html"):
                continue
            fpath = os.path.join(daily_dir, fname)
            stat = os.stat(fpath)
            # 解析文件名: YYYY-MM-DD_vN.html
            parts = fname.replace(".html", "").split("_")
            date_part = parts[0] if len(parts) >= 1 else ""
            version = parts[1] if len(parts) >= 2 and parts[1].startswith("v") else "v1"
            # 从文件名提取日期
            try:
                dt = datetime.strptime(date_part, "%Y-%m-%d")
                month_key = dt.strftime("%Y-%m")
                day_of_week = dt.weekday()
                weekdays_cn = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
                weekday_cn = weekdays_cn[day_of_week] if day_of_week < 7 else ""
            except ValueError:
                month_key = "unknown"
                weekday_cn = ""

            result["daily"].append({
                "file": fname,
                "path": f"/reports/daily/{fname}",
                "date": date_part,
                "version": version,
                "month": month_key,
                "weekday": weekday_cn,
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
            })

    # 周报
    weekly_dir = os.path.join(report_dir, "weekly")
    if os.path.isdir(weekly_dir):
        for fname in sorted(os.listdir(weekly_dir), reverse=True):
            if not fname.endswith(".html"):
                continue
            fpath = os.path.join(weekly_dir, fname)
            stat = os.stat(fpath)
            # 解析: 2026-W28.html → 计算日期范围
            week_id = fname.replace(".html", "")
            date_range_str = week_id
            skip_this = False
            try:
                parts = week_id.split("-W")
                year = int(parts[0])
                week_num = int(parts[1])
                jan4 = date(year, 1, 4)
                monday_jan4 = jan4 - timedelta(days=jan4.isoweekday() - 1)
                monday = monday_jan4 + timedelta(weeks=week_num - 1)
                sunday = monday + timedelta(days=6)
                today = date.today()
                if sunday > today:
                    # 当周未结束，不显示
                    skip_this = True
                    continue
                date_range_str = f"{monday.year}年{monday.month}月{monday.day}日-{sunday.month}月{sunday.day}日"
            except Exception:
                pass
            if skip_this:
                continue
            result["weekly"].append({
                "file": fname,
                "path": f"/reports/weekly/{fname}",
                "week": week_id,
                "date_range": date_range_str,
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
            })

    # 月报
    monthly_dir = os.path.join(report_dir, "monthly")
    if os.path.isdir(monthly_dir):
        for fname in sorted(os.listdir(monthly_dir), reverse=True):
            if not fname.endswith(".html"):
                continue
            fpath = os.path.join(monthly_dir, fname)
            stat = os.stat(fpath)
            result["monthly"].append({
                "file": fname,
                "path": f"/reports/monthly/{fname}",
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
            })

    return jsonify(result)


@app.route("/reports/<path:subpath>")
def serve_report(subpath):
    """提供 reports/ 下的静态文件访问。"""
    safe = os.path.normpath(subpath)
    full = os.path.join(BASE, "reports", safe)
    if os.path.isfile(full) and full.endswith(".html"):
        with open(full, encoding="utf-8") as f:
            return f.read()
    return "Not found", 404


@app.route("/api/export")
def api_export():
    """导出 CSV"""
    category = request.args.get("category", "")
    keyword = request.args.get("keyword", "")
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")

    where = []
    params = []
    if category:
        where.append("category = ?")
        params.append(category)
    if keyword:
        kw = f"%{keyword}%"
        where.append("(title LIKE ? OR summary LIKE ?)")
        params.extend([kw, kw])
    if date_from:
        where.append("publish_date >= ?")
        params.append(date_from)
    if date_to:
        where.append("publish_date <= ?")
        params.append(date_to)

    where_clause = " AND ".join(where) if where else "1=1"
    conn = get_db()
    rows = conn.execute(
        f"SELECT title, source, source_type, category, publish_date, importance, "
        f"summary, url, is_wechat FROM articles WHERE {where_clause} ORDER BY publish_date DESC",
        params,
    ).fetchall()
    conn.close()

    output = io.StringIO()
    output.write("\ufeff")  # BOM for Excel
    writer = csv.writer(output)
    writer.writerow(["标题", "来源", "来源类型", "分类", "发布日期", "重要性", "摘要", "链接", "是否公众号"])
    for r in rows:
        writer.writerow([
            r["title"], r["source"], r["source_type"], r["category"],
            r["publish_date"], r["importance"], r["summary"],
            r["url"], "是" if r["is_wechat"] else "否",
        ])

    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"icv_news_export_{datetime.now().strftime('%Y%m%d')}.csv",
    )


if __name__ == "__main__":
    print(f"[OK] 启动 Web 查询界面: http://localhost:5000")
    print(f"      数据库: {DB}")
    app.run(host="0.0.0.0", port=5000, debug=False)
