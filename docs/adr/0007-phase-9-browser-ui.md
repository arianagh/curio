# ADR 0007: Browser UI — session auth, no-Node Tailwind, htmx over a SPA

## Context

Every prior phase made Curio's data reachable over HTTP (the django-ninja API)
or over MCP (`mcp_server/`), but there was still no way to actually look at
your library in a browser — only curl or an AI assistant. Phase 9 adds that:
a minimal, modern, server-rendered UI to add a URL, watch it go
`pending` → `fetching` → `enriched`, search/filter by tag, read a summary,
and delete an article.

Three forks came up building it, each with a real trade-off:

1. How should the browser authenticate — reuse the existing JWT API, or
   something else?
2. How should Tailwind CSS get compiled, given this is otherwise a
   Python-only repo with no Node/npm anywhere?
3. How should the page get its interactivity — a JS framework, or something
   lighter?

## Decision

- **Auth: Django sessions, a second mechanism, not JWT reused.** JWTs
  living in `localStorage` (or hand-rolled into a cookie) don't fit plain
  server-rendered views/htmx cleanly, and the JWT API already has a real
  consumer (`mcp_server/`) whose contract shouldn't be disturbed. The `ui`
  app uses Django's built-in `LoginView`/`LogoutView` and
  `@login_required`, and its views query the ORM directly
  (`filter_articles(request.user, ...)`) — they never call the JWT API
  internally over HTTP. `library/api.py`'s `auth=JWTAuth()` routers are
  untouched by this phase. The two mechanisms share zero code by design;
  a bug in session handling can't leak into the API and vice versa.
- **Login-only, no self-service sign-up.** Curio reads as a personal,
  single-user app in practice — accounts are still created via
  `make superuser` or the admin, same as before this phase. Worth
  revisiting only if multi-user onboarding actually becomes a need.
- **Tailwind CSS v4 via its standalone CLI binary, not django-tailwind.**
  django-tailwind shells out to a Node-based toolchain internally, which
  would be the first Node dependency anywhere in this `uv`-managed,
  Python-only repo. The standalone CLI is a single downloadable binary with
  no `tailwind.config.js` needed for v4's minimal `@import "tailwindcss"`
  setup. It's not committed (platform-specific), so it's a one-time,
  documented `curl` download (see README/CLAUDE.md) — but the *compiled*
  `app.css` it produces **is** committed, like any other static asset, so
  cloning the repo and running the server doesn't require anyone to have
  the binary at all.
- **htmx instead of a SPA framework.** The UI's interactivity needs are
  small: swap a filtered list, prepend a new row, poll a status badge,
  delete a row. htmx attributes on plain server-rendered HTML cover all of
  it — `hx-boost` for free full-page-swap navigation, `hx-trigger="every
  3s"` (only emitted while an article is non-terminal, so polling
  self-stops) for live status, and `hx-swap-oob` so one response can update
  a status badge *and* clear a stale error banner / empty-state placeholder
  in one round trip. No bundler, no client-side router, no `package.json`.

## Trade-offs

- Two independent auth systems means two things to keep secure and in sync
  conceptually (e.g. a future permission change has to be applied in both
  places) — accepted because the alternative (JWT-in-cookie plumbing custom
  auth into Django's request cycle) was more code for no real benefit at
  this scale.
- The Tailwind binary being gitignored means anyone changing UI markup
  needs the one-time download step before `make css` works locally; this
  is documented but is still a manual step compared to `uv sync` covering
  everything else.
- htmx's out-of-band swaps and conditional polling triggers are simple
  once understood, but they're template-level plumbing (which elements
  poll, which get OOB-updated) that a SPA's state management would make
  more explicit at the cost of far more code — a reasonable trade for an
  app this size, worth reconsidering only if the UI's interactivity needs
  grow substantially.
- `Article.content` (raw scraped HTML) is deliberately never rendered
  `|safe` anywhere in templates — the detail page only shows a
  `strip_tags()` plain-text preview. This avoids XSS from third-party page
  content but means the UI can't (yet) render articles with their original
  formatting.
