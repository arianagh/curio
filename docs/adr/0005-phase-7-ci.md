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
