"""RPES M1 Data Models"""

class KnowledgeRecord:
    def __init__(self, knowledge_id, component, metric_type, observation, value, unit, observed_at):
        self.knowledge_id = knowledge_id
        self.component = component
        self.metric_type = metric_type
        self.observation = observation
        self.value = float(value)
        self.unit = unit
        self.observed_at = observed_at

class ConclusionRecord:
    def __init__(self, conclusion_id, referenced_knowledge, connector_used, baseline_reference, outcome_code, confidence):
        self.conclusion_id = conclusion_id
        self.referenced_knowledge = referenced_knowledge
        self.connector_used = connector_used
        self.baseline_reference = baseline_reference
        self.outcome_code = outcome_code
        self.confidence = confidence

class DecisionRecord:
    def __init__(self, decision_id, decision_code, referenced_conclusions):
        self.decision_id = decision_id
        self.decision_code = decision_code
        self.referenced_conclusions = referenced_conclusions

class AuditReport:
    def __init__(self, audit_id, knowledge_record, conclusion_record, decision_record):
        self.audit_id = audit_id
        self.knowledge_record = knowledge_record
        self.conclusion_record = conclusion_record
        self.decision_record = decision_record
