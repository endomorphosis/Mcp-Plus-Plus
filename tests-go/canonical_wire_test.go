package testsmcp

import (
	"encoding/json"
	"testing"

	"github.com/go-playground/validator/v10"
)

// Cross-server wire conformance for canonical full-name models. Mirrors the
// py/ts/rs conformance suites: deserialize the exact JSON-RPC shapes both
// ipfs_accelerate_py and ipfs_datasets_py emit and validate them, so third
// parties using the Go validator interoperate with both servers.

func TestCanonicalDelegationWire(t *testing.T) {
	v := validator.New()
	raw := `{"issuer":"did:key:zAlice","audience":"did:key:zBob",
		"capabilities":[{"resource":"mcp://tool/infer","ability":"invoke"}],
		"expiry":1782680000,"proof_cids":[],
		"cid":"bafkreifxone36h5jwjwulvkf27le3lmwon7jz65tzo27luipw55q7tcevu"}`
	var d Delegation
	if err := json.Unmarshal([]byte(raw), &d); err != nil {
		t.Fatalf("delegation unmarshal: %v", err)
	}
	if err := v.Struct(d); err != nil {
		t.Fatalf("delegation validate: %v", err)
	}
	if d.Issuer != "did:key:zAlice" || len(d.Capabilities) != 1 {
		t.Fatalf("delegation fields wrong: %+v", d)
	}
}

func TestCanonicalDAGEventBothTimestampForms(t *testing.T) {
	v := validator.New()
	c := "bafkreifxone36h5jwjwulvkf27le3lmwon7jz65tzo27luipw55q7tcevu"
	epoch := `{"event_type":"envelope","event_cid":"` + c + `","parents":[],
		"timestamp":1782680000.0,"payload":{"method":"infer"}}`
	iso := `{"event_type":"receipt","event_cid":"` + c + `","parents":["` + c + `"],
		"timestamp":"2026-06-28T00:00:00Z","payload":{"receipt_cid":"` + c + `"}}`
	for _, raw := range []string{epoch, iso} {
		var e DAGEvent
		if err := json.Unmarshal([]byte(raw), &e); err != nil {
			t.Fatalf("dag unmarshal: %v", err)
		}
		if err := v.Struct(e); err != nil {
			t.Fatalf("dag validate: %v", err)
		}
	}
}

func TestCanonicalPolicyDecisionWire(t *testing.T) {
	v := validator.New()
	var p PolicyDecisionWire
	raw := `{"decision":"allow","obligations":[],"allowed":true}`
	if err := json.Unmarshal([]byte(raw), &p); err != nil {
		t.Fatalf("policy unmarshal: %v", err)
	}
	if err := v.Struct(p); err != nil {
		t.Fatalf("policy validate: %v", err)
	}
	if p.Decision != "allow" || p.Allowed == nil || !*p.Allowed {
		t.Fatalf("policy fields wrong: %+v", p)
	}
}

func TestCanonicalErrorCodes(t *testing.T) {
	if ErrMethodNotFound != -32601 || ErrServerError != -32000 {
		t.Fatalf("error codes wrong")
	}
}
