"""RPES Conformance Runner (EI-005)"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

def create_report():
    return {
        "report_id": None,
        "generated_at": None,
        "implementation": None,
        "specification_target": "SPEC-M1-001",
        "results": [],
        "summary": {"total": 0, "passed": 0, "failed": 0, "errors": 0},
    }

def load_test_vector(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def deep_compare(observed: dict, expected: dict, fields: list = None) -> tuple:
    if fields is None:
        if observed == expected:
            return True, "Full artifact match"
        else:
            diffs = []
            all_keys = set(observed.keys()) | set(expected.keys())
            for key in sorted(all_keys):
                obs_val = observed.get(key)
                exp_val = expected.get(key)
                if obs_val != exp_val:
                    diffs.append(f"  {key}: observed={obs_val!r}, expected={exp_val!r}")
            return False, "Field mismatch:\n" + "\n".join(diffs)
    else:
        diffs = []
        for field in fields:
            obs_val = observed.get(field)
            exp_val = expected.get(field)
            if obs_val != exp_val:
                diffs.append(f"  {field}: observed={obs_val!r}, expected={exp_val!r}")
        if diffs:
            return False, "Field mismatch:\n" + "\n".join(diffs)
        return True, f"Fields match: {fields}"

def run_vector(vector: dict, pipeline_fn) -> dict:
    result = {"test_id": vector["test_id"], "description": vector.get("description", ""), "status": None, "details": ""}
    try:
        observed = pipeline_fn(vector["input"])
        passed, details = deep_compare(observed, vector["expected_output"], vector.get("comparison_fields"))
        result["status"] = "PASS" if passed else "FAIL"
        result["details"] = details
    except Exception as e:
        result["status"] = "ERROR"
        result["details"] = f"Exception: {type(e).__name__}: {e}"
    return result

def run_conformance(implementation_name: str, pipeline_fn, vector_dir: str) -> dict:
    report = create_report()
    report["generated_at"] = datetime.now(timezone.utc).isoformat()
    report["implementation"] = implementation_name
    vector_path = Path(vector_dir)
    if not vector_path.exists():
        report["summary"]["errors"] = 1
        report["results"].append({"test_id": "RUNNER-001", "description": "Vector directory not found", "status": "ERROR", "details": f"Directory does not exist: {vector_dir}"})
        return report
    vector_files = sorted(vector_path.glob("*.json"))
    if not vector_files:
        report["summary"]["errors"] = 1
        report["results"].append({"test_id": "RUNNER-002", "description": "No test vectors found", "status": "ERROR", "details": f"No JSON files in: {vector_dir}"})
        return report
    for vf in vector_files:
        vector = load_test_vector(str(vf))
        result = run_vector(vector, pipeline_fn)
        report["results"].append(result)
    report["summary"]["total"] = len(report["results"])
    for r in report["results"]:
        if r["status"] == "PASS":
            report["summary"]["passed"] += 1
        elif r["status"] == "FAIL":
            report["summary"]["failed"] += 1
        elif r["status"] == "ERROR":
            report["summary"]["errors"] += 1
    report["report_id"] = f"CR-{report['summary']['total']}T-{report['summary']['passed']}P-{report['summary']['failed']}F-{report['summary']['errors']}E"
    return report

def print_report(report: dict):
    print("=" * 60)
    print("RPES CONFORMANCE REPORT")
    print("=" * 60)
    print(f"Report ID:      {report['report_id']}")
    print(f"Generated:      {report['generated_at']}")
    print(f"Implementation: {report['implementation']}")
    print(f"Target:         {report['specification_target']}")
    print("-" * 60)
    print(f"Total:  {report['summary']['total']}")
    print(f"Passed: {report['summary']['passed']}")
    print(f"Failed: {report['summary']['failed']}")
    print(f"Errors: {report['summary']['errors']}")
    print("-" * 60)
    for r in report["results"]:
        icon = {"PASS": "[PASS]", "FAIL": "[FAIL]", "ERROR": "[ERR ]"}.get(r["status"], "[????]")
        print(f"{icon} {r['test_id']}: {r['description']}")
        if r["details"] and r["status"] != "PASS":
            for line in r["details"].split("\n"):
                if line.strip():
                    print(f"       {line}")
    print("=" * 60)
    return 0 if report["summary"]["failed"] == 0 and report["summary"]["errors"] == 0 else 1

def save_report(report: dict, output_path: str):
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
