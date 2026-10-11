#!/usr/bin/env python3
"""Build the ready-to-use Windows test package for the team.

Run it yourself on the Mac (it reads your own Pulse login):
    cd "~/Dev/Mix Batch UV"
    python3 tools/make_team_zip.py

It writes dist/UV-Mix-Batch-Windows-TEAM.zip: the app, the Windows launchers,
a filled-in .env (the DB_* lines copied from ~/Dev/Pulse/.env, plus a new
portal login and a random session key) and "START HERE.txt" with the login.
The new login is printed on screen. dist/ is git-ignored, so the password
never goes into GitHub. CONFIDENTIAL: share the ZIP with the team only.
"""

import secrets
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PULSE_ENV = Path.home() / "Dev" / "Pulse" / ".env"
OUT = ROOT / "dist" / "UV-Mix-Batch-Windows-TEAM.zip"
FILES = ["app", "requirements.txt", "Setup.bat", "Start UV Mix.bat", "windows", ".env.example", "README-WINDOWS.md"]


def main():
    db = {"DB_HOST": "pulse.getmt3.com", "DB_PORT": "3306", "DB_NAME": "mt3narada"}
    for line in PULSE_ENV.read_text().splitlines():
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            if k.strip() in ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"):
                db[k.strip()] = v.strip().strip('"')
    if not db.get("DB_USER") or not db.get("DB_PASSWORD"):
        sys.exit(f"DB_USER / DB_PASSWORD not found in {PULSE_ENV}")

    user = "uvteam"
    pw = secrets.token_urlsafe(9)
    env = (
        "# UV Mix Batch - team test PC settings (pre-filled). CONFIDENTIAL: contains the Pulse database login.\n"
        + "".join(f"{k}={db[k]}\n" for k in ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"))
        + f"\n# Portal login(s): username:password, comma-separated.\nPORTAL_USERS={user}:{pw}\n\n"
        + f"SECRET_KEY={secrets.token_urlsafe(48)}\nCOOKIE_SECURE=0\n"
    )
    start = f"""UV MIX BATCH - START HERE (team testing)
=======================================

Everything is already set up - no settings to change.

1. Copy the "UV Mix Batch" folder to this PC (e.g. C:\\UV Mix Batch).
2. Install Python 3.12 if not already installed: https://www.python.org/downloads/
   On the first installer screen tick "Add python.exe to PATH".
3. Double-click  Setup.bat  (once; takes a few minutes). It should end with
   "OK - connected to Pulse."
4. Double-click  Start UV Mix.bat  (every day). The browser opens http://localhost:8765
   Keep the black window open while working.

Portal login
   Username: {user}
   Password: {pw}

If Setup says "Cannot reach Pulse", send Rahul the internet address it prints -
the database only accepts allowlisted office addresses.

Full guide: README-WINDOWS.md.  CONFIDENTIAL - do not forward outside the team.
"""

    OUT.parent.mkdir(exist_ok=True)
    subprocess.run(["git", "archive", "--format=zip", "--prefix=UV Mix Batch/", "-o", str(OUT), "HEAD", *FILES],
                   cwd=ROOT, check=True)
    with zipfile.ZipFile(OUT, "a", zipfile.ZIP_DEFLATED) as z:
        z.writestr("UV Mix Batch/.env", env)
        z.writestr("UV Mix Batch/START HERE.txt", start.replace("\n", "\r\n"))

    print(f"Built {OUT}")
    print(f"Portal login for the team:  {user} / {pw}   (also inside START HERE.txt)")


if __name__ == "__main__":
    main()
