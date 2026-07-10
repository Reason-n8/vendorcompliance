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
- [ ] Wire RPES decision.py to EOS Authorization Engine
- [ ] Wire RPES audit.py to EOS Event Ledger
- [ ] Map RPES models.py to EOS-000 Ontology terms
- [ ] Run conformance suite
- [ ] Create eos_bridge.py

## DONE

## VERIFIED

## DEPLOYED
