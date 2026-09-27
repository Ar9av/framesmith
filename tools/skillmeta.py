"""Tiny SKILL.md frontmatter reader shared by the repo tools (no PyYAML needed)."""
import os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(path):
    s = open(path, encoding="utf-8").read()
    m = re.match(r"^---\n(.*?)\n---\n", s, re.S)
    if not m:
        return None, s
    meta, key = {}, None
    for line in m.group(1).splitlines():
        if re.match(r"^\w[\w-]*:", line):
            key, _, val = line.partition(":")
            meta[key.strip()] = val.strip()
        elif key and line.startswith("  ") and ":" in line and meta.get(key) == "":
            k2, _, v2 = line.strip().partition(":")
            meta.setdefault(key + "." + k2.strip(), v2.strip())
    return meta, s[m.end():]


def skills():
    base = os.path.join(ROOT, "skills")
    for name in sorted(os.listdir(base)):
        p = os.path.join(base, name, "SKILL.md")
        if os.path.exists(p):
            meta, body = read(p)
            yield name, p, meta, body
