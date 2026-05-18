import subprocess
import sys
import os
import time
import webbrowser

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(SCRIPT_DIR, "data", "flask_launcher.log")

os.chdir(SCRIPT_DIR)
os.makedirs("data", exist_ok=True)
sys.stdout = open(LOG_FILE, "w", encoding="utf-8", buffering=1)
sys.stderr = sys.stdout

PYTHON_EXE = os.path.join(SCRIPT_DIR, ".venv", "Scripts", "python.exe")
PYTHONW_EXE = os.path.join(SCRIPT_DIR, ".venv", "Scripts", "pythonw.exe")
FLASK_PORT = 8888


def check_port(port):
    result = subprocess.run(
        ["netstat", "-ano"], capture_output=True, text=True
    )
    needle = f":{port}"
    for line in result.stdout.splitlines():
        if needle in line and "LISTENING" in line:
            return True
    return False


def wait_port(port, timeout=10):
    for _ in range(timeout):
        time.sleep(1)
        if check_port(port):
            return True
    return False


if check_port(FLASK_PORT):
    print(f"WXDashboard already running on port {FLASK_PORT}")
    sys.exit(1)

if not os.path.exists(PYTHON_EXE):
    print(f"venv not found at {PYTHON_EXE}")
    sys.exit(1)

print("Initializing database...")
subprocess.run(
    [PYTHON_EXE, "-c", "from backend.database import init_db; init_db()"],
    capture_output=True,
    creationflags=subprocess.CREATE_NO_WINDOW,
)

print("Starting Flask in background...")
flask_stdout = open(os.path.join(SCRIPT_DIR, "data", "flask.log"), "w", encoding="utf-8", buffering=1)
flask_stderr = open(os.path.join(SCRIPT_DIR, "data", "flask_error.log"), "w", encoding="utf-8", buffering=1)
subprocess.Popen(
    [PYTHONW_EXE, "-m", "backend.app"],
    stdout=flask_stdout,
    stderr=flask_stderr,
    creationflags=subprocess.CREATE_NO_WINDOW,
)

if not wait_port(FLASK_PORT):
    print(f"Timeout: Flask did not start within 10 seconds")
    sys.exit(1)

print(f"Flask ready on http://127.0.0.1:{FLASK_PORT}")
webbrowser.open(f"http://127.0.0.1:{FLASK_PORT}")
sys.exit(0)
