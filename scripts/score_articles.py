# -*- coding: utf-8 -*-
"""
新闻重要性评分。规则基于《后续开发需求说明书》4.4节。

评分标准：
  5 = 重大政策/标准发布、重大投融资事件
  4 = 重要企业动态、技术突破
  3 = 一般性行业新闻、项目进展
  2 = 地方性动态、补充信息
  1 = 轻微动态、转载新闻

用法：
  python scripts/score_articles.py          # 为 news_index.json 打分 + 更新 DB
  python scripts/score_articles.py --dry   # 仅预览，不写文件
"""
import json
import os
import re
import sqlite3
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IDX = os.path.join(BASE, "data", "news_index.json")
DB = os.path.join(BASE, "data", "icv_news.db")

# 评分规则：关键词命中即得对应分数（优先级从上到下，取最高分）
RULES = [
    (5, [
        # 重大政策/标准发布
        "国标", "GB ", "强制", "强制性国家标准",
        "正式发布", "批准发布", "发布实施",
        # 重大投融资
        "上市", "IPO", "挂牌", "登陆港交所", "敲钟",
        "估值.*亿", "融资.*亿", "募资.*亿",
        # 重大技术/商用里程碑
        "全无人.*运营", "L3.*商用", "L3.*量产",
        "Robotaxi.*全无人",
    ]),
    (4, [
        # 重要企业动态、技术突破
        "量产落地", "规模量产", "量产交付",
        "技术突破", "重大突破", "首发", "首款",
        "商业运营", "商业化",
        "前装量产", "定点", "战略合作",
        "Robotaxi.*内测", "Robotaxi.*运营",
        # 重要国际动态
        "NHTSA", "方向盘.*取消", "无人驾驶.*上路",
        # 重要数据
        "渗透率", "产销.*增长",
    ]),
    (3, [
        # 一般性新闻、项目进展
        "项目", "落地", "启动", "上线", "部署",
        "生产基地", "投入运营", "量产",
        "融资", "投资", "天使轮", "A轮", "B轮",
        "合作", "签约", "共建",
        # 行业报告/数据
        "报告", "数据", "趋势", "运行情况",
        # 一般性动态
        "Robotaxi", "自动驾驶",
        "智能网联",
    ]),
    (2, [
        # 地方性动态
        "地方", "某市", "试点城市", "示范区",
        "征求意见", "草案", "公示",
        "通知", "征集",
    ]),
]


def score_article(title, summary):
    """返回重要性评分 1-5。"""
    text = (title + " " + (summary or "")).lower()
    for score, keywords in RULES:
        for kw in keywords:
            if re.search(kw.lower(), text):
                return score
    return 1  # 默认最低分


def main():
    dry_run = "--dry" in sys.argv
    if not os.path.exists(IDX):
        print("[ERR] news_index.json 不存在")
        return

    data = json.load(open(IDX, encoding="utf-8"))
    changed = 0
    for item in data.get("news", []):
        old = item.get("importance", 0)
        new = score_article(item.get("title", ""), item.get("summary", ""))
        if old != new:
            item["importance"] = new
            changed += 1

    if changed:
        # 更新 JSON
        if not dry_run:
            with open(IDX, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        # 同步更新 DB
        if not dry_run and os.path.exists(DB):
            conn = sqlite3.connect(DB)
            updated_db = 0
            for item in data.get("news", []):
                url = item.get("url", "")
                score = item.get("importance", 0)
                conn.execute(
                    "UPDATE articles SET importance = ? WHERE url = ?",
                    (score, url)
                )
                if conn.total_changes:
                    updated_db += conn.execute("SELECT changes()").fetchone()[0]
            conn.commit()
            conn.close()
            print(f"  DB 更新 {updated_db} 条")

        print(f"[OK] {changed} 条评分已更新" + ("（预览模式，未写入）" if dry_run else ""))
    else:
        print("[INFO] 无需更新")

    # 打印评分分布
    scores = {}
    for item in data.get("news", []):
        s = item.get("importance", 0)
        scores[s] = scores.get(s, 0) + 1
    print("  评分分布:", dict(sorted(scores.items())))


if __name__ == "__main__":
    main()
