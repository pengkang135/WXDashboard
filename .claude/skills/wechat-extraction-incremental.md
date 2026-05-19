---
name: wechat-extraction-incremental
description: 微信工作群关键信息增量提取——仅处理有新消息的群，只从SQLite读新消息，追加写入。用于日常高频使用。不调用wx-cli。
---

# 微信工作群关键信息提取（增量）

从 SQLite 中**上次提取之后的新消息**里提取结构化信息，追加写入 `ai_extractions` 表。

**核心原则：提取与同步分离。** 本技能只读 SQLite，不调用 wx-cli。新消息通过正常的同步流程（自动同步/手动 sync_incremental）进入数据库，本技能只负责从库中提取。

**安全约束**: 绝对禁止调用 wx-cli。所有消息从 SQLite 读取。

## 触发词

用户说以下任意短语时触发本技能（而非全量提取）：

- "更新提取" / "增量提取" / "更新一下提取"
- "更新关键信息" / "更新一下关键信息"
- "有新消息了更新一下"

如果用户明确说"全量提取"、"全部重新提取"、"从头提取"，则使用 `wechat-extraction` 全量技能。

## 提取范围

只处理两类群：

1. **有新增消息的群** — `last_active_date > last_extraction_time`，只读 `date_from=last_extraction_time` 之后的消息
2. **从未提取过的群** — `last_extraction_time IS NULL`，读全部消息（含专业/供货类别维度）

## 提取维度

**日常有消息的群（4 个维度）：**

| 维度 | 提取内容 | 严格条件 |
|------|---------|---------|
| 联系人 | 姓名、微信名、真实称呼、角色、公司、邮箱 | 姓名+公司+角色 缺一不可。本人（匹配 `MY_WECHAT_NAME`）仍提取但邮箱留空 |
| 工期节点 | 里程碑事件、日期、责任方 | 必须有明确日期或时间范围 |
| 技术参数 | 参数名、具体数值/规格 | 必须包含具体数值 |
| 文件引用 | 文件名、msg_date、用途说明 | 必须有文件名和发送日期 |

**新群首次提取（额外加第 5 维）：**

| 维度 | 提取内容 |
|------|---------|
| 专业/供货类别 | 类别、专业、说明 — 根据群名和消息推断该群的专业领域 |

日常增量**不碰**专业/供货类别，避免和全量提取的已有记录重复。

## 前置条件

- 消息已通过正常同步流程写入 SQLite（自动同步每 N 秒运行，或手动 `sync_incremental`）
- 全量提取至少执行过一次（确保大多数群已有专业/供货类别）

## 输入

无。自动发现需要处理的群。

## 输出

- `ai_extractions` 表追加的新记录
- 统计：处理群数、新增/跳过/各类型分布

## 标准步骤

### Step 0 — 检查是否有待处理群

```python
from backend.database import get_groups_for_incremental_extraction

targets = get_groups_for_incremental_extraction()
```

如果 `targets` 为空：
→ 报告"所有群提取状态已是最新，无需更新。"
→ 如果用户最近同步过但没有新消息，提示"最近一次同步也未发现新消息。"
→ 结束。

### Step 1 — 顺序逐群处理

**禁止并行。一次只处理一个群。**

```python
from backend.database import get_messages_for_ai_processing

for g in targets:
    if g["last_extraction_time"] is None:
        msgs = get_messages_for_ai_processing(g["id"], max_messages=200)
        include_category = True
    else:
        msgs = get_messages_for_ai_processing(
            g["id"], date_from=g["last_extraction_time"], max_messages=200
        )
        include_category = False

    if not msgs:
        continue  # 无新文本消息可提取（系统消息被过滤）

    # 提取维度信息（见上方维度表）
    # 稍作停顿(0.5-1s)再处理下一群
```

### Step 2 — 提取信息

对每条新消息按维度识别。输出格式与全量相同：

```
Group <id>:
('联系人', '{"姓名":"微信名（真实称呼）", "微信名":"...", "真实称呼":"...", "角色":"...", "公司":"...", "邮箱":"..."}')
('工期节点', '{"节点":"...", "日期":"...", "责任方":"..."}')
('技术参数', '{"参数":"...", "值":"..."}')
('文件引用', '{"文件":"...", "msg_date":"...", "说明":"..."}')
```

`include_category=True` 时追加：

```
('专业/供货类别', '{"类别":"...", "专业":"...", "说明":"..."}')
```

### Step 3 — 追加写入

```python
from backend.extraction_writer import append_extractions

result = append_extractions(group_data)
# {total, inserted, skipped, groups_count, by_type}
```

**必须使用 `append_extractions`，绝不用 `write_extractions`。** 后者会删除该群所有已有提取，只留下这次新增的几条。

### Step 4 — 更新提取时间

```python
from backend.database import update_extraction_time

for g in targets:
    update_extraction_time(g["id"])
```

### Step 5 — 汇总

输出: 处理群数、新增条数、跳过（重复）条数、各类型分布。

## 检查点

- 所有 `targets` 中的群都已处理
- `append_extractions` 的 `skipped` 合理（不应异常大）
- 非新群没有产生「专业/供货类别」条目
- 处理过程中无 wx-cli 进程产生

## 常见情况

| 情况 | 处理 |
|------|------|
| targets 为空 | 正常，无需提取。如果用户刚说"有新消息"，建议先同步 |
| 某群增量消息为 0 | 正常（系统消息被过滤），仍更新 last_extraction_time |
| append_extractions 全部 skipped | 新消息中没有可提取的结构化信息，正常 |
| 新群消息 > 200 条 | 分段读取 |
| JSON 中文编码 | `json.dumps(..., ensure_ascii=False)` |
