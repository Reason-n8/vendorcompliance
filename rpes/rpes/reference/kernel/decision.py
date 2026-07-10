"""RPES M1 Decision Engine"""

from models import ConclusionRecord, DecisionRecord

def evaluate_decision(c_rec: ConclusionRecord) -> DecisionRecord:
    if c_rec.outcome_code == "OUTSIDE_LIMIT" and c_rec.confidence == "HIGH":
        decision_code = "ACP_WARRANTED"
    else:
        decision_code = "ACP_NOT_WARRANTED"

    return DecisionRecord(
        decision_id="D-001",
        decision_code=decision_code,
        referenced_conclusions=[c_rec.conclusion_id]
    )
