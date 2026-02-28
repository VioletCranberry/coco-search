---
name: cocosearch-review-pr
description: Use when reviewing a GitHub PR or GitLab MR by URL. Fetches diff and metadata via API, then uses CocoSearch for blast radius analysis, dependency impact, pattern consistency, and test coverage assessment.
---

# PR/MR Review with CocoSearch

A structured workflow for reviewing pull requests (GitHub) or merge requests (GitLab) using CocoSearch's semantic search and dependency analysis. Goes beyond line-by-line diff reading to assess blast radius, dependency impact, pattern consistency, and test coverage.

**What this skill adds over manual review:**

- **Blast radius:** For each changed file, see what else in the codebase depends on it
- **Dependency context:** Understand what the changed code relies on
- **Pattern consistency:** Find similar patterns elsewhere to check if changes are consistent
- **Test coverage:** Verify that tests exist for the changed code
- **Missing changes:** Identify files that should have changed but didn't

## Pre-flight Check

1. Read `cocosearch.yaml` for `indexName` (critical -- use this for all operations)
2. **Inventory API tokens.** Check which tokens are available before anything else:

   ```bash
   python3 -c "
   import os
   tokens = {
       'GITHUB_TOKEN': bool(os.environ.get('GITHUB_TOKEN')),
       'GH_TOKEN': bool(os.environ.get('GH_TOKEN')),
       'GITLAB_TOKEN': bool(os.environ.get('GITLAB_TOKEN')),
       'GITLAB_PAT': bool(os.environ.get('GITLAB_PAT')),
   }
   found = [k for k, v in tokens.items() if v]
   print(f'Available tokens: {found if found else \"none\"}')"
   ```

   Record what's available. If nothing found, warn early: "No API tokens detected -- will need one after determining platform."

3. `list_indexes()` to confirm project is indexed
4. `index_stats(index_name="<configured-name>")` to check freshness
   - No index -> offer to index before reviewing. Review without search data misses the value of this skill.
   - Stale (>7 days) -> warn: "Index is X days old -- blast radius analysis may not reflect recent changes. Want me to reindex first?"
5. Check dependency freshness -- call `get_file_dependencies` on any known file (e.g., the first changed file from the PR):

   ```
   get_file_dependencies(file="<any-known-file>", depth=1)
   ```

   - **If response contains `warnings`** with type `deps_outdated` or `deps_branch_drift`:
     Warn: "Dependency data is outdated -- blast radius analysis may be incomplete. Want me to re-extract dependencies first? (`index_codebase` with `extract_deps=True`)"
   - **If response contains `warnings`** with type `deps_not_extracted`:
     Warn: "No dependency data found. Blast radius and impact analysis will be limited to search-only. Want me to extract dependencies first?"
   - **If no warnings:** Proceed normally.
6. Parse the PR/MR URL to detect platform:
   - `github.com/{owner}/{repo}/pull/{number}` -> GitHub
   - `{host}/{group}/{project}/-/merge_requests/{iid}` -> GitLab (self-hosted or gitlab.com)
   - If no URL provided, ask: "Which PR/MR should I review? Paste the URL."
7. **Match platform to tokens:**
   - **GitHub:** prefer `GITHUB_TOKEN` over `GH_TOKEN`. If neither set: "Set `GITHUB_TOKEN` (or `GH_TOKEN`) to access the GitHub API. Create one at https://github.com/settings/tokens (needs `repo` scope for private repos, no scope needed for public repos)." Stop.
   - **GitLab:** prefer `GITLAB_TOKEN` over `GITLAB_PAT`. If neither set: "Set `GITLAB_TOKEN` (or `GITLAB_PAT`) to access the GitLab API. Create one at `https://{host}/-/user_settings/personal_access_tokens` (needs `read_api` scope)." Stop.
8. Verify API access with a lightweight call (fetch PR/MR metadata -- Step 1 below). If it fails with 401/403, report the auth error and stop.

## Step 1: Fetch PR/MR Data

### GitHub

**Fetch metadata (Python -- primary):**

```bash
python3 << 'PYEOF'
import json, os, sys, urllib.request, urllib.error

token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN", "")
if not token:
    print("Error: No GitHub token found (checked GITHUB_TOKEN, GH_TOKEN)", file=sys.stderr)
    sys.exit(1)

url = "https://api.github.com/repos/{owner}/{repo}/pulls/{number}"
req = urllib.request.Request(url, headers={
    "Authorization": f"Bearer {token}",
    "Accept": "application/vnd.github+json",
})
try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())
        print(json.dumps({
            "title": data["title"],
            "body": (data.get("body") or "")[:500],
            "author": data["user"]["login"],
            "state": data["state"],
            "base_branch": data["base"]["ref"],
            "head_branch": data["head"]["ref"],
            "additions": data["additions"],
            "deletions": data["deletions"],
            "changed_files": data["changed_files"],
        }, indent=2))
except urllib.error.HTTPError as e:
    print(f"GitHub API error {e.code}: {e.read().decode()}", file=sys.stderr)
    sys.exit(1)
PYEOF
```

**Fallback (curl):**

```bash
curl -sf -H "Authorization: Bearer ${GITHUB_TOKEN:-$GH_TOKEN}" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/{owner}/{repo}/pulls/{number}"
```

**Fetch changed files (Python -- primary):**

```bash
python3 << 'PYEOF'
import json, os, sys, urllib.request, urllib.error

token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN", "")
url = "https://api.github.com/repos/{owner}/{repo}/pulls/{number}/files?per_page=100"
all_files = []
while url:
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            all_files.extend(json.loads(resp.read().decode()))
            # Follow Link header for pagination
            link = resp.headers.get("Link", "")
            url = None
            for part in link.split(","):
                if 'rel="next"' in part:
                    url = part.split("<")[1].split(">")[0]
    except urllib.error.HTTPError as e:
        print(f"GitHub API error {e.code}: {e.read().decode()}", file=sys.stderr)
        sys.exit(1)

for f in all_files:
    print(json.dumps({
        "filename": f["filename"],
        "status": f["status"],
        "additions": f["additions"],
        "deletions": f["deletions"],
        "patch": f.get("patch", "")[:2000],
    }))
PYEOF
```

**Fallback (curl):**

```bash
curl -sf -H "Authorization: Bearer ${GITHUB_TOKEN:-$GH_TOKEN}" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/{owner}/{repo}/pulls/{number}/files?per_page=100"
```

For PRs with >100 files, pagination is handled automatically by the Python script (follows `Link` header). With curl, paginate manually with `&page=2`, `&page=3`, etc.

### GitLab

**Fetch metadata (Python -- primary):**

```bash
python3 << 'PYEOF'
import json, os, sys, urllib.request, urllib.error

token = os.environ.get("GITLAB_TOKEN") or os.environ.get("GITLAB_PAT", "")
if not token:
    print("Error: No GitLab token found (checked GITLAB_TOKEN, GITLAB_PAT)", file=sys.stderr)
    sys.exit(1)

url = "https://{host}/api/v4/projects/{id}/merge_requests/{iid}"
req = urllib.request.Request(url, headers={"PRIVATE-TOKEN": token})
try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())
        print(json.dumps({
            "title": data["title"],
            "description": (data.get("description") or "")[:500],
            "author": data["author"]["username"],
            "state": data["state"],
            "target_branch": data["target_branch"],
            "source_branch": data["source_branch"],
            "changes_count": data.get("changes_count"),
        }, indent=2))
except urllib.error.HTTPError as e:
    print(f"GitLab API error {e.code}: {e.read().decode()}", file=sys.stderr)
    sys.exit(1)
PYEOF
```

Note: `{id}` is the URL-encoded project path (e.g., `group%2Fproject`) or numeric project ID.

**Fallback (curl):**

```bash
curl -sf -H "PRIVATE-TOKEN: ${GITLAB_TOKEN:-$GITLAB_PAT}" \
  "https://{host}/api/v4/projects/{id}/merge_requests/{iid}"
```

**Fetch changed files with diffs (Python -- primary):**

```bash
python3 << 'PYEOF'
import json, os, sys, urllib.request, urllib.error

token = os.environ.get("GITLAB_TOKEN") or os.environ.get("GITLAB_PAT", "")
url = "https://{host}/api/v4/projects/{id}/merge_requests/{iid}/diffs?per_page=100"
all_diffs = []
while url:
    req = urllib.request.Request(url, headers={"PRIVATE-TOKEN": token})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            all_diffs.extend(json.loads(resp.read().decode()))
            # Follow x-next-page header for pagination
            next_page = resp.headers.get("x-next-page", "")
            if next_page:
                base = url.split("?")[0]
                url = f"{base}?per_page=100&page={next_page}"
            else:
                url = None
    except urllib.error.HTTPError as e:
        print(f"GitLab API error {e.code}: {e.read().decode()}", file=sys.stderr)
        sys.exit(1)

for d in all_diffs:
    print(json.dumps({
        "old_path": d["old_path"],
        "new_path": d["new_path"],
        "new_file": d.get("new_file", False),
        "renamed_file": d.get("renamed_file", False),
        "deleted_file": d.get("deleted_file", False),
        "diff": d.get("diff", "")[:2000],
    }))
PYEOF
```

**Fallback (curl):**

```bash
curl -sf -H "PRIVATE-TOKEN: ${GITLAB_TOKEN:-$GITLAB_PAT}" \
  "https://{host}/api/v4/projects/{id}/merge_requests/{iid}/diffs?per_page=100"
```

For MRs with >100 diffs, pagination is handled automatically by the Python script (follows `x-next-page` header). With curl, paginate manually with `&page=2`, etc.

### Present PR Summary

Before proceeding with analysis, show:

```
## PR #{number}: {title}
Author: {author} | Target: {base_branch} <- {head_branch}
Files changed: {count} | +{additions} -{deletions}

Description:
{body/description, first ~500 chars}
```

### Branch Setup

After presenting the summary, check whether the local branch matches the PR's source branch for accurate analysis.

1. **Save current branch:**

   ```bash
   ORIGINAL_BRANCH=$(git rev-parse --abbrev-ref HEAD)
   ```

2. **Compare with `{head_branch}`** from PR metadata.

3. **If they match:** Note "Local branch matches PR -- analysis reflects PR changes." Set `SWITCHED_BRANCH=false`. Proceed to checkpoint.

4. **If they differ:**

   - Check for uncommitted changes:

     ```bash
     git status --porcelain
     ```

   - If dirty: warn "You have uncommitted changes" and offer `git stash` first.
   - Present options:
     - **Switch branches** -- `git stash` (if dirty), `git fetch origin {head_branch}`, `git checkout {head_branch}`, then `index_codebase()` + `index_codebase(extract_deps=True)` to reindex on the PR branch. Set `SWITCHED_BRANCH=true`. Note: "Earlier freshness checks are superseded by fresh indexing."
     - **Stay on current branch** -- set `SWITCHED_BRANCH=false`, proceed with caveat: "Analysis may miss PR-specific additions since the local branch differs."
   - If the branch doesn't exist locally or on the remote: note the issue, set `SWITCHED_BRANCH=false`, proceed on current branch.

**Checkpoint:** "Ready to analyze {count} changed files. Proceed?"

## Step 2: Triage Changed Files

Categorize files by review priority:

| Priority | File types | Examples |
|----------|-----------|---------|
| **HIGH** | Source code | `.py`, `.js`, `.ts`, `.go`, `.rs`, `.java`, `.rb`, `.scala` |
| **MEDIUM** | Tests, config, CI/CD | `test_*.py`, `*.test.ts`, `*.yaml`, `Dockerfile`, `.github/workflows/` |
| **LOW** | Docs, changelog, assets | `.md`, `CHANGELOG`, `.png`, `.svg`, `LICENSE` |

**Present the triage:**

```
HIGH priority (source code): N files
  - src/module/core.py (+45 -12)
  - src/module/utils.py (+8 -3)

MEDIUM priority (tests/config): M files
  - tests/test_core.py (+20 -5)
  - .github/workflows/ci.yaml (+2 -1)

LOW priority (docs): K files
  - README.md (+10 -2)
```

**For large PRs (30+ files):** "This is a large PR with {count} files. Want me to review all HIGH-priority files, or focus on specific files/directories?"

**For small PRs (<10 files):** Review all files without asking.

## Step 3: Per-File Analysis

This is the CocoSearch-powered core. For each HIGH-priority file, run these analyses. Run independent queries in parallel where possible.

### 3a. Blast Radius

```
get_file_impact(file="<changed_file>", depth=2)
```

Identifies what other files depend on this one. A file with many dependents is high-risk -- changes to its interface affect everything downstream.

**Classify:**

| Dependents | Impact level |
|-----------|-------------|
| 0 | Leaf file -- low risk |
| 1-5 | Moderate -- review dependents |
| 6-15 | High -- check for interface changes |
| 16+ | Critical hub -- extra scrutiny |

### 3b. Dependencies

```
get_file_dependencies(file="<changed_file>", depth=1)
```

Understand what the changed file relies on. Useful for spotting if the PR modifies assumptions that dependencies make.

### 3c. Pattern Consistency

For each changed file, search for similar patterns elsewhere in the codebase:

```
search_code(
    query="<semantic description of the change>",
    use_hybrid_search=True,
    smart_context=True
)
```

For example, if a file changes how errors are handled, search for error handling patterns across the codebase to check if this change is consistent or introduces a divergence.

### 3d. Test Coverage

Search for tests that cover the changed symbols:

```
search_code(
    query="test <primary_symbol_name>",
    symbol_name="test_*<symbol>*",
    symbol_type="function",
    use_hybrid_search=True
)
```

**Coverage assessment:**

- **Covered:** Tests exist and appear to exercise the changed code
- **Partially covered:** Tests exist but may not cover the specific change
- **Missing:** No tests found for this code
- **New code, no tests:** Flag for reviewer attention

### 3e. Diff Analysis

Review the actual diff content (from the patch/diff fetched in Step 1) for each file:

- **Logic errors:** Off-by-one, wrong comparisons, missing edge cases
- **Security issues:** Unsanitized input, injection risks, exposed secrets
- **Error handling:** Missing try/catch, swallowed exceptions, unhelpful error messages
- **API contract changes:** Modified function signatures, changed return types, new required parameters

### Per-File Output

For each HIGH-priority file, produce:

```
#### `path/to/file.py` [{IMPACT_LEVEL} - {N} dependents]

**Blast radius:** {N} files depend on this. Top dependents: {list top 3-5}
**Dependencies:** Relies on {M} internal modules.

**Diff findings:**
- {finding description} [severity: CRITICAL/IMPORTANT/MINOR]
- {finding description} [severity: ...]

**Pattern check:** {Consistent with codebase patterns / Diverges from pattern in X, Y, Z}
**Test coverage:** {Covered / Partially covered / Missing}
```

## Step 4: Cross-Cutting Analysis

After reviewing individual files, look for systemic issues across the entire PR.

### Missing Changes

Check if files that SHOULD have been modified are absent from the PR:

- **Tests for new/modified code:** If source files changed but no test files are in the PR, flag it.
- **Import updates:** If a file was renamed or moved, check if all importers were updated:

```
get_file_impact(file="<renamed_file>", depth=1)
```

Compare the impact list against the PR's changed files. Any dependent NOT in the PR is a potential missed update.

- **Documentation references:** For each changed source file, query documentation dependents:

  ```
  get_file_impact(file="<changed_source_file>", depth=1, dep_type="reference")
  ```

  Filter results for files ending in `.md` or `.mdx`. These are docs that reference
  the changed code. If any doc file is NOT in the PR's changed file list, flag it:

  "**Doc update needed:** `docs/architecture.md` references `src/cli.py`
  (doc_link, line 42) but was not updated in this PR."

  Include metadata.kind and metadata.line to help locate the specific reference.
  If no dependency data exists (deps not extracted), fall back to the manual check:
  "If public API signatures changed, check if docs were updated."

### Hub File Changes

If any changed file has 10+ dependents, highlight it:

"**High-impact change:** `core/models.py` has 18 dependents. Changes to its interface could break downstream consumers. Verify that all callers are compatible with the new behavior."

### Consistency Check

If a pattern was changed in one file, check if the same pattern exists elsewhere and should also change:

```
search_code(
    query="<old pattern that was changed>",
    use_hybrid_search=True,
    smart_context=True
)
```

If results show the old pattern still exists in other files, flag: "Pattern was updated in `file_a.py` but the old version still exists in `file_b.py`, `file_c.py`. Intentional divergence or missed update?"

## Step 5: Present Review

Assemble the full review in this structure:

```
## PR Review: {title}

**Summary:** {1-2 sentence overview of what the PR does}
**Risk Level:** LOW / MEDIUM / HIGH (based on blast radius and findings)
**Files reviewed:** {N} HIGH, {M} MEDIUM, {K} LOW priority

---

### File-by-File Findings

{Per-file output from Step 3, ordered by impact level (highest first)}

---

### Cross-Cutting Concerns

- {Missing changes, if any}
- {Hub file warnings, if any}
- {Consistency issues, if any}

---

### Test Coverage Summary

| File | Coverage | Notes |
|------|----------|-------|
| path/to/file.py | Covered | test_file.py exercises main paths |
| path/to/other.py | Missing | No tests found for new logic |

---

### Verdict

**{APPROVE / REQUEST CHANGES / NEEDS DISCUSSION}**

{If APPROVE: summary of why the changes look good}
{If REQUEST CHANGES: numbered list of blocking issues}
{If NEEDS DISCUSSION: questions that need answers before approval}
```

**Checkpoint:** "Want me to dig deeper into any file or finding? I can also check specific patterns or trace additional dependencies."

### Branch Cleanup

After presenting the review, handle branch lifecycle cleanup.

1. **If `SWITCHED_BRANCH=false`:** Skip -- nothing to clean up.

2. **If `SWITCHED_BRANCH=true`:**

   - Offer: "Review complete. Want me to switch back to `{ORIGINAL_BRANCH}`?"
   - If yes:
     - `git checkout {ORIGINAL_BRANCH}`
     - `git stash pop` (only if we stashed earlier)
     - Optionally: "Want me to reindex for `{ORIGINAL_BRANCH}`? (Only needed if you plan to use CocoSearch on this branch next.)"
   - If no: "Staying on `{head_branch}`. Remember to switch back when done."

3. Final note: "Review of PR #{number} is complete."

## Tips

- **Start with the highest-impact files.** Review files with many dependents first -- they carry the most risk.
- **Use dependency data to verify completeness.** The impact tree tells you what SHOULD have changed alongside a file.
- **Don't flag style nits.** Focus on correctness, security, and blast radius. Leave formatting to linters.
- **Branch lifecycle.** The workflow automatically offers to switch to the PR's branch for accurate analysis and switch back when done. If you skip the switch, blast radius results are based on your current branch.
- **Large PRs benefit from scoping.** Ask the user to focus on specific areas rather than reviewing 50+ files superficially.
- **Re-index if stale.** Blast radius analysis is only as good as the index. If the codebase changed significantly since last index, reindex first.

For common search tips (hybrid search, smart_context, symbol filtering), see `skills/README.md`.

For installation instructions, see `skills/README.md`.
