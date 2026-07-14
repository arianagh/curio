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

## Prerequisites

- [`uv`](https://docs.astral.sh/uv/getting-started/installation/) — manages the Python
  version (3.14) and dependencies; nothing else to install by hand
- [Docker](https://docs.docker.com/get-docker/) — runs the local Postgres, Redis, and
  Ollama services (see note below on current phase)
- [`gh`](https://cli.github.com/) — the GitHub CLI, used to open PRs and cut releases

## Quick start

```
uv sync              # install dependencies into .venv
make check           # lint + format-check + type-check + test
cd src && uv run python manage.py migrate
cd src && uv run python manage.py runserver
```

`make help` lists every available target. `compose.yaml` currently covers Redis,
Ollama, and the Celery worker; `make infra` / `make up` / `make down` will bring up
the full stack once Postgres lands as a Docker service in a later phase.

## Try it

Everything below assumes `make check` has already passed and the database is
migrated (see Quick start).

1. Start Redis + Ollama + the Celery worker, and the API, in two terminals:
   ```
   make up                                       # terminal 1: redis + ollama + worker (Docker)
   cd src && uv run python manage.py runserver   # terminal 2: the API
   ```
2. Pull the model ingest uses into the Ollama container (first run only):
   ```
   make pull-model
   ```
3. Create a user and log in:
   ```
   make superuser                             # prompts for username/password
   TOKEN=$(curl -s localhost:8000/api/v1/auth/token \
     -H "Content-Type: application/json" \
     -d '{"username": "you", "password": "your-password"}' | jq -r .access)
   ```
4. Submit an article and poll it until it's enriched:
   ```
   curl -s localhost:8000/api/v1/articles \
     -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
     -d '{"url": "https://example.com"}'

   curl -s localhost:8000/api/v1/articles/<id-from-above> \
     -H "Authorization: Bearer $TOKEN"
   ```

## API

All routes are mounted under `/api/v1/`. Interactive Swagger docs (django-ninja's
built-in, auto-generated from the schemas below) are at `/api/v1/docs`; the raw
OpenAPI schema is at `/api/v1/openapi.json`. Authenticate with `POST /auth/token`
to get a JWT pair, then send `Authorization: Bearer <access>` on the rest:

- `POST /auth/token` — `{username, password}` → `{access, refresh}`
- `POST /articles` — `{url}`; `202` if a new ingest was queued, `200` (with the
  existing article) if you'd already submitted that url
- `GET /articles` — list your own articles; filter with `?tag=` and `?q=`
- `GET /articles/{id}` / `DELETE /articles/{id}`
- `GET /tags` — your own tags

Articles are ingested asynchronously via Celery: `POST` returns immediately with
`status: "pending"`, then the article moves `pending` → `fetching` →
`enriched`/`failed` as the task fetches the url, then enriches it — a summary and
3-5 tags, generated in one structured-output call to Ollama's `/api/chat` and
attached to the article automatically. Poll `GET /articles/{id}` to watch it
resolve. Fetch/enrich failures are retried up to 3 times with exponential backoff
before the article is marked `failed`; a task re-run on an already-`enriched`
article is a no-op.

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

**Current phase:** `v0.4-enrichment` — splits ingest into a fetch step
(`library/services.fetch_article`) and a separate enrichment step
(`curio/enrichment`) that asks Ollama's `/api/chat` for a JSON-schema-constrained
summary + tags, then attaches the tags to the article. Ollama joins `compose.yaml`
as a Docker service with a healthcheck; Postgres and a containerized `web` service
are still outstanding.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the phase → branch → PR → tag loop and the
Claude Code slash commands used to drive it.

## License

[MIT](LICENSE)