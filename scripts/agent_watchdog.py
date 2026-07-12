#!/usr/bin/env python3
"""EOS agent watchdog (self-healing mode).

Runs via cron every 5 minutes. Uses monitor_once(do_restart=True) so a
genuinely DEAD agent (no heartbeat for > RESTART_AFTER=300s) is
auto-restarted by the telemetry monitor.

SAFETY (why this is now safe, where it wasn't before):
  * Each agent beats a DECOUPLED daemon heartbeat every HB_INTERVAL=60s,
    independent of its slow work cycle (Deployer=900s). A healthy agent
    never reaches the 300s dead threshold, so auto-restart can't fork-bomb
    a live-but-slow agent.
  * _restart_agent() enforces a per-agent cooldown (RESTART_COOLDOWN_S
    =600s), so even a failed restart won't re-fire every 5-min tick.
  * Builder is operator-driven (no _RESTART_CMD entry) and is escalated,
    never auto-restarted.

Side effects:
  * dead agent -> auto-restart (logged) + recorded as an escape
  * stuck lanes -> escalated to the Orchestrator as proposals
  * PRINTS ONLY when health != healthy or actions were taken.
Empty stdout = all agents within thresholds. Cron delivers nothing -> silence.
"""
import sys
sys.path.insert(0, r"D:\RPES-v2\dabdabi-agent\agents")

import institution_telemetry as tele

# do_restart=True: detect + auto-heal dead agents (guarded by 300s threshold
# + per-agent cooldown). Fork-bomb risk eliminated by the daemon heartbeat.
snap = tele.monitor_once(do_restart=True, cycle=0)

if snap["health"] == "healthy" and not snap.get("monitor_actions"):
    raise SystemExit(0)

lines = [f"EOS telemetry ALERT @ {snap['generated_at']}  health={snap['health']}"]
for a in snap["agents"]:
    if not a["alive"]:
        lines.append(f"  {a['role']:12} DEAD  age={a['age_s']}s  last={a['last_seen']}  detail={a['detail']}")
if snap.get("alerts"):
    lines.append("alerts: " + "; ".join(snap["alerts"]))
if snap.get("monitor_actions"):
    lines.append("actions: " + "; ".join(snap["monitor_actions"]))
print("\n".join(lines))
