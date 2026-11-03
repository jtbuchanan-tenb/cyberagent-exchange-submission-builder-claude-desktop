# Listing frontmatter shapes, body, and PR text

Every listing is one Markdown file: YAML frontmatter, then a Markdown body. **Field order matters**: `domains` goes straight after `tags` and before `integrations`, matching every merged listing. Quote strings. Leave `date_added` and `contribution_agreement_date` unquoted so YAML reads them as a date and a datetime.

Include `works_with_tenable_hexa_mcp: true` only when Hexa use is confirmed, placing it after `contribution_agreement_date`; otherwise omit it.

## Agent → `agents/<slug>.md`

```yaml
---
name: "<Name>"
author: "<owner>"
github_url: "<url>"
description: "<one line>"
license: "<SPDX>"
tier: "contributed"
tags: ["<tag>", "<tag>"]
domains: ["<primary>"]
integrations: ["<Vendor>"]
date_added: <YYYY-MM-DD>
contribution_agreement_date: <YYYY-MM-DDTHH:MM:SSZ>
---
```

## Skill → `skills/<slug>.md`

```yaml
---
name: "<Name>"
author: "<owner>"
github_url: "<url>"
description: "<one line>"
license: "<SPDX>"
tier: "contributed"
tags: ["<tag>", "<tag>"]
domains: ["<primary>"]
integrations: ["<Vendor>"]
date_added: <YYYY-MM-DD>
contribution_agreement_date: <YYYY-MM-DDTHH:MM:SSZ>
compatible_platforms: ["Claude Code", "Claude Desktop"]
invocation: "/<skill-name>"
---
```

`integrations` may be `[]` when the skill talks to no vendor platform.

## MCP server → `mcp-servers/<slug>.md`

```yaml
---
name: "<Name>"
author: "<owner>"
github_url: "<url>"
description: "<one line>"
license: "<SPDX>"
tier: "contributed"
tags: ["<tag>"]
domains: ["<primary>"]
integrations: ["<Vendor>"]
date_added: <YYYY-MM-DD>
contribution_agreement_date: <YYYY-MM-DDTHH:MM:SSZ>
transport: "stdio"
runtime: "python"
auth_method: "api-key"
compatible_clients: ["Claude Desktop", "Claude Code"]
tools_exposed:
  - name: "<tool>"
    description: "<what it does>"
resources_exposed: []
prompts_exposed: []
---
```

## Playbooks → `playbooks/<slug>.md`

Start with `playbook_type`, then use the common fields above. Then add the fields for the subtype:

```yaml
# standard
agents_used:
  - name: "<step>"
    role: "<one sentence>"
    type: "exchange"            # exchange | github | info
    ref: "<exchange-slug>"
# sponsored: as standard, vendor type allowed, plus
logo: "https://raw.githubusercontent.com/<owner>/<repo>/main/logo.png"
# n8n
workflow_diagram: |
  flowchart LR
    A[Trigger] --> B[Enrich] --> C[Decide] --> D[Notify]
```

`date_added` and `contribution_agreement_date` sit after the type-specific fields, as in the templates.

## Body

The body is original writing, not a copy of the README. Every claim must be supported by the repository.

```markdown
<One or two sentences: what this is and who it's for.>

## What it does

- <capability>
- <capability>

## How it works

<Short technical approach: runtime, what it calls, how it's installed and triggered, notable safeguards.>
```

**Multi-listing repos:** add a line in the intro or "How it works" naming the siblings. For example:

> This server ships in the same repository as the **Acme Claude Skills** bundle, which drives it. See that separate skill listing.

## Pull request

- **Title:** `Add listing: <Name>`, or `Update listing: <Name>` when the file already exists upstream.
- **Body:** write it to a file (`$WORK/pr-<slug>.md`) and pass it with `-F body=@…` or `--body-file`:

```markdown
## New Listing: <Name>

**Repository:** <github_url>
**Type:** <agent | skill | mcp-server | playbook (<subtype>)>
**Description:** <description>

I have reviewed and accept the [CyberAgents Contribution Agreement](https://github.com/tenable/cyberagents-exchange/blob/main/docs/CyberAgents_Contribution_Agreement).

### Checklist
- [x] Contribution Agreement accepted at <contribution_agreement_date>
- [x] Code is in a public repo under a personal (non-EMU) GitHub account
- [x] Full git history scanned for credentials (<scanner>, <N> commits): no unresolved findings
- [x] README covers purpose, prerequisites, how to run, outputs and limitations
- [x] Open source license present (<SPDX>)
- [x] Listing passes `validator.py`; placed in `<type-dir>/` as `<slug>.md`
- [x] `domains` set (1–2 values, primary first)

### Vocabulary Updates
- Added `<value>` to `<field>` in `validator.py`

### Multi-listing repository
This repository hosts more than one Exchange listing. Reason: <the person's stated reason>.
Sibling listings:
- <Name> (`<type-dir>/<slug>.md`): <PR link once open>

Submitted with the CyberAgents Exchange Submission Builder for Claude Desktop v<VERSION> (`<skill sha>`), against Exchange rules at `<exchange sha>`.
```

Remove the "Vocabulary Updates" section when there are none, and the "Multi-listing repository" section for a single-listing repo.
