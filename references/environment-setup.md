# Getting a Claude Desktop / Cowork session ready to submit

Claude Desktop and Cowork sessions run in a cloud sandbox, and different accounts get differently configured sandboxes. Before you promise anything, probe with `scripts/env_check.py` and your own tool list, then pick a route.

## What can differ between sessions

| Capability | Typical states | How to tell |
|---|---|---|
| GitHub git (clone, fetch, push over HTTPS) | usually allowed for clone; push needs credentials | `env_check.py` → "github.com git clone/fetch" |
| GitHub REST API (`api.github.com`) | open; reachable only with credentials through a session gateway; or blocked | `env_check.py`, plus `gh api user` |
| GitHub GraphQL | sometimes refused by the gateway ("GitHub GraphQL is not available…") | `gh repo view tenable/cyberagents-exchange` fails with that message |
| `gh` login via device code | sometimes blocked by the sandbox's egress policy (HTTP 403/415 on `github.com/login/device/code`) | the login command errors immediately |
| Package registries (pip, npm, Go) | open, or blocked by an org network policy | an install fails with a connection refusal |
| Files on the person's computer | reachable through the device bridge only while the desktop app is open and linked | `mcp__remote-devices__*` tools present |
| Account-wide GitHub API calls (create a repo, list your repos) | allowed, or refused by the gateway ("sessions are bound to their configured repositories") | `env_check.py` → "account-wide API calls" |
| A browser Claude can drive | optional: Claude in Chrome or the desktop app's built-in browser. Never assume one, and never rely on MCP servers installed on one person's machine | browser tools present |

Do not retry a refused or blocked network call in a loop, and do not route around a policy refusal. Pick the next route instead.

## Connecting GitHub — in order of preference

### A. `gh` already works (CLI route)

`env_check.py` reports `gh CLI … authenticated as <login>`, and `gh repo view tenable/cyberagents-exchange` works. Use the normal commands in `pr-workflow.md` → "CLI route".

If `env_check.py` says a **stale `GH_TOKEN`** is in the environment but `gh` works without it, prefix each `gh` command with `env -u GH_TOKEN -u GITHUB_TOKEN`.

### B. The session has its own GitHub gateway (REST route)

This is the common case in Claude Desktop cloud sessions. The signs:
- `gh api user` works, but GraphQL calls are refused.
- Your tool list includes repository-attach tools (for example `add_repo` / `check_repo_access`).

The person needs to do up to two one-time things.

1. **Link GitHub to Claude.** On claude.ai, open Customize → Connectors (or Settings → Connectors) → GitHub → Connect. If a repo-access check returns a `github_link_required` gate, it includes a direct connect link; give the person that link. They must sign in with their **personal** GitHub account, never an EMU account.
2. **Install the Claude GitHub App** on that personal account, so pushes are allowed: https://github.com/apps/claude/installations/select_target. Grant access to the repo being listed and to their fork of `cyberagents-exchange`, or simply "All repositories". You'll know this step is missing when an attach result says pushes will be refused.

Then **attach each repository** the work touches before using it:
- the person's project repo: read access for scanning, push access if you will commit fixes;
- their fork `<login>/cyberagents-exchange`: push access;
- upstream `tenable/cyberagents-exchange`: attach it with read access. Anonymous git clone usually works, but REST calls against it, such as opening a PR or forking, need it attached.

Attach even public repos before calling the API on them. The gateway refuses REST calls on repos the session hasn't attached.

Opening a PR on upstream from the fork is an API call against `tenable/cyberagents-exchange`. If the gateway refuses it even after attaching, use the browser route for that one step (see `pr-workflow.md`); the branch is already pushed.

**What the gateway cannot do, even with the connector and the GitHub App:**
- **Create a repository.** Account-wide endpoints are refused. When a new repo is needed (splitting a monorepo component, or a project that exists only locally), give the person a pre-filled link and wait for them to create it, private, with nothing initialised:
  `python3 -I "$SKILL_DIR/scripts/prefill_link.py" new-repo --name <repo-name> --description "<text>"`
  Then attach it and push.
- **Create a fork, when refused.** If `POST repos/tenable/cyberagents-exchange/forks` is refused, the person clicks Fork at https://github.com/tenable/cyberagents-exchange/fork.
- **Push to a repo outside the GitHub App's access.** If the person chose "Only select repositories", repos created later aren't included. They add them at github.com/settings/installations → Claude → Configure.

The gateway's own notes apply:
- Clone once, not in parallel. Some gateways cap concurrent git operations per repo; on HTTP 429, wait about 5 seconds and retry once.
- Give big clones a long timeout (up to 10 minutes).
- Before pushing from a shallow clone, run `git fetch origin main` so the push sends a thin pack. Otherwise it can be rejected with HTTP 413.

Only GitHub's REST API works here. Use the `gh api` forms in `pr-workflow.md`; `gh pr create`, `gh repo fork`, `gh repo view` and `gh repo create` use GraphQL and will fail.

### C. Device-code login inside the sandbox

If neither A nor B applies and the sandbox allows it:

```bash
env -u GH_TOKEN -u GITHUB_TOKEN gh auth login --hostname github.com --git-protocol https --web
```

Run it in the background, writing output to a log, because it waits for approval:

```bash
(yes "" | env -u GH_TOKEN -u GITHUB_TOKEN BROWSER=false nohup gh auth login --hostname github.com --git-protocol https --web > "$WORK/gh-login.log" 2>&1 &); sleep 6; cat "$WORK/gh-login.log"
```

Read the one-time code from the log. Give the person the code and https://github.com/login/device, wait while they approve it as their personal account, then confirm with `env -u GH_TOKEN gh api user --jq .login`. If the command errors at once with HTTP 403 or 415, the sandbox blocks device login; move on to D. The token lives only in this sandbox and disappears with it.

### D. Browser route (always available)

When nothing above works, for example under corporate policy, Claude still does all of the preparation: scanning, validation, the finished listing files and the PR text. The person performs the GitHub actions in their own browser. If this session also has a Claude browser tool (Claude in Chrome, or the desktop app's built-in browser) and the person is signed in to GitHub there, Claude can offer to drive those steps with them watching. Never assume one exists. See `pr-workflow.md` → "Browser route".

## Files on the person's computer

- **`device_bash` present:** you have a shell on their machine, scoped to the folders they connected. Run `git status`, `git remote -v` and `git push` there when their work lives only locally. Always ask before pushing.
- **Only file tools (list / stage / commit):** stage the repo folder into the sandbox. Staged copies may lack `.git`, so for history scanning, clone from GitHub instead.
- **No bridge:** ask them to choose "Add folder" from the "+" menu in the Claude desktop app, or to attach a zip, or just to give the GitHub URL.

## Installing this skill (for people asking how)

- **Claude Desktop / claude.ai:**
  1. Download `dist/cyberagents-exchange-submit-desktop.zip` from the skill repo.
  2. Open Settings → Capabilities → Skills, and choose **Upload skill**. Some builds put this under Customize → Skills.
  3. Code execution must be enabled for skills to appear. On Team and Enterprise plans, an owner may need to enable Skills for the organization.
- **Without installing:** ask Claude to "fetch https://github.com/jtbuchanan-tenb/cyberagent-exchange-submission-builder-claude-desktop and follow its SKILL.md". Phase 0.1 handles that mode.
- **Updating:** remove the old skill and upload the new zip. Every run also fetches the latest published skill in Phase 0.1 and follows it, so a stale installed copy is never used to submit.
