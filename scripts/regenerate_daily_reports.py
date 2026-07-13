# -*- coding: utf-8 -*-
"""
从 SQLite 数据库读取历史日报数据，用新模板重新生成所有历史日报。
用法:
  python scripts/regenerate_daily_reports.py                   # 重新生成所有历史日报
  python scripts/regenerate_daily_reports.py --date 2026-07-06  # 只重新生成指定日期
"""
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from collections import defaultdict
from datetime import date

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(BASE, "data", "icv_news.db")
IDX = os.path.join(BASE, "data", "news_index.json")
GEN_REPORT = os.path.join(os.path.dirname(BASE), "AppData", "Local", "Temp", "gen_report.py")
# 也尝试常见路径
ALT_GEN = r"C:\Users\18351\AppData\Local\Temp\gen_report.py"
if not os.path.exists(GEN_REPORT):
    GEN_REPORT = ALT_GEN if os.path.exists(ALT_GEN) else ""

CAT_MAP = {
    "政策法规": "cat-policy",
    "标准动态": "cat-standards",
    "投融资动态": "cat-investment",
    "技术动态": "cat-technology",
    "项目动态": "cat-projects",
    "行业动态": "cat-industry",
}
CAT_NAMES = {v: k for k, v in CAT_MAP.items()}


def load_db_articles_for_date(target_date):
    """从数据库加载指定日期的所有文章"""
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT title, source, category, publish_date, summary, overview, importance, url
           FROM articles
           WHERE publish_date = ?
           ORDER BY importance DESC, publish_date DESC""",
        (target_date,)
    ).fetchall()
    conn.close()
    return rows


def build_news_json(articles, target_date):
    """从数据库文章构建 gen_report.py 所需的 JSON 格式"""
    news = []
    for a in articles:
        cat_short = CAT_MAP.get(a["category"], "cat-industry")
        news.append({
            "cat": cat_short,
            "name": a["category"],
            "icon": "",
            "title": a["title"],
            "url": a["url"],
            "source": a["source"],
            "date": a["publish_date"],
            "summary": a["summary"] or "",
            "overview": a["overview"] or "",
            "importance": a["importance"] or 0,
        })

    # 统计各类别数量
    counts = defaultdict(int)
    for item in news:
        counts[item["name"]] += 1

    return {
        "news": news,
        "total_news": len(news),
        "category_counts": dict(counts),
        "data_source": "数据库历史数据重生成",
    }


def regenerate(target_date=None):
    if not os.path.exists(GEN_REPORT):
        print(f"[ERR] 找不到 gen_report.py: {GEN_REPORT}")
        return

    # 备份当前 news_index.json
    backup = IDX + ".bak"
    if os.path.exists(IDX):
        shutil.copy2(IDX, backup)

    try:
        if target_date:
            dates_to_process = [target_date]
        else:
            # 获取数据库中的所有不同日期
            conn = sqlite3.connect(DB)
            rows = conn.execute(
                "SELECT DISTINCT publish_date FROM articles WHERE publish_date IS NOT NULL ORDER BY publish_date"
            ).fetchall()
            conn.close()
            dates_to_process = [r[0] for r in rows]

        for dt_str in dates_to_process:
            articles = load_db_articles_for_date(dt_str)
            if not articles:
                print(f"  [{dt_str}] 无数据，跳过")
                continue

            # 构建 JSON 并写入 news_index.json
            data = build_news_json(articles, dt_str)
            with open(IDX, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            # 检查是否已有同名文件（取最新版本号）
            daily_dir = os.path.join(BASE, "reports", "daily")
            existing = [f for f in os.listdir(daily_dir) if f.startswith(dt_str) and f.endswith(".html")]
            max_v = 0
            for f in existing:
                parts = f.replace(".html", "").split("_")
                if len(parts) >= 2 and parts[1].startswith("v"):
                    try:
                        v = int(parts[1].lstrip("v").split("(")[0])
                        max_v = max(max_v, v)
                    except ValueError:
                        pass
            version = f"v{max_v + 1}"

            # 调用 gen_report.py
            py_exe = sys.executable or r"C:\Users\18351\.workbuddy\binaries\python\versions\3.13.12\python.exe"
            cmd = [py_exe, GEN_REPORT, dt_str, version, ""]
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=BASE)
            if result.returncode == 0:
                print(f"  [{dt_str}] ✅ {version} ({len(articles)} 条)")
            else:
                print(f"  [{dt_str}] ❌ 失败: {result.stderr[:200]}")

    finally:
        # 恢复原始的 news_index.json
        if os.path.exists(backup):
            shutil.move(backup, IDX)

    print("\n完成！")


if __name__ == "__main__":
    target = None
    if "--date" in sys.argv:
        idx = sys.argv.index("--date")
        if idx + 1 < len(sys.argv):
            target = sys.argv[idx + 1]
    regenerate(target)
