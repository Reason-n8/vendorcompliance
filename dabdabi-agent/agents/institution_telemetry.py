#!/usr/bin/env python3
"""Institution self-telemetry layer (RPES-v2 / EOS).

The 4 agents (Builder, Reviewer, Deployer, Orchestrator) don't share liveness
state. This module is the minimum viable synchronization layer:

  * AGENTS WRITE A HEARTBEAT on every cycle (one UPSERT into `heartbeats`).
  * A MONITOR reads heartbeats + task lanes and detects:
      - dead agents (no heartbeat for > MISSING limit)  -> alert + auto-restart
      - stuck items (an item sitting in one lane for > STUCK cycles)
        -> escalate to Orchestrator (a proposal)
  * No agent waits on another; each just stamps state. The monitor is the only
    process that reads everything and reacts.

Schema additions (created idempotently by init_telemetry):
  heartbeats(agent TEXT PRIMARY KEY, role TEXT, last_seen TEXT,
             cycle INTEGER, status TEXT, detail TEXT, pid INTEGER)
  escapes(agent TEXT, triggered_at TEXT, kind TEXT, detail TEXT)

All writes go through tasks.db (WAL) alongside task_store. This module imports
task_store only for the DB path and the proposal channel — it never becomes a
second writer of `tasks`.
"""
from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_AGENT_DIR = Path(__file__).resolve().parent
if str(_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(_AGENT_DIR))

import task_store as ts  # noqa: E402  # gives us DB_PATH + propose()

DB_PATH = ts.DB_PATH

# Heartbeat thresholds (seconds).
MISSING_AFTER = int(os.environ.get("TELE_HB_MISSING", "180"))      # 3 missed @60s
RESTART_AFTER = int(os.environ.get("TELE_HB_RESTART", "300"))      # 5 missed @60s
# Stuck-lane detection (number of poll cycles an item sits unmoved in a lane).
STUCK_CYCLES = int(os.environ.get("TELE_STUCK_CYCLES", "5"))

KNOWN_AGENTS = ("builder", "reviewer", "deployer", "orchestrator")
ROLE_OF = {
    "builder": "Builder",
    "reviewer": "Reviewer",
    "deployer": "Deployer",
    "orchestrator": "Orchestrator",
}

GREEN = "\033[92m"; RED = "\033[91m"; YELLOW = "\033[93m"
CYAN = "\033[96m"; DIM = "\033[2m"; BOLD = "\033[1m"; RESET = "\033[0m"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _conn():
    c = ts._conn()
    return c


def init_telemetry() -> None:
    """Create the telemetry tables if absent. Idempotent."""
    c = _conn()
    try:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS heartbeats (
            agent      TEXT PRIMARY KEY,
            role       TEXT,
            last_seen  TEXT,
            cycle      INTEGER,
            status     TEXT,
            detail     TEXT,
            pid        INTEGER
        );
        CREATE TABLE IF NOT EXISTS escapes (
            id          INTEGER PRIMARY KEY,
            agent       TEXT,
            triggered_at TEXT,
            kind        TEXT,
            detail      TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_escapes_agent ON escapes(agent);
        """)
        c.commit()
    finally:
        c.close()


def beat(agent: str, *, cycle: int | None = None, status: str = "alive",
         detail: str = "", pid: int | None = None) -> None:
    """Agent stamps liveness. Call once per poll cycle."""
    if agent not in KNOWN_AGENTS:
        raise ValueError(f"beat: unknown agent '{agent}'")
    init_telemetry()
    c = _conn()
    try:
        c.execute(
            """INSERT INTO heartbeats(agent, role, last_seen, cycle, status, detail, pid)
               VALUES(?,?,?,?,?,?,?)
               ON CONFLICT(agent) DO UPDATE SET
                 role=excluded.role, last_seen=excluded.last_seen,
                 cycle=excluded.cycle, status=excluded.status,
                 detail=excluded.detail, pid=excluded.pid""",
            (agent, ROLE_OF[agent], _now(), cycle, status, detail, pid))
        c.commit()
    finally:
        c.close()


def get_heartbeats() -> dict:
    init_telemetry()
    c = _conn()
    try:
        rows = c.execute("SELECT * FROM heartbeats").fetchall()
        return {r["agent"]: dict(r) for r in rows}
    finally:
        c.close()


def record_escape(agent: str, kind: str, detail: str) -> None:
    init_telemetry()
    c = _conn()
    try:
        c.execute(
            "INSERT INTO escapes(agent, triggered_at, kind, detail) "
            "VALUES(?,?,?,?)",
            (agent, _now(), kind, detail))
        c.commit()
    finally:
        c.close()


def recent_escapes(limit: int = 20) -> list:
    init_telemetry()
    c = _conn()
    try:
        rows = c.execute(
            "SELECT * FROM escapes ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        c.close()


def _age_seconds(last_seen: str) -> float:
    try:
        dt = datetime.fromisoformat(last_seen)
    except Exception:
        return 1e9
    return (datetime.now(timezone.utc) - dt).total_seconds()


def snapshot() -> dict:
    """Full institutional-health snapshot for the dashboard / monitor."""
    hbs = get_heartbeats()
    now = datetime.now(timezone.utc)
    agents = []
    for agent in KNOWN_AGENTS:
        hb = hbs.get(agent)
        if hb:
            age = _age_seconds(hb["last_seen"])
            alive = age <= MISSING_AFTER
            agents.append({
                "agent": agent,
                "role": hb.get("role") or ROLE_OF[agent],
                "last_seen": hb["last_seen"],
                "age_s": int(age),
                "cycle": hb.get("cycle"),
                "status": hb.get("status", "alive"),
                "detail": hb.get("detail", ""),
                "pid": hb.get("pid"),
                "alive": alive,
            })
        else:
            agents.append({
                "agent": agent,
                "role": ROLE_OF[agent],
                "last_seen": None,
                "age_s": None,
                "cycle": None,
                "status": "never",
                "detail": "",
                "pid": None,
                "alive": False,
            })

    # Lane counts from tasks.db (source of truth).
    lanes = {s: len(ts.get_tasks(s)) for s in ts.SECTIONS}

    alerts = []
    for a in agents:
        if a["last_seen"] is None:
            alerts.append(f"{a['role']} has never reported a heartbeat")
        elif a["age_s"] > RESTART_AFTER:
            alerts.append(f"{a['role']} MISSING {a['age_s']}s (>{RESTART_AFTER}s) — restart")
        elif a["age_s"] > MISSING_AFTER:
            alerts.append(f"{a['role']} stale {a['age_s']}s (>{MISSING_AFTER}s)")

    health = "degraded" if alerts else "healthy"
    return {
        "generated_at": now.isoformat(),
        "health": health,
        "agents": agents,
        "lanes": lanes,
        "alerts": alerts,
        "thresholds": {
            "missing_after_s": MISSING_AFTER,
            "restart_after_s": RESTART_AFTER,
            "stuck_cycles": STUCK_CYCLES,
        },
        "escapes": recent_escapes(10),
    }


# --------------------------------------------------------------------------
# MONITOR: the one process that reads everything and reacts.
# --------------------------------------------------------------------------
_RESTART_CMD = {
    "reviewer": [r"py", r"D:\RPES-v2\eos_review_watcher.py", "--interval", "20"],
    "deployer": [r"py", r"D:\RPES-v2\eos_deployer.py", "--interval", "900"],
    "orchestrator": [r"py", r"D:\RPES-v2\dabdabi-agent\agents\orchestrator.py",
                     "--interval", "60"],
    # Builder is the operator-driven Hermes loop; we cannot spawn a Hermes
    # terminal, so a missing Builder is escalated, not auto-restarted.
}


# Min seconds between two auto-restarts of the SAME agent. Guards against
# fork-bombing: even if a restart fails to take (e.g. port still bound),
# we won't re-issue every monitor tick (the watchdog runs every 5 min).
RESTART_COOLDOWN_S = int(os.environ.get("TELE_HB_RESTART_COOLDOWN", "600"))


# module-level last-restart timestamp per agent (single monitor process owns it)
_LAST_RESTART = {}


def _restart_agent(agent: str) -> str:
    """Best-effort background restart with a per-agent cooldown guard.

    Returns a human note. The cooldown (RESTART_COOLDOWN_S) ensures we
    never auto-restart the same agent more than once per window, so a
    restart that doesn't immediately take effect can't fork-bomb the host.
    """
    cmd = _RESTART_CMD.get(agent)
    if not cmd:
        return f"no auto-restart for {agent} (operator-driven)"
    now = time.time()
    last = _LAST_RESTART.get(agent)
    if last is not None and (now - last) < RESTART_COOLDOWN_S:
        remaining = int(RESTART_COOLDOWN_S - (now - last))
        return (f"restart SKIPPED (cooldown: {remaining}s left for {agent}; "
                f"last restart {(now-last):.0f}s ago)")
    try:
        import subprocess
        # Detach so we don't block the monitor; route output to a log.
        logp = Path(r"D:\RPES-v2") / f".{agent}-restart.log"
        with open(logp, "a", encoding="utf-8") as fh:
            subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT,
                             creationflags=0x00000008)  # DETACHED_PROCESS
        _LAST_RESTART[agent] = now
        record_escape(agent, "restart", f"auto-restart issued: {' '.join(cmd)}")
        return f"restart issued: {' '.join(cmd)}"
    except Exception as e:  # noqa: BLE001
        return f"restart FAILED: {e}"


def monitor_once(*, do_restart: bool = True, cycle: int = 0) -> dict:
    """One monitor pass.

    Returns a summary dict and performs side effects (restart + escalate).
    """
    init_telemetry()
    snap = snapshot()
    actions = []

    # 1) Dead / stale agents. Restart ONLY if the agent has been silent
    #    longer than RESTART_AFTER (300s) — i.e. genuinely dead, not just
    #    slow. The decoupled daemon heartbeat (HB_INTERVAL=60s) means a
    #    healthy agent never reaches this threshold, so auto-restart can't
    #    fork-bomb a live agent. _restart_agent adds a per-agent cooldown
    #    as a second guard.
    for a in snap["agents"]:
        if a["last_seen"] is None:
            continue
        if a["age_s"] > RESTART_AFTER and do_restart:
            note = _restart_agent(a["agent"])
            actions.append(f"RESTART {a['role']}: {note}")
        elif a["age_s"] > RESTART_AFTER and not do_restart:
            actions.append(f"ALERT {a['role']}: missing {a['age_s']}s (restart suppressed)")

    # 2) Stuck items: an item unmoved in a lane for STUCK_CYCLES cycles.
    #    We detect "sitting still" by tracking the max task id ever seen per
    #    lane; if the lane's composition hasn't changed in STUCK_CYCLES cycles
    #    AND it holds items, escalate. Simpler robust signal: lane has items
    #    and the top item id has been seen for >= STUCK_CYCLES cycles.
    stuck = _detect_stuck_lanes(cycle)
    for item in stuck:
        # Escalate to Orchestrator as a generic proposal so it can re-balance.
        try:
            ts.propose("orchestrator", "generic",
                       {"section": item["section"],
                        "line": f"TELEMETRY ESCALATION: {item['body'][:200]} "
                                f"(stuck in {item['section']} {item['cycles']} cycles)"},
                       intent=f"escalate stuck: {item['section']}")
            record_escape(item["section"].lower(), "stuck",
                          f"{item['body'][:80]} ({item['cycles']} cycles)")
            actions.append(f"ESCALATE stuck {item['section']}: "
                           f"{item['body'][:50]}")
        except Exception as e:  # noqa: BLE001
            actions.append(f"escalate FAILED: {e}")

    snap["monitor_actions"] = actions
    snap["monitor_cycle"] = cycle
    return snap


def _detect_stuck_lanes(cycle: int) -> list:
    """An item is 'stuck' if its lane hasn't advanced it for STUCK_CYCLES.

    We approximate lane-movement by watching the set of task ids per lane.
    This module keeps a tiny in-memory tombstone of the last-seen lane
    signature; a more durable store would use a `lane_history` table, but the
    monitor runs continuously so in-memory across its own loop is sufficient
    and avoids touching `tasks` writes.
    """
    out = []
    for section in ("TASKS", "DONE", "VERIFIED"):
        rows = ts.get_tasks(section)
        if not rows:
            continue
        ids = tuple(sorted(r["id"] for r in rows))
        key = (section, ids)
        hist = _detect_stuck_lanes._hist  # type: ignore[attr-defined]
        prev = hist.get(section)
        if prev is None:
            hist[section] = {"sig": ids, "first_seen": cycle}
            continue
        if prev["sig"] == ids:
            cycles = cycle - prev["first_seen"]
            if cycles >= STUCK_CYCLES:
                # top item is the stuck one (oldest / lowest id).
                top = min(rows, key=lambda r: r["id"])
                out.append({"section": section, "body": top["body"],
                            "cycles": cycles})
        else:
            hist[section] = {"sig": ids, "first_seen": cycle}
    return out


# module-level mutable history (single monitor process owns it)
_detect_stuck_lanes._hist = {}  # type: ignore[attr-defined]


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--interval", type=int, default=60)
    ap.add_argument("--no-restart", action="store_true",
                    help="detect + alert + escalate but do NOT auto-restart")
    args = ap.parse_args()

    print(f"{BOLD}Institution telemetry monitor started{RESET}")
    cycle = 0
    if args.once:
        snap = monitor_once(do_restart=not args.no_restart, cycle=cycle)
        print("health:", snap["health"])
        for a in snap["agents"]:
            print(f"  {a['role']:12} alive={a['alive']} age={a['age_s']}s "
                  f"cycle={a['cycle']} detail={a['detail']}")
        print("actions:", snap.get("monitor_actions"))
        return
    while True:
        try:
            snap = monitor_once(do_restart=not args.no_restart, cycle=cycle)
            if snap["monitor_actions"] or snap["health"] != "healthy":
                print(f"{YELLOW}[{datetime.now(timezone.utc):%H:%M:%S}]{RESET} "
                      f"health={snap['health']} actions={snap['monitor_actions']}")
        except Exception as e:  # noqa: BLE001
            print(f"{RED}monitor error: {e}{RESET}")
        cycle += 1
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
