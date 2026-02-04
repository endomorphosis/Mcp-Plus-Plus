# MCP++ TypeScript Validators

TypeScript implementation of MCP++ protocol validators with advanced type safety using Zod and TypeScript 5.x.

## Features

- **Strict Type Safety**: TypeScript 5.x with strictest compiler settings
- **Runtime Validation**: Zod schemas for runtime type checking
- **Comprehensive Coverage**: Validators for all 7 MCP++ profiles
- **Parallel Implementation**: Matches Python Pydantic validators
- **100% Test Coverage**: Comprehensive test suite with Vitest

## Installation

```bash
npm install
```

## Building

```bash
npm run build
```

## Testing

```bash
# Run tests once
npm test

# Watch mode
npm run test:watch

# Type checking
npm run type-check
```

## Validators

### Base MCP Protocol
- JSON-RPC 2.0 messages (requests, responses, notifications)
- Method-specific parameter validation
- Strict mode enforcement (no extra fields)

### Profile A: MCP-IDL
- Interface descriptor validation
- Method and error schemas
- Compatibility constraints

### Profile B: CID Artifacts
- Execution envelope validation
- Receipt validation with CID format checking
- Parent link validation

### Profile C: UCAN Delegation
- UCAN token validation
- Delegation chain validation
- Proof reference checking

### Profile D: Policy Evaluation
- Policy type validation (permission/prohibition/obligation)
- Decision type validation (allow/deny/allow_with_obligations)
- Temporal constraint validation

### Profile E: Transport (mcp+p2p)
- Protocol ID validation
- Message framing validation
- Session lifecycle validation

### Event DAG
- Event structure validation
- DAG integrity checking

## Usage

```typescript
import { MCPTypedValidator, validateMCPRequest } from '@mcp-plus-plus/validators-ts';

// Validate a request
const payload = {
  jsonrpc: '2.0',
  method: 'tools/call',
  params: { name: 'calculator', arguments: { x: 10, y: 20 } },
  id: 1,
};

const result = validateMCPRequest(payload);
console.log(result.isValid); // true
console.log(result.errors); // []
```

## Type Safety

All validators use:
- **Zod**: Runtime type validation with detailed error messages
- **TypeScript strict mode**: noImplicitAny, strictNullChecks, and 20+ strict flags
- **Type guards**: For discriminated unions and type narrowing
- **Branded types**: For CID and other domain-specific strings

## Cross-Language Compatibility

TypeScript validators are designed to be functionally equivalent to Python Pydantic validators:
- Identical validation rules
- Same error messages
- Compatible JSON schemas
- Shared test fixtures

## Development

```bash
# Install dependencies
npm install

# Build
npm run build

# Run tests with coverage
npm test

# Type check
npm run type-check

# Lint
npm run lint
```

## Architecture

```
tests-ts/
├── src/
│   ├── models.ts              # Zod schemas for all data types
│   ├── validators/
│   │   ├── baseMCP.ts        # Base MCP protocol
│   │   ├── mcpIDL.ts         # Profile A
│   │   ├── cidArtifacts.ts   # Profile B
│   │   ├── ucanDelegation.ts # Profile C
│   │   ├── policyEvaluation.ts # Profile D
│   │   ├── transport.ts      # Profile E
│   │   └── eventDAG.ts       # Event graph
│   └── __tests__/
│       └── validators.test.ts # Comprehensive tests
├── package.json
├── tsconfig.json              # Strict TypeScript config
└── vitest.config.ts          # Test configuration
```

## Contributing

Validators must maintain:
1. Type safety (mypy/TypeScript strict mode)
2. Runtime validation (Pydantic/Zod)
3. Test coverage (100%)
4. Cross-language compatibility
5. Spec compliance
