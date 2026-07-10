# RPES-v2 Institution Workboard

## RULES
- Builder: Watch TASKS. Fix top item. Move to DONE. Repeat.
- Reviewer: Watch DONE. Audit. Move to VERIFIED or REJECTED. Commit "Reviewed:".
- Deployer: Watch VERIFIED + git "Reviewed:" commits. Deploy. Move to DEPLOYED.
- CRITICAL: Never touch D:\Reason. Work only in D:\RPES-v2.
- CRITICAL: All file writes through governed_write at D:\EOS\wrappers\governed_write.py

## TASKS
- [x] Wire RPES audit.py to EOS Event Ledger
- [x] Map RPES models.py to EOS-000 Ontology terms
- [x] Run conformance suite
- [x] Create eos_bridge.py

## DONE

## VERIFIED

## REJECTED

## DEPLOYED
- [x] Wire RPES decision.py to EOS Authorization Engine  —  decision.py references EOS engine: ['decision.py:20', 'decision.py:23', 'decision.py:30', 'decision.py:39', 'decision.py:43', 'decision.py:49', 'decision.py:62', 'decision.py:65']; no eos_bridge.py yet; conformance gate: 5/5 PASS -> DEPLOYED.

## RPES-v2 ←→ EOS Mapping
