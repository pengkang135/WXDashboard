---
name: wechat-quotation-download
description: 从微信群聊中下载报价文档（PDF/XLSX），按专业分类/单位名称双语目录组织——仅从SQLite读取，禁止调用wx-cli
model: haiku
---

# 微信报价文档下载器

从外部供应商/分包微信群的 `[文件]` 消息中，识别并下载报价文档（PDF/XLSX），按 `专业分类_English / 单位名称` 双语目录组织到 `F:\WXDashboard\.Download\`。

**安全约束**: 绝对禁止调用 wx-cli。数据只从 SQLite 读取。

## 触发词

- "下载报价文件" / "下载quotation"
- "下载最近X天的报价"
- "更新报价文档"

## 前置条件

1. SQLite 数据库 (`data/ledger_v2.db`) 中已有足够最近的消息数据
2. `pdfplumber` 和 `openpyxl` 已安装（见 `requirements.txt`）
3. 源文件可由 `get_wx_file_path()` 解析到（微信文件存储路径）

**如果 SQLite 数据不足**: 用户需先手动通过前端刷新按钮触发增量同步，或通过 API `POST /api/sync/refresh` 同步。AI **不得**主动发起同步。

## 工作流

### Step 1: 确认数据就绪

```python
from backend.database import get_db, get_message_count
conn = get_db()
# 检查最近7天外部群是否有消息
rows = conn.execute("""
    SELECT COUNT(*) as cnt FROM messages m
    JOIN groups g ON m.group_id = g.id
    WHERE m.msg_date >= date('now', '-7 days')
      AND g.category IN ('供应商咨询', '地基处理', '建筑MEP', '保险', '物流')
""").fetchone()
print(f"最近7天外部群消息数: {rows['cnt']}")
conn.close()
```

如果消息数为 0，告知用户先同步数据。不要自己触发同步。

### Step 2: 执行下载

```bash
python -m backend.download_quotations [天数]
```

天数默认为 7。例如 `python -m backend.download_quotations 30` 扫描最近 30 天。

### Step 3: 解读输出

脚本输出格式:
```
[报价] 文件名
  发送者 @ 群名
  -> 目标路径

=== 下载完成 ===
扫描: X 个文件
下载: Y 个文件
跳过: Z 个
错误: N 个

目标目录: F:\WXDashboard\.Download
├── 专业分类_English/
│   └── 单位名称/
```

- **[报价]**: 检测到价格信息的文件
- **[公司介绍]**: 无价格但匹配公司介绍关键词
- **[SKIP] 文件不存在**: 微信本地文件已被清理或路径解析失败
- **[SKIP] 非报价文件**: 不含价格信息又非公司介绍，可能是我方发出的询价单
- **[ERROR]**: 权限错误或文件被占用（目标文件可能已在其他程序中打开）

## 筛选规则

### 来源范围
| 维度 | 条件 |
|------|------|
| 时间 | `msg_date >= 当前日期 - N 天` |
| 群组 | category 属于外部供应商/分包：供应商咨询、地基处理、建筑MEP、保险、物流 |
| 文件类型 | `.pdf` 和 `.xlsx`（仅） |
| 发送者 | 排除内部人员（从内部沟通/施工局合作/设计院合作群推算） |
| 排除 | 内部沟通群、施工局合作群、设计院合作群 |

### 价格内容验证

**XLSX** (openpyxl, read_only): 扫描前 50 行，匹配价格关键词:
`price`, `rate`, `amount`, `unit price`, `total`, `cost`, `quotation`, `单价`, `总价`, `金额`, `报价`, `合计`, `价格`, `费用`, `含税`, `subtotal`, `discount`, `FOB`, `CIF`, `EXW`

**PDF** (pdfplumber): 提取前 3 页文本，匹配价格关键词和货币符号 `$€¥£`。

### 公司介绍识别

文件名含以下关键词则判定为公司介绍（不检查价格直接保留）:
`brochure`, `company profile`, `introduction`, `catalog`, `介绍册`, `公司简介`, `产品目录`, `公司介绍`

## 目录结构

```
F:\WXDashboard\.Download\
├── 钢管桩_SteelPipePile/
│   └── 裕大管桩/
│       └── quotation_20260520.xlsx
├── 地基处理_GroundImprovement/
│   └── GeoHarbour/
│       └── Schedule_of_Prices.xlsx
├── 管道_Pipe/
│   ├── LESSO/
│   └── 中财管道/
└── ...
```

### 单位名称提取规则

从群名中提取供应商/分包单位名称：

1. `CHEC&XXX` → `XXX` （主模式）
2. `项目-港湾-XXX` → `XXX` （中划线模式）
3. `XXX&YYY` → `YYY` （其他 & 模式）
4. 以上都不匹配 → 使用完整群名

### 中英对照表（硬编码）

| 中文 | English |
|------|---------|
| 钢管桩 | SteelPipePile |
| 管桩 | PipePile |
| 地基处理 | GroundImprovement |
| 桩基/地基 | PileFoundation |
| 建筑总承包 | BuildingContractor |
| 机电总包 | MEPContractor |
| 管道 | Pipe |
| 疏浚 | Dredging |
| 保险经纪 | InsuranceBroker |
| 保险服务 | InsuranceService |
| 物流 | Logistics |
| 石料/土工 | StoneGeotextile |
| 供油/润滑 | OilLubricant |
| 钢材 | Steel |
| 钢轨 | Rail |
| 钢结构 | SteelStructure |
| 橡胶护舷 | RubberFender |
| 护舷 | RubberFender |
| 泵/液压 | PumpHydraulic |
| 光伏设备 | SolarEquipment |
| 漂浮安装 | FloatingInstallation |
| 电气 | Electrical |
| 机电安装 | MEPInstallation |
| 其他 | Others |

## 安全规范

### 绝对禁止
- **任何形式的 wx-cli 调用**（Bash、Python subprocess、MCP shell 等所有渠道）
- 直接访问微信 `MSG.db` 或 `MicroMsg.db`
- 使用 Agent 工具派发子 Agent 执行任何操作
- 调用 `sync_engine.py` 的任何同步函数
- 使用 `decrypt_dat_file` 或相关的微信解密函数

### 唯一允许的数据来源
- `data/ledger_v2.db` — SQLite 数据库（通过 `database.get_db()`）
- `get_wx_file_path()` — 仅用于解析微信文件路径（基于配置的 `_WX_FILE_ROOT`）

### 违反后果
用户已被微信警告并强制下线两次。再犯将面临封号风险。PreToolUse hook (`block-wx-cli.py`) 已部署，任何 Bash 命令含 wx 模式将被硬性阻断。

## 实现文件

- `backend/download_quotations.py` — 核心脚本（~300行），包含所有函数
- `requirements.txt` — `openpyxl>=3.1`, `pdfplumber>=0.11`
- `C:/Users/Kevin/.claude/hooks/block-wx-cli.py` — Bash 命令阻断 hook
