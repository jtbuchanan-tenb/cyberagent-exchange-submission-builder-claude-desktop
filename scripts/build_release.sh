#!/usr/bin/env bash
# Package the skill as an uploadable zip for Claude Desktop / claude.ai / Cowork.
# The zip's top-level folder must match the skill name in SKILL.md frontmatter.
# Usage: scripts/build_release.sh [out_dir]   (default: ./dist)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NAME="$(sed -n 's/^name:[[:space:]]*//p' "$ROOT/SKILL.md" | head -1)"
OUT="${1:-$ROOT/dist}"
STAGE="$(mktemp -d)"
mkdir -p "$STAGE/$NAME" "$OUT"
cp "$ROOT/SKILL.md" "$ROOT/VERSION" "$ROOT/LICENSE" "$ROOT/README.md" "$STAGE/$NAME/"
cp -R "$ROOT/references" "$ROOT/scripts" "$STAGE/$NAME/"
find "$STAGE/$NAME" -name '__pycache__' -prune -exec rm -rf {} + ; find "$STAGE/$NAME" -name '*.pyc' -delete
rm -f "$OUT/$NAME.zip"
(cd "$STAGE" && python3 -c "import shutil,sys; shutil.make_archive(sys.argv[1], 'zip', '.', sys.argv[2])" "$OUT/$NAME" "$NAME")
rm -rf "$STAGE"
echo "$OUT/$NAME.zip  (version $(cat "$ROOT/VERSION"))"
