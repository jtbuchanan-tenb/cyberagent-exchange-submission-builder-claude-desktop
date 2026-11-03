#!/usr/bin/env python3
"""Inventory the listable components in a repository for the CyberAgents Exchange.

Standard library only, so it runs in locked-down sandboxes. It walks a cloned
repository and reports every component that could become its own Exchange
listing: skills (or skill bundles), MCP servers, n8n workflows, Claude Code
subagents, and other standalone code projects that might be agents.

The output is a starting point for Claude, not a verdict. Every finding comes
with the signals that produced it so the user can confirm or correct it.

Usage:
    python3 detect_components.py <repo_dir> [--json]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

SKIP_DIRS = {
    ".git", "node_modules", ".venv", "venv", "env", "__pycache__", "dist", "build",
    ".next", ".tox", ".mypy_cache", ".pytest_cache", "target", "vendor", ".idea",
    ".vscode", "site-packages", "coverage", ".cache",
}
CODE_EXT = {".py", ".ts", ".js", ".mjs", ".cjs", ".go", ".rs", ".tsx"}
MANIFESTS = {
    "package.json": "node", "tsconfig.json": "node", "bun.lockb": "bun", "bunfig.toml": "bun",
    "pyproject.toml": "python", "setup.py": "python", "requirements.txt": "python",
    "Pipfile": "python", "Cargo.toml": "rust", "go.mod": "go",
}
MAX_FILE_BYTES = 600_000

PLATFORM_SIGNALS = [
    # (relative glob-ish check, platform)
    ("SKILL.md", "Claude Code"),
    (".cursorrules", "Cursor"),
    (".cursor/rules", "Cursor"),
    (".github/copilot-instructions.md", "GitHub Copilot"),
    (".github/skills", "GitHub Copilot"),
    (".windsurfrules", "Windsurf"),
    (".windsurf/skills", "Windsurf"),
    ("GEMINI.md", "Gemini CLI"),
    (".gemini", "Gemini CLI"),
    ("AGENTS.md", "Codex"),
    ("codex.json", "Codex"),
    (".clinerules", "Cline"),
    (".cline", "Cline"),
]


def walk_files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for f in filenames:
            yield Path(dirpath) / f


def read_text(p: Path) -> str:
    try:
        if p.stat().st_size > MAX_FILE_BYTES:
            return ""
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def rel(root: Path, p: Path) -> str:
    r = str(p.relative_to(root)) if p != root else "."
    return r.replace(os.sep, "/")


def readme_in(d: Path) -> str | None:
    for name in ("README.md", "readme.md", "Readme.md", "README.MD", "README.rst", "README.txt", "README"):
        if (d / name).is_file():
            return name
    return None


def license_in(d: Path) -> str | None:
    for p in sorted(d.iterdir()) if d.is_dir() else []:
        if p.is_file() and re.match(r"(?i)^(license|licence|copying)(\.|$)", p.name):
            return p.name
    return None


def readme_title(d: Path) -> str | None:
    name = readme_in(d)
    if not name:
        return None
    for line in read_text(d / name).splitlines():
        m = re.match(r"^#\s+(.+?)\s*#*\s*$", line)
        if m:
            return re.sub(r"\[!\[.*", "", m.group(1)).strip() or None
    return None


def parse_frontmatter(text: str) -> dict:
    m = re.match(r"^---\s*\n(.*?)\n---\s*(\n|$)", text, re.S)
    if not m:
        return {}
    out = {}
    for line in m.group(1).splitlines():
        mm = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if mm:
            out[mm.group(1)] = mm.group(2).strip().strip('"').strip("'")
    return out


def platform_signals(d: Path) -> list[str]:
    found = []
    for relpath, plat in PLATFORM_SIGNALS:
        if (d / relpath).exists() and plat not in found:
            found.append(plat)
    return found


# ---------------------------------------------------------------- MCP servers

MCP_DEP_PAT = re.compile(r'"@modelcontextprotocol/sdk"|\bfastmcp\b|^\s*"?mcp(\[[^\]]*\])?\s*[<>=~"]|"mcp(\[[^\]]*\])?[<>=~]|mark3labs/mcp-go|modelcontextprotocol/go-sdk|\brmcp\b', re.M | re.I)
MCP_CODE_PAT = re.compile(r"StdioServerTransport|StreamableHTTPServerTransport|SSEServerTransport|FastMCP\(|from mcp\.server|mcp\.server\.|McpServer\(|Model Context Protocol|['\"]tools/list['\"]|server\.NewMCPServer|mcp\.NewServer", re.I)

TOOL_PATTERNS = [
    # TS/JS SDK: server.tool("name", "desc", ...) / server.registerTool("name", {description})
    re.compile(r"\.(?:tool|registerTool)\(\s*['\"`]([A-Za-z0-9_.:-]+)['\"`]\s*,\s*(?:\{[^}]*?description\s*:\s*)?['\"`]([^'\"`]{3,300})", re.S),
    # Go mcp-go: mcp.NewTool("name", mcp.WithDescription("desc"))
    re.compile(r"NewTool\(\s*\"([A-Za-z0-9_.:-]+)\"\s*,\s*mcp\.WithDescription\(\s*\"([^\"]{3,300})\"", re.S),
    # Python low-level: Tool(name="x", description="y")
    re.compile(r"\bTool\(\s*name\s*=\s*['\"]([A-Za-z0-9_.:-]+)['\"]\s*,\s*description\s*=\s*['\"]([^'\"]{3,300})", re.S),
]
# Python decorators: @mcp.tool() / @server.tool(name="x") then def fn(...): """doc"""
PY_DECORATOR = re.compile(r"@\w+(?:\.\w+)*\.tool\((?P<args>[^)]*)\)\s*\n(?:\s*@[^\n]+\n)*\s*(?:async\s+)?def\s+(?P<fn>\w+)\s*\([^)]*\)[^:]*:\s*(?:\n\s*(?P<q>\"\"\"|''')(?P<doc>.*?)(?P=q))?", re.S)
# FastMCP functional registration: app.tool(description=X)(fn)
PY_FUNCTIONAL = re.compile(r"\.tool\([^)]*\)\(\s*(\w+)\s*\)")
# Raw JSON-RPC servers: { name: 'x', description: '...', inputSchema: ... }
RAW_TOOL = re.compile(r"name\s*:\s*(['\"])([a-z][a-z0-9_]{2,60})\1\s*,\s*(?:title\s*:[^\n]*\n\s*)?description\s*:\s*(['\"`])(.*?)(?<!\\)\3", re.S)
# Python module-level string constants, used as tool descriptions (description=SOME_CONSTANT)
PY_CONST = re.compile(r"^([A-Z][A-Z0-9_]{2,})\s*(?::\s*[\w\[\]. ]+)?=\s*(?:(?:textwrap\.)?dedent\s*)?\(?\s*[rbuf]*(\"\"\"|'''|\"|')(.*?)(?<!\\)\2", re.S | re.M)


def short(desc: str) -> str:
    """First sentence, whitespace collapsed, capped: listings want one line per tool."""
    d = re.sub(r"\s+", " ", desc or "").strip()
    m = re.match(r"(.{20,200}?[.!?])(\s|$)", d)
    return (m.group(1) if m else d[:200]).strip()

RESOURCE_PAT = re.compile(r"\.(?:resource|registerResource)\(\s*['\"`]([^'\"`]+)['\"`]|@\w+(?:\.\w+)*\.resource\(\s*['\"]([^'\"]+)['\"]")
PROMPT_PAT = re.compile(r"\.(?:prompt|registerPrompt)\(\s*['\"`]([A-Za-z0-9_.:-]+)['\"`]|@\w+(?:\.\w+)*\.prompt\((?:[^)]*name\s*=\s*['\"]([^'\"]+)['\"])?[^)]*\)\s*\n\s*(?:async\s+)?def\s+(\w+)")

STDIO_PAT = re.compile(r"StdioServerTransport|stdio_server|transport\s*=\s*['\"]stdio['\"]|\.run\(\s*\)|ServeStdio|over stdio|stdin", re.I)
HTTP_PAT = re.compile(r"StreamableHTTPServerTransport|SSEServerTransport|streamable[-_]?http|transport\s*=\s*['\"](?:http|sse|streamable-http)['\"]|NewStreamableHTTPServer|NewSSEServer|sse_app|streamable_http_app", re.I)
OAUTH_PAT = re.compile(r"oauth|/authorize\b|refresh_token", re.I)
BEARER_PAT = re.compile(r"Authorization['\"]?\s*[:=].{0,40}Bearer|bearer[_ ]?token|verify_token|auth_token", re.I)


def first_line(s: str | None) -> str:
    if not s:
        return ""
    for line in s.strip().splitlines():
        if line.strip():
            return line.strip()[:200]
    return ""


def analyse_mcp(d: Path) -> dict:
    tools: dict[str, str] = {}
    resources: list[str] = []
    prompts: list[str] = []
    stdio = http = oauth = bearer = False
    consts: dict[str, str] = {}
    pending_const: dict[str, str] = {}
    files = [p for p in walk_files(d) if p.suffix in CODE_EXT and "test" not in p.name.lower()]
    for p in files:
        t = read_text(p)
        if not t:
            continue
        for pat in TOOL_PATTERNS:
            for m in pat.finditer(t):
                tools.setdefault(m.group(1), short(m.group(2)))
        if p.suffix == ".py":
            consts.update({m.group(1): m.group(3) for m in PY_CONST.finditer(t)})
            for m in PY_DECORATOR.finditer(t):
                nm = re.search(r"name\s*=\s*['\"]([^'\"]+)['\"]", m.group("args") or "")
                desc = re.search(r"description\s*=\s*['\"]([^'\"]+)['\"]", m.group("args") or "")
                tools.setdefault(nm.group(1) if nm else m.group("fn"), (desc.group(1) if desc else first_line(m.group("doc"))))
            for m in re.finditer(r"\.tool\(([^)]*)\)\(\s*(\w+)\s*\)", t):
                dm = re.search(r"description\s*=\s*(?:['\"]([^'\"]+)['\"]|([A-Z][A-Z0-9_]+))", m.group(1))
                if dm and dm.group(2):
                    pending_const[m.group(2)] = dm.group(2)
                tools.setdefault(m.group(2), short(dm.group(1)) if dm and dm.group(1) else "")
        for m in RAW_TOOL.finditer(t):
            if re.search(r"input_?[sS]chema|parameters\s*:|handler\s*:", t[m.end(): m.end() + 4000]):
                tools.setdefault(m.group(2), short(m.group(4)))
        for m in RESOURCE_PAT.finditer(t):
            v = m.group(1) or m.group(2)
            if v and v not in resources:
                resources.append(v)
        for m in PROMPT_PAT.finditer(t):
            v = m.group(1) or m.group(2) or m.group(3)
            if v and v not in prompts:
                prompts.append(v)
        stdio = stdio or bool(STDIO_PAT.search(t))
        http = http or bool(HTTP_PAT.search(t))
        oauth = oauth or bool(OAUTH_PAT.search(t))
        bearer = bearer or bool(BEARER_PAT.search(t))
    for fn, const in pending_const.items():
        if not tools.get(fn) and const in consts:
            tools[fn] = short(consts[const])
    runtime = None
    for name, rt in MANIFESTS.items():
        if (d / name).exists():
            runtime = rt if not (rt == "node" and (d / "bun.lockb").exists()) else "bun"
            break
    transport = "both" if (stdio and http) else "http" if http else "stdio" if stdio else None
    auth_hint = "oauth2" if oauth else "token" if bearer else None
    readme = read_text(d / readme_in(d)) if readme_in(d) else ""
    clients = [c for c in ("Claude Desktop", "Claude Code", "Cursor", "Windsurf", "Cline", "Codex", "Continue",
                           "Gemini CLI", "VS Code Copilot", "ChatGPT", "Antigravity")
               if re.search(re.escape(c), readme, re.I)]
    if re.search(r'"mcpServers"', readme) and "Claude Desktop" not in clients:
        clients.insert(0, "Claude Desktop")
    return {
        "runtime": runtime or "binary",
        "transport": transport,
        "auth_method_hint": auth_hint,
        "compatible_clients_hint": clients,
        "tools": [{"name": k, "description": v} for k, v in tools.items()],
        "resources": resources,
        "prompts": prompts,
    }


def is_mcp_dir(d: Path) -> list[str]:
    signals = []
    for name in ("package.json", "pyproject.toml", "requirements.txt", "go.mod", "Cargo.toml", "setup.py"):
        p = d / name
        if p.is_file():
            t = read_text(p)
            if MCP_DEP_PAT.search(t):
                signals.append(f"{name} depends on an MCP SDK")
            if re.search(r"\bmcp[ -]server\b|model context protocol", t, re.I):
                signals.append(f"{name} describes an MCP server")
    if not signals:
        return []
    return signals


def mcp_code_signal(d: Path) -> bool:
    for p in walk_files(d):
        if p.suffix in CODE_EXT and MCP_CODE_PAT.search(read_text(p)):
            return True
    return False


# ------------------------------------------------------------------ n8n

def is_n8n(p: Path) -> bool:
    if p.suffix != ".json":
        return False
    try:
        if p.stat().st_size > 5_000_000:
            return False
        d = json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return False
    return (isinstance(d, dict) and isinstance(d.get("nodes"), list) and d["nodes"]
            and isinstance(d["nodes"][0], dict) and "type" in d["nodes"][0]
            and str(d["nodes"][0].get("type", "")).startswith(("n8n-nodes", "@n8n")) and "connections" in d)


# ------------------------------------------------------------------ main

def inventory(root: Path) -> dict:
    root = root.resolve()
    components: list[dict] = []
    claimed: set[Path] = set()

    all_files = list(walk_files(root))

    # 1. Plugin bundles (.claude-plugin/plugin.json) claim the skills beneath them.
    for p in all_files:
        if p.name == "plugin.json" and p.parent.name == ".claude-plugin":
            d = p.parent.parent
            try:
                meta = json.loads(read_text(p) or "{}")
            except Exception:
                meta = {}
            skills = sorted(rel(root, s.parent) for s in all_files
                            if s.name.lower() == "skill.md" and d in s.parents)
            mcp_cfg = (d / ".mcp.json").is_file()
            components.append({
                "kind": "skill",
                "shape": "plugin-bundle",
                "path": rel(root, d),
                "name_hint": meta.get("name") or readme_title(d) or d.name,
                "description_hint": meta.get("description", ""),
                "skills_inside": skills,
                "bundles_mcp_config": mcp_cfg,
                "readme": readme_in(d),
                "license_file": license_in(d),
                "platform_signals": platform_signals(d) or ["Claude Code"],
                "signals": [f"{rel(root, p)} plugin manifest", f"{len(skills)} SKILL.md file(s) inside"],
            })
            claimed.add(d)

    # 2. Standalone SKILL.md files not inside a bundle.
    skill_dirs = sorted({s.parent for s in all_files if s.name.lower() == "skill.md"})
    loose = [sd for sd in skill_dirs if not any(c == sd or c in sd.parents for c in claimed)]
    # Group sibling skills under a shared "skills/" folder into one candidate bundle.
    groups: dict[Path, list[Path]] = {}
    for sd in loose:
        if sd.parent.name in ("skills", ".skills") and sd.parent != root:
            groups.setdefault(sd.parent.parent if sd.parent.parent != root.parent else root, []).append(sd)
        else:
            groups.setdefault(sd, []).append(sd)
    for gdir, members in sorted(groups.items()):
        if len(members) == 1 and members[0] == gdir:
            sd = gdir
            fm = parse_frontmatter(read_text(next(sd.glob("[Ss][Kk][Ii][Ll][Ll].[Mm][Dd]"))))
            components.append({
                "kind": "skill",
                "shape": "single-skill",
                "path": rel(root, sd),
                "name_hint": readme_title(sd) or fm.get("name") or sd.name,
                "skill_frontmatter_name": fm.get("name"),
                "description_hint": fm.get("description", ""),
                "readme": readme_in(sd),
                "license_file": license_in(sd),
                "platform_signals": platform_signals(sd),
                "signals": [f"{rel(root, sd)}/SKILL.md"],
            })
        else:
            components.append({
                "kind": "skill",
                "shape": "skill-collection",
                "path": rel(root, gdir),
                "name_hint": readme_title(gdir) or gdir.name,
                "skills_inside": [rel(root, m) for m in members],
                "readme": readme_in(gdir),
                "license_file": license_in(gdir),
                "platform_signals": platform_signals(gdir),
                "signals": [f"{len(members)} SKILL.md files under {rel(root, gdir)}"],
                "note": "Could be listed as one bundle or as separate skills; ask the user.",
            })
        claimed.add(gdir)

    # 3. MCP servers: nearest manifest directory with MCP SDK dependency or MCP code.
    manifest_dirs = sorted({p.parent for p in all_files if p.name in MANIFESTS})
    for md in manifest_dirs:
        if any(c in md.parents for c in claimed if c != root) and md not in claimed:
            # inside a bundle/skill; bundled servers are still separately listable
            pass
        sig = is_mcp_dir(md)
        if not sig and not mcp_code_signal(md):
            continue
        if not sig:
            sig = ["source mentions MCP server transport / protocol"]
        # Skip if a parent manifest dir is already an MCP server (monorepo package roots)
        if any(c["kind"] == "mcp-server" and (root / c["path"]) in md.parents for c in components):
            continue
        info = analyse_mcp(md)
        if not info["tools"] and not sig[0].endswith("SDK"):
            # weak signal with no tools found: probably a client or docs, report as low confidence
            confidence = "low"
        else:
            confidence = "high" if info["tools"] else "medium"
        components.append({
            "kind": "mcp-server",
            "path": rel(root, md),
            "name_hint": readme_title(md) or md.name,
            "readme": readme_in(md),
            "license_file": license_in(md),
            "confidence": confidence,
            "signals": sig,
            **info,
        })
        claimed.add(md)

    # 4. n8n workflows
    for p in all_files:
        if is_n8n(p):
            components.append({
                "kind": "playbook",
                "playbook_type": "n8n",
                "path": rel(root, p.parent),
                "workflow_file": rel(root, p),
                "name_hint": readme_title(p.parent) or p.stem,
                "readme": readme_in(p.parent),
                "license_file": license_in(p.parent),
                "signals": ["n8n workflow JSON (nodes + connections)"],
            })

    # 5. Claude Code subagents -> listed as skills on the Exchange
    sub = [p for p in all_files if p.suffix == ".md" and p.parent.name == "agents" and p.parent.parent.name == ".claude"]
    if sub:
        components.append({
            "kind": "subagent-definitions",
            "path": rel(root, sub[0].parent.parent.parent),
            "files": [rel(root, p) for p in sub],
            "signals": ["Claude Code subagent definitions (.claude/agents/*.md)"],
            "note": "The Exchange lists subagents as skills; a SKILL.md entry point is required.",
        })

    # 6. Other standalone code projects (possible agents / tools)
    for md in manifest_dirs:
        if md in claimed or any(c in md.parents for c in claimed if c != root):
            continue
        if md == root and components:
            continue
        if not readme_in(md):
            continue
        components.append({
            "kind": "agent?",
            "path": rel(root, md),
            "name_hint": readme_title(md) or md.name,
            "readme": readme_in(md),
            "license_file": license_in(md),
            "runtime_hint": next((rt for n, rt in MANIFESTS.items() if (md / n).exists()), None),
            "confidence": "low",
            "signals": ["code project with its own manifest and README; not an MCP server or skill"],
        })
        claimed.add(md)

    # Root-level facts
    out = {
        "repo_root": str(root),
        "root_readme": readme_in(root),
        "root_license": license_in(root),
        "root_platform_signals": platform_signals(root),
        "component_count": len([c for c in components if c["kind"] != "subagent-definitions" and c.get("confidence") != "low"]),
        "low_confidence_candidates": len([c for c in components if c.get("confidence") == "low"]),
        "components": components,
    }
    out["multi_listing"] = out["component_count"] > 1
    return out


def human(inv: dict) -> str:
    lines = [f"Repo: {inv['repo_root']}",
             f"Root README: {inv['root_readme'] or 'MISSING'}   Root LICENSE: {inv['root_license'] or 'MISSING'}",
             f"Listable components found: {inv['component_count']}" + ("  (multi-listing repo)" if inv["multi_listing"] else "")
             + (f"  + {inv['low_confidence_candidates']} low-confidence candidate(s) to ask about" if inv["low_confidence_candidates"] else ""),
             ""]
    for i, c in enumerate(inv["components"], 1):
        lines.append(f"{i}. {'(low confidence) ' if c.get('confidence') == 'low' else ''}[{c['kind']}{'/' + c['shape'] if 'shape' in c else ''}] {c.get('name_hint', '')}  -> {c['path']}")
        for s in c.get("signals", []):
            lines.append(f"     signal: {s}")
        if c["kind"] == "mcp-server":
            lines.append(f"     runtime={c['runtime']} transport={c['transport']} auth_hint={c['auth_method_hint']} tools={len(c['tools'])} resources={len(c['resources'])} prompts={len(c['prompts'])}")
        if c.get("skills_inside"):
            lines.append(f"     skills: {', '.join(c['skills_inside'])}")
        if "readme" in c:
            lines.append(f"     README: {c['readme'] or 'none in this folder'}   LICENSE: {c.get('license_file') or 'inherits root'}")
        if c.get("note"):
            lines.append(f"     note: {c['note']}")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    root = Path(a.repo)
    if not root.is_dir():
        print(f"not a directory: {root}", file=sys.stderr)
        return 2
    inv = inventory(root)
    print(json.dumps(inv, indent=2) if a.json else human(inv))
    return 0


if __name__ == "__main__":
    sys.exit(main())
