# ADR 0001: JWT auth, real async ingest, and substring search for phase 1

## Context

Phase 1 added three pieces of the API that each had more than one reasonable
implementation: authenticating requests, running the article ingest pipeline
(fetch a url, summarize via Ollama) asynchronously, and implementing
`GET /articles?q=`. The project uses `django-ninja` (not DRF), already declares
`celery`/`redis` as dependencies without wiring them up, and runs on SQLite in dev
with Postgres likely later — so each of these had a real fork with trade-offs.

## Decision

- **Auth**: use the `django-ninja-jwt` package (a ninja-native, simplejwt-style
  library) instead of hand-rolling PyJWT encode/decode and a custom `HttpBearer`
  class. `POST /api/v1/auth/token` is a thin wrapper around `authenticate()` +
  `RefreshToken.for_user()`; protected routers use `ninja_jwt.authentication.JWTAuth`.
- **Async ingest**: wire a real Celery task (`library.tasks.ingest_article`) rather
  than stubbing the pipeline. `POST /articles` calls `.delay()` and returns `202`
  immediately; the task fetches the url via `httpx`, asks Ollama (`OLLAMA_BASE_URL`)
  for a summary, and moves the article `pending` → `fetching` → `enriched`/`failed`.
  Tests force `CELERY_TASK_ALWAYS_EAGER` so they run inline without a live broker.
- **Search**: `?q=` is a case-insensitive `icontains` OR across
  `title`/`content`/`summary`, not a real full-text index.

## Trade-offs

- `django-ninja-jwt` pulls in `django-ninja-extra`, `pyjwt`, and `cryptography` as
  transitive dependencies to save a modest amount of hand-written code; rolling our
  own would be leaner but leaves expiry/signing/refresh-rotation correctness on us.
- A real Celery task means `POST /articles` needs a reachable Redis broker (and
  Ollama) to actually enrich anything outside of tests — there's still no
  `docker-compose.yml` providing that, so manual end-to-end testing beyond the API
  contract requires standing up that infra by hand.
- `icontains` search works identically on SQLite and Postgres with no new infra,
  but it isn't ranked and doesn't stem — it'll need to become a real full-text
  index (e.g. Postgres `SearchVector`) once article volume or search quality
  matters.
