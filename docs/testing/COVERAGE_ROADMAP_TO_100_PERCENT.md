# Roadmap to 100% Coverage for All Languages

## Executive Summary

This document provides a comprehensive roadmap to achieve 100% code coverage for TypeScript, Rust, and Go validators, building on the **100% coverage already achieved for Python** (251 tests, 720/720 lines).

## Current Status

| Language | Coverage | Tests | Lines Covered | Lines Uncovered | Status |
|----------|----------|-------|---------------|-----------------|--------|
| **Python** | **100%** | 251 | 720 | 0 | ✅ **COMPLETE** |
| **TypeScript** | 90.36% | 100 | 1163 | 124 | ⚠️ Measured, needs expansion |
| **Rust** | Unknown | 34 | TBD | TBD | ⚠️ Needs measurement |
| **Go** | Unknown | 17 | TBD | TBD | ⚠️ Needs setup + measurement |

## Python - Reference Implementation (100% ✅)

### Achievement
- **100% line coverage** (720/720 lines)
- **10/10 validators at 100%**
- **251 comprehensive tests**
- **0.76s execution time**
- **Zero flaky tests**

### Test Organization (16 files)
1. Base MCP comprehensive tests (~40 tests)
2. MCP-IDL with CID computation (~28 tests)
3. CID Artifacts validation (~15 tests)
4. UCAN Delegation chains (~10 tests)
5. Policy Evaluation (~17 tests)
6. Transport Protocol (~16 tests)
7. Event DAG (~14 tests)
8. Cross-cutting concerns (~10 tests)
9. Type safety tests (~31 tests)
10. Multiple comprehensive coverage test files (~80 tests)

### Coverage Journey
- Initial: 49% (74 tests)
- Final: **100% (251 tests)**
- Improvement: +51 percentage points, +177 tests

---

## TypeScript - 90.36% → 100%

### Current State
- **Overall**: 90.36% coverage (1163/1287 lines)
- **Tests**: 100 (79 passing, 21 failing)
- **Uncovered**: 124 lines

### Per-Validator Coverage

| Validator | Coverage | Uncovered Lines | Priority |
|-----------|----------|-----------------|----------|
| cidArtifacts.ts | **100%** | 0 | ✅ Complete |
| policyEvaluation.ts | **100%** | 0 | ✅ Complete |
| transport.ts | **100%** | 0 | ✅ Complete |
| models.ts | 98.88% | 3 | High |
| eventDAG.ts | 100% (94.28% branches) | 2 branches | High |
| ucanDelegation.ts | 84.8% | 16 | High |
| mcpIDL.ts | 83.56% | 24 | High |
| baseMCP.ts | 76.43% | 81 | **Critical** |

### Uncovered Lines Detail

**baseMCP.ts** (81 lines - PRIORITY 1):
- Lines: 239,241-244,248-249,259-261,265,267,269,275-276,280,282-288,293-298
- Missing: Response validation edge cases, notification handling, tool/resource/prompt list validation
- Tests needed: ~35-40 targeted tests

**mcpIDL.ts** (24 lines - PRIORITY 2):
- Lines: 72-73,90-94,112-113,117-119,122-123,129
- Missing: Parameter validation, interface request handling
- Tests needed: ~12-15 targeted tests

**ucanDelegation.ts** (16 lines - PRIORITY 3):
- Lines: 53-63,76-77,99-100,103-106
- Missing: Delegation chain validation, token field checks
- Tests needed: ~8-10 targeted tests

**models.ts** (3 lines - PRIORITY 4):
- Lines: 27,84,261
- Missing: Some Zod schema validation branches
- Tests needed: ~3-5 targeted tests

**eventDAG.ts** (2 branches - PRIORITY 4):
- Lines: 86,140
- Missing: Edge case branches in cycle detection
- Tests needed: ~2-3 targeted tests

### Roadmap to 100%

#### Phase 1: Fix Failing Tests (21 tests)
**Goal**: Get all 100 existing tests passing

**Actions**:
1. Adjust Zod schemas to accept null params (request validation)
2. Fix response validation for null id
3. Add warning mechanism for notification method prefixes
4. Update envelope/receipt schemas for optional fields
5. Fix policy descriptor/decision schemas
6. Update session lifecycle validation
7. Fix event and DAG validation schemas

**Estimated Time**: 2-3 hours

#### Phase 2: Cover baseMCP.ts (81 lines)
**Goal**: Achieve 100% coverage for baseMCP.ts

**Tests to Add**:
1. Response validation edge cases (~10 tests)
   - Responses with missing jsonrpc
   - Responses with null/undefined id
   - Error responses with invalid error codes
   
2. Notification validation (~8 tests)
   - Notifications without proper method prefix
   - Notifications with id field
   - Invalid notification structures

3. Tool list validation (~6 tests)
   - Empty tool lists
   - Tools with missing required fields
   - Tools with invalid schemas

4. Resource list validation (~6 tests)
   - Empty resource lists
   - Resources with missing uri
   - Resources with invalid schemas

5. Prompt list validation (~5 tests)
   - Empty prompt lists
   - Prompts with missing name
   - Prompts with invalid arguments

**Estimated Time**: 3-4 hours

#### Phase 3: Cover mcpIDL.ts (24 lines)
**Goal**: Achieve 100% coverage for mcpIDL.ts

**Tests to Add**:
1. Interface descriptor validation (~5 tests)
   - Descriptors with missing fields
   - Invalid method lists
   
2. Interface list request (~3 tests)
   - Requests with missing parameters
   - Invalid request structures

3. Interface get/compat requests (~4 tests)
   - Missing interface_cid
   - Invalid parameters

**Estimated Time**: 1-2 hours

#### Phase 4: Cover ucanDelegation.ts (16 lines)
**Goal**: Achieve 100% coverage for ucanDelegation.ts

**Tests to Add**:
1. Delegation token validation (~4 tests)
   - Missing required token fields (iss, aud, att, exp)
   
2. Delegation chain validation (~3 tests)
   - Invalid chain continuity
   
3. Invocation validation (~3 tests)
   - Missing proof_cid
   - Invalid invocation structure

**Estimated Time**: 1-2 hours

#### Phase 5: Cover Remaining Lines (5 lines/branches)
**Goal**: Achieve 100% coverage for models.ts and eventDAG.ts

**Tests to Add**:
1. Model validation edge cases (~3 tests)
2. Event DAG branch coverage (~2 tests)

**Estimated Time**: 30 minutes - 1 hour

### Total Effort Estimate
- **Time**: 8-12 hours of focused work
- **New Tests**: ~60-80 additional tests
- **Final Test Count**: ~160-180 tests
- **Final Coverage**: 100% (1287/1287 lines)

### Verification
```bash
cd tests-ts
npm run test:coverage
# Expected output: 100% coverage across all files
```

---

## Rust - Unknown → 100%

### Current State
- **Tests**: 34 (19 unit + 14 integration + 1 doc)
- **Coverage**: Unknown - needs measurement
- **Status**: All tests passing

### Setup Required

#### Step 1: Install Coverage Tool
```bash
# Option 1: cargo-tarpaulin (Linux only)
cargo install cargo-tarpaulin

# Option 2: cargo-llvm-cov (cross-platform)
cargo install cargo-llvm-cov
```

#### Step 2: Measure Coverage
```bash
cd tests-rs

# Using cargo-tarpaulin
cargo tarpaulin --out Xml --out Html

# Using cargo-llvm-cov
cargo llvm-cov --html
```

### Roadmap to 100%

#### Phase 1: Measure Current Coverage
**Actions**:
1. Install coverage tool
2. Run existing 34 tests with coverage
3. Generate HTML/XML report
4. Identify all uncovered lines
5. Create detailed coverage breakdown

**Estimated Time**: 1 hour

#### Phase 2: Analyze Coverage Gaps
**Actions**:
1. Map uncovered lines to Python's test structure
2. Identify missing test categories
3. Prioritize validators by coverage gaps
4. Create test plan for each validator

**Estimated Time**: 1-2 hours

#### Phase 3: Add Comprehensive Tests
**Goal**: Systematically cover all uncovered lines

**Expected Test Categories** (based on Python):
1. Base MCP tests (~40 tests)
2. MCP-IDL tests (~25 tests)
3. CID Artifacts tests (~15 tests)
4. UCAN Delegation tests (~10 tests)
5. Policy Evaluation tests (~15 tests)
6. Transport Protocol tests (~15 tests)
7. Event DAG tests (~12 tests)
8. Edge case tests (~50 tests)

**Estimated Time**: 8-12 hours
**New Tests**: ~150-180 additional tests
**Final Test Count**: ~200-220 tests

#### Phase 4: Verify 100% Coverage
**Actions**:
1. Run coverage measurement
2. Confirm 100% achievement
3. Document coverage report
4. Ensure all tests pass

**Estimated Time**: 1 hour

### Total Effort Estimate
- **Time**: 11-16 hours
- **New Tests**: ~150-180
- **Final Test Count**: ~200-220 tests
- **Final Coverage**: 100%

---

## Go - Unknown → 100%

### Current State
- **Tests**: 17 (table-driven tests)
- **Coverage**: Unknown - needs setup and measurement
- **Status**: Module setup issues

### Setup Required

#### Step 1: Fix Module Configuration
```bash
cd tests-go
# Fix go.mod
# Ensure proper module path and dependencies
```

#### Step 2: Setup Coverage
```bash
# Run tests with coverage
go test -v -cover ./...

# Generate detailed coverage
go test -v -coverprofile=coverage.out ./...
go tool cover -html=coverage.out -o coverage.html
```

### Roadmap to 100%

#### Phase 1: Fix Setup and Measure Coverage
**Actions**:
1. Fix go.mod configuration
2. Resolve dependency issues
3. Get all 17 tests running
4. Measure current coverage
5. Generate coverage report

**Estimated Time**: 1-2 hours

#### Phase 2: Analyze Coverage Gaps
**Actions**:
1. Identify uncovered lines
2. Map to Python's test structure
3. Create test plan
4. Prioritize validators

**Estimated Time**: 1 hour

#### Phase 3: Add Comprehensive Tests
**Goal**: Achieve 100% coverage following Go best practices

**Expected Test Categories**:
1. Base MCP tests (~35 tests)
2. MCP-IDL tests (~20 tests)
3. CID Artifacts tests (~15 tests)
4. UCAN Delegation tests (~10 tests)
5. Policy Evaluation tests (~12 tests)
6. Transport Protocol tests (~12 tests)
7. Event DAG tests (~10 tests)
8. Edge case tests (~40 tests)

**Test Structure**:
- Table-driven tests for each validator
- Sub-tests for edge cases
- Clear test documentation
- Parallel execution where possible

**Estimated Time**: 8-12 hours
**New Tests**: ~130-160 additional tests
**Final Test Count**: ~150-180 tests

#### Phase 4: Verify 100% Coverage
**Actions**:
1. Run coverage measurement
2. Confirm 100% achievement
3. Generate coverage reports
4. Document results

**Estimated Time**: 1 hour

### Total Effort Estimate
- **Time**: 11-16 hours
- **New Tests**: ~130-160
- **Final Test Count**: ~150-180 tests
- **Final Coverage**: 100%

---

## Summary and Timeline

### Effort Summary

| Language | Current | Target | Time Estimate | New Tests | Priority |
|----------|---------|--------|---------------|-----------|----------|
| Python | ✅ 100% | ✅ 100% | 0 hours | 0 | Done |
| TypeScript | 90.36% | 100% | 8-12 hours | 60-80 | High |
| Rust | Unknown | 100% | 11-16 hours | 150-180 | Medium |
| Go | Unknown | 100% | 11-16 hours | 130-160 | Medium |

### Total Effort
- **Time**: 30-44 hours of focused development
- **New Tests**: 340-420 tests
- **Final Total**: ~750+ tests across all languages
- **Outcome**: 100% coverage for all four languages

### Recommended Sequence
1. **TypeScript** (fastest to complete, already 90%)
2. **Rust** (good foundation with 34 tests)
3. **Go** (needs setup fixes first)

### Success Criteria
- ✅ 100% line coverage for all languages
- ✅ All tests passing
- ✅ Coverage reports generated
- ✅ Documentation complete
- ✅ Consistent validation logic across languages

---

## Methodology

### No Shortcuts Approach

For each language:

1. **Measure Properly**
   - Use proper coverage tools
   - Generate detailed reports
   - Identify every uncovered line

2. **Analyze Thoroughly**
   - Map uncovered lines to functionality
   - Reference Python's comprehensive tests
   - Create detailed test plans

3. **Test Comprehensively**
   - Add targeted test for each uncovered line
   - Include edge cases and error paths
   - Match Python's validation patterns

4. **Verify Rigorously**
   - Run coverage repeatedly
   - Ensure 100% achievement
   - Confirm all tests pass
   - Document results

### Quality Standards

- Line coverage: 100%
- Branch coverage: 95%+
- Function coverage: 95%+
- All tests passing
- Zero flaky tests
- Fast execution (<2s per language)

---

## Documentation

### Per-Language Coverage Reports

Each language will have:
1. Coverage measurement output
2. Detailed uncovered line analysis
3. Test distribution breakdown
4. Achievement documentation

### Cross-Language Consistency

- Validation logic matches across all languages
- Test scenarios consistent
- Coverage standards uniform
- Documentation complete

---

## Conclusion

This roadmap provides a **systematic, no-shortcuts path** to achieving 100% code coverage for TypeScript, Rust, and Go validators, matching Python's industry-leading 100% coverage.

**Current Status**:
- ✅ Python: 100% COMPLETE
- ⚠️ TypeScript: 90.36%, clear path to 100%
- ⚠️ Rust: Needs measurement, estimated 11-16 hours
- ⚠️ Go: Needs setup + measurement, estimated 11-16 hours

**Total Work Required**: 30-44 hours to achieve 100% across all languages.

**No shortcuts. Comprehensive coverage. Production-ready quality.**
