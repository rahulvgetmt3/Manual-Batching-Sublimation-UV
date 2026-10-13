#!/usr/bin/env python3
"""Build the ready-to-use Windows test package for the team.

Run it yourself on the Mac (it reads your own Pulse login):
    cd "~/Dev/Mix Batch UV and Sublimation"
    python3 tools/make_team_zip.py                                   # UV team (login uvteam, opens on UV)
    python3 tools/make_team_zip.py --login DesignTeam --process sub \
        --out Manual-Batching-Sublimation-TEAM.zip                    # Sublimation (design) team

It writes dist/UV-Mix-Batch-Windows-TEAM.zip: the app, the Windows launchers,
a filled-in .env (the DB_* lines copied from ~/Dev/Pulse/.env, plus a new
portal login and a random session key) and "START HERE.txt" with the login.
The new login is printed on screen. dist/ is git-ignored, so the password
never goes into GitHub. CONFIDENTIAL: share the ZIP with the team only.
"""

import argparse
import secrets
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PULSE_ENV = Path.home() / "Dev" / "Pulse" / ".env"
FOLDER = "Manual Batching"
FILES = ["app", "requirements.txt", "Setup.bat", "Start Manual Batching.bat", "windows", ".env.example", "README-WINDOWS.md"]


def main():
    ap = argparse.ArgumentParser(description="Build a pre-filled Windows test package")
    ap.add_argument("--login", default="uvteam", help="portal username for this team")
    ap.add_argument("--process", choices=("uv", "sub"), default="uv", help="page the portal opens on")
    ap.add_argument("--out", default="UV-Mix-Batch-Windows-TEAM.zip", help="file name in dist/")
    args = ap.parse_args()
    out_zip = ROOT / "dist" / args.out
    db = {"DB_HOST": "pulse.getmt3.com", "DB_PORT": "3306", "DB_NAME": "mt3narada"}
    for line in PULSE_ENV.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            if k.strip() in ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"):
                db[k.strip()] = v.strip().strip('"')
    if not db.get("DB_USER") or not db.get("DB_PASSWORD"):
        sys.exit(f"DB_USER / DB_PASSWORD not found in {PULSE_ENV}")

    user = args.login
    pw = secrets.token_urlsafe(9)
    env = (
        "# Manual Batching - team test PC settings (pre-filled). CONFIDENTIAL: contains the Pulse database login.\n"
        + "".join(f"{k}={db[k]}\n" for k in ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"))
        + f"\n# Portal login(s): username:password, comma-separated.\nPORTAL_USERS={user}:{pw}\n\n"
        + f"SECRET_KEY={secrets.token_urlsafe(48)}\nCOOKIE_SECURE=0\n"
        + f"\n# Page the portal opens on: uv (UV Mix) or sub (Sublimation)\nDEFAULT_PROCESS={args.process}\n"
    )
    home = "Sublimation" if args.process == "sub" else "UV Mix"
    start = f"""MANUAL BATCHING ({home}) - START HERE (team testing)
====================================================

Everything is already set up - no settings to change.

1. Copy the "Manual Batching" folder to this PC (e.g. C:\\Manual Batching).
2. Install Python 3.13 (PowerShell: winget install Python.Python.3.13, or
   https://www.python.org/downloads/windows/ -> latest 3.13.x "Windows installer (64-bit)").
   Tick "Add python.exe to PATH". Python 3.14 is NOT supported yet - if the PC has 3.14,
   keep it and install 3.13 alongside; Setup picks 3.13 automatically.
3. Double-click  Setup.bat  (once; takes a few minutes). It should end with
   "OK - connected to Pulse."
4. Double-click  Start Manual Batching.bat  (every day). The browser opens
   http://localhost:8765 on the {home} page (switch via the "Manual Batching" menu).
   Keep the black window open while working.

Portal login
   Username: {user}
   Password: {pw}

If Setup says "Cannot reach Pulse", send Rahul the internet address it prints -
the database only accepts allowlisted office addresses.

Full guide: README-WINDOWS.md.  CONFIDENTIAL - do not forward outside the team.
"""

    out_zip.parent.mkdir(exist_ok=True)
    subprocess.run(["git", "archive", "--format=zip", f"--prefix={FOLDER}/", "-o", str(out_zip), "HEAD", *FILES],
                   cwd=ROOT, check=True)
    with zipfile.ZipFile(out_zip, "a", zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"{FOLDER}/.env", env)
        z.writestr(f"{FOLDER}/START HERE.txt", start.replace("\n", "\r\n"))

    print(f"Built {out_zip}")
    print(f"Portal login for the team:  {user} / {pw}   (also inside START HERE.txt)")


if __name__ == "__main__":
    main()
