package main

import (
	"encoding/json"
	"fmt"
	"os"
)

// M1 Data Models
type KnowledgeRecord struct {
	KnowledgeID string  `json:"knowledge_id"`
	Component   string  `json:"component"`
	MetricType  string  `json:"metric_type"`
	Observation string  `json:"observation"`
	Value       float64 `json:"value"`
	Unit        string  `json:"unit"`
	ObservedAt  string  `json:"observed_at"`
}

type ConclusionRecord struct {
	ConclusionID        string   `json:"conclusion_id"`
	ReferencedKnowledge []string `json:"referenced_knowledge"`
	ConnectorUsed       string   `json:"connector_used"`
	BaselineReference   string   `json:"baseline_reference"`
	OutcomeCode         string   `json:"outcome_code"`
	Confidence          string   `json:"confidence"`
}

type DecisionRecord struct {
	DecisionID           string   `json:"decision_id"`
	DecisionCode         string   `json:"decision_code"`
	ReferencedConclusions []string `json:"referenced_conclusions"`
}

// M1 Baseline
type Baseline struct {
	RuleID     string
	Comparator string
	Threshold  float64
}

var M1Baseline = Baseline{
	RuleID:     "RVS-001-MB",
	Comparator: "<",
	Threshold:  250.0,
}

// M1 Boundary Check
func executeBoundaryCheck(k KnowledgeRecord) ConclusionRecord {
	isWithinLimit := false
	switch M1Baseline.Comparator {
	case "<":
		isWithinLimit = k.Value < M1Baseline.Threshold
	case ">":
		isWithinLimit = k.Value > M1Baseline.Threshold
	case "<=":
		isWithinLimit = k.Value <= M1Baseline.Threshold
	case ">=":
		isWithinLimit = k.Value >= M1Baseline.Threshold
	case "==":
		isWithinLimit = k.Value == M1Baseline.Threshold
	default:
		panic(fmt.Sprintf("Constitutional violation: Unsupported comparator '%s'", M1Baseline.Comparator))
	}

	outcomeCode := "WITHIN_LIMIT"
	if !isWithinLimit {
		outcomeCode = "OUTSIDE_LIMIT"
	}

	return ConclusionRecord{
		ConclusionID:        "C-001",
		ReferencedKnowledge: []string{k.KnowledgeID},
		ConnectorUsed:       "Boundary Check",
		BaselineReference:   M1Baseline.RuleID,
		OutcomeCode:         outcomeCode,
		Confidence:          "HIGH",
	}
}

// M1 Decision Engine
func evaluateDecision(c ConclusionRecord) DecisionRecord {
	decisionCode := "ACP_NOT_WARRANTED"
	if c.OutcomeCode == "OUTSIDE_LIMIT" && c.Confidence == "HIGH" {
		decisionCode = "ACP_WARRANTED"
	}

	return DecisionRecord{
		DecisionID:            "D-001",
		DecisionCode:          decisionCode,
		ReferencedConclusions: []string{c.ConclusionID},
	}
}

// Conformance runner - processes test vectors from stdin
func main() {
	// Read test vector from stdin
	var vector struct {
		TestID          string          `json:"test_id"`
		Description     string          `json:"description"`
		Input           json.RawMessage `json:"input"`
		ExpectedOutput  json.RawMessage `json:"expected_output"`
		ComparisonFields []string       `json:"comparison_fields"`
	}

	decoder := json.NewDecoder(os.Stdin)
	decoder.Decode(&vector)

	// Determine if this is a KnowledgeRecord or ConclusionRecord input
	var inputMap map[string]interface{}
	json.Unmarshal(vector.Input, &inputMap)

	if _, hasValue := inputMap["value"]; hasValue {
		// KnowledgeRecord input -> ConclusionRecord output
		var k KnowledgeRecord
		json.Unmarshal(vector.Input, &k)
		c := executeBoundaryCheck(k)
		output, _ := json.Marshal(c)
		fmt.Println(string(output))
	} else if _, hasOutcome := inputMap["outcome_code"]; hasOutcome {
		// ConclusionRecord input -> DecisionRecord output
		var c ConclusionRecord
		json.Unmarshal(vector.Input, &c)
		d := evaluateDecision(c)
		output, _ := json.Marshal(d)
		fmt.Println(string(output))
	} else {
		fmt.Fprintf(os.Stderr, "Cannot determine vector type from input: %v\n", inputMap)
		os.Exit(1)
	}
}
