#!/usr/bin/env python3
"""Regenerate the skills table in README.md (between <!-- catalog:start/end --> markers)
from each SKILL.md's frontmatter. The router skill keeps its own hand-written table."""
import os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from skillmeta import ROOT, skills  # noqa: E402


def first_sentence(s):
    s = s.strip().strip('"')
    m = re.match(r"(.+?[.!?])(\s|$)", s)
    return (m.group(1) if m else s)[:220]


def main():
    rows = ["| Skill | What it makes | Preview |", "|---|---|---|"]
    for name, path, meta, _ in skills():
        if name == "framesmith":
            continue
        gif = f"docs/media/{name}.gif"
        prev = f'<img src="{gif}" width="120">' if os.path.exists(os.path.join(ROOT, gif)) else "—"
        rows.append(f"| [`{name}`](skills/{name}/SKILL.md) | {first_sentence(meta.get('description', ''))} | {prev} |")
    table = "\n".join(rows)
    p = os.path.join(ROOT, "README.md")
    s = open(p, encoding="utf-8").read()
    s2 = re.sub(r"(<!-- catalog:start -->\n).*?(\n<!-- catalog:end -->)", lambda m: m.group(1) + table + m.group(2), s, flags=re.S)
    open(p, "w", encoding="utf-8").write(s2)
    print("README catalog updated" if s2 != s else "README catalog already current")


if __name__ == "__main__":
    main()
