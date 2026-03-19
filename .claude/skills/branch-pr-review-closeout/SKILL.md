---
name: branch-pr-review-closeout
description: Standardize the finish-a-task workflow after implementation is complete. Use this skill to create PRs, review before merge, clean up branches, and close out cards.
allowed-tools:
  - Bash
  - Read
---

# Branch, PR, Review, and Closeout Workflow

## Pre-flight checks

1. Verify the working tree is clean: `git status` shows no uncommitted changes.
2. Verify all commits are pushed to the private remote: `git log --oneline origin/<branch>..HEAD` shows nothing.
3. Confirm verification passed (tests, checks, no secrets in diff).

## Open a pull request

1. Push the branch to origin if not already pushed:
   ```
   git push -u origin <branch-name>
   ```
2. Open a PR against `main` using `gh pr create`.
3. Write a clear PR title and description summarizing the card scope and changes.

## Review checklist before merge

Before merging, confirm:

- [ ] Diff matches the card scope.
- [ ] No secrets, `.env` values, or credentials in the diff.
- [ ] Tests pass (backend and/or frontend as applicable).
- [ ] Documentation updated only if something changed in developer workflow or architecture.
- [ ] No unrelated changes included.

## Merge strategy

- **Prefer squash merge** unless there is a strong reason to preserve individual commits (e.g., multiple logically distinct changes that benefit from separate history).
- Squash merge keeps `main` history clean and card-aligned.

## Post-merge cleanup

1. **Delete the remote branch** after merge:
   ```
   git push origin --delete <branch-name>
   ```
2. **Local branch deletion** depends on worktree state:
   - If using a git worktree for this branch, remove the worktree first, then delete the branch.
   - If on a regular checkout, switch to `main` and delete the local branch:
     ```
     git checkout main && git branch -d <branch-name>
     ```
3. **Sync local main**:
   ```
   git checkout main && git pull origin main
   ```

## Vibe Kanban card status

- Only move the Vibe card to **Done** after:
  - PR is merged.
  - Remote branch is deleted.
  - Local main is synced.
- Do not mark Done before merge.

## Important distinctions

- **Remote branch deletion**: safe after merge; always do it.
- **Local branch deletion**: may require worktree cleanup first; handle accordingly.
- **Vibe workspace cleanup**: separate concern from git branch cleanup.
