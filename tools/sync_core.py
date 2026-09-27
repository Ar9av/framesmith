#!/usr/bin/env python3
"""Vendor core/framesmith into every skill that uses it (skills/*/scripts/framesmith).

Skills must be self-contained so `npx skills add` / plugin installs work without
the rest of the repo. core/ is the source of truth; never edit vendored copies.

    python3 tools/sync_core.py          # copy
    python3 tools/sync_core.py --check  # exit 1 if any copy is stale (CI)
"""
import filecmp, os, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORE = os.path.join(ROOT, "core", "framesmith")


def targets():
    sk = os.path.join(ROOT, "skills")
    for name in sorted(os.listdir(sk)):
        scripts = os.path.join(sk, name, "scripts")
        if os.path.exists(os.path.join(scripts, "framesmith")) or os.path.exists(os.path.join(sk, name, ".uses-framesmith")):
            yield os.path.join(scripts, "framesmith")


def same(a, b):
    cmp = filecmp.dircmp(a, b, ignore=["__pycache__"])
    if cmp.left_only or cmp.right_only or cmp.diff_files or cmp.funny_files:
        return False
    return all(same(os.path.join(a, d), os.path.join(b, d)) for d in cmp.common_dirs)


def main():
    check = "--check" in sys.argv
    stale = []
    for dst in targets():
        if check:
            if not os.path.exists(dst) or not same(CORE, dst):
                stale.append(dst)
            continue
        shutil.rmtree(dst, ignore_errors=True)
        shutil.copytree(CORE, dst, ignore=shutil.ignore_patterns("__pycache__"))
        print("synced", os.path.relpath(dst, ROOT))
    if check:
        for s in stale:
            print("stale:", os.path.relpath(s, ROOT))
        sys.exit(1 if stale else 0)


if __name__ == "__main__":
    main()
