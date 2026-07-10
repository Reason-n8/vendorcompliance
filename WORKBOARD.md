# RPES-v2 Institution Workboard

## RULES
- Builder: Watch TASKS. Fix top item. Move to DONE. Repeat.
- Reviewer: Watch DONE. Audit. Move to VERIFIED or REJECTED. Commit "Reviewed:".
- Deployer: Watch VERIFIED + git "Reviewed:" commits. Deploy. Move to DEPLOYED.
- CRITICAL: Never touch D:\Reason. Work only in D:\RPES-v2.
- CRITICAL: All file writes through governed_write at D:\EOS\wrappers\governed_write.py

## RPES-v2 ←→ EOS Mapping
| RPES Kernel | EOS Component |
|-------------|---------------|
| reference/kernel/decision.py | Authorization Engine |
| reference/kernel/audit.py | Event Ledger |
| reference/kernel/models.py | EOS-000 Ontology |

## TASKS
- [x] Run conformance suite
- [x] Create eos_bridge.py

## DONE

## VERIFIED
- [x] Wire RPES audit.py to EOS Event Ledger  —  audit.py references ledger: ['audit.py:1', 'audit.py:4', 'audit.py:5', 'audit.py:6', 'audit.py:18', 'audit.py:21', 'audit.py:23', 'audit.py:29', 'audit.py:30', 'audit.py:33', 'audit.py:38', 'audit.py:40', 'audit.py:50', 'audit.py:52', 'audit.py:57', 'audit.py:59', 'audit.py:75', 'audit.py:83']; conformance gate: 5/5 PASS

## REJECTED
- [x] Wire RPES decision.py to EOS Authorization Engine  —  REJECTED: decision.py shows no wiring to EOS Authorization Engine (no engine/import reference).
- [x] Wire RPES decision.py to EOS Authorization Engine  —  REJECTED: decision.py shows no wiring to EOS Authorization Engine (no engine/import reference).

## DEPLOYED
- [x] Wire RPES decision.py to EOS Authorization Engine  —  decision.py references EOS engine: ['decision.py:20', 'decision.py:23', 'decision.py:30', 'decision.py:39', 'decision.py:43', 'decision.py:49', 'decision.py:62', 'decision.py:65']; no eos_bridge.py yet; conformance gate: 5/5 PASS -> DEPLOYED.

## RPES-v2 ←→ EOS Mapping
