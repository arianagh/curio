# ADR 0004: Postgres + pgvector, embeddings via Ollama, and RRF-ranked similarity for phase 5

## Context

Every prior phase's ADR/README flagged the same open gap: Curio ran on SQLite
with no Postgres service anywhere in `compose.yaml`. Phase 5's job was to
close that gap *and* add semantic "more like this" search on top of it —
which meant deciding what image runs Postgres+pgvector, how the app reaches
it without colliding with unrelated services already on this host, what
model generates embeddings, how a backfill of existing articles stays safe if
interrupted, and how to blend keyword and vector relevance into one ranking.

## Decision

- **Postgres via the official `pgvector/pgvector:pg17` image**, not a custom
  Dockerfile — pgvector ships baked in, so `compose.yaml` just needed a `db`
  service (named to match `Makefile`'s pre-existing `infra` target) with a
  named volume and a `pg_isready` healthcheck.
- **No host port on 5432**: this host already runs an unrelated
  `postgres_container` bound to `0.0.0.0:5432`. `compose.yaml` doesn't
  publish a host port for `db` at all (containers reach it at `db:5432` over
  Compose's internal network); `compose.override.yaml` adds `5433:5432`
  purely for host-side `manage.py`/`psql` access — the same pattern already
  used there for redis (`6380:6379`, from the redis-port-and-uv-cache fix).
- **`pgvector.django.VectorField`** (768 dims) on `Article`, plus an
  `HnswIndex` (cosine ops) for approximate-nearest-neighbor lookups, added via
  a migration that runs `pgvector.django.VectorExtension()` first so
  `CREATE EXTENSION vector` exists before the column does.
- **`nomic-embed-text` via Ollama's `/api/embeddings`** generates embeddings —
  chosen over a larger model (e.g. `mxbai-embed-large`) because it's small
  enough to stay fast on the same CPU-only Ollama container that already
  takes real time per `/api/chat` call (ADR 0003). `curio/enrichment/embeddings.get_embedding()`
  mirrors `enrich()`'s contract exactly: it raises `httpx.HTTPError`
  uncaught so callers reuse the same retry decision points.
- **Embedding generation is per-row, not batched**: `ingest_article` embeds a
  new article right after `enrich()` succeeds, in the same
  `except httpx.HTTPError: retry` branch. `backfill_embeddings` (for
  pre-phase-5 articles) embeds and saves one article at a time —
  `article.save(update_fields=["embedding"])` runs immediately after each
  Ollama call, with no transaction spanning the whole loop. If the command is
  killed mid-run, every already-saved row stays saved; a re-run's
  `embedding__isnull=True` filter naturally re-selects only what's left, with
  no bookkeeping — the same idempotency shape `ingest_article` already uses
  for its already-enriched skip check.
- **Reciprocal Rank Fusion for `?similar_to=`**: rather than normalizing
  `ts_rank` (full-text) against cosine distance (vector) onto a shared [0,1]
  scale and weighting them, `list_articles` ranks candidates by each signal
  separately (`Window(expression=Rank(), order_by=...)`) and combines the two
  rank *positions* as `1/(60 + rank_fts) + 1/(60 + rank_vec)`. This sidesteps
  ever having to justify a normalization scheme or a weight — it's scale-free
  by construction.

## Trade-offs

- Not publishing a host port for `db` in `compose.yaml` means the service is
  unreachable from the host unless `compose.override.yaml` (or an equivalent
  local override) is present — fine for this repo where the override is
  checked in, but worth remembering if `compose.override.yaml` is ever
  gitignored instead.
- `nomic-embed-text` trades retrieval quality for CPU speed; a future phase
  that wants better semantic recall would need to re-embed everything under a
  new model and dimension count, since `VectorField(dimensions=768)` is fixed
  at the schema level.
- RRF is scale-free but not tunable — there's no single weight to turn up
  "more like this, semantically" vs. "more like this, same words." A
  weighted linear blend would allow that at the cost of picking (and
  justifying) a normalization and a weight.
- The per-row backfill is simple and crash-safe but not the fastest way to
  embed a large backlog — each article is one synchronous Ollama round-trip,
  with no batching or concurrency. Fine at this project's scale; would need
  revisiting before backfilling a much larger corpus.
- Tests now require a reachable Postgres (`make infra` before `make test`),
  a real change from every prior phase, where the suite ran against SQLite
  with zero infra.
