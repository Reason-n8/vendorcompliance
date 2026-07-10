#!/bin/bash
# VP-L3-001 Go Conformance Runner
# Executes all M1 test vectors against the Go implementation

VECTOR_DIR="../conformance/vectors"
GO_BINARY="./go-kernel"

echo "============================================================"
echo "RPES CONFORMANCE REPORT"
echo "============================================================"
echo "Implementation: Clean-Room Kernel (Go)"
echo "Target:         SPEC-M1-001"
echo "------------------------------------------------------------"

TOTAL=0
PASSED=0
FAILED=0
ERRORS=0

for VECTOR_FILE in "$VECTOR_DIR"/tv*.json; do
    TOTAL=$((TOTAL + 1))
    TEST_ID=$(basename "$VECTOR_FILE" .json)

    # Run the Go binary with the vector as stdin
    OUTPUT=$("$GO_BINARY" < "$VECTOR_FILE" 2>/dev/null)
    EXIT_CODE=$?

    if [ $EXIT_CODE -ne 0 ]; then
        echo "[ERR ] $TEST_ID: execution error"
        ERRORS=$((ERRORS + 1))
        continue
    fi

    # Extract expected output from vector
    EXPECTED=$(python3 -c "
import json
with open('$VECTOR_FILE') as f:
    v = json.load(f)
fields = v.get('comparison_fields')
exp = v['expected_output']
if fields:
    result = {k: exp[k] for k in fields if k in exp}
else:
    result = exp
print(json.dumps(result, sort_keys=True))
" 2>/dev/null)

    # Extract matching fields from observed output
    OBSERVED=$(python3 -c "
import json
v = json.loads('''$OUTPUT''')
with open('$VECTOR_FILE') as f:
    vec = json.load(f)
fields = vec.get('comparison_fields')
if fields:
    result = {k: v[k] for k in fields if k in v}
else:
    result = v
print(json.dumps(result, sort_keys=True))
" 2>/dev/null)

    if [ "$EXPECTED" = "$OBSERVED" ]; then
        echo "[PASS] $TEST_ID: $(python3 -c "import json; f=open('$VECTOR_FILE'); print(json.load(f)['description'])")"
        PASSED=$((PASSED + 1))
    else
        echo "[FAIL] $TEST_ID: $(python3 -c "import json; f=open('$VECTOR_FILE'); print(json.load(f)['description'])")"
        echo "       Expected: $EXPECTED"
        echo "       Observed: $OBSERVED"
        FAILED=$((FAILED + 1))
    fi
done

echo "------------------------------------------------------------"
echo "Total:  $TOTAL"
echo "Passed: $PASSED"
echo "Failed: $FAILED"
echo "Errors: $ERRORS"
echo "============================================================"

if [ $FAILED -gt 0 ] || [ $ERRORS -gt 0 ]; then
    exit 1
fi
exit 0
