# -*- coding: utf-8 -*-
"""
公众号新闻采集脚本（作为每日采集流程的「补充源」）。
- 通过搜狗微信按核心关键词检索公众号文章（间接获取，非直采微信）。
- 提取：标题 / 公众号名 / 发布日期 / 中转链 / 真实文章链 / 正文摘要。
- 窗口过滤：只保留「运行日前 N 天」(默认 N=1) 发布的文章。
- 对窗口内条目二次跳转取正文（控频，避免触发搜狗/微信反爬）。
- 去重：按真实文章链去重，并跳过 data/news_index.json 中已存在的标题。
- 输出：data/public_accounts.json

用法：
  python scripts/collect_public_accounts.py
依赖：
  playwright（managed venv: C:/Users/18351/.workbuddy/binaries/python/envs/default）
注意：
  搜狗微信有频控，无头高频会被验证码拦截；建议运行时带合理间隔。若某关键词触发
  验证码会跳过并继续。二次跳转后优先从 mp.weixin.qq.com 真实页取链接与公众号名，
  兼容搜狗用新标签打开文章的情况。
"""
import json
import os
import re
import time
import random
from datetime import date, datetime, timedelta

from playwright.sync_api import sync_playwright

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")
IDX = os.path.join(DATA, "news_index.json")
OUT = os.path.join(DATA, "public_accounts.json")

KEYWORDS = ["智能网联汽车", "自动驾驶", "Robotaxi", "智能驾驶", "车路云"]
WINDOW_DAYS = 1          # 只采集运行日前 N 天
SUMMARY_LEN = 300        # 正文摘要字数
KW_GAP = (6, 10)         # 关键词之间随机间隔(秒)
ART_GAP = (2.5, 4.5)     # 取正文之间随机间隔(秒)
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# 汇编类公众号文章标题特征（日报/晨报/晚报/简报/速览/早报/快报/周刊/摘要）
DIGEST_PATTERNS = [
    r"日报", r"晨报", r"晚报", r"简报", r"速览", r"早报",
    r"快报", r"周刊", r"摘要", r"今日概览", r"本期精选",
    r"Daily\s*Brief", r"DIGEST", r"BRIEFING",
]


def is_digest(title: str) -> bool:
    """检测是否为汇编类文章（日报/晨报等标题特征）。"""
    t = title.strip()
    if not t:
        return False
    # 标题通常包含具体日期+汇编特征词，如"7月12日:xxx日报/晨报"
    for p in DIGEST_PATTERNS:
        if re.search(p, t, re.IGNORECASE):
            return True
    # 标题含3个以上逗号分隔的话题→大概率是汇编（如"xxx,xxx,xxx,xxx"）
    parts = [s for s in re.split(r"[,，、]", t) if len(s.strip()) >= 4]
    if len(parts) >= 3:
        return True
    return False


def parse_digest_items(summary: str) -> list:
    """从汇编文章的摘要正文中解析出各条目的标题。

    汇编类文章正文通常形如：
      '...本期精选 10 条 1 美国监管机构警告... 行业动态 央视网 2 文远知行...'
    解析策略：匹配「数字 + 标题文本（到下一个数字或末尾）」。
    返回提取到的标题列表。
    """
    items = []
    # 尝试匹配 "数字+空格+标题" 的模式
    # 匹配形如 "1 美国监管机构警告..." 的编号条目
    # 先按数字分割
    segs = re.split(r"(?<!\d)(\d+)\s+(?=\S)", summary)
    # segs 形如 ["前缀", "1", "美国监管机构...", "2", "文远知行..."]
    i = 1
    while i + 1 < len(segs):
        num = segs[i].strip()
        text = segs[i + 1].strip()
        # 过滤太短的、像纯数字/日期的、非中文开头的
        if len(text) >= 8 and not text.isdigit():
            # 去除末尾的"行业动态 央视网"这类来源标签
            clean = re.sub(r"\s+(行业动态|产品发布|模型发布|技术前沿|政策解读|投融资|项目动态)\s+\S+$", "", text)
            clean = re.sub(r"\s{2,}", " ", clean).strip()
            if clean not in items:
                items.append(clean)
        i += 2
    return items


def parse_date(raw: str, today: date):
    """把搜狗结果里的日期文本解析成 date；失败返回 None。"""
    if not raw:
        return None
    s = raw.strip()
    m = re.search(r"(\d+)\s*天前", s)
    if m:
        return today - timedelta(days=int(m.group(1)))
    if "昨天" in s:
        return today - timedelta(days=1)
    if "前天" in s:
        return today - timedelta(days=2)
    if "今天" in s:
        return today
    m = re.search(r"(20\d{2})[-/年.](\d{1,2})[-/月.](\d{1,2})", s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    m = re.search(r"(\d{1,2})[-/月.](\d{1,2})", s)
    if m:
        try:
            return date(today.year, int(m.group(1)), int(m.group(2)))
        except ValueError:
            return None
    return None


def extract_list(page):
    """从搜狗结果页提取文章条目（标题/公众号/日期/中转链）。"""
    return page.evaluate(
        """() => {
        const lis = [...document.querySelectorAll('#wrapper .news-list li, .news-list li')];
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
            else if (/前天/.test(txt)) dateRaw = '前天';
            else if (/今天/.test(txt)) dateRaw = '今天';
            if (title && href) out.push({title, href, gzh, dateRaw});
        }
        return out;
    }"""
    )


def fetch_summary(page, ctx, href):
    """二次跳转取正文摘要；兼容搜狗用新标签打开文章的情况。
    返回 (real_url, account, summary)。"""
    try:
        page.goto(href, wait_until="load", timeout=25000)
        time.sleep(3.5)
        # 跳转后优先找 mp.weixin.qq.com 页面（可能开在新标签）
        target = page
        for pg in ctx.pages:
            if "mp.weixin.qq.com" in pg.url:
                target = pg
                break
        data = target.evaluate(
            """() => {
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
            }"""
        )
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

    # 已存在标题（与官方源去重）
    existing = set()
    if os.path.exists(IDX):
        try:
            with open(IDX, encoding="utf-8") as f:
                for it in json.load(f).get("news", []):
                    existing.add(it.get("title", "").strip())
        except Exception:
            pass

    results = []
    seen_real = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--lang=zh-CN"],
        )
        ctx = browser.new_context(user_agent=UA, locale="zh-CN")
        page = ctx.new_page()
        page.set_default_timeout(30000)

        for kw in KEYWORDS:
            try:
                url = "https://weixin.sogou.com/weixin?type=2&query=" + kw
                page.goto(url, wait_until="networkidle", timeout=30000)
                content = page.content()
                if "antispider" in content or "验证码" in content[:3000]:
                    print(f"[WARN] 关键词「{kw}」触发验证码，跳过")
                    time.sleep(random.uniform(*KW_GAP))
                    continue
                items = extract_list(page)
                print(f"[INFO] 关键词「{kw}」检索到 {len(items)} 条")
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
                    results.append(
                        {
                            "title": it["title"],
                            "account": account or it.get("gzh", ""),
                            "date": window_str,
                            "url": it["href"],
                            "real_url": real,
                            "summary": summary,
                            "keyword": kw,
                            "digest": is_digest(it["title"]),
                            "parsed_items": parse_digest_items(summary) if is_digest(it["title"]) else [],
                        }
                    )
                    tag = "[汇编]" if is_digest(it["title"]) else ""
                    print(f"  + {tag}[{account or '?'}] {it['title'][:30]}")
                    if is_digest(it["title"]):
                        parsed = parse_digest_items(summary)
                        for pi in parsed:
                            covered = pi.strip() in existing
                            flag = " [已收录]" if covered else " [新]"
                            print(f"       - {pi[:50]}{flag}")
                    time.sleep(random.uniform(*ART_GAP))
            except Exception as e:
                print(f"[ERR] 关键词「{kw}」异常: {e}")
            time.sleep(random.uniform(*KW_GAP))

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
    print(f"\n[DONE] 窗口 {window_str} 公众号文章 {len(results)} 条 -> {OUT}")
    return out


if __name__ == "__main__":
    run()
