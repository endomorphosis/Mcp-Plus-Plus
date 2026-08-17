package testsmcp

// MCPP-033: four-language ExecutionEnvelope@1 family validators and vectors.
//
// Interface: ExecutionEnvelopeValidator@1
// Track: envelope-validators
//
// Mirrors the positive/negative catalog in:
//   - tests-py/integration/test_execution_envelope.py
//   - tests-ts/src/__tests__/execution-envelope.test.ts
//   - tests-rs/tests/execution_envelope_test.rs
//
// Structural acceptance only (ADR-0003). Same case ids must accept/reject
// identically across languages.

import (
	"encoding/json"
	"fmt"
	"reflect"
	"regexp"
	"testing"
)

const (
	interfaceName = "ExecutionEnvelopeValidator@1"
	taskID        = "MCPP-033"

	schemaEnvelope = "mcp++/execution/envelope@1"
	schemaResult   = "mcp++/execution/result@1"
	schemaReceipt  = "mcp++/execution/receipt@1"
	schemaError    = "mcp++/execution/portable-error@1"

	cidA = "bafkreigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"
	cidB = "bafkreihtwdlu4jntm7yl2mgsfzqgr4on37vr7inuld2dql2p4rmqafybti"
	cidC = "bafkreicssskybdf32rmzlbtge5bxyv4v6c6eac322pbrsr3azlb4fkxiqi"
	cidD = "bafkreihdwdcefgh4dqkjv67uzcmw7ojee6xedzdetojuzjevtenxquvyku"

	didRequester = "did:key:z6MkrequesterExample0001"
	didExecutor  = "did:key:z6MkexecutorExample00001"
)

var (
	cidRE = regexp.MustCompile(`^(Qm[1-9A-HJ-NP-Za-km-z]{44}|b[a-z2-7]{58,})$`)
	didRE = regexp.MustCompile(`^did:[a-z0-9]+:[A-Za-z0-9._:%-]+(?:[/?#][^\x00]*)?$`)

	statusValues = map[string]struct{}{
		"succeeded": {}, "failed": {}, "cancelled": {},
		"rejected": {}, "timed_out": {}, "compensated": {},
	}
	failureClasses = map[string]struct{}{
		"none": {}, "retryable": {}, "permanent": {}, "policy": {},
		"authority": {}, "fenced": {}, "resource": {}, "cancelled": {},
		"timeout": {}, "internal": {},
	}
)

type validationResult struct {
	IsValid bool
	Errors  []string
}

func (r *validationResult) add(msg string) {
	r.IsValid = false
	r.Errors = append(r.Errors, msg)
}

func isValidCID(v interface{}) bool {
	s, ok := v.(string)
	return ok && cidRE.MatchString(s)
}

func isValidDID(v interface{}) bool {
	s, ok := v.(string)
	return ok && didRE.MatchString(s)
}

func isNonNegInt(v interface{}) bool {
	switch n := v.(type) {
	case float64:
		return n >= 0 && n == float64(int64(n))
	case int:
		return n >= 0
	case int64:
		return n >= 0
	case json.Number:
		i, err := n.Int64()
		return err == nil && i >= 0
	default:
		return false
	}
}

func asMap(v interface{}) (map[string]interface{}, bool) {
	m, ok := v.(map[string]interface{})
	return m, ok
}

func asSlice(v interface{}) ([]interface{}, bool) {
	s, ok := v.([]interface{})
	return s, ok
}

// ---- ExecutionEnvelopeValidator@1 structural validators ----

func validatePortableError(errorObj interface{}) validationResult {
	r := validationResult{IsValid: true}
	m, ok := asMap(errorObj)
	if !ok {
		r.add("error must be an object")
		return r
	}
	if m["schema"] != schemaError {
		r.add(fmt.Sprintf("schema must be %q", schemaError))
	}
	for _, key := range []string{"code", "message", "retryable", "failure_class"} {
		if _, ok := m[key]; !ok {
			r.add("missing required field: " + key)
		}
	}
	if fc, ok := m["failure_class"]; ok {
		if s, ok := fc.(string); !ok {
			r.add("invalid failure_class")
		} else if _, ok := failureClasses[s]; !ok {
			r.add(fmt.Sprintf("invalid failure_class: %q", s))
		}
	}
	if rb, ok := m["retryable"]; ok {
		if _, ok := rb.(bool); !ok {
			r.add("retryable must be a boolean")
		}
	}
	if dc, ok := m["details_cid"]; ok && dc != nil && !isValidCID(dc) {
		r.add("invalid CID at /details_cid")
	}
	return r
}

func validateEnvelope(envelope interface{}) validationResult {
	r := validationResult{IsValid: true}
	m, ok := asMap(envelope)
	if !ok {
		r.add("envelope must be an object")
		return r
	}
	if m["schema"] != schemaEnvelope {
		r.add(fmt.Sprintf("schema must be %q", schemaEnvelope))
	}
	for _, key := range []string{
		"schema", "interface_cid", "input_cid", "intent_cid", "parents",
		"created_at_ms", "correlation_id", "requester", "authority",
	} {
		if _, ok := m[key]; !ok {
			r.add("missing required field: " + key)
		}
	}
	for _, key := range []string{
		"interface_cid", "input_cid", "intent_cid", "policy_cid", "decision_cid",
		"constraints_cid", "expected_output_schema_cid", "metadata_cid", "profile_b_envelope_cid",
	} {
		if v, ok := m[key]; ok && v != nil && !isValidCID(v) {
			r.add("invalid CID at /" + key)
		}
	}
	if parents, ok := m["parents"]; ok {
		sl, ok := asSlice(parents)
		if !ok {
			r.add("parents must be an array")
		} else {
			for i, p := range sl {
				if !isValidCID(p) {
					r.add(fmt.Sprintf("invalid parent CID at /parents/%d", i))
				}
			}
		}
	}
	if ts, ok := m["created_at_ms"]; ok && !isNonNegInt(ts) {
		r.add("created_at_ms must be a non-negative integer")
	}
	if corr, ok := m["correlation_id"]; ok {
		s, ok := corr.(string)
		if !ok || len(s) < 1 || len(s) > 128 {
			r.add("correlation_id must be a string of length 1..128")
		}
	}
	if req, ok := m["requester"]; ok {
		rm, ok := asMap(req)
		if !ok || !isValidDID(rm["did"]) {
			r.add("requester.did must be a valid DID")
		}
	}
	if auth, ok := m["authority"]; ok {
		am, ok := asMap(auth)
		if !ok {
			r.add("authority must be an object")
		} else {
			if _, ok := am["proof_cids"]; !ok {
				r.add("authority.proof_cids is required")
			} else if sl, ok := asSlice(am["proof_cids"]); !ok {
				r.add("authority.proof_cids must be an array")
			} else {
				for i, cid := range sl {
					if !isValidCID(cid) {
						r.add(fmt.Sprintf("invalid CID at /authority/proof_cids/%d", i))
					}
				}
			}
			if pc, ok := am["proof_cid"]; ok && pc != nil && !isValidCID(pc) {
				r.add("invalid CID at /authority/proof_cid")
			}
		}
	}
	if c, ok := m["canonicalization"]; ok && c != nil && c != "mcpp-jcs-v1" {
		r.add("canonicalization must be 'mcpp-jcs-v1' when present")
	}
	return r
}

func validateResult(resultObj interface{}) validationResult {
	r := validationResult{IsValid: true}
	m, ok := asMap(resultObj)
	if !ok {
		r.add("result must be an object")
		return r
	}
	if m["schema"] != schemaResult {
		r.add(fmt.Sprintf("schema must be %q", schemaResult))
	}
	for _, key := range []string{
		"schema", "envelope_cid", "status", "output_cids", "state_transitions",
		"side_effects", "decision_cid", "delegation_cid", "executor", "retry",
		"duration_ms", "error", "proofs", "started_at_ms", "finished_at_ms",
	} {
		if _, ok := m[key]; !ok {
			r.add("missing required field: " + key)
		}
	}
	if st, ok := m["status"]; ok {
		s, _ := st.(string)
		if _, ok := statusValues[s]; !ok {
			r.add(fmt.Sprintf("invalid status: %v", st))
		}
	}
	if m["status"] == "succeeded" && m["error"] != nil {
		r.add("error must be null when status is succeeded")
	}
	if v, ok := m["envelope_cid"]; ok && v != nil && !isValidCID(v) {
		r.add("invalid CID at /envelope_cid")
	}
	if outs, ok := m["output_cids"]; ok {
		sl, ok := asSlice(outs)
		if !ok {
			r.add("output_cids must be an array")
		} else {
			for i, cid := range sl {
				if !isValidCID(cid) {
					r.add(fmt.Sprintf("invalid CID at /output_cids/%d", i))
				}
			}
		}
	}
	if ex, ok := m["executor"]; ok {
		em, ok := asMap(ex)
		if !ok || !isValidDID(em["did"]) {
			r.add("executor.did must be a valid DID")
		}
	}
	if errObj, ok := m["error"]; ok && errObj != nil {
		pe := validatePortableError(errObj)
		if !pe.IsValid {
			r.Errors = append(r.Errors, pe.Errors...)
			r.IsValid = false
		}
	}
	if ts, ok := m["started_at_ms"]; ok && !isNonNegInt(ts) {
		r.add("started_at_ms must be a non-negative integer")
	}
	if ts, ok := m["finished_at_ms"]; ok && !isNonNegInt(ts) {
		r.add("finished_at_ms must be a non-negative integer")
	}
	if isNonNegInt(m["started_at_ms"]) && isNonNegInt(m["finished_at_ms"]) {
		start := toFloat(m["started_at_ms"])
		finish := toFloat(m["finished_at_ms"])
		if finish < start {
			r.add("finished_at_ms must be >= started_at_ms")
		}
	}
	return r
}

func toFloat(v interface{}) float64 {
	switch n := v.(type) {
	case float64:
		return n
	case int:
		return float64(n)
	case int64:
		return float64(n)
	default:
		return 0
	}
}

func validateReceipt(receipt interface{}) validationResult {
	r := validationResult{IsValid: true}
	m, ok := asMap(receipt)
	if !ok {
		r.add("receipt must be an object")
		return r
	}
	if m["schema"] != schemaReceipt {
		r.add(fmt.Sprintf("schema must be %q", schemaReceipt))
	}
	for _, key := range []string{
		"schema", "envelope_cid", "result_cid", "status", "output_cids",
		"state_transitions", "side_effects", "decision_cid", "delegation_cid",
		"executor", "retry", "duration_ms", "error", "proofs", "signature",
		"event_cid", "started_at_ms", "finished_at_ms",
	} {
		if _, ok := m[key]; !ok {
			r.add("missing required field: " + key)
		}
	}
	for _, key := range []string{
		"envelope_cid", "result_cid", "intent_cid", "receipt_cid", "decision_cid",
		"delegation_cid", "proof_cid", "event_cid", "primary_output_cid",
		"resource_use_cid", "policy_cid", "profile_b_receipt_cid", "profile_g_task_receipt_cid",
	} {
		if v, ok := m[key]; ok && v != nil && !isValidCID(v) {
			r.add("invalid CID at /" + key)
		}
	}
	if outs, ok := m["output_cids"]; ok {
		sl, ok := asSlice(outs)
		if !ok {
			r.add("output_cids must be an array")
		} else {
			for i, cid := range sl {
				if !isValidCID(cid) {
					r.add(fmt.Sprintf("invalid CID at /output_cids/%d", i))
				}
			}
		}
	}
	if st, ok := m["status"]; ok {
		s, _ := st.(string)
		if _, ok := statusValues[s]; !ok {
			r.add(fmt.Sprintf("invalid status: %v", st))
		}
	}
	if m["status"] == "succeeded" && m["error"] != nil {
		r.add("error must be null when status is succeeded")
	}
	if ex, ok := m["executor"]; ok {
		em, ok := asMap(ex)
		if !ok || !isValidDID(em["did"]) {
			r.add("executor.did must be a valid DID")
		}
	}
	if retry, ok := m["retry"]; ok {
		rm, ok := asMap(retry)
		if !ok || !isNonNegInt(rm["attempt"]) || toFloat(rm["attempt"]) < 1 {
			r.add("retry.attempt must be an integer >= 1")
		}
	}
	if errObj, ok := m["error"]; ok && errObj != nil {
		pe := validatePortableError(errObj)
		if !pe.IsValid {
			r.Errors = append(r.Errors, pe.Errors...)
			r.IsValid = false
		}
	}
	for _, ts := range []string{"started_at_ms", "finished_at_ms"} {
		if v, ok := m[ts]; ok && !isNonNegInt(v) {
			r.add(ts + " must be a non-negative integer")
		}
	}
	if isNonNegInt(m["started_at_ms"]) && isNonNegInt(m["finished_at_ms"]) {
		if toFloat(m["finished_at_ms"]) < toFloat(m["started_at_ms"]) {
			r.add("finished_at_ms must be >= started_at_ms")
		}
	}
	if c, ok := m["canonicalization"]; ok && c != nil && c != "mcpp-jcs-v1" {
		r.add("canonicalization must be 'mcpp-jcs-v1' when present")
	}
	return r
}

// validateKind is the ExecutionEnvelopeValidator@1 dispatch.
func validateKind(kind string, payload interface{}) bool {
	switch kind {
	case "envelope":
		return validateEnvelope(payload).IsValid
	case "result":
		return validateResult(payload).IsValid
	case "receipt":
		return validateReceipt(payload).IsValid
	case "error":
		return validatePortableError(payload).IsValid
	default:
		panic("unknown kind: " + kind)
	}
}

// ---- fixtures / catalog ----

func cloneMap(m map[string]interface{}) map[string]interface{} {
	raw, _ := json.Marshal(m)
	var out map[string]interface{}
	_ = json.Unmarshal(raw, &out)
	return out
}

func baseEnvelope() map[string]interface{} {
	return map[string]interface{}{
		"schema":         schemaEnvelope,
		"interface_cid":  cidA,
		"method":         "repo.status",
		"input_cid":      cidB,
		"intent_cid":     cidC,
		"policy_cid":     cidD,
		"parents":        []interface{}{},
		"created_at_ms":  float64(1783872000000),
		"correlation_id": "task-001",
		"requester":      map[string]interface{}{"did": didRequester},
		"authority": map[string]interface{}{
			"proof_cids": []interface{}{cidD},
			"proof_cid":  cidD,
		},
		"constraints":      map[string]interface{}{"timeout_ms": float64(30000), "max_retries": float64(3)},
		"state_refs":       []interface{}{},
		"canonicalization": "mcpp-jcs-v1",
	}
}

func basePortableError() map[string]interface{} {
	return map[string]interface{}{
		"schema":        schemaError,
		"code":          "E_POLICY_DENIED",
		"message":       "policy denied execution",
		"retryable":     false,
		"failure_class": "policy",
	}
}

func baseResultSucceeded() map[string]interface{} {
	return map[string]interface{}{
		"schema":            schemaResult,
		"envelope_cid":      cidA,
		"status":            "succeeded",
		"output_cids":       []interface{}{cidB},
		"state_transitions": []interface{}{},
		"side_effects":      []interface{}{},
		"decision_cid":      cidD,
		"delegation_cid":    cidC,
		"executor":          map[string]interface{}{"did": didExecutor},
		"retry":             map[string]interface{}{"attempt": float64(1)},
		"duration_ms":       12.5,
		"error":             nil,
		"proofs":            []interface{}{cidD},
		"started_at_ms":     float64(1783872001100),
		"finished_at_ms":    float64(1783872001113),
		"canonicalization":  "mcpp-jcs-v1",
	}
}

func baseResultFailed() map[string]interface{} {
	obj := baseResultSucceeded()
	obj["status"] = "failed"
	obj["output_cids"] = []interface{}{}
	obj["error"] = basePortableError()
	return obj
}

func baseReceiptSucceeded() map[string]interface{} {
	return map[string]interface{}{
		"schema":            schemaReceipt,
		"envelope_cid":      cidA,
		"result_cid":        cidB,
		"status":            "succeeded",
		"output_cids":       []interface{}{cidC},
		"state_transitions": []interface{}{},
		"side_effects":      []interface{}{},
		"decision_cid":      cidD,
		"delegation_cid":    cidC,
		"executor": map[string]interface{}{
			"did":             didExecutor,
			"runtime":         "ipfs_accelerate_py",
			"runtime_version": "3.2.0",
		},
		"retry":            map[string]interface{}{"attempt": float64(1)},
		"duration_ms":      12.5,
		"error":            nil,
		"proofs":           []interface{}{cidD},
		"signature":        nil,
		"signature_alg":    nil,
		"event_cid":        cidA,
		"started_at_ms":    float64(1783872001100),
		"finished_at_ms":   float64(1783872001113),
		"canonicalization": "mcpp-jcs-v1",
	}
}

func baseReceiptFailed() map[string]interface{} {
	obj := baseReceiptSucceeded()
	obj["status"] = "failed"
	obj["output_cids"] = []interface{}{}
	obj["error"] = basePortableError()
	return obj
}

type vectorCase struct {
	ID          string
	Kind        string
	Payload     map[string]interface{}
	ExpectValid bool
}

func vectorCatalog() []vectorCase {
	cases := []vectorCase{
		{ID: "pos-envelope-minimal", Kind: "envelope", Payload: baseEnvelope(), ExpectValid: true},
		{ID: "pos-envelope-with-parents", Kind: "envelope", Payload: func() map[string]interface{} {
			p := baseEnvelope()
			p["parents"] = []interface{}{cidA, cidB}
			return p
		}(), ExpectValid: true},
		{ID: "pos-result-succeeded", Kind: "result", Payload: baseResultSucceeded(), ExpectValid: true},
		{ID: "pos-result-failed-with-error", Kind: "result", Payload: baseResultFailed(), ExpectValid: true},
		{ID: "pos-receipt-succeeded", Kind: "receipt", Payload: baseReceiptSucceeded(), ExpectValid: true},
		{ID: "pos-receipt-failed", Kind: "receipt", Payload: baseReceiptFailed(), ExpectValid: true},
		{ID: "pos-portable-error", Kind: "error", Payload: basePortableError(), ExpectValid: true},
	}

	// Envelope negatives
	{
		p := baseEnvelope()
		p["schema"] = "mcp++/execution/envelope@0"
		cases = append(cases, vectorCase{ID: "neg-envelope-wrong-schema", Kind: "envelope", Payload: p, ExpectValid: false})
	}
	{
		p := baseEnvelope()
		delete(p, "interface_cid")
		cases = append(cases, vectorCase{ID: "neg-envelope-missing-interface-cid", Kind: "envelope", Payload: p, ExpectValid: false})
	}
	{
		p := baseEnvelope()
		p["interface_cid"] = "not-a-cid"
		cases = append(cases, vectorCase{ID: "neg-envelope-invalid-cid", Kind: "envelope", Payload: p, ExpectValid: false})
	}
	{
		p := baseEnvelope()
		p["requester"] = map[string]interface{}{"did": "not-a-did"}
		cases = append(cases, vectorCase{ID: "neg-envelope-invalid-did", Kind: "envelope", Payload: p, ExpectValid: false})
	}
	{
		p := baseEnvelope()
		p["authority"] = map[string]interface{}{"proof_cids": []interface{}{"bad-cid"}}
		cases = append(cases, vectorCase{ID: "neg-envelope-invalid-proof-cid", Kind: "envelope", Payload: p, ExpectValid: false})
	}
	{
		p := baseEnvelope()
		p["canonicalization"] = "jcs-v0"
		cases = append(cases, vectorCase{ID: "neg-envelope-bad-canonicalization", Kind: "envelope", Payload: p, ExpectValid: false})
	}
	{
		p := baseEnvelope()
		p["created_at_ms"] = float64(-1)
		cases = append(cases, vectorCase{ID: "neg-envelope-negative-timestamp", Kind: "envelope", Payload: p, ExpectValid: false})
	}
	{
		p := baseEnvelope()
		p["correlation_id"] = ""
		cases = append(cases, vectorCase{ID: "neg-envelope-empty-correlation", Kind: "envelope", Payload: p, ExpectValid: false})
	}
	{
		p := baseEnvelope()
		p["parents"] = []interface{}{"not-a-cid"}
		cases = append(cases, vectorCase{ID: "neg-envelope-bad-parent", Kind: "envelope", Payload: p, ExpectValid: false})
	}
	{
		p := baseEnvelope()
		auth := p["authority"].(map[string]interface{})
		delete(auth, "proof_cids")
		cases = append(cases, vectorCase{ID: "neg-envelope-missing-proof-cids", Kind: "envelope", Payload: p, ExpectValid: false})
	}

	// Error negatives
	{
		p := basePortableError()
		p["schema"] = "mcp++/execution/portable-error@0"
		cases = append(cases, vectorCase{ID: "neg-error-wrong-schema", Kind: "error", Payload: p, ExpectValid: false})
	}
	{
		p := basePortableError()
		delete(p, "code")
		cases = append(cases, vectorCase{ID: "neg-error-missing-code", Kind: "error", Payload: p, ExpectValid: false})
	}
	{
		p := basePortableError()
		p["failure_class"] = "bogus"
		cases = append(cases, vectorCase{ID: "neg-error-bad-failure-class", Kind: "error", Payload: p, ExpectValid: false})
	}
	{
		p := basePortableError()
		p["retryable"] = "yes"
		cases = append(cases, vectorCase{ID: "neg-error-nonbool-retryable", Kind: "error", Payload: p, ExpectValid: false})
	}

	// Result negatives
	{
		p := baseResultSucceeded()
		p["schema"] = "mcp++/execution/result@0"
		cases = append(cases, vectorCase{ID: "neg-result-wrong-schema", Kind: "result", Payload: p, ExpectValid: false})
	}
	{
		p := baseResultSucceeded()
		delete(p, "status")
		cases = append(cases, vectorCase{ID: "neg-result-missing-status", Kind: "result", Payload: p, ExpectValid: false})
	}
	{
		p := baseResultSucceeded()
		p["status"] = "running"
		cases = append(cases, vectorCase{ID: "neg-result-bad-status", Kind: "result", Payload: p, ExpectValid: false})
	}
	{
		p := baseResultSucceeded()
		p["error"] = basePortableError()
		cases = append(cases, vectorCase{ID: "neg-result-succeeded-with-error", Kind: "result", Payload: p, ExpectValid: false})
	}
	{
		p := baseResultSucceeded()
		p["envelope_cid"] = "not-a-cid"
		cases = append(cases, vectorCase{ID: "neg-result-invalid-envelope-cid", Kind: "result", Payload: p, ExpectValid: false})
	}

	// Receipt negatives
	{
		p := baseReceiptSucceeded()
		p["schema"] = "mcp++/execution/receipt@0"
		cases = append(cases, vectorCase{ID: "neg-receipt-wrong-schema", Kind: "receipt", Payload: p, ExpectValid: false})
	}
	{
		p := baseReceiptSucceeded()
		delete(p, "result_cid")
		cases = append(cases, vectorCase{ID: "neg-receipt-missing-result-cid", Kind: "receipt", Payload: p, ExpectValid: false})
	}
	{
		p := baseReceiptSucceeded()
		p["envelope_cid"] = "not-a-cid"
		cases = append(cases, vectorCase{ID: "neg-receipt-invalid-cid", Kind: "receipt", Payload: p, ExpectValid: false})
	}
	{
		p := baseReceiptSucceeded()
		p["status"] = "running"
		cases = append(cases, vectorCase{ID: "neg-receipt-bad-status", Kind: "receipt", Payload: p, ExpectValid: false})
	}
	{
		p := baseReceiptSucceeded()
		p["error"] = basePortableError()
		cases = append(cases, vectorCase{ID: "neg-receipt-succeeded-with-error", Kind: "receipt", Payload: p, ExpectValid: false})
	}
	{
		p := baseReceiptSucceeded()
		p["started_at_ms"] = float64(100)
		p["finished_at_ms"] = float64(1)
		cases = append(cases, vectorCase{ID: "neg-receipt-time-order", Kind: "receipt", Payload: p, ExpectValid: false})
	}
	{
		p := baseReceiptSucceeded()
		p["executor"] = map[string]interface{}{"did": "not-a-did"}
		cases = append(cases, vectorCase{ID: "neg-receipt-bad-executor-did", Kind: "receipt", Payload: p, ExpectValid: false})
	}
	{
		p := baseReceiptSucceeded()
		p["retry"] = map[string]interface{}{"attempt": float64(0)}
		cases = append(cases, vectorCase{ID: "neg-receipt-retry-attempt-zero", Kind: "receipt", Payload: p, ExpectValid: false})
	}

	return cases
}

var expectedPositiveIDs = map[string]struct{}{
	"pos-envelope-minimal": {}, "pos-envelope-with-parents": {},
	"pos-result-succeeded": {}, "pos-result-failed-with-error": {},
	"pos-receipt-succeeded": {}, "pos-receipt-failed": {},
	"pos-portable-error": {},
}

var expectedNegativeIDs = map[string]struct{}{
	"neg-envelope-wrong-schema": {}, "neg-envelope-missing-interface-cid": {},
	"neg-envelope-invalid-cid": {}, "neg-envelope-invalid-did": {},
	"neg-envelope-invalid-proof-cid": {}, "neg-envelope-bad-canonicalization": {},
	"neg-envelope-negative-timestamp": {}, "neg-envelope-empty-correlation": {},
	"neg-envelope-bad-parent": {}, "neg-envelope-missing-proof-cids": {},
	"neg-error-wrong-schema": {}, "neg-error-missing-code": {},
	"neg-error-bad-failure-class": {}, "neg-error-nonbool-retryable": {},
	"neg-result-wrong-schema": {}, "neg-result-missing-status": {},
	"neg-result-bad-status": {}, "neg-result-succeeded-with-error": {},
	"neg-result-invalid-envelope-cid": {},
	"neg-receipt-wrong-schema": {}, "neg-receipt-missing-result-cid": {},
	"neg-receipt-invalid-cid": {}, "neg-receipt-bad-status": {},
	"neg-receipt-succeeded-with-error": {}, "neg-receipt-time-order": {},
	"neg-receipt-bad-executor-did": {}, "neg-receipt-retry-attempt-zero": {},
}

// ---- tests ----

func TestExecutionEnvelopeValidatorInterface(t *testing.T) {
	if interfaceName != "ExecutionEnvelopeValidator@1" {
		t.Fatalf("interface: %s", interfaceName)
	}
	if taskID != "MCPP-033" {
		t.Fatalf("task: %s", taskID)
	}
}

func TestExecutionEnvelopeCatalogIDs(t *testing.T) {
	catalog := vectorCatalog()
	pos := map[string]struct{}{}
	neg := map[string]struct{}{}
	seen := map[string]struct{}{}
	for _, c := range catalog {
		if _, ok := seen[c.ID]; ok {
			t.Fatalf("duplicate case id %s", c.ID)
		}
		seen[c.ID] = struct{}{}
		if c.ExpectValid {
			pos[c.ID] = struct{}{}
		} else {
			neg[c.ID] = struct{}{}
		}
	}
	if !reflect.DeepEqual(pos, expectedPositiveIDs) {
		t.Fatalf("positive ids mismatch: got %v want %v", pos, expectedPositiveIDs)
	}
	if !reflect.DeepEqual(neg, expectedNegativeIDs) {
		t.Fatalf("negative ids mismatch: got %v want %v", neg, expectedNegativeIDs)
	}
}

func TestExecutionEnvelopeVectors(t *testing.T) {
	for _, c := range vectorCatalog() {
		c := c
		t.Run(c.ID, func(t *testing.T) {
			ok := validateKind(c.Kind, cloneMap(c.Payload))
			if ok != c.ExpectValid {
				var vr validationResult
				switch c.Kind {
				case "envelope":
					vr = validateEnvelope(c.Payload)
				case "result":
					vr = validateResult(c.Payload)
				case "receipt":
					vr = validateReceipt(c.Payload)
				case "error":
					vr = validatePortableError(c.Payload)
				}
				t.Fatalf("%s (%s): expected valid=%v got %v errors=%v",
					c.ID, c.Kind, c.ExpectValid, ok, vr.Errors)
			}
		})
	}
}

func TestExecutionEnvelopeAllPositives(t *testing.T) {
	for _, c := range vectorCatalog() {
		if !c.ExpectValid {
			continue
		}
		if !validateKind(c.Kind, c.Payload) {
			t.Fatalf("positive %s rejected", c.ID)
		}
	}
}

func TestExecutionEnvelopeAllNegatives(t *testing.T) {
	for _, c := range vectorCatalog() {
		if c.ExpectValid {
			continue
		}
		if validateKind(c.Kind, c.Payload) {
			t.Fatalf("negative %s accepted", c.ID)
		}
	}
}

func TestExecutionEnvelopeCrossKindInvariants(t *testing.T) {
	payload := baseResultSucceeded()
	if !validateKind("result", payload) {
		t.Fatal("base succeeded result should validate")
	}
	payload["error"] = basePortableError()
	if validateKind("result", payload) {
		t.Fatal("succeeded+error must reject")
	}

	failed := baseResultFailed()
	if !validateKind("result", failed) {
		t.Fatal("failed result should validate")
	}
	if !validateKind("error", failed["error"]) {
		t.Fatal("embedded portable error should validate")
	}

	rc := baseReceiptSucceeded()
	delete(rc, "result_cid")
	if validateKind("receipt", rc) {
		t.Fatal("receipt without result_cid must reject")
	}
}
