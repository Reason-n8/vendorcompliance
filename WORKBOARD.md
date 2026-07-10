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

## DONE

## VERIFIED
- [x] Wire RPES decision.py to EOS Authorization Engine  —  decision.py references EOS engine: ['decision.py:3']; conformance gate: 5/5 PASS
- [x] Wire RPES audit.py to EOS Event Ledger  —  audit.py references ledger: ['audit.py:1', 'audit.py:4', 'audit.py:5', 'audit.py:6', 'audit.py:18', 'audit.py:21', 'audit.py:23', 'audit.py:29', 'audit.py:30', 'audit.py:33', 'audit.py:38', 'audit.py:40', 'audit.py:50', 'audit.py:52', 'audit.py:57', 'audit.py:59', 'audit.py:75', 'audit.py:83']; conformance gate: 5/5 PASS
- [x] Map RPES models.py to EOS-000 Ontology terms  —  models.py references ontology: ['models.py:1', 'models.py:3', 'models.py:4', 'models.py:14', 'models.py:15', 'models.py:17', 'models.py:29', 'models.py:30', 'models.py:31', 'models.py:44', 'models.py:45', 'models.py:46', 'models.py:58', 'models.py:60', 'models.py:61', 'models.py:62', 'models.py:71', 'models.py:73', 'models.py:74', 'models.py:75']; conformance gate: 5/5 PASS
- [x] Run conformance suite  —  conformance: 5/5 PASS (failed=0, errors=0); conformance gate: 5/5 PASS
- [x] Create eos_bridge.py  —  eos_bridge.py found: ['rpes\\rpes\\eos_bridge.py']; imports kernel and EOS governed_write/AuthorizationEngine; conformance gate: 5/5 PASS

## REJECTED

## DEPLOYED
