# <img src="frontend/public/favicon.svg" alt="" width="32" height="32" align="top"> Toolbox

A small, local, iLovePDF-style toolbox for everyday file tasks. It currently has these PDF tools, and image
tools (compression, conversion) are planned:

- **Merge PDF**: combine several PDFs into one, in the order you choose (drag the files, or sort them by name).
- **Compress PDF**: shrink a PDF with Ghostscript. Images above 200 dpi (less compression), 150 dpi (recommended)
  or 120 dpi (extreme) are downsampled to it, and colour images are stored as JPEG; text and vector graphics are
  left sharp.
- **Image to PDF**: turn JPG and PNG images into a PDF, one image per page.
- **Split PDF**: split a PDF into one file per page range (such as `1-3, 5, 8-10`) or every N pages, or extract
  the chosen pages into a single PDF. A numbered preview of the pages helps pick the ranges.

There are no accounts and nothing is stored. Each file is processed in a temporary folder that is
deleted before the response is sent.

**Stack:** FastAPI (Python 3.13) backend · React + Vite + TypeScript frontend · Ghostscript, pypdf, Pillow and img2pdf.

## Run with Docker (recommended)

Requires Docker with Compose v2.

```bash
docker compose up --build
```

- App and API: http://localhost:8080 (the API is under `/api/`)

The port is bound to `127.0.0.1`, so the app is only reachable from this machine. The backend isn't
published at all; nginx in the frontend container is the only way in. To expose the app on your
network, change the `ports` entry in `docker-compose.yml`. The app has no authentication, so only do
this on a network you trust.

The interactive API docs (Swagger) are available when running locally, at http://localhost:8000/docs.

Rebuild regularly (`docker compose build --pull`) to pick up security fixes for Ghostscript and the base images.

## Run locally (development)

Requirements: Python 3.13, Node 22 and Ghostscript (`sudo apt install ghostscript`, or `brew install ghostscript`).

**Backend**

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/uvicorn app.main:app --reload        # http://localhost:8000
```

**Frontend** (in a second terminal)

```bash
cd frontend
npm install
npm run dev                                     # http://localhost:5173, proxies /api to :8000
```

**Checks**

```bash
cd backend && .venv/bin/pytest                  # backend tests
cd frontend && npm run lint && npm run build    # lint, type-check and build
```

## Configuration

The backend reads these environment variables. Each must be a positive integer, and the app refuses
to start otherwise.

| Variable | Default | Purpose |
|---|---|---|
| `MAX_FILE_SIZE_MB` | `50` | Largest single uploaded file |
| `MAX_TOTAL_SIZE_MB` | `200` | Largest request body (checked before the upload is read) |
| `MAX_FILES` | `20` | Most files in one request |
| `MAX_IMAGE_PIXELS` | `100000000` | Largest image (width × height) for Image to PDF |
| `MAX_CONCURRENT_COMPRESSIONS` | CPU count | Compressions and size estimates at once; extra requests get `503`. An estimate only starts if a slot stays free for a compression, so with `1` there are no estimates |
| `MAX_CONCURRENT_IMAGE_JOBS` | `min(CPU count, 4)` | Image conversions at once; extra requests get `503` |
| `MAX_SPLIT_PARTS` | `500` | Most PDFs one split may produce |
| `MAX_SPLIT_OUTPUT_MB` | `200` | Largest total size of a split's PDFs (each part keeps its own copy of shared fonts and images, so this can exceed the original's size) |
| `MAX_CONCURRENT_SPLITS` | `min(CPU count, 4)` | Splits at once; extra requests get `503` |
| `GS_TIMEOUT_SECONDS` | `120` | Time limit for one compression, or for all three levels of a size estimate |
| `GS_MEMORY_LIMIT_MB` | `2048` | Memory limit for one Ghostscript run |
| `GS_BINARY` | `gs` | Ghostscript executable |
| `ALLOWED_ORIGINS` | `http://localhost:5173` | Comma-separated CORS origins (only needed when the frontend runs on another origin) |

If you change the size or file-count limits, update the matching constants in
`frontend/src/fileItems.ts` (the frontend checks them before uploading) and `client_max_body_size`
in `frontend/nginx.conf`.

## API

All endpoints take `multipart/form-data` and return the resulting PDF (or ZIP) as a download. Errors return
JSON `{"detail": "..."}` with status 400, 413, 422 or 503.

| Endpoint | Fields | Result |
|---|---|---|
| `POST /api/merge` | `files` (2 or more PDFs, in order) | `merged.pdf` |
| `POST /api/split` | `file` (one PDF), `mode` = `ranges` (default) \| `every`, `ranges` (for `ranges`: comma-separated, non-overlapping, e.g. `1-3, 5, 8-10`; at most 1000 characters), `every` (for `every`: pages per file, default `1`), `merge` = `true` \| `false` (default; `ranges` only) | One PDF per range or chunk, as `<name>_split.zip`. A single result is returned as `<name>_<range>.pdf`, and with `merge=true` all ranges go into `<name>_split.pdf` |
| `POST /api/compress` | `file` (one PDF), `level` = `low` \| `medium` (default) \| `high` | `<name>_compressed.pdf`, plus `X-Original-Size` / `X-Compressed-Size` headers |
| `POST /api/compress/estimate` | `file` (one PDF) | `{"original_size": n, "sizes": {"low": n, "medium": n, "high": n}}`: the exact size `/api/compress` returns at each level |
| `POST /api/images-to-pdf` | `files` (1 or more JPEG/PNG, in order) | `images.pdf` |
| `GET /api/health` | none | `{"status": "ok"}` |

Example:

```bash
curl -F files=@a.pdf -F files=@b.pdf http://localhost:8080/api/merge -o merged.pdf
```

(Use port 8000 when running the backend locally.)

## Security notes

- **Uploads are checked by content, not extension**, and are limited in size and count before they're processed.
- **Ghostscript runs with `-dSAFER`**, plus memory and CPU limits, a timeout and a cap on concurrent jobs.
- **Images are decoded only by Pillow's JPEG or PNG decoder**, with a pixel limit against decompression bombs.
- **In Docker:**
  - both containers run as non-root users;
  - they have read-only filesystems and drop all Linux capabilities;
  - the backend container has a 4 GB memory cap, and its `/tmp` is a disk volume so uploads don't count against it;
  - nginx sends a strict Content-Security-Policy and other security headers.
- **Owner-password restrictions are removed.** PDFs with only an owner password (print or copy restrictions) are
  processed, and the result doesn't keep those restrictions. PDFs that need a password to open are rejected.

## Project layout

```
backend/    FastAPI app (app/routers, app/services, app/utils), pytest suite, Dockerfile
frontend/   React app (src/pages, src/components, src/api), nginx.conf, Dockerfile
docker-compose.yml
```
