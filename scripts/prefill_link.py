#!/usr/bin/env python3
"""Build pre-filled GitHub links for steps the person does in their own browser.

Every value GitHub accepts in the URL is filled in, so the person only checks and clicks.

Usage:
  prefill_link.py new-repo  --name N [--public] [--description D]
  prefill_link.py fork
  prefill_link.py new-file  --owner ME --branch main --dir skills --filename slug.md [--content-file F]
  prefill_link.py new-file  --repo OWNER/REPO --branch main --dir .github/workflows --filename x.yml [--content-file F]
  prefill_link.py pr        --owner ME --branch add-slug --title T [--body-file F]
  prefill_link.py license   --owner O --repo R [--branch main] [--template mit]

GitHub caps URL length (roughly 8 KB in practice). When a pre-filled value would
exceed that, the link is printed without it and a note says to paste it instead.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import quote, urlencode

MAX_URL = 8000
EXCHANGE = "tenable/cyberagents-exchange"


def emit(base: str, params: dict, big: dict | None = None) -> None:
    url = base + ("?" + urlencode(params, quote_via=quote) if params else "")
    dropped = []
    for k, v in (big or {}).items():
        trial = url + ("&" if "?" in url else "?") + urlencode({k: v}, quote_via=quote)
        if len(trial) <= MAX_URL:
            url = trial
        else:
            dropped.append(k)
    print(url)
    for k in dropped:
        print(f"NOTE: `{k}` was too long to pre-fill - give the person that text to paste.", file=sys.stderr)


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("new-repo"); s.add_argument("--name", required=True); s.add_argument("--public", action="store_true"); s.add_argument("--description", default="")
    sub.add_parser("fork")
    s = sub.add_parser("new-file"); s.add_argument("--owner"); s.add_argument("--repo", help="OWNER/REPO (default: OWNER/cyberagents-exchange)"); s.add_argument("--branch", default="main"); s.add_argument("--dir", required=True); s.add_argument("--filename", required=True); s.add_argument("--content-file")
    s = sub.add_parser("pr"); s.add_argument("--owner", required=True); s.add_argument("--branch", required=True); s.add_argument("--title", required=True); s.add_argument("--body-file")
    s = sub.add_parser("license"); s.add_argument("--owner", required=True); s.add_argument("--repo", required=True); s.add_argument("--branch", default="main"); s.add_argument("--template", default="mit")
    a = ap.parse_args()

    if a.cmd == "new-repo":
        p = {"name": a.name, "visibility": "public" if a.public else "private"}
        if a.description:
            p["description"] = a.description
        emit("https://github.com/new", p)
    elif a.cmd == "fork":
        emit(f"https://github.com/{EXCHANGE}/fork", {})
    elif a.cmd == "new-file":
        big = {"value": Path(a.content_file).read_text(encoding="utf-8")} if a.content_file else None
        repo = a.repo or (f"{a.owner}/cyberagents-exchange" if a.owner else None)
        if not repo:
            ap.error("new-file needs --owner (for the Exchange fork) or --repo OWNER/REPO")
        emit(f"https://github.com/{repo}/new/{a.branch}/{a.dir.strip('/')}", {"filename": a.filename}, big)
    elif a.cmd == "pr":
        big = {"body": Path(a.body_file).read_text(encoding="utf-8")} if a.body_file else None
        emit(f"https://github.com/{EXCHANGE}/compare/main...{a.owner}:cyberagents-exchange:{a.branch}",
             {"expand": "1", "title": a.title}, big)
    elif a.cmd == "license":
        emit(f"https://github.com/{a.owner}/{a.repo}/community/license/new", {"branch": a.branch, "template": a.template})
    return 0


if __name__ == "__main__":
    sys.exit(main())
