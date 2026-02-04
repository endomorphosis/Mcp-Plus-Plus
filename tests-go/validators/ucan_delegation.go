package validators

import (
	"encoding/json"
	"fmt"

	testsmcp "github.com/endomorphosis/Mcp-Plus-Plus/tests-go"
)

// UCANValidator validates UCAN Delegation (Profile C) messages.
//
// SPEC: UCAN-Delegation.md § Capability Chains
// Validates UCAN tokens and delegation chains.
type UCANValidator struct {
	base *BaseMCPValidator
}

// NewUCANValidator creates a new UCAN delegation validator.
func NewUCANValidator() *UCANValidator {
	return &UCANValidator{
		base: NewBaseMCPValidator(),
	}
}

// ValidateUCANToken validates a UCAN token.
//
// SPEC: UCAN-Delegation.md, MUST have iss, aud, att, and exp fields
func (v *UCANValidator) ValidateUCANToken(data []byte) (*testsmcp.UCANToken, error) {
	var token testsmcp.UCANToken
	if err := json.Unmarshal(data, &token); err != nil {
		return nil, fmt.Errorf("invalid JSON: %w", err)
	}
	
	if err := v.base.validate.Struct(token); err != nil {
		return nil, fmt.Errorf("validation failed: %w", err)
	}
	
	// Validate that capabilities list is not empty
	if len(token.Capabilities) == 0 {
		return nil, fmt.Errorf("UCAN token must have at least one capability")
	}
	
	// Validate each capability
	for i, cap := range token.Capabilities {
		if cap.With == "" {
			return nil, fmt.Errorf("capability %d has empty 'with' field", i)
		}
		if cap.Can == "" {
			return nil, fmt.Errorf("capability %d has empty 'can' field", i)
		}
	}
	
	return &token, nil
}

// ValidateDelegationChain validates a delegation chain.
//
// SPEC: UCAN-Delegation.md, chain MUST have root token and optional proofs
func (v *UCANValidator) ValidateDelegationChain(data []byte) (*testsmcp.DelegationChain, error) {
	var chain testsmcp.DelegationChain
	if err := json.Unmarshal(data, &chain); err != nil {
		return nil, fmt.Errorf("invalid JSON: %w", err)
	}
	
	if err := v.base.validate.Struct(chain); err != nil {
		return nil, fmt.Errorf("validation failed: %w", err)
	}
	
	// Validate root token
	rootJSON, _ := json.Marshal(chain.Root)
	if _, err := v.ValidateUCANToken(rootJSON); err != nil {
		return nil, fmt.Errorf("invalid root token: %w", err)
	}
	
	// Validate each proof token
	for i, proof := range chain.Proofs {
		proofJSON, _ := json.Marshal(proof)
		if _, err := v.ValidateUCANToken(proofJSON); err != nil {
			return nil, fmt.Errorf("invalid proof token %d: %w", i, err)
		}
	}
	
	return &chain, nil
}
