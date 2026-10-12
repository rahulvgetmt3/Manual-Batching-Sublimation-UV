---
name: pulse-design-system
description: The portal UI uses Pulse's own CSS (copied verbatim) so it can move into Pulse as a "Batching" dropdown; how to re-extract it
metadata:
  type: project
---

**The plan:** Rahul wants to move this tool into **Pulse** (pulse.getmt3.com, the MT3 React app) later, as just another **dropdown in the top menu ("Batching ▾")**, alongside Orders, Logistics, Print Mgmt and the rest. So the UI must look like Pulse **and use Pulse's class names**.

**How it's done (2026-10-12):**
- `app/static/pulse-shell.css` holds rules copied **verbatim** from Pulse's public stylesheet `https://pulse.getmt3.com/assets/index-CHH9mRZz.css`. The hash changes on each Pulse deploy; find the current one in `<link rel=stylesheet>` of `https://pulse.getmt3.com/`. **Fetch it with a browser User-Agent**, because plain curl hangs. A local copy is in `Reference/pulse-theme/`, which is git-ignored.
- **What was copied:**
  - the `:root` tokens: `--color-primary #667eea`, `--secondary #764ba2`, `--gradient-primary`, the gray scale, `--nordic-*`, `--radius-*`;
  - the aurora shell vars (`--sh-*`);
  - the `body` font: **"Segoe UI, Tahoma, Geneva, Verdana"**, with background `#f5f5f7`;
  - the classes `.app-header-menu*`, `.top-nav*`, `.cd-kpi*`, `.cd-badge*`, `.cd-btn*`, `.cd-card*`, `.cd-page*`, `.cd-pill-tab*` and `.nordic-table*`.

  Only the first occurrence of each selector was kept, so later media-query overrides are skipped.
- **In the page:** `index.html` uses that markup: the header with the logo, title "Batching" and a top-nav **Batching ▾ dropdown** (UV Mix › Build batch / History; Sublimation › Coming soon), plus a user button with a dropdown containing Sign out.
  - A small "bridge" CSS block maps the older page classes onto Pulse tokens.
  - Tables are `.nordic-table`, statuses are `.cd-badge-*`, buttons are `.cd-btn-*`, input tabs are `.cd-pill-tab`, and the last batch is a `.cd-kpi.c-green` card.

**Why:** a first attempt with colours sampled from screenshots and the Inter font looked wrong to Rahul ("fonts etc are not matching"). Pulse's font stack is Segoe UI → Tahoma, so on a Mac it renders in Tahoma.

**How to apply:**
- New screens, including Sublimation, should use these Pulse classes rather than new styles.
- If Pulse's theme changes, re-extract the rules (the script logic is in this session's transcript) and don't hand-edit `pulse-shell.css`.
- The Sublimation entry in the dropdown is where the Sublimation page will go.

Related: [[uv-mix-portal-overview]], [[uv-mix-team-requirements]].
