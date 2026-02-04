package validators

import (
	"encoding/json"
	"fmt"

	testsmcp "github.com/endomorphosis/Mcp-Plus-Plus/tests-go"
)

// EventDAGValidator validates Event DAG messages.
//
// SPEC: Event-DAG.md § Provenance Graphs
// Validates event structures and DAG properties (acyclicity, causality).
type EventDAGValidator struct {
	base *BaseMCPValidator
}

// NewEventDAGValidator creates a new event DAG validator.
func NewEventDAGValidator() *EventDAGValidator {
	return &EventDAGValidator{
		base: NewBaseMCPValidator(),
	}
}

// ValidateEvent validates a single event.
//
// SPEC: Event-DAG.md, MUST have event_cid, type, timestamp, and action
func (v *EventDAGValidator) ValidateEvent(data []byte) (*testsmcp.Event, error) {
	var event testsmcp.Event
	if err := json.Unmarshal(data, &event); err != nil {
		return nil, fmt.Errorf("invalid JSON: %w", err)
	}
	
	if err := v.base.validate.Struct(event); err != nil {
		return nil, fmt.Errorf("validation failed: %w", err)
	}
	
	// Validate event_cid format
	if err := v.base.validate.Var(event.EventCID, "cid"); err != nil {
		return nil, fmt.Errorf("invalid event_cid format: %w", err)
	}
	
	// Validate parent CIDs
	for i, parent := range event.Parents {
		if err := v.base.validate.Var(parent, "cid"); err != nil {
			return nil, fmt.Errorf("invalid parent CID at index %d: %w", i, err)
		}
	}
	
	return &event, nil
}

// ValidateEventDAG validates an event DAG structure.
//
// SPEC: Event-DAG.md, MUST be acyclic and have at least one root
func (v *EventDAGValidator) ValidateEventDAG(data []byte) (*testsmcp.EventDAG, error) {
	var dag testsmcp.EventDAG
	if err := json.Unmarshal(data, &dag); err != nil {
		return nil, fmt.Errorf("invalid JSON: %w", err)
	}
	
	if err := v.base.validate.Struct(dag); err != nil {
		return nil, fmt.Errorf("validation failed: %w", err)
	}
	
	// Validate that all root CIDs exist in events
	for _, rootCID := range dag.Roots {
		if _, exists := dag.Events[rootCID]; !exists {
			return nil, fmt.Errorf("root CID %s not found in events", rootCID)
		}
	}
	
	// Validate that all parent references exist
	for eventCID, event := range dag.Events {
		for _, parentCID := range event.Parents {
			if _, exists := dag.Events[parentCID]; !exists {
				return nil, fmt.Errorf("event %s references non-existent parent %s", eventCID, parentCID)
			}
		}
	}
	
	// Check for cycles using DFS
	if err := v.checkForCycles(&dag); err != nil {
		return nil, fmt.Errorf("DAG validation failed: %w", err)
	}
	
	return &dag, nil
}

// checkForCycles performs cycle detection using depth-first search.
func (v *EventDAGValidator) checkForCycles(dag *testsmcp.EventDAG) error {
	visited := make(map[string]bool)
	recStack := make(map[string]bool)
	
	var dfs func(string) error
	dfs = func(eventCID string) error {
		visited[eventCID] = true
		recStack[eventCID] = true
		
		event := dag.Events[eventCID]
		for _, parentCID := range event.Parents {
			if !visited[parentCID] {
				if err := dfs(parentCID); err != nil {
					return err
				}
			} else if recStack[parentCID] {
				return fmt.Errorf("cycle detected involving event %s", parentCID)
			}
		}
		
		recStack[eventCID] = false
		return nil
	}
	
	// Check from all roots
	for _, rootCID := range dag.Roots {
		if !visited[rootCID] {
			if err := dfs(rootCID); err != nil {
				return err
			}
		}
	}
	
	return nil
}
