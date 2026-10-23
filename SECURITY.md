# Security

## The sandbox is not a security boundary

Lingenious executes Python scripts written by an LLM. `core/sandbox` applies an AST allow-list
(only `cadquery` and `math` may be imported; `open`, `exec`, `eval`, dunder attribute access and a
few other names are rejected), runs the script in a child process, and limits wall-clock time and
memory. This reduces accidents; it does **not** make it safe to run untrusted or adversarial code.

If you expose Lingenious to untrusted users or models, run it inside a container or VM with no
network access, a read-only filesystem apart from a scratch directory, and dropped capabilities.

## Web app deployment

By default the web app (`web/server`) has **no authentication**: anyone who can reach the port can start
runs (spending your LLM quota) and execute sandboxed CadQuery code. `docker-compose.yml` therefore
publishes it on `127.0.0.1:8000` only.

Optional access token: set `LINGENIOUS_ACCESS_TOKEN` (e.g. in `.env`, passed through by compose) and every
`/api` route except `/api/health` (and the login/logout endpoints) requires it, via
`Authorization: Bearer <token>` (constant-time comparison) or the HttpOnly, SameSite=Strict session cookie set by
`POST /api/auth/login` (the cookie holds an HMAC-derived value, not the token; `Secure` is added over HTTPS).
The static UI stays public and shows a login screen. Failed logins are throttled per client address with an
in-memory exponential backoff (behind a reverse proxy all clients share the proxy's address, so rate-limit
there too). The token is a single shared secret: use a long random value (`openssl rand -hex 32`), serve over
HTTPS when not on localhost (the token and cookie travel in clear over plain HTTP), and rotate it by restarting
with a new value. This is access control for a small team, not user management. To expose the app publicly,
prefer an authenticating reverse proxy with TLS in front as well, and change the port mapping deliberately.

The compose file and `web/Dockerfile` apply these hardening defaults: non-root user (uid 10001, owns
only `/app/data`), read-only root filesystem with tmpfs for `/tmp` (sandbox scratch space and the
matplotlib cache), `cap_drop: [ALL]`, `no-new-privileges`, memory/CPU/pids limits, a healthcheck and
`restart: unless-stopped`. The runtime image does not contain pytest or ruff. None of this makes the
sandbox safe against adversarial code (see above); add network isolation if the model or users are untrusted.

## Secrets

API keys are read from environment variables (`.env`, which is git-ignored). Never commit `.env`.
The Feishu adapter uses the locally logged-in `lark-cli` identity and stores no credentials in the repo.

## Reporting a vulnerability

Please report it privately rather than in a public issue: use "Report a vulnerability" on the repository's
Security tab (GitHub private vulnerability reporting), or email related_storm_1g@icloud.com.
