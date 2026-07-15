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

Run the app: `cd src && uv run python manage.py runserver` — this now also serves
the browser UI at `/` (session-authed, separate from the JWT API).

`make migrate`/`migrations`/`superuser`/`shell` already `cd src` before invoking
`manage.py` — no need to `cd` yourself for those.

### UI assets (Tailwind + htmx)

The UI (`src/ui/`) is Django templates + Tailwind CSS v4 + htmx — no Node/npm
toolchain. Tailwind is compiled via its standalone CLI binary, which is not
committed (platform-specific). One-time setup:

```
mkdir -p bin
curl -sLo bin/tailwindcss https://github.com/tailwindlabs/tailwindcss/releases/latest/download/tailwindcss-linux-x64
chmod +x bin/tailwindcss
```

(macOS: substitute `tailwindcss-macos-arm64`/`-x64` in the URL.)

```
make css         # compile src/ui/static_src/css/input.css -> src/ui/static/ui/css/app.css
make css-watch    # same, rebuilding on change
```

The compiled `app.css` and vendored `src/ui/static/ui/js/htmx.min.js` **are**
committed, like any other static asset — only the Tailwind binary itself is
gitignored (`bin/`). Re-run `make css` after adding/changing Tailwind classes
in templates.

## Layout

- `src/curio/` — the Django project package (settings, urls, asgi/wsgi).
- `src/manage.py` — Django's CLI entrypoint; everything Django-related runs from `src/`.
- `src/ui/` — the browser UI: session-authed Django template views (`login`,
  article list/detail/add/delete, htmx-polled status), fully separate from
  the JWT-authed `library`/`accounts` API apps.

Django + django-ninja (not DRF) for the API layer, Python 3.14 managed by `uv`, local
Ollama reachable via `OLLAMA_BASE_URL`, and our workflow slash commands in
`.claude/commands/` (`/branch`, `/commit`, `/verify`, `/pr`, `/docs`, `/release`).