# UV Mix Batch on a Windows PC (testing)

This runs the portal on your own PC. You open it in your browser at **http://localhost:8765**.
It's meant for testing; the live version will be hosted online later.

## One-time setup
1. **Copy this whole folder** to the PC, for example to `C:\UV Mix Batch`.
2. **Install Python 3.12** if it isn't already installed. Get it from https://www.python.org/downloads/ (the Windows installer, 64-bit). On its first screen, tick **"Add python.exe to PATH"**.
3. **Double-click `Setup.bat`.** The first run takes a few minutes. It does three things:
   - installs everything the portal needs, inside this folder only;
   - opens a settings file in Notepad;
   - checks the connection to the Pulse database.
4. **Fill in the settings file (`.env`)** that opens in Notepad:
   - `DB_USER` and `DB_PASSWORD`: the Pulse database login, which you get from Rahul.
   - `PORTAL_USERS`: logins for the portal. For example `priya:Uv2026!,amit:Print#7` gives two users.
   Then **save** the file and run `Setup.bat` again to check the connection.
5. **If Setup says "Cannot reach Pulse"**, send Rahul the internet address it shows. That address has to be allowlisted on the database before the portal can work.

## Every day
- **Double-click `Start UV Mix.bat`.** A black window opens, and your browser opens the portal at http://localhost:8765.
- **Keep the black window open** while you work. Closing it stops the portal.
- **Your files:** finished batches (ZIP, File, Die and Spot PDFs, Excel) download from the browser, and a copy is kept in `data\runs\`.

## If something goes wrong
- **Windows says "Windows protected your PC"** when you run a `.bat` file: click **More info**, then **Run anyway**.
- **The browser says "can't reach this page"**: check that the black window is still open, then refresh.
- **Anything else:** take a screenshot of the black window and send it to Rahul.
