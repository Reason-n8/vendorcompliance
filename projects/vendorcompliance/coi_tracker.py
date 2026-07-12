#!/usr/bin/env python3
"""
VendorCompliance OS — COI Expiry Tracker MVP
Stdlib-only: http.server + sqlite3. Zero pip install.

Run:  python coi_tracker.py            (serves :8766, seeds demo data)
      python coi_tracker.py --port 9000
      python tests.py                  (run unit tests)

Endpoints:
  GET  /                      dashboard (HTML)
  GET  /api/dashboard         JSON {total, expired, expiring_30, expiring_60, ok, rows[]}
  GET  /api/vendors           JSON list of vendors
  POST /api/vendors           JSON {name, coi_expiry, coverage, email}  -> create
  POST /api/ingest            JSON {text} or form file=COI.txt -> parse + create
  GET  /api/vendors/<id>      JSON single vendor
  DELETE /api/vendors/<id>    delete
"""
from __future__ import annotations
import argparse, json, sqlite3, os, re, datetime as dt
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

DB_PATH = os.environ.get("COI_DB", os.path.join(os.path.dirname(__file__), "coi.db"))
WARN_DAYS = int(os.environ.get("COI_WARN_DAYS", "30"))   # "expiring soon" window
CRIT_DAYS = int(os.environ.get("COI_CRIT_DAYS", "60"))   # "expiring" window

# ----------------------------------------------------------------------------
# Storage
# ----------------------------------------------------------------------------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(conn):
    conn.execute("""
    CREATE TABLE IF NOT EXISTS vendors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        coi_expiry TEXT NOT NULL,        -- ISO date YYYY-MM-DD
        coverage TEXT DEFAULT '',        -- e.g. "1M/2M" (per-occurrence/aggregate)
        email TEXT DEFAULT '',
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )""")
    conn.execute("""
    CREATE TABLE IF NOT EXISTS waivers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vendor TEXT NOT NULL,            -- subcontractor / vendor name
        project TEXT DEFAULT '',         -- job / project name
        waiver_type TEXT DEFAULT 'conditional',  -- conditional|unconditional|partial|final
        amount TEXT DEFAULT '',          -- $ value covered by the waiver
        executed_date TEXT DEFAULT '',   -- ISO date waiver signed
        through_date TEXT NOT NULL,      -- ISO date waiver valid through (pay period end)
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )""")
    conn.commit()

# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
# Domain logic (pure, testable)
# ----------------------------------------------------------------------------
def parse_date(s: str) -> str | None:
    """Parse many date formats -> ISO YYYY-MM-DD. Returns None if unparseable."""
    if not s:
        return None
    s = s.strip().replace("/", "-").replace(".", "-")
    fmts = ["%Y-%m-%d", "%m-%d-%Y", "%d-%m-%Y", "%Y/%m/%d", "%m/%d/%Y", "%B %d %Y",
            "%b %d %Y", "%d %B %Y", "%d %b %Y", "%m-%d-%y", "%Y%m%d"]
    for f in fmts:
        try:
            return dt.datetime.strptime(s, f).date().isoformat()
        except ValueError:
            continue
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        try:
            return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
        except ValueError:
            return None
    return None

def days_until(iso: str, today: dt.date | None = None) -> int | None:
    today = today or dt.date.today()
    try:
        d = dt.date.fromisoformat(iso)
    except (ValueError, TypeError):
        return None
    return (d - today).days

def status_for(iso: str, today: dt.date | None = None) -> str:
    """expired | critical(<30) | warning(<60) | ok"""
    n = days_until(iso, today)
    if n is None:
        return "unknown"
    if n < 0:
        return "expired"
    if n <= WARN_DAYS:
        return "critical"
    if n <= CRIT_DAYS:
        return "warning"
    return "ok"

def parse_coi_text(text: str) -> dict:
    """Best-effort parse of a pasted COI / email blob into a vendor record.
    Looks for: a vendor/insured name line, a date, optional coverage limits."""
    out = {"name": "", "coi_expiry": "", "coverage": "", "email": ""}
    # email
    m = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
    if m:
        out["email"] = m.group(0)
    # expiry date — first date-looking token
    dm = re.search(r"(\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|"
                   r"\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})",
                   text, re.IGNORECASE)
    if dm:
        out["coi_expiry"] = parse_date(dm.group(0)) or ""
    # coverage like 1,000,000 / 1M / $2,000,000
    cm = re.search(r"(?:\$|\b)(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?\s*[MmKk])", text)
    if cm:
        out["coverage"] = cm.group(0).strip()
    # name: line containing "Insured" / "Named Insured" / "Company"
    for line in text.splitlines():
        low = line.lower()
        if "named insured" in low or "insured:" in low or "company:" in low:
            nm = re.sub(r"(?i)(.*insured\s*:?|company\s*:?)\s*", "", line).strip(" :|-")
            if nm:
                out["name"] = nm[:120]
                break
    if not out["name"]:
        # fallback: first non-empty line
        for line in text.splitlines():
            if line.strip():
                out["name"] = line.strip()[:120]
                break
    return out

# ----------------------------------------------------------------------------
# CRUD
# ----------------------------------------------------------------------------
def add_vendor(conn, name, coi_expiry, coverage="", email=""):
    cur = conn.execute(
        "INSERT INTO vendors (name, coi_expiry, coverage, email) VALUES (?,?,?,?)",
        (name, coi_expiry, coverage, email))
    conn.commit()
    return cur.lastrowid

def delete_vendor(conn, vid):
    conn.execute("DELETE FROM vendors WHERE id=?", (vid,))
    conn.commit()

def list_vendors(conn, today=None):
    rows = conn.execute("SELECT * FROM vendors ORDER BY coi_expiry ASC").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["days_left"] = days_until(d["coi_expiry"], today)
        d["status"] = status_for(d["coi_expiry"], today)
        out.append(d)
    return out

def dashboard(conn, today=None):
    rows = list_vendors(conn, today)
    counts = {"total": len(rows), "expired": 0, "critical": 0, "warning": 0, "ok": 0,
              "unknown": 0}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    return {"counts": counts, "rows": rows}

# ----------------------------------------------------------------------------
# Lien-waiver module
# ----------------------------------------------------------------------------
VALID_TYPES = ("conditional", "unconditional", "partial", "final")

def add_waiver(conn, vendor, through_date, project="", waiver_type="conditional",
               amount="", executed_date=""):
    cur = conn.execute(
        "INSERT INTO waivers (vendor, project, waiver_type, amount, executed_date, through_date) "
        "VALUES (?,?,?,?,?,?)",
        (vendor, project, waiver_type, amount, executed_date, through_date))
    conn.commit()
    return cur.lastrowid

def delete_waiver(conn, wid):
    conn.execute("DELETE FROM waivers WHERE id=?", (wid,))
    conn.commit()

def list_waivers(conn, today=None):
    rows = conn.execute("SELECT * FROM waivers ORDER BY through_date ASC").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["days_left"] = days_until(d["through_date"], today)
        d["status"] = status_for(d["through_date"], today)
        out.append(d)
    return out

def waiver_dashboard(conn, today=None):
    rows = list_waivers(conn, today)
    counts = {"total": len(rows), "expired": 0, "critical": 0, "warning": 0, "ok": 0,
              "unknown": 0}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    return {"counts": counts, "rows": rows}

# Extend the top-level dashboard with waiver counts + rows.
def full_dashboard(conn, today=None):
    coi = dashboard(conn, today)
    wv = waiver_dashboard(conn, today)
    coi["waivers"] = wv["counts"]
    coi["waivers_rows"] = wv["rows"]
    return coi
# Seed demo data
# ----------------------------------------------------------------------------
def seed(conn, today=None):
    today = today or dt.date.today()
    existing = conn.execute("SELECT COUNT(*) AS c FROM vendors").fetchone()["c"]
    if existing:
        return
    samples = [
        ("Apex Electrical Contractors", (today + dt.timedelta(days=-5)).isoformat(), "1M/2M", "apx@apex.com"),
        ("BlueLine Plumbing LLC", (today + dt.timedelta(days=12)).isoformat(), "1M/2M", "ops@blueline.com"),
        ("Cedar Roofing Co", (today + dt.timedelta(days=45)).isoformat(), "2M/4M", "admin@cedar.com"),
        ("Dynamo Concrete Inc", (today + dt.timedelta(days=90)).isoformat(), "1M/2M", "bill@dynamo.com"),
        ("Evergreen HVAC", (today + dt.timedelta(days=3)).isoformat(), "1M/2M", "jane@evergreen.com"),
    ]
    for nm, exp, cov, em in samples:
        add_vendor(conn, nm, exp, cov, em)
    # Lien waivers (per pay period). Through-date drives status.
    waivers = [
        ("Apex Electrical Contractors", "Riverside Elementary", "conditional", "45000",
         (today + dt.timedelta(days=-2)).isoformat(), (today + dt.timedelta(days=-2)).isoformat()),
        ("BlueLine Plumbing LLC", "Maple Ave Reno", "unconditional", "22000",
         (today + dt.timedelta(days=8)).isoformat(), (today + dt.timedelta(days=8)).isoformat()),
        ("Cedar Roofing Co", "Hilltop Commons", "partial", "60000",
         (today + dt.timedelta(days=40)).isoformat(), (today + dt.timedelta(days=40)).isoformat()),
        ("Dynamo Concrete Inc", "Civic Center", "final", "120000",
         (today + dt.timedelta(days=75)).isoformat(), (today + dt.timedelta(days=75)).isoformat()),
    ]
    for v, p, wt, amt, ex, th in waivers:
        add_waiver(conn, v, th, p, wt, amt, ex)

# ----------------------------------------------------------------------------
# HTTP
# ----------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, indent=2, default=str)
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self._send(204, "")

    def _json_body(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        if not length:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    def do_GET(self):
        p = urlparse(self.path)
        path = p.path.rstrip("/") or "/"
        conn = get_db()
        if path == "/" or path == "/index.html":
            self._send(200, dashboard_html(conn), "text/html")
        elif path == "/api/dashboard":
            self._send(200, full_dashboard(conn))
        elif path == "/api/vendors":
            self._send(200, list_vendors(conn))
        elif path == "/api/waivers":
            self._send(200, list_waivers(conn))
        elif path.startswith("/api/vendors/"):
            vid = path.split("/")[-1]
            r = conn.execute("SELECT * FROM vendors WHERE id=?", (vid,)).fetchone()
            if r:
                d = dict(r); d["days_left"] = days_until(d["coi_expiry"]); d["status"] = status_for(d["coi_expiry"])
                self._send(200, d)
            else:
                self._send(404, {"error": "not found"})
        elif path.startswith("/api/waivers/"):
            wid = path.split("/")[-1]
            r = conn.execute("SELECT * FROM waivers WHERE id=?", (wid,)).fetchone()
            if r:
                d = dict(r); d["days_left"] = days_until(d["through_date"]); d["status"] = status_for(d["through_date"])
                self._send(200, d)
            else:
                self._send(404, {"error": "not found"})
        else:
            self._send(404, {"error": "unknown route"})

    def do_POST(self):
        p = urlparse(self.path)
        path = p.path.rstrip("/")
        conn = get_db()
        if path == "/api/vendors":
            b = self._json_body()
            vid = add_vendor(conn, b.get("name",""), b.get("coi_expiry",""),
                             b.get("coverage",""), b.get("email",""))
            self._send(201, {"id": vid, "status": status_for(b.get("coi_expiry",""))})
        elif path == "/api/waivers":
            b = self._json_body()
            wid = add_waiver(conn, b.get("vendor",""), b.get("through_date",""),
                             b.get("project",""), b.get("waiver_type","conditional"),
                             b.get("amount",""), b.get("executed_date",""))
            self._send(201, {"id": wid, "status": status_for(b.get("through_date",""))})
        elif path == "/api/ingest":
            b = self._json_body()
            parsed = parse_coi_text(b.get("text", ""))
            if not parsed.get("coi_expiry") or not parsed.get("name"):
                self._send(422, {"error": "could not parse name/expiry", "parsed": parsed})
            else:
                vid = add_vendor(conn, parsed["name"], parsed["coi_expiry"],
                                 parsed["coverage"], parsed["email"])
                self._send(201, {"id": vid, "parsed": parsed})
        else:
            self._send(404, {"error": "unknown route"})

    def do_DELETE(self):
        p = urlparse(self.path)
        path = p.path.rstrip("/")
        conn = get_db()
        if path.startswith("/api/vendors/"):
            vid = path.split("/")[-1]
            delete_vendor(conn, vid)
            self._send(200, {"deleted": vid})
        elif path.startswith("/api/waivers/"):
            wid = path.split("/")[-1]
            delete_waiver(conn, wid)
            self._send(200, {"deleted": wid})
        else:
            self._send(404, {"error": "unknown route"})

    def log_message(self, *a):
        pass

def dashboard_html(conn):
    d = full_dashboard(conn)
    c = d["counts"]
    w = d["waivers"]
    rows = "".join(
        f"<tr class='{r['status']}'><td>{r['id']}</td><td>{r['name']}</td>"
        f"<td>{r['coi_expiry']}</td><td>{r['days_left']}</td>"
        f"<td>{r['status'].upper()}</td><td>{r['coverage']}</td></tr>"
        for r in d["rows"])
    wrows = "".join(
        f"<tr class='{r['status']}'><td>{r['id']}</td><td>{r['vendor']}</td><td>{r['project']}</td>"
        f"<td>{r['waiver_type']}</td><td>{r['through_date']}</td><td>{r['days_left']}</td>"
        f"<td>{r['status'].upper()}</td></tr>"
        for r in d["waivers_rows"])
    return f"""<!doctype html><html><head><meta charset=utf-8>
<title>VendorCompliance OS — COI + Lien Waiver Tracker</title>
<style>body{{font-family:system-ui,Arial;margin:0;background:#0b0f1a;color:#e8edf7}}
.wrap{{max-width:1000px;margin:0 auto;padding:24px}}
h1{{margin:0 0 4px}} .sub{{color:#9aa6c0;margin-bottom:18px}} h2{{margin-top:28px;font-size:18px;color:#9aa6c0}}
.cards{{display:flex;gap:12px;margin-bottom:20px;flex-wrap:wrap}}
.card{{flex:1;min-width:120px;background:#121829;border:1px solid #1f2940;border-radius:10px;padding:14px;text-align:center}}
.card .n{{font-size:30px;font-weight:700}} .card .l{{color:#9aa6c0;font-size:12px}}
.expired .n{{color:#ff6b6b}} .critical .n{{color:#ffa94d}} .warning .n{{color:#ffe066}} .ok .n{{color:#22d3a6}}
table{{width:100%;border-collapse:collapse;background:#121829;border-radius:10px;overflow:hidden;margin-top:8px}}
th,td{{padding:10px 12px;text-align:left;border-bottom:1px solid #1f2940;font-size:14px}}
th{{background:#0e1424;color:#9aa6c0;font-size:12px;text-transform:uppercase}}
tr.expired td:first-child{{border-left:3px solid #ff6b6b}}
tr.critical td:first-child{{border-left:3px solid #ffa94d}}
tr.warning td:first-child{{border-left:3px solid #ffe066}}
tr.ok td:first-child{{border-left:3px solid #22d3a6}}
code{{background:#0e1424;padding:2px 6px;border-radius:4px}}</style></head>
<body><div class='wrap'>
<h1>VendorCompliance OS</h1><div class='sub'>COI + Lien-Waiver Tracking — $99/mo · never let an expired certificate or missing waiver become a six-figure liability</div>
<div class='cards'>
<div class='card expired'><div class='n'>{c['expired']}</div><div class='l'>COI EXPIRED</div></div>
<div class='card critical'><div class='n'>{c['critical']}</div><div class='l'>COI CRITICAL ≤{WARN_DAYS}d</div></div>
<div class='card warning'><div class='n'>{c['warning']}</div><div class='l'>COI WARNING ≤{CRIT_DAYS}d</div></div>
<div class='card'><div class='n'>{c['total']}</div><div class='l'>TOTAL VENDORS</div></div>
<div class='card expired'><div class='n'>{w['expired']}</div><div class='l'>WAIVER EXPIRED</div></div>
<div class='card critical'><div class='n'>{w['critical']}</div><div class='l'>WAIVER CRITICAL</div></div>
<div class='card'><div class='n'>{w['total']}</div><div class='l'>TOTAL WAIVERS</div></div>
</div>
<h2>Certificates of Insurance (COI)</h2>
<table><thead><tr><th>#</th><th>Vendor</th><th>COI Expiry</th><th>Days Left</th><th>Status</th><th>Coverage</th></tr></thead>
<tbody>{rows}</tbody></table>
<h2>Lien Waivers</h2>
<table><thead><tr><th>#</th><th>Vendor</th><th>Project</th><th>Type</th><th>Through</th><th>Days Left</th><th>Status</th></tr></thead>
<tbody>{wrows}</tbody></table>
<p style='color:#9aa6c0;font-size:12px;margin-top:16px'>API: <code>GET /api/dashboard</code> · <code>POST /api/vendors</code> · <code>POST /api/waivers</code> · <code>POST /api/ingest</code></p>
</div></body></html>"""

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8766")))
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--no-seed", action="store_true")
    args = ap.parse_args()
    # On Railway a volume is mounted at /data; persist the DB there.
    vol = os.environ.get("COI_DB_DIR", "/data")
    if os.path.isdir(vol):
        global DB_PATH
        DB_PATH = os.path.join(vol, "coi.db")
    conn = get_db()
    init_db(conn)
    if not args.no_seed:
        seed(conn)
    conn.close()
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"VendorCompliance OS COI Tracker on http://{args.host}:{args.port}")
    srv.serve_forever()

if __name__ == "__main__":
    main()
