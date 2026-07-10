#!/usr/bin/env python3
"""Run M1 conformance vectors against Go implementation"""

import json, subprocess, sys, os
from pathlib import Path

VECTOR_DIR = "../conformance/vectors"
GO_BINARY = "./go-kernel.exe"

passed = 0
failed = 0
errors = 0
total = 0

vector_files = sorted(Path(VECTOR_DIR).glob("tv*.json"))

for vf in vector_files:
    total += 1
    with open(vf) as f:
        vector = json.load(f)
    
    test_id = vector["test_id"]
    desc = vector.get("description", "")
    
    try:
        result = subprocess.run(
            [GO_BINARY],
            input=json.dumps(vector),
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode != 0:
            print(f"[ERR ] {test_id}: {desc}")
            print(f"       {result.stderr.strip()}")
            errors += 1
            continue
        
        observed = json.loads(result.stdout)
        expected = vector["expected_output"]
        fields = vector.get("comparison_fields")
        
        if fields:
            obs_check = {k: observed.get(k) for k in fields}
            exp_check = {k: expected.get(k) for k in fields}
        else:
            obs_check = observed
            exp_check = expected
        
        if obs_check == exp_check:
            print(f"[PASS] {test_id}: {desc}")
            passed += 1
        else:
            print(f"[FAIL] {test_id}: {desc}")
            print(f"       Expected: {json.dumps(exp_check)}")
            print(f"       Observed: {json.dumps(obs_check)}")
            failed += 1
            
    except json.JSONDecodeError as e:
        print(f"[ERR ] {test_id}: {desc}")
        print(f"       JSON parse error: {e}")
        print(f"       Output: {result.stdout[:200]}")
        errors += 1
    except Exception as e:
        print(f"[ERR ] {test_id}: {desc}")
        print(f"       {e}")
        errors += 1

print()
print(f"Total:  {total}")
print(f"Passed: {passed}")
print(f"Failed: {failed}")
print(f"Errors: {errors}")

if failed > 0 or errors > 0:
    sys.exit(1)
