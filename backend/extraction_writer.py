from backend.database import get_db
from datetime import datetime


def write_extractions(group_data):
    """将提取结果写入 ai_extractions 表（先删后插，幂等）。

    Args:
        group_data: dict, {group_id: [(extract_type, content_json_str), ...], ...}

    Returns:
        dict: {total, groups_count, by_type: {extract_type: count}}
    """
    conn = get_db()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    total = 0
    by_type = {}

    for gid, items in group_data.items():
        conn.execute('DELETE FROM ai_extractions WHERE group_id=?', (gid,))
        for ext_type, content in items:
            conn.execute(
                'INSERT INTO ai_extractions (group_id, extract_type, content, generated_at) VALUES (?, ?, ?, ?)',
                (gid, ext_type, content, now)
            )
            total += 1
            by_type[ext_type] = by_type.get(ext_type, 0) + 1

    conn.commit()
    conn.close()
    return {
        'total': total,
        'groups_count': len(group_data),
        'by_type': by_type
    }


def append_extractions(group_data):
    """增量追加提取结果到 ai_extractions 表（只 INSERT，不 DELETE）。

    按 (group_id, extract_type, content) 去重，避免重复插入。

    Args:
        group_data: dict, {group_id: [(extract_type, content_json_str), ...], ...}

    Returns:
        dict: {total, inserted, skipped, groups_count, by_type: {extract_type: count}}
    """
    conn = get_db()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    total = 0
    inserted = 0
    skipped = 0
    by_type = {}

    for gid, items in group_data.items():
        for ext_type, content in items:
            total += 1
            existing = conn.execute(
                'SELECT id FROM ai_extractions WHERE group_id=? AND extract_type=? AND content=?',
                (gid, ext_type, content)
            ).fetchone()
            if existing:
                skipped += 1
                continue
            conn.execute(
                'INSERT INTO ai_extractions (group_id, extract_type, content, generated_at) VALUES (?, ?, ?, ?)',
                (gid, ext_type, content, now)
            )
            inserted += 1
            by_type[ext_type] = by_type.get(ext_type, 0) + 1

    conn.commit()
    conn.close()
    return {
        'total': total,
        'inserted': inserted,
        'skipped': skipped,
        'groups_count': len(group_data),
        'by_type': by_type
    }
