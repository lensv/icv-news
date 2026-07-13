"""
GitHub Actions 采集脚本 — 使用 Playwright 扫描多个新闻源。
安装依赖: pip install playwright && python -m playwright install chromium
"""
import json, os, sys, re
from datetime import date, datetime, timedelta

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IDX = os.path.join(BASE, "data", "news_index.json")
DB = os.path.join(BASE, "data", "icv_news.db")

YESTERDAY = (date.today() - timedelta(days=1)).isoformat()
WINDOW = YESTERDAY

CAT_KEYS = {
    "政策法规": ["工信部", "公安部", "交通部", "政策", "法规", "条例", "管理办法", "准入"],
    "标准动态": ["标准", "国标", "GB", "GA/T", "规范", "UN", "WP.29"],
    "投融资动态": ["融资", "投资", "上市", "IPO", "估值", "天使轮", "A轮", "B轮"],
    "技术动态": ["自动驾驶", "L2", "L3", "L4", "FSD", "智驾", "ADS", "NOA", "算法", "雷达", "芯片"],
    "项目动态": ["Robotaxi", "测试", "量产", "交付", "落地", "试点", "运营"],
    "行业动态": ["行业", "市场", "销量", "渗透率", "数据", "报告", "占比"],
}


def classify(title, summary=""):
    text = title + " " + (summary or "")
    for cat, kws in CAT_KEYS.items():
        if any(kw in text for kw in kws):
            return cat
    return "行业动态"


def scrape_miit(page):
    """工信部 - 新闻列表"""
    items = []
    try:
        page.goto("https://www.miit.gov.cn/xwfb/gxdt/sjdt/index.html", timeout=30000)
        page.wait_for_timeout(3000)
        links = page.evaluate("""
            Array.from(document.querySelectorAll('a[href*="art/2026"]')).slice(0,15).map(a => ({
                title: a.textContent.trim(),
                url: a.href
            }))
        """)
        for link in links:
            if any(k in link["title"] for k in ["智能网联", "自动驾驶", "汽车", "L2", "L3", "L4", "驾驶"]):
                items.append(link)
    except Exception as e:
        print(f"  [工信部] {e}")
    return items


def scrape_catarc(page):
    """CATARC 中汽中心"""
    items = []
    try:
        page.goto("https://www.catarc.org.cn/", timeout=30000)
        page.wait_for_timeout(3000)
        links = page.evaluate("""
            Array.from(document.querySelectorAll('a')).slice(0,40).map(a => ({
                title: a.textContent.trim(),
                url: a.href
            }))
        """)
        for link in links:
            t = link["title"]
            if len(t) > 10 and any(k in t for k in ["智能", "网联", "自动", "驾驶", "汽车", "标准", "法规"]):
                items.append(link)
    except Exception as e:
        print(f"  [CATARC] {e}")
    return items


def scrape_36kr(page):
    """36氪搜索"""
    items = []
    try:
        page.goto("https://36kr.com/search/articles/%E6%99%BA%E8%83%BD%E7%BD%91%E8%81%94%E6%B1%BD%E8%BD%A6", timeout=30000)
        page.wait_for_timeout(4000)
        links = page.evaluate("""
            Array.from(document.querySelectorAll('a.cooper-link, a.article-item-title, a[href*="article"]')).slice(0,12).map(a => ({
                title: a.textContent.trim(),
                url: a.href.startsWith('http') ? a.href : 'https://36kr.com' + a.href
            }))
        """)
        for link in links:
            t = link["title"]
            if len(t) > 8:
                items.append(link)
    except Exception as e:
        print(f"  [36氪] {e}")
    return items


def scrape_gasgoo(page):
    """盖世汽车"""
    items = []
    try:
        page.goto("https://auto.gasgoo.com/news/", timeout=30000)
        page.wait_for_timeout(3000)
        links = page.evaluate("""
            Array.from(document.querySelectorAll('a[href*="/news/"]')).slice(0,20).map(a => ({
                title: a.textContent.trim(),
                url: a.href
            }))
        """)
        for link in links:
            t = link["title"]
            if len(t) > 8:
                items.append(link)
    except Exception as e:
        print(f"  [盖世] {e}")
    return items


def main():
    print(f"=== Playwright 采集: window={WINDOW} ===")

    from playwright.sync_api import sync_playwright

    all_news = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        all_news.extend(scrape_miit(page))
        all_news.extend(scrape_catarc(page))
        all_news.extend(scrape_36kr(page))
        all_news.extend(scrape_gasgoo(page))

        browser.close()

    # 去重
    seen = set()
    articles = []
    for item in all_news:
        key = item["title"][:30]
        if key not in seen:
            seen.add(key)
            cat_name = classify(item["title"])
            articles.append({
                "title": item["title"],
                "url": item["url"],
                "source": "自动采集",
                "date": YESTERDAY,
                "cat": cat_name,
                "summary": "",
            })

    # 统计
    cat_counts = {}
    for a in articles:
        cat_counts[a["cat"]] = cat_counts.get(a["cat"], 0) + 1

    data = {
        "news": articles,
        "total_news": len(articles),
        "category_counts": cat_counts,
        "data_source": "Playwright 直采 (GitHub Actions)",
    }

    os.makedirs(os.path.dirname(IDX), exist_ok=True)
    with open(IDX, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # 写数据库
    import sqlite3
    conn = sqlite3.connect(DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            source TEXT,
            source_type TEXT,
            url TEXT UNIQUE,
            publish_date TEXT,
            collected_at TEXT,
            category TEXT,
            summary TEXT,
            full_content TEXT,
            is_wechat INTEGER DEFAULT 0,
            importance INTEGER DEFAULT 0,
            window TEXT,
            overview TEXT,
            keywords TEXT
        )
    """)
    for a in articles:
        conn.execute(
            "INSERT OR IGNORE INTO articles (title, source, source_type, url, publish_date, collected_at, category, summary, window, importance) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (a["title"], a["source"], "media", a["url"], a["date"],
             datetime.now().isoformat(), a["cat"], a["summary"], WINDOW, 3)
        )
    conn.commit()
    conn.close()

    print(f"  采集到 {len(articles)} 条")
    print(f"  分类: {cat_counts}")
    print("[OK]")

if __name__ == "__main__":
    main()
