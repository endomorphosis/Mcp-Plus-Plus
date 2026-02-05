# MCP Architecture

A comprehensive guide to the Model Context Protocol's architecture, design principles, and implementation patterns.

## Table of Contents

1. [Overview](#overview)
2. [Core Components](#core-components)
3. [Protocol Design](#protocol-design)
4. [Transport Layers](#transport-layers)
5. [Message Flow](#message-flow)
6. [Security Model](#security-model)
7. [Extension Points](#extension-points)

## Overview

The Model Context Protocol (MCP) follows a client-server architecture that enables AI applications to securely access external capabilities. The protocol is designed to be:

- **Stateful**: Maintains connection state and context
- **Bidirectional**: Both clients and servers can initiate requests
- **Asynchronous**: Supports non-blocking operations
- **Extensible**: Easily adaptable to new use cases

## Core Components

### 1. MCP Host

The **MCP Host** is the AI application that users interact with.

**Examples:**
- Claude Desktop
- ChatGPT with plugins
- Custom AI applications
- IDE extensions

**Responsibilities:**
- Manage user interactions
- Coordinate multiple MCP clients
- Handle user permissions and approvals
- Present results to users

```
┌─────────────────────────────┐
│       MCP Host              │
│  (AI Application)           │
│                             │
│  ┌───────────────────────┐  │
│  │   Client Manager      │  │
│  └───────┬───────────────┘  │
│          │                  │
│     ┌────┴──────┐           │
│  ┌──▼────┐  ┌───▼───┐       │
│  │Client1│  │Client2│       │
│  └───────┘  └───────┘       │
└─────────────────────────────┘
```

### 2. MCP Client

The **MCP Client** manages connections between the host and servers.

**Responsibilities:**
- Establish and maintain server connections
- Send requests and handle responses
- Manage protocol lifecycle
- Handle connection errors and reconnection

**Key Features:**
- Connection pooling
- Request multiplexing
- Automatic reconnection
- Error handling

### 3. MCP Server

The **MCP Server** exposes capabilities to clients.

**Types of Capabilities:**

1. **Resources**: Read-only data sources
   ```json
   {
     "uri": "file:///data/report.pdf",
     "mimeType": "application/pdf",
     "name": "Quarterly Report"
   }
   ```

2. **Tools**: Executable functions
   ```json
   {
     "name": "send_email",
     "description": "Send an email message",
     "inputSchema": { "..." }
   }
   ```

3. **Prompts**: Reusable templates
   ```json
   {
     "name": "code_review",
     "description": "Review code for quality",
     "arguments": [{"name": "language", "required": true}]
   }
   ```

## Protocol Design

### Protocol Layers

```
┌─────────────────────────────────┐
│     Application Layer           │  (Tools, Resources, Prompts)
├─────────────────────────────────┤
│     Protocol Layer              │  (JSON-RPC 2.0 Messages)
├─────────────────────────────────┤
│     Transport Layer             │  (stdio, HTTP/SSE, WebSocket)
├─────────────────────────────────┤
│     Physical Layer              │  (IPC, Network)
└─────────────────────────────────┘
```

### Message Format

MCP uses JSON-RPC 2.0 as its message format:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "get_temperature",
    "arguments": {
      "location": "San Francisco"
    }
  }
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "The temperature is 72°F"
      }
    ]
  }
}
```

### Core Methods

#### Initialization

```
Client → Server: initialize
Server → Client: initialized
```

#### Capabilities

```
Client → Server: capabilities/list
Server → Client: capabilities
```

#### Tools

```
Client → Server: tools/list
Server → Client: tools

Client → Server: tools/call
Server → Client: result
```

#### Resources

```
Client → Server: resources/list
Server → Client: resources

Client → Server: resources/read
Server → Client: content
```

#### Prompts

```
Client → Server: prompts/list
Server → Client: prompts

Client → Server: prompts/get
Server → Client: prompt
```

## Transport Layers

### 1. Standard I/O (stdio)

**Best for**: Local processes, command-line tools

```python
# Python example
async with stdio_server() as (read, write):
    await server.run(read, write, options)
```

**Characteristics:**
- Process-to-process communication
- Low latency
- Simple setup
- Limited to local machine

### 2. Server-Sent Events (SSE) over HTTP

**Best for**: Remote servers, web applications

```typescript
// TypeScript example
const transport = new SSEServerTransport(
  "http://localhost:3000/mcp",
  sse_client
);
```

**Characteristics:**
- Works over HTTP/HTTPS
- Supports remote connections
- Firewall-friendly
- One-way server push with HTTP requests

### 3. WebSocket

**Best for**: Real-time bidirectional communication

```python
# Python example
async with websocket_server("ws://localhost:8080") as transport:
    await server.run(transport, options)
```

**Characteristics:**
- Full duplex communication
- Low latency
- Efficient for high-frequency updates
- Requires WebSocket support

### Transport Comparison

| Feature | stdio | HTTP/SSE | WebSocket |
|---------|-------|----------|-----------|
| Latency | Very Low | Medium | Low |
| Remote Access | No | Yes | Yes |
| Complexity | Low | Medium | Medium |
| Bidirectional | Yes | Limited | Yes |
| Resource Usage | Low | Medium | Medium |

## Message Flow

### Typical Session Flow

```
┌────────┐                      ┌────────┐
│ Client │                      │ Server │
└───┬────┘                      └───┬────┘
    │                               │
    │ 1. initialize                 │
    ├──────────────────────────────>│
    │                               │
    │ 2. initialized                │
    │<──────────────────────────────┤
    │                               │
    │ 3. capabilities/list          │
    ├──────────────────────────────>│
    │                               │
    │ 4. capabilities               │
    │<──────────────────────────────┤
    │                               │
    │ 5. tools/list                 │
    ├──────────────────────────────>│
    │                               │
    │ 6. tools                      │
    │<──────────────────────────────┤
    │                               │
    │ 7. tools/call                 │
    ├──────────────────────────────>│
    │                               │
    │ 8. result                     │
    │<──────────────────────────────┤
    │                               │
```

### Tool Execution Flow

```
1. User asks AI to perform an action
   ↓
2. AI determines which tool to use
   ↓
3. Host requests user approval (if required)
   ↓
4. Client sends tool/call to server
   ↓
5. Server validates request
   ↓
6. Server executes tool
   ↓
7. Server returns results
   ↓
8. Client processes results
   ↓
9. Host presents results to user
```

## Security Model

### Authentication

MCP supports multiple authentication mechanisms:

1. **Environment Variables**
   ```bash
   export API_KEY="secret-key"
   ```

2. **Configuration Files**
   ```json
   {
     "auth": {
       "type": "bearer",
       "token": "..."
     }
   }
   ```

3. **OAuth 2.0**
   ```python
   server = Server(
       name="secure-server",
       auth=OAuth2Auth(
           client_id="...",
           client_secret="..."
       )
   )
   ```

### Authorization

**Permission Levels:**

1. **Read**: Access to resources
2. **Execute**: Call tools
3. **Admin**: Configure server

**Example Permission Check:**
```python
@server.call_tool()
async def call_tool(name: str, arguments: dict, context: CallContext):
    # Check permissions
    if not context.has_permission("execute"):
        raise PermissionError("Execution not allowed")
    
    # Execute tool
    return await execute_tool(name, arguments)
```

### Input Validation

Always validate inputs:

```python
def validate_input(schema: dict, data: dict) -> bool:
    """Validate input against JSON schema."""
    from jsonschema import validate
    validate(instance=data, schema=schema)
    return True
```

### Output Sanitization

Sanitize sensitive data:

```python
def sanitize_output(data: str) -> str:
    """Remove sensitive information from output."""
    import re
    # Remove API keys
    data = re.sub(r'api[_-]?key["\s:=]+[\w-]+', '[REDACTED]', data, flags=re.I)
    # Remove tokens
    data = re.sub(r'token["\s:=]+[\w-]+', '[REDACTED]', data, flags=re.I)
    return data
```

## Extension Points

### Custom Transports

Implement your own transport layer:

```python
class CustomTransport(Transport):
    async def connect(self):
        """Establish connection."""
        pass
    
    async def send(self, message: Message):
        """Send a message."""
        pass
    
    async def receive(self) -> Message:
        """Receive a message."""
        pass
    
    async def close(self):
        """Close connection."""
        pass
```

### Custom Capabilities

Extend MCP with custom capabilities:

```python
@server.list_capabilities()
async def list_capabilities():
    return {
        "tools": {},
        "resources": {},
        "prompts": {},
        "custom": {
            "streaming": True,
            "batch_operations": True
        }
    }
```

### Middleware

Add middleware for cross-cutting concerns:

```python
class LoggingMiddleware:
    async def process_request(self, request: Request) -> Request:
        logger.info(f"Request: {request.method}")
        return request
    
    async def process_response(self, response: Response) -> Response:
        logger.info(f"Response: {response.result}")
        return response

server.add_middleware(LoggingMiddleware())
```

## Performance Considerations

### Connection Pooling

```python
class ConnectionPool:
    def __init__(self, max_connections: int = 10):
        self.max_connections = max_connections
        self.connections = []
    
    async def get_connection(self) -> Connection:
        if len(self.connections) < self.max_connections:
            return await self.create_connection()
        return await self.wait_for_connection()
```

### Caching

```python
from functools import lru_cache

@lru_cache(maxsize=100)
async def get_resource(uri: str):
    """Cache resource access."""
    return await fetch_resource(uri)
```

### Batching

```python
async def batch_tool_calls(calls: list[ToolCall]) -> list[ToolResult]:
    """Execute multiple tools in parallel."""
    tasks = [call_tool(call) for call in calls]
    return await asyncio.gather(*tasks)
```

## Design Patterns

### 1. Single Responsibility

Each server should focus on one domain:
- ✅ `weather-server`: Only weather data
- ✅ `email-server`: Only email operations
- ❌ `everything-server`: Weather, email, database, etc.

### 2. Fail Fast

Validate early, fail quickly:
```python
if not is_valid(input):
    raise ValueError("Invalid input")
```

### 3. Circuit Breaker

Protect against cascading failures:
```python
class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5):
        self.failures = 0
        self.threshold = failure_threshold
        self.state = "closed"
    
    async def call(self, func):
        if self.state == "open":
            raise Exception("Circuit breaker is open")
        
        try:
            result = await func()
            self.failures = 0
            return result
        except Exception:
            self.failures += 1
            if self.failures >= self.threshold:
                self.state = "open"
            raise
```

## References

- [MCP Specification](https://github.com/modelcontextprotocol/modelcontextprotocol)
- [JSON-RPC 2.0](https://www.jsonrpc.org/specification)
- [OAuth 2.0](https://oauth.net/2/)
- [Best Practices](BEST_PRACTICES.md)

---

Next: [Best Practices](BEST_PRACTICES.md) | Previous: [Getting Started](GETTING_STARTED.md)
