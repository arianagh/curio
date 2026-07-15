# ADR 0006: MCP server auth and transport

## Context

Phase 8 adds an MCP server so an AI assistant can search and read a user's
library directly, reusing the Django ORM rather than calling the existing
REST API over HTTP or writing raw SQL. That constraint immediately raises a
question the REST API never had to answer this way: there's no Django
request/response cycle to hang `JWTAuth()` off of, so the server needs its
own way to decide which user's data a given process should see, and its own
transport for Claude Code to actually reach it.

## Decision

- **Auth: reuse `ninja_jwt`'s refresh token, not a new mechanism.** The
  server reads a token from `CURIO_MCP_TOKEN` at startup and resolves it to a
  Django `User` via `ninja_jwt.tokens.RefreshToken` — the same class
  `accounts/api.py` already uses to mint tokens, verifying the same signature
  against the same `SECRET_KEY`. The *refresh* token (7-day lifetime) is used
  instead of the 15-minute access token, since a Claude Code session can run
  far longer than that; the trade-off is a token that stays valid for a week
  if it leaks, versus re-authenticating a long-running local process
  mid-conversation.
- **Validate once, at startup, not per call.** `resolve_user()` runs before
  `mcp.run()` starts the stdio loop; an expired/invalid token fails fast with
  one clear stderr message and a non-zero exit, rather than the server
  accepting the connection and only failing (opaquely) on the first tool
  call. The cost is that a token expiring mid-session requires restarting the
  server, not a silent re-auth — acceptable for a local dev tool restarted by
  Claude Code per session anyway.
- **Transport: stdio, not HTTP/SSE.** `FastMCP`'s default — Claude Code
  spawns the server as a subprocess and talks over stdin/stdout, so there's
  no port to bind, no CORS, no network exposure to reason about. This only
  works because the server and the Django app share one machine and one
  Postgres instance; it wouldn't extend to a remotely-hosted MCP server.
- **Registration: a checked-in `.mcp.json`, not `claude mcp add` at user
  scope.** Project-scoped config means anyone who clones the repo gets the
  server available (after an approval prompt) without a separate setup step,
  consistent with this repo's "check the workflow into the repo" style
  (`.claude/commands/`). The actual token is never committed — `.mcp.json`
  interpolates `${CURIO_MCP_TOKEN}` from the environment Claude Code runs in.
- **Django ORM called from async tool functions via `sync_to_async`.** MCP's
  stdio transport runs an asyncio event loop, and Django refuses synchronous
  ORM calls inside a running loop (`SynchronousOnlyOperation`). Each
  `@mcp.tool()` function wraps its call into `mcp_server/service.py` with
  `asgiref.sync.sync_to_async(..., thread_sensitive=True)` — the same
  pattern Django's own ASGI views use, not a one-off workaround.

## Trade-offs

- A leaked refresh token grants library read access for up to 7 days with no
  way to revoke it short of rotating `SECRET_KEY` (which invalidates every
  outstanding token, not just this one) — `ninja_jwt`'s blacklist app would
  fix this but isn't wired up yet.
- `search_library` deliberately does not reuse the hybrid FTS+vector
  `similar_to` ranking from `GET /articles?similar_to=`, since that's seeded
  from an existing article's embedding, not a free-text query, and doesn't
  fit a `search_library(query)` signature. A query-embedding step for true
  semantic search is a reasonable follow-up phase, not this one.
- Project-scoped `.mcp.json` means the server command and structure are
  public (in the repo); only the token is kept out, which is the right split
  for this teaching repo but would need reconsidering for anything more
  sensitive.
