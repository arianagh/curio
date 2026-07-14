# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

Prefer `make` targets over calling `uv run` directly:

```
make test         # uv run pytest
make lint         # uv run ruff check .
make fmt-check    # uv run ruff format --check .
make types        # uv run mypy src
make check        # all of the above
```

Single test: `uv run pytest path/to/test_file.py::test_name`.

Run the app (no Makefile target yet): `cd src && uv run python manage.py runserver`.

`make migrate`/`migrations`/`superuser`/`shell` already `cd src` before invoking
`manage.py` — no need to `cd` yourself for those.

## Layout

- `src/curio/` — the Django project package (settings, urls, asgi/wsgi).
- `src/manage.py` — Django's CLI entrypoint; everything Django-related runs from `src/`.

Django + django-ninja (not DRF) for the API layer, Python 3.14 managed by `uv`, local
Ollama reachable via `OLLAMA_BASE_URL`, and our workflow slash commands in
`.claude/commands/` (`/branch`, `/commit`, `/verify`, `/pr`, `/docs`, `/release`).