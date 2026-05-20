# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

WXDashboard — 微信工作群消息管理系统。对所有工作微信群聊记录进行归档、检索与信息筛选管理。通过 `wx-cli` (npm) 读取本地微信数据库,经 `sync_engine.py` 解析写入 SQLite + FTS5 全文索引,Flask 提供 Web 仪表盘进行浏览和搜索。

# 行为准则

1. **Ask, don't assume:** If requirements are ambiguous, list the tradeoffs or options and ask for clarification before writing a single line of code.
2. **Simplest solution first:** Write the minimum viable code to solve the problem. Avoid speculative abstractions or over-engineering.
3. **Surgical changes:** Only touch the files and functions required for the current task. Do not make unrelated structural edits, drive-by refactoring, or style changes.
4. **Goal-driven execution:** Provide verifiable success criteria (like unit tests) and allow the AI to loop until those tests pass, rather than issuing vague commands

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
├── .claude/
│   └── skills/
│       ├── wechat-classify.md    # 新群快速分类（haiku，高频急迫）
│       ├── wechat-extraction.md  # 定向关键信息提取（haiku，按项目/专业/群）
│       └── wechat-summary.md     # 定向摘要生成（haiku，>50条消息）
├── backend/                 # Python 后端包
│   ├── app.py              # Flask 主应用 + 自动同步线程
│   ├── config.py           # 路径与端口配置
│   ├── database.py         # SQLite schema + FTS5 + CRUD
│   ├── sync_engine.py      # wx-cli 调用、类别推断、消息入库
│   ├── contact_extractor.py # 正则提取邮箱与手机号
│   ├── extraction_writer.py # AI 提取结果写入数据库
│   └── import_legacy.py    # 旧版 Excel/JSON 台账导入
├── static/
│   ├── app.js              # 前端 SPA 逻辑(含自动刷新)
│   ├── style.css           # 样式(CSS 变量设计系统)
│   └── favicon.svg         # SVG 图标
├── templates/
│   └── dashboard.html      # 主页面模板
├── data/                    # SQLite 数据库(自动创建)
├── .originfiles/            # 临时/原始文件(不上传仓库)
├── requirements.txt
├── start_ledger.bat
└── .gitignore
```

### 分层

| 层       | 文件                                                                  | 职责                                                                  |
| -------- | --------------------------------------------------------------------- | --------------------------------------------------------------------- |
| 数据采集 | `backend/sync_engine.py`                                            | 通过 subprocess 调用 `wx` CLI,解析 JSON 输出,类别推断,去重入库      |
| 数据层   | `backend/database.py`                                               | SQLite schema (groups/messages/contacts/sync_log), FTS5 全文搜索,CRUD |
| Web API  | `backend/app.py`                                                    | 15 个 REST 端点,Flask 开发服务器,后台自动同步线程                     |
| 前端     | `templates/dashboard.html`, `static/app.js`, `static/style.css` | 原生 JS SPA,无框架,前端缓存 + 自动刷新                                |

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

分类体系**随项目而定**，不是固定不变的。当前项目（工程建设项目）合作单位多，从项目管理角度按总承包和各分包分为两大类:

- **内部（总承包）**: 内部沟通、施工局合作、设计院合作
- **外部（各分包）**: 供应商询价、地基处理、建筑MEP、保险、物流、其他

类别推断规则见 `sync_engine.py` 中的 `infer_category()`,子类别推断见 `_infer_subcategory()`。新项目启动时需根据项目特点调整分类关键词和体系。

### 前端交互要点

- 项目选择器:标题下拉切换项目,自动发现 `/api/projects`
- 左侧分类标签页:内部(上部)含 内部沟通/施工局合作/设计院合作,外部(下部)含 供应商咨询/地基处理/建筑MEP/保险/其他
- 群组行颜色:绿色(≤3天)、琥珀色(3-7天)、红色(>7天)
- 点击行打开右侧抽屉:分页显示消息(50条/页)、自动提取的联系人信息。图片消息支持点击解密打开，文件消息点击跳转资源管理器
- 搜索面板:全库 FTS5 搜索,sender/content 范围
- 自动刷新:工具栏时钟按钮,可选 30s/1m/2m/5m 间隔,后台静默同步,有新消息自动更新表格

### API 端点一览

| 方法 | 路径                                 | 说明                                 |
| ---- | ------------------------------------ | ------------------------------------ |
| GET  | `/api/groups`                      | 群组列表(支持 category/project 筛选) |
| GET  | `/api/groups/<id>`                 | 群组详情                             |
| GET  | `/api/groups/<id>/messages`        | 分页消息(limit/offset)               |
| GET  | `/api/groups/<id>/messages/latest` | 最近 N 条消息                        |
| GET  | `/api/groups/<id>/contacts`        | 群组联系人                           |
| POST | `/api/groups/<id>/subcategory`     | 设置子类别                           |
| GET  | `/api/categories`                  | 分类列表                             |
| GET  | `/api/search`                      | FTS5 全文搜索                        |
| GET  | `/api/projects`                    | 项目列表                             |
| GET  | `/api/sync/status`                 | 同步统计                             |
| POST | `/api/sync/refresh`                | 增量同步                             |
| POST | `/api/sync/pull-all`               | 全量拉取(可指定群)                   |
| POST | `/api/sync/discover`               | 发现新群组                           |
| POST | `/api/sync/auto/start`             | 启动自动同步(参数 interval 秒)       |
| POST | `/api/sync/auto/stop`              | 停止自动同步                         |
| GET  | `/api/sync/auto/status`            | 自动同步状态                         |

### 关键路径/常量

- 数据库: `data/ledger_v2.db` (由 `init_db()` 自动创建)
- 临时文件: `.originfiles/` (已加入 .gitignore)
- AI 产出归档: `.originfiles/AIWork/` (摘要、提取结果 Markdown 备份)

## 微信安全注意事项

为防止被微信检测为外挂导致封号，所有与微信数据库的交互必须遵循：

### wx-cli 调用规范

- **唯一调用者**: 只有 `sync_engine.py` 可以调用 wx-cli，用于消息同步
- **频率控制**: 两次 wx-cli 调用之间至少间隔 1.5 秒（`WX_MIN_INTERVAL`）
- **群间延迟**: 同步不同群之间随机延迟 3-8 秒（`SYNC_DELAY_MIN/MAX`）
- **批量限制**: 单次拉取最多 200 条消息（`SYNC_BATCH_LIMIT`），全量同步最多 500 条
- **禁止并行**: 任何时候不得并行调用 wx-cli

### AI 处理规范

- **绝对禁止**: AI 技能/Agent 在任何情况下调用 wx-cli
- **数据来源**: 所有 AI 读取的消息必须来自 SQLite（`data/ledger_v2.db`）
- **处理方式**: 群组间顺序处理，不使用并行子 Agent
- **先用后问**: 先检查 SQLite 是否有足够数据，如有则直接使用；如数据不足，先通过正常同步流程补充

### 环境变量

可通过环境变量调整限速参数（生产环境建议保持默认值）:

- `WX_SYNC_DELAY_MIN=3.0` 最小群间延迟(秒)
- `WX_SYNC_DELAY_MAX=8.0` 最大群间延迟(秒)
- `WX_SYNC_BATCH_LIMIT=200` 单次拉取消息数上限
- `WX_MIN_INTERVAL=1.5` wx-cli 最小调用间隔(秒)

## AI 辅助操作

Claude Code 对本项目的 AI 介入定位:**信息筛选与整理**，让微信群工作信息更清晰展示。不涉及比价、问答、语义搜索、风险预警。所有 AI 处理均在 Claude Code 会话中完成，不接入外部 API。

**重要**: 所有 AI 操作的消息数据来源必须是 SQLite 数据库，绝对禁止直接调用 wx-cli。

### 模型选择

**提取、分类、摘要这三类 AI 操作只使用快速模型（haiku）。** 这些工作本质是模式识别 + 信息整理，不需要强推理能力。快速模型速度快、成本低，完全胜任。仅极少数边界判断（如无法确定分类）才临时用高级模型看一眼。

### 三个独立技能

AI 操作按频率和紧急度拆分为三个独立技能:

| 技能                  | 频率     | 紧急度       | 用途                               |
| --------------------- | -------- | ------------ | ---------------------------------- |
| `wechat-classify`   | 每天     | **高** | 新群快速分类，尽快上仪表盘         |
| `wechat-extraction` | 几天一次 | 中           | 定向提取关键信息（按项目/专业/群） |
| `wechat-summary`    | 偶尔     | 低           | 定向生成摘要（按项目/群）          |

**绝不进行无范围的"全面提取"。** 用户调用时必须指定范围（项目/专业/群），或由 AI 自动判断当前最需要的范围。

### 群组智能分类 (wechat-classify)

最高频最急迫的技能。新加的工作群必须尽快分类才能显示在仪表盘上。

技能文件: `.claude/skills/wechat-classify.md`

1. 调用 `get_groups_for_classification()` 获取待分类群 + 最近 5 条样本消息
2. 根据群名和样本消息判断 category、sub_category、project
3. 通过 `POST /api/groups/<id>/settings` 写入
4. 不确定的留在"其他"，不强行分类
5. 群间顺序处理，使用 haiku 快速模型

### 群聊摘要生成 (wechat-summary)

消息数 > 50 条才做摘要。按项目或单个群定向生成。

技能文件: `.claude/skills/wechat-summary.md`

1. 按指定范围筛选群（project/group_id）
2. 调用 `get_messages_for_ai_processing()` 从 SQLite 读取消息
3. 生成结构化摘要，写入 `ai_summaries` 表
4. 使用 haiku 快速模型

### 关键信息提取 (wechat-extraction)

按项目、专业或单个群定向提取。支持全量和增量两种模式。

技能文件: `.claude/skills/wechat-extraction.md`

全量提取（新群首次）5 维度: 联系人、工期节点、技术参数、文件引用、专业/供货类别
增量提取（已提取过的群）4 维度: 不含专业/供货类别

写入 `ai_extractions` 表。全量用 `write_extractions`（先删后插），增量用 `append_extractions`（追加）。使用 haiku 快速模型。

### 前端 AI 功能

群消息详情抽屉右侧两个标签页:

- **群摘要**: AI 摘要列表，按时间倒序
- **关键信息**: 结构化信息分类展示（联系人、技术参数、工期、文件引用、专业/供货类别）。文件引用支持点击跳转。联系人显示格式为"微信名（真实称呼）"

后端 API: `GET /api/groups/<id>/summaries`, `GET /api/groups/<id>/extractions`
