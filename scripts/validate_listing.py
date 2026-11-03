#!/usr/bin/env python3
"""Validate a CyberAgents Exchange listing before a pull request is opened.

Two layers:
  1. The Exchange's OWN validator.py (loaded from your clone of
     tenable/cyberagents-exchange), so schema and vocabulary checks match CI.
     If its optional deps (python-frontmatter, rich, typer) cannot be installed
     in a locked-down sandbox, small shims stand in for them; pydantic and
     PyYAML are still required and are preinstalled in Claude's sandbox.
  2. The Tier 1 checklist items validator.py does not enforce: slug, directory,
     Tenable-set fields, template placeholders, plausible dates, domains present,
     a substantive body, github_url shape, EMU owners.

Usage:
    python3 validate_listing.py <exchange_clone_dir> <listing_path_inside_clone> [--full] [--json]
      --full   also run validator.py over every listing + CONTRIBUTING.md (needed
               whenever the PR edits validator.py vocabulary)
Exit code: 0 = ready, 1 = blocking problems, 2 = could not run.
"""
from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import io
import json
import re
import subprocess
import sys
import types
from pathlib import Path

TYPE_DIRS = {"agents": "Agent", "skills": "Skill", "mcp-servers": "MCPServer", "playbooks": "PlaybookAdapter"}
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*\.md$")
TENABLE_SET = ["partner_contribution", "vetted_on", "vetted_commit_sha", "last_reviewed"]
PLACEHOLDERS = [
    "your-github-username", "your-username", "your-repo", '"tag1"', '"tag2"', "Your Agent Name", "Your Skill Name",
    "Your MCP Server Name", "Your Playbook Name", "A one-line description of what", "Optional longer description",
    "Describe the skill's purpose", "Describe the agent's purpose", "Brief overview of the approach", "/your-command",
    "What this tool does", "What this agent does in the playbook", "What this agent does in the chain",
    "Your n8n Workflow Name", "Brief capabilities overview", "Describe what this n8n workflow does", "https://github.com/user/repo", "slug-of-exchange-listing",
]
FM_ONLY_PLACEHOLDERS = ['name: "example_tool"', 'name: "First Agent"', 'name: "Second Agent"', 'name: "Manual Step"', 'name: "tool_name"']
GH_URL = re.compile(r"^https://github\.com/(?P<owner>[A-Za-z0-9-_.]+)/(?P<repo>[A-Za-z0-9-_.]+?)(?:\.git)?(?:/tree/(?P<ref>[^/]+)(?:/(?P<sub>.+?))?)?/?$")


def install_shims() -> list[str]:
    """Stand-ins for validator.py's non-essential deps when they are not importable."""
    shimmed = []
    try:
        import frontmatter  # noqa: F401
    except ImportError:
        import yaml
        mod = types.ModuleType("frontmatter")

        class Post(dict):
            def __init__(self, meta, content):
                super().__init__(meta)
                self.content = content

        def load(fh):
            text = fh.read() if hasattr(fh, "read") else open(fh, encoding="utf-8").read()
            m = re.match(r"^---\s*\n(.*?)\n---\s*(?:\n|$)(.*)$", text, re.S)
            if not m:
                return Post({}, text)
            return Post(yaml.safe_load(m.group(1)) or {}, m.group(2))

        mod.load = load
        mod.loads = lambda s: load(io.StringIO(s))
        sys.modules["frontmatter"] = mod
        shimmed.append("frontmatter")
    try:
        import rich.console  # noqa: F401
    except ImportError:
        rich = types.ModuleType("rich")
        con = types.ModuleType("rich.console")

        class Console:
            def print(self, *a, **k):
                print(*(re.sub(r"\[/?[a-z ]+\]", "", str(x)) for x in a))

        con.Console = Console
        rich.console = con
        sys.modules["rich"], sys.modules["rich.console"] = rich, con
        shimmed.append("rich")
    try:
        import typer  # noqa: F401
    except ImportError:
        ty = types.ModuleType("typer")

        class Typer:
            def command(self, *a, **k):
                return lambda f: f

            def __call__(self):
                pass

        ty.Typer = Typer
        sys.modules["typer"] = ty
        shimmed.append("typer")
    return shimmed


def load_validator(exchange: Path):
    spec = importlib.util.spec_from_file_location("exchange_validator", exchange / "validator.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def split(text: str):
    import yaml
    m = re.match(r"^---\s*\n(.*?)\n---\s*(?:\n|$)(.*)$", text, re.S)
    if not m:
        return None, text
    return (yaml.safe_load(m.group(1)) or {}), m.group(2)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("exchange")
    ap.add_argument("listing")
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--repo-created", help="ISO date the linked repo was created (gh api repos/O/R --jq .created_at); "
                    "contribution_agreement_date may not predate it")
    a = ap.parse_args()
    exchange = Path(a.exchange).resolve()
    lp = Path(a.listing)
    listing = (exchange / lp) if not lp.is_absolute() else lp
    errors: list[str] = []
    warnings: list[str] = []
    passed: list[str] = []

    if not (exchange / "validator.py").is_file():
        print(f"{exchange} is not a clone of tenable/cyberagents-exchange (no validator.py)", file=sys.stderr)
        return 2
    if not listing.is_file():
        print(f"listing not found: {listing}", file=sys.stderr)
        return 2
    relp = listing.resolve().relative_to(exchange)
    tdir = relp.parts[0] if len(relp.parts) == 2 else None

    # -- placement
    if tdir not in TYPE_DIRS:
        errors.append(f"listing must sit directly in one of {', '.join(TYPE_DIRS)}/ (got {relp})")
    else:
        passed.append(f"placed in {tdir}/")
    if SLUG.match(listing.name):
        passed.append(f"filename {listing.name} is a valid slug")
    else:
        errors.append(f"filename {listing.name} is not a valid slug (lowercase letters, digits, single hyphens, .md)")
    base_ref = next((r for r in ("upstream/main", "origin/main") if subprocess.run(
        ["git", "-C", str(exchange), "rev-parse", "--verify", "-q", r], capture_output=True).returncode == 0), "origin/main")
    shown = subprocess.run(["git", "-C", str(exchange), "show", f"{base_ref}:{relp.as_posix()}"], capture_output=True, text=True)
    existed = shown.returncode == 0
    upstream_fm: dict = {}
    upstream_body = ""
    if existed:
        upstream_fm, upstream_body = split(shown.stdout)
        upstream_fm = upstream_fm or {}
        warnings.append(f"{relp} already exists upstream - this PR is an UPDATE, title it 'Update listing: <Name>'")
    others = [d for d in TYPE_DIRS if d != tdir and (exchange / d / listing.name).exists()]
    if others:
        errors.append(f"slug {listing.stem} already used in {', '.join(others)}/ - pick a distinct slug")

    # -- schema via the Exchange's own validator
    try:
        shims = install_shims()
        v = load_validator(exchange)
        schema = getattr(v, TYPE_DIRS.get(tdir, "Agent"))
        v.validate_markdown_frontmatter(listing, schema)
        passed.append("validator.py schema + controlled vocabularies" + (f" (shims: {', '.join(shims)})" if shims else ""))
    except ModuleNotFoundError as e:
        errors.append(f"could not run validator.py: missing module {e.name}. Try: pip install --break-system-packages pydantic pyyaml")
    except Exception as e:  # pydantic ValidationError and friends
        errors.append("validator.py rejected the frontmatter:\n      " + str(e).replace("\n", "\n      "))

    text = listing.read_text(encoding="utf-8")
    fm, body = split(text)
    if fm is None:
        errors.append("no YAML frontmatter block (--- ... ---) at the top of the file")
        fm = {}

    # -- unknown keys (validator.py ignores them silently; reviewers don't)
    try:
        known = set(schema.model_fields) if hasattr(schema, "model_fields") else set().union(
            *(m.model_fields for m in (v.StandardPlaybook, v.SponsoredPlaybook, v.N8nPlaybook)))
        unknown = sorted(set(fm) - known)
        if unknown:
            warnings.append("keys not in the schema (ignored by validator.py, likely removed in review): " + ", ".join(unknown))
    except Exception:
        pass

    # -- Tenable-set fields and tier. On an UPDATE, values already on the upstream listing must be kept as-is.
    for k in TENABLE_SET:
        if k in fm:
            if existed and k in upstream_fm and fm[k] == upstream_fm[k]:
                passed.append(f"`{k}` carried over unchanged from the live listing (Tenable-set; keep it)")
            elif existed and k in upstream_fm:
                errors.append(f"`{k}` differs from the live listing - Tenable sets it; restore the upstream value {upstream_fm[k]!r}")
            else:
                errors.append(f"`{k}` is set by Tenable during review - remove it from the submission")
        elif existed and k in upstream_fm:
            errors.append(f"`{k}` was removed - it is Tenable-set on the live listing; restore {upstream_fm[k]!r}")
    if existed and upstream_fm.get("tier") and fm.get("tier") == upstream_fm.get("tier"):
        passed.append(f"tier {fm.get('tier')!r} kept from the live listing")
    elif fm.get("tier") != "contributed":
        errors.append("tier must be \"contributed\" for every new submission (only Tenable promotes listings to vetted)")
    if existed and upstream_fm.get("tier") == "vetted":
        warnings.append("this is a VETTED listing: material changes to the linked repo may trigger re-review; "
                        "frontmatter edits keep tier/vetted_on/vetted_commit_sha exactly as they are")
    if fm.get("visibility") == "example":
        warnings.append("visibility: example hides the listing from browse/leaderboard/home - only keep it if intended")

    # -- dates
    today = dt.date.today()
    da = fm.get("date_added")
    if isinstance(da, dt.datetime):
        da = da.date()
    if isinstance(da, dt.date):
        if da == dt.date(2026, 1, 1):
            errors.append("date_added is the template default 2026-01-01")
        elif da > today + dt.timedelta(days=1) or da < dt.date(2024, 1, 1):
            errors.append(f"date_added {da} is not plausible")
        else:
            passed.append("date_added plausible")
    cad = fm.get("contribution_agreement_date")
    if cad is None:
        errors.append("contribution_agreement_date missing - record the UTC time the user accepted the agreement")
    else:
        c = cad if isinstance(cad, dt.datetime) else None
        if c is None:
            try:
                c = dt.datetime.fromisoformat(str(cad).replace("Z", "+00:00"))
            except ValueError:
                errors.append(f"contribution_agreement_date {cad!r} is not ISO 8601")
        if c is not None:
            cu = c if c.tzinfo else c.replace(tzinfo=dt.timezone.utc)
            if cu.date() == dt.date(2026, 1, 1) and cu.hour == 0 and cu.minute == 0:
                errors.append("contribution_agreement_date is the template default")
            elif cu > dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1):
                errors.append("contribution_agreement_date is in the future")
            else:
                passed.append("contribution_agreement_date valid")
            if a.repo_created:
                try:
                    rc = dt.datetime.fromisoformat(a.repo_created.replace("Z", "+00:00"))
                    rc = rc if rc.tzinfo else rc.replace(tzinfo=dt.timezone.utc)
                    if cu < rc:
                        errors.append(f"contribution_agreement_date {cu:%Y-%m-%dT%H:%M:%SZ} is before the repo was created ({rc:%Y-%m-%d})")
                except ValueError:
                    warnings.append(f"could not parse --repo-created {a.repo_created!r}")

    # -- domains
    doms = fm.get("domains")
    if not doms:
        errors.append("domains missing - pick 1-2 values from the closed taxonomy (first is primary)")
    else:
        passed.append(f"domains set (primary: {doms[0]})")

    # -- github_url / author
    m = GH_URL.match(str(fm.get("github_url", "")))
    if not m:
        errors.append("github_url must be https://github.com/<owner>/<repo> or .../tree/<branch>/<subfolder>")
    else:
        owner = m.group("owner")
        if "_" in owner:
            errors.append(f"github_url owner {owner} looks like an Enterprise Managed User (EMU) account - use a personal account")
        if str(fm.get("author", "")).lower() != owner.lower():
            warnings.append(f"author {fm.get('author')!r} differs from the repo owner {owner!r}; reviewers check they match")
        if m.group("sub"):
            passed.append(f"github_url points at subfolder {m.group('sub')} (multi-listing repo)")

    # -- placeholders and body
    fm_text = text[: len(text) - len(body)]
    hits = [p for p in PLACEHOLDERS if p in text] + [p for p in FM_ONLY_PLACEHOLDERS if p in fm_text]
    if hits:
        errors.append("template placeholders left in the file: " + ", ".join(hits))
    for heading in ("What it does", "How it works"):
        if not re.search(rf"(?im)^##\s+{heading}\s*$", body):
            if existed and not re.search(rf"(?im)^##\s+{heading}\s*$", upstream_body or ""):
                warnings.append(f"body has no '## {heading}' section (neither does the live listing; consider adding it)")
            else:
                errors.append(f"body is missing a '## {heading}' section")

    # -- playbook agents_used references
    for ag in fm.get("agents_used") or []:
        t, ref = (ag or {}).get("type"), (ag or {}).get("ref")
        if t == "exchange":
            if not ref or not any((exchange / d / f"{ref}.md").exists() for d in TYPE_DIRS):
                errors.append(f"agents_used {ag.get('name')!r}: exchange ref {ref!r} is not an existing listing slug")
        elif t == "github" and not GH_URL.match(str(ref or "")):
            errors.append(f"agents_used {ag.get('name')!r}: github ref {ref!r} is not a GitHub repo URL")
        elif t == "vendor" and fm.get("playbook_type") != "sponsored":
            errors.append(f"agents_used {ag.get('name')!r}: vendor-type agents are only allowed in sponsored playbooks")
    words = len(re.findall(r"\w+", body))
    if words < 80:
        errors.append(f"body is only {words} words - reviewers reject stub bodies")
    else:
        passed.append(f"body has substance ({words} words)")
    desc = str(fm.get("description", ""))
    if len(desc) > 300:
        warnings.append(f"description is {len(desc)} characters; aim for one concise line")

    # -- full-repo validation (vocabulary edits, CONTRIBUTING.md consistency)
    if a.full:
        r = subprocess.run([sys.executable, "-I", "-c",
                            "import sys; sys.path.insert(0, %r); import validate_listing as vl; vl.install_shims(); "
                            "v = vl.load_validator(__import__('pathlib').Path(%r)); v.validate(__import__('pathlib').Path(%r))"
                            % (str(Path(__file__).parent), str(exchange), str(exchange))],
                           capture_output=True, text=True)
        bad = [ln for ln in r.stdout.splitlines() if "✘" in ln or "Issues Identified" in ln]
        if r.returncode != 0 or bad:
            errors.append("full validator run failed:\n      " + "\n      ".join(bad or r.stderr.splitlines()[-5:]))
        else:
            passed.append("full validator.py run over every listing + CONTRIBUTING.md")

    result = {"listing": relp.as_posix(), "ready": not errors, "errors": errors, "warnings": warnings, "passed": passed}
    if a.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Listing: {relp.as_posix()}")
        for p in passed:
            print(f"  ✔ {p}")
        for w in warnings:
            print(f"  ! {w}")
        for e in errors:
            print(f"  ✘ {e}")
        print("READY for a pull request" if not errors else f"NOT READY - {len(errors)} blocking problem(s)")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
