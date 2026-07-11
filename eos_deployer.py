#!/usr/bin/env python3
"""
EOS Deployer watcher for D:\RPES-v2\WORKBOARD.md  (profile: eos-deployer)

Loop:
  1. Poll D:\RPES-v2 git for NEW commits whose message contains "Reviewed:".
  2. When a Reviewed: commit lands AND the board has items under VERIFIED,
     run the deploy gate (RPES M1 conformance suite must stay 5/5 PASS).
  3. Move each VERIFIED item -> DEPLOYED (append " -> DEPLOYED.").
  4. Write the board through eos_governed_write (actor_type=institutional_body,
     action_type=governance, evidence=["workboard-update-protocol"]).
  5. Commit the board with `git -C D:\RPES-v2 add WORKBOARD.md` ONLY.
  6. On ANY failure: append a TASK to the board describing the failure.

Hard constraints (RULES + operator):
  - Never touch D:\Reason.
  - Never run rm -rf.
  - All WORKBOARD.md writes go through the governed channel.
  - Only ever `git add WORKBOARD.md`; never `git commit -a` / stage other files.

Run:
  py eos_deployer.py            # blocks forever, polls every 15 min
  py eos_deployer.py --once    # single pass then exit
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

# --- governed write channel (institutional_body) ---------------------------
# eos_governed_write.py lives in D:\RPES-v2 (the deployer's repo), not in
# D:\EOS\wrappers. Add both locations to sys.path so the import resolves.
_RPES_V2 = Path(r"D:\RPES-v2")
if str(_RPES_V2) not in sys.path:
    sys.path.insert(0, str(_RPES_V2))
sys.path.insert(0, r"D:\EOS\wrappers")
from eos_governed_write import eos_governed_write  # noqa: E402

# --- Coder Execution Gate (Deployer monitor runs through it) ----------------
sys.path.insert(0, r"D:\EOS\services\coder")
CODER_AVAILABLE = True
try:
    from coder import Coder  # noqa: E402
except Exception as _imp_err:  # pragma: no cover - defensive
    Coder = None
    CODER_AVAILABLE = False
    print(f"{YELLOW if False else ''}[warn] Coder gate unavailable: {_imp_err}{RESET if False else ''}", flush=True)

# --- paths -----------------------------------------------------------------
RPES        = Path(r"D:\RPES-v2")
WORKBOARD   = RPES / "WORKBOARD.md"
CONFORMANCE = RPES / "rpes" / "rpes" / "conformance" / "run_conformance.py"
PY          = "py"
SEEN_FILE   = RPES / ".deployer-seen-commits.txt"
LOG_FILE    = RPES / ".deployer-log.txt"

GOV_ACTOR    = "eos-deployer"
GOV_ATYPE    = "governance"
GOV_EVIDENCE = ["workboard-update-protocol"]
# Real triggers are commits whose SUBJECT begins with "Reviewed:" or "Fix:"
# (per eos_review_watcher.py commit format). Unanchored matching would catch
# unrelated commits that merely mention those words.
TRIGGER_RE   = re.compile(r"^(Reviewed:|Fix:)")
POLL_SECONDS = 15 * 60  # 15 minutes
# Liveness heartbeat cadence. The Deployer's WORK cycle is POLL_SECONDS (900s)
# but the telemetry monitor flags an agent "stale" after MISSING_AFTER=180s.
# To keep liveness honest (and avoid the monitor auto-restarting a healthy
# agent into a duplicate), the heartbeat runs in its own fast daemon thread,
# decoupled from the slow work cycle.
HB_INTERVAL = 60  # seconds between liveness beats (well under 180s)

DIM = "\033[2m"; GREEN = "\033[92m"; RED = "\033[91m"; YELLOW = "\033[93m"; RESET = "\033[0m"


def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"[{ts}] {msg}"
    print(f"{DIM}[{ts}]{RESET} {msg}", flush=True)
    try:
        with LOG_FILE.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass


# --- git helpers -----------------------------------------------------------
def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(RPES), *args],
        capture_output=True, text=True,
    )


def seen_commits() -> set:
    if not SEEN_FILE.exists():
        return set()
    return {ln.strip() for ln in SEEN_FILE.read_text(encoding="utf-8").splitlines() if ln.strip()}


def record_seen(sha: str) -> None:
    with SEEN_FILE.open("a", encoding="utf-8") as fh:
        fh.write(sha + "\n")


def new_reviewed_commits() -> list:
    """SHAs of Reviewed:/Fix: commits not yet processed, newest first."""
    seen = seen_commits()
    out = git("log", "--format=%H %s")
    if out.returncode != 0:
        return []
    pending = []
    for ln in out.stdout.splitlines():
        if not ln.strip():
            continue
        sha, _, subject = ln.partition(" ")
        if sha in seen:
            continue
        if TRIGGER_RE.search(subject):
            pending.append(sha)
    return pending


# --- board parsing ---------------------------------------------------------
SECTION_RE = re.compile(r"^##\s+(.*?)\s*$")
ITEM_RE    = re.compile(r"^-\s*\[([ x])\]\s*(.*)$")


def split_sections(text: str) -> dict:
    sections = {}
    current = None
    for line in text.splitlines():
        m = SECTION_RE.match(line)
        if m:
            current = m.group(1).strip()
            sections.setdefault(current, [])
        elif current is not None:
            sections[current].append(line)
    return sections


def parse_items(lines: list) -> list:
    items = []
    for ln in lines:
        m = ITEM_RE.match(ln)
        if m:
            items.append((m.group(1) == "x", m.group(2).strip()))
    return items


def build_board(tasks, verified, rejected, deployed, other):
    out = ["# RPES-v2 Institution Workboard", ""]
    if "RULES" in other:
        out.append("## RULES"); out.extend([l for l in other["RULES"] if l.strip()]); out.append("")
    if "RPES-v2 \u2194 EOS Mapping" in other:
        out.append("## RPES-v2 \u2194 EOS Mapping")
        out.extend([l for l in other["RPES-v2 \u2194 EOS Mapping"] if l.strip()]); out.append("")

    def sec(name, items):
        block = [f"## {name}"]
        for _, txt in items:
            block.append(f"- [x] {txt}")
        block.append("")
        return block

    out.extend(sec("TASKS", tasks))
    out.extend(sec("DONE", []))
    out.extend(sec("VERIFIED", verified))
    out.extend(sec("REJECTED", rejected))
    out.extend(sec("DEPLOYED", deployed))
    for k, v in other.items():
        if k in ("RULES", "RPES-v2 \u2194 EOS Mapping", "TASKS", "DONE", "VERIFIED", "REJECTED", "DEPLOYED"):
            continue
        out.extend(sec(k, parse_items(v) if isinstance(v, list) else []))
    return "\n".join(out).rstrip() + "\n"


def read_board() -> str:
    return WORKBOARD.read_text(encoding="utf-8")


# --- governed board write --------------------------------------------------
# NOTE: the Deployer no longer writes the board directly. Board mutations go
# through task_store.propose('deployer', ...) and are committed solely by the
# Orchestrator. This function is retained ONLY as a documented dead reference
# of the pre-migration path and is never called.
def write_board_governed(content: str, intent_summary: str) -> bool:  # pragma: no cover
    raise RuntimeError("write_board_governed is disabled; use task_store.propose")


# --- deploy gate -----------------------------------------------------------
def run_conformance() -> dict:
    try:
        res = subprocess.run(
            [PY, str(CONFORMANCE)],
            cwd=str(CONFORMANCE.parent),
            capture_output=True, text=True, timeout=180,
        )
    except Exception as e:  # noqa
        return {"ok": False, "error": f"conformance crashed: {e}"}
    text = res.stdout + res.stderr
    s = {"total": -1, "passed": -1, "failed": -1, "errors": -1}
    for line in text.splitlines():
        m = re.match(r"^\s*(Total|Passed|Failed|Errors):\s*(\d+)\s*$", line)
        if m:
            s[m.group(1).lower()] = int(m.group(2))
    s["ok"] = (s["failed"] == 0 and s["errors"] == 0 and s["passed"] >= 5)
    s["raw"] = text
    return s


# --- failure TASK ----------------------------------------------------------
def add_failure_task(detail: str) -> None:
    """Record a deploy failure as a proposal (not a direct board write). The
    Orchestrator commits it into TASKS atomically and regenerates the export."""
    try:
        import sys
        from pathlib import Path as _P
        _agents = _P(r"D:\RPES-v2\dabdabi-agent\agents")
        if str(_agents) not in sys.path:
            sys.path.insert(0, str(_agents))
        import task_store as ts
        ts.propose("deployer", "deployer_failure", {"detail": detail},
                   intent=f"deploy failure: {detail[:80]}")
        log(f"{YELLOW}Failure proposed to board queue{RESET}")
    except Exception as e:  # noqa: BLE001
        log(f"{RED}Could not even propose failure task: {e}{RESET}")


# --- health monitor (through Coder Execution Gate) -------------------------
def run_health_check() -> None:
    """Deployer monitor: run the Coder-managed health_check every cycle
    (15 min) via the Authorization Engine gate. The Coder script itself
    auto-creates a WORKBOARD TASK on failure via governed_write; this helper
    adds a defensive Deployer TASK only if the gate itself blocks or errors."""
    if not CODER_AVAILABLE or Coder is None:
        log(f"{YELLOW}Coder gate unavailable - skipping health monitor{RESET}")
        return
    try:
        coder = Coder()
        res = coder.run("health_check")
    except Exception as e:  # noqa
        add_failure_task(f"health monitor crashed: {e}")
        return
    outcome = res.get("outcome")
    log(f"{DIM}health monitor gate outcome={outcome} "
        f"authorized={res.get('authorized')} executed={res.get('executed')}{RESET}")
    if outcome != "authorized" or not res.get("executed"):
        # Gate denied or errored - the monitor itself could not run.
        add_failure_task(f"health monitor blocked by Coder gate: {res.get('reason')}")


# --- one cycle -------------------------------------------------------------
def _deploy_verified(verified_text_items, origin: str) -> bool:
    if not verified_text_items:
        return False

    cf = run_conformance()
    if not cf.get("ok"):
        detail = (f"conformance gate FAILED on {origin} "
                  f"(total={cf.get('total')}, passed={cf.get('passed')}, "
                  f"failed={cf.get('failed')}, errors={cf.get('errors')})")
        log(f"{RED}{detail}{RESET}")
        add_failure_task(detail)
        return False

    # Propose the deploy to tasks.db instead of writing the board directly.
    # The Orchestrator is the SOLE committer: it applies the proposal
    # (VERIFIED -> DEPLOYED) atomically and regenerates the read-only export.
    # The Deployer keeps its conformance gate here; the actual board mutation
    # is delegated to the single-writer Orchestrator (ends the race).
    try:
        import sys
        from pathlib import Path as _P
        _agents = _P(r"D:\RPES-v2\dabdabi-agent\agents")
        if str(_agents) not in sys.path:
            sys.path.insert(0, str(_agents))
        import task_store as ts
        ts.propose("deployer", "deployer_deployed",
                   {"items": list(verified_text_items)},
                   intent=f"deploy verified: {origin}")
        log(f"{GREEN}proposed deploy{RESET} of {len(verified_text_items)} "
            f"item(s) for {origin}")
        return True
    except Exception as e:  # noqa: BLE001
        log(f"{RED}deploy propose failed: {e}{RESET}")
        add_failure_task(f"deploy propose failed: {e}")
        return False


def _heartbeat(detail: str = "health check + Reviewed: scan") -> None:
    """Stamp Deployer liveness. Safe to call from any thread; never raises."""
    try:
        from pathlib import Path as _P
        sys.path.insert(0, r"D:\RPES-v2\dabdabi-agent\agents")
        import institution_telemetry as tele
        tele.beat("deployer", status="polling", detail=detail)
    except Exception as _e:  # never silently swallow a heartbeat failure
        import traceback
        traceback.print_exc()
        log(f"{RED}heartbeat beat() failed: {_e}{RESET}")


def _heartbeat_loop() -> None:
    """Daemon thread: beat every HB_INTERVAL so liveness is independent of
    the slow 900s work cycle (the monitor flags 'stale' after 180s)."""
    while True:
        try:
            _heartbeat()
        except Exception:  # pragma: no cover - defensive
            pass
        time.sleep(HB_INTERVAL)


def cycle() -> None:
    # --- telemetry heartbeat (also covered by the daemon thread) ---
    _heartbeat(detail="work cycle + Reviewed: scan")
    # Deployer monitor: health check every cycle (15 min) via Coder gate.
    try:
        run_health_check()
    except Exception as e:  # noqa
        log(f"{RED}health monitor error: {e}{RESET}")
        try:
            add_failure_task(f"health monitor error: {e}")
        except Exception:
            pass

    pending = new_reviewed_commits()
    any_deployed = False

    for sha in reversed(pending):  # oldest unprocessed first
        subj = git("log", "-1", "--format=%s", sha).stdout.strip()
        log(f"{YELLOW}trigger{RESET}: {sha[:8]} '{subj}'")

        text = read_board()
        secs = split_sections(text)
        verified = parse_items(secs.get("VERIFIED", []))
        if not verified:
            log("Reviewed: commit present but VERIFIED is empty - nothing to deploy yet")
            record_seen(sha)
            continue

        if _deploy_verified([txt for _, txt in verified], sha[:8]):
            any_deployed = True
        record_seen(sha)

    # Fallback: if no new Reviewed: commits, still advance any surviving VERIFIED items.
    if not pending:
        text = read_board()
        secs = split_sections(text)
        verified = parse_items(secs.get("VERIFIED", []))
        deployed = parse_items(secs.get("DEPLOYED", []))
        deployed_texts = {txt for _, txt in deployed}
        pending_texts = [
            txt for _, txt in verified
            if not txt.endswith(" -> DEPLOYED.") or txt not in deployed_texts
        ]
        if pending_texts:
            origin = "verified-backfill"
            log(f"{YELLOW}fallback{RESET}: deploying {len(pending_texts)} pending VERIFIED item(s)")
            if _deploy_verified(pending_texts, origin):
                any_deployed = True

    if not pending and not any_deployed:
        log("no new Reviewed:/Fix: commits")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--interval", type=int, default=POLL_SECONDS)
    args = ap.parse_args()

    log(f"EOS Deployer watcher started on {WORKBOARD}")
    if args.once:
        try:
            cycle()
        except Exception as e:  # noqa
            log(f"{RED}cycle error: {e}{RESET}")
            add_failure_task(f"cycle exception: {e}")
        return
    # Long-lived mode: start the liveness heartbeat thread (decoupled from the
    # 900s work cycle) so the monitor never sees a false "stale" and tries to
    # auto-restart a healthy agent into a duplicate process.
    _hb = threading.Thread(target=_heartbeat_loop, name="deployer-hb", daemon=True)
    _hb.start()
    while True:
        try:
            cycle()
        except Exception as e:  # noqa
            log(f"{RED}watch error: {e}{RESET}")
            try:
                add_failure_task(f"watch exception: {e}")
            except Exception:
                pass
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
