"""
GitHub Actions 采集脚本 — 使用 Playwright 扫描多个新闻源。
安装依赖: pip install playwright && python -m playwright install chromium
"""
import json, os, sys
from datetime import date, datetime, timedelta

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IDX = os.path.join(BASE, "data", "news_index.json")
DB = os.path.join(BASE, "data", "icv_news.db")

YESTERDAY = (date.today() - timedelta(days=1)).isoformat()
WINDOW = YESTERDAY

from scripts.icv_filter import CAT_KEYS, filter_icv, classify, validate_url


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
            if len(t) > 8 and any(k in t for k in ["智能网联","自动驾驶","智驾","汽车","新能源","激光雷达","芯片","融资","Robotaxi","L2","L3","L4"]):
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
            if len(t) > 8 and any(k in t for k in ["智能网联","自动驾驶","智驾","汽车","新能源","激光雷达","芯片","融资","Robotaxi","L2","L3","L4","雷达"]):
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
            articles.append(item)

    # ICV 白名单过滤
    before = len(articles)
    articles = [item for item in articles if filter_icv(item["title"])]
    print(f"  ICV白名单过滤: {before} → {len(articles)} 条")

    # URL 有效性校验（防假链接/占位符）
    url_before = len(articles)
    articles = [item for item in articles if validate_url(item.get("url", ""))]
    if len(articles) < url_before:
        print(f"  无效URL过滤: {url_before} → {len(articles)} 条")

    # 分类
    categorized = []
    for item in articles:
        cat_name = classify(item["title"])
        categorized.append({
            "title": item["title"],
            "url": item["url"],
            "source": "自动采集",
            "date": YESTERDAY,
            "cat": cat_name,
            "summary": "",
        })
    articles = categorized

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
