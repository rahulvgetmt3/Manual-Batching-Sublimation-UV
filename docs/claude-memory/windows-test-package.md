---
name: windows-test-package
description: How the team runs the portal locally on Windows for testing, and how the credential-bearing team ZIP must be built (by Rahul, not Claude)
metadata:
  type: project
---

**What the team runs:** a local copy on Windows PCs (testing only, 2026-10-11):
- **`Setup.bat`**, once. It finds Python 3.10–3.13 (3.12 preferred), creates `.venv`, runs `pip install -r requirements.txt`, creates `.env` if it's missing, and checks the DB with `windows/check_db.py`. That check prints the PC's public IP when port 3306 isn't reachable.
- **`Start UV Mix.bat`**, each day. It loads `.env`, forces `COOKIE_SECURE=0`, serves on 127.0.0.1:8765 and opens the browser.

Both `.bat` files call `windows/*.ps1` with `-ExecutionPolicy Bypass`. Guide: `README-WINDOWS.md`. `requirements.txt` pins `numpy>=2.0.2,<3` so the install also works on Python 3.13.

**Two ZIPs, both in `dist/` (git-ignored):**
- `UV-Mix-Batch-Windows.zip`: no secrets. Built with `git archive`; the command is in SCRATCHPAD.
- `UV-Mix-Batch-Windows-TEAM.zip`: pre-filled `.env` (the DB_* lines from `~/Dev/Pulse/.env`, portal user `uvteam` with a random password, a random SECRET_KEY) plus `START HERE.txt`. Built by `tools/make_team_zip.py`. **Rahul runs it himself**, or explicitly tells Claude to.

**Credential rule:** Claude's auto-mode classifier blocks Claude from copying the DB password into a shareable file, and from committing the builder script ("Credential Leakage"). That's correct: sharing credentials is Rahul's decision. When Rahul explicitly asked, running `python3 tools/make_team_zip.py` was allowed. Never put credentials in git.

**Result:** the team PC connected to Pulse on 2026-10-11. It must be on an IP that's allowlisted on the DB security group.

**Why:** Rahul wanted the team to test fully without needing him, before the proper hosted deployment.

**How to apply:** after code changes, rebuild the plain ZIP. Ask Rahul to rerun `make_team_zip.py` (this gives a new portal password each time), or ask the team to replace just the `app/` folder.

Related: [[uv-mix-portal-overview]], [[pulse-lookup-for-uv-mix]].
