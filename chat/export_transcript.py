#!/usr/bin/env python3
"""Turn a Claude Code session .jsonl into a readable transcript.md.

Usage:  python3 chat/export_transcript.py <session.jsonl> chat/transcript.md
Secrets: the DB_PASSWORD value found in the environment is masked (it has never appeared so far).
"""

import json
import os
import re
import sys

SECRETS = [v for v in (os.environ.get("DB_PASSWORD"),) if v and len(v) >= 4]


def mask(s):
    for v in SECRETS:
        s = s.replace(v, "<redacted>")
    return s


def clean_user(text):
    text = re.sub(r"<system-reminder>.*?</system-reminder>", "", text, flags=re.S)
    text = re.sub(r"<ide_selection>.*?</ide_selection>", "", text, flags=re.S)
    return text.strip()


def tool_line(block):
    inp = block.get("input", {})
    name = block.get("name", "tool")
    desc = inp.get("description") or inp.get("file_path") or inp.get("query") or inp.get("pattern") or ""
    if name == "Bash" and inp.get("command"):
        cmd = inp["command"].strip().splitlines()[0][:160]
        return f"- 🔧 **{name}** — {desc}\n  `{cmd}`"
    return f"- 🔧 **{name}** — {desc}"


def main(src, dst):
    out = ["# Chat transcript — UV Mix Batch portal", "",
           "Readable export of the Claude Code session. Tool calls are summarised; tool output is shortened.", ""]
    for line in open(src, encoding="utf-8"):
        d = json.loads(line)
        t = d.get("type")
        if t not in ("user", "assistant") or d.get("isSidechain"):
            continue
        ts = d.get("timestamp", "")[:16].replace("T", " ")
        content = d["message"].get("content")
        blocks = [{"type": "text", "text": content}] if isinstance(content, str) else content
        parts = []
        for b in blocks:
            bt = b.get("type")
            if t == "user" and bt == "text":
                txt = clean_user(b["text"])
                if txt:
                    parts.append(txt)
            elif t == "user" and bt == "image":
                parts.append("*[screenshot attached]*")
            elif t == "user" and bt == "tool_result":
                c = b.get("content")
                if isinstance(c, list):
                    c = " ".join(x.get("text", "[image]") if x.get("type") == "text" else "[image]" for x in c)
                c = (c or "").strip()
                if c:
                    short = c[:400] + (" …" if len(c) > 400 else "")
                    parts.append("  <details><summary>output</summary>\n\n```\n" + short + "\n```\n</details>")
            elif t == "assistant" and bt == "text" and b.get("text", "").strip():
                parts.append(b["text"].strip())
            elif t == "assistant" and bt == "tool_use":
                parts.append(tool_line(b))
        if not parts:
            continue
        only_results = t == "user" and all(p.startswith("  <details>") for p in parts)
        if only_results:
            out += parts + [""]
        else:
            out += [f"## {'🧑 Rahul' if t == 'user' else '🤖 Claude'} · {ts}", ""] + parts + [""]
    with open(dst, "w", encoding="utf-8") as f:
        f.write(mask("\n".join(out)))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
