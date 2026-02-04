package validators

import (
	"encoding/json"
	"fmt"

	testsmcp "github.com/endomorphosis/Mcp-Plus-Plus/tests-go"
)

// PolicyValidator validates Policy Evaluation (Profile D) messages.
//
// SPEC: Policy-Evaluation.md § Temporal Deontic Policies
// Validates policy descriptors and evaluation decisions.
type PolicyValidator struct {
	base *BaseMCPValidator
}

// NewPolicyValidator creates a new policy evaluation validator.
func NewPolicyValidator() *PolicyValidator {
	return &PolicyValidator{
		base: NewBaseMCPValidator(),
	}
}

// ValidatePolicyDescriptor validates a policy descriptor.
//
// SPEC: Policy-Evaluation.md, MUST have policy_cid, type, and target
func (v *PolicyValidator) ValidatePolicyDescriptor(data []byte) (*testsmcp.PolicyDescriptor, error) {
	var policy testsmcp.PolicyDescriptor
	if err := json.Unmarshal(data, &policy); err != nil {
		return nil, fmt.Errorf("invalid JSON: %w", err)
	}
	
	if err := v.base.validate.Struct(policy); err != nil {
		return nil, fmt.Errorf("validation failed: %w", err)
	}
	
	// Validate policy_cid format
	if err := v.base.validate.Var(policy.PolicyCID, "cid"); err != nil {
		return nil, fmt.Errorf("invalid policy_cid format: %w", err)
	}
	
	// Validate policy type
	validTypes := map[testsmcp.PolicyType]bool{
		testsmcp.PolicyTypePermission:  true,
		testsmcp.PolicyTypeProhibition: true,
		testsmcp.PolicyTypeObligation:  true,
	}
	if !validTypes[policy.Type] {
		return nil, fmt.Errorf("invalid policy type: %s", policy.Type)
	}
	
	return &policy, nil
}

// ValidatePolicyDecision validates a policy decision.
//
// SPEC: Policy-Evaluation.md, MUST have decision_cid, decision, policy_cid, and timestamp
func (v *PolicyValidator) ValidatePolicyDecision(data []byte) (*testsmcp.PolicyDecision, error) {
	var decision testsmcp.PolicyDecision
	if err := json.Unmarshal(data, &decision); err != nil {
		return nil, fmt.Errorf("invalid JSON: %w", err)
	}
	
	if err := v.base.validate.Struct(decision); err != nil {
		return nil, fmt.Errorf("validation failed: %w", err)
	}
	
	// Validate CID formats
	if err := v.base.validate.Var(decision.DecisionCID, "cid"); err != nil {
		return nil, fmt.Errorf("invalid decision_cid format: %w", err)
	}
	if err := v.base.validate.Var(decision.PolicyCID, "cid"); err != nil {
		return nil, fmt.Errorf("invalid policy_cid format: %w", err)
	}
	
	// Validate decision type
	validDecisions := map[testsmcp.DecisionType]bool{
		testsmcp.DecisionAllow:                true,
		testsmcp.DecisionDeny:                 true,
		testsmcp.DecisionAllowWithObligations: true,
	}
	if !validDecisions[decision.Decision] {
		return nil, fmt.Errorf("invalid decision type: %s", decision.Decision)
	}
	
	// If decision is allow_with_obligations, must have obligations
	if decision.Decision == testsmcp.DecisionAllowWithObligations && len(decision.Obligations) == 0 {
		return nil, fmt.Errorf("allow_with_obligations decision must have at least one obligation")
	}
	
	return &decision, nil
}
