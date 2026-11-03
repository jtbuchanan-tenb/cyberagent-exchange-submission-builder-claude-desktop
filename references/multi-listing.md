# Several Exchange listings from one repository

## The policy

The CyberAgents Exchange **prefers one repository per listing**. A dedicated repo means:
- the listing's `github_url` points at exactly what is reviewed;
- the README, licence, issues and history belong to that one component;
- reviewers, and later the vetting review pinned to a commit, can scope the work cleanly.

The Exchange **will** accept several listings from one repository in exceptional circumstances. The precedent is SentinelOne's `ai-siem` monorepo:
- An MCP server lives at `mcp/s1-secops-mcp` → https://exchange.tenable.com/mcp-servers/sentinelone-s1-secops-mcp/ with `github_url: https://github.com/Sentinel-One/ai-siem/tree/main/mcp/s1-secops-mcp`.
- A skill bundle lives at `plugins/s1-secops-skills` → https://exchange.tenable.com/skills/sentinelone-ai-analyst-claude-skills/ with `github_url: https://github.com/Sentinel-One/ai-siem/tree/main/plugins/s1-secops-skills`.
- The skill listing's body says plainly that the MCP server is bundled in the same repository, with its own separate listing.

## How to raise it with the person

When `detect_components.py` reports more than one component, show the inventory and say something like:

> Your repo contains **3 listable components**: an MCP server (`mcp/server`), a skill bundle (`plugins/skills`) and an n8n workflow (`workflows/triage`). The Exchange prefers one repository per listing. That gives each listing its own README, licence and history, and keeps reviews scoped. How would you like to proceed?
> 1. **Split into separate repos** (recommended). I can help extract each folder with its history.
> 2. **Submit just one component now**, and handle the others later.
> 3. **Keep one repo with several listings.** The Exchange accepts this only in exceptional cases. What makes this one exceptional?

Accept option 3 only with a concrete reason. Good examples:
- a vendor or platform monorepo whose components share code and release together;
- a skill bundle that ships the MCP server it depends on;
- components that can't be used independently.

"Convenience" is not a reason. Record the reason in the person's words in `submission-plan.json`; it goes in every PR body for the maintainers.

Grouping matters too. Several `SKILL.md` files under one plugin (`.claude-plugin/plugin.json`) or one `skills/` folder are usually **one bundle listing**, like the SentinelOne skills listing. Recommend that, and split skills into separate listings only when each one is meaningfully standalone.

## Splitting a component into its own repo (option 1)

Extract the folder's history locally and **scan it before it goes anywhere**:

```bash
cd "$WORK/repo"
git subtree split --prefix=<path/to/component> -b split/<component>      # history of that folder only
git clone -q --branch split/<component> "$WORK/repo" "$WORK/split-<component>"
python3 -I "$SKILL_DIR/scripts/secret_scan.py" "$WORK/split-<component>"
```

Then, with the scan clean:
1. The person creates a new **private**, empty repo under their personal account. On the REST route that is the pre-filled `https://github.com/new?name=<new-repo>&visibility=private` link; on the CLI route, `gh repo create --private`.
2. Attach the repo, then push (after confirming):
   ```bash
   git -C "$WORK/split-<component>" push https://github.com/<owner>/<new-repo>.git split/<component>:main
   ```
3. Add a README and LICENSE at its root, then run Phase 2 against the new repo (licence and copyright, archive policy, and 2.5 to make it public). It is a different repository, so it goes through the same gates.

## The exception path (option 3): what changes

**Done once for the repo:** Phase 2 as normal (EMU check, visibility, the full-history secret scan, archive policy, the root licence and Tenable copyright gate).

**Done per listing:**

| Item | Rule |
|---|---|
| Listing root | The component's folder. Run every "repo root" check against this folder. For a skill, `SKILL.md` sits at the folder root, or under a plugin's `skills/` for a bundle. |
| `github_url` | `https://github.com/<owner>/<repo>/tree/<default-branch>/<path>`. Use the real default branch, not an assumed `main`. A component at the repo root keeps the plain repo URL. |
| README | The folder needs its own README covering what it does, prerequisites, how to run it, outputs and known limitations. A root README section is not enough, because reviewers open the `github_url`. Offer to draft one. |
| Licence | The folder's own licence file if it has one, otherwise the root licence. The `license` field must match whichever applies, and differing folder licences must be confirmed. |
| Installation instructions | Specific to the component's folder (correct `cd` paths and the right manifest), and for each declared platform or client. |
| `name` / `description` | Distinct per listing, so the listings don't read as duplicates. Prefix with the product name when it helps ("Acme Platform: MCP Server", "Acme Platform: Claude Skills"). |
| Slug | Unique across `agents/`, `skills/`, `mcp-servers/` and `playbooks/`. |
| Body | Includes a sentence naming the sibling listings and how they relate. |
| Pull request | **One PR per listing, on its own `add-<slug>` branch.** The checklist requires each PR to add exactly one file. |
| Vocabulary edits | Make the identical `validator.py` insertion in each PR that needs it. Identical edits merge cleanly after the first PR is squash-merged. |

**Order of PRs:** open the component other listings depend on first (usually the MCP server). Sibling bodies can then point at it. Once all PRs exist, update each PR body's "Sibling listings" section with the other PR links (`pr-workflow.md` → "Linking sibling PRs").

**Interview batching:** ask the shared fields once (author, agreement date, date added, licence), then go listing by listing. Show all the finished listing files together for one final review before opening any PR, so the person sees the whole set side by side.
