# 三千要看

> 三千万象，一猫读尽。

每日自动聚合 26 个 RSS 源的英文/中文长文，由 AI 筛选、翻译、编排为四栏杂志，支持 Web 阅读和 Kindle 推送。

## 工作方式

1. **抓取** — 每天从 26 个 RSS 源拉取最新文章（18 个英文源 + 8 个中文源）
2. **筛选** — AI 按信息密度和可读性初筛，剔除短于 1200 字的文章
3. **选稿** — 四个栏目的 AI 编辑各自从候选池中挑选最契合的一篇
4. **翻译** — 英文文章由 DeepSeek/Gemini 翻译为中文，中文源直接保留
5. **发布** — 生成静态页面、EPUB，推送到 Kindle，部署到 GitHub Pages

## 每日栏目

| 栏目 | 选稿方向 |
|------|----------|
| 🔍 罪案 | 真实犯罪、卧底调查、骗局、悬案、法庭叙事 |
| 🎬 光影 | 电影/动画评论、导演访谈、影史回顾 |
| 🌍 切片 | 社会非虚构、国际议题、跨文化故事 |
| 🎲 今日意外 | 前三栏放不下的有趣文章，科学怪谈、个人散文、游戏文化等 |

## 内容来源

### 英文长文（18 源）
Aeon · The Atlantic · The New Yorker · The Guardian Long Read · Longreads · Harper's Magazine · London Review of Books · The Atavist · Rest of World · Nautilus · Quanta Magazine · The Ringer Movies · Vulture Movies · Anime News Network · Aftermath · Polygon · Rock Paper Shotgun

### 中文博客（8 源）
阮一峰 · 木遥的窗子 · 左岸读书 · 扯氮集 · 土木坛子 · 少数派 · 机核 · 月光博客

## 技术栈

- **语言**: Python 3.11+
- **Web 框架**: FastAPI + Jinja2
- **AI**: DeepSeek API（主）/ Gemini API（备）
- **内容提取**: Jina Reader API · readability-lxml · feedparser
- **EPUB 生成**: ebooklib
- **静态站点**: 自研构建器，专为 E-ink 和移动端优化
- **部署**: Render.com（Web + Cron）

## 项目结构

```
sanqian-reader/
├── pipeline.py          # 主流水线：抓取→筛选→选稿→翻译→出版
├── briefing.py          # 早报短管线（轻量版）
├── ai_client.py         # AI 客户端（翻译、选稿、剧透检测）
├── server.py            # FastAPI Web 服务
├── build_static.py      # GitHub Pages 静态站点生成
├── sender.py            # SMTP → Kindle EPUB 推送
├── models.py            # 数据模型（Article/Issue/CandidateArticle）
├── config.py            # 全局配置
├── db.py                # JSON 文件数据库
├── sources.yaml         # 26 个 RSS 源定义
├── sections.yaml        # 四栏位选稿规则
├── providers/           # 内容获取提供者（RSS/Jina/Readability）
├── templates/           # Jinja2 模板
├── static/              # 静态资源
├── data/                # 运行数据（文章缓存、期刊存档）
├── output/              # 生成的 EPUB
└── site/                # 生成的静态站点
```

## 本地运行

### 环境要求

- Python 3.11+
- DeepSeek API Key（翻译和选稿必需）

### 安装

```bash
git clone https://github.com/sanqiandawang/sanqian-reader.git
cd sanqian-reader
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 配置

```bash
cp .env.example .env
# 编辑 .env，填入你的 API Key 和邮件配置
```

必需环境变量：

| 变量 | 说明 |
|------|------|
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 |
| `SMTP_USER` / `SMTP_PASS` | Kindle 推送邮件账号 |
| `KINDLE_EMAIL` | 接收推送的 Kindle 邮箱 |
| `REFRESH_TOKEN` | Web 刷新接口的鉴权 token |

### 运行流水线

```bash
# 完整流水线（抓取 → 翻译 → 出版）
python pipeline.py

# 仅生成静态站点
python build_static.py

# 启动 Web 服务（http://localhost:8765）
python server.py

# 推送本期 EPUB 到 Kindle
python sender.py
```

### 一键启动（macOS）

双击 `启动三千要看.command` 启动 Web 服务。

## 部署

项目配置了 Render.com 蓝图部署（`render.yaml`）：

- **Web 服务**: FastAPI，免费计划
- **定时任务**: 每天 UTC 22:00 触发流水线刷新

也支持 GitHub Actions 手动推送（`.github/workflows/`）。

## 设计理念

- **宁缺毋滥** — 每栏最多 1 篇，选不出就空着
- **信息密度优先** — 短而精优于长而水
- **E-ink 友好** — Web 页面针对墨水屏和移动端优化排版
- **反推荐腔** — 编辑器笔记禁止使用"精彩纷呈""不容错过"等空洞推荐语

## License

MIT
