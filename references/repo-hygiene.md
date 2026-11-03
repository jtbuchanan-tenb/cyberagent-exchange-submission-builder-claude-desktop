# Repository hygiene recommendations for contributors

These are **recommendations, not Exchange requirements**. The requirements are in Phase 2 and the checklist. Offer them once, near the end (Phase 6), tailored to what you saw in the person's repo, and never block a submission on them. They help a listing stay accepted as the repo changes: reviewers re-check congruence on updates, and vetted listings are re-reviewed when the code changes materially.

Pick only the items that apply. Present them as a short list, each with one line on *why*, and offer to add the ones they want. Every change goes through the normal confirmation rule.

## 1. Keep any committed archive identical to the unpacked files

**When:** the repo ships a `.zip`, `.skill`, `.plugin` or similar alongside the unpacked content, for example an uploadable skill zip for Claude Desktop.

**Why:** reviewers extract archives and compare them with the source. A stale archive is a congruence finding, and users who install from it get old instructions.

**Offer:**
- `assets/contributor-workflows/skill-archive-sync.yml` → `.github/workflows/skill-archive-sync.yml` in their repo.
  - On pull requests it fails if the archive no longer matches the files.
  - On the default branch it rebuilds and commits the archive automatically.
  - Set `SKILL_PATH` (the folder with `SKILL.md`) and `ARCHIVE` (its path; `${SKILL_NAME}` is filled in from the frontmatter).
  - The zip's top folder is the skill `name`, as Claude's skill upload requires.
- The alternative: drop the committed archive and attach it to a GitHub Release instead. Then there is nothing in the tree to drift.

## 2. Scan for secrets on every push

**Why:** the Exchange rejects any listing whose history ever contained a credential, and checks again on updates. Catching it on the first push makes the fix a revert rather than a history rewrite plus a key rotation.

**Offer:**
- `assets/contributor-workflows/secret-scan.yml` → `.github/workflows/secret-scan.yml`: gitleaks on every push and PR. It's free for personal-account repos.
- For local protection too, suggest gitleaks' pre-commit hook: https://github.com/gitleaks/gitleaks#pre-commit

## 3. Ignore secret-bearing files

**When:** there's no `.gitignore`, or it doesn't cover `.env`, keys or credential files.

**Offer:** merge the lines from `assets/contributor-workflows/gitignore-security.txt` into their `.gitignore`. Keep their existing entries, and keep any `!.env.example` style exceptions.

## 4. Version the thing users install

**When:** it's a skill, plugin or MCP server that people install and update.

**Why:** a `VERSION` file, or a version in `package.json` / `pyproject.toml` / plugin manifest, plus tagged releases lets users and reviewers tell what changed. A short `CHANGELOG.md` lets reviewers see whether an update is material.

**Offer:** add `VERSION` (or use the manifest's version) and a `CHANGELOG.md` with one entry for this release. Suggest tagging releases (`git tag v1.0.0 && git push --tags`).

## 5. Keep the README in step with the code

**Why:** the reviewers' installation-instructions and congruence checks run again on every update.

**Offer:** a one-line habit for their contributing notes: "When you add a tool, platform, client or outbound call, update the README's install steps and the Exchange listing in the same change."

For an MCP server, a README tool table generated from code prevents drift; the SentinelOne server does this. If the README has no "Known limitations" or "Data flows / outbound calls" section, offer to draft one. Undisclosed outbound calls are a rejection criterion.

## 6. Keep dependencies patched

**When:** the repo has a manifest (`package.json`, `pyproject.toml`, `requirements.txt`, `go.mod`, `Cargo.toml`).

**Offer:** a `.github/dependabot.yml` for that ecosystem, plus GitHub's free secret scanning and push protection: Settings → Code security → Secret Protection. Link them to `https://github.com/<owner>/<repo>/settings/security_analysis`.

## 7. One repo per listing

**When:** they took the multi-listing exception path.

**Why:** if the components start to diverge (separate releases, maintainers or issues), splitting later is harder.

**Offer:** a reminder that `references/multi-listing.md` → "Splitting a component into its own repo" is there when they want it.

## 8. Show it off

After merge:
- add the "Listed on CyberAgents Exchange" badge (Phase 6);
- fill in a contributor profile on the Exchange, which is also an eligibility item if Tenable later selects the listing for vetting.

## Adding these files

Workflow files live in `.github/workflows/`. Some GitHub tokens and apps aren't allowed to push workflow files: a push rejected with a message about `workflow` scope or permission means exactly that.
- **If that happens,** give the person a pre-filled new-file link for each file:
  ```bash
  python3 -I "$SKILL_DIR/scripts/prefill_link.py" new-file --repo <owner>/<repo> --dir .github/workflows \
    --filename secret-scan.yml --content-file "$SKILL_DIR/assets/contributor-workflows/secret-scan.yml"
  ```
  They review the file, then choose **Commit changes**.
- **On the device bridge with `device_bash`,** they can also commit and push the files from their own machine.
