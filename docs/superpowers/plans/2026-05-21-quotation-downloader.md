# Quotation Document Downloader — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** 从微信群聊中下载报价文档（PDF/XLSX），按 `专业分类_EN / 单位名称` 目录组织到 `F:\WXDashboard\.Download\`

**Architecture:** 单个 Python 脚本 `backend/download_quotations.py`，查询 SQLite 获取候选文件消息，通过 `get_wx_file_path()` 解析文件路径，openpyxl/pdfplumber 验证价格内容，shutil.copy2 复制到目标目录。

**Tech Stack:** Python 3, sqlite3, openpyxl (read_only), pdfplumber, shutil

---

### Task 1: Install pdfplumber dependency

- [ ] **Step 1: Add pdfplumber to requirements.txt**

Edit `requirements.txt`:

```
flask>=3.0
openpyxl>=3.1
pdfplumber>=0.11
```

- [ ] **Step 2: Install pdfplumber**

```bash
pip install pdfplumber
```

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "add pdfplumber dependency for quotation downloader"
```

---

### Task 2: Create quotation downloader script — data collection

**Files:**
- Create: `backend/download_quotations.py`

- [ ] **Step 1: Write the script with imports, constants, and DB query function**

```python
import sqlite3
import os
import re
import shutil
from datetime import datetime, timedelta

from .config import get_wx_file_path
from .database import DB_PATH

DOWNLOAD_ROOT = r"F:\WXDashboard\.Download"

EXTERNAL_CATEGORIES = {"供应商咨询", "地基处理", "建筑MEP", "保险", "物流"}

SUB_CATEGORY_EN = {
    "钢管桩": "SteelPipePile",
    "管桩": "PipePile",
    "地基处理": "GroundImprovement",
    "桩基/地基": "PileFoundation",
    "建筑总承包": "BuildingContractor",
    "机电总包": "MEPContractor",
    "管道": "Pipe",
    "疏浚": "Dredging",
    "保险经纪": "InsuranceBroker",
    "保险服务": "InsuranceService",
    "物流": "Logistics",
    "石料/土工": "StoneGeotextile",
    "供油/润滑": "OilLubricant",
    "钢材": "Steel",
    "钢轨": "Rail",
    "钢结构": "SteelStructure",
    "橡胶护舷": "RubberFender",
    "护舷": "RubberFender",
    "泵/液压": "PumpHydraulic",
    "光伏设备": "SolarEquipment",
    "漂浮安装": "FloatingInstallation",
    "电气": "Electrical",
    "机电安装": "MEPInstallation",
    "其他": "Others",
}

PRICE_KEYWORDS = [
    "price", "rate", "amount", "unit price", "total", "cost", "quotation",
    "单价", "总价", "金额", "报价", "合计", "价格", "费用", "含税",
    "subtotal", "discount", "net price", "gross price", "FOB", "CIF", "EXW",
]

BROCHURE_KEYWORDS = [
    "brochure", "company profile", "introduction", "catalog",
    "介绍册", "公司简介", "产品目录", "公司介绍",
]


def _get_db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def _get_internal_senders(conn):
    """Dynamically identify our people: anyone who sent messages in internal groups."""
    rows = conn.execute("""
        SELECT DISTINCT m.sender
        FROM messages m
        JOIN groups g ON m.group_id = g.id
        WHERE g.category IN ('内部沟通', '施工局合作', '设计院合作')
    """).fetchall()
    return {r["sender"] for r in rows if r["sender"]}


def collect_file_messages(conn, days=7):
    """Return list of dicts: {id, group_id, sender, content, msg_time, msg_date,
    group_name, category, sub_category, filename, ext}"""
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    internal_senders = _get_internal_senders(conn)

    rows = conn.execute("""
        SELECT m.id, m.group_id, m.sender, m.content, m.msg_time, m.msg_date,
               g.name AS group_name, g.category, g.sub_category
        FROM messages m
        JOIN groups g ON m.group_id = g.id
        WHERE m.msg_date >= ?
          AND m.content LIKE '%[文件]%'
          AND g.category IN ({})
        ORDER BY m.msg_time DESC
    """.format(",".join("?" * len(EXTERNAL_CATEGORIES))),
        [since] + list(EXTERNAL_CATEGORIES)
    ).fetchall()

    results = []
    for row in rows:
        # Extract filename from content: [文件] filename.ext
        m = re.search(r'\[文件\]\s*(.+?)(?:\n|$)', row["content"])
        if not m:
            continue
        filename = m.group(1).strip()
        ext_match = re.search(r'\.(pdf|xlsx)$', filename, re.IGNORECASE)
        if not ext_match:
            continue

        # Skip files from our own people
        if row["sender"] in internal_senders:
            continue

        results.append({
            "id": row["id"],
            "group_id": row["group_id"],
            "sender": row["sender"],
            "content": row["content"],
            "msg_time": row["msg_time"],
            "msg_date": row["msg_date"],
            "group_name": row["group_name"],
            "category": row["category"],
            "sub_category": row["sub_category"],
            "filename": filename,
            "ext": ext_match.group(1).lower(),
        })
    return results
```

- [ ] **Step 2: Verify DB query logic with a quick test run**

```bash
python -c "
from backend.download_quotations import collect_file_messages, _get_db
conn = _get_db()
files = collect_file_messages(conn, days=7)
print(f'Found {len(files)} candidate file messages')
for f in files:
    print(f'  [{f[\"msg_time\"]}] [{f[\"group_name\"]}] {f[\"sender\"]} -> {f[\"filename\"]} ({f[\"ext\"]})')
"
```

---

### Task 3: Add company name extraction and price detection

**Files:**
- Modify: `backend/download_quotations.py`

- [ ] **Step 1: Add company name extraction function**

Add after `collect_file_messages`:

```python
def extract_company_from_group(group_name):
    """Extract supplier/company name from group name.
    'Laldia-CHEC&裕大管桩' -> '裕大管桩'
    '孟加拉Laldia项目-港湾-中岩大地' -> '中岩大地'
    'Laldia-MEP-CHEC&Inspur浪潮' -> 'Inspur_浪潮'
    """
    # Pattern 1: CHEC&XXX or CHEC&XXX中文
    m = re.search(r'CHEC&(.+?)$', group_name)
    if m:
        return m.group(1).strip()

    # Pattern 2: 项目-港湾-XXX or 项目-单位-XXX
    parts = group_name.split("-")
    if len(parts) >= 3:
        return parts[-1].strip()

    return group_name


def build_dir_name(sub_category, company):
    """Build bilingual directory name.
    sub_category='钢管桩', company='裕大管桩' -> '钢管桩_SteelPipePile/裕大管桩'
    """
    en = SUB_CATEGORY_EN.get(sub_category, sub_category)
    cat_dir = f"{sub_category}_{en}" if sub_category else f"未分类_Unclassified"
    company_dir = company.replace("/", "_").replace("\\", "_").strip()
    return os.path.join(cat_dir, company_dir)
```

- [ ] **Step 2: Add XLSX price detection**

```python
def _xlsx_has_price(file_path):
    """Check if xlsx file contains price information."""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            row_count = 0
            for row in ws.iter_rows(max_row=50, values_only=True):
                row_count += 1
                row_text = " ".join(str(c) for c in row if c is not None)
                row_lower = row_text.lower()
                # Check for price keywords
                if any(kw in row_lower for kw in PRICE_KEYWORDS):
                    wb.close()
                    return True
                # Check for numeric patterns: columns with many numbers
        wb.close()
    except Exception:
        pass
    return False


def _pdf_has_price(file_path):
    """Check if PDF file contains price information."""
    try:
        import pdfplumber
        with pdfplumber.open(file_path) as pdf:
            pages_to_check = pdf.pages[:3]
            text = "\n".join(
                page.extract_text() or "" for page in pages_to_check
            )
        text_lower = text.lower()
        if any(kw in text_lower for kw in PRICE_KEYWORDS):
            return True
        # Check for currency/number patterns
        if re.search(r'[\$\€\¥\£]', text):
            return True
    except Exception:
        pass
    return False


def is_price_document(file_path, ext):
    """Check if file is a quotation document."""
    if ext == "xlsx":
        return _xlsx_has_price(file_path)
    elif ext == "pdf":
        return _pdf_has_price(file_path)
    return False


def is_brochure(file_path, ext, filename):
    """Check if file appears to be a company brochure."""
    name_lower = filename.lower()
    if any(kw in name_lower for kw in BROCHURE_KEYWORDS):
        return True
    return False
```

- [ ] **Step 3: Commit**

```bash
git add backend/download_quotations.py
git commit -m "add quotation downloader: data collection, company extraction, price detection"
```

---

### Task 4: Add main download orchestration function

**Files:**
- Modify: `backend/download_quotations.py`

- [ ] **Step 1: Add main download function**

Add at end of file:

```python
def download_quotations(days=7):
    """Main entry point. Scan recent supplier messages, validate, copy files.
    Returns dict with stats: scanned, downloaded, skipped, errors.
    """
    conn = _get_db()
    candidates = collect_file_messages(conn, days=days)
    conn.close()

    stats = {"scanned": len(candidates), "downloaded": 0, "skipped": 0, "errors": []}
    downloaded_files = []

    for item in candidates:
        file_path = get_wx_file_path(item["msg_date"], item["filename"])
        if not file_path:
            stats["skipped"] += 1
            print(f"[SKIP] 文件不存在: {item['filename']}")
            continue

        ext = item["ext"]

        # Determine if price document or brochure
        is_price = is_price_document(file_path, ext)
        is_brochure_doc = is_brochure(file_path, ext, item["filename"])

        if not is_price and not is_brochure_doc:
            stats["skipped"] += 1
            print(f"[SKIP] 非报价文件: {item['filename']} ({item['sender']} @ {item['group_name']})")
            continue

        doc_type = "报价" if is_price else "介绍"
        if is_brochure_doc and not is_price:
            doc_type = "公司介绍"

        # Build destination paths
        company = extract_company_from_group(item["group_name"])
        sub_dir = build_dir_name(item["sub_category"], company)
        dest_dir = os.path.join(DOWNLOAD_ROOT, sub_dir)
        os.makedirs(dest_dir, exist_ok=True)
        dest_path = os.path.join(dest_dir, item["filename"])

        try:
            shutil.copy2(file_path, dest_path)
            stats["downloaded"] += 1
            downloaded_files.append({
                "filename": item["filename"],
                "sender": item["sender"],
                "group": item["group_name"],
                "company": company,
                "sub_category": item["sub_category"],
                "type": doc_type,
                "dest": dest_path,
            })
            print(f"[{doc_type}] {item['filename']}")
            print(f"  {item['sender']} @ {item['group_name']}")
            print(f"  -> {dest_path}")
        except Exception as e:
            stats["errors"].append({"file": item["filename"], "error": str(e)})
            print(f"[ERROR] {item['filename']}: {e}")

    # Print summary
    print(f"\n=== 下载完成 ===")
    print(f"扫描: {stats['scanned']} 个文件")
    print(f"下载: {stats['downloaded']} 个文件")
    print(f"跳过: {stats['skipped']} 个")
    if stats["errors"]:
        print(f"错误: {len(stats['errors'])} 个")
        for e in stats["errors"]:
            print(f"  - {e['file']}: {e['error']}")

    print(f"\n目标目录: {DOWNLOAD_ROOT}")
    _print_tree(DOWNLOAD_ROOT)

    return stats


def _print_tree(root, prefix=""):
    """Print a simple directory tree."""
    if not os.path.isdir(root):
        return
    entries = sorted(os.listdir(root))
    for i, name in enumerate(entries):
        path = os.path.join(root, name)
        is_last = i == len(entries) - 1
        marker = "└── " if is_last else "├── "
        if os.path.isdir(path):
            print(f"{prefix}{marker}{name}/")
            _print_tree(path, prefix + ("    " if is_last else "│   "))
```

- [ ] **Step 2: Commit**

```bash
git add backend/download_quotations.py
git commit -m "add download_quotations main orchestration and reporting"
```

---

### Task 5: Integration test — dry run with actual data

- [ ] **Step 1: Run the downloader**

```bash
python -m backend.download_quotations
```

- [ ] **Step 2: Verify output**

Check that:
- Files are copied to correct bilingual directories
- Non-price files are skipped
- Errors (if any) are reported clearly

- [ ] **Step 3: Fix any issues and final commit**

```bash
git add -A
git commit -m "quotation downloader: fixes from integration test"
```

---

### Task 6: Add `__main__` entry point

**Files:**
- Modify: `backend/download_quotations.py`

- [ ] **Step 1: Add module entry point**

Add at end of file:

```python
if __name__ == "__main__":
    import sys
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    print(f"扫描最近 {days} 天的报价文件...\n")
    download_quotations(days=days)
```

- [ ] **Step 2: Commit**

```bash
git add backend/download_quotations.py
git commit -m "add __main__ entry point for quotation downloader"
```
