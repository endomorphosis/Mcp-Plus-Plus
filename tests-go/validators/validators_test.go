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
		{
			name:    "empty method",
			input:   `{"jsonrpc":"2.0","method":"","params":{},"id":1}`,
			wantErr: true,
		},
		{
			name:    "invalid JSON",
			input:   `{"jsonrpc":"2.0","method":}`,
			wantErr: true,
		},
		{
			name:    "valid request with string id",
			input:   `{"jsonrpc":"2.0","method":"initialize","params":{},"id":"abc"}`,
			wantErr: false,
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
		{
			name:    "invalid JSON",
			input:   `{"jsonrpc":"2.0","id":}`,
			wantErr: true,
		},
		{
			name:    "missing jsonrpc",
			input:   `{"id":1,"result":{}}`,
			wantErr: true,
		},
		{
			name:    "missing id",
			input:   `{"jsonrpc":"2.0","result":{}}`,
			wantErr: true,
		},
		{
			name:    "wrong jsonrpc version",
			input:   `{"jsonrpc":"1.0","id":1,"result":{}}`,
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
		{
			name:    "invalid JSON",
			input:   `{"jsonrpc":"2.0","method":}`,
			wantErr: true,
		},
		{
			name:    "missing jsonrpc",
			input:   `{"method":"notifications/test","params":{}}`,
			wantErr: true,
		},
		{
			name:    "missing method",
			input:   `{"jsonrpc":"2.0","params":{}}`,
			wantErr: true,
		},
		{
			name:    "empty method",
			input:   `{"jsonrpc":"2.0","method":"","params":{}}`,
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
	
	tests := []struct {
		name    string
		input   string
		wantErr bool
	}{
		{
			name: "valid initialize request",
			input: `{
				"jsonrpc":"2.0",
				"method":"initialize",
				"params":{
					"protocolVersion":"1.0.0",
					"capabilities":{"tools":{}},
					"clientInfo":{"name":"test-client","version":"1.0.0"}
				},
				"id":1
			}`,
			wantErr: false,
		},
		{
			name: "missing protocolVersion",
			input: `{
				"jsonrpc":"2.0",
				"method":"initialize",
				"params":{
					"capabilities":{"tools":{}},
					"clientInfo":{"name":"test-client","version":"1.0.0"}
				},
				"id":1
			}`,
			wantErr: true,
		},
		{
			name: "valid initialize request with empty capabilities",
			input: `{
				"jsonrpc":"2.0",
				"method":"initialize",
				"params":{
					"protocolVersion":"1.0.0",
					"capabilities":{},
					"clientInfo":{"name":"test-client","version":"1.0.0"}
				},
				"id":1
			}`,
			wantErr: false,
		},
		{
			name: "missing clientInfo",
			input: `{
				"jsonrpc":"2.0",
				"method":"initialize",
				"params":{
					"protocolVersion":"1.0.0",
					"capabilities":{"tools":{}}
				},
				"id":1
			}`,
			wantErr: true,
		},
		{
			name: "wrong method",
			input: `{
				"jsonrpc":"2.0",
				"method":"other",
				"params":{
					"protocolVersion":"1.0.0",
					"capabilities":{"tools":{}},
					"clientInfo":{"name":"test-client","version":"1.0.0"}
				},
				"id":1
			}`,
			wantErr: true,
		},
		{
			name: "empty clientInfo name",
			input: `{
				"jsonrpc":"2.0",
				"method":"initialize",
				"params":{
					"protocolVersion":"1.0.0",
					"capabilities":{"tools":{}},
					"clientInfo":{"name":"","version":"1.0.0"}
				},
				"id":1
			}`,
			wantErr: true,
		},
		{
			name: "empty clientInfo version",
			input: `{
				"jsonrpc":"2.0",
				"method":"initialize",
				"params":{
					"protocolVersion":"1.0.0",
					"capabilities":{"tools":{}},
					"clientInfo":{"name":"test-client","version":""}
				},
				"id":1
			}`,
			wantErr: true,
		},
		{
			name:    "invalid JSON",
			input:   `{"jsonrpc":"2.0","method":"initialize","params":}`,
			wantErr: true,
		},
	}
	
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, err := validator.ValidateInitializeRequest([]byte(tt.input))
			if (err != nil) != tt.wantErr {
				t.Errorf("ValidateInitializeRequest() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}

func TestBaseMCPValidator_ToolCall(t *testing.T) {
	validator := NewBaseMCPValidator()
	
	tests := []struct {
		name    string
		input   string
		wantErr bool
	}{
		{
			name: "valid tool call",
			input: `{
				"jsonrpc":"2.0",
				"method":"tools/call",
				"params":{"name":"get_weather","arguments":{"location":"NYC"}},
				"id":1
			}`,
			wantErr: false,
		},
		{
			name: "missing name",
			input: `{
				"jsonrpc":"2.0",
				"method":"tools/call",
				"params":{"arguments":{"location":"NYC"}},
				"id":1
			}`,
			wantErr: true,
		},
		{
			name: "empty name",
			input: `{
				"jsonrpc":"2.0",
				"method":"tools/call",
				"params":{"name":"","arguments":{"location":"NYC"}},
				"id":1
			}`,
			wantErr: true,
		},
		{
			name: "wrong method",
			input: `{
				"jsonrpc":"2.0",
				"method":"other/call",
				"params":{"name":"get_weather","arguments":{"location":"NYC"}},
				"id":1
			}`,
			wantErr: true,
		},
		{
			name:    "invalid JSON",
			input:   `{"jsonrpc":"2.0","method":"tools/call","params":}`,
			wantErr: true,
		},
		{
			name: "valid tool call without arguments",
			input: `{
				"jsonrpc":"2.0",
				"method":"tools/call",
				"params":{"name":"get_status"},
				"id":1
			}`,
			wantErr: false,
		},
	}
	
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, err := validator.ValidateToolCall([]byte(tt.input))
			if (err != nil) != tt.wantErr {
				t.Errorf("ValidateToolCall() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}

func TestBaseMCPValidator_ResourceRead(t *testing.T) {
	validator := NewBaseMCPValidator()
	
	tests := []struct {
		name    string
		input   string
		wantErr bool
	}{
		{
			name: "valid resource read",
			input: `{
				"jsonrpc":"2.0",
				"method":"resources/read",
				"params":{"uri":"file:///path/to/resource"},
				"id":1
			}`,
			wantErr: false,
		},
		{
			name: "missing uri",
			input: `{
				"jsonrpc":"2.0",
				"method":"resources/read",
				"params":{},
				"id":1
			}`,
			wantErr: true,
		},
		{
			name: "empty uri",
			input: `{
				"jsonrpc":"2.0",
				"method":"resources/read",
				"params":{"uri":""},
				"id":1
			}`,
			wantErr: true,
		},
		{
			name: "wrong method",
			input: `{
				"jsonrpc":"2.0",
				"method":"resources/write",
				"params":{"uri":"file:///path/to/resource"},
				"id":1
			}`,
			wantErr: true,
		},
		{
			name:    "invalid JSON",
			input:   `{"jsonrpc":"2.0","method":"resources/read","params":}`,
			wantErr: true,
		},
	}
	
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, err := validator.ValidateResourceRead([]byte(tt.input))
			if (err != nil) != tt.wantErr {
				t.Errorf("ValidateResourceRead() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}

func TestBaseMCPValidator_PromptGet(t *testing.T) {
	validator := NewBaseMCPValidator()
	
	tests := []struct {
		name    string
		input   string
		wantErr bool
	}{
		{
			name: "valid prompt get",
			input: `{
				"jsonrpc":"2.0",
				"method":"prompts/get",
				"params":{"name":"code-review","arguments":{"language":"go"}},
				"id":1
			}`,
			wantErr: false,
		},
		{
			name: "missing name",
			input: `{
				"jsonrpc":"2.0",
				"method":"prompts/get",
				"params":{"arguments":{"language":"go"}},
				"id":1
			}`,
			wantErr: true,
		},
		{
			name: "empty name",
			input: `{
				"jsonrpc":"2.0",
				"method":"prompts/get",
				"params":{"name":"","arguments":{"language":"go"}},
				"id":1
			}`,
			wantErr: true,
		},
		{
			name: "wrong method",
			input: `{
				"jsonrpc":"2.0",
				"method":"prompts/list",
				"params":{"name":"code-review","arguments":{"language":"go"}},
				"id":1
			}`,
			wantErr: true,
		},
		{
			name:    "invalid JSON",
			input:   `{"jsonrpc":"2.0","method":"prompts/get","params":}`,
			wantErr: true,
		},
		{
			name: "valid prompt get without arguments",
			input: `{
				"jsonrpc":"2.0",
				"method":"prompts/get",
				"params":{"name":"default-prompt"},
				"id":1
			}`,
			wantErr: false,
		},
	}
	
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, err := validator.ValidatePromptGet([]byte(tt.input))
			if (err != nil) != tt.wantErr {
				t.Errorf("ValidatePromptGet() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}

func TestMCPIDLValidator_InterfaceDescriptor(t *testing.T) {
	validator := NewMCPIDLValidator()
	
	tests := []struct {
		name    string
		input   string
		wantErr bool
	}{
		{
			name: "valid descriptor",
			input: `{
				"interface_name":"WeatherService",
				"version":"1.0.0",
				"methods":[{
					"name":"get_weather",
					"return_type":"Weather",
					"parameters":[{"name":"location","type":"string","required":true}]
				}]
			}`,
			wantErr: false,
		},
		{
			name: "missing interface_name",
			input: `{
				"version":"1.0.0",
				"methods":[{
					"name":"get_weather",
					"return_type":"Weather"
				}]
			}`,
			wantErr: true,
		},
		{
			name: "empty interface_name",
			input: `{
				"interface_name":"",
				"version":"1.0.0",
				"methods":[{
					"name":"get_weather",
					"return_type":"Weather"
				}]
			}`,
			wantErr: true,
		},
		{
			name: "missing version",
			input: `{
				"interface_name":"WeatherService",
				"methods":[{
					"name":"get_weather",
					"return_type":"Weather"
				}]
			}`,
			wantErr: true,
		},
		{
			name: "missing methods",
			input: `{
				"interface_name":"WeatherService",
				"version":"1.0.0",
				"methods":[]
			}`,
			wantErr: true,
		},
		{
			name: "method with empty name",
			input: `{
				"interface_name":"WeatherService",
				"version":"1.0.0",
				"methods":[{
					"name":"",
					"return_type":"Weather"
				}]
			}`,
			wantErr: true,
		},
		{
			name: "method with empty return_type",
			input: `{
				"interface_name":"WeatherService",
				"version":"1.0.0",
				"methods":[{
					"name":"get_weather",
					"return_type":""
				}]
			}`,
			wantErr: true,
		},
		{
			name:    "invalid JSON",
			input:   `{"interface_name":"WeatherService","version":}`,
			wantErr: true,
		},
	}
	
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, err := validator.ValidateInterfaceDescriptor([]byte(tt.input))
			if (err != nil) != tt.wantErr {
				t.Errorf("ValidateInterfaceDescriptor() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}

func TestMCPIDLValidator_CompatibilityCheck(t *testing.T) {
	validator := NewMCPIDLValidator()
	
	tests := []struct {
		name    string
		input   string
		wantErr bool
	}{
		{
			name: "compatible interfaces",
			input: `{
				"compatible":true,
				"reasons":[]
			}`,
			wantErr: false,
		},
		{
			name:    "invalid JSON",
			input:   `{"compatible":}`,
			wantErr: true,
		},
	}
	
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, err := validator.ValidateCompatibilityCheck([]byte(tt.input))
			if (err != nil) != tt.wantErr {
				t.Errorf("ValidateCompatibilityCheck() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}

func TestCIDValidator_ExecutionEnvelope(t *testing.T) {
	validator := NewCIDValidator()
	
	tests := []struct {
		name    string
		input   string
		wantErr bool
	}{
		{
			name: "valid envelope",
			input: `{
				"interface_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
				"input_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
				"parents":["QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG"],
				"invocation":{"method":"get_weather","params":{"location":"NYC"}}
			}`,
			wantErr: false,
		},
		{
			name: "invalid interface_cid format",
			input: `{
				"interface_cid":"invalid-cid",
				"input_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
				"parents":[],
				"invocation":{"method":"test"}
			}`,
			wantErr: true,
		},
		{
			name: "invalid input_cid format",
			input: `{
				"interface_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
				"input_cid":"bad-cid",
				"parents":[],
				"invocation":{"method":"test"}
			}`,
			wantErr: true,
		},
		{
			name: "missing interface_cid",
			input: `{
				"input_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
				"invocation":{"method":"test"}
			}`,
			wantErr: true,
		},
		{
			name: "missing input_cid",
			input: `{
				"interface_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
				"invocation":{"method":"test"}
			}`,
			wantErr: true,
		},
		{
			name: "missing invocation",
			input: `{
				"interface_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
				"input_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG"
			}`,
			wantErr: true,
		},
		{
			name: "invalid parent CID in array",
			input: `{
				"interface_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
				"input_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
				"parents":["invalid-parent-cid"],
				"invocation":{"method":"test"}
			}`,
			wantErr: true,
		},
		{
			name:    "invalid JSON",
			input:   `{"interface_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG","input_cid":}`,
			wantErr: true,
		},
	}
	
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, err := validator.ValidateExecutionEnvelope([]byte(tt.input))
			if (err != nil) != tt.wantErr {
				t.Errorf("ValidateExecutionEnvelope() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}

func TestCIDValidator_ExecutionReceipt(t *testing.T) {
	validator := NewCIDValidator()
	
	timestamp := time.Now().Format(time.RFC3339)
	
	tests := []struct {
		name    string
		input   string
		wantErr bool
	}{
		{
			name: "valid receipt with success",
			input: `{
				"envelope_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
				"output_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
				"status":"success",
				"result":{"temperature":72},
				"timestamp":"` + timestamp + `"
			}`,
			wantErr: false,
		},
		{
			name: "valid receipt with failure",
			input: `{
				"envelope_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
				"output_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
				"status":"failure",
				"error":{"code":-1,"message":"execution failed"},
				"timestamp":"` + timestamp + `"
			}`,
			wantErr: false,
		},
		{
			name: "invalid envelope_cid format",
			input: `{
				"envelope_cid":"invalid-cid",
				"output_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
				"status":"success",
				"result":{},
				"timestamp":"` + timestamp + `"
			}`,
			wantErr: true,
		},
		{
			name: "invalid output_cid format",
			input: `{
				"envelope_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
				"output_cid":"bad-cid",
				"status":"success",
				"result":{},
				"timestamp":"` + timestamp + `"
			}`,
			wantErr: true,
		},
		{
			name: "invalid status",
			input: `{
				"envelope_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
				"output_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
				"status":"pending",
				"result":{},
				"timestamp":"` + timestamp + `"
			}`,
			wantErr: true,
		},
		{
			name: "missing envelope_cid",
			input: `{
				"output_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
				"status":"success",
				"result":{},
				"timestamp":"` + timestamp + `"
			}`,
			wantErr: true,
		},
		{
			name: "missing output_cid",
			input: `{
				"envelope_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
				"status":"success",
				"result":{},
				"timestamp":"` + timestamp + `"
			}`,
			wantErr: true,
		},
		{
			name: "missing status",
			input: `{
				"envelope_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
				"output_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
				"result":{},
				"timestamp":"` + timestamp + `"
			}`,
			wantErr: true,
		},
		{
			name: "missing timestamp",
			input: `{
				"envelope_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
				"output_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
				"status":"success",
				"result":{}
			}`,
			wantErr: true,
		},
		{
			name:    "invalid JSON",
			input:   `{"envelope_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG","output_cid":}`,
			wantErr: true,
		},
	}
	
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, err := validator.ValidateExecutionReceipt([]byte(tt.input))
			if (err != nil) != tt.wantErr {
				t.Errorf("ValidateExecutionReceipt() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}

func TestUCANValidator_UCANToken(t *testing.T) {
	validator := NewUCANValidator()
	
	exp := time.Now().Add(24 * time.Hour).Unix()
	expPast := time.Now().Add(-24 * time.Hour).Unix()
	
	tests := []struct {
		name    string
		input   string
		wantErr bool
	}{
		{
			name: "valid token",
			input: `{
				"iss":"did:key:123",
				"aud":"did:key:456",
				"att":[{"with":"storage://mybucket","can":"read"}],
				"exp":` + fmt.Sprintf("%d", exp) + `
			}`,
			wantErr: false,
		},
		{
			name: "missing issuer",
			input: `{
				"aud":"did:key:456",
				"att":[{"with":"storage://mybucket","can":"read"}],
				"exp":` + fmt.Sprintf("%d", exp) + `
			}`,
			wantErr: true,
		},
		{
			name: "missing audience",
			input: `{
				"iss":"did:key:123",
				"att":[{"with":"storage://mybucket","can":"read"}],
				"exp":` + fmt.Sprintf("%d", exp) + `
			}`,
			wantErr: true,
		},
		{
			name: "missing capabilities",
			input: `{
				"iss":"did:key:123",
				"aud":"did:key:456",
				"att":[],
				"exp":` + fmt.Sprintf("%d", exp) + `
			}`,
			wantErr: true,
		},
		{
			name: "capability with empty with",
			input: `{
				"iss":"did:key:123",
				"aud":"did:key:456",
				"att":[{"with":"","can":"read"}],
				"exp":` + fmt.Sprintf("%d", exp) + `
			}`,
			wantErr: true,
		},
		{
			name: "capability with empty can",
			input: `{
				"iss":"did:key:123",
				"aud":"did:key:456",
				"att":[{"with":"storage://mybucket","can":""}],
				"exp":` + fmt.Sprintf("%d", exp) + `
			}`,
			wantErr: true,
		},
		{
			name: "missing expiration",
			input: `{
				"iss":"did:key:123",
				"aud":"did:key:456",
				"att":[{"with":"storage://mybucket","can":"read"}]
			}`,
			wantErr: true,
		},
		{
			name: "expired token",
			input: `{
				"iss":"did:key:123",
				"aud":"did:key:456",
				"att":[{"with":"storage://mybucket","can":"read"}],
				"exp":` + fmt.Sprintf("%d", expPast) + `
			}`,
			wantErr: false,
		},
		{
			name:    "invalid JSON",
			input:   `{"iss":"did:key:123","aud":}`,
			wantErr: true,
		},
	}
	
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, err := validator.ValidateUCANToken([]byte(tt.input))
			if (err != nil) != tt.wantErr {
				t.Errorf("ValidateUCANToken() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}

func TestUCANValidator_DelegationChain(t *testing.T) {
	validator := NewUCANValidator()
	
	exp := time.Now().Add(24 * time.Hour).Unix()
	
	tests := []struct {
		name    string
		input   string
		wantErr bool
	}{
		{
			name: "valid chain without proofs",
			input: `{
				"root":{
					"iss":"did:key:root",
					"aud":"did:key:delegate",
					"att":[{"with":"storage://mybucket","can":"read"}],
					"exp":` + fmt.Sprintf("%d", exp) + `
				},
				"proofs":[]
			}`,
			wantErr: false,
		},
		{
			name: "valid chain with proofs",
			input: `{
				"root":{
					"iss":"did:key:root",
					"aud":"did:key:delegate1",
					"att":[{"with":"storage://mybucket","can":"read"}],
					"exp":` + fmt.Sprintf("%d", exp) + `
				},
				"proofs":[
					{
						"iss":"did:key:delegate1",
						"aud":"did:key:delegate2",
						"att":[{"with":"storage://mybucket","can":"read"}],
						"exp":` + fmt.Sprintf("%d", exp) + `
					}
				]
			}`,
			wantErr: false,
		},
		{
			name: "invalid root token",
			input: `{
				"root":{
					"iss":"did:key:root",
					"aud":"did:key:delegate",
					"att":[],
					"exp":` + fmt.Sprintf("%d", exp) + `
				},
				"proofs":[]
			}`,
			wantErr: true,
		},
		{
			name: "invalid proof token",
			input: `{
				"root":{
					"iss":"did:key:root",
					"aud":"did:key:delegate1",
					"att":[{"with":"storage://mybucket","can":"read"}],
					"exp":` + fmt.Sprintf("%d", exp) + `
				},
				"proofs":[
					{
						"iss":"did:key:delegate1",
						"aud":"did:key:delegate2",
						"att":[],
						"exp":` + fmt.Sprintf("%d", exp) + `
					}
				]
			}`,
			wantErr: true,
		},
		{
			name:    "invalid JSON",
			input:   `{"root":{"iss":"did:key:root","aud":}}`,
			wantErr: true,
		},
	}
	
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, err := validator.ValidateDelegationChain([]byte(tt.input))
			if (err != nil) != tt.wantErr {
				t.Errorf("ValidateDelegationChain() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}

func TestPolicyValidator_PolicyDescriptor(t *testing.T) {
	validator := NewPolicyValidator()
	
	timestamp := time.Now().Format(time.RFC3339)
	
	tests := []struct {
		name    string
		input   string
		wantErr bool
	}{
		{
			name: "valid permission policy",
			input: `{
				"policy_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
				"type":"permission",
				"target":"resource:documents/*",
				"constraints":[{"type":"time","condition":"between","value":"9:00-17:00"}]
			}`,
			wantErr: false,
		},
		{
			name: "valid prohibition policy",
			input: `{
				"policy_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
				"type":"prohibition",
				"target":"resource:sensitive/*",
				"constraints":[]
			}`,
			wantErr: false,
		},
		{
			name: "valid obligation policy",
			input: `{
				"policy_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
				"type":"obligation",
				"target":"action:audit",
				"constraints":[]
			}`,
			wantErr: false,
		},
		{
			name: "policy with temporal constraints",
			input: `{
				"policy_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
				"type":"permission",
				"target":"resource:documents/*",
				"valid_from":"` + timestamp + `",
				"valid_until":"` + time.Now().Add(24 * time.Hour).Format(time.RFC3339) + `"
			}`,
			wantErr: false,
		},
		{
			name: "invalid policy_cid format",
			input: `{
				"policy_cid":"invalid-cid",
				"type":"permission",
				"target":"resource:documents/*"
			}`,
			wantErr: true,
		},
		{
			name: "invalid policy type",
			input: `{
				"policy_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
				"type":"invalid",
				"target":"resource:documents/*"
			}`,
			wantErr: true,
		},
		{
			name: "missing policy_cid",
			input: `{
				"type":"permission",
				"target":"resource:documents/*"
			}`,
			wantErr: true,
		},
		{
			name: "missing type",
			input: `{
				"policy_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
				"target":"resource:documents/*"
			}`,
			wantErr: true,
		},
		{
			name: "missing target",
			input: `{
				"policy_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
				"type":"permission"
			}`,
			wantErr: true,
		},
		{
			name:    "invalid JSON",
			input:   `{"policy_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG","type":}`,
			wantErr: true,
		},
	}
	
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, err := validator.ValidatePolicyDescriptor([]byte(tt.input))
			if (err != nil) != tt.wantErr {
				t.Errorf("ValidatePolicyDescriptor() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}

func TestPolicyValidator_PolicyDecision(t *testing.T) {
	validator := NewPolicyValidator()
	
	timestamp := time.Now().Format(time.RFC3339)
	obligationDeadline := time.Now().Add(24 * time.Hour).Format(time.RFC3339)
	
	tests := []struct {
		name    string
		input   string
		wantErr bool
	}{
		{
			name: "valid allow decision",
			input: `{
				"decision_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
				"decision":"allow",
				"policy_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
				"timestamp":"` + timestamp + `"
			}`,
			wantErr: false,
		},
		{
			name: "valid deny decision",
			input: `{
				"decision_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
				"decision":"deny",
				"policy_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
				"timestamp":"` + timestamp + `"
			}`,
			wantErr: false,
		},
		{
			name: "valid allow_with_obligations",
			input: `{
				"decision_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
				"decision":"allow_with_obligations",
				"policy_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
				"timestamp":"` + timestamp + `",
				"obligations":[{"action":"audit","deadline":"` + obligationDeadline + `","status":"pending"}]
			}`,
			wantErr: false,
		},
		{
			name: "allow_with_obligations without obligations",
			input: `{
				"decision_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
				"decision":"allow_with_obligations",
				"policy_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
				"timestamp":"` + timestamp + `",
				"obligations":[]
			}`,
			wantErr: true,
		},
		{
			name: "invalid decision_cid format",
			input: `{
				"decision_cid":"invalid-cid",
				"decision":"allow",
				"policy_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
				"timestamp":"` + timestamp + `"
			}`,
			wantErr: true,
		},
		{
			name: "invalid policy_cid format",
			input: `{
				"decision_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
				"decision":"allow",
				"policy_cid":"bad-cid",
				"timestamp":"` + timestamp + `"
			}`,
			wantErr: true,
		},
		{
			name: "invalid decision type",
			input: `{
				"decision_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
				"decision":"maybe",
				"policy_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
				"timestamp":"` + timestamp + `"
			}`,
			wantErr: true,
		},
		{
			name: "missing decision_cid",
			input: `{
				"decision":"allow",
				"policy_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
				"timestamp":"` + timestamp + `"
			}`,
			wantErr: true,
		},
		{
			name: "missing timestamp",
			input: `{
				"decision_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
				"decision":"allow",
				"policy_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG"
			}`,
			wantErr: true,
		},
		{
			name:    "invalid JSON",
			input:   `{"decision_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG","decision":}`,
			wantErr: true,
		},
	}
	
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, err := validator.ValidatePolicyDecision([]byte(tt.input))
			if (err != nil) != tt.wantErr {
				t.Errorf("ValidatePolicyDecision() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}

func TestTransportValidator_TransportMessage(t *testing.T) {
	validator := NewTransportValidator()
	
	tests := []struct {
		name    string
		input   string
		wantErr bool
	}{
		{
			name: "valid message",
			input: `{
				"protocol_id":"/mcp+p2p/1.0.0",
				"session_id":"session-123",
				"sequence":1,
				"payload":{"method":"initialize"}
			}`,
			wantErr: false,
		},
		{
			name: "invalid protocol_id",
			input: `{
				"protocol_id":"/mcp/1.0.0",
				"session_id":"session-123",
				"sequence":1,
				"payload":{"method":"initialize"}
			}`,
			wantErr: true,
		},
		{
			name: "missing protocol_id",
			input: `{
				"session_id":"session-123",
				"sequence":1,
				"payload":{"method":"initialize"}
			}`,
			wantErr: true,
		},
		{
			name: "missing session_id",
			input: `{
				"protocol_id":"/mcp+p2p/1.0.0",
				"sequence":1,
				"payload":{"method":"initialize"}
			}`,
			wantErr: true,
		},
		{
			name: "missing sequence",
			input: `{
				"protocol_id":"/mcp+p2p/1.0.0",
				"session_id":"session-123",
				"payload":{"method":"initialize"}
			}`,
			wantErr: true,
		},
		{
			name: "missing payload",
			input: `{
				"protocol_id":"/mcp+p2p/1.0.0",
				"session_id":"session-123",
				"sequence":1
			}`,
			wantErr: true,
		},
		{
			name:    "invalid JSON",
			input:   `{"protocol_id":"/mcp+p2p/1.0.0","session_id":}`,
			wantErr: true,
		},
	}
	
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, err := validator.ValidateTransportMessage([]byte(tt.input))
			if (err != nil) != tt.wantErr {
				t.Errorf("ValidateTransportMessage() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}

func TestTransportValidator_SessionInit(t *testing.T) {
	validator := NewTransportValidator()
	
	tests := []struct {
		name    string
		input   string
		wantErr bool
	}{
		{
			name: "valid session init",
			input: `{
				"session_id":"session-123",
				"protocol_version":"1.0.0",
				"capabilities":{"tools":{}},
				"peer_id":"peer-456"
			}`,
			wantErr: false,
		},
		{
			name: "valid session init with empty capabilities",
			input: `{
				"session_id":"session-123",
				"protocol_version":"1.0.0",
				"capabilities":{},
				"peer_id":"peer-456"
			}`,
			wantErr: false,
		},
		{
			name: "missing session_id",
			input: `{
				"protocol_version":"1.0.0",
				"capabilities":{"tools":{}},
				"peer_id":"peer-456"
			}`,
			wantErr: true,
		},
		{
			name: "missing protocol_version",
			input: `{
				"session_id":"session-123",
				"capabilities":{"tools":{}},
				"peer_id":"peer-456"
			}`,
			wantErr: true,
		},
		{
			name: "missing peer_id",
			input: `{
				"session_id":"session-123",
				"protocol_version":"1.0.0",
				"capabilities":{"tools":{}}
			}`,
			wantErr: true,
		},
		{
			name:    "invalid JSON",
			input:   `{"session_id":"session-123","protocol_version":}`,
			wantErr: true,
		},
	}
	
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, err := validator.ValidateSessionInit([]byte(tt.input))
			if (err != nil) != tt.wantErr {
				t.Errorf("ValidateSessionInit() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}

func TestEventDAGValidator_Event(t *testing.T) {
	validator := NewEventDAGValidator()
	
	timestamp := time.Now().Format(time.RFC3339)
	
	tests := []struct {
		name    string
		input   string
		wantErr bool
	}{
		{
			name: "valid event without parents",
			input: `{
				"event_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
				"type":"execution",
				"timestamp":"` + timestamp + `",
				"action":"tool_call",
				"parents":[]
			}`,
			wantErr: false,
		},
		{
			name: "valid event with parents",
			input: `{
				"event_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
				"type":"execution",
				"timestamp":"` + timestamp + `",
				"action":"tool_call",
				"parents":["QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG"]
			}`,
			wantErr: false,
		},
		{
			name: "valid event with actor and target",
			input: `{
				"event_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
				"type":"execution",
				"timestamp":"` + timestamp + `",
				"action":"tool_call",
				"actor":"did:key:123",
				"target":"resource:file.txt",
				"parents":[]
			}`,
			wantErr: false,
		},
		{
			name: "invalid event_cid format",
			input: `{
				"event_cid":"invalid-cid",
				"type":"execution",
				"timestamp":"` + timestamp + `",
				"action":"tool_call",
				"parents":[]
			}`,
			wantErr: true,
		},
		{
			name: "invalid parent CID format",
			input: `{
				"event_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
				"type":"execution",
				"timestamp":"` + timestamp + `",
				"action":"tool_call",
				"parents":["bad-cid"]
			}`,
			wantErr: true,
		},
		{
			name: "missing event_cid",
			input: `{
				"type":"execution",
				"timestamp":"` + timestamp + `",
				"action":"tool_call",
				"parents":[]
			}`,
			wantErr: true,
		},
		{
			name: "missing type",
			input: `{
				"event_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
				"timestamp":"` + timestamp + `",
				"action":"tool_call",
				"parents":[]
			}`,
			wantErr: true,
		},
		{
			name: "missing timestamp",
			input: `{
				"event_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
				"type":"execution",
				"action":"tool_call",
				"parents":[]
			}`,
			wantErr: true,
		},
		{
			name: "missing action",
			input: `{
				"event_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
				"type":"execution",
				"timestamp":"` + timestamp + `",
				"parents":[]
			}`,
			wantErr: true,
		},
		{
			name:    "invalid JSON",
			input:   `{"event_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG","type":}`,
			wantErr: true,
		},
	}
	
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, err := validator.ValidateEvent([]byte(tt.input))
			if (err != nil) != tt.wantErr {
				t.Errorf("ValidateEvent() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}

func TestEventDAGValidator_EventDAG(t *testing.T) {
	validator := NewEventDAGValidator()
	
	timestamp := time.Now().Format(time.RFC3339)
	
	tests := []struct {
		name    string
		input   string
		wantErr bool
	}{
		{
			name: "valid DAG with single event",
			input: `{
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
			}`,
			wantErr: false,
		},
		{
			name: "valid DAG with multiple events",
			input: `{
				"events":{
					"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG":{
						"event_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
						"type":"execution",
						"timestamp":"` + timestamp + `",
						"action":"init",
						"parents":[]
					},
					"QmPZ9gcCEpqKTo6aq61g2nXGUhM4iCL3ewB6LDXZCtioEB":{
						"event_cid":"QmPZ9gcCEpqKTo6aq61g2nXGUhM4iCL3ewB6LDXZCtioEB",
						"type":"execution",
						"timestamp":"` + timestamp + `",
						"action":"step",
						"parents":["QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG"]
					}
				},
				"roots":["QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG"]
			}`,
			wantErr: false,
		},
		{
			name: "root CID not in events",
			input: `{
				"events":{
					"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG":{
						"event_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
						"type":"execution",
						"timestamp":"` + timestamp + `",
						"action":"init",
						"parents":[]
					}
				},
				"roots":["QmPZ9gcCEpqKTo6aq61g2nXGUhM4iCL3ewB6LDXZCtioEB"]
			}`,
			wantErr: true,
		},
		{
			name: "parent reference not in events",
			input: `{
				"events":{
					"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG":{
						"event_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
						"type":"execution",
						"timestamp":"` + timestamp + `",
						"action":"init",
						"parents":["QmPZ9gcCEpqKTo6aq61g2nXGUhM4iCL3ewB6LDXZCtioEB"]
					}
				},
				"roots":["QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG"]
			}`,
			wantErr: true,
		},
		{
			name: "missing events",
			input: `{
				"events":{},
				"roots":["QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG"]
			}`,
			wantErr: true,
		},
		{
			name: "missing roots",
			input: `{
				"events":{
					"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG":{
						"event_cid":"QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
						"type":"execution",
						"timestamp":"` + timestamp + `",
						"action":"init",
						"parents":[]
					}
				},
				"roots":[]
			}`,
			wantErr: true,
		},
		{
			name:    "invalid JSON",
			input:   `{"events":{},"roots":}`,
			wantErr: true,
		},
	}
	
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, err := validator.ValidateEventDAG([]byte(tt.input))
			if (err != nil) != tt.wantErr {
				t.Errorf("ValidateEventDAG() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
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
