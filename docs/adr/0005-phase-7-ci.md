# ADR 0005: CI pipeline, image registry, and service containers for phase 7

## Context

Through phase 6 the quality gate (`make check`: ruff, ruff format --check, mypy,
pytest) only ran on a developer's own machine — nothing enforced it on GitHub, and
the Celery worker's `Dockerfile` had never been built outside `docker compose`.
Wiring that up as GitHub Actions had several forks with real trade-offs: which
container registry to publish images to, which Postgres image to run in CI (the
phase-5 `pgvector` migration needs the `vector` extension compiled in), whether to
gate merges on a numeric coverage threshold, and whether to invoke `docker build`
directly or go through a bake file.

## Decision

- **Registry**: publish to GHCR (`ghcr.io/arianagh/curio`) using the workflow's
  built-in `GITHUB_TOKEN`, rather than Docker Hub. No new secret to provision, and
  the package lives next to the repo in GitHub's own UI.
- **CI Postgres**: `pgvector/pgvector:pg17` — the identical image `compose.yaml`
  already uses for local dev, not stock `postgres:17`. Stock Postgres has no
  `vector` extension for `pgvector.django.VectorExtension()` (phase 5's migration)
  to enable, so it isn't actually a viable substitute here.
- **Redis service container**: included even though nothing in the test suite
  touches Redis live today (Celery runs eager/in-process during tests). This is for
  parity with `compose.yaml` and so a future test that does need Redis doesn't also
  need a CI change to go with it.
- **Build tool**: `docker buildx bake` against a new `docker-bake.hcl`, not a bare
  `docker build`/`docker push`. Tags, build context, and cache config live in one
  file usable both from CI and a developer's own machine (`docker buildx bake
  --print`), and a `group "default"` wraps the single `worker` target so a second
  image (e.g. a future `web` service) can be added without restructuring the
  workflow.
- **Coverage**: `pytest --cov` reports to the terminal and as an uploaded
  `coverage.xml` artifact, with no `--cov-fail-under` threshold yet. The first real
  CI run establishes a baseline; gating on a guessed number now would just be a
  threshold to fight later.
- **Dependabot grouping**: `uv` minor/patch bumps are grouped into a single weekly
  PR to cut noise; major bumps (e.g. a future Django major) stay ungrouped since
  those need a human to actually read the changelog. GitHub Actions and Docker
  base-image bumps stay individual too — there are few enough of them that grouping
  buys nothing.

## Trade-offs

- GHCR ties image distribution to GitHub identity rather than Docker Hub's broader
  reach — acceptable for a teaching repo that isn't trying to be a general-purpose
  published image; would need revisiting if that changed.
- The `quality` check doesn't yet protect phase 6's coverage gains from regressing
  — it reports coverage but doesn't fail below any number. Needs a follow-up once a
  baseline from real CI runs exists.
- The Redis service container costs a few seconds of job startup for headroom nothing
  currently uses.
- `cache-from`/`cache-to: type=gha` ties the Docker build cache to GitHub's own
  Actions cache (subject to the same size/eviction limits as everything else
  cached there) instead of a registry-based cache — simpler and needs no extra
  credentials, but not the most efficient option available.

## Addendum: real-stack e2e workflow

**Context.** `quality` mocks Ollama (`respx`) and runs Celery eager, so it
verifies the API's contract but not real topology — exactly the class of bug
(unpublished Redis port, too-short Ollama timeout) that's bitten this repo
before mocked tests couldn't catch. Closing that gap meant running the actual
`celery worker` process against a real broker and a real Ollama call, which
raised three more forks: how to trigger it, how to keep it fast, and how to
cache a multi-hundred-MB model download across runs.

**Decision.**
- **Trigger**: `workflow_dispatch` only — no push/PR/schedule. A real model
  pull is a third-party network dependency GitHub doesn't control, and even a
  small real inference call is slow enough that gating merges on it isn't
  worth the flakiness risk. Run it by hand when a real-stack check is wanted.
- **Model**: `qwen2.5:0.5b` instead of production's `qwen3:8b` — same family
  (still exercises Ollama's structured-JSON `format` support), ~10x smaller,
  fast enough that a full cold run (pull + real inference) finished in under
  2 minutes. Moved both model names out of `enrichment/service.py`/
  `embeddings.py` (previously hardcoded) into `OLLAMA_CHAT_MODEL`/
  `OLLAMA_EMBED_MODEL` settings so the workflow can override just the model,
  not application code.
- **Ollama as a step, not a `services:` entry**: GitHub Actions starts service
  containers before any step runs, so a service container's volume can never
  be pre-seeded by a cache-restore step that runs later. Ollama runs via a
  plain `docker run` step instead, bind-mounted to a path `actions/cache`
  restores first.
- **The smoke test is a standalone script (`scripts/e2e_smoke.py`), not a
  pytest test**: it needs `CELERY_TASK_ALWAYS_EAGER=false` and a real running
  server/worker outside the pytest-django test-client model entirely, so
  reusing pytest's fixtures would have fought the tool rather than used it.

**Trade-offs.**
- Manual-only means real-stack regressions can sit unnoticed between runs —
  it's a deliberate trade of coverage-recency for not slowing down every PR.
- The first real dispatch (run 29423284537) passed the smoke test but the
  cache-save step failed silently — the Ollama container writes its cache
  directory as root, and `actions/cache`'s post-job save runs as the
  unprivileged runner user, so `tar` couldn't read the root-owned files. Fixed
  with an explicit `chown` after pulling models, before the job ends. Worth
  remembering for any future job that bind-mounts a container's writes into a
  path `actions/cache` is expected to persist.
