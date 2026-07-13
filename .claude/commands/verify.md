---
description: Run the full local quality gate and fix any failures
allowed-tools: Bash(uv run:*)
---
Run the local quality gate, and fix anything that fails, then re-run until it's green:

1. `uv run ruff check .`
2. `uv run ruff format --check .`
3. `uv run mypy src`
4. `uv run pytest`

Report what failed and exactly what you changed to fix it. If a failure is a real
test catching a real bug, fix the code — do not weaken the test to make it pass.