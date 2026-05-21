# Quotation Document Downloader — Design Spec

## 目标

从微信群聊中下载报价文档（PDF/XLSX），按 `专业分类_English / 单位名称_English` 目录结构
组织到 `F:\WXDashboard\.Download\`。

## 数据筛选规则

### 来源范围
- **时间**: 最近 7 天（msg_date >= 当前日期 - 7 天）
- **群组**: category 属于外部供应商/分包类别
  - `供应商询价`
  - `地基处理`
  - `建筑MEP`
  - `保险`
  - `物流`
  - `其他`（需人工判断是否供应商群）
  - 排除: `内部沟通`、`施工局合作`、`设计院合作`
- **文件类型**: 仅 `.pdf` 和 `.xlsx`（大小写不敏感）
- **消息来源**: 排除我们自己人（CHEC 成本团队、项目管理人员）

### 内部人员排除名单
从 Costing Team 群和内部沟通群的常见发送者汇总（可配置）：
- 彭康、vanz mee QS manager、MR.F、Pepsi、Mr. Sing、TanChao、K.Kwan
- 具体名单在脚本中维护 `INTERNAL_SENDERS` 集合

## 单位名称提取

从群名中提取供应商/分包单位名称：
- 模式 1: `CHEC&XXX` → `XXX`
- 模式 2: `项目-港湾-XXX` → `XXX`
- 模式 3: `XXX（中文名）` → 取主要名称

提取后清理：去空格、去特殊字符。

## 价格内容验证

### XLSX 文件
用 openpyxl 读取前 50 行，检测：
- 表头含价格关键词: `price`, `rate`, `amount`, `unit price`, `total`, `单价`, `总价`, `金额`, `报价`, `合计`
- 数值列有货币格式或大量数字金额

### PDF 文件
用 pdfplumber 提取文本（前 3 页），检测：
- 价格模式: 数字 + 货币符号/单位
- 价格关键词: `price`, `rate`, `amount`, `quotation`, `报价`

### 判定
- 含价格信息 → 保留为报价文件
- 不含价格但含公司名/产品名 → 可能为公司介绍，保留（用户允许）
- 不含以上 → 可能是我们发出的询价单，跳过

## 目录结构

```
F:\WXDashboard\.Download\
├── 钢管桩_SteelPipePile/
│   ├── 裕大管桩_YuDaPile/
│   │   ├── CEPCO-piles-Brochure.pdf
│   │   └── quotation_20260520.xlsx
│   └── Oriental/
│       └── Schedule_of_Prices_20260520.xlsx
├── 地基处理_GroundImprovement/
│   └── GeoHarbour/
│       └── Schedule_of_Prices_5.20.xlsx
├── 管道_Pipe/
│   ├── LESSO_联塑/
│   └── 中财管道_Zhongcai/
└── ...
```

### 命名规则
- 子目录: `{sub_category}_{English}` — 英文翻译硬编码映射表
- 单位目录: 从群名提取的中文名或英文名，如同时存在则 `中文_English`
- 文件名: 保持原文件名不变

### Sub_category 中英对照表（当前项目）
| 中文 | English |
|------|---------|
| 钢管桩 | SteelPipePile |
| 管桩 | PipePile |
| 地基处理 | GroundImprovement |
| 桩基/地基 | PileFoundation |
| 建筑总承包 | BuildingContractor |
| 管道 | Pipe |
| 疏浚 | Dredging |
| 保险服务 | Insurance |
| 物流 | Logistics |
| 供油/润滑 | OilLubricant |
| 钢结构 | SteelStructure |
| 橡胶护舷 | RubberFender |
| 光伏设备 | SolarEquipment |
| 漂浮安装 | FloatingInstallation |
| 其他 | Others |

## 实现

单个 Python 脚本 `backend/download_quotations.py`：

1. `collect_file_messages(days=7)` — SQLite 查询获取候选文件消息列表
2. `extract_company_from_group(group_name)` — 从群名提取单位名
3. `is_price_document(file_path, extension)` — 价格内容验证
4. `build_dest_path(sub_category, company, filename)` — 构造目标路径（含双语）
5. `download_quotations()` — 主流程，输出统计报告

### 依赖
- openpyxl（xlsx 读取）
- pdfplumber（PDF 文本提取）

新增依赖加入 requirements.txt。

### 执行方式
```bash
python -m backend.download_quotations
```

输出：
- 每个文件的处理状态（已下载/跳过/原因）
- 最终统计：共扫描 X 个文件，下载 Y 个报价文件，跳过 Z 个

## 安全注意事项
- 脚本不调用 wx-cli，仅从 SQLite 读取消息元数据
- 文件复制使用 shutil.copy2（保留时间戳），不修改原文件
- 目标目录自动创建
- 同名文件覆盖（以最新为准）
