# Ship — Rebase Stage

You are running the **rebase** stage of the ship pipeline. Your job is to rebase the feature branch onto the parent branch, resolve any conflicts, verify the result, and land the branch via PR or local merge.

This is a **single context window** — complete all steps in one pass. Do NOT decompose into separate task iterations.

---

## Context

- **Parent branch**: `{parent_branch}`
- **Clean summary**: {clean_summary}
- **Test summary**: {test_summary}
- **Context files**: {context_files}

---

## Steps

### 1. Confirm Target Branch

1. Verify the parent branch `{parent_branch}` exists: `git rev-parse --verify {parent_branch}`
2. Verify you are NOT already on the parent branch: `git branch --show-current`
3. If either check fails, STOP and report the error — do not proceed with rebase

### 2. Prepare

1. Check for uncommitted changes: `git status --porcelain`
   - If uncommitted changes exist, commit them with message `chore: commit uncommitted work before rebase`
2. Fetch latest from remote (if remote exists): `git fetch origin {parent_branch}`
   - If fetch fails (no remote), continue with local branch — this is expected for local-only repos
3. Create a safety backup ref before rebase:
   ```bash
   git branch safety-backup-pre-rebase
   ```
   - This ref lets you restore the branch if anything goes wrong: `git reset --hard safety-backup-pre-rebase`

### 3. Execute Rebase

1. Rebase onto the parent branch:
   ```bash
   git rebase {parent_branch}
   ```
2. If the rebase completes cleanly (exit code 0), proceed to Step 4
3. If conflicts arise, proceed to conflict resolution (Step 3a)

### 3a. Resolve Conflicts

If `git rebase` reports conflicts:

1. Run `git status` to identify conflicted files
2. For each conflicted file:
   - Read the file to understand both sides of the conflict
   - Resolve the conflict by keeping the intent of the feature branch changes while incorporating parent branch updates
   - Stage the resolved file: `git add <file>`
3. Continue the rebase: `git rebase --continue`
4. If more conflicts arise, repeat this process
5. If conflicts are unresolvable (e.g., fundamental incompatibility):
   - Abort the rebase: `git rebase --abort`
   - Report which files had unresolvable conflicts and why
   - The safety backup ref is still intact

### 4. Verify

After the rebase completes successfully:

1. Run the project's linter on all source files in the working set to ensure no lint regressions
2. Run the project's test suite (scoped to the working set) to ensure all tests pass
3. If lint or tests fail:
   - Investigate and fix the issue (likely a merge resolution error)
   - Commit the fix with message `fix: resolve post-rebase lint/test failure`
   - Re-run lint and tests to confirm the fix
4. If unfixable failures remain after 2 attempts:
   - Document the failures
   - Continue to Step 5 — report them in the summary

### 5. Land the Branch

Determine the landing strategy based on the environment:

#### 5a. Check for Remote and GitHub CLI

```bash
git remote -v
gh auth status
```

#### 5b. If Remote Exists and `gh` is Authenticated — Create PR

1. Check for a PR template in the repository:
   - Look for `.github/PULL_REQUEST_TEMPLATE.md` or `.github/pull_request_template.md`
   - Also check `.github/PULL_REQUEST_TEMPLATE/` directory for multiple templates
2. Determine PR title from branch name or most recent commit message
3. Build PR body:
   - If a PR template exists, fill it in with relevant information
   - If no PR template found, use this default structure:
     ```
     ## Summary
     [Brief description of what this branch does]

     ## Changes
     ### Clean stage
     {clean_summary}

     ### Test stage
     {test_summary}

     ## Verification
     - [ ] Lint passes
     - [ ] Tests pass
     - [ ] Rebased onto {parent_branch}
     ```
4. Create the PR:
   ```bash
   gh pr create --base {parent_branch} --title "<title>" --body "<body>"
   ```
5. Report the PR URL in the summary

#### 5c. If No Remote or `gh` Not Authenticated — Local Merge

1. Check if the target branch has uncommitted work:
   ```bash
   git stash list
   git checkout {parent_branch}
   git status --porcelain
   ```
2. **If the target branch is clean** (no uncommitted changes):
   ```bash
   git merge --ff-only <feature-branch>
   ```
   - If fast-forward merge fails, report that manual merge is needed
3. **If the target branch is dirty** (uncommitted changes):
   - Stash the changes on the target branch:
     ```bash
     read -p "Target branch {parent_branch} has uncommitted work. Stash and merge? [y/N]: " approve
     ```
   - If approved (`y` or `Y`):
     ```bash
     git stash push -m "auto-stash before ship merge"
     git merge --ff-only <feature-branch>
     git stash pop
     ```
   - If stash pop has conflicts, warn the user and leave the stash intact
   - If declined or no response: abort merge, switch back to feature branch, report that manual merge is needed
4. After local merge, clean up the feature branch:
   ```bash
   git branch -d <feature-branch>
   ```

### 6. Clean Up

1. Delete the safety backup ref:
   ```bash
   git branch -d safety-backup-pre-rebase
   ```
2. If the safety ref deletion fails (branch doesn't exist), that's fine — continue

---

## Completion

After completing all steps, output a summary and the completion signal.

Summary should include:
- Rebase result (clean or conflicts resolved)
- Verification result (lint + tests pass/fail)
- Landing method (PR created with URL, or local merge)
- Any issues encountered

**When done, output:**
```json
{"status": "SHIP_COMPLETE", "summary": "<brief summary of rebase, verify, and landing result>"}
```

---

## Rules

- Always create the safety backup ref before rebasing — this is your rollback path
- Resolve conflicts by preserving the intent of the feature branch while incorporating parent updates
- Never force-push to the parent branch
- Always verify (lint + tests) after rebase before landing
- PR description should reference the clean and test summaries so reviewers have context

**Do NOT:**
- Force-push to any branch (`--force` or `--force-with-lease` on shared branches)
- Delete the safety backup ref until AFTER successful landing
- Skip verification (lint + tests) after rebase
- Modify production code during rebase — only resolve conflicts
- Create a PR if `gh auth status` fails — use the local merge fallback instead
- Merge without fast-forward unless explicitly required by conflict resolution
