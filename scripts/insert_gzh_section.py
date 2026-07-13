# -*- coding: utf-8 -*-
"""
把 data/public_accounts.json 的公众号文章，作为「独立补充区块」插入每日报告
（reports/daily/YYYY-MM-DD_vN.html）的 </main> 之前。
- 自动 HTML 转义（URL 中的 &、文本中的 < > &）。
- 幂等：若报告已含 cat-gzh 区块则跳过，不重复插入。
- 窗口内无公众号文章时，插入「暂无更新」空区块。
用法：
  python scripts/insert_gzh_section.py [报告路径，默认最新 v* 文件]
"""
import html
import json
import os
import sys
import glob

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")
REPORT_DIR = os.path.join(BASE, "reports", "daily")


def latest_report():
    files = glob.glob(os.path.join(REPORT_DIR, "*.html"))
    return max(files, key=os.path.getmtime) if files else None


def build_section(gzh):
    items = gzh.get("items", [])
    window = gzh.get("window", "")
    kws = " / ".join(gzh.get("keywords", []))
    if not items:
        body = ('      <div style="padding:48px 0;text-align:center;color:var(--color-text-secondary);'
                'font-size:14px;background:var(--color-bg);border-radius:var(--radius-md);'
                'border:1px dashed var(--color-border);">本期采集窗口内（%s）公众号暂无更新</div>' % window)
    else:
        cards = ""
        for i, it in enumerate(items, 1):
            href = html.escape(it.get("real_url") or it.get("url", ""), quote=True)
            title = html.escape(it.get("title", ""))
            acct = html.escape(it.get("account", ""))
            summ = html.escape(it.get("summary", ""))
            date = html.escape(it.get("date", ""))
            cards += f"""      <article class="news-card animate-on-scroll stagger-{i}">
        <div class="news-card-inner">
          <span class="news-number">{i}</span>
          <div class="news-content">
            <h3 class="news-title"><a href="{href}">{title}</a></h3>
            <div class="news-meta">
              <span>{acct}</span>
              <span class="news-meta-dot"></span>
              <span>{date}</span>
            </div>
            <p class="news-summary">{summ}</p>
          </div>
        </div>
      </article>
"""
        body = cards
    return f"""    <section class="category-section cat-gzh" aria-label="公众号补充">
    <div class="container">
      <div class="category-header animate-on-scroll">
        <span class="category-icon">&#128241;</span>
        <h2 class="category-title">公众号补充</h2>
        <span class="category-count">{len(items)} 条</span>
      </div>
      <div style="font-size:12px;color:var(--color-text-secondary);margin:-6px 0 18px;">关键词检索补充源（{html.escape(kws)}），采集窗口 {html.escape(window)}</div>
{body}    </div>
  </section>

"""


GZH_CSS = """
.cat-gzh { --cat-gzh:#07c160; --cat-gzh-bg:#e8f8ef; }
.cat-gzh .category-header::after { background: var(--cat-gzh); }
.cat-gzh .category-icon { background: var(--cat-gzh-bg); color: var(--cat-gzh); }
.cat-gzh .news-card::before { background: var(--cat-gzh); }
.cat-gzh .news-number { background: var(--cat-gzh-bg); color: var(--cat-gzh); }
.cat-gzh .news-title a:hover { color: var(--cat-gzh); }
"""


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else latest_report()
    if not path or not os.path.exists(path):
        print("[ERR] 找不到报告文件")
        return
    with open(path, encoding="utf-8") as f:
        content = f.read()
    # 注入公众号区块样式（若报告尚未包含）
    if "cat-gzh" in content:
        print(f"[SKIP] 报告已含公众号区块: {path}")
        return
    if ".cat-gzh .news-number" not in content and "</style>" in content:
        content = content.replace("</style>", GZH_CSS + "</style>", 1)
    gzh_path = os.path.join(DATA, "public_accounts.json")
    if not os.path.exists(gzh_path):
        print("[ERR] 缺少 public_accounts.json")
        return
    gzh = json.load(open(gzh_path, encoding="utf-8"))
    section = build_section(gzh)
    content = content.replace("</main>", section + "  </main>", 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[OK] 已插入公众号区块({gzh.get('total',0)} 条) -> {path}")


if __name__ == "__main__":
    main()
