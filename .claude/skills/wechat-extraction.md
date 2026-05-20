---
name: wechat-extraction
description: 定向提取微信工作群关键信息（联系人、工期节点、技术参数、文件引用）——按项目/专业/群指定范围，支持全量和增量。使用haiku快速模型。
model: haiku
---

# 微信工作群关键信息提取（定向）

从 SQLite 消息中提取结构化信息，写入 `ai_extractions` 表。按项目、专业或单个群定向提取，不做无范围的全量提取。

**模型**: 使用 haiku（快速模型）。提取本质是模式识别，不需要强推理。

**安全约束**: 绝对禁止调用 wx-cli。

## 触发词

- "提取XX项目的关键信息" / "提取一下XX项目"
- "提取群XX" / "提取XX专业"
- "更新提取" / "增量提取"（自动找有新消息的群）
- 用户说"全量提取XX" → 对该范围全量（先删后插）
- 用户说"更新提取"不指定范围 → 增量模式

## 两种模式

| 模式 | 触发 | 写入方式 | 维度 |
|------|------|---------|------|
| 全量 | 新群首次 / 用户明确说"全量" | `write_extractions`（先删后插） | 5维（含专业/供货类别） |
| 增量 | 日常更新 / "更新提取" | `append_extractions`（追加） | 4维（不含专业/供货类别） |

## 提取维度

**全量模式（5维）:**

| 维度 | 内容 | 严格条件 |
|------|------|---------|
| 联系人 | 姓名、微信名、真实称呼、角色、公司、邮箱 | 姓名+公司+角色 缺一不可 |
| 工期节点 | 里程碑事件、日期、责任方 | 必须有明确日期 |
| 技术参数 | 参数名、具体数值/规格 | 必须包含具体数值 |
| 文件引用 | 文件名、msg_date、用途说明 | 必须有文件名和发送日期 |
| 专业/供货类别 | 类别、专业、说明 | 每个群至少一条 |

**增量模式（4维）:** 不含专业/供货类别。

## 步骤

### Step 0 — 确定范围和模式

用户指定范围时直接使用。未指定时:

- "更新提取" → 调用 `get_groups_for_incremental_extraction()` 找有待处理消息的群
- 如果该函数返回空 → "所有群提取状态已是最新，无需更新。"
- 如果用户是新项目首次提取 → 全量模式

### Step 1 — 读取消息

```python
from backend.database import get_messages_for_ai_processing

for g in target_groups:
    if mode == 'incremental' and g["last_extraction_time"]:
        msgs = get_messages_for_ai_processing(g["id"], date_from=g["last_extraction_time"], max_messages=200)
    else:
        msgs = get_messages_for_ai_processing(g["id"], max_messages=200)
    
    if not msgs:
        continue
```

### Step 2 — 提取信息

对每条消息按维度识别，输出格式:

```
Group <id>:
('联系人', '{"姓名":"微信名（真实称呼）", "微信名":"...", "真实称呼":"...", "角色":"...", "公司":"...", "邮箱":"..."}')
('工期节点', '{"节点名称":"...", "日期":"...", "状态":"...", "备注":"..."}')
('技术参数', '{"参数名称":"...", "参数值":"...", "备注":"..."}')
('文件引用', '{"文件说明":"...", "链接":"", "来源":"..."}')
```

全量模式追加:
```
('专业/供货类别', '{"类别":"...", "专业":"...", "说明":"..."}')
```

### Step 3 — 写入

```python
from backend.extraction_writer import write_extractions, append_extractions

if mode == 'full':
    result = write_extractions(group_data)
else:
    result = append_extractions(group_data)
```

### Step 4 — 更新时间

```python
from backend.database import update_extraction_time

for g in target_groups:
    update_extraction_time(g["id"])
```

### Step 5 — 汇总

处理群数、新增/跳过、各类型分布。

## 检查点

- 增量模式没有产生「专业/供货类别」条目
- `append_extractions` 的 skipped 合理
- JSON 使用 `json.dumps(..., ensure_ascii=False)`
- 未调用 wx-cli