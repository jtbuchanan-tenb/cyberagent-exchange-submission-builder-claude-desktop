---
name: cyberagents-exchange-submit-desktop
description: Submit agents, skills, MCP servers and playbooks to the Tenable CyberAgents Exchange (exchange.tenable.com) from Claude Desktop or Cowork, including repos that hold several listings. Use when someone wants to list a project on the Exchange, check a repo against its requirements, build listing metadata, or open the Exchange pull requests. Triggers - submit to the exchange, CyberAgents Exchange, list my agent, list my skill, list my MCP server, publish to exchange.
---

# CyberAgents Exchange Submission — Claude Desktop & Cowork

Guide the person through submitting their project to the Tenable CyberAgents Exchange: get the session connected, validate the repository, build one listing per component, and open one pull request per listing against `tenable/cyberagents-exchange`.

This is the Claude Desktop / Cowork edition of the Claude Code submission skill. The rules are the same; what changes is the environment. Here you work in a **cloud sandbox**, not in the person's terminal:

- The person's repo is not in the current directory. You clone it into the sandbox from GitHub, bring it in from their computer, or take an uploaded zip.
- GitHub access goes through whatever the session offers (a linked GitHub account, an authenticated `gh`, or the person's browser). Package registries may be blocked.
- Every helper in `scripts/` is standard-library Python so it runs even in locked-down sandboxes.

## Ground rules

- **Ask before anything that changes something outside the sandbox:** commits or pushes to the person's repo, changing repo visibility, creating repos or forks, editing `validator.py`, opening or editing pull requests. Show what will happen, then wait for a yes.
- **Never display a secret.** Report where a credential is and what kind it is, with the value redacted.
- **Controlled-vocabulary values come from the live `validator.py`** (via `scripts/vocab.py`), never from memory or from this file.
- **Never emit `partner_contribution`, `vetted_on`, `vetted_commit_sha` or `last_reviewed` on a new listing.** Tenable sets them during review, and `tier` is always `"contributed"`. When *updating* a listing that already exists, keep those fields and `tier` exactly as they are upstream; `validate_listing.py` enforces both cases.
- When the session has a multiple-choice question tool (e.g. AskUserQuestion), use it for choices; otherwise ask in plain text. Keep questions few and batched.
- Keep running state in `$WORK/submission-plan.json` (see Phase 3) so a long session, or a person returning later, can resume.
- Talk in plain words. Paths and commands go in code blocks; don't narrate tool plumbing.
- **Always run from the latest published version of this skill.** An installed or cached copy may be stale. Phase 0.1 fetches the current one from the public repo and, if it differs, you follow that copy instead of this file.
- **The Exchange's own policy files are the authority.** Phase 0.2 pulls the current `CONTRIBUTING.md`, contributing checklist and `validator.py` before anything else. If they say something different from this skill, follow the Exchange's files and tell the person what changed.
- **Give pre-filled links for anything the person must do in a browser.** Put every value GitHub accepts into the URL (repo name, visibility, description, file name, branch, compare target), so the person only checks and clicks. Hand over anything a URL can't carry (a PR body, file contents) ready to paste. `references/pr-workflow.md` → "Pre-filled links" has the formats.

Set up a working directory once and reuse it. Shell variables don't persist between commands in every sandbox, so restate `WORK` and `SKILL_DIR` at the top of each command block.

```bash
export WORK="${WORK:-$HOME/cae-submission}"; mkdir -p "$WORK"
```

---

## Phase 0 — Session readiness

Do this first, every time, before the Contribution Agreement or any question about the project. Its purpose is that the person learns **now**, not halfway through, what this session can and cannot do, and that every later step uses current instructions.

### 0.1 Use the latest published skill — always

Fetch the current published skill, replacing any copy left from an earlier session, and locate the installed one:

```bash
export WORK="${WORK:-$HOME/cae-submission}"; mkdir -p "$WORK"
REPO=https://github.com/jtbuchanan-tenb/cyberagent-exchange-submission-builder-claude-desktop
rm -rf "$WORK/skill-latest" && git clone -q --depth 1 "$REPO" "$WORK/skill-latest" \
  && echo "latest=v$(cat "$WORK/skill-latest/VERSION") @ $(git -C "$WORK/skill-latest" rev-parse --short HEAD)"
INSTALLED="$(find /mnt/skills "$HOME/.claude/skills" /mnt/user-data "$HOME" -maxdepth 6 -path '*cyberagents-exchange-submit-desktop/SKILL.md' -not -path "$WORK/*" 2>/dev/null | head -1)"
echo "installed=${INSTALLED:-<none - running from a fetched URL>} v$( [ -n "$INSTALLED" ] && cat "$(dirname "$INSTALLED")/VERSION")"
[ -n "$INSTALLED" ] && diff -rq "$(dirname "$INSTALLED")" "$WORK/skill-latest" -x .git -x .gitignore -x .github -x .githooks -x dist -x __pycache__ >/dev/null && echo "installed copy is current" || echo "installed copy differs from the published one (or none installed)"
```

From here on, **`SKILL_DIR="$WORK/skill-latest"`** for every script and reference, whatever is installed.

- **The installed copy is current:** continue silently.
- **It differs, or nothing is installed:** read `$WORK/skill-latest/SKILL.md` in full **now**, and follow it from its Phase 0.2 instead of the rest of this file, which may be stale. If an installed copy is out of date, tell the person in one line, without asking:
  > Your installed copy of the Exchange submission skill is out of date (v<old>; current is v<new>). I'm using the current published instructions for this session. To update your installed copy, re-upload the zip from <REPO>/tree/main/dist.

  If the installed `VERSION` is *higher* than the published one, it's a maintainer's development copy. Ask which one to use.
- **The fetch fails:** GitHub isn't reachable from this sandbox, so no submission can be made from here anyway. Say so plainly and stop. Don't carry on with a possibly stale cached copy. Phase 0.3's route table and `references/environment-setup.md` cover what to try.

### 0.2 Pull the Exchange's current rules

Before beginning, get the Exchange's **current** policy and schema, replacing any clone from an earlier session:

```bash
export WORK="${WORK:-$HOME/cae-submission}" SKILL_DIR="$WORK/skill-latest"
rm -rf "$WORK/exchange-upstream" && git clone -q https://github.com/tenable/cyberagents-exchange "$WORK/exchange-upstream"
cd "$WORK/exchange-upstream" && echo "exchange rules @ $(git rev-parse --short HEAD) ($(git log -1 --format=%cs))"
for f in CONTRIBUTING.md docs/contributing_checklist.md validator.py docs/CyberAgents_Contribution_Agreement; do
  printf '%-40s last changed %s\n' "$f" "$(git log -1 --format=%cs -- "$f")"; done
```

Then **read `CONTRIBUTING.md` and `docs/contributing_checklist.md` in full**, not just skim them. They are the directions contributors must follow and the checklist reviewers apply. While reading, compare them with this skill's assumptions:
- the repository requirements;
- the Contribution Agreement wording, and the statement required in the PR;
- the listing fields, and which fields are Tenable-set;
- the domains rules;
- one new listing file per PR;
- the PR title format;
- the rejection criteria;
- anything new.

If the Exchange's files differ from this skill, **the Exchange's files win**. Follow them for this submission, and tell the person in a line or two what changed and how you're adapting. A new required field, for example, gets added to every listing. Record both commit SHAs (the skill's and the Exchange's) in `submission-plan.json`.

Every later phase uses this same fresh clone. Before opening each pull request, Phase 5 checks again whether the policy files have moved on.

### 0.3 Probe the sandbox

```bash
python3 -I "$SKILL_DIR/scripts/env_check.py"
```

It reports: whether github.com git and the GitHub REST API are reachable, whether `gh` is authenticated (and whether a stale `GH_TOKEN` is the cause), what Python modules the validator needs, which secret scanners exist, and a recommended route.

Also check your own tool list (not the shell) for:
- **Session GitHub repo tools** — e.g. `add_repo` / `check_repo_access`. These attach repositories to the session with the person's linked GitHub account.
- **The device bridge** — `mcp__remote-devices__*` tools for files on the person's computer; `device_bash` means you also have a shell there.
- **A built-in browser tool**, such as Claude in Chrome or the desktop app's own browser. This is optional. The fallback for anything the sandbox cannot reach is always the person's own browser, with Claude preparing the content and links.

Use only tools that come with Claude itself or that the person explicitly connected for this. Never depend on MCP servers that happen to be installed on one person's machine.

### 0.4 Connect GitHub

Read `references/environment-setup.md` and walk the person through the route that fits. In short:

| What env_check / your tools show | Route |
|---|---|
| `RECOMMENDED ROUTE … cli` (`gh` authenticated, GraphQL and account-wide calls work) | **CLI route** — normal `gh` + `git` |
| `RECOMMENDED ROUTE … rest` (`gh` authenticated, GraphQL refused and/or calls limited to attached repos) | **REST route** — `gh api` REST calls only; attach **every** repo you touch, public ones included, with the session repo tools first; the person creates any brand-new repo or fork in their browser |
| `gh` not authenticated, session repo tools present | Ask them to **link GitHub to Claude**, then **install the Claude GitHub App** on their personal account for the repos involved |
| Nothing works (corporate policy, no app install) | **Browser route** — Claude prepares every file; the person (or a browser tool) does the GitHub clicks |

Never ask the person to paste a GitHub token into the chat unless they insist and understand it will live in the transcript.

### 0.5 Personal account check (EMU)

```bash
gh api user --jq '.login'   # or whatever account the person names for the browser route
```

An **underscore** separating an org prefix from a username (`tenable_jdoe`) means an Enterprise Managed User account. EMU accounts cannot fork the Exchange or open PRs on it. Hyphens (`jdoe-tenb`) are normal personal accounts — don't flag them. If EMU: stop and help them sign in with, or create, a personal account (github.com/signup), then re-link it.

### 0.6 Readiness summary

Give the person a short summary before doing any real work, for example:

> **Ready to submit from this session**
> - GitHub: linked as `jdoe-tenb` (personal account) — REST route
> - Pushes: allowed to `jdoe-tenb/my-agent` and your Exchange fork *(or: "need the Claude GitHub App installed — link")*
> - Your project: will be cloned from GitHub *(or: read from your computer / from the zip you attached)*
> - Secret scanning: built-in scanner (gitleaks isn't installable here); the Exchange also runs gitleaks on review
> - Validation: the Exchange's own `validator.py`, run here before any PR

Anything missing gets one line saying how to fix it. Do not start Phase 1 while a blocker remains, unless the person chooses the browser route.

---

## Phase 1 — Contribution Agreement

Ask the person to review and accept the agreement:

> Before we start: you'll need to review and accept the CyberAgents Exchange Contribution Agreement —
> https://github.com/tenable/cyberagents-exchange/blob/main/docs/CyberAgents_Contribution_Agreement
> Have you reviewed it, and do you accept it?

Only an explicit yes counts. On no or uncertainty, stop: the agreement must be accepted before any submission. On yes, record the moment straight away:

```bash
date -u +%Y-%m-%dT%H:%M:%SZ
```

That timestamp becomes `contribution_agreement_date` on **every** listing in this session.

---

## Phase 2 — Get the repository and validate it

Run this phase **once per repository**, even when the repository will produce several listings.

### 2.1 Bring the repo into the sandbox

Ask where the project lives if it isn't obvious from the conversation:

- **On GitHub** (most common): clone with **full history**. The secret scan must see every commit.
  ```bash
  git clone https://github.com/<owner>/<repo> "$WORK/repo" && cd "$WORK/repo" && git fetch --all --tags -q
  ```
  On the REST route, attach the repo with the session repo tools first, even when it's public. The gateway refuses API calls (visibility, creation date) on unattached repos. Use push access if you may commit fixes, otherwise read access. If the session gives you a shallow clone, deepen it (`git fetch --unshallow`, or `git fetch --depth=100000 origin <branch>` if unshallow is blocked). If history stays partial, the scan report must say so.
- **Only on the person's computer:** with `device_bash`, run `git remote -v` / `git status` there. If the work isn't pushed, help them push it from their machine (they confirm first), then clone it here. Without a device shell, ask them to push it, or to choose "Add folder" in the desktop app and let you stage it.
- **An uploaded zip:** it rarely carries `.git`. That is enough to draft listings, but the repo still has to be on GitHub before submission, and the history scan runs against the GitHub clone.

### 2.2 Owner and URL

```bash
git -C "$WORK/repo" remote get-url origin
git -C "$WORK/repo" symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null || git -C "$WORK/repo" rev-parse --abbrev-ref HEAD
```

Parse `owner` and `repo`, and the default branch: strip the leading `origin/` from the first command's output. You need the branch for monorepo `github_url`s. Also record when the repo was created (`gh api repos/<owner>/<repo> --jq .created_at`); `contribution_agreement_date` may not predate it. Apply the EMU rule from 0.5 to the repo owner. If the repo sits under an EMU account, it must move to a personal account. Do **not** make the EMU copy public. After the move, rerun Phase 2 against the new remote, because its history has never been scanned.

### 2.3 Visibility

```bash
gh api repos/<owner>/<repo> --jq '.visibility + " archived=" + (.archived|tostring)'
```

Record it. **Do not change it yet.** An archived or disabled repo cannot be listed.

### 2.4 Credential scan — working tree **and full history**

```bash
python3 -I "$SKILL_DIR/scripts/secret_scan.py" "$WORK/repo"
```

It uses gitleaks or trufflehog when installed (the Exchange reviews with gitleaks), and otherwise falls back to the built-in scanner. Don't install tools without asking. In a locked-down sandbox, installation usually fails anyway. If the person has gitleaks on their own computer and you have `device_bash`, you can offer to run `gitleaks detect --redact` there as a second opinion.

Report findings grouped by where they live, values redacted. Then gate:

> I found what look like credentials. Your repo is still **private**, so nothing is exposed yet.
> **In current files:** `config.py:12` — AWS access key id (redacted)
> **Only in git history:** commit `6224be0`, `.env` — GitHub token (redacted)
>
> Before the repo can go public:
> - Move secrets to environment variables, and add the files to `.gitignore`.
> - For anything in history, deleting the file isn't enough. Purge it with git-filter-repo or BFG, then force-push.
> - **Rotate every credential that was ever committed**, even in a private repo.

If the person wants help purging history, show them the exact `git filter-repo` / BFG command and the branches and tags it will rewrite. Run it only after an explicit yes, and force-push only after a second explicit yes; both steps are irreversible for anyone else's clones. Then rerun the scan.

Items marked *low confidence* (test or docs paths, test-like values) are often false positives. Ask the person to confirm each one, and record what they waived for 2.5. **Do not continue until every finding is fixed or confirmed false.** If nothing is found, say so in one line that states what was covered (scanner, number of commits).

### 2.5 Make the repo public (only if private)

Only after 2.4 is clean and 2.2 confirmed a personal account. Show the scan summary (scanner, coverage, findings resolved or waived, what isn't covered). Explain that making the repo public publishes every reachable commit, and that this can't be undone. Then offer to do it:

```bash
gh api -X PATCH repos/<owner>/<repo> -f visibility=public     # REST route (works everywhere gh works)
```

Run it only on an explicit yes. Then re-check with 2.3. If they're unsure, leave it private and stop; the submission can resume later.

### 2.6 Archive policy

```bash
find "$WORK/repo" -maxdepth 4 -type f \( -name '*.zip' -o -name '*.tar.gz' -o -name '*.tgz' -o -name '*.skill' -o -name '*.plugin' -o -name '*.rar' -o -name '*.7z' \) -not -path '*/.git/*' -not -path '*/node_modules/*'
```

- If the content exists **only** inside an archive, that is **blocking**. Reviewers must be able to read every file on GitHub. Help them commit the unpacked files.
- Archives alongside the unpacked content are fine as convenience downloads. Note that reviewers will extract them and compare them with the source. Note it for Phase 6: `references/repo-hygiene.md` §1 has a workflow that keeps a committed archive in sync automatically.

### 2.7 License and copyright

```bash
ls "$WORK/repo" | grep -iE '^(license|licence|copying)'; head -5 "$WORK/repo"/LICEN* 2>/dev/null
grep -iE '"license"|^license' "$WORK/repo"/{package.json,pyproject.toml,Cargo.toml} 2>/dev/null
```

- Map the licence to SPDX (`MIT`, `Apache-2.0`, `BSD-2-Clause`, `GPL-3.0-only`, `AGPL-3.0`…) and confirm it with the person. Manifest licence fields must not contradict the file.
- **No licence:** the Exchange requires one. Recommend MIT (Apache-2.0 is also welcome). Write it only after they agree, and commit only with their confirmation.
- **Tenable employee check.** Look for these signals:
  - commit author emails at `@tenable.com`. Check with `git -C "$WORK/repo" log --format=%ae | sort -u`, not the sandbox's own `git config`, which is not the person's.
  - a GitHub login or repo owner containing `tenable` or `tenb`;
  - a `@tenable.com` address for the person in the session context. If any signal is present, ask "Are you a Tenable employee?" If yes, the copyright line must name **Tenable, Inc.** (`Copyright (c) <year> Tenable, Inc.`). Offer the edit. This is a **hard gate**: do not continue until the line names Tenable, Inc.
- In a multi-listing repo, also check each component folder for its own licence file. A folder licence overrides the root licence for that listing. Confirm the SPDX id per listing.

Commit changes you made to the person's repo (licence, README, SKILL.md) only with confirmation. Push them by whatever route Phase 0 settled; see `references/pr-workflow.md` → "Pushing to the person's own repo".

---

## Phase 3 — Inventory: one listing or several?

```bash
python3 -I "$SKILL_DIR/scripts/detect_components.py" "$WORK/repo"          # add --json for the full detail
```

The script lists every listable component it finds, with the signals behind each: skills (single, collections, or Claude plugin bundles), MCP servers (runtime, transport, tool names), n8n workflows, Claude Code subagents, and other code projects that may be agents. Treat it as a draft. Open the files and confirm before relying on it.

**One component:** continue to Phase 4 with that component's folder as the listing root (usually the repo root).

**More than one:** read `references/multi-listing.md` and follow it. The short version:

1. Show the inventory and explain the Exchange's preference: **one repository per listing**. Separate repos give each listing its own README, licence, history, issues and review scope.
2. Offer, in this order: (a) split the components into separate repos, and help with `git subtree split` or `git filter-repo` so history is preserved; (b) submit just one component now; (c) the **exception path**, where one repo carries several listings.
3. Take the exception path only when the person confirms an exceptional reason. Examples: a vendor platform monorepo whose components share code and release together (the SentinelOne precedent), or a skill bundle that ships its own MCP server. Record the reason in their words; it goes in every PR body.
4. On the exception path, each listing gets its own subfolder `github_url` (`https://github.com/<owner>/<repo>/tree/<default-branch>/<path>`). Each also needs its own README in that folder, its own body section cross-referencing its siblings, its own branch, and **its own pull request**: the Exchange checklist requires each PR to add exactly one listing file.

Write the plan, then show it to the person:

```json
{"agreement_accepted_at": "…Z", "repo": "owner/repo", "default_branch": "main", "multi_listing_reason": "… or null",
 "listings": [{"slug": "…", "type": "mcp-server", "path": "mcp/server", "github_url": "…", "status": "planned", "pr": null}]}
```

Save it as `$WORK/submission-plan.json`, and update each listing's `status` as you go (`planned → drafted → validated → submitted`).

---

## Phase 4 — Build each listing

Read `references/field-reference.md` (field rules, domains, type-specific detection) and `references/listing-templates.md` (frontmatter shapes and body guidance) before the first listing.

### 4.1 Load the live vocabularies and templates

Use the fresh Exchange clone from Phase 0.2:

```bash
export WORK="${WORK:-$HOME/cae-submission}" SKILL_DIR="$WORK/skill-latest"
python3 -I "$SKILL_DIR/scripts/vocab.py" "$WORK/exchange-upstream"
ls "$WORK/exchange-upstream/templates"; cat "$WORK/exchange-upstream/templates/<type>-template.md"
```

Use the vocabularies printed here for every controlled field, and the template for field order. Build each listing to pass the checklist you read in Phase 0.2, because that is what reviewers apply.

### 4.2 Interview — shared fields once, listing fields per listing

**Shared across every listing from this repo** (ask once):
- `author`: the repo owner
- `license`: the SPDX id; may differ per listing if a folder has its own licence
- `date_added`: today, YYYY-MM-DD
- `contribution_agreement_date`: from Phase 1

**Per listing**, in order. Propose values from the component's own README and code, then let the person correct them:

1. **Type**: agent, skill, mcp-server or playbook (with subtype standard, sponsored or n8n). A `.claude/agents/*.md` subagent is a **skill**, not an agent; see field-reference.
2. **Name**: the component README's first `#` heading, falling back to the folder name.
3. **`github_url`**: the repo URL, or the `/tree/<branch>/<path>` URL for a subfolder listing.
4. **Description**: one line, under about 120 characters.
5. **Tags**: 3–7, lowercase and hyphenated.
6. **Integrations**: matched against the vocabulary. Fuzzy-correct values such as "sentinelone" to "SentinelOne". A genuinely new vendor can be added to `validator.py` in the same PR, but only with the person's agreement.
7. **Tenable Hexa MCP**: ask only if `Tenable` is among the integrations.
8. **Domains**: propose 1–2 values, with the primary first, and let the person decide. The taxonomy is closed; never extend it.
9. **Type-specific fields**: see field-reference.
   - Skills: `compatible_platforms`, `invocation`, and the platform structure checks.
   - MCP servers: runtime, transport, auth, clients, tools, resources, prompts.
   - Playbooks: `agents_used`, logo, n8n diagram.
10. **Installation-instructions audit** for this component's README. Every declared platform or client needs real, accurate steps. Fix gaps before writing the body.
11. **Body**: a short intro, then `## What it does` and `## How it works`, written fresh rather than copied from the README. Every claim must trace back to the repo. **In a multi-listing repo**, add a sentence naming the sibling listings and how they relate (for example, "uses the `x-mcp` server bundled in this same repository — see its separate MCP server listing").

### 4.3 Assemble, validate, review

Write the listing into a scratch copy of the Exchange repo, at the type directory and slug, then validate it with the Exchange's own validator plus the checklist lint:

```bash
mkdir -p "$WORK/listings"; # write $WORK/listings/<slug>.md
cp "$WORK/listings/<slug>.md" "$WORK/exchange-upstream/<type-dir>/<slug>.md"
python3 -I "$SKILL_DIR/scripts/validate_listing.py" "$WORK/exchange-upstream" "<type-dir>/<slug>.md" --repo-created "<created_at from 2.2>"
git -C "$WORK/exchange-upstream" checkout -q -- . && git -C "$WORK/exchange-upstream" clean -fdq   # leave the scratch copy clean
```

Fix every ✘ before showing the file. Then show the person the complete listing and ask for changes, iterating until they approve. A slug that already exists upstream means this is an **update** to an existing listing. Confirm that's what they want, start from the upstream file rather than a blank one, and keep its Tenable-set fields and `tier` exactly as they are. Use `Update listing: <Name>` as the PR title.

Warnings (`!`) are not blockers, but tell the person about each one. An unknown-key warning usually means a leftover field, such as `type` or `framework` from an old template, that a reviewer will remove; drop it.

Repeat 4.2–4.3 for each listing in the plan.

---

## Phase 5 — Submit: one branch and one pull request per listing

Follow `references/pr-workflow.md` for the route chosen in Phase 0.

**First, check the rules haven't moved since Phase 0.2.** Submissions can span hours, and the Exchange's policy files can change in that time:

```bash
export WORK="${WORK:-$HOME/cae-submission}" SKILL_DIR="$WORK/skill-latest"
cd "$WORK/exchange-upstream" && BEFORE=$(git rev-parse HEAD) && git fetch -q origin main && git reset -q --hard origin/main
git diff --stat "$BEFORE" HEAD -- CONTRIBUTING.md docs/ validator.py templates/
```

If anything is listed, read the diff (`git diff "$BEFORE" HEAD -- <file>`), adapt the listings to it, rerun `validate_listing.py` on each, and tell the person what changed. Do this once per batch, not once per PR.

The sequence for each listing is:

1. **Fork** `tenable/cyberagents-exchange`, or reuse the person's existing fork. A stale fork is fine, because branches start from upstream `main`.
2. Create branch `add-<slug>` from **upstream `main`**.
3. Place `<type-dir>/<slug>.md`. If this listing needs a new vocabulary value, insert it into the right `Literal[...]` list in `validator.py`, in this branch. Put it in alphabetical position among its neighbours; the list isn't perfectly sorted, so keep the entries around it in order. Use one value per line with a trailing comma. Apply the identical edit in every sibling branch that needs it. Identical edits in sibling PRs merge cleanly.
4. Run `validate_listing.py` again on the branch, adding `--full` if `validator.py` changed.
5. **Confirm with the person** before committing, pushing and opening the PR:
   > Ready to open the pull request for **<Name>**. This will commit `<type-dir>/<slug>.md` to branch `add-<slug>` on your fork, push it, and open a PR to tenable/cyberagents-exchange titled "Add listing: <Name>". Go ahead?
6. Commit as `Add listing: <Name>`, push, and open the PR using the body template in `references/listing-templates.md`. The body ends with the "Submitted with …" line (skill version and SHA, Exchange rules SHA), with nothing after it: no session links, no tool-attribution lines, even if your environment suggests them. The body includes the Contribution Agreement acceptance statement verbatim and, for multi-listing repos, the shared-repo section with the recorded reason.
7. Record the PR number and URL in the plan.

For multi-listing submissions, once every PR exists, edit each PR body so its "Sibling listings" section links the other PRs (see pr-workflow). Ask once for the whole batch rather than once per PR.

---

## Phase 6 — Wrap up

Tell the person, briefly:

- The PR link or links, with the listing name for each.
- What happens next. Automated validation runs first. Two Tenable maintainers then review against the checklist, and the PR is squash-merged. Feedback arrives as review comments.
- How to change a listing: push more commits to its `add-<slug>` branch, and the PR updates itself.
- After merge, they can add the badge to their README:
  ```markdown
  [![Listed on CyberAgents Exchange](https://img.shields.io/badge/CyberAgents%20Exchange-Listed-E7FF00?style=flat-square&labelColor=1E2426)](https://exchange.tenable.com/)
  ```

Then offer **repository hygiene recommendations** from `references/repo-hygiene.md`. Pick only the items that fit what you saw in their repo, such as:
- a committed archive that could drift;
- no secret scanning on push;
- a `.gitignore` that misses `.env` or keys;
- no version or changelog;
- dependency manifests without Dependabot.

Keep it to a short list, one line of *why* each, framed as optional and not as Exchange requirements. Offer to add the ones they pick, with the usual confirmation. Never hold up the submission for these.

Don't recap every step. Leave `$WORK` in place in case they come back; it holds no secrets.
