---
description: Write GitHub Release notes for a tag
argument-hint: <tag>  e.g. v0.3-async
allowed-tools: Bash(git log:*), Bash(git describe:*)
---
## Commits in this release
!`git log $(git describe --tags --abbrev=0 HEAD^ 2>/dev/null)..HEAD --oneline 2>/dev/null || git log --oneline -20`

Write concise GitHub Release notes for tag **$ARGUMENTS**:
- 3–6 bullets of what this phase adds (plain language, no hype)
- one final line: what a learner practices in this phase

Output just the notes, ready to paste into `gh release create $ARGUMENTS --notes-file -`.