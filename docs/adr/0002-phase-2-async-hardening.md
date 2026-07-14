# ADR 0002: retry/backoff, idempotency guard, and compose scope for phase 2

## Context

Phase 1 already dispatched ingest via a real Celery task and returned `202` +
`pending` immediately (see ADR 0001). Phase 2's job was to harden that pipeline:
retry transient fetch/summarize failures instead of failing permanently on the
first error, guard against a redelivered/re-run task double-processing an
article, extract the fetch/summarize logic out of the task for testability, and
add the first `compose.yaml` so the worker can run outside a developer's host
Python. Each of these had more than one reasonable shape.

## Decision

- **Retry**: `ingest_article` is now `@shared_task(bind=True, max_retries=3,
  retry_backoff=True, retry_backoff_max=60, retry_jitter=True)`. Only
  `httpx.HTTPError` (covers both connection/timeout errors and non-2xx
  responses from either the fetch or the Ollama call) triggers `self.retry()`;
  any other exception goes straight to `failed`, since it's not a transient
  condition a retry would fix. The task checks `self.request.retries >=
  self.max_retries` itself before retrying, so it explicitly controls when to
  give up and mark `failed`, rather than relying on `MaxRetriesExceededError`
  propagating out of `self.retry()`.
- **Idempotency guard**: the task wraps its initial read in
  `transaction.atomic()` + `select_for_update()` and no-ops if the article is
  already `enriched`. This closes the specific race the phase-1 investigation
  flagged — a redelivered or concurrently-dispatched task re-fetching and
  overwriting an already-completed article. `select_for_update()` is a
  documented no-op on SQLite (today's dev/test database) and becomes a real row
  lock once Postgres lands, so this is forward-compatible rather than
  SQLite-only.
- **Services extraction**: `fetch_and_summarize()` moved to
  `library/services.py` as a plain function with no Celery/task-state
  dependency, so it can be unit-tested (and reused) without going through the
  task machinery.
- **Testing retries under `CELERY_TASK_ALWAYS_EAGER`**: with
  `CELERY_TASK_EAGER_PROPAGATES = True` (set globally for tests in
  `conftest.py`), a real `self.retry()` re-raises `celery.exceptions.Retry` to
  the caller instead of transparently re-running the task the way a live
  worker would. The two new tests that actually exercise a retry loop
  (`test_ingest_article_retries_then_succeeds`,
  `test_ingest_article_marks_failed_after_exhausting_retries`) flip
  `CELERY_TASK_EAGER_PROPAGATES` to `False` locally via the `settings` fixture,
  rather than changing that default for every test.
- **Compose scope**: `compose.yaml` and a new root `Dockerfile` cover the first
  slice of what the Makefile already anticipated (`infra`/`pull-model`
  reference `db` and `ollama` services) — `redis` (the Celery broker) and
  `worker` (the Celery worker, built from the repo). Postgres and Ollama as
  Docker services, and a containerized `web` service, are follow-up phases, not
  a permanent scope cut — the app still runs on SQLite with no `DATABASE_URL`
  wiring, and Ollama runs on the host for now, reached via
  `host.docker.internal`. The Makefile's `infra`/`pull-model` targets are left
  referencing `db`/`ollama` as-is (they'll start working once those services
  land) rather than rewritten around today's partial `compose.yaml`.

## Trade-offs

- The idempotency guard only protects against a task seeing an already-
  `enriched` article; it doesn't add a distinct idempotency key or version
  column, so two workers racing to pick up the *same not-yet-started* article
  at the exact same instant are only serialized by `select_for_update()` (a
  real lock on Postgres, a no-op on SQLite today) — there's no protection at
  all until Postgres lands.
- Retrying only on `httpx.HTTPError` means a bad Ollama response body (e.g.
  malformed JSON) or any bug in `fetch_and_summarize` still fails permanently
  on the first attempt. That's deliberate — retrying non-transient errors would
  just burn 3 attempts on something that will never succeed — but it does mean
  a real Ollama outage that manifests as, say, a JSON decode error rather than
  an HTTP error would not benefit from backoff.
- `make infra` and `make pull-model` still reference the `db`/`ollama` compose
  services from the original Makefile scaffold, which don't exist in
  `compose.yaml` yet — they'll error if run today. Left as-is deliberately
  (matching the pre-existing README note that these targets activate once the
  full stack lands) rather than quietly rewritten to only describe what phase 2
  shipped; `make up` (redis + worker) and a locally-run Ollama are what actually
  works right now, documented in the README's "Try it" section.
