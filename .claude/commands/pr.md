---
description: Draft a PR description and the gh command for the current branch
allowed-tools: Bash(git diff:*), Bash(git log:*), Bash(git branch:*)
---
## This branch vs master
!`git log master..HEAD --oneline`
!`git diff master...HEAD --stat`

Write a PR description with short sections:
- **Summary** — what changed and why
- **What changed** — the notable pieces
- **How to test** — exact commands
- **For learners** — what a reader of this teaching repo should notice about the approach

Then give me the exact `gh pr create` command with a clear title and this body.