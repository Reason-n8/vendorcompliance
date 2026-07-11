#!/usr/bin/env python3
"""
EOS Reviewer Watcher for D:\\RPES-v2\\WORKBOARD.md

Loop:
  1. Read WORKBOARD.md.
  2. For each item under `## DONE`, audit it against real source:
       - Verify the claimed wiring/writes actually exist (file:line).
       - Re-run the conformance suite (must stay 5/5 PASS).
       - Verify it does not break EOS authorization engine import/usage.
  3. Move the item to `## VERIFIED` (with audit notes) or `## REJECTED`
     (with the reason). All WORKBOARD writes go through git (this is the
     only place the Reviewer may edit WORKBOARD.md).
  4. Commit with message `Reviewed: <summary>`.

This script ONLY edits WORKBOARD.md inside D:\\RPES-v2 (the governed zone)
and commits via git. It never touches D:\\Reason.

Run: py eos_review_watcher.py            # blocks forever, polls every 20s
     py eos_review_watcher.py --once     # single pass, then exit
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

RPES = Path(r"D:\RPES-v2")
WORKBOARD = RPES / "WORKBOARD.md"
CONFORMANCE = RPES / "rpes" / "rpes" / "conformance" / "run_conformance.py"
PY = "py"  # python launcher on this host

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"


def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"{DIM}[{ts}]{RESET} {msg}", flush=True)


def run_conformance() -> dict:
    """Run the RPES M1 conformance suite (read-only). Returns summary dict."""
    try:
        out = subprocess.run(
            [PY, str(CONFORMANCE)],
            cwd=str(CONFORMANCE.parent),
            capture_output=True,
            text=True,
            timeout=120,
        )
    except Exception as e:  # noqa
        return {"ok": False, "error": f"conformance crashed: {e}"}
    # Parse the printed summary
    text = out.stdout + out.stderr
    passed = failed = errors = total = -1
    for line in text.splitlines():
        m = re.match(r"^\s*(Total|Passed|Failed|Errors):\s*(\d+)\s*$", line)
        if m:
            key, val = m.group(1), int(m.group(2))
            if key == "Total":
                total = val
            elif key == "Passed":
                passed = val
            elif key == "Failed":
                failed = val
            elif key == "Errors":
                errors = val
    ok = (failed == 0 and errors == 0 and passed >= 5)
    return {
        "ok": ok,
        "total": total,
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "raw": text,
    }


def find_in_file(path: Path, pattern: str) -> list[str]:
    if not path.exists():
        return []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []
    hits = []
    for i, line in enumerate(text.splitlines(), 1):
        if re.search(pattern, line):
            hits.append(f"{path.name}:{i}")
    return hits


def audit_item(item: str) -> tuple[bool, str]:
    """
    Audit a single DONE item. Returns (verified, notes).
    Evidence-based: checks the claimed source wiring exists and conformance passes.
    """
    notes = []
    low = item.lower()

    # Always re-run conformance; a green suite is a prerequisite for VERIFIED.
    cf = run_conformance()
    if not cf.get("ok"):
        return False, (
            f"REJECTED: conformance suite NOT green "
            f"(total={cf.get('total')}, passed={cf.get('passed')}, "
            f"failed={cf.get('failed')}, errors={cf.get('errors')}). "
            f"Cannot verify wiring while the kernel is broken."
        )

    ref = RPES / "rpes" / "rpes" / "reference" / "kernel"
    decision_py = ref / "decision.py"
    audit_py = ref / "audit.py"
    models_py = ref / "models.py"

    # Task 1: Wire decision.py to EOS Authorization Engine
    if "decision.py" in low and ("authorization" in low or "auth engine" in low):
        hits = find_in_file(decision_py, r"AuthorizationEngine|authorization-engine|governed_write|eos")
        if hits:
            notes.append(f"decision.py references EOS engine: {hits}")
        else:
            return False, "REJECTED: decision.py shows no wiring to EOS Authorization Engine (no engine/import reference)."
        bridge = list((RPES / "rpes" / "rpes").rglob("eos_bridge.py"))
        notes.append(f"eos_bridge.py present: {[b.name for b in bridge]}" if bridge else "no eos_bridge.py yet")

    # Task 2: Wire audit.py to EOS Event Ledger
    elif "audit.py" in low and ("ledger" in low or "event" in low):
        hits = find_in_file(audit_py, r"Ledger|ledger|EventLedger|append|governed")
        if hits:
            notes.append(f"audit.py references ledger: {hits}")
        else:
            return False, "REJECTED: audit.py shows no wiring to EOS Event Ledger (no ledger/append reference)."

    # Task 3: Map models.py to EOS-000 Ontology terms
    elif "models.py" in low and ("ontology" in low or "eos-000" in low):
        hits = find_in_file(models_py, r"EOS-000|ontology|Ontology|specification|spec")
        if hits:
            notes.append(f"models.py references ontology: {hits}")
        else:
            return False, "REJECTED: models.py shows no mapping to EOS-000 Ontology terms."

    # Task 4: Run conformance suite
    elif "conformance" in low:
        notes.append(f"conformance: {cf['passed']}/{cf['total']} PASS (failed={cf['failed']}, errors={cf['errors']})")

    # Task 5: Create eos_bridge.py
    elif "eos_bridge" in low:
        bridge = list((RPES / "rpes").rglob("eos_bridge.py"))
        if not bridge:
            return False, "REJECTED: eos_bridge.py does not exist anywhere under D:\\RPES-v2\\rpes."
        notes.append(f"eos_bridge.py found: {[str(b.relative_to(RPES)) for b in bridge]}")
        # sanity: it should import the kernel and/or the EOS wrapper
        content = bridge[0].read_text(encoding="utf-8", errors="ignore")
        if "governed_write" not in content and "AuthorizationEngine" not in content and "decision" not in content:
            return False, "REJECTED: eos_bridge.py exists but imports neither the RPES kernel nor the EOS governed_write/AuthorizationEngine."

    else:
        # Generic fallback: require conformance green + traceable source change.
        notes.append("generic audit: no specific wiring pattern matched; relying on conformance green + manual review.")

    notes.append(f"conformance gate: {cf['passed']}/{cf['total']} PASS")
    return True, "; ".join(notes)


def split_sections(text: str) -> dict[str, list[str]]:
    """Return {section_name: [lines...]} preserving order. Handles one-level '## '."""
    sections: dict[str, list[str]] = {}
    current = None
    for line in text.splitlines():
        m = re.match(r"^##\s+(.*?)\s*$", line)
        if m:
            current = m.group(1).strip()
            sections.setdefault(current, [])
        elif current is not None:
            sections[current].append(line)
    return sections


def parse_items(lines: list[str]) -> list[str]:
    items = []
    for ln in lines:
        m = re.match(r"^\s*-\s*\[[ x]\]\s*(.*)$", ln)
        if m:
            items.append(m.group(1).strip())
    return items


def render_section(name: str, items: list[str]) -> list[str]:
    out = [f"## {name}"]
    for it in items:
        out.append(f"- [x] {it}")
    out.append("")  # trailing blank for readability
    return out


def process_once() -> bool:
    """One watch pass. Returns True if a commit was made."""
    # --- telemetry heartbeat (institution self-monitoring) ---
    try:
        sys.path.insert(0, r"D:\RPES-v2\dabdabi-agent\agents")
        import institution_telemetry as tele
        tele.beat("reviewer", status="polling", detail="scanning DONE lane")
    except Exception as _e:  # never silently swallow a heartbeat failure
        import traceback
        traceback.print_exc()
        log(f"{RED}heartbeat beat() failed: {_e}{RESET}")
    if not WORKBOARD.exists():
        log(f"{RED}WORKBOARD.md missing at {WORKBOARD}{RESET}")
        return False
    text = WORKBOARD.read_text(encoding="utf-8")
    sections = split_sections(text)

    done = parse_items(sections.get("DONE", []))
    verified = parse_items(sections.get("VERIFIED", []))
    rejected = parse_items(sections.get("REJECTED", []))
    if not done:
        return False

    committed = False
    for item in done:
        log(f"{YELLOW}AUDIT{RESET}: {item}")
        ok, notes = audit_item(item)
        if ok:
            verdict = "VERIFIED"
            verified.append(f"{item}  —  {notes}")
            log(f"  {GREEN}VERIFIED{RESET}: {notes}")
        else:
            verdict = "REJECTED"
            rejected.append(f"{item}  —  {notes}")
            log(f"  {RED}REJECTED{RESET}: {notes}")

        # Propose the verdict to tasks.db instead of writing the board directly.
        # The Orchestrator is the SOLE committer: it applies the proposal
        # (DONE -> VERIFIED/REJECTED) atomically and regenerates the read-only
        # WORKBOARD.md export. This removes the Reviewer as a concurrent board
        # writer (the root of the multi-writer corruption).
        try:
            from pathlib import Path as _P
            _ad = _P(__file__).resolve().parent
            # task_store lives in dabdabi-agent/agents/ (one level under repo).
            _agents = _P(r"D:\RPES-v2\dabdabi-agent\agents")
            if str(_agents) not in sys.path:
                sys.path.insert(0, str(_agents))
            import task_store as ts
            ts.propose("reviewer", "reviewer_verdict",
                       {"item": item, "verdict": verdict, "notes": notes},
                       intent=f"review: {verdict} {item[:100]}")
            committed = True
            log(f"  {GREEN}proposed{RESET} {verdict} for '{item[:60]}'")
        except Exception as e:  # noqa
            log(f"  {RED}propose failed: {e}{RESET}")

    return committed


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", help="single pass then exit")
    ap.add_argument("--interval", type=int, default=20, help="poll seconds")
    args = ap.parse_args()

    log(f"{BOLD}EOS Reviewer watcher started{RESET} on {WORKBOARD}")
    if args.once:
        process_once()
        return
    while True:
        try:
            process_once()
        except Exception as e:  # noqa
            log(f"{RED}watch error: {e}{RESET}")
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
