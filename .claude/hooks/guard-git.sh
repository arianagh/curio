#!/usr/bin/env bash
# guard-git.sh — PreToolUse hook (Bash tool) for a public teaching repo.
# Enforces two rules in code so they don't depend on Claude remembering them:
#   1. never force-push (it rewrites shared history on a public repo)
#   2. never commit straight to main (use a phase branch)
#
# Claude Code pipes the tool call to us as JSON on stdin. We read tool_input.command,
# and if it breaks a rule we print a reason to stderr and exit 2 (which blocks the
# tool call and shows Claude the reason so it can correct course). exit 0 = allow.
# Requires: jq  (Ubuntu: sudo apt install jq)

INPUT=$(cat)
CMD=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty')

# 1) block force-push
if printf '%s' "$CMD" | grep -Eq 'git +push.*(--force|-f)([[:space:]]|$)'; then
  echo "Blocked: force-push is disabled on this public repo (it rewrites shared history)." >&2
  exit 2
fi

# 2) block commits made while on master
if printf '%s' "$CMD" | grep -Eq 'git +commit'; then
  BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
  if [ "$BRANCH" = "master" ]; then
    echo "Blocked: you're on master. Start a phase branch first, e.g. git switch -c feat/phase-N-slug" >&2
    exit 2
  fi
fi

exit 0