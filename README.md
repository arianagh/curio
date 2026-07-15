# Curio

Curio is a Django + [django-ninja](https://django-ninja.dev/) API, built in public,
one phase at a time. Each phase is a small, reviewable step — a branch, a PR, a tagged
release — so you can follow the whole build from an empty scaffold to a working app.

## What you'll learn

- Structuring a Django project with `src/` layout and one app per feature
- Building a typed HTTP API with django-ninja (schemas, routers, OpenAPI docs) instead
  of Django REST Framework
- Running Python with [`uv`](https://docs.astral.sh/uv/) instead of a plain venv
- Wiring up async work with Celery + Redis
- Running local infra (Postgres, Redis, Ollama) with Docker Compose
- A phase → branch → PR → tag workflow, and using Claude Code slash commands to
  keep that workflow consistent
- Enforcing that workflow with CI: a GitHub Actions quality gate on every PR, an
  image build via `docker buildx bake`, and Dependabot for dependency upkeep
- Exposing the same data through an MCP server (`mcp_server/`) so an AI assistant
  like Claude Code can search and read a user's library directly via the Django
  ORM, reusing the app's existing JWT auth instead of a new mechanism
- Building a browser UI with plain Django templates + htmx instead of a SPA
  framework, styled with Tailwind CSS (compiled via a standalone CLI — no
  Node/npm toolchain) — and running it on Django sessions, a second auth
  mechanism that sits next to the JWT API without either leaking into the other

## Prerequisites

- [`uv`](https://docs.astral.sh/uv/getting-started/installation/) — manages the Python
  version (3.14) and dependencies; nothing else to install by hand
- [Docker](https://docs.docker.com/get-docker/) — runs the local Postgres, Redis, and
  Ollama services
- [`gh`](https://cli.github.com/) — the GitHub CLI, used to open PRs and cut releases

## Quick start

```
uv sync              # install dependencies into .venv
uv run pre-commit install  # optional: run lint/format/type-check on every commit
make infra           # start Postgres + Redis + Ollama (needed for migrate/test below)
make check           # lint + format-check + type-check + test
cd src && uv run python manage.py migrate
cd src && uv run python manage.py runserver
```

`runserver` serves both the JSON API (`/api/v1/`) and the browser UI (`/`) —
see [Try it](#try-it) below for testing either one.

`make help` lists every available target. `compose.yaml` covers Postgres, Redis,
Ollama, and the Celery worker; `make infra` starts just the infra services (for the
host-run API/tests), `make up` builds and starts the full stack including the
worker, `make down` stops it. Postgres is reachable from the host at
`localhost:5433` (not `5432`, to avoid colliding with any other local Postgres) —
see `compose.override.yaml`.

## Try it

Everything below assumes `make check` has already passed and the database is
migrated (see Quick start). Steps 1–3 are shared setup; then pick the browser
UI or the raw API depending on what you want to see.

1. Start Postgres + Redis + Ollama + the Celery worker, and the app, in two terminals:
   ```
   make up                                       # terminal 1: db + redis + ollama + worker (Docker)
   cd src && uv run python manage.py runserver   # terminal 2: the app (API + UI)
   ```
2. Pull the models ingest uses into the Ollama container (first run only):
   ```
   make pull-model         # qwen3:8b, for enrichment
   make pull-embed-model   # nomic-embed-text, for embeddings
   ```
3. Create a user:
   ```
   make superuser   # prompts for username/password
   ```

### Via the browser UI

1. Visit `http://localhost:8000/` — you'll be redirected to `/login/`. Log in
   with the user from step 3 above (there's no self-service sign-up; accounts
   are created via `make superuser` or the Django admin).
2. Paste a URL into the add-article field and submit. The new row appears
   immediately with a **pending** badge, then updates itself in place —
   **fetching** → **enriched** (or **failed**) — every few seconds with no
   page reload, until Celery finishes ingesting it.
3. Use the search box and tag dropdown to filter the list; click an
   article's title to open its detail page (summary, tags, and a collapsible
   raw-content preview); use **Delete** to remove it.

### Via the API (curl)

1. Log in to get a JWT:
   ```
   TOKEN=$(curl -s localhost:8000/api/v1/auth/token \
     -H "Content-Type: application/json" \
     -d '{"username": "you", "password": "your-password"}' | jq -r .access)
   ```
2. Submit an article and poll it until it's enriched:
   ```
   curl -s localhost:8000/api/v1/articles \
     -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
     -d '{"url": "https://example.com"}'

   curl -s localhost:8000/api/v1/articles/<id-from-above> \
     -H "Authorization: Bearer $TOKEN"
   ```

The UI and the API read/write the same articles — an article added through
one shows up in the other, since both sit on top of the same `library` app
and Celery pipeline. They just don't share an auth mechanism (see
[UI](#ui) below).

## API

All routes are mounted under `/api/v1/`. Interactive Swagger docs (django-ninja's
built-in, auto-generated from the schemas below) are at `/api/v1/docs`; the raw
OpenAPI schema is at `/api/v1/openapi.json`. Authenticate with `POST /auth/token`
to get a JWT pair, then send `Authorization: Bearer <access>` on the rest:

- `POST /auth/token` — `{username, password}` → `{access, refresh}`
- `POST /articles` — `{url}`; `202` if a new ingest was queued, `200` (with the
  existing article) if you'd already submitted that url
- `GET /articles` — list your own articles; filter with `?tag=` and `?q=`, or pass
  `?similar_to=<id>` instead for semantic "more like this" (see below)
- `GET /articles/{id}` / `DELETE /articles/{id}`
- `GET /tags` — your own tags

Articles are ingested asynchronously via Celery: `POST` returns immediately with
`status: "pending"`, then the article moves `pending` → `fetching` →
`enriched`/`failed` as the task fetches the url, then enriches it — a summary and
3-5 tags, generated in one structured-output call to Ollama's `/api/chat`, plus an
embedding from Ollama's `/api/embeddings` (`nomic-embed-text`) — attached to the
article automatically. Poll `GET /articles/{id}` to watch it resolve. Fetch/enrich
failures are retried up to 3 times with exponential backoff before the article is
marked `failed`; a task re-run on an already-`enriched` article is a no-op.

`GET /articles?similar_to=<id>` ranks your other articles by how similar they are
to the given one, blending full-text relevance (Postgres `SearchRank` against the
source article's own title/summary) and vector similarity (`pgvector` cosine
distance between embeddings) via Reciprocal Rank Fusion, so neither signal has to
be normalized against the other's scale. 404s if the article doesn't exist, isn't
yours, or hasn't been embedded yet. Articles ingested before this phase won't have
an embedding until backfilled:
```
cd src && uv run python manage.py backfill_embeddings
```
Safe to interrupt and re-run — each article is embedded and saved individually, so
a partial run just leaves the remaining articles to pick up next time.

## UI

`src/ui/` is a server-rendered browser UI — Django templates + htmx (no SPA
framework, no JS build step) styled with Tailwind CSS v4 (compiled via its
standalone CLI, no Node/npm). Routes:

- `/login` / `/logout` — Django session auth. Login-only; there's no
  sign-up route, accounts are created via `make superuser` or the admin.
- `/` — your articles, with `?q=` and `?tag=` filters and an add-article form
- `/articles/<id>/` — one article's summary, tags, status, and a
  stripped-content preview (never raw HTML — the source page's markup is
  scraped third-party content, so it's shown as plain text)

The UI **does not use the JWT API** — it's a second, independent auth
mechanism (Django sessions) that talks to the same `library` app models
directly, not over HTTP. See [ADR 0007](docs/adr/0007-phase-9-browser-ui.md)
for why.

The status badge on each article polls itself via htmx every few seconds
while `pending`/`fetching`, and stops once the article reaches `enriched` or
`failed` — that's genuinely live, not a fixed-count refresh.

If you change any Tailwind classes in `src/ui/templates/`, recompile the
committed CSS (the standalone binary isn't committed — download it once):

```
mkdir -p bin
curl -sLo bin/tailwindcss https://github.com/tailwindlabs/tailwindcss/releases/latest/download/tailwindcss-linux-x64
chmod +x bin/tailwindcss
make css   # or `make css-watch` to rebuild on every save
```

## MCP server

`mcp_server/` exposes a user's library to Claude Code (or any MCP client) over
stdio, using the Django ORM directly rather than going through the HTTP API:

- `search_library(query)` — the same title/content/summary match `GET
  /articles?q=` uses, scoped to one user
- `get_article(id)` — a single article, including its full `content` (the REST
  API's `GET /articles/{id}` omits it)

**Auth:** the server acts as one Django user, resolved from a JWT refresh token
in `CURIO_MCP_TOKEN` (not a new auth mechanism — the same `ninja_jwt` tokens
`POST /auth/token` already issues). Mint one and export it:

```
TOKEN=$(curl -s localhost:8000/api/v1/auth/token \
  -H "Content-Type: application/json" \
  -d '{"username": "you", "password": "your-password"}' | jq -r .refresh)
export CURIO_MCP_TOKEN=$TOKEN
```

The refresh token (7-day lifetime) is used instead of the 15-minute access
token so a long-running MCP server doesn't need to re-authenticate mid-session.

**Registering it:** `.mcp.json` at the repo root already declares a
`curio-library` server (`uv run python mcp_server/server.py`), reading
`CURIO_MCP_TOKEN` from your shell. Open Claude Code in this repo and it'll
prompt to approve the project-scoped server on first use; run `/mcp` any time
to check its connection status or see `search_library`/`get_article` listed
as available tools.

## CI

`.github/workflows/ci.yml` runs on every PR and every push to `master`:

- **`quality`** — the same `make check` gate (ruff, ruff format --check, mypy,
  `pytest --cov`), against real `pgvector/pgvector:pg17` and `redis` service
  containers, so it's the exact same Postgres image `compose.yaml` uses, not a
  stand-in.
- **`build`** — builds the worker image with `docker buildx bake` (config in
  `docker-bake.hcl`) on every PR to catch a broken `Dockerfile` early; only pushes
  to `ghcr.io/arianagh/curio` on a push to `master`.

Dependabot (`.github/dependabot.yml`) checks `uv` dependencies, GitHub Actions, and
the Docker base image weekly and opens PRs against the same `quality` gate.

### Real-stack e2e (manual)

`.github/workflows/e2e.yml` runs the real thing: a real Celery worker consuming
from a real Redis broker, a real Ollama call (`qwen2.5:0.5b` — same family as
production's `qwen3:8b`, ~10x smaller so it's fast enough for CI), hit over actual
HTTP by `scripts/e2e_smoke.py`. `quality` mocks Ollama and runs Celery eager, so it
can't catch real network/timeout/topology bugs the way this can — but a real model
pull and inference call is too slow and third-party-network-dependent to gate every
merge on, so it's `workflow_dispatch`-only (manual trigger, no push/PR/schedule).
The pulled models are cached across runs via `actions/cache`, so only the first run
after a cache eviction pays the download cost.

Run it whenever you want a real-stack check:

```
gh workflow run e2e.yml --ref master
gh run watch --exit-status $(gh run list --workflow=e2e.yml --limit 1 --json databaseId -q '.[0].databaseId')
```

Or from the GitHub UI: **Actions** tab → **E2E (real stack)** in the left sidebar →
**Run workflow** → pick `master` → **Run workflow**.

## Follow the build

This repo is tagged phase by phase — `v0.1` through `v1.0` — so you can check out any
point in the build and see exactly what existed at that step:

```
git fetch --tags
git checkout v0.1   # or any tag
```

Browse the full list of phases on the
[Releases page](https://github.com/arianagh/curio/releases) and
[tags](https://github.com/arianagh/curio/tags). Each release's notes describe what
that phase adds and what it's meant to teach.

**Current phase:** `v0.9-ui` — a new `ui` app adds a minimal, server-rendered
browser UI (Django templates + htmx + Tailwind CSS, no SPA framework) on
Django session auth, fully independent of the JWT API that `mcp_server/` and
API clients use. See [UI](#ui) above.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the phase → branch → PR → tag loop and the
Claude Code slash commands used to drive it.

## License

[MIT](LICENSE)