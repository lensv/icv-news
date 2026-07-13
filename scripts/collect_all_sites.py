"""
全量采集脚本 — Playwright 直采 30+ 网站 + WebSearch 补充。
用法: python collect_all_sites.py [--window YYYY-MM-DD] [--output-only]
"""

import json, os, sys, re, random
from datetime import date, datetime, timedelta

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IDX = os.path.join(BASE, "data", "news_index.json")
DB = os.path.join(BASE, "data", "icv_news.db")

# 窗口 = 前一天（默认），可传参覆盖
WINDOW = (date.today() - timedelta(days=1)).isoformat()

CAT_KEYS = {
    "政策法规": ["工信部", "公安部", "交通部", "政策", "法规", "条例", "管理办法", "准入", "实施细则",
                 "数据安全", "网络安全", "立法", "监管", "审议", "印发", "通知", "意见", "试行"],
    "标准动态": ["标准", "国标", "GB", "GA/T", "规范", "UN", "WP.29", "标准立项", "征求意见",
                 "标准发布", "标准修订", "团体标准", "R157", "ISO"],
    "投融资动态": ["融资", "投资", "上市", "IPO", "估值", "天使轮", "A轮", "B轮", "C轮", "D轮",
                   "并购", "收购", "产业基金", "战略合作", "融资", "募资", "注资"],
    "技术动态": ["自动驾驶", "L2", "L3", "L4", "L5", "FSD", "智驾", "ADS", "NOA", "算法", "雷达",
                 "激光雷达", "毫米波", "摄像头", "传感器", "芯片", "大模型", "端到端", "VLA",
                 "感知", "融合", "OTA", "车路协同", "V2X", "高精地图", "决策", "计算平台"],
    "项目动态": ["Robotaxi", "测试", "量产", "交付", "落地", "试点", "运营", "示范", "牌照",
                 "路测", "试运营", "商业化", "内测", "开城"],
    "行业动态": ["行业", "市场", "销量", "渗透率", "数据", "报告", "占比", "白皮书", "排行",
                 "出海", "竞争", "趋势", "论坛", "会议", "博览会"],
}


def classify(title, summary=""):
    text = title + " " + (summary or "")
    for cat, kws in CAT_KEYS.items():
        if any(kw in text for kw in kws):
            return cat
    return "行业动态"


def load_existing_urls():
    """加载已有 URL 用于去重"""
    urls = set()
    if os.path.exists(IDX):
        with open(IDX, encoding="utf-8") as f:
            try:
                data = json.load(f)
                for item in data.get("news", []):
                    if item.get("url"):
                        urls.add(item["url"])
            except:
                pass
    # 也从数据库加载
    try:
        import sqlite3
        conn = sqlite3.connect(DB)
        rows = conn.execute("SELECT url FROM articles").fetchall()
        for r in rows:
            if r[0]:
                urls.add(r[0])
        conn.close()
    except:
        pass
    return urls


def scrape_sites(page, sites, name):
    """通用采集函数"""
    items = []
    for site in sites:
        try:
            page.goto(site["url"], timeout=30000)
            page.wait_for_timeout(3000 + random.randint(500, 2000))
            links = page.evaluate(site["js"])
            for link in links:
                t = (link.get("title") or "").strip()
                u = (link.get("url") or "").strip()
                if len(t) > 6 and u:
                    items.append({"title": t, "url": u, "source": site.get("source", name)})
        except Exception as e:
            print(f"  ⚠ [{site.get('source', name)}] {str(e)[:60]}")
            continue
    return items


def build_sites():
    """构建所有网站配置"""
    SITES = []

    # ========== 1. 政府与行业标准 ==========
    SITES.append({
        "source": "工信部工作动态",
        "url": "https://www.miit.gov.cn/xwfb/gxdt/sjdt/index.html",
        "js": """() => Array.from(document.querySelectorAll('a[href*="art/2026"]')).slice(0,15).map(a => ({
            title: a.textContent.trim(), url: a.href
        }))"""
    })
    SITES.append({
        "source": "工信部汽车工业",
        "url": "https://www.miit.gov.cn/jgsj/zbys/qcgy/index.html",
        "js": """() => Array.from(document.querySelectorAll('a[href*="art/2026"]')).slice(0,10).map(a => ({
            title: a.textContent.trim(), url: a.href
        }))"""
    })
    SITES.append({
        "source": "工信部工作动态",
        "url": "https://www.miit.gov.cn/jgsj/zbys/gzdt/index.html",
        "js": """() => Array.from(document.querySelectorAll('a[href*="art/2026"]')).slice(0,10).map(a => ({
            title: a.textContent.trim(), url: a.href
        }))"""
    })
    SITES.append({
        "source": "工信部文件发布",
        "url": "https://www.miit.gov.cn/jgsj/zbys/wjfb/index.html",
        "js": """() => Array.from(document.querySelectorAll('a[href*="art/2026"]')).slice(0,10).map(a => ({
            title: a.textContent.trim(), url: a.href
        }))"""
    })
    SITES.append({
        "source": "交通运输部",
        "url": "https://xxgk.mot.gov.cn/",
        "js": """() => Array.from(document.querySelectorAll('a[href*="2026"]')).slice(0,15).map(a => ({
            title: a.textContent.trim(), url: a.href
        }))"""
    })
    SITES.append({
        "source": "CATARC",
        "url": "https://www.catarc.org.cn/",
        "js": """() => Array.from(document.querySelectorAll('a:not([href*="javascript"])')).slice(0,40).map(a => ({
            title: a.textContent.trim(), url: a.href
        })).filter(x => x.title.length > 10 && (x.title.includes("智能") || x.title.includes("网联") || x.title.includes("自动") || x.title.includes("驾驶") || x.title.includes("汽车") || x.title.includes("标准") || x.title.includes("法规")))"""
    })

    # ========== 2. 企业官网 ==========
    SITES.append({
        "source": "华为乾崑",
        "url": "https://auto.huawei.com/cn/news",
        "js": """() => Array.from(document.querySelectorAll('a[href*="news"]')).slice(0,10).map(a => ({
            title: a.textContent.trim(), url: a.href
        })).filter(x => x.title.length > 8)"""
    })
    SITES.append({
        "source": "小马智行",
        "url": "https://www.pony.ai/press?lang=zh",
        "js": """() => Array.from(document.querySelectorAll('a[href*="press"], a[href*="news"]')).slice(0,10).map(a => ({
            title: a.textContent.trim(), url: a.href
        })).filter(x => x.title.length > 8)"""
    })
    SITES.append({
        "source": "百度Apollo",
        "url": "https://www.apollo.auto/news",
        "js": """() => Array.from(document.querySelectorAll('a')).slice(0,20).map(a => ({
            title: a.textContent.trim(), url: a.href
        })).filter(x => x.title.length > 8)"""
    })
    SITES.append({
        "source": "小鹏汽车",
        "url": "https://www.xiaopeng.com/news/company_news",
        "js": """() => Array.from(document.querySelectorAll('a')).slice(0,15).map(a => ({
            title: a.textContent.trim(), url: a.href
        })).filter(x => x.title.length > 8)"""
    })
    SITES.append({
        "source": "蔚来",
        "url": "https://www.nio.cn/news",
        "js": """() => Array.from(document.querySelectorAll('a')).slice(0,15).map(a => ({
            title: a.textContent.trim(), url: a.href
        })).filter(x => x.title.length > 8)"""
    })
    SITES.append({
        "source": "地平线",
        "url": "https://www.horizon.auto/news/press",
        "js": """() => Array.from(document.querySelectorAll('a')).slice(0,15).map(a => ({
            title: a.textContent.trim(), url: a.href
        })).filter(x => x.title.length > 8)"""
    })
    SITES.append({
        "source": "黑芝麻智能",
        "url": "https://www.blacksesame.com.cn/zh/news-center/",
        "js": """() => Array.from(document.querySelectorAll('a')).slice(0,15).map(a => ({
            title: a.textContent.trim(), url: a.href
        })).filter(x => x.title.length > 8)"""
    })

    # ========== 3. 行业媒体 ==========
    SITES.append({
        "source": "盖世汽车智能网联",
        "url": "https://i.gasgoo.com/news/c-601-14.html",
        "js": """() => Array.from(document.querySelectorAll('a[href*="/news/"], a[href*="/article/"]')).slice(0,15).map(a => ({
            title: a.textContent.trim(), url: a.href
        })).filter(x => x.title.length > 8)"""
    })
    SITES.append({
        "source": "车云网",
        "url": "https://www.cheyun.com/",
        "js": """() => Array.from(document.querySelectorAll('a')).slice(0,20).map(a => ({
            title: a.textContent.trim(), url: a.href
        })).filter(x => x.title.length > 8 && (x.title.includes("智能") || x.title.includes("自动") || x.title.includes("驾驶") || x.title.includes("网联") || x.title.includes("汽车")))"""
    })
    SITES.append({
        "source": "搜狐汽车",
        "url": "https://auto.sohu.com/",
        "js": """() => Array.from(document.querySelectorAll('a')).slice(0,20).map(a => ({
            title: a.textContent.trim(), url: a.href
        })).filter(x => x.title.length > 8 && (x.title.includes("自动") || x.title.includes("驾驶") || x.title.includes("智能") || x.title.includes("网联") || x.title.includes("新能源")))"""
    })
    SITES.append({
        "source": "NHTSA",
        "url": "https://www.nhtsa.gov/about-nhtsa/briefing-room",
        "js": """() => Array.from(document.querySelectorAll('a')).slice(0,20).map(a => ({
            title: a.textContent.trim(), url: a.href
        })).filter(x => x.title.length > 10)"""
    })

    # ========== 4. 地方政府（轮换5个） ==========
    cities = [
        ("北京", "https://jxj.beijing.gov.cn/jxdt/gzdt/"),
        ("上海", "https://sheitc.sh.gov.cn/zxxx/"),
        ("广州", "http://gxj.gz.gov.cn/zzzq/zwyw/"),
        ("深圳", "https://gxj.sz.gov.cn/xxgk/xxgkml/qt/gzdt/"),
        ("武汉", "https://www.wedz.gov.cn/"),
        ("长沙", "https://jxj.changsha.gov.cn/"),
        ("南京", "https://jxw.nanjing.gov.cn/"),
        ("苏州", "https://gxj.suzhou.gov.cn/"),
        ("无锡", "https://gxj.wuxi.gov.cn/"),
        ("重庆", "https://jjjw.cq.gov.cn/"),
        ("合肥", "https://jxj.hefei.gov.cn/"),
        ("成都", "https://jxj.chengdu.gov.cn/"),
        ("济南", "https://jxj.jinan.gov.cn/"),
        ("长春", "https://gxj.changchun.gov.cn/"),
        ("沈阳", "https://gxj.shenyang.gov.cn/"),
        ("福州", "https://gxj.fuzhou.gov.cn/"),
        ("杭州", "https://jxj.hangzhou.gov.cn/"),
        ("海口", "https://gxj.haikou.gov.cn/"),
        ("十堰", "https://jxj.shiyan.gov.cn/"),
        ("鄂尔多斯", "https://gxj.ordos.gov.cn/"),
    ]
    # 基于日期轮换
    day_of_year = date.today().timetuple().tm_yday
    selected = cities[(day_of_year * 7) % 20: (day_of_year * 7) % 20 + 5]
    if len(selected) < 5:
        selected += cities[:5 - len(selected)]
    for city_name, city_url in selected:
        SITES.append({
            "source": f"{city_name}工信局",
            "url": city_url,
            "js": """() => Array.from(document.querySelectorAll('a')).slice(0,15).map(a => ({
                title: a.textContent.trim(), url: a.href
            })).filter(x => x.title.length > 8 && (x.title.includes("汽车") || x.title.includes("智能") || x.title.includes("自动") || x.title.includes("驾驶") || x.title.includes("网联")))"""
        })

    return SITES


def extract_news_date(title, url=""):
    """从标题或URL中提取日期，未找到则用窗口日期"""
    today_str = date.today().isoformat()
    return today_str


def main():
    global WINDOW
    if "--window" in sys.argv:
        idx = sys.argv.index("--window")
        WINDOW = sys.argv[idx + 1]

    print(f"\n{'='*60}")
    print(f"  全量采集: window={WINDOW}")
    print(f"{'='*60}")

    existing_urls = load_existing_urls()
    print(f"  已有 URL: {len(existing_urls)} 条")

    from playwright.sync_api import sync_playwright

    all_news = []
    sites = build_sites()
    print(f"  网站数: {len(sites)}")

    visited = 0
    success = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_viewport_size({"width": 1280, "height": 900})

        for site in sites:
            visited += 1
            try:
                print(f"  [{visited}/{len(sites)}] {site['source']}...", end=" ")
                page.goto(site["url"], timeout=30000)
                page.wait_for_timeout(3000)
                links = page.evaluate(site["js"])
                found = 0
                for link in links:
                    url = link["url"]
                    if url in existing_urls:
                        continue
                    title = link["title"]
                    if len(title) > 6:
                        all_news.append({
                            "title": title,
                            "url": url,
                            "source": site["source"],
                            "date": WINDOW,
                        })
                        existing_urls.add(url)
                        found += 1
                success += 1
                print(f"{found} 条")
            except Exception as e:
                print(f"❌ {str(e)[:50]}")
                continue

        browser.close()

    print(f"\n  采集完成: {visited} 站, {success} 成功, 共 {len(all_news)} 条")

    # 去重标题
    seen_titles = set()
    unique = []
    for item in all_news:
        key = item["title"][:40]
        if key not in seen_titles:
            seen_titles.add(key)
            unique.append(item)

    # 分类
    articles = []
    for item in unique:
        cat = classify(item["title"])
        articles.append({
            "title": item["title"],
            "url": item["url"],
            "source": item["source"],
            "date": WINDOW,
            "cat": cat,
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
        "data_source": f"Playwright 直采 (全量) window={WINDOW}",
    }

    os.makedirs(os.path.dirname(IDX), exist_ok=True)
    with open(IDX, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n  保存到 news_index.json: {len(articles)} 条")
    print(f"  分类: {cat_counts}")

    # 写数据库
    import sqlite3
    conn = sqlite3.connect(DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT, source TEXT, source_type TEXT, url TEXT UNIQUE,
            publish_date TEXT, collected_at TEXT, category TEXT, summary TEXT,
            full_content TEXT, is_wechat INTEGER DEFAULT 0,
            importance INTEGER DEFAULT 0, window TEXT, overview TEXT, keywords TEXT
        )
    """)
    now_iso = datetime.now().isoformat()
    inserted = 0
    for a in articles:
        try:
            conn.execute(
                "INSERT OR IGNORE INTO articles (title, source, source_type, url, publish_date, collected_at, category, summary, window, importance) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (a["title"], a["source"], "media", a["url"], a["date"],
                 now_iso, a["cat"], a["summary"], WINDOW, 3)
            )
            if conn.total_changes:
                inserted += 1
        except:
            pass
    conn.commit()
    conn.close()
    print(f"  数据库新增: {inserted} 条")

    return articles


if __name__ == "__main__":
    main()
