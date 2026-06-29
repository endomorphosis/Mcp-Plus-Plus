package testsmcp

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"

	"github.com/go-playground/validator/v10"
)

// Cross-language conformance: validate shared vectors against canonical models.
// Same ../conformance/vectors/*.json as py/ts/rs so the four mirrors can't drift.
func TestConformanceVectors(t *testing.T) {
	v := validator.New()
	dir := filepath.Join("..", "conformance", "vectors")
	files, err := os.ReadDir(dir)
	if err != nil {
		t.Fatalf("read vectors dir: %v", err)
	}
	n := 0
	for _, f := range files {
		if filepath.Ext(f.Name()) != ".json" {
			continue
		}
		raw, _ := os.ReadFile(filepath.Join(dir, f.Name()))
		var vec struct {
			Model   string          `json:"model"`
			Payload json.RawMessage `json:"payload"`
		}
		if err := json.Unmarshal(raw, &vec); err != nil {
			t.Fatalf("%s: %v", f.Name(), err)
		}
		var target interface{}
		switch vec.Model {
		case "InitializeResult":
			target = &InitializeResult{}
		case "PolicyDecision":
			target = &PolicyDecisionWire{}
		case "P2PMessage":
			target = &P2PMessage{}
		case "Delegation":
			target = &Delegation{}
		case "DAGEvent":
			target = &DAGEvent{}
		case "ExecutionReceipt":
			target = &ExecutionReceipt{}
		default:
			t.Fatalf("unknown model %s in %s", vec.Model, f.Name())
		}
		if err := json.Unmarshal(vec.Payload, target); err != nil {
			t.Fatalf("%s unmarshal: %v", f.Name(), err)
		}
		if err := v.Struct(target); err != nil {
			t.Fatalf("%s validate: %v", f.Name(), err)
		}
		n++
	}
	if n < 6 {
		t.Fatalf("expected vectors, got %d", n)
	}
}
