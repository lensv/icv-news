"""
智能网联汽车新闻过滤与分类共享模块。
供 collect_all_sites.py、collect_ci.py 等采集脚本引用。
"""
import re

CAT_KEYS = {
    "政策法规": ["工信部", "公安部", "交通部", "政策", "法规", "条例", "管理办法", "准入", "实施细则",
                 "数据安全", "网络安全", "立法", "监管", "审议", "印发", "通知", "意见", "试行"],
    "标准动态": ["标准", "国标", "GB", "GA/T", "规范", "UN", "WP.29", "标准立项", "征求意见",
                 "标准发布", "标准修订", "团体标准", "R157", "ISO"],
    "投融资动态": ["融资", "投资", "上市", "IPO", "估值", "天使轮", "A轮", "B轮", "C轮", "D轮",
                   "并购", "收购", "产业基金", "战略合作", "融资", "募资", "注资"],
    "技术动态": ["自动驾驶", "L2", "L3", "L4", "L5", "FSD", "智驾", "ADS", "NOA", "算法", "雷达",
                 "激光雷达", "毫米波", "摄像头", "传感器", "芯片", "大模型", "端到端", "VLA",
                 "感知", "融合", "OTA", "车路协同", "V2X", "高精地图", "决策", "计算平台",
                 "辅助驾驶", "智能网联汽车", "智能网联", "C-V2X", "HSD", "域控"],
    "项目动态": ["Robotaxi", "测试", "量产", "交付", "落地", "试点", "运营", "示范", "牌照",
                 "路测", "试运营", "商业化", "内测", "开城"],
    "行业动态": ["行业", "市场", "销量", "渗透率", "数据", "报告", "占比", "白皮书", "排行",
                 "出海", "竞争", "趋势", "论坛", "会议", "博览会"],
}


def filter_icv(title):
    """过滤：白名单制，只保留智能网联汽车相关新闻"""
    text = title.strip()

    # === 噪音黑名单（扩充至 30+ 项）===
    noise = [
        '千帆星座', '组网卫星', '卫星发射', '海洋', '水库', '应急通信',
        '台风', '抢险', '抗震', '防汛',
        '工业通信', '工业自动化', '工业互联网', '智能制造试点', '汇智同步',
        '机动车注册登记', '机动车登记', '出厂合格证信息', '注册登记业务', '机动车检测', '报废机动车',
        '充换电设施补短板', '充电桩建设', '充换电站',
        '铁路', '轨道交通', '民航', '桥梁', '隧道工程',
        '粮食', '农业', '卫生健康', '医保', '教育', '火灾',
    ]
    for n in noise:
        if n in text:
            return False

    # ========== 白名单分层 ==========

    # 层级1：强相关关键词 → 直接保留
    strong = ['智能网联汽车', '智能网联', '自动驾驶', '智能驾驶',
              '智驾', 'Robotaxi', '车路云', '组合驾驶辅助',
              '智能座舱', '辅助驾驶', '无人驾驶', '车联网', 'C-V2X']
    for kw in strong:
        if kw in text:
            return True

    # 层级2：技术关键词 → 直接保留
    tech = ['L2', 'L3', 'L4', 'L5', 'FSD', 'NOA', 'V2X', '激光雷达',
            '城市NOA', '线控转向',
            '端到端', 'VLA', '毫米波雷达', '高精地图', '车路协同', '感知融合', 'ADAS']
    for kw in tech:
        if kw in text:
            return True

    # 层级3：公司名 + 新闻动词 → 组合保留（防官网产品页）
    companies = ['华为', '比亚迪', '特斯拉', '蔚来', '小鹏', '理想', '小米',
                 '零跑', '哪吒', '阿维塔', '极狐', '地平线', '黑芝麻',
                 'Momenta', '文远知行', '小马智行', '百度Apollo', '滴滴',
                 '大疆', '卓驭', '元戎启行',
                 '速腾聚创', '禾赛', 'Waymo', 'Cruise', 'Zoox']
    news_verbs = ['发布', '量产', '交付', '融资', '上市', '合作', '签约',
                  '测试', '运营', '上线', '落地', '首发', '推出', '公布',
                  '宣布', '获批', '开通', '启动', '投产', '投资', '收购',
                  '入股', '开放', '打入', '登陆', '挂牌',
                  '开城', '获牌', '获得许可', '部署', '获得认证']
    has_company = any(c in text for c in companies)
    has_verb = any(v in text for v in news_verbs)
    if has_company and has_verb:
        return True

    # 层级4：泛汽车词 + ICV特有关键词 → 组合保留
    car_words = ['汽车', '车辆', '新能源']
    icv_specific = ['智能网联', '自动驾驶', '智驾', 'ADAS', 'FSD', 'NOA',
                    'L2', 'L3', 'L4', 'L5', '雷达', '传感器', '芯片', '域控', 'V2X',
                    'OTA升级', '路测', '牌照', '示范应用', 'Robotaxi',
                    '渗透率', '搭载率', '产销', '组合驾驶辅助']
    has_car = any(w in text for w in car_words)
    has_icv = any(w in text for w in icv_specific)
    if has_car and has_icv:
        return True

    # 层级5：国标/GB → 复合判断（排除非汽车国标）
    if '国标' in text or 'GB ' in text:
        if any(ctx in text for ctx in ['汽车', '车辆', '驾驶', '智能', '智驾', '新能源', '充电',
                                        'L2', 'L3', 'L4', '组合驾驶辅助', 'GB 47955',
                                        '道路机动车辆', '乘用车', '制动', '转向', '碰撞',
                                        '功能安全', '预期功能安全', '信息安全', '数据安全']):
            return True
        return False  # 排除非汽车国标

    # 层级6：数据类（数字+单位） → 兜底保留
    if re.search(r'[0-9]+万[辆台]|[0-9]+亿[元]|robotaxi|autopilot', text, re.IGNORECASE):
        return True

    return False


def classify(title, summary=""):
    text = title + " " + (summary or "")
    for cat, kws in CAT_KEYS.items():
        if any(kw in text for kw in kws):
            return cat
    return ""  # 不再默认 fallback 到行业动态


def validate_url(url):
    """校验 URL 是否有效，防止假链接/占位符进入数据库。返回 True 表示可用。"""
    if not url or not isinstance(url, str):
        return False
    url = url.strip()
    # 必须是 http 或 https
    if not url.startswith(("http://", "https://")):
        return False
    # 禁止已知的占位/测试域名
    banned_domains = [
        "example.com", "example.org", "test.com",
        "localhost", "127.0.0.1", "0.0.0.0",
    ]
    from urllib.parse import urlparse
    try:
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower()
        for bd in banned_domains:
            if hostname == bd or hostname.endswith("." + bd):
                return False
        # 必须至少包含一个点（有效的域名格式）
        if "." not in hostname:
            return False
        # 拒绝明显的占位/垃圾路径（article/xxx、page/test 等）
        path = (parsed.path or "").lower()
        garbage_patterns = ["/xxx", "/test/", "/abc", "/test.", "/undefined", "/null"]
        for gp in garbage_patterns:
            if gp in path:
                return False
        return True
    except Exception:
        return False
