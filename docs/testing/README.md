# Testing and coverage status (authoritative)

**Status:** Current testing honesty guide (MCP++ 1.0 gap-closure)  
**Task:** MCPP-079 · Goal `MCPP-G170` · Bundle `mcplusplus/1.0/docs-stale-claims`  
**Interfaces:** `DocumentationHonestyReceipt@1`  
**Document class:** **reference** (measurement index) — **not** production admission

This directory indexes how validators and harnesses are tested. **Only this
README** (plus cited baseline receipts / generated CI artifacts) is the
authoritative source for coverage and readiness claims in this tree.

Historical files that once claimed full line coverage, “validation complete”, or
readiness for production deployment remain on disk for audit trail only. They
are marked **HISTORICAL / NON-AUTHORITATIVE** and must not be cited as current
evidence.

---

## 1. Policy (fail-closed)

1. **Do not claim 100% coverage** unless a current, named CI or baseline
   artifact measures that exact percentage for the same scope and metric.
2. **Do not claim production readiness** unless a named admission artifact
   proves production admission at the claimed conformance level
   (ADR-0003 ladder: structural → canonical → cryptographic → policy-enforced →
   receipt-signed → proof-verified).
3. **Green structural suites are not production evidence.** Field-presence
   validators for Profiles C/D remain structural-only even when well covered.
4. **Static trophy markdown is observation-only.** Files under this directory
   that predate MCPP-079 are not recomputed measurements.
5. Prefer recomputed commands bound in baseline receipts over any on-disk
   `coverage.html`, `coverage.out`, or `*COVERAGE*100*` narrative.

Forbidden promotion phrases (unless a current automated artifact proves the
exact claim) include readiness-for-production language, “zero vulnerabilities”,
“fully conformant”, “zero knowledge”, unqualified full-coverage percentages,
and “validation complete” used as production status.

---

## 2. Current measured evidence (baseline receipts)

Measurements below are copied from the MCP++ 1.0 gap-closure baseline forest
(MCPP-002…005 / MCPP-012). Re-run the declared commands and update this table
when new receipts or CI artifacts replace them.

| Language | Declared validation command | Suite result | Coverage status | Evidence |
| --- | --- | --- | --- | --- |
| **Python** | `cd ipfs_accelerate_py/mcplusplus && python -m pytest -q tests-py --maxfail=1` | **323 passed** | **~96.1%** statement coverage of `tests-py/validators` (1184/1232); **not** 100% | `docs/reports/mcplusplus-1.0-gap-closure/baseline/mcpplusplus-python.json` |
| **TypeScript** | `cd ipfs_accelerate_py/mcplusplus/tests-ts && npm test` | **223 passed**, **19 skipped**; disabled suite `comprehensive.test.ts.disabled` listed as skipped/disabled, **not** as pass | Supplemental `npm run test:coverage`: **~98.1%** statements / lines; **not** 100% | `docs/reports/mcplusplus-1.0-gap-closure/baseline/mcpplusplus-typescript.json` |
| **Go** | `cd ipfs_accelerate_py/mcplusplus/tests-go && go test ./...` | **211 passed** | Fresh coverprofile: **~96.9%** statements overall (250/258); validators package **~97.6%**; on-disk `coverage.html` / static `*COVERAGE*.md` **rejected** as current evidence | `docs/reports/mcplusplus-1.0-gap-closure/baseline/mcpplusplus-go.json` |
| **Rust** | `cd ipfs_accelerate_py/mcplusplus/tests-rs && cargo test` | **191 passed** | Coverage **unavailable** in baseline (tooling not installed). `COVERAGE_100_PERCENT_ACHIEVED.md` cited **only as stale**, never as measured result | `docs/reports/mcplusplus-1.0-gap-closure/baseline/mcpplusplus-rust.json` |

**Interpretation:** four-language Mcp-Plus-Plus validator suites are green at
the **structural / codec** layer. That is inventory for gap-closure, **not**
cryptographic, policy-enforced, or production admission of Profiles A–H.

Traceability matrix (requirement → evidence):  
[../roadmap/mcplusplus-1.0-gap-closure.md](../roadmap/mcplusplus-1.0-gap-closure.md)

---

## 3. How to remeasure

```bash
# Python (declared gate)
cd ipfs_accelerate_py/mcplusplus && python -m pytest -q tests-py --maxfail=1

# TypeScript (declared gate)
cd ipfs_accelerate_py/mcplusplus/tests-ts && npm test
# Optional supplemental coverage (not the declared gate alone):
# npm run test:coverage

# Go (declared gate)
cd ipfs_accelerate_py/mcplusplus/tests-go && go test ./...
# Optional coverage (write a fresh profile; do not treat checked-in coverage.html as current):
# go test ./... -coverprofile=/tmp/mcpp-go.out -covermode=set
# go tool cover -func=/tmp/mcpp-go.out

# Rust (declared gate)
cd ipfs_accelerate_py/mcplusplus/tests-rs && cargo test
# Coverage only when tooling is present; absence means "unavailable", not 100%.
```

When multi-language CI lands (MCPP-080), prefer generated workflow artifacts
over manual baseline JSON if the artifact is newer and binds the same command.

---

## 4. Historical documents (retained, non-authoritative)

Conflict policy (MCPP-079): **do not delete** these files without preserving
history. Each file below begins with a **HISTORICAL / NON-AUTHORITATIVE**
banner and must not be used to claim 100% coverage or production readiness.

| File | Former claim pattern (historical only) |
| --- | --- |
| [FINAL_100_PERCENT_COVERAGE_SUMMARY.md](FINAL_100_PERCENT_COVERAGE_SUMMARY.md) | Claimed near-perfect multi-language line coverage and mission complete |
| [FINAL_COVERAGE_ACHIEVEMENT.md](FINAL_COVERAGE_ACHIEVEMENT.md) | Claimed mission complete and readiness for production deployment |
| [FINAL_VERIFICATION.txt](FINAL_VERIFICATION.txt) | Claimed verification complete / perfect coverage table |
| [VERIFICATION_COMPLETE.md](VERIFICATION_COMPLETE.md) | Claimed full coverage and full pass rate as readiness evidence |
| [MULTI_LANGUAGE_VALIDATION_COMPLETE.md](MULTI_LANGUAGE_VALIDATION_COMPLETE.md) | Claimed multi-language complete; Python as 100% reference |
| [VALIDATION_TESTING_COMPLETE.md](VALIDATION_TESTING_COMPLETE.md) | Claimed readiness for production; internally inconsistent percentages |
| [VALIDATION_TESTING_SUMMARY.md](VALIDATION_TESTING_SUMMARY.md) | Validation complete narrative |
| [VALIDATION_STATUS_SUMMARY.md](VALIDATION_STATUS_SUMMARY.md) | Status framing that implied readiness for production |
| [VALIDATOR_TESTING_FINAL_STATUS.md](VALIDATOR_TESTING_FINAL_STATUS.md) | Final status framing with claimed full Python line coverage |
| [CURRENT_COVERAGE_STATUS.md](CURRENT_COVERAGE_STATUS.md) | Snapshot that contradicts later “final complete” peers |
| [COVERAGE_ROADMAP_TO_100_PERCENT.md](COVERAGE_ROADMAP_TO_100_PERCENT.md) | Roadmap to full coverage while other docs claimed already done |
| [TESTING_SUMMARY.md](TESTING_SUMMARY.md) | Summary complete tone with readiness implications |

Per-language trophies **outside** this directory (e.g.
`tests-py/COVERAGE_100_PERCENT.md`, `tests-rs/COVERAGE_100_PERCENT_ACHIEVED.md`,
`tests-go/validators/COVERAGE_89_6_PERCENT_FINAL.md`) are likewise
observation-only; they are inventoried in the gap-closure baseline profile
inventory §10 and are not current measurement authority.

---

## 5. Operational harness docs (not coverage trophies)

These describe specific harnesses or measured runs. They do not authorize
global full-coverage percentages or whole-project production admission.

| Path | Role |
| --- | --- |
| [profile-g-three-peer-conformance.md](profile-g-three-peer-conformance.md) | Profile G three-peer harness requirements |
| [profile-g-performance/](profile-g-performance/) | Performance run artifacts |
| [profile-g-release/](profile-g-release/) | Release evidence bundle for Profile G work |

Treat any numeric pass/fail or performance numbers in those trees as scoped to
that harness and date, not as program-wide production admission.

---

## 6. Related surfaces

| Surface | Path |
| --- | --- |
| Project README (no unproven 100% / production claims) | [../../README.md](../../README.md) |
| Contributing / local test commands | [../../CONTRIBUTING.md](../../CONTRIBUTING.md) |
| Architecture honesty rules | [../architecture/overview.md](../architecture/overview.md) |
| Requirement → evidence matrix | [../roadmap/mcplusplus-1.0-gap-closure.md](../roadmap/mcplusplus-1.0-gap-closure.md) |
| Test implementations | `../../tests-py/`, `../../tests-ts/`, `../../tests-go/`, `../../tests-rs/` |

---

## 7. Documentation honesty receipt (MCPP-079)

| Field | Value |
| --- | --- |
| Schema | `DocumentationHonestyReceipt@1` |
| Task | MCPP-079 |
| Current authority | this README + baseline receipts listed in §2 |
| Claims of full (100%) coverage | **absent** from current authority (measured values below 100% or unavailable) |
| Claims of production readiness | **absent** from current authority |
| Historical trophy docs | retained and banner-marked (§4); not evidence |
| Supersedes | any pre-MCPP-079 perfect / complete / readiness-for-production framing in this directory |
