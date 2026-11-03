#!/usr/bin/env bash
# Thin wrapper kept for compatibility: builds dist/<skill-name>.zip reproducibly.
# Pass --check to verify the committed zip matches the sources instead.
exec python3 "$(cd "$(dirname "$0")" && pwd)/build_release.py" "$@"
