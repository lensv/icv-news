# -*- coding: utf-8 -*-
"""
公众号新闻采集脚本 v2（增强版）。
- 通过搜狗微信检索公众号文章。
- 增强：隐身模式、随机UA/鼠标/滚动、多页搜索、智能重试、10+关键词。
- 输出：data/public_accounts.json
"""

import json, os, re, time, random
from datetime import date, datetime, timedelta
from playwright.sync_api import sync_playwright

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")
IDX = os.path.join(DATA, "news_index.json")
OUT = os.path.join(DATA, "public_accounts.json")

WINDOW_DAYS = 1
SUMMARY_LEN = 300
MAX_PAGES = 3          # 每关键词翻页数
KW_GAP = (8, 15)       # 关键词间隔（秒）
PAGE_GAP = (5, 10)     # 翻页间隔（秒）
ART_GAP = (3, 6)       # 每篇文章取正文间隔（秒）
CAPTCHA_WAIT = 120     # 遇到验证码等多久

UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]

# 10个关键词覆盖ICV全维度
KEYWORDS = [
    "智能网联汽车", "自动驾驶", "Robotaxi",
    "智能驾驶", "车路云", "L3级 自动驾驶",
    "城市NOA", "组合驾驶辅助 安全要求",
    "智慧交通 车路协同", "无人驾驶 商业化",
]

DIGEST_PATTERNS = [
    r"日报", r"晨报", r"晚报", r"简报", r"速览", r"早报",
    r"快报", r"周刊", r"摘要", r"今日概览", r"本期精选",
    r"Daily\s*Brief", r"DIGEST", r"BRIEFING",
]


def is_digest(t):
    if not t: return False
    for p in DIGEST_PATTERNS:
        if re.search(p, t, re.IGNORECASE): return True
    parts = [s for s in re.split(r"[,，、]", t) if len(s.strip()) >= 4]
    return len(parts) >= 3


def parse_digest_items(summary):
    items = []
    segs = re.split(r"(?<!\d)(\d+)\s+(?=\S)", summary)
    i = 1
    while i + 1 < len(segs):
        text = segs[i + 1].strip()
        if len(text) >= 8 and not text.isdigit():
            clean = re.sub(r"\s+(行业动态|产品发布|技术前沿|政策解读|投融资)\s+\S+$", "", text)
            clean = re.sub(r"\s{2,}", " ", clean).strip()
            if clean not in items: items.append(clean)
        i += 2
    return items


def parse_date(raw, today):
    if not raw: return None
    s = raw.strip()
    m = re.search(r"(\d+)\s*天前", s)
    if m: return today - timedelta(days=int(m.group(1)))
    if "昨天" in s: return today - timedelta(days=1)
    if "前天" in s: return today - timedelta(days=2)
    if "今天" in s: return today
    m = re.search(r"(20\d{2})[-/年.](\d{1,2})[-/月.](\d{1,2})", s)
    if m:
        try: return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except: pass
    m = re.search(r"(\d{1,2})[-/月.](\d{1,2})", s)
    if m:
        try: return date(today.year, int(m.group(1)), int(m.group(2)))
        except: pass
    return None


def random_scroll(page):
    """模拟人类随机滚动"""
    try:
        for _ in range(random.randint(1, 3)):
            scroll_y = random.randint(100, 600)
            page.evaluate(f"window.scrollBy(0, {scroll_y})")
            time.sleep(random.uniform(0.5, 1.5))
    except:
        pass


def extract_list(page):
    """从搜狗结果页提取文章条目"""
    return page.evaluate("""() => {
        const lis = [...document.querySelectorAll('#wrapper .news-list li, .news-list li, .result-list li')];
        const out = [];
        for (const li of lis) {
            const a = li.querySelector('h3 a') || li.querySelector('a');
            if (!a) continue;
            const title = (a.innerText || '').replace(/\\s+/g, ' ').trim();
            let href = a.getAttribute('href') || '';
            if (href && href.startsWith('/')) href = 'https://weixin.sogou.com' + href;
            const gzh = (li.querySelector('.account, .wx-name, a.account_nickname')?.innerText || '').trim();
            const txt = (li.innerText || '').replace(/\\s+/g, ' ');
            let dateRaw = null;
            const am = txt.match(/(20\\d{2}[-/年.])?\\d{1,2}[-/月.]\\d{1,2}/);
            if (am) dateRaw = am[0];
            else if (/(\\d+)\\s*天前/.test(txt)) dateRaw = RegExp.$1 + '天前';
            else if (/昨天/.test(txt)) dateRaw = '昨天';
            if (title && href) out.push({title, href, gzh, dateRaw});
        }
        return out;
    }""")


def has_captcha(page):
    """检测是否触发验证码"""
    try:
        text = page.content()[:3000]
        return "antispider" in text or "验证码" in text or "请输入验证码" in text
    except:
        return False


def fetch_summary(page, ctx, href):
    """二次跳转取正文摘要"""
    try:
        page.goto(href, wait_until="load", timeout=25000)
        time.sleep(random.uniform(3, 5))
        target = page
        for pg in ctx.pages:
            if "mp.weixin.qq.com" in pg.url:
                target = pg; break
        data = target.evaluate("""() => {
            const c = document.querySelector('#js_content');
            const name = document.querySelector('#js_name, .account_nickname_inner, .profile_nickname');
            const og = document.querySelector('meta[property="og:url"]');
            return {
                ok: !!c,
                text: c ? c.innerText.replace(/\\s+/g, ' ').trim() : '',
                account: name ? name.innerText.trim() : '',
                href: location.href,
                og: og ? og.content : ''
            };
        }""")
        real = data.get("og") or data.get("href") or target.url
        summary = data.get("text", "")[:SUMMARY_LEN] if data.get("ok") else ""
        account = data.get("account", "")
        return real, account, summary
    except Exception as e:
        return href, "", f"(取正文失败: {e})"


def run():
    today = date.today()
    window = today - timedelta(days=WINDOW_DAYS)
    window_str = window.strftime("%Y-%m-%d")

    # 加载已有标题用于去重
    existing = set()
    if os.path.exists(IDX):
        try:
            with open(IDX, encoding="utf-8") as f:
                for it in json.load(f).get("news", []):
                    existing.add(it.get("title", "").strip())
        except: pass

    results = []
    seen_real = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--lang=zh-CN",
                "--disable-web-security",
                "--no-sandbox",
            ],
        )
        ctx = browser.new_context(
            user_agent=random.choice(UA_POOL),
            locale="zh-CN",
            viewport={"width": random.choice([1366,1440,1536,1920]), "height": random.choice([768,900,1080])},
        )
        ctx.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN','zh','en']});
        """)
        page = ctx.new_page()
        page.set_default_timeout(30000)

        for ki, kw in enumerate(KEYWORDS):
            kw_gap = random.uniform(*KW_GAP)
            print(f"\n[{ki+1}/{len(KEYWORDS)}] 关键词: {kw}")

            for pg_num in range(1, MAX_PAGES + 1):
                url = f"https://weixin.sogou.com/weixin?type=2&query={kw}&page={pg_num}"
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    time.sleep(random.uniform(2, 4))
                    random_scroll(page)

                    if has_captcha(page):
                        print(f"  ⚠ 触发验证码，等待 {CAPTCHA_WAIT}s 后重试...")
                        time.sleep(CAPTCHA_WAIT)
                        page.goto(url, wait_until="domcontentloaded", timeout=30000)
                        time.sleep(random.uniform(2, 4))
                        if has_captcha(page):
                            print(f"  ❌ 验证码持续，跳过关键词")
                            break

                    items = extract_list(page)
                    print(f"  第{pg_num}页: {len(items)} 条", end="")
                    page_items = 0

                    for it in items:
                        d = parse_date(it.get("dateRaw"), today)
                        if d != window:
                            continue
                        if it["title"].strip() in existing:
                            continue

                        real, account, summary = fetch_summary(page, ctx, it["href"])
                        key = real or it["href"]
                        if key in seen_real:
                            continue
                        seen_real.add(key)

                        results.append({
                            "title": it["title"],
                            "account": account or it.get("gzh", ""),
                            "date": window_str,
                            "url": it["href"],
                            "real_url": real,
                            "summary": summary,
                            "keyword": kw,
                            "digest": is_digest(it["title"]),
                            "parsed_items": parse_digest_items(summary) if is_digest(it["title"]) else [],
                        })
                        page_items += 1
                        tag = "[汇编]" if is_digest(it["title"]) else ""
                        print(f"\n    + {tag}[{account or '?'}] {it['title'][:35]}")
                        time.sleep(random.uniform(*ART_GAP))

                    if page_items == 0:
                        print(" (无窗口内新数据)")
                    else:
                        print(f"")

                    # 翻页继续
                    if pg_num < MAX_PAGES:
                        time.sleep(random.uniform(*PAGE_GAP))

                except Exception as e:
                    print(f"  ❌ 异常: {str(e)[:60]}")
                    continue

            # 关键词之间间隔
            if ki < len(KEYWORDS) - 1:
                print(f"  等待 {kw_gap:.0f}s 后下一个关键词...")
                time.sleep(kw_gap)

        browser.close()

    out = {
        "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "window": window_str,
        "keywords": KEYWORDS,
        "total": len(results),
        "items": results,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n{'='*50}")
    print(f"[DONE] 窗口 {window_str} 公众号 {len(results)} 条 -> {OUT}")
    return out


if __name__ == "__main__":
    run()
