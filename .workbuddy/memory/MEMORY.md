# 项目长期记忆 — 智能网联汽车新闻自动化监测

## 关键决策与配置
- **采集方式（v14 起升级）**：混合采集 = 浏览器 MCP 直采（第一优先级）+ WebSearch 补充（第二优先级）。
  - 浏览器 MCP 已配置：`~/.workbuddy/mcp.json` 写入 `@playwright/mcp`，工具前缀 `mcp__playwright__browser_*`。
  - 直采实操：用 `browser_navigate` + `browser_evaluate`（JS 提取 `a` 标签的标题/URL/日期）；CATARC 列表用相对路径，需补域名 `https://www.catarc.org.cn`。
  - v13 及之前版本仅用 WebSearch，banner 标注"基于 WebSearch 实时检索"。
- **运行环境**：Playwright Chromium 已安装至 `C:\Users\18351\AppData\Local\ms-playwright\`；node 用 managed `22.22.2`，python 用 managed `3.13.12`。
  - **含 playwright 的 venv 路径**：`C:/Users/18351/.workbuddy/binaries/python/envs/default/Scripts/python.exe`（普通脚本用 `versions/3.13.12/python.exe`，需要 playwright 的脚本用此 venv）。
- **日报生成**：基于 `templates/daily_template.html`（含完整 CSS/JS），用 Python 脚本生成：`python C:\Users\18351\AppData\Local\Temp\gen_report.py <日期> <版本号> [窗口日期]`。脚本从模板读取 CSS，替换 hero/stats/sections 生成 `reports/daily/YYYY-MM-DD_vN.html`。
- **版本号规则**：按天重置，每天第一版为 v1，当天内重新生成为 v2、v3 递增。
- **数据文件**：`data/news_index.json`（全量新闻索引，含 cat/name/icon/title/url/source/date/summary）、`data/last_update.json`（version/total_news/category_counts/data_source）。
- **新闻入库（SQLite）**：2026-07-10 起使用统一数据库 `data/icv_news.db`，含两张核心表：
  - `articles`：新闻主表（字段：title/source/source_type/url[UNIQUE]/publish_date/collected_at/category/summary/window/importance/keywords），合并原 news 表和 public_accounts 表；
  - `collect_log`：采集运行日志（run_date/version/window/total_articles/categories/source_summary 等），替代 last_update.json。
  - 入库脚本 `scripts/import_news_to_db.py`：读 `news_index.json` → `INSERT OR IGNORE`（按 url 去重），同时写入 collect_log。
  - 旧 `data/news.db` 保留未删除，作为历史备份。
- **采集窗口与凑数规则（v15 起，用户明确）**：新闻发布日期只采集前 1 天（运行日 -1，单一日期窗口），超出一律剔除；某类别在窗口内无信息则显示「暂无更新」空区块，**禁止为凑满 5×2 而硬塞**。生成前需先在窗口内真实补采一轮，确认没漏窗口内新新闻再生成。

## 公众号数据采集可行性（2026-07-09 实测）
- **结论：可间接采集，但只能作第3优先级补充源，不稳。**
- WebSearch 直搜 `mp.weixin.qq.com`：几乎无结果（公众号文章不进通用搜索索引）。
- 浏览器 MCP + 搜狗微信 `https://weixin.sogou.com/weixin?type=2&query=<关键词>`：可拿到公众号文章**标题列表**（中转链接 `/link?url=...` 形式，如"智能网联汽车"实测返回9条真实标题）。
- **正文实测可获取（2026-07-09 验证）**：点开搜狗中转链→跳转 `mp.weixin.qq.com/s?...` 成功，拿到标题+公众号名(如"智能制造IM")+正文(635字)。微信文章公开可访问，无需登录。限制：① 须经搜狗中转二次跳转，列表里只有 `/link?url=` 中转链无直链；② 中转链带 timestamp 签名有时效(约数小时)，过期需重搜；③ 高频请求会被搜狗/微信反爬拦截(验证码)。
- 建议若集成：列表页抓标题+公众号名+中转链做索引；仅对重点条目二次跳转取正文，控频避免反爬。

## 信息源要点（来自方案 .trae/documents/智能网联汽车新闻自动化监测方案.md）
- 政府/标准一手源：工信部、CATARC、国标全文公开系统、CAICV；20 个车路云试点城市工信局。
- 行业媒体：盖世汽车、车云网、高工智能、36氪等（部分官网失效，改 WebSearch 定向搜）。
- 企业一手源：华为乾崑、小马智行、百度Apollo、小鹏、蔚来、地平线、文远知行、Momenta 等（有官网优先浏览器抓，无新闻页用 WebSearch）。
- 分类：政策法规 / 标准动态 / 投融资动态 / 技术动态 / 项目动态 / 行业动态（6 类）。

## 版本记录
- v13 (2026-07-09 09:09)：纯 WebSearch，10 条。
- v14 (2026-07-09 09:25)：浏览器直采+WebSearch，10 条，新增 3 条官网一手源。
- v15 (2026-07-09 09:30 起多次微调)：窗口逐步收紧 前3天→前2天→前1天；最终窗口=只采集前1天(2026-07-08)，5 条(政策1/标准1/投融资1/技术2/项目0 暂无更新)；剔除超期6/26、7/2、及窗口外7/7新闻。页脚已去括号与版本号。
- v1 (2026-07-10)：**版本号按天重置**。窗口=2026-07-09，11条(政策1/标准1/投融资1/技术2/项目6含3条公众号/行业0)。MCP添加HEADLESS=true；公众号归入主分类；新增行业动态第6类。每天第一版=当天v1，更新才递增。

## 公众号采集与分类合并（v16 起，公众号内容归入主分类）
- 脚本（venv `C:/Users/18351/.workbuddy/binaries/python/envs/default/Scripts/python.exe` 已装 playwright）：`scripts/collect_public_accounts.py` 经搜狗微信按关键词(智能网联汽车/自动驾驶/Robotaxi/智能驾驶/车路云)检索→提取标题+公众号名+日期+中转链→窗口过滤(前1天)→二次跳转取正文摘要(控频)→输出 `data/public_accounts.json`。
- **归入主分类（v16 起）**：`scripts/merge_public_accounts.py` 按标题/摘要关键词自动分类，合并到 `news_index.json` 的 `news` 数组（5类主新闻），不再显示独立「公众号补充」区块。`insert_gzh_section.py` 已废弃。
- 入库：`scripts/import_public_accounts.py` 写 `news.db` 的 `public_accounts` 表(real_url UNIQUE 去重，可反复运行)。`import_news_to_db.py` 仍会通过 news_index.json 写入主 news 表。
- **每日流程串联顺序（v16 起）**：官网直采+WebSearch 生成 news_index.json → collect_public_accounts.py（需用 venv python） → merge_public_accounts.py → **generate_overview.py（新增：从标题提炼概览文本写入 JSON+DB）** → score_articles.py（重要性评分1-5） → fetch_full_content.py batch（抓正文全文） → gen_report.py 生成日报 HTML → import_news_to_db.py（写入 icv_news.db + 生成每日快照）。
- 注意：搜狗微信有频控，无头环境高频会弹验证码；微信文章链接带 timestamp 签名有时效，长期存档建议未来改存纯文章 ID。

## Web 入口（2026-07-13 完成）
- `web/app.py` Flask 后端，`web/templates/index.html` 单页前端
- 顶部导航：日报 / 周报 / 月报 / 数据查询
- 日报：日历组件 + iframe 内嵌报告，标题链接 `target="_blank"` 新窗口打开原文
- 周报：iframe 内嵌报告，底部往期回顾列表，文章点击弹窗（父页面级全局弹窗，通过 `postMessage` 跨 iframe 通信）
- 弹窗：显示全文 + 底部"查看原文"链接（`target="_blank"`），打开时保持父页面滚动位置
- 日报/周报顶部新增"概览"板块：卡片网格布局，每类有标题+bullet列表，每条截断至55字
