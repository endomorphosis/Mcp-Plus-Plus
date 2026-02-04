package validators

import (
	"encoding/json"
	"fmt"

	testsmcp "github.com/endomorphosis/Mcp-Plus-Plus/tests-go"
)

// TransportValidator validates Transport (Profile E) messages.
//
// SPEC: Transport.md § mcp+p2p Protocol
// Validates transport protocol framing and session management.
type TransportValidator struct {
	base *BaseMCPValidator
}

// NewTransportValidator creates a new transport protocol validator.
func NewTransportValidator() *TransportValidator {
	return &TransportValidator{
		base: NewBaseMCPValidator(),
	}
}

// ValidateTransportMessage validates a transport protocol message.
//
// SPEC: Transport.md, MUST have protocol_id, session_id, sequence, and payload
func (v *TransportValidator) ValidateTransportMessage(data []byte) (*testsmcp.TransportMessage, error) {
	var msg testsmcp.TransportMessage
	if err := json.Unmarshal(data, &msg); err != nil {
		return nil, fmt.Errorf("invalid JSON: %w", err)
	}
	
	if err := v.base.validate.Struct(msg); err != nil {
		return nil, fmt.Errorf("validation failed: %w", err)
	}
	
	// Validate protocol ID
	if msg.ProtocolID != "/mcp+p2p/1.0.0" {
		return nil, fmt.Errorf("invalid protocol_id: must be '/mcp+p2p/1.0.0', got '%s'", msg.ProtocolID)
	}
	
	// Validate that payload is valid JSON
	var payloadCheck interface{}
	if err := json.Unmarshal(msg.Payload, &payloadCheck); err != nil {
		return nil, fmt.Errorf("invalid payload: not valid JSON: %w", err)
	}
	
	return &msg, nil
}

// ValidateSessionInit validates a session initialization message.
//
// SPEC: Transport.md, session init MUST have session_id, protocol_version, and capabilities
func (v *TransportValidator) ValidateSessionInit(data []byte) (*testsmcp.SessionInit, error) {
	var init testsmcp.SessionInit
	if err := json.Unmarshal(data, &init); err != nil {
		return nil, fmt.Errorf("invalid JSON: %w", err)
	}
	
	if err := v.base.validate.Struct(init); err != nil {
		return nil, fmt.Errorf("validation failed: %w", err)
	}
	
	return &init, nil
}
