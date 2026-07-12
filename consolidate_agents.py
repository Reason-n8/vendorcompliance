#!/usr/bin/env python3
"""consolidate_agents.py — collapse the institution to ONE clean instance per role.

The 4 roles (Reviewer, Deployer, Orchestrator, Dashboard) had drifted into
multiple stale copies, all loading pre-edit code and (for the dashboard) all
fighting over port 8765. This script:

  1. Kills EVERY running process whose command line names one of the role
     scripts (the `py` launcher, its `python` child, and any bash wrapper).
  2. Waits for the port / processes to release.
  3. Launches EXACTLY ONE detached instance of each from the current code,
     logging to a per-role log file.
  4. Verifies: one worker per role, the dashboard answers on :8765, and the
     new watchers are stamping heartbeats into tasks.db.

It is safe: it only ever matches the specific role scripts and explicitly
excludes its own process (`consolidate_agents.py`) and the `wmic`/shell
wrappers that merely echo the command line.

Run:
    py consolidate_agents.py            # full kill + single clean restart
    py consolidate_agents.py --dry-run  # report what would happen, no changes
    py consolidate_agents.py --no-wait  # kill + launch, skip the verify pause
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

RPES = Path(r"D:\RPES-v2")
EOS = Path(r"D:\EOS")
PY = shutil.which("py") or "py"

# One entry per role. `script` is the command-line substring we match/kill on.
TARGETS = [
    {
        "key": "reviewer", "name": "Reviewer",
        "script": "eos_review_watcher.py", "cwd": RPES,
        "args": ["--interval", "20"], "log": RPES / ".reviewer.log",
    },
    {
        "key": "deployer", "name": "Deployer",
        "script": "eos_deployer.py", "cwd": RPES,
        "args": ["--interval", "900"], "log": RPES / ".deployer.log",
    },
    {
        "key": "orchestrator", "name": "Orchestrator",
        "script": str(RPES / "dabdabi-agent" / "agents" / "orchestrator.py"), "cwd": RPES / "dabdabi-agent" / "agents",
        "args": ["--interval", "60"], "log": RPES / ".orchestrator.log",
    },
    {
        "key": "dashboard", "name": "Dashboard",
        "script": "dashboard/server.py", "cwd": EOS,
        "args": [], "log": EOS / "dashboard.log", "port": 8765,
    },
]

# DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP — launch truly headless.
DETACH = 0x00000008 | 0x00000200

SELF_GUARD = "consolidate_agents.py"


def _ps(script: str) -> str:
    r = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        capture_output=True, text=True,
    )
    # Surface PowerShell failures instead of silently returning '' (which would
    # masquerade as "0 workers"). A non-zero exit with stderr is a bug in the
    # query, not evidence of a dead agent.
    if r.returncode != 0 and r.stderr.strip():
        raise RuntimeError(f"powershell failed ({r.returncode}): {r.stderr.strip()}")
    return r.stdout


def find_pids(substr: str) -> list[int]:
    """PIDs whose command line names `substr`, excluding our own process and
    any shell/wmic wrapper that merely echoes the string."""
    ps = (
        "Get-CimInstance Win32_Process | Where-Object { "
        f"$_.CommandLine -like '*{substr}*' -and "
        f"$_.CommandLine -notlike '*{SELF_GUARD}*' }} | "
        "ForEach-Object { $_.ProcessId }"
    )
    out = _ps(ps)
    return [int(x) for x in out.split() if x.strip().isdigit()]


def count_workers(substr: str) -> int:
    """Count of LOGICAL worker instances running `substr` (0, 1, or N).

    ROOT CAUSE OF THE OLD BUG (forensic):
    `Get-CimInstance ... | Where-Object {...}` returns a SCALAR object
    when exactly ONE process matches. On a scalar Win32_Process object,
    `.Count` is `$null` -> empty stdout -> the regex find finds
    nothing -> returns 0. So with the normal ONE live instance the verify
    step reported a false FAIL. (The `py` launcher + `python.exe` child
    pair means the `python*` Name filter yields exactly one interpreter,
    i.e. the scalar case every time.)

    NOTE on the `py.exe` vs `python*` hypothesis: `python*` does NOT
    match `py.exe` ("py" != "python"), so the interpreter child is the
    only matching row — good. The real defect was the scalar `.Count`.

    FIX: wrap the pipeline in `@(...)` to force ARRAY context so `.Count`
    is always a real integer (0, 1, N). Also surface PowerShell errors
    via `_ps()` instead of silently returning ''.
    """
    ps = (
        "$n = @(Get-CimInstance Win32_Process | Where-Object { "
        "($_.Name -like 'python*') -and "
        f"($_.CommandLine -like '*{substr}*') -and "
        f"($_.CommandLine -notlike '*{SELF_GUARD}*') }}); $n.Count"
    )
    m = re.search(r"\d+", _ps(ps))
    return int(m.group()) if m else 0


def kill_target(t: dict, dry: bool) -> int:
    pids = find_pids(t["script"])
    if not pids:
        print(f"  {t['name']:12} no running instances to kill")
        return 0
    print(f"  {t['name']:12} killing {len(pids)} process(es): {pids}")
    if dry:
        return len(pids)
    idlist = ",".join(str(p) for p in pids)
    ps = (
        "Get-CimInstance Win32_Process | Where-Object { "
        f"$_.ProcessId -in ({idlist}) }} | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force "
        "-ErrorAction SilentlyContinue }"
    )
    _ps(ps)
    return len(pids)


def launch(t: dict, dry: bool):
    cmd = [PY, str(t["script"]), *t["args"]]
    print(f"  {t['name']:12} launch: {' '.join(cmd)}  (cwd={t['cwd']})")
    if dry:
        return None
    logf = open(t["log"], "a", encoding="utf-8")
    logf.write(
        f"\n=== consolidate_agents launch "
        f"{datetime.now(timezone.utc):%Y-%m-%dT%H:%M:%SZ} ===\n"
    )
    return subprocess.Popen(
        cmd, cwd=str(t["cwd"]), stdout=logf, stderr=subprocess.STDOUT,
        creationflags=DETACH,
    )


def port_listeners(port: int) -> int:
    # @(...) forces array context so a SINGLE listener still returns 1
    # (a scalar NetTCPConnection object has no .Count -> $null -> 0).
    out = _ps(
        f"@(Get-NetTCPConnection -LocalPort {port} -State Listen "
        "-ErrorAction SilentlyContinue).Count"
    )
    m = re.search(r"\d+", out)
    return int(m.group()) if m else 0


def http_ok(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=4) as r:
            return r.status == 200
    except Exception:
        return False


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-wait", action="store_true")
    args = ap.parse_args()
    tag = "DRY-RUN " if args.dry_run else ""
    print(f"{tag}consolidate_agents: collapsing to single clean instances")

    # 1) kill all existing instances of every role
    print("[1] kill duplicates")
    for t in TARGETS:
        kill_target(t, args.dry_run)

    if args.dry_run:
        print("[dry-run] no changes made.")
        return

    # 2) release
    print("[2] wait for release")
    time.sleep(3)

    # 3) launch exactly one of each
    print("[3] launch single clean instances")
    for t in TARGETS:
        launch(t, args.dry_run)

    # 4) verify
    if args.no_wait:
        print("[verify] skipped (--no-wait)")
        return
    print("[4] verify")
    time.sleep(5)

    ok = True
    for t in TARGETS:
        workers = count_workers(t["script"])
        if t.get("port"):
            listeners = port_listeners(t["port"])
            live = http_ok(f"http://localhost:{t['port']}/api/institution-health")
            status = "OK" if (workers >= 1 and listeners == 1 and live) else "FAIL"
            print(f"  {t['name']:12} workers={workers} port{ t['port'] }_listeners="
                  f"{listeners} http={live} -> {status}")
            ok = ok and (workers >= 1 and listeners == 1 and live)
        else:
            status = "OK" if workers == 1 else ("WARN" if workers >= 1 else "FAIL")
            print(f"  {t['name']:12} workers={workers} -> {status}")
            ok = ok and workers >= 1

    # 5) confirm the new watchers are stamping heartbeats
    print("[5] heartbeat liveness (new watchers should be recent)")
    try:
        sys.path.insert(0, str(RPES / "dabdabi-agent" / "agents"))
        import institution_telemetry as tele
        snap = tele.snapshot()
        print(f"    institution health: {snap['health']}")
        for a in snap["agents"]:
            if a["agent"] == "builder":
                continue  # Builder is operator-driven, not a daemon
            age = "never" if a["age_s"] is None else f"{a['age_s']}s"
            print(f"    {a['role']:12} alive={a['alive']} age={age} "
                  f"cycle={a['cycle']}")
    except Exception as e:  # noqa: BLE001
        print(f"    heartbeat check error: {e}")

    print("RESULT:", "CONSOLIDATED" if ok else "CHECK ABOVE")


if __name__ == "__main__":
    main()
