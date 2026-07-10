"""RPES M1 Audit Engine"""

from models import KnowledgeRecord, ConclusionRecord, DecisionRecord, AuditReport

def generate_audit(k_record, c_record, d_record):
    return AuditReport(
        audit_id="A-001",
        knowledge_record=k_record,
        conclusion_record=c_record,
        decision_record=d_record
    )
