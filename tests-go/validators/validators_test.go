package validators

import (
	"fmt"
	"testing"
	"time"

	testsmcp "github.com/endomorphosis/Mcp-Plus-Plus/tests-go"
)

func TestBaseMCPValidator_JSONRPCRequest(t *testing.T) {
	validator := NewBaseMCPValidator()
	
	tests := []struct {
		name    string
		input   string
		wantErr bool
	}{
		{
			name:    "valid request",
			input:   `{"jsonrpc":"2.0","method":"initialize","params":{},"id":1}`,
			wantErr: false,
		},
		{
			name:    "missing jsonrpc",
			input:   `{"method":"initialize","params":{},"id":1}`,
			wantErr: true,
		},
		{
			name:    "wrong jsonrpc version",
			input:   `{"jsonrpc":"1.0","method":"initialize","params":{},"id":1}`,
			wantErr: true,
		},
		{
			name:    "missing method",
			input:   `{"jsonrpc":"2.0","params":{},"id":1}`,
			wantErr: true,
		},
		{
			name:    "missing id",
			input:   `{"jsonrpc":"2.0","method":"initialize","params":{}}`,
			wantErr: true,
		},
	}
	
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, err := validator.ValidateJSONRPCRequest([]byte(tt.input))
			if (err != nil) != tt.wantErr {
				t.Errorf("ValidateJSONRPCRequest() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}

func TestBaseMCPValidator_JSONRPCResponse(t *testing.T) {
	validator := NewBaseMCPValidator()
	
	tests := []struct {
		name    string
		input   string
		wantErr bool
	}{
		{
			name:    "valid response with result",
			input:   `{"jsonrpc":"2.0","id":1,"result":{"status":"ok"}}`,
			wantErr: false,
		},
		{
			name:    "valid response with error",
			input:   `{"jsonrpc":"2.0","id":1,"error":{"code":-32600,"message":"Invalid Request"}}`,
			wantErr: false,
		},
		{
			name:    "both result and error",
			input:   `{"jsonrpc":"2.0","id":1,"result":{},"error":{"code":-32600,"message":"Invalid"}}`,
			wantErr: true,
		},
		{
			name:    "neither result nor error",
			input:   `{"jsonrpc":"2.0","id":1}`,
			wantErr: true,
		},
	}
	
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, err := validator.ValidateJSONRPCResponse([]byte(tt.input))
			if (err != nil) != tt.wantErr {
				t.Errorf("ValidateJSONRPCResponse() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}

func TestBaseMCPValidator_Notification(t *testing.T) {
	validator := NewBaseMCPValidator()
	
	tests := []struct {
		name    string
		input   string
		wantErr bool
	}{
		{
			name:    "valid notification",
			input:   `{"jsonrpc":"2.0","method":"notifications/progress","params":{"progress":50}}`,
			wantErr: false,
		},
		{
			name:    "method not starting with notifications/",
			input:   `{"jsonrpc":"2.0","method":"progress","params":{}}`,
			wantErr: true,
		},
	}
	
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, err := validator.ValidateJSONRPCNotification([]byte(tt.input))
			if (err != nil) != tt.wantErr {
				t.Errorf("ValidateJSONRPCNotification() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}

func TestBaseMCPValidator_InitializeRequest(t *testing.T) {
	validator := NewBaseMCPValidator()
	
	validInit := `{
		"jsonrpc":"2.0",
		"method":"initialize",
		"params":{
			"protocolVersion":"1.0.0",
			"capabilities":{"tools":{}},
			"clientInfo":{"name":"test-client","version":"1.0.0"}
		},
		"id":1
	}`
	
	_, err := validator.ValidateInitializeRequest([]byte(validInit))
	if err != nil {
		t.Errorf("ValidateInitializeRequest() unexpected error: %v", err)
	}
	
	invalidInit := `{
		"jsonrpc":"2.0",
		"method":"initialize",
		"params":{},
		"id":1
	}`
	
	_, err = validator.ValidateInitializeRequest([]byte(invalidInit))
	if err == nil {
		t.Error("ValidateInitializeRequest() expected error for invalid params")
	}
}

func TestBaseMCPValidator_ToolCall(t *testing.T) {
	validator := NewBaseMCPValidator()
	
	validToolCall := `{
		"jsonrpc":"2.0",
		"method":"tools/call",
		"params":{"name":"get_weather","arguments":{"location":"NYC"}},
		"id":1
	}`
	
	_, err := validator.ValidateToolCall([]byte(validToolCall))
	if err != nil {
		t.Errorf("ValidateToolCall() unexpected error: %v", err)
	}
}

func TestBaseMCPValidator_ResourceRead(t *testing.T) {
	validator := NewBaseMCPValidator()
	
	validResourceRead := `{
		"jsonrpc":"2.0",
		"method":"resources/read",
		"params":{"uri":"file:///path/to/resource"},
		"id":1
	}`
	
	_, err := validator.ValidateResourceRead([]byte(validResourceRead))
	if err != nil {
		t.Errorf("ValidateResourceRead() unexpected error: %v", err)
	}
}

func TestBaseMCPValidator_PromptGet(t *testing.T) {
	validator := NewBaseMCPValidator()
	
	validPromptGet := `{
		"jsonrpc":"2.0",
		"method":"prompts/get",
		"params":{"name":"code-review","arguments":{"language":"go"}},
		"id":1
	}`
	
	_, err := validator.ValidatePromptGet([]byte(validPromptGet))
	if err != nil {
		t.Errorf("ValidatePromptGet() unexpected error: %v", err)
	}
}

func TestMCPIDLValidator_InterfaceDescriptor(t *testing.T) {
	validator := NewMCPIDLValidator()
	
	validDescriptor := `{
		"interface_name":"WeatherService",
		"version":"1.0.0",
		"methods":[{
			"name":"get_weather",
			"return_type":"Weather",
			"parameters":[{"name":"location","type":"string","required":true}]
		}]
	}`
	
	_, err := validator.ValidateInterfaceDescriptor([]byte(validDescriptor))
	if err != nil {
		t.Errorf("ValidateInterfaceDescriptor() unexpected error: %v", err)
	}
}

func TestCIDValidator_ExecutionEnvelope(t *testing.T) {
	validator := NewCIDValidator()
	
	validEnvelope := `{
		"interface_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
		"input_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
		"parents":["QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG"],
		"invocation":{"method":"get_weather","params":{"location":"NYC"}}
	}`
	
	_, err := validator.ValidateExecutionEnvelope([]byte(validEnvelope))
	if err != nil {
		t.Errorf("ValidateExecutionEnvelope() unexpected error: %v", err)
	}
}

func TestCIDValidator_ExecutionReceipt(t *testing.T) {
	validator := NewCIDValidator()
	
	timestamp := time.Now().Format(time.RFC3339)
	validReceipt := `{
		"envelope_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
		"output_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
		"status":"success",
		"result":{"temperature":72},
		"timestamp":"` + timestamp + `"
	}`
	
	_, err := validator.ValidateExecutionReceipt([]byte(validReceipt))
	if err != nil {
		t.Errorf("ValidateExecutionReceipt() unexpected error: %v", err)
	}
}

func TestUCANValidator_UCANToken(t *testing.T) {
	validator := NewUCANValidator()
	
	exp := time.Now().Add(24 * time.Hour).Unix()
	validToken := `{
		"iss":"did:key:123",
		"aud":"did:key:456",
		"att":[{"with":"storage://mybucket","can":"read"}],
		"exp":` + fmt.Sprintf("%d", exp) + `
	}`
	
	_, err := validator.ValidateUCANToken([]byte(validToken))
	if err != nil {
		t.Errorf("ValidateUCANToken() unexpected error: %v", err)
	}
}

func TestPolicyValidator_PolicyDescriptor(t *testing.T) {
	validator := NewPolicyValidator()
	
	validPolicy := `{
		"policy_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
		"type":"permission",
		"target":"resource:documents/*",
		"constraints":[{"type":"time","condition":"between","value":"9:00-17:00"}]
	}`
	
	_, err := validator.ValidatePolicyDescriptor([]byte(validPolicy))
	if err != nil {
		t.Errorf("ValidatePolicyDescriptor() unexpected error: %v", err)
	}
}

func TestPolicyValidator_PolicyDecision(t *testing.T) {
	validator := NewPolicyValidator()
	
	timestamp := time.Now().Format(time.RFC3339)
	validDecision := `{
		"decision_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
		"decision":"allow",
		"policy_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
		"timestamp":"` + timestamp + `"
	}`
	
	_, err := validator.ValidatePolicyDecision([]byte(validDecision))
	if err != nil {
		t.Errorf("ValidatePolicyDecision() unexpected error: %v", err)
	}
}

func TestTransportValidator_TransportMessage(t *testing.T) {
	validator := NewTransportValidator()
	
	validMessage := `{
		"protocol_id":"/mcp+p2p/1.0.0",
		"session_id":"session-123",
		"sequence":1,
		"payload":{"method":"initialize"}
	}`
	
	_, err := validator.ValidateTransportMessage([]byte(validMessage))
	if err != nil {
		t.Errorf("ValidateTransportMessage() unexpected error: %v", err)
	}
}

func TestEventDAGValidator_Event(t *testing.T) {
	validator := NewEventDAGValidator()
	
	timestamp := time.Now().Format(time.RFC3339)
	validEvent := `{
		"event_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
		"type":"execution",
		"timestamp":"` + timestamp + `",
		"action":"tool_call",
		"parents":[]
	}`
	
	_, err := validator.ValidateEvent([]byte(validEvent))
	if err != nil {
		t.Errorf("ValidateEvent() unexpected error: %v", err)
	}
}

func TestEventDAGValidator_EventDAG(t *testing.T) {
	validator := NewEventDAGValidator()
	
	timestamp := time.Now().Format(time.RFC3339)
	validDAG := `{
		"events":{
			"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG":{
				"event_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
				"type":"execution",
				"timestamp":"` + timestamp + `",
				"action":"init",
				"parents":[]
			}
		},
		"roots":["QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG"]
	}`
	
	_, err := validator.ValidateEventDAG([]byte(validDAG))
	if err != nil {
		t.Errorf("ValidateEventDAG() unexpected error: %v", err)
	}
}

// Test cycle detection in DAG
func TestEventDAGValidator_CycleDetection(t *testing.T) {
	validator := NewEventDAGValidator()
	
	// Create a DAG with a cycle
	dag := &testsmcp.EventDAG{
		Events: map[string]*testsmcp.Event{
			"event1": {
				EventCID: "event1",
				Type:     "test",
				Action:   "action1",
				Parents:  []string{"event2"}, // Creates cycle
				Timestamp: time.Now(),
			},
			"event2": {
				EventCID: "event2",
				Type:     "test",
				Action:   "action2",
				Parents:  []string{"event1"}, // Creates cycle
				Timestamp: time.Now(),
			},
		},
		Roots: []string{"event1"},
	}
	
	err := validator.checkForCycles(dag)
	if err == nil {
		t.Error("checkForCycles() expected error for cyclic DAG")
	}
}
