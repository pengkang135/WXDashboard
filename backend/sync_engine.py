import json
import subprocess
import shutil
from datetime import datetime
from .database import (
    get_db, upsert_message, upsert_group, update_group_stats, add_sync_log,
    get_all_group_names, get_message_count
)


WX_CLI = shutil.which("wx") or "wx"

CATEGORY_RULES = [
    (["ground improvement", "地基处理", "地基", "gi "], "地基处理"),
    (["mep"], "建筑MEP"),
    (["保险"], "保险"),
    (["物流"], "内部沟通"),
    (["成本", "costing"], "内部沟通"),
    (["沟通群", "总包沟通"], "内部沟通"),
    (["四航院", "水规院", "水运院"], "设计院合作"),
    (["一航局", "二航局", "三航局", "四航局"], "施工局合作"),
]

SUBCATEGORY_RULES = [
    (["护舷", "天盾", "泰鸿", "特瑞堡", "fender", "橡胶"], "护舷"),
    (["管桩", "建华", "裕大", "pipe"], "管桩"),
    (["管道", "中财", "狼博", "日丰", "伟星", "lesso"], "管道"),
    (["桩基", "中岩", "岩土", "地基"], "桩基/地基"),
    (["钢结构", "钢构", "oriental castle", "中冶"], "钢结构"),
    (["电气", "中科芯源", "芯源", "配电"], "电气"),
    (["石料", "欧博", "军西", "土工", "疏浚", "吹填"], "石料/土工"),
    (["钢轨", "ganrail", "轨道", "道岔"], "钢轨"),
    (["mep", "机电"], "机电总包"),
    (["浪潮", "辛玮", "inspur", "弱电", "智能"], "弱电"),
    (["利锋", "消防", "lifeng"], "消防"),
    (["山西安装", "sig", "安装"], "机电安装"),
    (["江苏", "jsi", "省安"], "机电安装"),
    (["citcc", "通信"], "通信"),
    (["中交特种", "cccc", "特种"], "地基处理"),
    (["geoharbour", "geo harbour"], "地基处理"),
    (["江苏", "地基"], "地基处理"),
    (["保险经纪", "保险", "中怡", "aon", "怡"], "保险经纪"),
    (["物流", "捷环", "logistic", "货运", "运输", "报关"], "物流"),
    (["成本", "costing", "测算"], "成本测算"),
    (["设计", "四航院", "水规院", "水运院", "consult"], "设计咨询"),
    (["四航局", "一航局", "二航局", "三航局", "施工", "contractor"], "施工"),
]


def _infer_category(name):
    lower = name.lower()
    for keywords, cat in CATEGORY_RULES:
        if any(kw in lower for kw in keywords):
            return cat
    return "供应商咨询"


def _infer_subcategory(name, category=None):
    lower = name.lower()
    for keywords, sub in SUBCATEGORY_RULES:
        if any(kw in lower for kw in keywords):
            return sub
    return ""


def _run_wx(args, timeout=120):
    import tempfile, os as _os
    if WX_CLI == "wx" and not shutil.which("wx"):
        raise RuntimeError("wx-cli 未安装")

    def _quote(a):
        return f'"{a}"' if any(c in a for c in ' &|<>^') else a

    cmd_str = " ".join(_quote(a) for a in [WX_CLI] + args)
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
    tmp.close()
    try:
        result = subprocess.run(
            cmd_str,
            stdout=open(tmp.name, "w", encoding="utf-8"),
            stderr=subprocess.PIPE, text=False, timeout=timeout
        )
        with open(tmp.name, "r", encoding="utf-8") as f:
            stdout = f.read()
    except FileNotFoundError:
        _os.unlink(tmp.name)
        raise RuntimeError("wx-cli 未安装")
    except subprocess.TimeoutExpired:
        _os.unlink(tmp.name)
        raise RuntimeError(f"wx-cli 执行超时 ({timeout}s)")
    finally:
        try:
            _os.unlink(tmp.name)
        except OSError:
            pass
    if result.returncode != 0:
        stderr = (result.stderr or b"").decode("utf-8", errors="replace").strip()
        if "not found" in stderr.lower() or "not recognized" in stderr.lower():
            raise RuntimeError("wx-cli 未安装")
        if "init" in stderr.lower():
            raise RuntimeError("wx-cli 未初始化，请运行: wx init")
        raise RuntimeError(f"wx-cli 错误: {stderr or '未知错误'}")
    return (stdout or "").strip()


def discover_new_groups(project="Laldia"):
    output = _run_wx(["sessions", "-n", "200"])
    group_names = set(get_all_group_names())
    new_groups = []
    conn = get_db()

    project_keywords = ["laldia", "港湾"]
    if project != "Laldia":
        project_keywords = [project.lower()]

    for line in output.split("\n"):
        line = line.strip()
        if not line.startswith("- chat:"):
            continue
        name = line[7:].strip()
        if name in group_names:
            continue
        if not any(kw in name.lower() for kw in project_keywords):
            continue
        if any(skip in name.lower() for skip in ["通威", "364mw"]):
            continue

        category = _infer_category(name)
        sub_category = _infer_subcategory(name, category)
        upsert_group(name, category, sub_category=sub_category, project=project)
        group_names.add(name)
        new_groups.append((name, category, sub_category))

    conn.close()
    return new_groups


def sync_incremental():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    output = _run_wx(["new-messages", "--json"])
    messages = json.loads(output) if output else []

    group_names = set(get_all_group_names())
    stats = {"groups_updated": 0, "messages_new": 0, "errors": [],
             "new_groups_discovered": [], "contacts_extracted": 0}

    conn = get_db()
    for msg in messages:
        chat_type = msg.get("chat_type", "")
        if chat_type not in ("group",):
            continue

        group_name = msg.get("chat_name", "") or msg.get("name", "")
        if not group_name:
            continue

        if group_name not in group_names:
            if "laldia" in group_name.lower() or "港湾" in group_name:
                cat = _infer_category(group_name)
                sub = _infer_subcategory(group_name, cat)
                gid = upsert_group(group_name, cat, sub_category=sub, project="Laldia")
                group_names.add(group_name)
                stats["new_groups_discovered"].append({"name": group_name, "category": cat})
            else:
                stats["errors"].append(f"未知群组: {group_name}")
                continue

        group = conn.execute("SELECT id FROM groups WHERE name=?", (group_name,)).fetchone()
        if not group:
            stats["errors"].append(f"群组不在数据库: {group_name}")
            continue
        group_id = group["id"]

        inserted = _upsert_from_wx_msg(conn, group_id, msg)
        if inserted:
            stats["messages_new"] += 1

    conn.close()

    conn2 = get_db()
    for gname in group_names:
        group = conn2.execute("SELECT id FROM groups WHERE name=?", (gname,)).fetchone()
        if not group:
            continue
        gid = group["id"]
        count = conn2.execute("SELECT COUNT(*) as cnt FROM messages WHERE group_id=?", (gid,)).fetchone()["cnt"]
        last = conn2.execute(
            "SELECT msg_date FROM messages WHERE group_id=? ORDER BY msg_time DESC LIMIT 1",
            (gid,)
        ).fetchone()
        update_group_stats(gid, last_active_date=last["msg_date"] if last else None, total_messages=count, conn=conn2)
    conn2.close()

    add_sync_log("全部群组(增量)", None, len(messages), stats["messages_new"],
                  "ok" if not stats["errors"] else f"部分错误: {len(stats['errors'])}个群")

    stats["groups_updated"] = len(group_names)
    return stats


def sync_full(group_name, limit=2000):
    output = _run_wx(["history", group_name, "--json", "-n", str(limit)], timeout=300)
    messages = json.loads(output) if output else []

    conn = get_db()
    group = conn.execute("SELECT id FROM groups WHERE name=?", (group_name,)).fetchone()
    if not group:
        group_id = upsert_group(group_name, _infer_category(group_name), project="Laldia")
    else:
        group_id = group["id"]

    new_count = 0
    for msg in messages:
        if _upsert_from_wx_msg(conn, group_id, msg):
            new_count += 1

    count = conn.execute("SELECT COUNT(*) as cnt FROM messages WHERE group_id=?", (group_id,)).fetchone()["cnt"]
    last_date = None
    if messages:
        last_date = messages[-1].get("time", "")[:10]
    update_group_stats(group_id, last_active_date=last_date, total_messages=count, conn=conn)
    conn.close()

    add_sync_log(group_name, None, len(messages), new_count, "ok")
    return {"group": group_name, "pulled": len(messages), "new": new_count, "total": count}


def sync_all_groups_full(limit=2000):
    results = []
    errors = []
    for gname in get_all_group_names():
        try:
            r = sync_full(gname, limit)
            results.append(r)
        except Exception as e:
            errors.append({"group": gname, "error": str(e)})
    return {"results": results, "errors": errors}


def _upsert_from_wx_msg(conn, group_id, msg):
    local_id = msg.get("local_id")
    sender = msg.get("sender", "未知")
    content = msg.get("content", "")
    msg_time = msg.get("time", "")
    msg_date = msg_time[:10] if msg_time else ""
    msg_type = msg.get("type", "text")
    raw_json = json.dumps(msg, ensure_ascii=False)

    existing = conn.execute(
        "SELECT id FROM messages WHERE group_id=? AND local_id=?",
        (group_id, local_id)
    ).fetchone()

    if existing:
        return False

    cur = conn.execute("""
        INSERT INTO messages (group_id, local_id, sender, content, msg_time,
                              msg_date, msg_type, raw_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (group_id, local_id, sender, content, msg_time, msg_date, msg_type, raw_json))

    from .contact_extractor import extract_and_save
    extract_and_save(conn, group_id, cur.lastrowid, sender, content)
    return True


def get_sync_stats():
    conn = get_db()
    group_count = conn.execute("SELECT COUNT(*) as cnt FROM groups WHERE deleted=0").fetchone()["cnt"]
    msg_count = conn.execute("SELECT COUNT(*) as cnt FROM messages").fetchone()["cnt"]
    last_sync = conn.execute(
        "SELECT * FROM sync_log ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return {
        "group_count": group_count,
        "message_count": msg_count,
        "last_sync": dict(last_sync) if last_sync else None
    }
