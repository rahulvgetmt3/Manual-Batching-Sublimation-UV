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

**Updating team PCs:** after code changes, run `git archive --format=zip -o dist/app-update.zip HEAD app`. The team then:
1. closes the Start window;
2. unzips the update into their folder and replaces `app`;
3. restarts.

Their settings, login and history are kept. This worked on 2026-10-11.

**Since 2026-10-12, use the full update:** `dist/Manual-Batching-UPDATE.zip`, which holds `app`, `requirements.txt`, Setup/Start bats, `windows/`, README-WINDOWS, `.env.example` and "UPDATE - READ ME.txt". It has no credentials. The team copies everything over the existing folder, keeping `.env` and `data`, then runs **Setup.bat once** (segno was added for labels; the UV team's original package predates it), starts with "Start Manual Batching.bat" and presses Ctrl+F5. For new PCs, rebuild `UV-Mix-Batch-Windows.zip` and ask Rahul to rerun `make_team_zip.py`, which creates a new `uvteam` password each time.

**Windows gotcha (fixed 2026-10-11):** Python's `read_text()` / `open()` without an encoding uses **cp1252 on Windows**. The UI showed mojibake ("â¬‡ ZIP", "LUX Â· 2 pieces"). **Always pass `encoding="utf-8"`** for text files in `app/`. Mac testing won't catch this.

**How to apply:** test anything text-related with Windows in mind, and ship fixes through `app-update.zip`.

Related: [[uv-mix-portal-overview]], [[pulse-lookup-for-uv-mix]].

**Sublimation (Design) team package (2026-10-12):** built from the `sublimation` branch:
```
python3 tools/make_team_zip.py --login DesignTeam --process sub --out Manual-Batching-Sublimation-TEAM.zip
```
- The output is `dist/Manual-Batching-Sublimation-TEAM.zip`. The folder is now named "Manual Batching" and the launcher is **`Start Manual Batching.bat`**; it was "Start UV Mix.bat".
- `DEFAULT_PROCESS=sub` in its `.env` makes a fresh browser open on Sublimation › Build batch (`/api/me` returns `default_process`). UV stays reachable from the menu.
- Login: **DesignTeam**. The password is in `START HERE.txt` and `dist/LOGINS-private.txt`, never in git.
- The builder packages **committed** files (`git archive HEAD`), so commit before building.

**Python version (2026-10-12):** the Design team PC had **Python 3.14**. Installing **3.13 alongside it** worked, because Setup asks the py launcher for 3.12/3.13 first; 3.14 isn't supported yet (no cp314 wheels for pikepdf, the mysql connector and others). python.org security-only releases (e.g. 3.12.15) have **no Windows installer**, so point people at 3.13 (`winget install Python.Python.3.13`) or 3.12.10. The docs, START HERE text and Setup message now say this. **The Design team is set up and running.**

**Update 2026-10-16 (batch numbers):** rebuilt `dist/Manual-Batching-UPDATE.zip` from commit 548fc6d with `git archive HEAD app requirements.txt Setup.bat "Start Manual Batching.bat" windows README-WINDOWS.md .env.example`, then added a CRLF "UPDATE - READ ME.txt" (written in the scratchpad). **Setup.bat is required this time:** `python-barcode` was added to requirements.txt and the app won't start without it. Rahul is sending it to both teams. On Rahul's Mac, code changes need a portal restart (`./start-mac.sh`), because uvicorn runs without reload; a stale server is why his first test "didn't work".
