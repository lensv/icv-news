"""编译完整新闻集并生成 JSON"""
import json

WINDOW = '2026-07-12'

news = [
    # ===== 标准动态 =====
    {
        "title": "GB 47955—2026《智能网联汽车 组合驾驶辅助系统安全要求》强制性国家标准正式发布",
        "cat": "标准动态", "source": "工信部/人民日报",
        "url": "https://www.miit.gov.cn/jgsj/zbys/qcgy/art/2026/art_...",
        "summary": ""
    },
    {
        "title": "我国牵头制定的联合国自动驾驶系统全球技术法规（ADS GTR）获批发布",
        "cat": "标准动态", "source": "工信部",
        "url": "https://www.miit.gov.cn/xwfb/gxdt/sjdt/art/2026/art_...",
        "summary": ""
    },
    {
        "title": "华为乾崑引望核心参与L2强标制定",
        "cat": "标准动态", "source": "华为乾崑",
        "url": "https://auto.huawei.com/cn/news",
        "summary": ""
    },
    # ===== 政策法规 =====
    {
        "title": "工业和信息化部等五部门联合启动2026年新能源汽车下乡活动",
        "cat": "政策法规", "source": "工信部",
        "url": "https://www.miit.gov.cn/xwfb/gxdt/sjdt/art/2026/art_...",
        "summary": ""
    },
    {
        "title": "智能网联汽车保险纠纷成北京金融法院关注焦点，智驾保险体系建设提速",
        "cat": "政策法规", "source": "中国经营报/新浪财经",
        "url": "https://cj.sina.com.cn/articles/view/1650111241/625ab30902001gw3w",
        "summary": ""
    },
    {
        "title": "关于组织开展2026年度道路机动车辆生产企业及产品生产一致性监督检查工作的通知",
        "cat": "政策法规", "source": "工信部",
        "url": "https://www.miit.gov.cn/jgsj/zbys/gzdt/art/2026/art_...",
        "summary": ""
    },
    # ===== 技术动态 =====
    {
        "title": "全球量产最高规格896线！华为乾崑发布新一代双光路图像级激光雷达",
        "cat": "技术动态", "source": "华为乾崑",
        "url": "https://auto.huawei.com/cn/news",
        "summary": ""
    },
    {
        "title": "高阶智驾加速下沉至大众市场，零跑已将城市NOA落地至8万元级车型",
        "cat": "技术动态", "source": "中国新闻网",
        "url": "https://view.inews.qq.com/a/20260712A05JRL00",
        "summary": ""
    },
    {
        "title": "特斯拉FSD v14 Lite首次走出美国，韩国成为全球首个获得更新的海外市场",
        "cat": "技术动态", "source": "IT之家",
        "url": "https://view.inews.qq.com/a/20260712A039TS00",
        "summary": ""
    },
    {
        "title": "2026华为乾崑技术大会即将召开",
        "cat": "技术动态", "source": "华为乾崑",
        "url": "https://auto.huawei.com/cn/news",
        "summary": ""
    },
    # ===== 项目动态 =====
    {
        "title": "特斯拉Cybercab即将在得州超级工厂向员工开放试乘体验",
        "cat": "项目动态", "source": "IT之家",
        "url": "https://www.163.com/dy/article/L1KDFB3N0511B8LM.html",
        "summary": ""
    },
    {
        "title": "小鹏Robotaxi正式开启员工内测，何小鹏完成首单并兼任机器人业务负责人",
        "cat": "项目动态", "source": "21世纪经济报道",
        "url": "https://view.inews.qq.com/a/20260712A04M4K00",
        "summary": ""
    },
    {
        "title": "2026京津冀新能源和智能网联汽车产业链对接活动在廊坊举办",
        "cat": "项目动态", "source": "河北新闻网",
        "url": "https://hebei.news.163.com/26/0712/10/L1KN5INQ04159CNM.html",
        "summary": ""
    },
    {
        "title": "2026世界智能安全大会专题会议：智能网联汽车预期功能安全精彩回顾",
        "cat": "项目动态", "source": "FISITA/公众号",
        "url": "https://mp.weixin.qq.com/s?src=11&...",
        "summary": ""
    },
    # ===== 投融资动态 =====
    {
        "title": "临界点完成近10亿元融资，投后估值超10亿美元",
        "cat": "投融资动态", "source": "盖世汽车",
        "url": "https://i.gasgoo.com/news/c-601-14.html",
        "summary": ""
    },
    # ===== 行业动态 =====
    {
        "title": "工信部：2026上半年国内乘用车L2级自动驾驶搭载率达70%，NOA车型占比超30%",
        "cat": "行业动态", "source": "工信部",
        "url": "https://www.miit.gov.cn/xwfb/gxdt/sjdt/art/2026/art_...",
        "summary": ""
    },
    {
        "title": "特斯拉46天拆除Model S/X生产线，改造为Optimus人形机器人生产基地",
        "cat": "行业动态", "source": "红星新闻",
        "url": "https://view.inews.qq.com/a/20260712A06DB600",
        "summary": ""
    },
    {
        "title": "2026年5月汽车工业经济运行情况发布",
        "cat": "行业动态", "source": "工信部",
        "url": "https://www.miit.gov.cn/xwfb/gxdt/sjdt/art/2026/art_...",
        "summary": ""
    },
    {
        "title": "两部门约谈提醒涉嫌非理性竞争汽车生产企业",
        "cat": "行业动态", "source": "工信部",
        "url": "https://www.miit.gov.cn/jgsj/zbys/qcgy/art/2026/art_...",
        "summary": ""
    },
]

for item in news:
    item["date"] = WINDOW

cat_counts = {}
for item in news:
    cat_counts[item["cat"]] = cat_counts.get(item["cat"], 0) + 1

data = {
    "news": news,
    "total_news": len(news),
    "category_counts": cat_counts,
    "data_source": f"Playwright 直采 + WebSearch window={WINDOW}",
}

path = r"E:\trae_solo\自动化监测智能网联汽车新闻\data\news_index.json"
with open(path, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print(f"OK: {len(news)} items, cats: {cat_counts}")
