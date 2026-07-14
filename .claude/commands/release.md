---
description: Write GitHub Release notes for a tag
argument-hint: <tag>  e.g. v0.3-async
allowed-tools: Bash(git log:*), Bash(git describe:*), Bash(git tag:*)
---
Find the commits included in this release for tag **$ARGUMENTS**:
1. Run `git describe --tags --abbrev=0 HEAD^` to find the previous tag.
   (If that errors, there's no previous tag — this is the first release; use
   `git log --oneline` instead.)
2. Run `git log <previous-tag>..HEAD --oneline` to list the commits in this release.

Then write concise GitHub Release notes for tag **$ARGUMENTS**:
- 3–6 bullets of what this phase adds (plain language, no hype)
- one final line: what a learner practices in this phase

Output just the notes, ready to paste into `gh release create $ARGUMENTS --notes-file -`.