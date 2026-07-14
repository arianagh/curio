# Contributing

Curio is built one phase at a time, straight from `master`. The loop is always the
same: **phase → branch → PR → tag.**

## The loop

1. **Branch** off the latest `master` for the phase you're working on:
   ```
   git switch master && git pull
   git switch -c feat/phase-N-slug
   ```
2. **Build** the phase, running `make check` (lint, format-check, type-check, test)
   before you consider it done.
3. **Commit** in small, Conventional Commits — `feat`, `fix`, `test`, `docs`,
   `refactor`, `chore`, `ci`, `build`.
4. **PR** the branch against `master`, describing what the phase adds and how to
   verify it.
5. **Tag** the merge commit once it lands (`vX.Y`, matching the phase), and write
   release notes.

Never commit directly to `master` or force-push — both are blocked by this repo's
`guard-git` hook.

## Claude Code slash commands

If you're using Claude Code, these commands drive each step of the loop:

| Command | Does |
|---|---|
| `/branch <type/slug>` | Cuts a fresh phase branch off `master` |
| `/verify` | Runs the full local quality gate and fixes failures |
| `/commit` | Drafts a Conventional Commit message from staged changes |
| `/pr` | Drafts a PR description and the `gh pr create` command |
| `/docs` | Updates the README and adds an ADR under `docs/adr/` for real decisions |
| `/release <tag>` | Drafts GitHub Release notes for a tag |

## Style

- Work happens under `src/`; each new feature gets its own Django app, registered in
  `INSTALLED_APPS`.
- `uv run <cmd>` (or the matching `make` target) for everything Python — no bare
  `python`/`pip`.
- Document real architectural decisions as an ADR (`docs/adr/`), not inline in code
  comments.
