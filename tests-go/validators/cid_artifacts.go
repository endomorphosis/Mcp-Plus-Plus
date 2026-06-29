package validators

import (
	"encoding/json"
	"fmt"

	testsmcp "github.com/endomorphosis/Mcp-Plus-Plus/tests-go"
)

// CIDValidator validates CID Artifacts (Profile B) messages.
//
// SPEC: CID-Artifacts.md § Execution Envelopes and Receipts
// Validates content-addressed execution artifacts with provenance.
type CIDValidator struct {
	base *BaseMCPValidator
}

// NewCIDValidator creates a new CID artifacts validator.
func NewCIDValidator() *CIDValidator {
	return &CIDValidator{
		base: NewBaseMCPValidator(),
	}
}

// ValidateExecutionEnvelope validates an execution envelope.
//
// SPEC: CID-Artifacts.md, MUST have interface_cid, input_cid, and invocation
func (v *CIDValidator) ValidateExecutionEnvelope(data []byte) (*testsmcp.ExecutionEnvelope, error) {
	var envelope testsmcp.ExecutionEnvelope
	if err := json.Unmarshal(data, &envelope); err != nil {
		return nil, fmt.Errorf("invalid JSON: %w", err)
	}
	
	if err := v.base.validate.Struct(envelope); err != nil {
		return nil, fmt.Errorf("validation failed: %w", err)
	}
	
	// Validate CID format
	if err := v.base.validate.Var(envelope.InterfaceCID, "cid"); err != nil {
		return nil, fmt.Errorf("invalid interface_cid format: %w", err)
	}
	if err := v.base.validate.Var(envelope.InputCID, "cid"); err != nil {
		return nil, fmt.Errorf("invalid input_cid format: %w", err)
	}
	
	// Validate parent CIDs
	for i, parent := range envelope.Parents {
		if err := v.base.validate.Var(parent, "cid"); err != nil {
			return nil, fmt.Errorf("invalid parent CID at index %d: %w", i, err)
		}
	}
	
	return &envelope, nil
}

// ValidateExecutionReceipt validates an execution receipt.
//
// SPEC: CID-Artifacts.md, MUST have receipt_cid; success/output_cid de-facto
func (v *CIDValidator) ValidateExecutionReceipt(data []byte) (*testsmcp.ExecutionReceipt, error) {
	var receipt testsmcp.ExecutionReceipt
	if err := json.Unmarshal(data, &receipt); err != nil {
		return nil, fmt.Errorf("invalid JSON: %w", err)
	}
	
	if err := v.base.validate.Struct(receipt); err != nil {
		return nil, fmt.Errorf("validation failed: %w", err)
	}
	
	// Validate CID formats
	if err := v.base.validate.Var(receipt.ReceiptCID, "cid"); err != nil {
		return nil, fmt.Errorf("invalid receipt_cid format: %w", err)
	}
	if receipt.OutputCID != "" {
		if err := v.base.validate.Var(receipt.OutputCID, "cid"); err != nil {
			return nil, fmt.Errorf("invalid output_cid format: %w", err)
		}
	}
	
	return &receipt, nil
}
