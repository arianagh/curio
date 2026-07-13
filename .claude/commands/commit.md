---
description: Draft a Conventional Commit message from staged changes
allowed-tools: Bash(git diff:*), Bash(git status:*)
---
## Staged changes
!`git diff --cached --stat`
!`git diff --cached`

Draft a Conventional Commits message for the staged changes above:
- `<type>(scope): subject` — under 72 chars. Types: feat, fix, test, docs, refactor, chore, ci, build.
- blank line, then a short body explaining WHY (not a restatement of the diff).

If the staged changes are actually two unrelated things, tell me to split them into
two commits instead of writing one message. Show me the message — do NOT commit yet.