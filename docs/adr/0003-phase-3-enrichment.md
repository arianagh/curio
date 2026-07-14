# ADR 0003: split fetch/enrich, structured Ollama output, and containerized Ollama for phase 3

## Context

Phase 2 fetched a url and asked Ollama for a plain-text summary in the same
`fetch_and_summarize()` call, with no tags. Phase 3's job was to add tags as a
second LLM-derived field, decide how reliably to get structured output out of
a local model, decide whether that call should share the fetch step's retry
budget, and finally bring Ollama itself into `compose.yaml` (flagged as a
known gap in ADR 0002). Each of these had more than one reasonable shape.

## Decision

- **Split fetch from enrich**: `library/services.fetch_article()` now only
  does the HTTP GET + title parse; a new `curio/enrichment/service.enrich()`
  is the sole place that talks to Ollama, called from `ingest_article` right
  after fetch succeeds. `curio/enrichment/` sits at the project level (next
  to `curio/config.py`, which already centralizes `OLLAMA_BASE_URL`) rather
  than inside `library/`, since it's Ollama-client infrastructure rather than
  article-specific business logic.
- **Structured output via `/api/chat`**: `enrich()` passes
  `EnrichmentResult.model_json_schema()` as the `format` field on Ollama's
  `/api/chat` request instead of just asking for JSON in the prompt text.
  The response's `message.content` is parsed with
  `EnrichmentResult.model_validate_json()`. Schema-constrained decoding makes
  a well-formed `{summary, tags}` body far more likely on the first attempt
  than prompt-only JSON, at the cost of depending on an Ollama version that
  supports the `format` parameter.
- **Shared retry budget**: `enrich()` does no exception handling of its own —
  a connection/timeout/non-2xx failure raises `httpx.HTTPError` and falls
  into `ingest_article`'s existing `except httpx.HTTPError: retry` branch
  (ADR 0002), the same budget the fetch step uses. A malformed response body
  (a `pydantic.ValidationError` or `json.JSONDecodeError`, neither an
  `httpx.HTTPError`) instead hits the existing `except Exception: fail
  immediately` branch — identical to how a bad response body already behaved
  before this phase.
- **Ollama as a compose service**: added with a named volume
  (`ollama_data:/root/.ollama`) so pulled models survive container restarts,
  and a healthcheck running `ollama list` (the official image has no
  curl/wget, but does have the `ollama` binary on `PATH`). `worker` now
  depends on `ollama` with `condition: service_healthy` and reaches it at
  `http://ollama:11434` instead of `host.docker.internal`.
- **Tag normalization**: tag names from the LLM are lowercased, stripped, and
  deduplicated before `Tag.objects.get_or_create(owner=article.owner,
  name=...)`, since `(owner, name)` is a unique constraint and an LLM won't
  reliably return consistent casing across runs.

## Trade-offs

- Schema-constrained decoding is only as reliable as the Ollama version and
  model's support for it; there's no fallback path if `qwen3:8b` returns
  something `model_validate_json` can't parse — that case is deliberately
  treated as a permanent failure (see ADR 0002's identical stance on a bad
  `/api/generate` body), not retried.
- Sharing the fetch step's retry budget means a slow-starting Ollama
  container (e.g. right after `docker compose up`, before the healthcheck
  passes) gets a chance to recover via backoff — but it also means a
  consistently broken enrichment call burns the same 3 attempts as a broken
  fetch, rather than failing fast on the first try.
- Lowercasing tag names is a real (if minor) product decision: `"Python"` and
  `"python"` collapse into one tag, which is almost certainly desired but
  does mean the original casing an LLM chose is never preserved.
- Ollama now runs in `compose.yaml`, but the model itself isn't pulled
  automatically — `make pull-model` is still a manual, first-run step, since
  baking a multi-gigabyte model into the image or auto-pulling on container
  start was out of scope for this phase.
