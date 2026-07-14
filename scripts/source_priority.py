# -*- coding: utf-8 -*-
"""
信息源优先级规则（第一梯队 > 第二梯队 > 第三梯队）。
在数据入库环节自动应用：
- 已存在第一梯队源时，丢弃后入的第二/三梯队文章
- 同标题文章保留 source_tier 最低的那个

用法:
    from scripts.source_priority import source_tier, pick_better_article

    t1 = source_tier("工信部", "https://www.miit.gov.cn/...")
    t2 = source_tier("My车轱辘", "https://www.163.com/...")
"""

# 第一梯队：政府/标准 / 整车企业 / 主流行业媒体
# 匹配方式：URL 域名 OR 来源名关键词
TIER1_RULES = {
    # 政府/标准/官方
    "gov": [
        "miit.gov.cn", "catarc.org.cn", "mot.gov.cn",
        "samr.gov.cn", "caam.org.cn", "caicv.org.cn",
        "ga.gov.cn", "jiangsu.gov.cn", "beijing.gov.cn",
        "sh.gov.cn", "sheitc.sh.gov.cn", "gxj.suzhou.gov.cn",
        "gxj.wuxi.gov.cn", "cs.com.cn", "stats.gov.cn",
        "gxcg.sh.gov.cn", "sheitc", "通信管理局",
        # 官方公众号
        "工信部", "公安部", "交通运输部", "上海市通管局",
        "智能网联汽车年鉴", "国家智能网联汽车创新中心",
    ],
    # 整车与自动驾驶企业官网
    "enterprise": [
        "auto.huawei.com", "pony.ai", "apollo.auto",
        "xiaopeng.com", "nio.cn", "nio.com", "horizon.auto",
        "blacksesame.com.cn", "byd.com", "tesla.cn",
        "weRide.ai", "deeproute.ai", "weride.ai", "motional.com",
    ],
    # 主流行业媒体（含主流财经媒体）
    "media": [
        "gasgoo.com", "i.gasgoo.com", "cheyun.com",
        "sohu.com", "ithome.com", "21jingji.com", "21cbh.com",
        "stcn.com", "cnstock.com", "yicai.com", "nbd.com.cn",
        "eeo.com.cn", "jiemian.com", "thepaper.cn",
        "cls.cn", "huxiu.com", "sina.com.cn", "new.qq.com", "news.qq.com",
        "eefocus.com", "eet-china.com", "autohome.com.cn",
        "36kr.com",         "高工智能汽车", "财联社", "证券时报",
        "第一财经", "经济观察报", "中国证券报", "上海证券报",
        "每日经济新闻", "21世纪经济报道", "经济日报", "人民日报",
        "新华日报", "环球网", "南方+", "南方周末",
        "深圳商报",
        # 正规媒体公众号
        "中国汽车报", "经济观察报", "证券时报", "财联社",
        "盖世汽车", "高工智能汽车", "车云", "车云网",
        "36氪", "界面新闻", "澎湃新闻",
    ],
}

# 已知个人账号 / 自媒体（第三梯队，永远不是第一梯队）
TIER3_KEYWORDS = [
    "车轱辘", "星球", "号", "君", "观察", "笔记", "深评",
    "辣评", "锐评", "热评", "谈车", "聊车", "侃车",
    "视角", "洞察", "锐评", "一探", "漫谈",
]

# 第二梯队：商业媒体但非头部 / 一般转载
TIER2_KEYWORDS = [
    "gongfeng", "wenku", "tupianzhi", "qudong",
    "100link", "sspai", "huxiu",
]


def is_english_source(source_name="", url=""):
    """检测来源是否为英文页面"""
    s = (source_name or "").lower()
    u = (url or "").lower()
    # 知名英文媒体
    en_domains = ["chinadaily.com", "bbc.com", "cnn.com", "reuters.com",
                  "bloomberg.com", "wsj.com", "nytimes.com", "apnews.com",
                  "theguardian.com", "techcrunch.com"]
    for d in en_domains:
        if d in u:
            return True
    # 来源名含英文媒体名
    en_names = ["china daily", "reuters", "bloomberg", "bbc", "cnn"]
    for n in en_names:
        if n in s:
            return True
    return False


def source_tier(source_name="", url=""):
    """判断来源所在梯队。返回 1/2/3，3 为最低优先级。"""
    s = (source_name or "").lower()
    u = (url or "").lower()

    # 非中文页面 → 降级（优先采用中文源）
    if is_english_source(s, u):
        return 3  # 强制最低梯队，会被中文源替代

    # 第一梯队匹配（URL 域名 或 源名称）
    for domain in TIER1_RULES["gov"]:
        if domain in u or domain.lower() in s:
            return 1
    for domain in TIER1_RULES["enterprise"]:
        if domain in u or domain.lower() in s:
            return 1
    for domain in TIER1_RULES["media"]:
        if domain in u or domain.lower() in s:
            return 1

    # 公众账号但不属于第一梯队 → 第二梯队
    if "公众号" in s or "weixin" in u:
        return 2

    # 显式个人账号 → 第三梯队
    for kw in TIER3_KEYWORDS:
        if kw in s:
            return 3

    # 第二梯队
    for kw in TIER2_KEYWORDS:
        if kw in s:
            return 2

    # 未知来源 → 第二梯队（保守）
    return 2


def pick_better(existing, candidate):
    """同一标题的两个候选中，选 source_tier 较小（更优）的那个。"""
    if not existing:
        return candidate
    if not candidate:
        return existing
    t1 = source_tier(existing.get("source", ""), existing.get("url", ""))
    t2 = source_tier(candidate.get("source", ""), candidate.get("url", ""))
    if t2 < t1:
        return candidate
    return existing
