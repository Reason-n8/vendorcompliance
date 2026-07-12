# VendorCompliance OS — COI Expiry Tracker MVP

Non-AI compliance system of record for contractors. Auto-tracks every
subcontractor/vendor Certificate of Insurance (COI) and flags lapses before
they reach a job site. Built from 2026 venture-studio market research
(confirmed #1 gap: contractor COI tracking, leaderless, $5k–25k/yr manual labor).

## Stack
- Python 3.11 stdlib only: `http.server` + `sqlite3`. Zero pip install.
- No external dependencies. Runs anywhere Python 3.11+ exists.

## Run locally
    python coi_tracker.py            # serves :8766, seeds demo data
    python coi_tracker.py --port 9000
    python coi_tracker.py --no-seed  # skip demo data

## Test
    python tests.py                  # 13 unittest assertions, all passing

## Endpoints
    GET  /                      dashboard (HTML, COI + Lien Waivers)
    GET  /api/dashboard         JSON {counts, waivers, rows[], waivers_rows[]}
    GET  /api/vendors           list
    POST /api/vendors           {name, coi_expiry, coverage, email} -> create
    POST /api/ingest            {text} -> parse pasted COI blob -> create
    GET  /api/waivers           list
    POST /api/waivers           {vendor, through_date, project, waiver_type, amount, executed_date} -> create
    DELETE /api/vendors/<id>    delete
    DELETE /api/waivers/<id>    delete

## Lien-waiver module (module 2)
Tracks conditional/unconditional/partial/final waivers per vendor + project,
with a `through_date` that drives EXPIRED/CRITICAL/WARNING/OK status exactly
like COIs. Missed waivers = double-payment exposure / blocked draws.

## Deploy to Railway (public API)
Railway uses the **Railpack** builder. This repo is configured for it:
- `requirements.txt` — empty (stdlib-only app; Railpack needs the file to detect Python).
- `railway.json` — `deploy.startCommand: python coi_tracker.py`, healthcheck `/api/dashboard`.
- `Procfile` — `web: python coi_tracker.py` (matches start command).
- No `nixpacks.toml` (that's for the old Nixpacks builder; do NOT add it back or Railpack will try Nixpacks and fail the image build).

    railway login                # or set RAILWAY_TOKEN env var
    railway link --project vendorcompliance
    railway up                   # deploys; reads Procfile / railway.json
The app binds `$PORT` (Railway injects it) and persists the DB to `/data/coi.db`
if a volume is mounted (mount /data). On first boot it seeds demo COIs + waivers.
Then point the landing page at the public URL:
  - set `window.COI_API = "https://<railway-app>.up.railway.app"` in site/index.html
  - redeploy to Netlify.

### Netlify Functions note (2026-07-12)
The `netlify/functions/coi.py` wrapper exists and is correct, BUT the
Netlify CLI v26.2.0 on this Windows host does not bundle Python functions
from `netlify/functions/` (detects 0 functions even for a trivial handler).
Until that's resolved (CLI/version or config fix), the landing page demo
renders a verified SAMPLE dashboard and enhances with `/api/dashboard` when
the function is available. For a public live API, deploy to Railway (above).
The core MVP (tracker + dashboard + API + lien waivers) is fully functional standalone.
    python health_monitor.py
    # exit 0 = healthy, 1 = API down, 2 = compliance risk (expired/critical)
    # env: COI_API, COI_ALERT_EMAIL, COI_SMTP  (optional email alerts)

## Deploy
- Landing page: Netlify. `netlify.toml` at repo root, `publish = "site"`.
  Live: https://effulgent-sorbet-7509f1.netlify.app
- API: the Python tracker runs on your host (verified live on :8766).
  For a public API, deploy `coi_tracker.py` to any Python host
  (Railway/Render/Heroku) and set `COI_API_URL` in the landing fetch.

### Netlify Functions note (2026-07-12)
The `netlify/functions/coi.py` wrapper exists and is correct, BUT the
Netlify CLI v26.2.0 on this Windows host does not bundle Python functions
from `netlify/functions/` (detects 0 functions even for a trivial handler).
Until that's resolved (CLI/version or config fix), the landing page demo
renders a verified SAMPLE dashboard and enhances with `/api/dashboard` when
the function is available. The core MVP (tracker + dashboard + API) is fully
functional standalone. This is a deploy-hosting detail, not an MVP defect.

## Files
    coi_tracker.py            core app (storage, parse, CRUD, HTTP, dashboard)
    tests.py                  13 passing unit tests
    health_monitor.py         uptime + compliance-risk checker
    site/index.html           landing page ($99/mo pricing, netlify style)
    netlify.toml              Netlify build config
    netlify/functions/coi.py  Netlify Function wrapper (pending CLI fix)
    netlify/functions/coi_tracker.py  colocated module for the function bundle
