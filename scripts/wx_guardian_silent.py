"""wx-cli guardian — kill stale wx-cli daemon processes (silent)."""
import subprocess
import sys
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PS1_PATH = os.path.join(SCRIPT_DIR, "wx_guardian.ps1")

subprocess.run(
    ["powershell.exe", "-NoProfile", "-NonInteractive", "-File", PS1_PATH],
    creationflags=subprocess.CREATE_NO_WINDOW,
    capture_output=True,
    timeout=30,
)
