# MCP++ Specification Compliance Matrix

This document maps test cases to normative requirements from the MCP++ specifications.

## Specification Sources

- `docs/spec/mcp++-profiles-draft.md` - Main profile registry
- `docs/spec/mcp-idl.md` - Profile A: Interface Contracts
- `docs/spec/cid-native-artifacts.md` - Profile B: Execution Artifacts
- `docs/spec/ucan-delegation.md` - Profile C: Capability Delegation
- `docs/spec/temporal-deontic-policy.md` - Profile D: Policy Evaluation
- `docs/spec/event-dag-ordering.md` - Event DAG and Ordering
- `docs/spec/transport-mcp-p2p.md` - Profile E: P2P Transport
- `docs/spec/risk-scheduling.md` - Risk Scoring and Scheduling

## Normative Requirements (MUST/SHOULD/REQUIRED)

### Profile A: MCP-IDL

| Requirement | Spec Location | Test Coverage | Test File |
|-------------|---------------|---------------|-----------|
| Interface Descriptor MUST be canonicalized and content-addressed | mcp++-profiles-draft.md:62 | ✅ | test_mcp_idl.py::test_interface_cid_computation |
| Servers MUST expose interfaces/list | mcp++-profiles-draft.md:82 | ✅ | test_mcp_idl.py::test_interface_list_request |
| Servers MUST expose interfaces/get | mcp++-profiles-draft.md:83 | ✅ | test_mcp_idl.py::test_interface_get_request |
| Servers MUST expose interfaces/compat | mcp++-profiles-draft.md:84 | ✅ | test_mcp_idl.py::test_interface_compat_request |
| Required fields: name, namespace, version, methods, errors, requires, compatibility | mcp-idl.md:44-52 | ✅ | test_mcp_idl.py::test_valid_interface_descriptor |
| Canonicalization MUST be deterministic | mcp-idl.md:32 | ✅ | test_mcp_idl.py::test_interface_cid_computation |
| Methods MUST include input/output schemas | mcp-idl.md:49 | ✅ | test_mcp_idl.py::test_methods_array_validation |
| Toolset slicing with budget (MAY) | mcp++-profiles-draft.md:88 | ✅ | test_mcp_idl.py::test_toolset_select_request |

### Profile B: CID-Native Execution Artifacts

| Requirement | Spec Location | Test Coverage | Test File |
|-------------|---------------|---------------|-----------|
| Envelope MAY wrap MCP invocation | mcp++-profiles-draft.md:96 | ✅ | test_cid_envelopes.py::test_valid_execution_envelope |
| Envelope includes interface_cid, input_cid | mcp++-profiles-draft.md:97-98 | ✅ | test_cid_envelopes.py::test_missing_required_fields |
| Envelope includes parents[] | mcp++-profiles-draft.md:102 | ✅ | test_cid_envelopes.py::test_parents_array_validation |
| Receipts MUST be content-addressed | mcp++-profiles-draft.md:110 | ✅ | test_cid_envelopes.py::test_valid_execution_receipt |
| Receipts MAY be signed | mcp++-profiles-draft.md:110 | ✅ | test_cid_envelopes.py::test_valid_execution_receipt |
| Canonicalization MUST be deterministic | cid-native-artifacts.md:15 | ⚠️ PARTIAL | Need canonicalization pipeline test |
| Decision SHOULD support allow/deny/allow_with_obligations | cid-native-artifacts.md:86 | ❌ MISSING | Need decision validation test |
| Correlation ID SHOULD be carried | cid-native-artifacts.md:118 | ❌ MISSING | Need correlation test |

### Profile C: UCAN Delegation

| Requirement | Spec Location | Test Coverage | Test File |
|-------------|---------------|---------------|-----------|
| Execution-time validation is REQUIRED | mcp++-profiles-draft.md:120 | ⚠️ PARTIAL | Need runtime validation test |
| Invocations MUST reference valid delegation chain | mcp++-profiles-draft.md:125 | ❌ MISSING | Need chain validation test |
| Delegation chains MUST be validated | ucan-delegation.md | ⚠️ PARTIAL | validators/ucan_delegation.py exists but needs tests |
| UCAN tokens MUST include iss, aud, att, exp | ucan-delegation.md | ⚠️ PARTIAL | Validator exists but no integration tests |

### Profile D: Temporal Deontic Policy

| Requirement | Spec Location | Test Coverage | Test File |
|-------------|---------------|---------------|-----------|
| Policies MUST be content-addressed | mcp++-profiles-draft.md:134 | ❌ MISSING | Need policy_cid validation test |
| Policies MUST express permissions/prohibitions/obligations | mcp++-profiles-draft.md:135-137 | ❌ MISSING | Need policy structure test |
| Runtime MUST validate delegation proofs | mcp++-profiles-draft.md:142 | ❌ MISSING | Need runtime validation test |
| Runtime MUST evaluate policy constraints | mcp++-profiles-draft.md:143 | ❌ MISSING | Need constraint evaluation test |
| Runtime MUST emit decision_cid | mcp++-profiles-draft.md:144 | ❌ MISSING | Need decision emission test |
| Decisions MAY spawn obligations with deadlines | mcp++-profiles-draft.md:146 | ❌ MISSING | Need obligation test |
| Temporal constraints | temporal-deontic-policy.md | ⚠️ PARTIAL | Validator exists but needs tests |

### Event DAG and Ordering

| Requirement | Spec Location | Test Coverage | Test File |
|-------------|---------------|---------------|-----------|
| Each event CID MUST commit to specific fields | mcp++-profiles-draft.md:153 | ⚠️ PARTIAL | Need comprehensive event structure test |
| Parent links MUST be immutable and verifiable | event-dag-ordering.md:24 | ❌ MISSING | Need parent immutability test |
| DAG acyclicity | event-dag-ordering.md | ⚠️ PARTIAL | Basic validation exists |
| Causal ordering | event-dag-ordering.md | ⚠️ PARTIAL | Basic validation exists |

### Profile E: Transport (mcp+p2p)

| Requirement | Spec Location | Test Coverage | Test File |
|-------------|---------------|---------------|-----------|
| MUST establish libp2p connection | transport-mcp-p2p.md:56 | ❌ MISSING | Need transport tests |
| MUST open stream with protocol ID | transport-mcp-p2p.md:58 | ❌ MISSING | Need protocol ID test |
| MUST run MCP initialization handshake | transport-mcp-p2p.md:59 | ❌ MISSING | Need handshake test |
| MUST preserve JSON-RPC semantics | transport-mcp-p2p.md:60 | ❌ MISSING | Need semantic preservation test |
| MUST define message framing | transport-mcp-p2p.md:80-82 | ❌ MISSING | Need framing test |
| SHOULD use length-prefixed framing | transport-mcp-p2p.md:86 | ❌ MISSING | Need length-prefix test |

### Baseline MCP Protocol

| Requirement | Spec Location | Test Coverage | Test File |
|-------------|---------------|---------------|-----------|
| JSON-RPC 2.0 format | MCP spec | ✅ | test_mcp_baseline.py::test_valid_tool_call_request |
| Required fields: jsonrpc, id, method | MCP spec | ✅ | test_mcp_baseline.py::test_missing_* |
| tools/call requires name and arguments | MCP spec | ✅ | test_mcp_baseline.py::test_tool_call_missing_name |
| initialize requires protocolVersion, capabilities | MCP spec | ✅ | test_mcp_baseline.py::test_initialize_request |
| Response must have result OR error | MCP spec | ✅ | test_mcp_baseline.py::test_response_with_both_result_and_error |
| Notifications don't have id | MCP spec | ✅ | test_mcp_baseline.py::test_valid_notification |

### Cross-Cutting Requirements

| Requirement | Spec Location | Test Coverage | Test File |
|-------------|---------------|---------------|-----------|
| Backward compatibility with baseline MCP | mcp++-profiles-draft.md:46 | ❌ MISSING | Need compatibility test |
| Capability negotiation during initialization | mcp++-profiles-draft.md:46 | ❌ MISSING | Need negotiation test |
| Content-addressed artifacts MUST be canonicalized | mcp++-profiles-draft.md:162 | ⚠️ PARTIAL | Need comprehensive canonicalization test |
| Authority validation MUST occur at execution-time | mcp++-profiles-draft.md:161 | ❌ MISSING | Need execution-time validation test |

## Coverage Summary

- ✅ **Full Coverage**: 15 requirements
- ⚠️ **Partial Coverage**: 10 requirements
- ❌ **Missing Coverage**: 20 requirements

**Total**: 45 normative requirements identified  
**Coverage**: 33% full, 22% partial, 45% missing

## Priority for Test Enhancement

1. **HIGH PRIORITY** (MUST requirements with missing/partial coverage):
   - Profile C: Delegation chain validation at execution-time
   - Profile D: Policy evaluation runtime requirements
   - Profile E: Transport protocol compliance
   - Cross-cutting: Backward compatibility validation

2. **MEDIUM PRIORITY** (SHOULD requirements):
   - Canonicalization pipeline testing
   - Decision types validation
   - Temporal constraints evaluation

3. **LOW PRIORITY** (MAY requirements and enhancements):
   - Optional features testing
   - Performance benchmarks
   - Extended compatibility matrices

## Next Steps

1. Add missing test cases for HIGH PRIORITY items
2. Enhance existing partial coverage tests
3. Create integration tests for multi-profile scenarios
4. Add negative test cases for invalid payloads
5. Document test-to-spec mapping in test docstrings
