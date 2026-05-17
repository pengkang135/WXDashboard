# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

WXDashboard — 微信工作群消息管理系统。核心应用场景:孟加拉 Laldia 港口建设项目(港湾工程)的微信群聊记录归档、检索与分析。通过 `wx-cli` (npm) 读取本地微信数据库,经 `sync_engine.py` 解析写入 SQLite + FTS5 全文索引,Flask 提供 Web 仪表盘进行浏览和搜索。

## 常用命令

```bash
# 启动开发服务器
python -m backend.app                           # 启动 Flask,监听 127.0.0.1:8888

# 或使用 bat 脚本(初始化 DB + 启动)
start_ledger.bat

# 数据同步
python -c "from backend.sync_engine import sync_incremental; print(sync_incremental())"     # 增量同步最新消息
python -c "from backend.sync_engine import sync_full; print(sync_full('群名'))"              # 全量拉取指定群
python -c "from backend.sync_engine import sync_all_groups_full; sync_all_groups_full()"     # 全量拉取所有群
python -c "from backend.sync_engine import discover_new_groups; print(discover_new_groups())" # 发现新群

# 搜索
python -c "from backend.database import search_messages; print(search_messages('关键词'))"

# 遗留数据导入
python -m backend.import_legacy
```

## 架构

```
本地微信加密DB → [wx-cli (npm)] → sync_engine.py → SQLite + FTS5 → Flask REST API → 浏览器SPA
```

### 目录结构

```
WXDashboard/
├── backend/                 # Python 后端包
│   ├── app.py              # Flask 主应用 + 自动同步线程
│   ├── config.py           # 路径与端口配置
│   ├── database.py         # SQLite schema + FTS5 + CRUD
│   ├── sync_engine.py      # wx-cli 调用、类别推断、消息入库
│   ├── contact_extractor.py # 正则提取邮箱与手机号
│   └── import_legacy.py    # 旧版 Excel/JSON 台账导入
├── static/
│   ├── app.js              # 前端 SPA 逻辑(含自动刷新)
│   ├── style.css           # 样式(CSS 变量设计系统)
│   └── favicon.svg         # SVG 图标
├── templates/
│   └── dashboard.html      # 主页面模板
├── data/                    # SQLite 数据库(自动创建)
├── Laldia/                  # 项目示例数据(不上传仓库)
├── docs/                    # 设计文档
├── .originfiles/            # 临时/原始文件(不上传仓库)
├── requirements.txt
├── start_ledger.bat
└── .gitignore
```

### 分层

| 层 | 文件 | 职责 |
|---|---|---|
| 数据采集 | `backend/sync_engine.py` | 通过 subprocess 调用 `wx` CLI,解析 JSON 输出,类别推断,去重入库 |
| 数据层 | `backend/database.py` | SQLite schema (groups/messages/contacts/sync_log), FTS5 全文搜索,CRUD |
| Web API | `backend/app.py` | 15 个 REST 端点,Flask 开发服务器,后台自动同步线程 |
| 前端 | `templates/dashboard.html`, `static/app.js`, `static/style.css` | 原生 JS SPA,无框架,前端缓存 + 自动刷新 |

### 核心依赖

- **外部工具**: `wx-cli` (npm 全局安装),需能读取本地微信 `MSG.db`
- **Python**: `flask`, `openpyxl` (参 `requirements.txt`)
- **数据库**: `data/ledger_v2.db` — SQLite WAL 模式,启用外键
- **入口**: `python -m backend.app` (或 `start_ledger.bat`)

### 数据库核心表

- `groups` — 微信群元数据(名称、类别、子类别、项目、合作方、备注)
- `messages` — 消息记录,`(group_id, local_id)` UNIQUE 去重,含 raw_json 原文
- `contacts` — 从消息中提取的邮箱/手机号,按 `(group_id, sender_name, email, phone)` 去重
- `messages_fts` — FTS5 虚拟表,索引 `group_name + sender + content`,触发器自动同步
- `sync_log` — 同步审计日志

### 群组分类体系

八类(含子类):内部沟通、设计院合作、施工局合作、地基处理、建筑MEP、供应商询价、保险、物流。类别推断规则见 `sync_engine.py` 中的 `infer_category()`,子类别推断见 `_infer_subcategory()` (25 条规则)。

### 前端交互要点

- 项目选择器:标题下拉切换项目,自动发现 `/api/projects`
- 左侧分类标签页:内部(上部)含 内部沟通/施工局合作/设计院合作,外部(下部)含 供应商咨询/地基处理/建筑MEP/保险
- 群组行颜色:绿色(≤3天)、琥珀色(3-7天)、红色(>7天)
- 点击行打开右侧抽屉:分页显示消息(50条/页)、自动提取的联系人信息
- 搜索面板:全库 FTS5 搜索,sender/content 范围
- 自动刷新:工具栏时钟按钮,可选 30s/1m/2m/5m 间隔,后台静默同步,有新消息自动更新表格

### API 端点一览

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/groups` | 群组列表(支持 category/project 筛选) |
| GET | `/api/groups/<id>` | 群组详情 |
| GET | `/api/groups/<id>/messages` | 分页消息(limit/offset) |
| GET | `/api/groups/<id>/messages/latest` | 最近 N 条消息 |
| GET | `/api/groups/<id>/contacts` | 群组联系人 |
| POST | `/api/groups/<id>/subcategory` | 设置子类别 |
| GET | `/api/categories` | 分类列表 |
| GET | `/api/search` | FTS5 全文搜索 |
| GET | `/api/projects` | 项目列表 |
| GET | `/api/sync/status` | 同步统计 |
| POST | `/api/sync/refresh` | 增量同步 |
| POST | `/api/sync/pull-all` | 全量拉取(可指定群) |
| POST | `/api/sync/discover` | 发现新群组 |
| POST | `/api/sync/auto/start` | 启动自动同步(参数 interval 秒) |
| POST | `/api/sync/auto/stop` | 停止自动同步 |
| GET | `/api/sync/auto/status` | 自动同步状态 |

### 关键路径/常量

- Excel 台账: `Laldia/Laldia港湾微信群台账.xlsx` sheet "微信群台账"
- JSON 导出: `Laldia/wx_json/*.json`
- 旧版归档: `Laldia/微信群归档_legacy/`
- 设计决策记录: `Laldia/设计方案决策记录.md`
- 设计文档: `docs/`
- 临时文件: `.originfiles/` (已加入 .gitignore)

## AI 辅助操作

Claude Code 对本项目的 AI 介入定位:**信息筛选与整理**，让微信群工作信息更清晰展示。不涉及比价、问答、语义搜索、风险预警。所有 AI 处理均在 Claude Code 会话中完成，不接入外部 API。

### 群组智能分类

当有未分类或分类存疑的群时:

1. 查询 `SELECT name FROM groups WHERE category IS NULL OR category = ''`
2. 取群名 + 该群最近 5 条消息 (`SELECT content, sender FROM messages WHERE group_id=? ORDER BY timestamp DESC LIMIT 5`)
3. 参照现有分类体系（内部沟通、设计院合作、施工局合作、地基处理、建筑MEP、供应商询价、保险、物流）判断类别
4. 通过 `/api/groups/<id>/subcategory` 写入 `category` 和 `sub_category`
5. 如判断不确定，标记为"待确认"并给出理由，不强行分类

### 群聊摘要生成

按需对指定群、指定时段生成摘要:

1. 从 `messages` 表读取目标消息: `SELECT sender, content, timestamp FROM messages WHERE group_id=? AND timestamp BETWEEN ? AND ? ORDER BY timestamp`
2. 生成结构化摘要，输出格式:
   - **要点**: 讨论了什么
   - **决策**: 定了什么事
   - **待办**: 谁需要跟进什么
3. 摘要写入 `.originfiles/AIWork/summaries/<群名>_<日期>.md`
4. 如需要，可同时写入 `ai_summaries` 表供前端调用

### 关键信息提取

按需从群消息中提取结构化信息:

1. 从 `messages` 表读取目标群、目标时段消息
2. 按以下维度提取:
   - 联系人信息（公司名、职位）
   - 技术参数（规格、标准、指标值）
   - 工期节点（计划日期、里程碑事件）
   - 文件/图纸引用（编号、版本）
3. 提取结果写入 `.originfiles/AIWork/extractions/<群名>_<日期>.md`
4. 如需要，可同时写入 `ai_extractions` 表供前端调用

### AI 产出物存放

| 类型 | 文件路径 | 用途 |
|------|---------|------|
| 摘要 | `.originfiles/AIWork/summaries/<群名>_<日期>.md` | 版本可追踪的 Markdown |
| 信息提取 | `.originfiles/AIWork/extractions/<群名>_<日期>.md` | 版本可追踪的 Markdown |

## 项目改造背景

当前项目是方案一(Flask+SQLite)的落地实现。改造目标是将静态 HTML/JSON 台账(原方案)升级为支持动态刷新、分类筛选、全文检索的交互式 Web 应用。`docs/` 目录包含完整的方案设计、需求对照和后续 Docker/AI 增强规划。
