#!/usr/bin/env python3
"""Readiness check for an Exchange submission in a Claude Desktop / Cowork sandbox.

Probes what the sandbox shell can actually do, so the skill picks a working
route instead of discovering a blocked one halfway through a submission:
  - git present, and whether github.com is reachable for clone/fetch/push
  - whether api.github.com (REST API used by `gh`) is reachable
  - whether the gh CLI is authenticated (and whether a stale GH_TOKEN is the cause)
  - python packages the Exchange validator needs
  - secret scanners available
It cannot see connector or device-bridge tools; Claude checks those from its tool list.

Usage: python3 env_check.py [--json]
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys


def run(cmd, env=None, timeout=25):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
        return r.returncode, (r.stdout + r.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as e:
        return 99, str(e)


def http_status(url: str) -> str:
    code, out = run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", "15", url])
    return out if code == 0 else f"unreachable ({out[:80]})"


def main() -> int:
    r: dict = {}
    r["git"] = bool(shutil.which("git"))
    code, out = run(["git", "ls-remote", "https://github.com/tenable/cyberagents-exchange.git", "HEAD"])
    r["github_git_read"] = code == 0
    r["api_github_status"] = http_status("https://api.github.com/repos/tenable/cyberagents-exchange")
    r["raw_githubusercontent_status"] = http_status("https://raw.githubusercontent.com/tenable/cyberagents-exchange/main/README.md")

    r["gh_installed"] = bool(shutil.which("gh"))
    if r["gh_installed"]:
        code, out = run(["gh", "api", "user", "--jq", ".login"])
        r["gh_user"] = out if code == 0 else None
        r["gh_error"] = None if code == 0 else out.splitlines()[-1][:160] if out else "failed"
        stale = None
        if code != 0 and (os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")):
            env = {k: v for k, v in os.environ.items() if k not in ("GH_TOKEN", "GITHUB_TOKEN")}
            c2, o2 = run(["gh", "api", "user", "--jq", ".login"], env=env)
            stale = {"env_token_present": True, "works_without_env_token": c2 == 0, "user_without_env_token": o2 if c2 == 0 else None}
        r["gh_env_token"] = stale
        r["gh_graphql"] = None
        if r["gh_user"] or (stale and stale.get("works_without_env_token")):
            env = None if r["gh_user"] else {k: v for k, v in os.environ.items() if k not in ("GH_TOKEN", "GITHUB_TOKEN")}
            c3, o3 = run(["gh", "api", "graphql", "-f", "query={viewer{login}}"], env=env)
            r["gh_graphql"] = c3 == 0
            r["gh_graphql_error"] = None if c3 == 0 else (o3.splitlines() or ["failed"])[0][:160]
            # Does the gateway restrict API calls to attached repos? Probe an account-scoped endpoint (read-only).
            c4, o4 = run(["gh", "api", "user/repos?per_page=1", "--jq", "length"], env=env)
            r["gh_account_scoped_api"] = c4 == 0
            r["gh_account_scoped_error"] = None if c4 == 0 else (o4.splitlines() or ["failed"])[0][:160]
    r["python"] = sys.version.split()[0]
    r["python_modules"] = {m: importlib.util.find_spec(m) is not None for m in ("pydantic", "yaml", "frontmatter")}
    r["secret_scanners"] = [t for t in ("gitleaks", "trufflehog") if shutil.which(t)]
    code, out = run(["git", "config", "--global", "user.email"])
    r["sandbox_git_email"] = out if code == 0 and out else None  # the SANDBOX identity, not the person's

    # Route recommendation
    gh_ok = bool(r.get("gh_user")) or bool((r.get("gh_env_token") or {}).get("works_without_env_token"))
    prefix = "" if r.get("gh_user") else "unset-GH_TOKEN + "
    if gh_ok and r.get("gh_graphql") and r.get("gh_account_scoped_api"):
        route = prefix + "cli"  # full gh CLI route
    elif gh_ok:
        route = prefix + "rest"  # session gateway: REST only, repo-scoped; attach repos first
    elif r["github_git_read"]:
        route = "link-github-then-rest"  # needs GitHub linked to Claude, or the web-UI fallback
    else:
        route = "browser-only"
    r["recommended_route"] = route

    if "--json" in sys.argv:
        print(json.dumps(r, indent=2))
        return 0
    yes = lambda b: "yes" if b else "NO"  # noqa: E731
    print(f"git installed ............... {yes(r['git'])}")
    print(f"github.com git clone/fetch .. {yes(r['github_git_read'])}")
    print(f"api.github.com (no auth) .... HTTP {r['api_github_status']}")
    print(f"raw.githubusercontent.com ... HTTP {r['raw_githubusercontent_status']}")
    print(f"gh CLI ...................... {('authenticated as ' + r['gh_user']) if r.get('gh_user') else ('installed, NOT authenticated: ' + str(r.get('gh_error'))) if r['gh_installed'] else 'not installed'}")
    if r.get("gh_graphql") is not None:
        print(f"  GraphQL ................... {'yes' if r['gh_graphql'] else 'NO - use REST forms (gh api ...): ' + str(r.get('gh_graphql_error'))}")
        print(f"  account-wide API calls .... {'yes' if r['gh_account_scoped_api'] else 'NO - repo-scoped only; attach repos, person creates new repos/forks in the browser if refused'}")
    if r.get("gh_env_token"):
        print(f"  stale GH_TOKEN in env ..... works without it: {yes(r['gh_env_token']['works_without_env_token'])}")
    print(f"python {r['python']} modules ...... " + ", ".join(f"{k}={'ok' if v else 'missing'}" for k, v in r["python_modules"].items()))
    print(f"secret scanners ............. {', '.join(r['secret_scanners']) or 'none (built-in scanner will be used)'}")
    print(f"sandbox git identity ........ {r['sandbox_git_email'] or 'not set'} (not the person's - commit as their GitHub identity)")
    print(f"RECOMMENDED ROUTE ........... {route}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
