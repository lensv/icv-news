# -*- coding: utf-8 -*-
"""
URL 健康检查脚本 — 对数据库所有 URL 做 HTTP 探测，找出失效链接。

策略：
- HEAD 请求（节省带宽），失败时降级 GET（部分站点不支持 HEAD）
- 超时 8 秒，UA 伪装
- HTTP 200-399 视为可达
- 404/403/500/超时/连接错误 → 失效

用法:
    python scripts/check_urls_health.py                # 检查所有有效文章
    python scripts/check_urls_health.py --window 2026-07-04  # 指定窗口
    python scripts/check_urls_health.py --soft-delete-broken  # 自动软删除失效链接

输出：表格列出健康状态 + 失败原因，统计汇总。
"""
import argparse
import sqlite3
import sys
import os
import subprocess
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(BASE, "data", "icv_news.db")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}
TIMEOUT = 8


def _check_via_curl(url):
    """使用 curl 兜底，处理 Python SSL_BAD_ECPOINT 等兼容问题。"""
    try:
        r = subprocess.run(
            ["curl", "-sk", "-A", HEADERS["User-Agent"],
             "-o", os.devnull, "-w", "%{http_code}",
             "--max-time", str(TIMEOUT), url],
            capture_output=True, text=True, timeout=TIMEOUT + 2
        )
        code = int(r.stdout.strip() or "0")
        if 200 <= code < 400:
            return True, code, "OK_VIA_CURL"
        return False, code, f"HTTP_{code}"
    except Exception as e:
        return False, None, f"CURL_ERR: {type(e).__name__}"


def _fetch_html_content(url):
    """抓取 HTML 内容（用于 JS-render 检测）。失败返回 None。"""
    try:
        r = subprocess.run(
            ["curl", "-sk", "-A", HEADERS["User-Agent"],
             "-L", "--max-time", "10", url],
            capture_output=True, timeout=12
        )
        if r.returncode == 0 and r.stdout:
            return r.stdout.decode("utf-8", errors="ignore")
    except Exception:
        pass
    return None


def _check_js_render(url, title=""):
    """检测 URL 是否 JS-render（HTML 壳无内容）。返回 (ok, reason)"""
    # 政府/标准等公开站点一般支持外部访问，跳过 JS 检测
    skip_domains = ("szrd.gov.cn", "miit.gov.cn", "catarc.org.cn", "sz.gov.cn",
                    "gov.cn", "miit-eidc.org.cn", "csjrw.cn", "wuxi.gov.cn",
                    "suzhou.gov.cn", "beijing.gov.cn", "sh.gov.cn")
    if any(d in url for d in skip_domains):
        return True, None
    html = _fetch_html_content(url)
    if not html or len(html) < 5000:
        # 腾讯/新浪等软 404：HTML 短小但包含 404 字样
        if html and any(w in html for w in ["404", "页面找不到了", "page not found"]):
            return False, f"SOFT_404: HTML {len(html)}字节，页面显示404"
        return True, None
    # 提取 title 关键词（中文 2 字以上、英文 4 字以上）
    keywords = []
    if title:
        for w in title.replace("：", " ").replace("，", " ").replace("！", " ").replace("?", " ").replace("?", " ").split():
            if len(w) >= 2 and not w.isdigit():
                keywords.append(w)
    if not keywords:
        return True, None
    # 关键词命中率
    hits = sum(1 for k in keywords if k in html)
    # 头条/百家号特征：HTML 极长但无标题词
    if hits == 0 and len(html) > 30000:
        return False, f"JS_RENDER: HTML {len(html)}字节，标题关键词 0/{len(keywords)} 命中（外部 referrer 不可见）"
    return True, None


def check_url(url, title=""):
    """对单个 URL 做健康检查。返回 (ok, code, reason)"""
    if not url or not url.startswith(("http://", "https://")):
        return False, None, "INVALID_URL"
    # SSL 容错：政府站点证书经常不信任
    http_ok = False
    http_code = None
    http_reason = ""
    for verify in (True, False):
        try:
            r = requests.head(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True, verify=verify)
            if 200 <= r.status_code < 400:
                http_ok, http_code, http_reason = True, r.status_code, "OK" if verify else "OK_INSECURE_SSL"
                break
            if r.status_code in (403, 405, 501):
                r2 = requests.get(url, headers={**HEADERS, "Range": "bytes=0-1024"},
                                  timeout=TIMEOUT, allow_redirects=True, stream=True, verify=verify)
                if 200 <= r2.status_code < 400 or r2.status_code == 416:
                    http_ok, http_code, http_reason = True, r2.status_code, "OK_VIA_GET"
                    break
                return False, r2.status_code, f"GET_{r2.status_code}"
            return False, r.status_code, f"HTTP_{r.status_code}"
        except requests.exceptions.SSLError:
            if verify:
                continue
            ok, code, reason = _check_via_curl(url)
            if ok:
                http_ok, http_code, http_reason = True, code, reason
                break
            return False, code, f"SSL_ERROR (curl: {reason})"
        except requests.exceptions.Timeout:
            return False, None, "TIMEOUT"
        except requests.exceptions.ConnectionError as e:
            return False, None, f"CONN_ERROR: {str(e)[:40]}"
        except Exception as e:
            return False, None, f"ERROR: {type(e).__name__}"

    if not http_ok:
        return False, http_code, "UNKNOWN"

    # HTTP 通过后再做 JS-render 检测（头条/百家号空壳）
    if title:
        ok, reason = _check_js_render(url, title)
        if not ok:
            return False, None, reason
    return True, http_code, http_reason


def run(window=None, soft_delete=False, max_workers=8):
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    if window:
        sql = "SELECT id, title, source, url, window FROM articles WHERE is_deleted=0 AND window=?"
        rows = conn.execute(sql, (window,)).fetchall()
    else:
        sql = "SELECT id, title, source, url, window FROM articles WHERE is_deleted=0"
        rows = conn.execute(sql).fetchall()

    if not rows:
        print(f"[WARN] 无文章需检查（window={window}）")
        conn.close()
        return

    print(f"[INFO] 检查 {len(rows)} 条文章的 URL（{max_workers} 并发）...\n")

    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(check_url, r["url"], r["title"]): r for r in rows}
        for fut in as_completed(futures):
            r = futures[fut]
            ok, code, reason = fut.result()
            results.append((r, ok, code, reason))

    # 排序：失败在前
    results.sort(key=lambda x: (x[1], x[0]["id"]))

    ok_count = sum(1 for _, ok, _, _ in results if ok)
    bad = [x for x in results if not x[1]]

    print(f"{'ID':>4s}  {'状态':6s} {'窗口':10s} {'来源':14s}  URL")
    print("-" * 100)
    for r, ok, code, reason in results:
        if ok:
            status = f"✅{code}"
        else:
            code_str = f"{code:>3d}" if code else "  -"
            status = f"❌{code_str}"
        print(f"  {r['id']:>3d}  {status:8s} {r['window']:10s} {r['source'][:14]:14s}  {r['url'][:60]}")
        if not ok:
            print(f"        └─ {reason}")

    print(f"\n[STATS] 正常 {ok_count} / 失效 {len(bad)} / 总 {len(results)}")

    if soft_delete and bad:
        print(f"\n[ACTION] 软删除 {len(bad)} 条失效链接...")
        for r, ok, code, reason in bad:
            conn.execute("""
                INSERT INTO articles_deleted_audit
                    (id, title, source, url, category, publish_date, window,
                     deleted_at, delete_reason, original_row_json)
                SELECT id, title, source, url, category, publish_date, window,
                       datetime('now','localtime'),
                       'URL_UNREACHABLE: ' || ?,
                       json_object('title',title,'url',url)
                FROM articles WHERE id=?
            """, (reason, r["id"]))
            conn.execute("UPDATE articles SET is_deleted=1 WHERE id=?", (r["id"],))
            print(f"  - #{r['id']} {r['title'][:40]}")
        conn.commit()
        print(f"[DONE] 软删除 {len(bad)} 条")

    conn.close()
    sys.exit(0 if not bad else 1)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--window", help="指定采集窗口日期 (如 2026-07-04)")
    p.add_argument("--soft-delete-broken", action="store_true",
                   help="自动软删除失效链接")
    p.add_argument("--workers", type=int, default=8, help="并发数")
    args = p.parse_args()
    run(window=args.window, soft_delete=args.soft_delete_broken, max_workers=args.workers)
