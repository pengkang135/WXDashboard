---
name: wechat-classify
description: 新群快速分类——根据群名和最近消息判断项目归属、类别、子类别。高频急迫，使用haiku快速模型。
model: haiku
---

# 新群快速分类

对未分类的微信工作群进行快速分类，使其尽快显示在仪表盘上。只读 SQLite，不调用 wx-cli。

**模型**: 使用 haiku（快速模型）。分类本质是模式识别，不需要强推理。

## 触发词

- "新群分类" / "分下类" / "把新加的群分一下"
- "看看有哪些没分类的群"
- "分类一下新群"

## 范围

只处理 `category IS NULL OR category = '' OR category = '其他'` 的群。

## 步骤

### Step 1 — 获取待分类群

```python
from backend.database import get_groups_for_classification
groups = get_groups_for_classification()
```

如果为空 → "所有群已分类，无需处理。"

### Step 2 — 顺序逐群分类

一次一个群，不并行。

对每个群，根据群名 + 5 条样本消息判断:

1. **project**: 属于哪个项目。常见项目: 孟加拉Laldia、泰国光伏、其他/待定
2. **category**: 内部（总承包）还是 外部（各分包）
3. **sub_category**: 
   - 内部: 内部沟通、施工局合作、设计院合作
   - 外部: 供应商询价、地基处理、建筑MEP、保险、物流、其他

判断依据:
- 群名含"港湾""CHEC"内部人员为主 → 内部
- 群名含供应商/分包商名称 → 外部
- 群名含"设计院""珠江""水规院" → 设计院合作
- 群名含"物流""货运" → 物流
- 群名含"光伏""漂浮""solar" → project=泰国光伏
- 群名含"Laldia""孟加拉""吉大港" → project=孟加拉Laldia

不确定时 project 留空、category 留"其他"，不强行判断。

### Step 3 — 写入

```python
import requests
for g in classified_groups:
    requests.post(
        f'http://127.0.0.1:8888/api/groups/{g["id"]}/settings',
        json={'project': g['project'], 'category': g['category'], 'sub_category': g['sub_category']}
    )
```

### Step 4 — 汇总

报告: 处理群数、各分类/项目分布、留在"其他"的群及原因。

## 检查点

- 只处理了未分类的群
- 未对不确定的群强行分类
- 未调用 wx-cli