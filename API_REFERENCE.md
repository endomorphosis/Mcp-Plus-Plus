# MCP API Reference

Complete API reference for the Model Context Protocol.

## Table of Contents

1. [Protocol Overview](#protocol-overview)
2. [Request/Response Format](#requestresponse-format)
3. [Lifecycle Methods](#lifecycle-methods)
4. [Capabilities](#capabilities)
5. [Tools](#tools)
6. [Resources](#resources)
7. [Prompts](#prompts)
8. [Notifications](#notifications)
9. [Error Codes](#error-codes)

## Protocol Overview

MCP uses JSON-RPC 2.0 as its message format over various transport layers (stdio, HTTP/SSE, WebSocket).

### Base Request

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "method_name",
  "params": {
    "param1": "value1"
  }
}
```

### Base Response

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "key": "value"
  }
}
```

### Error Response

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": -32600,
    "message": "Invalid Request",
    "data": {
      "details": "Additional error information"
    }
  }
}
```

## Request/Response Format

### Content Types

MCP supports multiple content types for responses:

#### Text Content

```json
{
  "type": "text",
  "text": "Plain text response"
}
```

#### Image Content

```json
{
  "type": "image",
  "data": "base64_encoded_image_data",
  "mimeType": "image/png"
}
```

#### Resource Content

```json
{
  "type": "resource",
  "uri": "file:///path/to/resource",
  "mimeType": "application/json",
  "text": "Resource content"
}
```

## Lifecycle Methods

### initialize

Establish connection and exchange capabilities.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2024-11-05",
    "capabilities": {
      "experimental": {},
      "sampling": {}
    },
    "clientInfo": {
      "name": "ExampleClient",
      "version": "1.0.0"
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
    "protocolVersion": "2024-11-05",
    "capabilities": {
      "tools": {},
      "resources": {},
      "prompts": {}
    },
    "serverInfo": {
      "name": "ExampleServer",
      "version": "1.0.0"
    }
  }
}
```

### initialized

Notification sent after initialization is complete.

**Notification:**
```json
{
  "jsonrpc": "2.0",
  "method": "notifications/initialized"
}
```

### ping

Check if the connection is alive.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "ping"
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {}
}
```

## Capabilities

### capabilities/list

List server capabilities.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "capabilities/list"
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "capabilities": {
      "tools": {
        "supportsProgress": true
      },
      "resources": {
        "supportsSubscribe": true,
        "listChanged": true
      },
      "prompts": {
        "listChanged": true
      }
    }
  }
}
```

## Tools

### tools/list

List all available tools.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "method": "tools/list"
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "result": {
    "tools": [
      {
        "name": "get_weather",
        "description": "Get current weather for a location",
        "inputSchema": {
          "type": "object",
          "properties": {
            "location": {
              "type": "string",
              "description": "City name"
            },
            "units": {
              "type": "string",
              "enum": ["metric", "imperial"],
              "default": "metric"
            }
          },
          "required": ["location"]
        }
      },
      {
        "name": "search_web",
        "description": "Search the web for information",
        "inputSchema": {
          "type": "object",
          "properties": {
            "query": {
              "type": "string",
              "description": "Search query"
            },
            "max_results": {
              "type": "integer",
              "minimum": 1,
              "maximum": 10,
              "default": 5
            }
          },
          "required": ["query"]
        }
      }
    ]
  }
}
```

### tools/call

Execute a tool with given arguments.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "id": 5,
  "method": "tools/call",
  "params": {
    "name": "get_weather",
    "arguments": {
      "location": "San Francisco",
      "units": "metric"
    }
  }
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 5,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "The current weather in San Francisco is 18°C with partly cloudy skies."
      }
    ],
    "isError": false
  }
}
```

**Error Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 5,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Error: Unable to fetch weather data"
      }
    ],
    "isError": true
  }
}
```

## Resources

### resources/list

List all available resources.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "id": 6,
  "method": "resources/list"
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 6,
  "result": {
    "resources": [
      {
        "uri": "file:///documents/report.pdf",
        "name": "Quarterly Report",
        "description": "Q4 2023 Financial Report",
        "mimeType": "application/pdf"
      },
      {
        "uri": "file:///data/metrics.json",
        "name": "Performance Metrics",
        "description": "System performance metrics",
        "mimeType": "application/json"
      }
    ]
  }
}
```

### resources/read

Read a specific resource.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "id": 7,
  "method": "resources/read",
  "params": {
    "uri": "file:///data/metrics.json"
  }
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 7,
  "result": {
    "contents": [
      {
        "uri": "file:///data/metrics.json",
        "mimeType": "application/json",
        "text": "{\"cpu_usage\": 45.2, \"memory_usage\": 62.1}"
      }
    ]
  }
}
```

### resources/subscribe

Subscribe to updates for a resource.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "id": 8,
  "method": "resources/subscribe",
  "params": {
    "uri": "file:///data/metrics.json"
  }
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 8,
  "result": {}
}
```

### resources/unsubscribe

Unsubscribe from resource updates.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "id": 9,
  "method": "resources/unsubscribe",
  "params": {
    "uri": "file:///data/metrics.json"
  }
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 9,
  "result": {}
}
```

### resources/templates/list

List resource URI templates.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "id": 10,
  "method": "resources/templates/list"
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 10,
  "result": {
    "resourceTemplates": [
      {
        "uriTemplate": "file:///projects/{project_id}/documents/{doc_id}",
        "name": "Project Document",
        "description": "Access documents within a project",
        "mimeType": "application/pdf"
      }
    ]
  }
}
```

## Prompts

### prompts/list

List all available prompts.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "id": 11,
  "method": "prompts/list"
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 11,
  "result": {
    "prompts": [
      {
        "name": "code_review",
        "description": "Review code for quality and best practices",
        "arguments": [
          {
            "name": "language",
            "description": "Programming language",
            "required": true
          },
          {
            "name": "code",
            "description": "Code to review",
            "required": true
          }
        ]
      },
      {
        "name": "summarize_document",
        "description": "Create a summary of a document",
        "arguments": [
          {
            "name": "document_uri",
            "description": "URI of document to summarize",
            "required": true
          },
          {
            "name": "max_length",
            "description": "Maximum summary length in words",
            "required": false
          }
        ]
      }
    ]
  }
}
```

### prompts/get

Get a specific prompt with arguments filled in.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "id": 12,
  "method": "prompts/get",
  "params": {
    "name": "code_review",
    "arguments": {
      "language": "python",
      "code": "def hello(): print('Hello')"
    }
  }
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 12,
  "result": {
    "description": "Review Python code for quality",
    "messages": [
      {
        "role": "user",
        "content": {
          "type": "text",
          "text": "Please review the following Python code:\n\n```python\ndef hello(): print('Hello')\n```\n\nProvide feedback on:\n1. Code style and conventions\n2. Potential bugs\n3. Performance improvements\n4. Best practices"
        }
      }
    ]
  }
}
```

## Notifications

### notifications/resources/updated

Sent when a subscribed resource is updated.

**Notification:**
```json
{
  "jsonrpc": "2.0",
  "method": "notifications/resources/updated",
  "params": {
    "uri": "file:///data/metrics.json"
  }
}
```

### notifications/resources/list_changed

Sent when the list of resources changes.

**Notification:**
```json
{
  "jsonrpc": "2.0",
  "method": "notifications/resources/list_changed"
}
```

### notifications/tools/list_changed

Sent when the list of tools changes.

**Notification:**
```json
{
  "jsonrpc": "2.0",
  "method": "notifications/tools/list_changed"
}
```

### notifications/prompts/list_changed

Sent when the list of prompts changes.

**Notification:**
```json
{
  "jsonrpc": "2.0",
  "method": "notifications/prompts/list_changed"
}
```

### notifications/progress

Progress updates for long-running operations.

**Notification:**
```json
{
  "jsonrpc": "2.0",
  "method": "notifications/progress",
  "params": {
    "progressToken": "abc123",
    "progress": 50,
    "total": 100,
    "message": "Processing items..."
  }
}
```

## Error Codes

MCP uses standard JSON-RPC 2.0 error codes plus custom codes:

### Standard JSON-RPC Errors

| Code | Message | Description |
|------|---------|-------------|
| -32700 | Parse error | Invalid JSON |
| -32600 | Invalid Request | Invalid JSON-RPC request |
| -32601 | Method not found | Method does not exist |
| -32602 | Invalid params | Invalid method parameters |
| -32603 | Internal error | Internal server error |

### MCP Custom Errors

| Code | Message | Description |
|------|---------|-------------|
| -32000 | Server error | Generic server error |
| -32001 | Connection error | Connection failed |
| -32002 | Timeout error | Operation timed out |
| -32003 | Resource not found | Requested resource doesn't exist |
| -32004 | Tool not found | Requested tool doesn't exist |
| -32005 | Prompt not found | Requested prompt doesn't exist |
| -32006 | Permission denied | Insufficient permissions |
| -32007 | Rate limit exceeded | Too many requests |
| -32008 | Invalid input | Input validation failed |

### Error Example

```json
{
  "jsonrpc": "2.0",
  "id": 5,
  "error": {
    "code": -32004,
    "message": "Tool not found",
    "data": {
      "tool_name": "invalid_tool",
      "available_tools": ["get_weather", "search_web"]
    }
  }
}
```

## SDK Examples

### Python SDK

```python
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, Resource, Prompt, TextContent

server = Server("example-server")

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="example_tool",
            description="An example tool",
            inputSchema={
                "type": "object",
                "properties": {
                    "param": {"type": "string"}
                },
                "required": ["param"]
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "example_tool":
        return [TextContent(type="text", text=f"Result: {arguments['param']}")]
    raise ValueError(f"Unknown tool: {name}")

@server.list_resources()
async def list_resources() -> list[Resource]:
    return [
        Resource(
            uri="file:///example.txt",
            name="Example Resource",
            mimeType="text/plain"
        )
    ]

@server.read_resource()
async def read_resource(uri: str) -> str:
    if uri == "file:///example.txt":
        return "Example content"
    raise ValueError(f"Resource not found: {uri}")

async def main():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())
```

### TypeScript SDK

```typescript
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  ListResourcesRequestSchema,
  ReadResourceRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";

const server = new Server(
  { name: "example-server", version: "1.0.0" },
  { capabilities: { tools: {}, resources: {} } }
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "example_tool",
      description: "An example tool",
      inputSchema: {
        type: "object",
        properties: {
          param: { type: "string" },
        },
        required: ["param"],
      },
    },
  ],
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => ({
  content: [
    {
      type: "text",
      text: `Result: ${request.params.arguments.param}`,
    },
  ],
}));

server.setRequestHandler(ListResourcesRequestSchema, async () => ({
  resources: [
    {
      uri: "file:///example.txt",
      name: "Example Resource",
      mimeType: "text/plain",
    },
  ],
}));

server.setRequestHandler(ReadResourceRequestSchema, async (request) => ({
  contents: [
    {
      uri: request.params.uri,
      mimeType: "text/plain",
      text: "Example content",
    },
  ],
}));

const transport = new StdioServerTransport();
await server.connect(transport);
```

## Versioning

MCP uses protocol versioning to maintain compatibility:

```json
{
  "protocolVersion": "2024-11-05"
}
```

Servers should support multiple protocol versions when possible and negotiate the highest common version during initialization.

## Security Considerations

1. **Always validate inputs** against the defined schema
2. **Sanitize outputs** to prevent information leakage
3. **Implement rate limiting** to prevent abuse
4. **Use authentication** for sensitive operations
5. **Log all operations** for audit trails
6. **Handle errors gracefully** without exposing internal details

See [Security](SECURITY.md) for detailed security guidelines.

## Further Reading

- [Getting Started](GETTING_STARTED.md)
- [Architecture](ARCHITECTURE.md)
- [Best Practices](BEST_PRACTICES.md)
- [Security](SECURITY.md)
- [Official Specification](https://github.com/modelcontextprotocol/modelcontextprotocol)

---

Previous: [Best Practices](BEST_PRACTICES.md) | Next: [Security](SECURITY.md)
