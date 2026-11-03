# CyberAgents Exchange Submit — Claude Desktop & Cowork

A Claude skill that walks you through submitting a cybersecurity AI agent, skill, MCP server or playbook to the [Tenable CyberAgents Exchange](https://exchange.tenable.com) from **Claude Desktop**, **claude.ai** or **Claude Cowork**. You don't need a terminal or Claude Code.

It is the sibling of the [Claude Code submission builder](https://github.com/jtbuchanan-tenb/cyberagent-exchange-submission-builder). Both apply the same Exchange rules. This edition is built for the cloud sandbox those apps run in, and it adds support for **repositories that contain several listings**.

## What it does

1. **Gets the session ready.** It checks what this particular sandbox can reach, then helps you connect GitHub the way that works here:
   - linking GitHub to Claude and installing the Claude GitHub App;
   - an already-authenticated `gh`;
   - or your own browser.

   It also checks that you're on a personal GitHub account, not an Enterprise Managed User (EMU) account.
2. **Validates your repository.** It clones the repo into the sandbox and checks:
   - that the repo is public, which it changes only after a clean scan and your OK;
   - for credentials across the **working tree and the full git history**, with values always redacted;
   - the licence, including the Tenable, Inc. copyright rule for Tenable employees;
   - the README and installation instructions;
   - the Exchange's archive policy.
3. **Inventories the components.** It finds every listable component (single skills, skill and plugin bundles, MCP servers with their tools, n8n workflows, subagents, other code projects). It recommends one repository per listing. When you confirm an exceptional case, it plans one listing per component, with subfolder `github_url`s and cross-references between them.
4. **Builds each listing.** It interviews you, auto-detecting what it can. Controlled values come from the Exchange's live `validator.py`. It then validates each file with that same validator plus the reviewers' Tier 1 checklist.
5. **Opens the pull requests.** It forks `tenable/cyberagents-exchange` and opens **one branch and one PR per listing** (the checklist allows one new listing file per PR). It links sibling PRs to each other, and asks before every push and PR.

## Prerequisites

- **Claude Desktop, claude.ai or Cowork** on a plan with Skills, and **code execution** turned on (Settings → Capabilities). On Team and Enterprise plans an owner may need to enable Skills.
- A **personal GitHub account**. Tenable employees: not your EMU account.
- Your project in a **GitHub repository** under that account. It can stay private until the scan passes.
- For the smoothest run, **link GitHub to Claude** and install the **[Claude GitHub App](https://github.com/apps/claude/installations/select_target)** on your personal account, for your project repo and your fork of `cyberagents-exchange`. The skill tells you exactly what's missing if you skip this. If your organization blocks it, a browser-only fallback still gets you to a PR.

## Installation

### Claude Desktop / claude.ai / Cowork (upload the skill)

1. Download [`dist/cyberagents-exchange-submit-desktop.zip`](dist/cyberagents-exchange-submit-desktop.zip) from this repository (open it, then use **Download raw file**).
2. In Claude, open **Settings → Capabilities → Skills** and choose **Upload skill**. Some builds put this under Customize → Skills.
3. Select the zip. The skill appears as **cyberagents-exchange-submit-desktop**; make sure it's toggled on.

To build the zip yourself from a clone, run `scripts/build_release.sh`. It writes `dist/cyberagents-exchange-submit-desktop.zip`, whose top folder matches the skill name, as the upload requires.

### Without installing

Paste this into a Claude Desktop or Cowork chat:

```
I want to submit my project to the CyberAgents Exchange. Fetch https://github.com/jtbuchanan-tenb/cyberagent-exchange-submission-builder-claude-desktop, follow its SKILL.md, and ask me before opening any PR.
```

### Always current

You never have to remember to update. Every run starts by fetching this repository's latest published version. If your installed copy differs, Claude follows the latest instructions for that session and tells you, so a cached copy can't send you through an old process. It also pulls the Exchange's current `CONTRIBUTING.md`, contributing checklist and `validator.py` before it begins, and checks them again before opening each PR. If the Exchange changes its policy, the skill follows the new rules. To refresh your installed copy, remove it and upload the new zip.

## Usage

In a new chat, say something like:

```
Submit my project to the Tenable CyberAgents Exchange: https://github.com/<you>/<repo>
```

or invoke it by name: `/cyberagents-exchange-submit-desktop`.

Claude works through readiness, the Contribution Agreement, validation, the inventory, the listing interviews and the PRs. It confirms with you before any commit, push, visibility change or pull request.

## What you get

- A validated listing file per component, written to `~/cae-submission/listings/` in the sandbox.
- A pull request per listing on `tenable/cyberagents-exchange`. Its title is `Add listing: <Name>` and its body includes the Contribution Agreement acceptance statement and checklist; multi-listing PRs also carry the shared-repo reason and links to sibling PRs.
- If you agree, fixes committed to your own repo: licence, README sections, a `SKILL.md` entry point for subagents.
- A resumable plan at `~/cae-submission/submission-plan.json` in the sandbox.

## Repositories with several listings

The Exchange **prefers one repository per listing**, and the skill says so first. It offers to split components into their own repos with history preserved, or to submit one component at a time.

When you confirm an exceptional reason (for example, a platform monorepo whose components ship together, like SentinelOne's [MCP server](https://exchange.tenable.com/mcp-servers/sentinelone-s1-secops-mcp/) and [skills](https://exchange.tenable.com/skills/sentinelone-ai-analyst-claude-skills/) listings), it:
- scans and checks the repo once;
- gives each component its own listing, with a `github_url` pointing at its folder (`…/tree/<branch>/<path>`);
- checks each folder for its own README, licence and install steps;
- cross-references the siblings in each listing body;
- opens one PR per listing, linked to each other, with your reason recorded for the maintainers.

## How it works

`SKILL.md` holds the step-by-step instructions. `references/` holds the detail Claude reads when it reaches each stage: environment setup, multi-listing policy, field rules, frontmatter shapes, and PR workflows per route.

`scripts/` are standard-library Python, so they run even in sandboxes where package installs are blocked:

| Script | Purpose |
|---|---|
| `env_check.py` | Probes GitHub git and API reachability, `gh` auth (including a stale `GH_TOKEN`), validator dependencies and scanners, then recommends a route |
| `detect_components.py` | Inventories listable components and their signals: plugin bundles, skills, MCP runtime/transport/tools, n8n workflows, subagents |
| `secret_scan.py` | Credential scan of the working tree and full history. Uses gitleaks or trufflehog when installed, otherwise a built-in rule set. Always redacts. |
| `validate_listing.py` | Runs the Exchange's own `validator.py` against a listing, plus Tier 1 checklist lint: slug, directory, Tenable-set fields, placeholders, dates, domains, body, `github_url`, EMU |
| `vocab.py` | Prints the live controlled vocabularies from `validator.py` |
| `prefill_link.py` | Builds pre-filled github.com links (new repo, fork, new file, PR with title and body, licence) for steps you do in your browser |
| `build_release.sh` | Builds the uploadable skill zip |

### Network access

The skill talks only to **GitHub**: `github.com` for git, `api.github.com` through `gh`, and the browser pages you open yourself. It clones:
- your repository;
- `tenable/cyberagents-exchange`, for the live validator, templates and checklist;
- this repository, for the version check.

It sends no telemetry and calls no other services.

## Known limitations

- **Sandbox network policies vary.** Package registries, raw.githubusercontent.com, device-code login or GitHub GraphQL may be blocked. The skill detects each and picks another route, but some organizations allow only the browser route.
- **Claude can't create GitHub repositories for you** in Claude Desktop cloud sessions, even with GitHub linked and the Claude GitHub App installed. The session's GitHub gateway only allows calls against repositories attached to the session. When a new repo or fork is needed, the skill gives you a pre-filled github.com link and continues once it exists.
- **Built-in secret scanning is pattern-based.** If gitleaks or trufflehog can't be installed in the sandbox, the scan uses a built-in rule set that covers common credential formats, private keys and hard-coded assignments. It does not cover binaries, LFS objects or submodules. The Exchange's review also runs gitleaks.
- **Detection is a draft.** Component and MCP tool detection is heuristic. Claude confirms against the code and asks you, but review the generated metadata.
- **Validator deps.** The Exchange's `validator.py` needs `pydantic` and `PyYAML`, which Claude's sandbox normally includes. Its other optional deps are shimmed when they can't be installed.
- **Files on your computer** are reachable only while the Claude desktop app is open and linked. Otherwise the skill works from GitHub or an uploaded zip.

## License

MIT. See [LICENSE](LICENSE).

## Questions or issues

- Exchange questions: [exchange.tenable.com](https://exchange.tenable.com), or [open an issue on the Exchange repo](https://github.com/tenable/cyberagents-exchange/issues)
- Issues with this skill: [open an issue here](https://github.com/jtbuchanan-tenb/cyberagent-exchange-submission-builder-claude-desktop/issues)
