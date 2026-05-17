import re
from .database import get_db

EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
PHONE_RE = re.compile(r'1[3-9]\d{9}')


def _dedup_contacts(contacts):
    seen = set()
    result = []
    for c in contacts:
        key = (c['group_id'], c['sender_name'], c['email'] or '', c['phone'] or '')
        if key not in seen:
            seen.add(key)
            result.append(c)
    return result


def extract_from_message(group_id, message_id, sender, content):
    if not content:
        return []
    emails = EMAIL_RE.findall(content)
    phones = PHONE_RE.findall(content)
    contacts = []
    for email in emails:
        contacts.append({
            'group_id': group_id,
            'sender_name': sender,
            'email': email,
            'phone': None,
            'source_message_id': message_id,
            'extraction_method': 'regex',
            'confirmed': 0
        })
    for phone in phones:
        contacts.append({
            'group_id': group_id,
            'sender_name': sender,
            'email': None,
            'phone': phone,
            'source_message_id': message_id,
            'extraction_method': 'regex',
            'confirmed': 0
        })
    return _dedup_contacts(contacts)


def extract_and_save(conn, group_id, message_id, sender, content):
    contacts = extract_from_message(group_id, message_id, sender, content)
    for c in contacts:
        existing = conn.execute(
            "SELECT id FROM contacts WHERE group_id=? AND sender_name=? AND email IS ? AND phone IS ?",
            (c['group_id'], c['sender_name'], c['email'], c['phone'])
        ).fetchone()
        if not existing:
            conn.execute("""
                INSERT INTO contacts (group_id, sender_name, email, phone,
                                     source_message_id, extraction_method, confirmed)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (c['group_id'], c['sender_name'], c['email'], c['phone'],
                  c['source_message_id'], c['extraction_method'], c['confirmed']))
    return len(contacts)


def extract_for_group(group_id):
    conn = get_db()
    rows = conn.execute("""
        SELECT id, sender, content FROM messages
        WHERE group_id=? AND (content LIKE '%@%.%' OR content LIKE '%1_________%')
    """, (group_id,)).fetchall()
    count = 0
    for r in rows:
        count += extract_and_save(conn, group_id, r['id'], r['sender'], r['content'])
    conn.commit()
    conn.close()
    return count
