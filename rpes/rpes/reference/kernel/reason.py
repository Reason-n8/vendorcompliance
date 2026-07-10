"""RPES M1 Reason Engine - Boundary Check"""

from models import KnowledgeRecord, ConclusionRecord

M1_BASELINE = {
    "rule_id": "RVS-001-MB",
    "comparator": "<",
    "threshold": 250.0
}

def execute_boundary_check(k_record: KnowledgeRecord) -> ConclusionRecord:
    comparator = M1_BASELINE["comparator"]
    value = k_record.value
    threshold = M1_BASELINE["threshold"]

    if comparator == "<":
        is_within_limit = value < threshold
    elif comparator == ">":
        is_within_limit = value > threshold
    elif comparator == "<=":
        is_within_limit = value <= threshold
    elif comparator == ">=":
        is_within_limit = value >= threshold
    elif comparator == "==":
        is_within_limit = value == threshold
    else:
        raise ValueError(f"Constitutional violation: Unsupported comparator '{comparator}'")

    outcome_code = "WITHIN_LIMIT" if is_within_limit else "OUTSIDE_LIMIT"

    return ConclusionRecord(
        conclusion_id="C-001",
        referenced_knowledge=[k_record.knowledge_id],
        connector_used="Boundary Check",
        baseline_reference=M1_BASELINE["rule_id"],
        outcome_code=outcome_code,
        confidence="HIGH"
    )
