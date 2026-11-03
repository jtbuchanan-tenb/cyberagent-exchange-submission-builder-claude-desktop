# Listing field reference

Allowed values for controlled fields always come from `scripts/vocab.py` run against a fresh clone of `tenable/cyberagents-exchange`. This file covers how to *choose* values, and which rules `validator.py` does not enforce.

## Fields Claude fills in without asking

| Field | Source |
|---|---|
| `author` | The GitHub owner of the repo, which must match `github_url`. |
| `github_url` | `https://github.com/<owner>/<repo>`, or `…/tree/<default-branch>/<path>` for a subfolder listing. |
| `license` | The SPDX id confirmed in Phase 2.7. |
| `tier` | Always `"contributed"`. Never ask about it. |
| `date_added` | Today, as YYYY-MM-DD. |
| `contribution_agreement_date` | The UTC timestamp captured in Phase 1, for example `2026-11-03T22:48:00Z`. |

Show these to the person for confirmation along with the name.

**Tenable-set fields: never emit.** These are `partner_contribution`, `vetted_on`, `vetted_commit_sha` and `last_reviewed`. If the person or the repo supplies them, leave them out and explain why.
- `vetted_on` and `vetted_commit_sha` make validation fail on a contributed listing.
- `partner_contribution` passes validation, but reviewers remove it.
- `visibility: example` hides a listing from browse. Include it only if the person explicitly wants an example listing.

## Name, description, tags

- **`name`**: the component README's first `#` heading, falling back to the folder or repo name in title case.
- **`description`**: one line under about 120 characters, saying what it does, not that it is "an AI agent". Propose it, then let the person revise.
- **`tags`**: 3–7, lowercase and hyphenated, drawn from README and code keywords. Tags are free-form, so don't over-think them.

## Integrations

Search the README and code for the platforms the component talks to, and match them to the vocabulary. Fuzzy-correct casing and spelling (`crowdstrike` → `CrowdStrike`). Show the matches along with the full list.

If the person needs a value that genuinely doesn't exist (a real vendor not yet listed), offer to add it to `validator.py` in the same PR. Insert it in **alphabetical order** in the right `Literal[...]` list and keep the existing formatting. The same mechanism applies to `compatible_platforms`, `compatible_clients`, `transport`, `runtime` and `auth_method`.

**`domains` is never extended.** Its taxonomy is closed.

### Tenable Hexa AI MCP

Ask this only when `integrations` includes `Tenable`:

> Does this connect to Tenable through the **Tenable Hexa AI MCP** server, or through other Tenable APIs directly (VM, Security Center, Nessus…)?

Check the repo too: `grep -rniE "hexa.?mcp|tenable/hexa" .`

- **Hexa confirmed:** set `works_with_tenable_hexa_mcp: true` **and** add `"Tenable Hexa AI MCP"` to `integrations`. The validator requires the two together.
- **Otherwise:** omit the field entirely; don't write `false`.

## Domains (closed taxonomy, 1–2 values, first is primary)

| Value | Belongs here |
|---|---|
| `ai-security` | Security **of** AI systems: agent and MCP security, AI-SPM, prompt-injection testing. Being an AI agent doesn't qualify. |
| `application-security` | SAST/DAST, dependency and supply-chain risk, secrets in code, secure SDLC, API security. |
| `cloud-security` | CSPM/CNAPP, cloud misconfiguration, container and Kubernetes posture, cloud attack paths. |
| `cryptography-pki` | TLS and certificate posture, post-quantum readiness, key management. |
| `data-security` | Data discovery and classification, DLP, database security, sensitive-data exposure. |
| `email-collaboration-security` | Phishing analysis, email gateway and header forensics, Slack/Teams/SaaS collaboration risk. |
| `governance-risk-compliance` | Framework and benchmark mapping, audit evidence, policy, risk quantification, reporting to leadership. |
| `identity-access` | IAM and entitlement review, privilege-escalation paths, MFA/SSO posture, AD and Entra ID. |
| `network-security` | Firewall and segmentation review, network device configuration, traffic and perimeter analysis. |
| `ot-iot-security` | ICS/SCADA, medical and embedded devices, industrial protocols. |
| `platform-operations` | **Not a security domain.** Operating or administering a security platform: health checks, licensing, scan operations, exports, connectors, onboarding helpers. |
| `security-awareness` | Training content, phishing simulation, secure-behaviour coaching. |
| `security-operations` | SIEM/EDR/NDR work, threat hunting, detection engineering, incident response, malware analysis, insider threat. |
| `threat-intelligence` | IOC and actor research, CVE and exploit enrichment, threat feeds, attribution. |
| `vulnerability-management` | Core VM workflows only: scanning, prioritisation, remediation tracking, exposure scoring for known vulnerabilities. |

Before trusting this table, check it against `vocab.py`, which is the authority. Infer 1–2 candidates, weighting the description most heavily, and propose them:

> I'd file this under **Security Operations** (`security-operations`). The first value is the primary domain, the one the Exchange leads with. Keep it, swap it, or add a second?

The person decides. Add a second value only when the listing genuinely straddles two domains. Don't reach for `vulnerability-management` or `platform-operations` by reflex.

If the person wants a domain that doesn't exist, pick the closest existing one now and suggest opening an issue at https://github.com/tenable/cyberagents-exchange/issues.

## Type: agent vs skill (subagent rule)

The types are:
- `agent`: a standalone program, CLI, library or service with its own runtime.
- `skill`: a `SKILL.md`-based skill or bundle for an AI assistant.

If the component's main artifact is a Claude Code subagent (`.claude/agents/*.md`), the Exchange lists it as a **skill**, and it needs a `SKILL.md` entry point at the listing root. Explain this, offer to draft a `SKILL.md` that wraps the subagent (frontmatter `name` and `description`, plus instructions), and show it for approval. Commit it only with confirmation. Don't submit such a component as an agent.

## Skill fields

**Platform signals**, checked at the listing root:

| Signal | Platform |
|---|---|
| `SKILL.md` with `name`/`description` frontmatter | Claude Code, Claude Desktop, Claude Cowork |
| `.cursor/rules/` or `.cursorrules` | Cursor |
| `.github/copilot-instructions.md` or `.github/skills/<n>/SKILL.md` | GitHub Copilot |
| `.windsurfrules` or `.windsurf/skills/<n>/SKILL.md` | Windsurf |
| `GEMINI.md` or `.gemini/skills/<n>/SKILL.md` | Gemini CLI |
| `AGENTS.md` (or `codex.json`) | Codex |
| `.clinerules` or `.cline/skills/<n>/SKILL.md` | Cline |

**Structure checks** for every declared platform. A mismatch means a reviewer rejection, so either fix the structure or drop the platform:

- `SKILL.md` must start with `---`, contain non-empty `name:` and `description:`, close with `---`, and have a substantive body.
- Every file `SKILL.md` references (`references/…`, `scripts/…`, `templates/…`) must exist:
  ```bash
  grep -oE '(references|scripts|templates|assets)/[A-Za-z0-9_./-]+' SKILL.md | sort -u | while read f; do [ -e "$f" ] || echo "missing: $f"; done
  ```
- **Claude Desktop / Cowork:** the README must explain uploading the skill as a zip (Settings → Capabilities → Skills → Upload skill), and the zip's top folder must match the skill's `name`. A release zip, or clear "zip this folder" steps, both work. The unpacked files must stay in the repo.
- **Claude Code:** the README must show where the skill goes (`~/.claude/skills/<name>/`, or the plugin install command).
- **Other platforms:** say where the file goes on that platform. Content can usually be copied from `SKILL.md`; offer to create the file.

**`invocation`**: the trigger. Use `/` plus the frontmatter `name`, or a slash command named in the README. For skills that trigger only from natural language, describe that, as the SentinelOne listing does. The declared invocation must appear in `SKILL.md` or the README.

## MCP server fields

`detect_components.py` proposes these values. Confirm them by reading the code.

| Field | How to decide |
|---|---|
| `runtime` | `package.json`/`tsconfig.json` → `node`; `bun.lockb`/`bunfig.toml` → `bun`; `pyproject.toml`/`setup.py`/`requirements.txt` → `python`; `Cargo.toml` → `rust`; `go.mod` → `go`; otherwise `binary`. |
| `transport` | stdio transport in code → `stdio`; Streamable HTTP or SSE → `http`; both present → `both`. Check the current code, not old docs. Servers sometimes drop a transport (the SentinelOne server went stdio-only). |
| `auth_method` | Auth on **the MCP connection itself**: none → `none`; a bearer token checked by the server → `token`; an API key the client passes to the server → `api-key`; an OAuth flow → `oauth2`. An API key for an *upstream* service is not the MCP auth method; ask if unsure. |
| `compatible_clients` | Clients the README actually documents (an `mcpServers` JSON block implies Claude Desktop). Each declared client needs real install steps. |
| `tools_exposed` | Every tool, each with a name and a one-line description. The detector catches SDK, FastMCP, Go and raw JSON-RPC patterns, but may miss some, so cross-check against the README's tool table or the tool registry file. |
| `resources_exposed` / `prompts_exposed` | List them, or `[]`. Resource names must be URIs. |

## Playbook fields

`playbook_type` is one of:
- **`standard`**: requires `agents_used`.
- **`sponsored`**: requires `agents_used` and a `logo`; `vendor`-type agents are allowed only here.
- **`n8n`**: requires a `workflow_diagram`; `agents_used` is optional.

**`agents_used`** entries each have `name`, `role` (one sentence), `type` and `ref`:

| `type` | `ref` |
|---|---|
| `exchange` | the slug of an existing Exchange listing |
| `github` | a GitHub URL |
| `info` | blank (a manual or informational step) |
| `vendor` | vendor docs (sponsored playbooks only) |

Collect entries one at a time, then read the whole chain back.

**`logo`** (sponsored only): a public image URL; a `raw.githubusercontent.com` link to a PNG or SVG in the repo is best. If the sandbox can't reach the URL, ask the person to open it and confirm it loads.

**`workflow_diagram`** (n8n only): build it from the workflow JSON.
1. Start at the trigger nodes and follow `connections`.
2. Group adjacent steps by purpose, and aim for 4–7 nodes.
3. Use `flowchart LR` for linear flows and `flowchart TD` when the flow branches.
4. Show the diagram, then let the person edit it.

## Installation-instructions audit (all types)

Reviewers reject instructions that are vague or refer to things that don't exist. For each listing root, confirm:
- the README has a prerequisites section (runtimes, accounts, API keys);
- the README has at least one concrete install-and-run path for each declared platform or client;
- every file, script, package and command mentioned actually exists, with the right paths from the listing root;
- the README covers what the component outputs and its known limitations;
- every outbound call (APIs, telemetry) is documented, since undisclosed outbound calls mean outright rejection.

Offer to draft the missing pieces. Commit them only with confirmation.

## Rejected regardless of quality

Stop and explain, rather than submitting, if the component is:
- offensive or weaponized (exploitation, lateral movement, exfiltration);
- carrying hardcoded secrets in history;
- making undisclosed outbound calls;
- targeting competitors;
- weakening security controls without justification.
