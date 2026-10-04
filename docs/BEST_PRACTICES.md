# MCP Best Practices

Production-ready guidelines for implementing and deploying Model Context Protocol servers and clients.

## Table of Contents

1. [Server Design](#server-design)
2. [Security](#security)
3. [Performance](#performance)
4. [Error Handling](#error-handling)
5. [Testing](#testing)
6. [Monitoring](#monitoring)
7. [Deployment](#deployment)

## Server Design

### Single Responsibility Principle

Each server should focus on one specific domain or service.

✅ **Good:**
```python
# weather_server.py - Only weather functionality
@server.list_tools()
async def list_tools():
    return [
        Tool(name="get_temperature", ...),
        Tool(name="get_forecast", ...),
        Tool(name="get_alerts", ...)
    ]
```

❌ **Bad:**
```python
# everything_server.py - Too many responsibilities
@server.list_tools()
async def list_tools():
    return [
        Tool(name="get_temperature", ...),
        Tool(name="send_email", ...),
        Tool(name="query_database", ...),
        Tool(name="process_payment", ...)
    ]
```

### Clear Tool Definitions

Provide comprehensive descriptions and schemas:

```python
Tool(
    name="search_documents",
    description="Search through company documents using keywords. Returns top 10 most relevant documents with excerpts.",
    inputSchema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query keywords",
                "minLength": 1,
                "maxLength": 200
            },
            "filters": {
                "type": "object",
                "properties": {
                    "date_from": {
                        "type": "string",
                        "format": "date",
                        "description": "Start date (YYYY-MM-DD)"
                    },
                    "date_to": {
                        "type": "string",
                        "format": "date",
                        "description": "End date (YYYY-MM-DD)"
                    },
                    "document_type": {
                        "type": "string",
                        "enum": ["pdf", "docx", "txt", "markdown"],
                        "description": "Filter by document type"
                    }
                }
            },
            "max_results": {
                "type": "integer",
                "minimum": 1,
                "maximum": 100,
                "default": 10,
                "description": "Maximum number of results to return"
            }
        },
        "required": ["query"]
    }
)
```

### Resource Organization

Structure resources hierarchically:

```python
# Good resource URI structure
"file:///projects/project-1/documents/report.pdf"
"file:///projects/project-1/data/metrics.csv"
"file:///projects/project-2/documents/proposal.docx"

# Allows for easy filtering and discovery
async def list_resources(uri_pattern: str = None):
    if uri_pattern:
        resources = filter_resources(uri_pattern)
    else:
        resources = all_resources()
    return resources
```

### Versioning

Include version information:

```python
server = Server(
    name="document-server",
    version="2.1.0"  # Semantic versioning
)

# Support multiple API versions if needed
@server.call_tool()
async def call_tool(name: str, arguments: dict, version: str = "2.0"):
    if version == "1.0":
        return await call_tool_v1(name, arguments)
    elif version == "2.0":
        return await call_tool_v2(name, arguments)
    else:
        raise ValueError(f"Unsupported version: {version}")
```

## Security

### Authentication

Always authenticate clients:

```python
from mcp.server.auth import BearerAuth

server = Server(
    name="secure-server",
    auth=BearerAuth(
        token_validator=validate_token
    )
)

async def validate_token(token: str) -> bool:
    """Validate bearer token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload.get("exp", 0) > time.time()
    except jwt.InvalidTokenError:
        return False
```

### Authorization

Implement granular permissions:

```python
from enum import Enum

class Permission(Enum):
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    ADMIN = "admin"

class AuthContext:
    def __init__(self, user_id: str, permissions: set[Permission]):
        self.user_id = user_id
        self.permissions = permissions
    
    def has_permission(self, permission: Permission) -> bool:
        return permission in self.permissions

@server.call_tool()
async def call_tool(name: str, arguments: dict, context: AuthContext):
    # Check permissions before execution
    if name == "delete_document":
        if not context.has_permission(Permission.WRITE):
            raise PermissionError("Write permission required")
    
    return await execute_tool(name, arguments)
```

### Input Validation

Validate all inputs rigorously:

```python
from jsonschema import validate, ValidationError
import re

def validate_tool_input(schema: dict, arguments: dict) -> None:
    """Validate tool arguments against schema."""
    try:
        validate(instance=arguments, schema=schema)
    except ValidationError as e:
        raise ValueError(f"Invalid input: {e.message}")

def sanitize_string(value: str, max_length: int = 1000) -> str:
    """Sanitize string input."""
    # Remove null bytes
    value = value.replace('\x00', '')
    
    # Limit length
    if len(value) > max_length:
        raise ValueError(f"Input too long (max {max_length} characters)")
    
    # Remove potentially dangerous characters for file paths
    if '..' in value or value.startswith('/'):
        raise ValueError("Invalid characters in input")
    
    return value

def validate_email(email: str) -> str:
    """Validate email format."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email):
        raise ValueError("Invalid email format")
    return email
```

### Secrets Management

Never hardcode secrets:

```python
import os
from dotenv import load_dotenv

# Load from environment
load_dotenv()

API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise ValueError("API_KEY environment variable not set")

# Use a secrets manager in production
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential

def get_secret(secret_name: str) -> str:
    """Retrieve secret from Azure Key Vault."""
    credential = DefaultAzureCredential()
    client = SecretClient(
        vault_url="https://your-vault.vault.azure.net/",
        credential=credential
    )
    return client.get_secret(secret_name).value
```

### Rate Limiting

Protect against abuse:

```python
from collections import defaultdict
from datetime import datetime, timedelta
import asyncio

class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window = timedelta(seconds=window_seconds)
        self.requests = defaultdict(list)
    
    async def check_limit(self, client_id: str) -> bool:
        """Check if client has exceeded rate limit."""
        now = datetime.now()
        
        # Clean old requests
        self.requests[client_id] = [
            req_time for req_time in self.requests[client_id]
            if now - req_time < self.window
        ]
        
        # Check limit
        if len(self.requests[client_id]) >= self.max_requests:
            return False
        
        self.requests[client_id].append(now)
        return True

# Usage
rate_limiter = RateLimiter(max_requests=100, window_seconds=60)

@server.call_tool()
async def call_tool(name: str, arguments: dict, client_id: str):
    if not await rate_limiter.check_limit(client_id):
        raise Exception("Rate limit exceeded")
    
    return await execute_tool(name, arguments)
```

## Performance

### Async/Await Patterns

Use async properly:

```python
# ✅ Good - Concurrent execution
async def fetch_multiple_resources(uris: list[str]):
    tasks = [fetch_resource(uri) for uri in uris]
    return await asyncio.gather(*tasks)

# ❌ Bad - Sequential execution
async def fetch_multiple_resources_slow(uris: list[str]):
    results = []
    for uri in uris:
        result = await fetch_resource(uri)
        results.append(result)
    return results
```

### Caching

Cache expensive operations:

```python
from functools import lru_cache
from datetime import datetime, timedelta

class CacheEntry:
    def __init__(self, value, expires_at: datetime):
        self.value = value
        self.expires_at = expires_at
    
    def is_expired(self) -> bool:
        return datetime.now() > self.expires_at

class AsyncCache:
    def __init__(self):
        self.cache = {}
    
    async def get_or_fetch(self, key: str, fetch_func, ttl_seconds: int = 300):
        """Get from cache or fetch if expired."""
        entry = self.cache.get(key)
        
        if entry and not entry.is_expired():
            return entry.value
        
        # Fetch new value
        value = await fetch_func()
        expires_at = datetime.now() + timedelta(seconds=ttl_seconds)
        self.cache[key] = CacheEntry(value, expires_at)
        
        return value

# Usage
cache = AsyncCache()

@server.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "get_exchange_rate":
        currency = arguments["currency"]
        key = f"exchange_rate:{currency}"
        
        return await cache.get_or_fetch(
            key,
            lambda: fetch_exchange_rate(currency),
            ttl_seconds=300  # Cache for 5 minutes
        )
```

### Connection Pooling

Reuse connections:

```python
import aiohttp

class ConnectionPool:
    def __init__(self, max_connections: int = 10):
        self.session = None
        self.max_connections = max_connections
    
    async def __aenter__(self):
        connector = aiohttp.TCPConnector(limit=self.max_connections)
        self.session = aiohttp.ClientSession(connector=connector)
        return self.session
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.session.close()

# Usage
async with ConnectionPool() as session:
    async with session.get(url) as response:
        return await response.json()
```

### Resource Limits

Set appropriate limits:

```python
# Limit response size
MAX_RESPONSE_SIZE = 10 * 1024 * 1024  # 10 MB

async def get_resource(uri: str) -> str:
    content = await fetch_resource(uri)
    
    if len(content) > MAX_RESPONSE_SIZE:
        # Return truncated content with warning
        return {
            "content": content[:MAX_RESPONSE_SIZE],
            "truncated": True,
            "original_size": len(content)
        }
    
    return {"content": content, "truncated": False}

# Timeout long-running operations
async def call_tool_with_timeout(name: str, arguments: dict, timeout: int = 30):
    try:
        return await asyncio.wait_for(
            call_tool(name, arguments),
            timeout=timeout
        )
    except asyncio.TimeoutError:
        raise Exception(f"Tool execution timeout after {timeout} seconds")
```

## Error Handling

### Structured Errors

Use consistent error formats:

```python
from enum import Enum

class ErrorCode(Enum):
    VALIDATION_ERROR = "validation_error"
    AUTHENTICATION_ERROR = "authentication_error"
    PERMISSION_ERROR = "permission_error"
    NOT_FOUND = "not_found"
    RATE_LIMIT = "rate_limit_exceeded"
    INTERNAL_ERROR = "internal_error"

class MCPError(Exception):
    def __init__(self, code: ErrorCode, message: str, details: dict = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)
    
    def to_dict(self):
        return {
            "error": {
                "code": self.code.value,
                "message": self.message,
                "details": self.details
            }
        }

# Usage
@server.call_tool()
async def call_tool(name: str, arguments: dict):
    try:
        return await execute_tool(name, arguments)
    except ValueError as e:
        raise MCPError(
            ErrorCode.VALIDATION_ERROR,
            "Invalid input",
            {"field": str(e)}
        )
    except PermissionError:
        raise MCPError(
            ErrorCode.PERMISSION_ERROR,
            "Insufficient permissions"
        )
    except Exception as e:
        # Log the actual error
        logger.exception("Tool execution failed")
        # Return generic error to client
        raise MCPError(
            ErrorCode.INTERNAL_ERROR,
            "Internal server error"
        )
```

### Retry Logic

Implement smart retries:

```python
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((ConnectionError, TimeoutError))
)
async def fetch_with_retry(url: str):
    """Fetch with exponential backoff retry."""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            response.raise_for_status()
            return await response.json()
```

### Circuit Breaker

Prevent cascading failures:

```python
from datetime import datetime, timedelta

class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = timedelta(seconds=recovery_timeout)
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open
    
    async def call(self, func):
        """Execute function with circuit breaker protection."""
        if self.state == "open":
            if datetime.now() - self.last_failure_time > self.recovery_timeout:
                self.state = "half-open"
            else:
                raise Exception("Circuit breaker is OPEN")
        
        try:
            result = await func()
            if self.state == "half-open":
                self.state = "closed"
                self.failure_count = 0
            return result
        
        except self.expected_exception:
            self.failure_count += 1
            self.last_failure_time = datetime.now()
            
            if self.failure_count >= self.failure_threshold:
                self.state = "open"
            
            raise

# Usage
breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60)

@server.call_tool()
async def call_tool(name: str, arguments: dict):
    return await breaker.call(lambda: execute_tool(name, arguments))
```

## Testing

### Unit Tests

Test individual components:

```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_get_temperature_tool():
    """Test temperature tool returns correct format."""
    server = WeatherServer()
    
    result = await server.call_tool(
        "get_temperature",
        {"location": "San Francisco", "unit": "celsius"}
    )
    
    assert result.content[0].type == "text"
    assert "San Francisco" in result.content[0].text
    assert "°C" in result.content[0].text

@pytest.mark.asyncio
async def test_invalid_tool_name():
    """Test error handling for invalid tool."""
    server = WeatherServer()
    
    with pytest.raises(ValueError, match="Unknown tool"):
        await server.call_tool("invalid_tool", {})

@pytest.mark.asyncio
async def test_missing_required_argument():
    """Test validation of required arguments."""
    server = WeatherServer()
    
    with pytest.raises(ValueError, match="location"):
        await server.call_tool("get_temperature", {})
```

### Integration Tests

Test complete workflows:

```python
@pytest.mark.asyncio
async def test_client_server_integration():
    """Test full client-server communication."""
    # Start server in test mode
    server_process = await start_test_server()
    
    try:
        # Create client
        client = create_test_client()
        
        # Test connection
        await client.initialize()
        
        # List tools
        tools = await client.list_tools()
        assert len(tools.tools) > 0
        
        # Call tool
        result = await client.call_tool(
            "get_temperature",
            {"location": "Tokyo"}
        )
        assert "Tokyo" in result.content[0].text
    
    finally:
        await server_process.terminate()
```

### Load Testing

Test under realistic load:

```python
import asyncio
import time

async def load_test(num_requests: int, concurrency: int):
    """Run load test with specified concurrency."""
    client = create_client()
    
    async def make_request():
        start = time.time()
        try:
            await client.call_tool("get_temperature", {"location": "NYC"})
            return time.time() - start, None
        except Exception as e:
            return time.time() - start, str(e)
    
    # Run requests in batches
    results = []
    for i in range(0, num_requests, concurrency):
        batch_size = min(concurrency, num_requests - i)
        batch_results = await asyncio.gather(
            *[make_request() for _ in range(batch_size)]
        )
        results.extend(batch_results)
    
    # Analyze results
    latencies = [r[0] for r in results]
    errors = [r[1] for r in results if r[1]]
    
    print(f"Total requests: {num_requests}")
    print(f"Successful: {num_requests - len(errors)}")
    print(f"Failed: {len(errors)}")
    print(f"Avg latency: {sum(latencies) / len(latencies):.3f}s")
    print(f"Max latency: {max(latencies):.3f}s")

# Run load test
asyncio.run(load_test(num_requests=1000, concurrency=50))
```

## Monitoring

### Logging

Implement structured logging:

```python
import logging
import json
from datetime import datetime

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
        }
        
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data)

# Configure logger
logger = logging.getLogger("mcp_server")
handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Usage
@server.call_tool()
async def call_tool(name: str, arguments: dict):
    logger.info(
        "Tool called",
        extra={
            "tool_name": name,
            "arguments": arguments
        }
    )
    
    try:
        result = await execute_tool(name, arguments)
        logger.info("Tool succeeded", extra={"tool_name": name})
        return result
    except Exception as e:
        logger.error(
            "Tool failed",
            extra={"tool_name": name, "error": str(e)},
            exc_info=True
        )
        raise
```

### Metrics

Track key metrics:

```python
from prometheus_client import Counter, Histogram, Gauge
import time

# Define metrics
tool_calls_total = Counter(
    'mcp_tool_calls_total',
    'Total number of tool calls',
    ['tool_name', 'status']
)

tool_duration_seconds = Histogram(
    'mcp_tool_duration_seconds',
    'Tool execution duration',
    ['tool_name']
)

active_connections = Gauge(
    'mcp_active_connections',
    'Number of active client connections'
)

# Usage
@server.call_tool()
async def call_tool(name: str, arguments: dict):
    start_time = time.time()
    
    try:
        result = await execute_tool(name, arguments)
        tool_calls_total.labels(tool_name=name, status='success').inc()
        return result
    except Exception:
        tool_calls_total.labels(tool_name=name, status='error').inc()
        raise
    finally:
        duration = time.time() - start_time
        tool_duration_seconds.labels(tool_name=name).observe(duration)
```

### Health Checks

Implement health endpoints:

```python
from datetime import datetime

class HealthCheck:
    def __init__(self):
        self.start_time = datetime.now()
        self.last_check_time = None
        self.status = "healthy"
    
    async def check_health(self) -> dict:
        """Comprehensive health check."""
        checks = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "uptime_seconds": (datetime.now() - self.start_time).total_seconds(),
            "checks": {}
        }
        
        # Check database connection
        try:
            await check_database()
            checks["checks"]["database"] = "healthy"
        except Exception as e:
            checks["checks"]["database"] = f"unhealthy: {e}"
            checks["status"] = "unhealthy"
        
        # Check external APIs
        try:
            await check_external_api()
            checks["checks"]["external_api"] = "healthy"
        except Exception as e:
            checks["checks"]["external_api"] = f"degraded: {e}"
            if checks["status"] == "healthy":
                checks["status"] = "degraded"
        
        self.last_check_time = datetime.now()
        self.status = checks["status"]
        
        return checks
```

## Deployment

### Configuration Management

Use environment-based configuration:

```python
from pydantic import BaseSettings

class Settings(BaseSettings):
    # Server settings
    server_name: str = "mcp-server"
    server_version: str = "1.0.0"
    
    # API keys
    api_key: str
    
    # Database
    database_url: str
    database_pool_size: int = 10
    
    # Performance
    max_connections: int = 100
    request_timeout: int = 30
    
    # Logging
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"
        case_sensitive = False

# Load settings
settings = Settings()

# Use in server
server = Server(
    name=settings.server_name,
    version=settings.server_version
)
```

### Docker Deployment

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python health_check.py || exit 1

# Run server
CMD ["python", "server.py"]
```

```yaml
# docker-compose.yml
version: '3.8'

services:
  mcp-server:
    build: .
    environment:
      - API_KEY=${API_KEY}
      - DATABASE_URL=postgresql://user:pass@db:5432/mcp
      - LOG_LEVEL=INFO
    ports:
      - "8080:8080"
    depends_on:
      - db
    restart: unless-stopped
    
  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=mcp
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

### Kubernetes Deployment

```yaml
# k8s-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mcp-server
spec:
  replicas: 3
  selector:
    matchLabels:
      app: mcp-server
  template:
    metadata:
      labels:
        app: mcp-server
    spec:
      containers:
      - name: mcp-server
        image: mcp-server:1.0.0
        ports:
        - containerPort: 8080
        env:
        - name: API_KEY
          valueFrom:
            secretKeyRef:
              name: mcp-secrets
              key: api-key
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: mcp-server
spec:
  selector:
    app: mcp-server
  ports:
  - port: 80
    targetPort: 8080
  type: LoadBalancer
```

## Summary Checklist

Before deploying to production, ensure:

- [ ] Authentication and authorization implemented
- [ ] Input validation on all endpoints
- [ ] Output sanitization for sensitive data
- [ ] Rate limiting configured
- [ ] Error handling with structured errors
- [ ] Logging with structured format
- [ ] Metrics collection enabled
- [ ] Health check endpoints
- [ ] Unit tests with >80% coverage
- [ ] Integration tests for key workflows
- [ ] Load testing completed
- [ ] Documentation up to date
- [ ] Secrets in environment variables or secrets manager
- [ ] Resource limits configured
- [ ] Monitoring and alerting set up
- [ ] Deployment configuration reviewed
- [ ] Backup and recovery plan

---

Next: [API Reference](API_REFERENCE.md) | Previous: [Architecture](ARCHITECTURE.md)
