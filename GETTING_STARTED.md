# Getting Started with MCP

This guide will help you create your first Model Context Protocol (MCP) server and client in under 15 minutes.

## Prerequisites

- Python 3.10+ OR Node.js 18+ OR Java 17+
- Basic understanding of async programming
- A text editor or IDE

## Table of Contents

1. [Installation](#installation)
2. [Creating Your First Server](#creating-your-first-server)
3. [Connecting a Client](#connecting-a-client)
4. [Testing Your Implementation](#testing-your-implementation)
5. [Next Steps](#next-steps)

## Installation

### Python

```bash
# Create a virtual environment
python -m venv mcp-env
source mcp-env/bin/activate  # On Windows: mcp-env\Scripts\activate

# Install MCP SDK
pip install mcp
```

### TypeScript/JavaScript

```bash
# Initialize a new project
npm init -y

# Install MCP SDK
npm install @modelcontextprotocol/sdk

# Install TypeScript (optional but recommended)
npm install -D typescript @types/node
```

### Java

```xml
<!-- Add to your pom.xml -->
<dependency>
    <groupId>io.modelcontextprotocol</groupId>
    <artifactId>mcp-sdk</artifactId>
    <version>1.0.0</version>
</dependency>
```

## Creating Your First Server

Let's create a simple weather server that provides a tool to get temperature information.

### Python Example

Create a file called `weather_server.py`:

```python
import asyncio
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Initialize the server
server = Server("weather-server")

# Define available tools
@server.list_tools()
async def list_tools() -> list[Tool]:
    """List all available tools."""
    return [
        Tool(
            name="get_temperature",
            description="Get the current temperature for a location",
            inputSchema={
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "City name or location"
                    },
                    "unit": {
                        "type": "string",
                        "enum": ["celsius", "fahrenheit"],
                        "description": "Temperature unit",
                        "default": "celsius"
                    }
                },
                "required": ["location"]
            }
        )
    ]

# Implement tool functionality
@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Execute a tool with given arguments."""
    if name == "get_temperature":
        location = arguments.get("location")
        unit = arguments.get("unit", "celsius")
        
        # In a real implementation, you would call a weather API here
        # For demo purposes, we'll return mock data
        temp = 72 if unit == "fahrenheit" else 22
        
        return [
            TextContent(
                type="text",
                text=f"The temperature in {location} is {temp}°{unit[0].upper()}"
            )
        ]
    
    raise ValueError(f"Unknown tool: {name}")

async def main():
    """Run the server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )

if __name__ == "__main__":
    asyncio.run(main())
```

### TypeScript Example

Create a file called `weather-server.ts`:

```typescript
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";

// Initialize the server
const server = new Server(
  {
    name: "weather-server",
    version: "1.0.0",
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

// Define available tools
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      {
        name: "get_temperature",
        description: "Get the current temperature for a location",
        inputSchema: {
          type: "object",
          properties: {
            location: {
              type: "string",
              description: "City name or location",
            },
            unit: {
              type: "string",
              enum: ["celsius", "fahrenheit"],
              description: "Temperature unit",
              default: "celsius",
            },
          },
          required: ["location"],
        },
      },
    ],
  };
});

// Implement tool functionality
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  if (name === "get_temperature") {
    const location = args.location as string;
    const unit = (args.unit as string) || "fahrenheit";
    
    // In a real implementation, call a weather API
    const temp = unit === "fahrenheit" ? 72 : 22;
    
    return {
      content: [
        {
          type: "text",
          text: `The temperature in ${location} is ${temp}°${unit[0].toUpperCase()}`,
        },
      ],
    };
  }

  throw new Error(`Unknown tool: ${name}`);
});

// Start the server
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

main().catch(console.error);
```

## Connecting a Client

Now let's create a client that connects to our weather server.

### Python Client

Create `weather_client.py`:

```python
import asyncio
from mcp.client import Client
from mcp.client.stdio import stdio_client

async def main():
    # Connect to the server
    server_params = {
        "command": "python",
        "args": ["weather_server.py"]
    }
    
    async with stdio_client(server_params) as (read, write):
        async with Client(read, write) as client:
            # Initialize the connection
            await client.initialize()
            
            # List available tools
            tools = await client.list_tools()
            print(f"Available tools: {[tool.name for tool in tools.tools]}")
            
            # Call the temperature tool
            result = await client.call_tool(
                "get_temperature",
                {"location": "San Francisco", "unit": "celsius"}
            )
            
            print(f"Result: {result.content[0].text}")

if __name__ == "__main__":
    asyncio.run(main())
```

### TypeScript Client

Create `weather-client.ts`:

```typescript
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

async function main() {
  // Connect to the server
  const transport = new StdioClientTransport({
    command: "node",
    args: ["weather-server.js"],
  });

  const client = new Client(
    {
      name: "weather-client",
      version: "1.0.0",
    },
    {
      capabilities: {},
    }
  );

  await client.connect(transport);

  // List available tools
  const tools = await client.listTools();
  console.log("Available tools:", tools.tools.map((t) => t.name));

  // Call the temperature tool
  const result = await client.callTool({
    name: "get_temperature",
    arguments: {
      location: "San Francisco",
      unit: "celsius",
    },
  });

  console.log("Result:", result.content[0].text);
}

main().catch(console.error);
```

## Testing Your Implementation

### 1. Start the Server

```bash
# Python
python weather_server.py

# TypeScript (after compiling)
node weather-server.js
```

### 2. Run the Client

In a new terminal:

```bash
# Python
python weather_client.py

# TypeScript
node weather-client.js
```

Expected output:
```
Available tools: ['get_temperature']
Result: The temperature in San Francisco is 22°C
```

## Configuration

### Server Configuration

Create a `mcp-config.json` file for your MCP host (e.g., Claude Desktop):

```json
{
  "mcpServers": {
    "weather": {
      "command": "python",
      "args": ["/path/to/weather_server.py"],
      "env": {
        "API_KEY": "your-api-key-here"
      }
    }
  }
}
```

For Claude Desktop on macOS, place this at:
```
~/Library/Application Support/Claude/claude_desktop_config.json
```

For Windows:
```
%APPDATA%\Claude\claude_desktop_config.json
```

## Next Steps

Now that you have a basic MCP server and client running, you can:

1. **Add More Tools**: Extend your server with additional functionality
2. **Add Resources**: Expose data sources for the AI to read
3. **Add Prompts**: Create reusable prompt templates
4. **Error Handling**: Implement robust error handling and validation
5. **Security**: Add authentication and authorization
6. **Testing**: Write tests for your MCP server

### Learn More

- [Architecture Guide](ARCHITECTURE.md) - Understand MCP's design
- [API Reference](API_REFERENCE.md) - Complete API documentation
- [Best Practices](BEST_PRACTICES.md) - Production deployment tips
- [Examples](examples/) - More complex examples

## Troubleshooting

### Common Issues

**Problem**: Server not starting
```
Solution: Check that all dependencies are installed and Python/Node version is correct
```

**Problem**: Client can't connect
```
Solution: Verify the server command path in your configuration
```

**Problem**: Tool not found
```
Solution: Ensure tool names match exactly between client calls and server definitions
```

### Debug Mode

Enable debug logging:

```python
# Python
import logging
logging.basicConfig(level=logging.DEBUG)
```

```typescript
// TypeScript
const server = new Server({
  name: "weather-server",
  version: "1.0.0",
}, {
  capabilities: { tools: {} },
  debug: true
});
```

## Resources

- [MCP Specification](https://github.com/modelcontextprotocol/modelcontextprotocol)
- [Official Documentation](https://modelcontextprotocol.io/docs/)
- [Community Examples](https://github.com/modelcontextprotocol/servers)
- [Discord Community](https://discord.gg/mcp)

---

Ready to build something amazing? Check out our [Examples](examples/) directory for more complex use cases!
