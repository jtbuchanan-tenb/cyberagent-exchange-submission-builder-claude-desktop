#!/usr/bin/env python3
"""Credential scan of a git repository: working tree AND full reachable history.

Uses gitleaks or trufflehog when one is installed (the Exchange's own review runs
gitleaks across full history, so that is the closest match). When neither can be
installed - common in locked-down Claude Desktop / Cowork sandboxes - it falls
back to a built-in, standard-library pattern scanner.

Matched values are ALWAYS redacted. The report names the location and the kind of
credential, never the secret.

Usage:
    python3 secret_scan.py <repo_dir> [--max-commits N] [--json]
Exit code: 0 = no findings, 1 = findings, 2 = error.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

RULES: list[tuple[str, re.Pattern]] = [
    ("AWS access key id", re.compile(r"\b(?:AKIA|ASIA|ABIA|ACCA)[0-9A-Z]{16}\b")),
    ("AWS secret access key", re.compile(r"(?i)aws.{0,20}(?:secret|private).{0,20}[:=]\s*['\"]?[A-Za-z0-9/+=]{40}\b")),
    ("GitHub token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{22,})\b")),
    ("GitLab token", re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}\b")),
    ("Slack token", re.compile(r"\bxox[abposr]-[A-Za-z0-9-]{10,}\b")),
    ("Slack webhook", re.compile(r"https://hooks\.slack\.com/services/T[A-Za-z0-9_]+/B[A-Za-z0-9_]+/[A-Za-z0-9_]+")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("Google OAuth client secret", re.compile(r"\bGOCSPX-[A-Za-z0-9_-]{28}\b")),
    ("Anthropic API key", re.compile(r"\bsk-ant-(?:api|admin)\d{2}-[A-Za-z0-9_-]{80,}\b")),
    ("OpenAI API key", re.compile(r"\bsk-(?:proj-|svcacct-|admin-)?[A-Za-z0-9_-]{20,}T3BlbkFJ[A-Za-z0-9_-]{20,}\b|\bsk-[A-Za-z0-9]{48}\b")),
    ("Stripe secret key", re.compile(r"\b(?:sk|rk)_live_[A-Za-z0-9]{24,}\b")),
    ("Twilio API key", re.compile(r"\bSK[0-9a-fA-F]{32}\b")),
    ("SendGrid API key", re.compile(r"\bSG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}\b")),
    ("npm token", re.compile(r"\bnpm_[A-Za-z0-9]{36}\b")),
    ("PyPI token", re.compile(r"\bpypi-AgEIcHlwaS5vcmc[A-Za-z0-9_-]{50,}\b")),
    ("Azure storage key", re.compile(r"(?i)AccountKey=[A-Za-z0-9+/=]{80,}")),
    ("Private key block", re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP |ENCRYPTED )?PRIVATE KEY(?: BLOCK)?-----")),
    ("JSON web token", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")),
    ("Tenable API key", re.compile(r"(?i)(?:access|secret)[_-]?key\s*[=:]\s*['\"]?[0-9a-f]{64}\b")),
    ("Tenable API key header", re.compile(r"(?i)accessKey=[0-9a-f]{64};\s*secretKey=[0-9a-f]{64}")),
    ("Generic credential assignment", re.compile(
        r"(?i)\b(?:api[_-]?key|api[_-]?secret|auth[_-]?token|access[_-]?token|secret[_-]?key|client[_-]?secret|private[_-]?key|password|passwd)\b"
        r"\s*[:=]\s*['\"]([A-Za-z0-9+/=_\-!@#$%^&*.]{16,})['\"]")),
]
PLACEHOLDER = re.compile(r"(?i)(x{6,}|your[_-]|example|placeholder|changeme|dummy|redacted|<[^>]+>|\$\{|\{\{|process\.env|os\.environ|getenv|0{16,}|1234567890|abcdef(?:ghij)?)")
SECRET_FILENAME = re.compile(
    r"(?i)(^|/)(\.env(\.[^/]*)?|\.envrc|credentials\.json|service[-_]account[^/]*\.json|id_rsa|id_dsa|id_ecdsa|id_ed25519|"
    r"[^/]*\.(pem|p12|pfx|jks|keystore|ppk|key)|(?:[^/]*[-_.])?secrets?\.(ya?ml|json|toml|ini)|\.npmrc|\.pypirc|\.netrc|\.git-credentials)$")
ALLOWED_FILENAME = re.compile(r"(?i)\.env\.(example|sample|template|dist)$|example|sample|test[s]?/fixtures")
LOW_CONF_PATH = re.compile(r"(?i)(^|/)(tests?|spec|fixtures?|docs?|examples?)/|\.(md|rst|txt)$|_test\.|test_")
LOW_CONF_VALUE = re.compile(r"(?i)^(test|fake|mock|sample|dummy|hardcoded|secret|password)")
BINARY_EXT = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".gz", ".tgz", ".woff", ".woff2", ".ttf", ".mp4", ".mov", ".lock", ".svg"}


def run(cmd, cwd, timeout=600):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, errors="replace", timeout=timeout)


KNOWN_PREFIX = re.compile(r"^(AKIA|ASIA|ABIA|ACCA|gh[pousr]_|github_pat_|glpat-|xox[abposr]-|AIza|GOCSPX-|sk-ant-|sk-|sk_live_|rk_live_|SG\.|npm_|pypi-|eyJ|-----BEGIN)")


def redact(v: str) -> str:
    """Show only a well-known, non-secret format prefix (e.g. 'ghp_'), never characters of the secret itself."""
    m = KNOWN_PREFIX.match(v)
    return (m.group(1) + "…" if m else "") + f"[{len(v)} chars redacted]"


def low_conf(kind: str, path: str, raw_value: str) -> bool:
    return kind == "Generic credential assignment" and bool(LOW_CONF_PATH.search(path) or LOW_CONF_VALUE.search(raw_value))


def scan_text(text: str):
    for kind, pat in RULES:
        for m in pat.finditer(text):
            val = m.group(1) if (m.lastindex and kind == "Generic credential assignment") else m.group(0)
            line_start = text.rfind("\n", 0, m.start()) + 1
            line_end = text.find("\n", m.end())
            line = text[line_start: line_end if line_end != -1 else len(text)]
            if PLACEHOLDER.search(val) or (kind == "Generic credential assignment" and PLACEHOLDER.search(line)):
                continue
            if kind == "Generic credential assignment" and len(set(val)) < 6:
                continue
            yield kind, val, text.count("\n", 0, m.start()) + 1


def builtin_scan(repo: Path, max_commits: int | None):
    findings = {"tree": [], "history": [], "filenames": []}
    # Working tree (tracked + untracked-but-not-ignored files)
    ls = run(["git", "ls-files", "-co", "--exclude-standard"], repo)
    files = [f for f in ls.stdout.splitlines() if f]
    for f in files:
        p = repo / f
        if p.suffix.lower() in BINARY_EXT or not p.is_file():
            continue
        try:
            if p.stat().st_size > 2_000_000:
                continue
            t = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for kind, val, ln in scan_text(t):
            findings["tree"].append({"file": f, "line": ln, "kind": kind, "value": redact(val), "low_confidence": low_conf(kind, f, val)})
        if SECRET_FILENAME.search(f) and not ALLOWED_FILENAME.search(f):
            findings["filenames"].append({"file": f, "where": "working tree", "kind": "secret-bearing filename"})

    # Every filename that ever existed in reachable history
    objs = run(["git", "rev-list", "--all", "--objects"], repo)
    current = set(files)
    for line in objs.stdout.splitlines():
        parts = line.split(" ", 1)
        if len(parts) == 2 and SECRET_FILENAME.search(parts[1]) and not ALLOWED_FILENAME.search(parts[1]) and parts[1] not in current:
            findings["filenames"].append({"file": parts[1], "where": "history only", "kind": "secret-bearing filename"})

    # Full-history patch scan
    total = int((run(["git", "rev-list", "--all", "--count"], repo).stdout or "0").strip() or 0)
    cmd = ["git", "log", "--all", "--full-history", "-p", "--no-color", "--format=__COMMIT__ %h"]
    if max_commits:
        cmd.insert(2, f"-n{max_commits}")
    proc = subprocess.Popen(cmd, cwd=repo, stdout=subprocess.PIPE, text=True, errors="replace")
    commit, cur_file, seen = "?", "?", set()
    tree_keys = {(x["file"], x["kind"]) for x in findings["tree"]}
    for raw in proc.stdout:
        if raw.startswith("__COMMIT__ "):
            commit = raw.split()[1]
            continue
        if raw.startswith("+++ b/"):
            cur_file = raw[6:].strip()
            continue
        if not raw.startswith("+") or raw.startswith("+++"):
            continue
        if Path(cur_file).suffix.lower() in BINARY_EXT:
            continue
        for kind, val, _ in scan_text(raw[1:]):
            key = (cur_file, kind, val)
            if key in seen:
                continue
            seen.add(key)
            findings["history"].append({"commit": commit, "file": cur_file, "kind": kind, "value": redact(val),
                                        "also_in_tree": (cur_file, kind) in tree_keys, "low_confidence": low_conf(kind, cur_file, val)})
    proc.wait()
    scanned = min(total, max_commits) if max_commits else total
    return findings, {"scanner": "built-in pattern scan (stdlib)", "commits_total": total, "commits_scanned": scanned,
                      "partial": bool(max_commits and total > max_commits),
                      "not_covered": ["binary files", "Git LFS objects", "submodule contents", "files > 2 MB",
                                      "credential formats outside the built-in rule set"]}


def tool_scan(repo: Path):
    if shutil.which("gitleaks"):
        r = run(["gitleaks", "detect", "--source", str(repo), "--redact", "--no-banner", "--exit-code", "0",
                 "--report-format", "json", "--report-path", "/dev/stdout"], repo, timeout=1800)
        try:
            data = json.loads(r.stdout or "[]")
        except json.JSONDecodeError:
            return None
        total = int((run(["git", "rev-list", "--all", "--count"], repo).stdout or "0").strip() or 0)
        hist = [{"commit": d.get("Commit", "")[:8], "file": d.get("File"), "line": d.get("StartLine"),
                 "kind": d.get("Description") or d.get("RuleID"), "value": "[redacted by gitleaks]"} for d in data]
        return {"tree": [], "history": hist, "filenames": []}, {"scanner": "gitleaks (full history)",
                                                                 "commits_total": total, "commits_scanned": total,
                                                                 "partial": False, "not_covered": ["submodule contents"]}
    if shutil.which("trufflehog"):
        r = run(["trufflehog", "git", f"file://{repo}", "--no-update", "--json", "--results=verified,unknown"], repo, timeout=1800)
        hist = []
        for line in r.stdout.splitlines():
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            g = d.get("SourceMetadata", {}).get("Data", {}).get("Git", {})
            hist.append({"commit": g.get("commit", "")[:8], "file": g.get("file"), "line": g.get("line"),
                         "kind": d.get("DetectorName"), "value": "[redacted]", "verified": d.get("Verified")})
        return {"tree": [], "history": hist, "filenames": []}, {"scanner": "trufflehog (full history)", "partial": False,
                                                                 "not_covered": ["submodule contents"]}
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--max-commits", type=int, default=None)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--builtin", action="store_true", help="force the built-in scanner")
    a = ap.parse_args()
    repo = Path(a.repo).resolve()
    if run(["git", "rev-parse", "--git-dir"], repo).returncode != 0:
        print("not a git repository (a full clone with history is required)", file=sys.stderr)
        return 2
    if run(["git", "rev-parse", "--is-shallow-repository"], repo).stdout.strip() == "true":
        print("WARNING: shallow clone - history is incomplete. Run `git fetch --unshallow` (and `git fetch --all`) first.", file=sys.stderr)
    res = None if a.builtin else tool_scan(repo)
    findings, meta = res if res else builtin_scan(repo, a.max_commits)
    n = sum(len(v) for v in findings.values())
    if a.json:
        print(json.dumps({"meta": meta, "findings": findings, "count": n}, indent=2))
    else:
        print(f"Scanner: {meta['scanner']}")
        if "commits_total" in meta:
            print(f"Coverage: working tree + {meta['commits_scanned']} of {meta['commits_total']} commits (all branches and tags)"
                  + ("  ** PARTIAL **" if meta.get("partial") else ""))
        print(f"Not covered: {', '.join(meta['not_covered'])}")
        if not n:
            print("Findings: none")
        for section, title in (("tree", "In current files"), ("history", "In git history"), ("filenames", "Secret-bearing filenames")):
            if findings[section]:
                print(f"\n{title}:")
                for f in findings[section]:
                    loc = f"commit {f['commit']} " if "commit" in f else ""
                    ln = f":{f['line']}" if f.get("line") else ""
                    extra = " (also still in current tree)" if f.get("also_in_tree") else ""
                    extra += f" ({f['where']})" if f.get("where") else ""
                    extra += "  [low confidence: test/docs path or test-like value - confirm with the user]" if f.get("low_confidence") else ""
                    print(f"  - {loc}{f['file']}{ln} — {f['kind']} {f.get('value', '')}{extra}")
    return 1 if n else 0


if __name__ == "__main__":
    sys.exit(main())
