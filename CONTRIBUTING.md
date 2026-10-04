# Contributing to MCP++

Thank you for your interest in contributing to MCP++! This guide will help you get started.

## Table of Contents

1. [Code of Conduct](#code-of-conduct)
2. [Getting Started](#getting-started)
3. [Development Setup](#development-setup)
4. [Making Changes](#making-changes)
5. [Testing](#testing)
6. [Documentation](#documentation)
7. [Pull Request Process](#pull-request-process)
8. [Style Guide](#style-guide)

## Code of Conduct

### Our Pledge

We pledge to make participation in our project a harassment-free experience for everyone, regardless of age, body size, disability, ethnicity, gender identity and expression, level of experience, nationality, personal appearance, race, religion, or sexual identity and orientation.

### Our Standards

**Positive behaviors:**
- Using welcoming and inclusive language
- Being respectful of differing viewpoints
- Gracefully accepting constructive criticism
- Focusing on what is best for the community
- Showing empathy towards other community members

**Unacceptable behaviors:**
- Trolling, insulting/derogatory comments, and personal attacks
- Public or private harassment
- Publishing others' private information without permission
- Other conduct which could reasonably be considered inappropriate

## Getting Started

### Prerequisites

- Python 3.10+ or Node.js 18+ or Java 17+
- Git
- Familiarity with MCP concepts (see [Getting Started](GETTING_STARTED.md))

### Finding Issues to Work On

1. Check the [Issues](https://github.com/endomorphosis/Mcp-/issues) page
2. Look for issues labeled `good first issue` or `help wanted`
3. Comment on the issue to let others know you're working on it
4. If you have a new idea, create an issue first to discuss it

## Development Setup

### Fork and Clone

```bash
# Fork the repository on GitHub, then clone your fork
git clone https://github.com/YOUR_USERNAME/Mcp-.git
cd Mcp-

# Add upstream remote
git remote add upstream https://github.com/endomorphosis/Mcp-.git
```

### Python Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install
```

### TypeScript Setup

```bash
# Install dependencies
npm install

# Install development dependencies
npm install --save-dev

# Build the project
npm run build
```

### Java Setup

```bash
# Build with Maven
mvn clean install

# Or with Gradle
./gradlew build
```

## Making Changes

### Branch Naming

Create a descriptive branch name:

```bash
git checkout -b feature/add-new-tool
git checkout -b fix/authentication-bug
git checkout -b docs/update-api-reference
```

**Branch naming conventions:**
- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation changes
- `refactor/` - Code refactoring
- `test/` - Test additions or changes

### Commit Messages

Write clear, descriptive commit messages:

```
type: Short description (50 chars or less)

More detailed explanation if needed. Wrap at 72 characters.
Explain the problem this commit solves and why you chose
this solution.

Fixes #123
```

**Commit types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

**Examples:**
```bash
feat: Add rate limiting to tool execution

Implements a token bucket algorithm for rate limiting tool calls.
This prevents abuse and ensures fair usage across clients.

Fixes #45

---

fix: Prevent SQL injection in resource queries

Use parameterized queries instead of string concatenation.
Added input validation and tests.

Closes #67

---

docs: Update Getting Started guide with TypeScript examples

Added complete TypeScript examples for server and client.
Includes explanations of key concepts.
```

### Keep Changes Focused

- One feature/fix per pull request
- Keep pull requests small and focused
- Large changes should be discussed in an issue first

## Testing

### Running Tests

**Python:**
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=mcp --cov-report=html

# Run specific test file
pytest tests/test_server.py

# Run specific test
pytest tests/test_server.py::test_tool_execution
```

**TypeScript:**
```bash
# Run all tests
npm test

# Run with coverage
npm run test:coverage

# Run in watch mode
npm run test:watch
```

**Java:**
```bash
# Maven
mvn test

# Gradle
./gradlew test
```

### Writing Tests

#### Test Structure

```python
# test_weather_server.py
import pytest
from weather_server import WeatherServer

@pytest.fixture
def server():
    """Create a test server instance."""
    return WeatherServer()

@pytest.mark.asyncio
async def test_get_temperature_success(server):
    """Test successful temperature retrieval."""
    # Arrange
    location = "San Francisco"
    
    # Act
    result = await server.get_temperature(location)
    
    # Assert
    assert result.location == location
    assert isinstance(result.temperature, float)
    assert result.temperature > -100  # Sanity check

@pytest.mark.asyncio
async def test_get_temperature_invalid_location(server):
    """Test error handling for invalid location."""
    # Arrange
    location = ""
    
    # Act & Assert
    with pytest.raises(ValueError, match="Invalid location"):
        await server.get_temperature(location)
```

#### Test Coverage

Aim for:
- 80%+ code coverage overall
- 100% coverage for critical security functions
- All edge cases covered
- Both success and failure paths tested

#### Integration Tests

```python
@pytest.mark.integration
async def test_full_client_server_flow():
    """Test complete client-server interaction."""
    # Start server
    async with create_test_server() as server:
        # Create client
        client = create_test_client(server.address)
        
        # Test initialization
        await client.initialize()
        
        # Test tool listing
        tools = await client.list_tools()
        assert len(tools) > 0
        
        # Test tool execution
        result = await client.call_tool("get_temperature", {
            "location": "Tokyo"
        })
        assert "Tokyo" in result.content[0].text
```

### Performance Tests

```python
import time
import asyncio

@pytest.mark.performance
async def test_tool_execution_latency():
    """Test tool execution completes within acceptable time."""
    server = WeatherServer()
    
    start = time.time()
    await server.get_temperature("New York")
    duration = time.time() - start
    
    assert duration < 1.0, f"Tool took {duration}s (should be < 1s)"

@pytest.mark.performance
async def test_concurrent_tool_calls():
    """Test handling of concurrent tool calls."""
    server = WeatherServer()
    locations = ["NYC", "LA", "Chicago", "Houston", "Phoenix"]
    
    start = time.time()
    results = await asyncio.gather(*[
        server.get_temperature(loc) for loc in locations
    ])
    duration = time.time() - start
    
    assert len(results) == len(locations)
    assert duration < 2.0, f"Concurrent calls took {duration}s"
```

## Documentation

### Code Documentation

**Python:**
```python
def get_temperature(location: str, unit: str = "celsius") -> float:
    """Get current temperature for a location.
    
    Args:
        location: City name or coordinates (e.g., "San Francisco" or "37.7749,-122.4194")
        unit: Temperature unit, either "celsius" or "fahrenheit"
    
    Returns:
        Current temperature as a float
    
    Raises:
        ValueError: If location is invalid or unit is not supported
        ConnectionError: If weather API is unreachable
    
    Example:
        >>> temp = get_temperature("San Francisco", "fahrenheit")
        >>> print(f"Temperature: {temp}°F")
        Temperature: 72.5°F
    """
    pass
```

**TypeScript:**
```typescript
/**
 * Get current temperature for a location
 * 
 * @param location - City name or coordinates
 * @param unit - Temperature unit ("celsius" or "fahrenheit")
 * @returns Current temperature
 * @throws {Error} If location is invalid
 * 
 * @example
 * ```typescript
 * const temp = await getTemperature("San Francisco", "fahrenheit");
 * console.log(`Temperature: ${temp}°F`);
 * ```
 */
async function getTemperature(
  location: string,
  unit: "celsius" | "fahrenheit" = "celsius"
): Promise<number> {
  // Implementation
}
```

### Updating Documentation

When making changes:

1. Update relevant `.md` files
2. Add code examples if introducing new features
3. Update API reference for API changes
4. Add migration guide for breaking changes

### Documentation Standards

- Use clear, simple language
- Provide code examples
- Include expected outputs
- Link to related documentation
- Keep examples up to date

## Pull Request Process

### Before Submitting

- [ ] Code follows style guide
- [ ] All tests pass
- [ ] New tests added for new features
- [ ] Documentation updated
- [ ] Commit messages are clear
- [ ] Branch is up to date with main

### Submitting a Pull Request

1. **Push your branch:**
   ```bash
   git push origin feature/your-feature-name
   ```

2. **Create pull request on GitHub:**
   - Click "New Pull Request"
   - Select your branch
   - Fill out the PR template

3. **PR Description Template:**
   ```markdown
   ## Description
   Brief description of the changes
   
   ## Type of Change
   - [ ] Bug fix
   - [ ] New feature
   - [ ] Breaking change
   - [ ] Documentation update
   
   ## Related Issues
   Fixes #123
   Related to #456
   
   ## Testing
   Describe the testing you've done
   
   ## Checklist
   - [ ] Tests pass locally
   - [ ] Added new tests
   - [ ] Updated documentation
   - [ ] Followed style guide
   - [ ] No breaking changes (or documented)
   ```

### Review Process

1. Automated checks run (tests, linting, coverage)
2. At least one maintainer reviews your code
3. Address feedback and make changes
4. Once approved, a maintainer will merge

### After Merge

1. Delete your feature branch
2. Update your local main branch:
   ```bash
   git checkout main
   git pull upstream main
   ```

## Style Guide

### Python

Follow [PEP 8](https://pep8.org/) and use type hints:

```python
from typing import Optional, List, Dict

async def process_data(
    items: List[str],
    config: Optional[Dict[str, any]] = None
) -> Dict[str, any]:
    """Process a list of items with optional configuration."""
    config = config or {}
    
    results = []
    for item in items:
        result = await process_item(item, config)
        results.append(result)
    
    return {"results": results, "count": len(results)}
```

**Tools:**
- Use `black` for formatting
- Use `isort` for import sorting
- Use `mypy` for type checking
- Use `pylint` for linting

### TypeScript

Follow common TypeScript conventions:

```typescript
interface ProcessConfig {
  maxRetries: number;
  timeout: number;
}

async function processData(
  items: string[],
  config?: ProcessConfig
): Promise<{ results: any[]; count: number }> {
  const actualConfig = config || { maxRetries: 3, timeout: 5000 };
  
  const results = await Promise.all(
    items.map(item => processItem(item, actualConfig))
  );
  
  return { results, count: results.length };
}
```

**Tools:**
- Use `prettier` for formatting
- Use `eslint` for linting
- Enable strict mode in `tsconfig.json`

### Java

Follow Java conventions and use modern features:

```java
public class DataProcessor {
    private final ProcessConfig config;
    
    public DataProcessor(ProcessConfig config) {
        this.config = Objects.requireNonNull(config, "config cannot be null");
    }
    
    public CompletableFuture<ProcessResult> processData(List<String> items) {
        return CompletableFuture.supplyAsync(() -> {
            List<String> results = items.stream()
                .map(this::processItem)
                .collect(Collectors.toList());
            
            return new ProcessResult(results);
        });
    }
}
```

### General Guidelines

1. **Naming:**
   - Use descriptive names
   - Avoid abbreviations
   - Be consistent with existing code

2. **Functions:**
   - Keep functions small and focused
   - One responsibility per function
   - Use descriptive names

3. **Comments:**
   - Explain why, not what
   - Keep comments up to date
   - Use documentation strings

4. **Error Handling:**
   - Handle errors explicitly
   - Provide helpful error messages
   - Log errors appropriately

## Getting Help

- **Documentation:** Check [README](README.md) and other docs
- **Issues:** Search existing issues or create a new one
- **Discussions:** Use [GitHub Discussions](https://github.com/endomorphosis/Mcp-/discussions)
- **Email:** Contact maintainers at [maintainers@example.com](mailto:maintainers@example.com)

## Recognition

Contributors are recognized in:
- [CONTRIBUTORS.md](CONTRIBUTORS.md) file
- Release notes
- Project documentation

Thank you for contributing to MCP++! 🎉

---

Previous: [Security](SECURITY.md)
