"""
GitHub Actions 专用采集脚本。
使用 Playwright 直采 + requests 补充，不依赖 WorkBuddy MCP 工具。
"""
import json, os, sys, time
from datetime import datetime, date, timedelta
from playwright.sync_api import sync_playwright

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IDX = os.path.join(BASE, "data", "news_index.json")
DB = os.path.join(BASE, "data", "icv_news.db")

TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)
WINDOW = YESTERDAY.isoformat()

# 6大分类
CATS = [
    ("cat-policy",     "政策法规",  "&#9878;", "#c0392b"),
    ("cat-standards",  "标准动态",  "&#9881;", "#2980b9"),
    ("cat-investment", "投融资动态", "&#9733;", "#d4a843"),
    ("cat-technology", "技术动态",  "&#9889;", "#27ae60"),
    ("cat-projects",   "项目动态",  "&#9874;", "#8e44ad"),
    ("cat-industry",   "行业动态",  "&#128200;","#e67e22"),
]

def scrape_catarc(page):
    """采集 CATARC 新闻"""
    news = []
    try:
        page.goto("https://www.catarc.org.cn", timeout=30000)
        page.wait_for_selector("a", timeout=10000)
        links = page.evaluate("""
            Array.from(document.querySelectorAll('a')).slice(0,30).map(a => ({
                title: a.textContent.trim(),
                url: a.href,
                source: 'CATARC'
            }))
        """)
        for link in links:
            if link['title'] and len(link['title']) > 8:
                link['cat'] = 'cat-policy'
                link['date'] = YESTERDAY.isoformat()
                news.append(link)
    except Exception as e:
        print(f"  [CATARC] 采集失败: {e}")
    return news

def scrape_36kr(page):
    """采集 36氪 智能汽车新闻"""
    news = []
    try:
        page.goto("https://36kr.com/search/articles/%E6%99%BA%E8%83%BD%E7%BD%91%E8%81%94%E6%B1%BD%E8%BD%A6", timeout=30000)
        page.wait_for_timeout(3000)
        items = page.evaluate("""
            Array.from(document.querySelectorAll('a.article-item-title')).slice(0,10).map(a => ({
                title: a.textContent.trim(),
                url: a.href,
                source: '36氪'
            }))
        """)
        for item in items:
            if item['title']:
                item['cat'] = 'cat-technology'
                item['date'] = YESTERDAY.isoformat()
                news.append(item)
    except Exception as e:
        print(f"  [36氪] 采集失败: {e}")
    return news

def scrape_autohome(page):
    """采集汽车之家新闻"""
    news = []
    try:
        page.goto("https://www.autohome.com.cn/news/1.html", timeout=30000)
        page.wait_for_selector("li", timeout=10000)
        items = page.evaluate("""
            Array.from(document.querySelectorAll('ul.article li a')).slice(0,10).map(a => ({
                title: a.textContent.trim(),
                url: a.href,
                source: '汽车之家'
            }))
        """)
        for item in items:
            if item['title'] and len(item['title']) > 6:
                item['cat'] = 'cat-industry'
                item['date'] = YESTERDAY.isoformat()
                news.append(item)
    except Exception as e:
        print(f"  [汽车之家] 采集失败: {e}")
    return news

def main():
    print(f"=== 自动采集: window={WINDOW} ===")
    all_news = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        all_news.extend(scrape_catarc(page))
        all_news.extend(scrape_36kr(page))
        all_news.extend(scrape_autohome(page))

        browser.close()

    # 去重
    seen = set()
    unique_news = []
    for item in all_news:
        key = item['title'][:30]
        if key not in seen:
            seen.add(key)
            unique_news.append(item)

    # 构建 news_index.json
    data = {
        "news": [],
        "total_news": len(unique_news),
        "category_counts": {},
        "data_source": "Playwright直采 (GitHub Actions)"
    }
    for item in unique_news:
        entry = {
            "cat": item.get('cat', 'cat-industry'),
            "name": dict(CATS).get(item.get('cat', 'cat-industry'), '行业动态'),
            "title": item['title'],
            "url": item['url'],
            "source": item.get('source', ''),
            "date": item.get('date', WINDOW),
            "summary": "",
        }
        data["news"].append(entry)

    # 统计分类
    for item in data["news"]:
        cat_name = item["name"]
        data["category_counts"][cat_name] = data["category_counts"].get(cat_name, 0) + 1

    os.makedirs(os.path.dirname(IDX), exist_ok=True)
    with open(IDX, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"  采集到 {len(unique_news)} 条")
    print(f"  分类: {data['category_counts']}")
    print("[OK] 采集完成")

if __name__ == "__main__":
    main()
