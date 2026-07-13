# -*- coding: utf-8 -*-
"""
将 data/public_accounts.json 的公众号文章自动分类后，
合并到 data/news_index.json 的 news 数组中。

处理规则：
- 普通文章：直接分类后合并到 news 数组。
- 汇编类文章（digest=true）：不合并其本身，而是拆解出 parsed_items，
  与已有新闻对比去重，仅输出「未收录」的条目及搜索关键词，
  供后续 WebSearch 查找原文后手动/自动补录。
"""
import json
import os
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")
IDX = os.path.join(DATA, "news_index.json")
GZH = os.path.join(DATA, "public_accounts.json")

# 类别关键词映射（优先级自上而下）
CATEGORY_RULES = [
    ("cat-standards", "标准动态", "&#9881;",
     ["标准", "国标", "征求意见", "报批稿", "标准化", "ISO", "GB/T", "GB "]),
    ("cat-investment", "投融资动态", "&#9733;",
     ["融资", "上市", "IPO", "募资", "估值", "投资", "天使轮", "A轮", "B轮",
      "C轮", "D轮", "挂牌"]),
    ("cat-policy", "政策法规", "&#9878;",
     ["政策", "法规", "实施", "规定", "监管", "准入", "通知", "意见", "指南",
      "管理办法", "实施细则", "安全要求"]),
    ("cat-technology", "技术动态", "&#9889;",
     ["技术", "研发", "系统", "芯片", "算法", "雷达", "传感器", "平台", "架构",
      "大模型", "端到端", "算力", "激光雷达", "计算平台", "OS", "操作系统",
      "方案", "自动驾驶系统", "智驾", "ADAS", "NOA", "城市NOA"]),
    ("cat-projects", "项目动态", "&#9874;",
     ["项目", "落地", "启动", "运营", "部署", "上线", "试点", "量产",
      "Robotaxi", "生产基地", "开城", "测试", "示范", "开通",
      "试点城市", "投入运营", "合作"]),
    ("cat-industry", "行业动态", "&#128200;",
     ["行业", "市场", "趋势", "报告", "数据", "预测", "分析", "展望",
      "销量", "渗透率", "巨头", "竞争", "布局", "观察", "深度",
      "解读", "观点", "评论", "白皮书", "蓝皮书"]),
]

DEFAULT_CAT = ("cat-industry", "行业动态", "&#128200;")


def classify(title, summary):
    """按关键词匹配返回 (cat_class, cat_name, cat_icon)。"""
    text = (title + " " + (summary or "")).lower()
    if re.search(r"robotaxi|自动驾驶出租车", text, re.IGNORECASE):
        return ("cat-projects", "项目动态", "&#9874;")
    for cat_cls, cat_name, icon, keywords in CATEGORY_RULES:
        for kw in keywords:
            if kw.lower() in text:
                return cat_cls, cat_name, icon
    return DEFAULT_CAT


def existing_titles_urls(idx):
    """返回已有新闻的 title set 和 url set，用于去重。"""
    titles = set()
    urls = set()
    for n in idx.get("news", []):
        titles.add(n.get("title", "").strip())
        urls.add(n.get("url", "").strip())
    return titles, urls


def keyword_overlap(text_a, text_b):
    """计算两段文本的关键词重叠程度（简单分词取公共子串）。"""
    # 提取2字以上的词（中文按字符bigram近似分词）
    def tokens(s):
        s = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", s.lower())
        return {s[i:i+2] for i in range(len(s)-1) if len(s[i:i+2]) >= 2}
    ta = tokens(text_a)
    tb = tokens(text_b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(len(ta), len(tb))


def main():
    if not os.path.exists(GZH):
        print("[SKIP] public_accounts.json 不存在")
        return

    gzh = json.load(open(GZH, encoding="utf-8"))
    items = gzh.get("items", [])
    if not items:
        print("[INFO] 公众号无数据")
        return

    idx = json.load(open(IDX, encoding="utf-8"))
    exist_titles, exist_urls = existing_titles_urls(idx)

    added = 0
    digest_new_items = []  # 汇编中未收录的条目

    for it in items:
        title = (it.get("title") or "").strip()
        url = it.get("real_url") or it.get("url") or ""
        is_digest = it.get("digest", False)

        if is_digest:
            # ── 汇编类文章：拆解条目，对比去重 ──
            parsed = it.get("parsed_items", [])
            print(f"\n[汇编] {title[:40]}")
            print(f"       共 {len(parsed)} 条子条目")
            for pi in parsed:
                # 与已有新闻标题做关键词重叠检测
                best_overlap = 0.0
                best_match = ""
                for et in exist_titles:
                    ov = keyword_overlap(pi, et)
                    if ov > best_overlap:
                        best_overlap = ov
                        best_match = et
                if best_overlap >= 0.35:
                    print(f"  ✓ [已收录] {pi[:50]} (相似度{best_overlap:.0%} → {best_match[:30]}...)")
                else:
                    print(f"  ★ [未收录] {pi[:50]} (需搜索原文)")
                    digest_new_items.append(pi)
            # 不合并汇编文章本身到 news 数组
            continue

        # ── 普通公众号文章：正常合并 ──
        if title in exist_titles or url in exist_urls:
            continue

        summary = (it.get("summary") or "")[:300]
        cat_cls, cat_name, icon = classify(title, summary)
        account = it.get("account", "")
        source = f"{account}（公众号）"

        entry = {
            "cat": cat_cls,
            "name": cat_name,
            "icon": icon,
            "title": title,
            "url": url,
            "source": source,
            "date": it.get("date", ""),
            "summary": summary,
            "_gzh": True,
        }
        idx["news"].append(entry)
        exist_titles.add(title)
        exist_urls.add(url)
        added += 1
        print(f"  + [{cat_name}] {source}: {title[:40]}")

    # ── 输出汇编中未收录条目，供后续搜索原文 ──
    if digest_new_items:
        print(f"\n{'='*60}")
        print(f"⚠ 汇编文章中发现 {len(digest_new_items)} 条未收录条目，需搜索原文：")
        print(f"{'='*60}")
        for i, item in enumerate(digest_new_items, 1):
            # 提取搜索关键词
            search_kw = item[:40].strip()
            print(f"  [{i}] {item}")
            print(f"      搜索关键词: {search_kw}")
        print(f"{'='*60}")
        print("提示：用 WebSearch 搜索上述关键词，找到原文后手动加入 news_index.json")

    if added:
        idx["total_news"] = len(idx["news"])
        counts = {}
        for n in idx["news"]:
            n_name = n.get("name", "")
            counts[n_name] = counts.get(n_name, 0) + 1
        idx["category_counts"] = counts
        idx["public_accounts_merged"] = added

        with open(IDX, "w", encoding="utf-8") as f:
            json.dump(idx, f, ensure_ascii=False, indent=2)
        print(f"\n[DONE] 合并 {added} 条公众号文章到主新闻，当前总计 {idx['total_news']} 条")
    else:
        print("\n[INFO] 无新公众号文章需要合并")

    if digest_new_items:
        print(f"[NOTE] 另有 {len(digest_new_items)} 条汇编子条目待搜索原文")


if __name__ == "__main__":
    main()
