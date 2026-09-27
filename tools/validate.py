#!/usr/bin/env python3
"""Validate every skill: frontmatter, naming, size limits, vendored engine, example brief renders a frame.

    python3 tools/validate.py            # full (renders one still per template)
    python3 tools/validate.py --fast     # static checks only
"""
import os, re, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from skillmeta import ROOT, skills  # noqa: E402

errors = []


def err(skill, msg):
    errors.append(f"{skill}: {msg}")


def main():
    fast = "--fast" in sys.argv
    for name, path, meta, body in skills():
        if meta is None:
            err(name, "SKILL.md has no YAML frontmatter")
            continue
        if meta.get("name") != name:
            err(name, f"frontmatter name '{meta.get('name')}' must equal folder name")
        if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name) or len(name) > 64:
            err(name, "name must be kebab-case, ≤ 64 chars")
        desc = meta.get("description", "")
        if len(desc) < 80:
            err(name, "description too short; it is the trigger, so say what AND when")
        if len(desc) > 1024:
            err(name, f"description is {len(desc)} chars (max 1024)")
        if "TODO" in desc or "TODO" in body[:400]:
            err(name, "still contains TODO")
        if len(body.splitlines()) > 500:
            err(name, "SKILL.md body > 500 lines; move detail into references/")
        scripts = os.path.join(ROOT, "skills", name, "scripts")
        entries = [f for f in os.listdir(scripts) if f.endswith(".py")] if os.path.isdir(scripts) else []
        if entries and not fast:
            ex = os.path.join(ROOT, "skills", name, "examples")
            briefs = [os.path.join(dp, "brief.json") for dp, _, fs in os.walk(ex) if "brief.json" in fs]
            for b in briefs[:1]:
                for e in entries:
                    r = subprocess.run([sys.executable, os.path.join(scripts, e), "still", "--brief", b, "1.0"],
                                       capture_output=True, text=True)
                    if r.returncode:
                        err(name, f"{e} still failed:\n{r.stderr[-800:]}")
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "sync_core.py"), "--check"], capture_output=True, text=True)
    if r.returncode:
        errors.append("vendored engine is stale; run tools/sync_core.py\n" + r.stdout)
    for e in errors:
        print("✗", e)
    print("ok" if not errors else f"{len(errors)} problem(s)")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
