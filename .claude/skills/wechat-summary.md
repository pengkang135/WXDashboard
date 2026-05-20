---
name: wechat-summary
description: 定向生成群聊摘要——按项目或单个群，仅对消息>50条的群生成摘要。使用haiku快速模型。
model: haiku
---

# 群聊摘要生成（定向）

按指定范围生成群聊摘要。仅对消息数 > 50 条的群执行。

**模型**: 使用 haiku（快速模型）。

## 触发词

- "总结一下XX项目" / "生成XX项目摘要"
- "看看群XX最近在聊什么"
- "给XX群生成摘要"

## 范围

用户必须指定范围，或 AI 主动询问:
- 按项目: "总结泰国光伏项目"
- 按单个群: "总结群40"
- 不接无范围的全量摘要请求

## 步骤

### Step 1 — 确定目标群

```python
from backend.database import get_db

conn = get_db()
if project:
    groups = conn.execute(
        "SELECT id, name, total_messages FROM groups WHERE deleted=0 AND project=? AND total_messages > 50 ORDER BY total_messages DESC",
        (project,)
    ).fetchall()
elif group_id:
    groups = conn.execute(
        "SELECT id, name, total_messages FROM groups WHERE deleted=0 AND id=?",
        (group_id,)
    ).fetchall()
conn.close()
```

消息数 ≤ 50 的群跳过并说明。

### Step 2 — 顺序逐群生成

```python
from backend.database import get_messages_for_ai_processing

for g in groups:
    msgs = get_messages_for_ai_processing(g["id"], max_messages=200)
    # 生成摘要
    # 稍作停顿再处理下一群
```

### Step 3 — 生成摘要

摘要结构:
- **主题**: 该群近期讨论的核心话题（1-2句话）
- **关键事项**: 3-5个要点
- **时间范围**: 消息覆盖的日期区间

### Step 4 — 写入数据库

```python
from backend.database import get_db
from datetime import datetime

conn = get_db()
conn.execute("""
    INSERT INTO ai_summaries (group_id, date_range, summary_text, key_topics, generated_at)
    VALUES (?, ?, ?, ?, ?)
""", (group_id, date_range, summary_text, key_topics, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
conn.commit()
conn.close()
```

### Step 5 — 汇总

报告: 处理群数、各群摘要概要。

## 检查点

- 消息数 ≤ 50 的群未生成摘要
- 摘要不编造消息中不存在的内容
- 未调用 wx-cli