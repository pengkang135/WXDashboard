import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "ledger_v2.db")

LEGACY_EXCEL = os.path.join(BASE_DIR, "Laldia", "Laldia港湾微信群台账.xlsx")
LEGACY_WX_JSON_DIR = os.path.join(BASE_DIR, "Laldia", "wx_json")
LEGACY_LEDGER_JSON = os.path.join(BASE_DIR, "Laldia", "Laldia微信群台账.json")
LEGACY_DAILY_SUMMARY = os.path.join(BASE_DIR, "Laldia", "每日摘要")
LEGACY_ARCHIVE_DIR = os.path.join(BASE_DIR, "Laldia", "微信群归档")
LEGACY_ARCHIVE_LEGACY_DIR = os.path.join(BASE_DIR, "Laldia", "微信群归档_legacy")

TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")

FLASK_HOST = "127.0.0.1"
FLASK_PORT = 8888
