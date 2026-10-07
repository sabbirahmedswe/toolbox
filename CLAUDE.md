# Toolbox

Local iLovePDF-style file toolbox (PDF tools today, image tools planned): FastAPI backend in `backend/`, React + Vite + TypeScript frontend in `frontend/`.
See `README.md` for features, setup, configuration and the API; this file covers how to work on the code.

## Working on this project

- Build features **one step at a time** and stop after each for the user to review. Don't start the next step until asked.
- Commit only when the user asks.
- **Every code review must include a security pass**: injection, resource exhaustion / DoS, handling of
  untrusted input (Ghostscript, pypdf, Pillow), Content-Disposition / filename handling, and XSS.
- There is no browser in the dev environment: verify end-to-end with `curl` through the Vite proxy
  (`http://localhost:5173/api/...`) and leave UI checks to the user.
- Keep `README.md` in sync: when a setting, endpoint, field or limit changes, update its Configuration and API
  tables. Limit changes also go in `frontend/src/fileItems.ts` and `client_max_body_size` in `frontend/nginx.conf`.

## Commands

Setup and run instructions are in `README.md`. These are the forms to use from Claude's shell:

- Backend tests: `cd backend && .venv/bin/pytest -q -p no:warnings` (`-p no:warnings` hides a Starlette testclient deprecation).
  Test-only deps live in `requirements-dev.txt`; `requirements.txt` is runtime only (used by the Docker image).
- Frontend checks: `cd frontend && npx tsc -b && npm run lint && npm run build`
- Start dev servers in the background with `nohup ... &`; stop them by PID from `pgrep -f "[u]vicorn app.main|[b]in/vite"`.
  The brackets stop the pattern matching the calling shell. Plain `pkill -f` kills the shell (exit 144).
- Docker (via Docker Desktop WSL integration): this shell may predate the user's `docker` group membership, so run
  `sg docker -c "docker compose up --build"` if plain `docker` gives "permission denied" on the socket.

## Backend conventions

- Routers (`app/routers/`) handle HTTP; services (`app/services/`) are pure functions that raise
  `ProcessingError`, which becomes a 400 `{detail}`.
- Uploads: `save_upload(upload, dest, allowed_kinds)` validates by magic bytes and size. Never trust extensions.
- Return results from memory as `Response(bytes)` and delete the temp workdir in a `finally` block. Don't use a
  `FileResponse` / `BackgroundTask` for cleanup: Starlette skips it on client abort or a bad `Range` header.
- Run CPU-heavy or blocking work with `run_in_threadpool`.
- CPU-heavy endpoints use a `JobLimiter` (`app/utils/limits.py`): call `limiter.check()` before saving uploads
  and `async with limiter.slot()` around processing.
- Build download headers with `attachment(filename)` (RFC 6266 ASCII fallback + `filename*`).
- Limits live in `app/config.py` (env-driven, validated). Read `config.X` at request time so tests can monkeypatch.
  Keep `frontend/src/fileItems.ts` limits in sync with the defaults.
- Ghostscript runs with `-dSAFER`, memory/CPU `ulimit`s via an `sh` wrapper (not `preexec_fn`), a timeout,
  and output discarded.
- Pillow: restrict decoders with `Image.open(..., formats=[...])` and enforce `MAX_IMAGE_PIXELS` before decoding.
- Tests generate their fixtures in `tests/helpers.py`. Tests that need Ghostscript skip when it's missing.

## Frontend conventions

- Each tool is one entry in `src/tools.tsx` (route, card, nav and the home hero's decorative icons are derived
  from it; the hero shows the first three icons).
- Keep site-wide copy (hero, page title) tool-agnostic: the toolbox isn't PDF-only.
- Use `postForFile` / `downloadBlob` from `src/api/client.ts`, and `FileDropzone` / `SortableFileList` for uploads.
- Plain CSS in `src/index.css` using the `:root` variables; no UI library.
