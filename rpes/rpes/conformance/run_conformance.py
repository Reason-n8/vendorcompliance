#!/usr/bin/env python3
"""RPES M1 Conformance Runner - Execute against Reference Kernel"""

import json
import os
import sys
from pathlib import Path

# Add the reference/kernel directory to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent / "reference" / "kernel"))

from models import KnowledgeRecord, ConclusionRecord, DecisionRecord
from reason import execute_boundary_check
from decision import evaluate_decision
from runner import run_conformance, print_report, save_report


def m1_reference_pipeline(input_data: dict) -> dict:
    if "value" in input_data and "component" in input_data:
        k_rec = KnowledgeRecord(
            knowledge_id=input_data.get("knowledge_id", "K-001"),
            component=input_data.get("component", ""),
            metric_type=input_data.get("metric_type", ""),
            observation=input_data.get("observation", ""),
            value=float(input_data["value"]),
            unit=input_data.get("unit", ""),
            observed_at=input_data.get("observed_at", ""),
        )
        c_rec = execute_boundary_check(k_rec)
        return {
            "conclusion_id": c_rec.conclusion_id,
            "outcome_code": c_rec.outcome_code,
            "confidence": c_rec.confidence,
            "connector_used": c_rec.connector_used,
            "baseline_reference": c_rec.baseline_reference,
        }
    elif "outcome_code" in input_data and "confidence" in input_data:
        c_rec = ConclusionRecord(
            conclusion_id=input_data.get("conclusion_id", "C-001"),
            referenced_knowledge=input_data.get("referenced_knowledge", []),
            connector_used=input_data.get("connector_used", ""),
            baseline_reference=input_data.get("baseline_reference", ""),
            outcome_code=input_data["outcome_code"],
            confidence=input_data["confidence"],
        )
        d_rec = evaluate_decision(c_rec)
        return {
            "decision_id": d_rec.decision_id,
            "decision_code": d_rec.decision_code,
            "referenced_conclusions": d_rec.referenced_conclusions,
        }
    else:
        raise ValueError(f"Cannot determine vector type from input: {list(input_data.keys())}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="RPES M1 Conformance Runner")
    parser.add_argument("--output", type=str, default=None, help="Path to save JSON conformance report")
    args = parser.parse_args()

    vector_dir = Path(__file__).parent / "vectors"
    report = run_conformance("Reference Kernel v0.6 (Python)", m1_reference_pipeline, str(vector_dir))
    exit_code = print_report(report)
    if args.output:
        save_report(report, args.output)
        print(f"\nReport saved to: {args.output}")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
