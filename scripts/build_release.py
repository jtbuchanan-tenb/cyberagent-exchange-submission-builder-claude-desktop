#!/usr/bin/env python3
"""Build the uploadable skill zip for Claude Desktop / claude.ai / Cowork - reproducibly.

The zip's top-level folder matches the `name:` in SKILL.md frontmatter (Claude's
skill upload requires that). The build is deterministic: same sources -> byte-for-byte
the same zip (sorted entries, fixed timestamps and permissions). --check compares the
*contents* (entry names, modes, file bytes) rather than compressed bytes, so a different
zlib build on a CI runner can't cause a false "stale" result.

Usage:
  python3 scripts/build_release.py            # write dist/<name>.zip
  python3 scripts/build_release.py --check    # exit 1 if dist/<name>.zip is missing or stale
"""
from __future__ import annotations

import argparse
import io
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INCLUDE_FILES = ["SKILL.md", "VERSION", "LICENSE", "README.md"]
INCLUDE_DIRS = ["references", "scripts", "assets"]
SKIP = re.compile(r"(__pycache__|\.pyc$|\.DS_Store$)")
EPOCH = (1980, 1, 1, 0, 0, 0)


def skill_name() -> str:
    m = re.search(r"^name:\s*(\S+)\s*$", (ROOT / "SKILL.md").read_text(encoding="utf-8"), re.M)
    if not m:
        sys.exit("SKILL.md has no name: in its frontmatter")
    return m.group(1).strip("\"'")


def sources() -> list[Path]:
    files = [ROOT / f for f in INCLUDE_FILES if (ROOT / f).is_file()]
    for d in INCLUDE_DIRS:
        if (ROOT / d).is_dir():
            files += [p for p in (ROOT / d).rglob("*") if p.is_file() and not SKIP.search(str(p))]
    return sorted(files, key=lambda p: p.relative_to(ROOT).as_posix())


def build_bytes(name: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        dirs: set[str] = set()
        for p in sources():
            rel = p.relative_to(ROOT).as_posix()
            parts = rel.split("/")[:-1]
            for i in range(len(parts) + 1):
                d = "/".join([name] + parts[:i]) + "/"
                if d not in dirs:
                    dirs.add(d)
                    zi = zipfile.ZipInfo(d, EPOCH)
                    zi.external_attr = (0o40755 << 16) | 0x10
                    z.writestr(zi, b"")
            zi = zipfile.ZipInfo(f"{name}/{rel}", EPOCH)
            executable = rel.startswith("scripts/") and p.suffix in (".py", ".sh")
            zi.external_attr = ((0o100755 if executable else 0o100644) << 16)
            zi.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(zi, p.read_bytes())
    return buf.getvalue()


def entries(data: bytes) -> dict:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return {i.filename: (i.external_attr >> 16, z.read(i)) for i in z.infolist()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="fail if the committed zip doesn't match the sources")
    a = ap.parse_args()
    name = skill_name()
    out = ROOT / "dist" / f"{name}.zip"
    data = build_bytes(name)
    version = (ROOT / "VERSION").read_text().strip() if (ROOT / "VERSION").is_file() else "?"
    if a.check:
        if not out.is_file() or entries(out.read_bytes()) != entries(data):
            print(f"STALE: {out.relative_to(ROOT)} does not match the sources. Run: python3 scripts/build_release.py")
            return 1
        print(f"OK: {out.relative_to(ROOT)} matches the sources (version {version})")
        return 0
    out.parent.mkdir(exist_ok=True)
    if out.is_file() and entries(out.read_bytes()) == entries(data):
        print(f"{out}  already up to date (version {version})")
        return 0
    out.write_bytes(data)
    print(f"{out}  (version {version})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
