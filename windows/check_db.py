"""Setup check: can this PC reach Pulse with the settings in .env? (read-only)"""

import os
import sys
import urllib.request
from pathlib import Path

root = Path(__file__).resolve().parent.parent
for line in (root / ".env").read_text(encoding="utf-8-sig").splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"'))

try:
    ip = urllib.request.urlopen("https://api.ipify.org", timeout=10).read().decode()
except Exception:
    ip = "unknown"
print(f"This PC's internet address: {ip}")

if not os.environ.get("DB_USER") or not os.environ.get("DB_PASSWORD"):
    print("DB_USER / DB_PASSWORD are empty in .env - fill them in, then run Setup.bat again.")
    sys.exit(0)

import mysql.connector  # noqa: E402

try:
    conn = mysql.connector.connect(
        host=os.environ.get("DB_HOST", "pulse.getmt3.com"),
        port=int(os.environ.get("DB_PORT", "3306")),
        user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"],
        database=os.environ.get("DB_NAME", "mt3narada"), connection_timeout=15,
    )
    conn.close()
    print("OK - connected to Pulse.")
except mysql.connector.Error as e:
    if e.errno == 2003:
        print(f"Cannot reach Pulse. Ask for this address to be allowlisted on the database (port 3306): {ip}")
    elif e.errno == 1045:
        print("Pulse refused the login - check DB_USER / DB_PASSWORD in .env.")
    else:
        print(f"Pulse error: {e}")
