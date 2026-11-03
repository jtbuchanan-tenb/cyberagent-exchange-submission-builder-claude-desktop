# Fork, branch, push and pull request — by route

Placeholders: `ME` = the person's GitHub login, `SLUG` = the listing slug, `TYPE_DIR` = `agents` | `skills` | `mcp-servers` | `playbooks`. Confirm with the person before every push, PR creation and PR edit.

## Prepare the fork clone (all API routes)

```bash
ME=$(gh api user --jq .login)
# 1. Does the fork exist?
gh api repos/$ME/cyberagents-exchange --jq '.full_name + " fork=" + (.fork|tostring)' 2>/dev/null || echo "no fork"
```

- **No fork:** create one.
  - CLI route: `gh repo fork tenable/cyberagents-exchange --clone=false`
  - REST route: `gh api -X POST repos/tenable/cyberagents-exchange/forks -F default_branch_only=true`
  - If both are refused, the person clicks **Fork** at https://github.com/tenable/cyberagents-exchange/fork.

  Forks take a few seconds to appear; poll the `gh api repos/$ME/cyberagents-exchange` call above.
- **Session gateway:** attach `ME/cyberagents-exchange` with push access, and `tenable/cyberagents-exchange` with read access, before any API call on them. Clone the fork exactly once.

```bash
git clone https://github.com/$ME/cyberagents-exchange "$WORK/exchange-fork"
cd "$WORK/exchange-fork"
git remote add upstream https://github.com/tenable/cyberagents-exchange.git 2>/dev/null
git fetch upstream main
git fetch origin main        # keeps pushes thin from shallow clones
```

A stale fork is fine. Every branch starts from `upstream/main`. Optionally sync the fork's own `main`:
- `gh api -X POST repos/$ME/cyberagents-exchange/merge-upstream -f branch=main`

## Per listing: branch, place, validate, commit

```bash
cd "$WORK/exchange-fork"
git checkout -q -B add-$SLUG upstream/main
cp "$WORK/listings/$SLUG.md" "$TYPE_DIR/$SLUG.md"
# only if this listing needs a new vocabulary value: edit validator.py (alphabetical insertion)
python3 -I "$SKILL_DIR/scripts/validate_listing.py" . "$TYPE_DIR/$SLUG.md"          # add --full if validator.py changed
git add "$TYPE_DIR/$SLUG.md" validator.py 2>/dev/null
git -c user.name="$(gh api user --jq '.name // .login')" -c user.email="$(gh api user --jq '.id|tostring')+$ME@users.noreply.github.com" \
    commit -qm "Add listing: <Name>"
git push -u origin add-$SLUG
```

The commit author is the person's GitHub noreply identity, not the sandbox default. If they'd rather use their own email, ask for it.

## Open the PR

**CLI route** (GraphQL available):
```bash
gh pr create --repo tenable/cyberagents-exchange --base main --head $ME:add-$SLUG \
  --title "Add listing: <Name>" --body-file "$WORK/pr-$SLUG.md"
```

**REST route** (session gateway, GraphQL refused):
```bash
gh api -X POST repos/tenable/cyberagents-exchange/pulls \
  -f title="Add listing: <Name>" -f head="$ME:add-$SLUG" -f base=main -F body=@"$WORK/pr-$SLUG.md" \
  --jq '.html_url + "  #" + (.number|tostring)'
```

On the session gateway this call is normally refused ("GitHub access to this repository is not enabled for this session"). Opening a PR is an API call on `tenable/cyberagents-exchange`, and the session can only make those on repos attached with push access, which contributors don't have. Don't work around it. The branch is already pushed, so the person only needs one click on this pre-filled link:

```bash
python3 -I "$SKILL_DIR/scripts/prefill_link.py" pr --owner "$ME" --branch "add-$SLUG" --title "Add listing: <Name>" --body-file "$WORK/pr-$SLUG.md"
```

The compare page opens with the title and body already filled in. If the script notes the body was too long to pre-fill, give them the body text to paste.

## Linking sibling PRs (multi-listing)

Once every PR in the batch exists, update each body's "Sibling listings" section with the other PR URLs, then:

```bash
gh api -X PATCH repos/tenable/cyberagents-exchange/pulls/<number> -F body=@"$WORK/pr-$SLUG.md"     # REST
gh pr edit <number> --repo tenable/cyberagents-exchange --body-file "$WORK/pr-$SLUG.md"           # CLI
```

If editing is refused (some gateways only allow writes to attached repos), post the links as one comment per PR instead:
- `gh api -X POST repos/tenable/cyberagents-exchange/issues/<number>/comments -f body=…`

If that is refused too, give the person the links to paste.

## Pushing to the person's own repo

This covers fixes made in Phase 2 or 4: licence, README, `SKILL.md`.

- **Gateway:** attach `<owner>/<repo>` with push access, commit in `$WORK/repo` and `git push`. If the push is refused, the Claude GitHub App isn't installed for that repo; give them the install link from `environment-setup.md`.
- **Device bridge with `device_bash`:** write the changed files back into their local clone, show `git diff`, and run `git commit` and `git push` there once they confirm.
- **Neither:** send the changed files with a one-line note on where each goes, and wait while they commit and push. Then `git pull` in `$WORK/repo` and continue.

**Creating a repo** (for a split component, or a project not yet on GitHub):
- **CLI route:** `gh repo create ME/<name> --private`, then `git push`.
- **REST route:** the gateway refuses account-wide calls, so the person creates the repo themselves from a pre-filled link: `https://github.com/new?name=<name>&visibility=private`. They leave README, .gitignore and licence unticked, and add the repo to the Claude GitHub App's access. Then attach it and push.

Keep it private until Phase 2.4 passes.

## Pre-filled links

Whenever the person has to do something on github.com or claude.ai, give them a link with everything filled in. `scripts/prefill_link.py` builds the GitHub ones, URL-encodes the values, and warns when something is too long to fit in a URL:

| Step | Link |
|---|---|
| Create a repo | `prefill_link.py new-repo --name <repo> [--public] --description "<text>"` → `https://github.com/new?name=…&visibility=private&description=…`. Tell them to leave README, .gitignore and licence unticked when you will push existing history. |
| Fork the Exchange | `prefill_link.py fork` → `https://github.com/tenable/cyberagents-exchange/fork` |
| Add a listing file in the browser | `prefill_link.py new-file --owner ME --dir skills --filename SLUG.md --content-file "$WORK/listings/SLUG.md"` → the file name and contents are pre-filled |
| Open the PR | `prefill_link.py pr --owner ME --branch add-SLUG --title "Add listing: <Name>" --body-file "$WORK/pr-SLUG.md"` → the compare page with title and body pre-filled |
| Add a licence | `prefill_link.py license --owner O --repo R --template mit` → GitHub's licence picker, pre-selected. For Tenable employees, they must still change the copyright holder to Tenable, Inc. |
| Link GitHub to Claude | the connect link a repo-access check returns, or `https://claude.ai/customize/connectors` |
| Install the Claude GitHub App | `https://github.com/apps/claude/installations/select_target` |
| Add a repo to the App's access | `https://github.com/settings/installations` → Claude → Configure |
| Make a repo public (manual) | `https://github.com/<owner>/<repo>/settings`, under Danger Zone → Change visibility. Only after the Phase 2.4 scan is clean. |

## Browser route (no usable GitHub API from the sandbox)

Prepare everything first: the validated listing files, the PR title and the PR body. Then guide the person through these steps in their own browser. If the session has a Claude browser tool and the person asks you to, you may drive the steps, showing each page before submitting anything.

1. Fork https://github.com/tenable/cyberagents-exchange (Fork → Create fork).
2. Open the pre-filled new-file link (`prefill_link.py new-file --owner ME --dir TYPE_DIR --filename SLUG.md --content-file "$WORK/listings/SLUG.md"`). The file name and contents arrive filled in; if the script says the contents were too long, paste them instead.
3. Choose **Create a new branch** named `add-SLUG`, then **Propose changes**.
4. On the compare page, make sure the base is `tenable/cyberagents-exchange` `main`, paste the title and body, then **Create pull request**.
5. For a multi-listing repo, repeat steps 2–4 once per listing, each on its own branch.

Ask the person for each PR URL afterwards so you can record it in `submission-plan.json` and link the siblings.
