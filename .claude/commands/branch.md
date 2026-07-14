---
description: Start a phase branch fresh off the latest master
argument-hint: <type/slug>  e.g. feat/phase-2-async
allowed-tools: Bash(git switch:*), Bash(git pull:*), Bash(git fetch:*), Bash(git status)
---
Start a clean working branch off the latest master:
1. `git switch master`
2. `git pull`
3. `git switch -c $ARGUMENTS`

Confirm we're on the new branch and it's up to date with origin/master.
