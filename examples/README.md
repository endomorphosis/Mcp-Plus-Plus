# MCP Examples

This directory contains example implementations of MCP servers and clients in various programming languages.

## Directory Structure

```
examples/
├── python/
│   ├── weather_server.py       # Simple weather tool server
│   ├── file_server.py          # File system resource server
│   └── requirements.txt        # Python dependencies
└── typescript/
    ├── weather-server.ts       # Weather server in TypeScript
    ├── package.json            # TypeScript dependencies
    └── tsconfig.json           # TypeScript configuration
```

## Examples Overview

### Weather Server
A simple MCP server that provides weather information tools.

**Features:**
- Get current temperature
- Get weather forecast

**Languages:** Python, TypeScript

### File Server
An MCP server that exposes file system resources.

**Features:**
- List files in directory
- Read file contents
- Search files by pattern
- Create new files

**Languages:** Python

## Running Examples

### Python Examples

```bash
cd examples/python

# Install dependencies
pip install -r requirements.txt

# Run server
python weather_server.py

# In another terminal, test with client
python -c "
import asyncio
from mcp.client import Client
from mcp.client.stdio import stdio_client

async def main():
    async with stdio_client({'command': 'python', 'args': ['weather_server.py']}) as (r, w):
        async with Client(r, w) as client:
            await client.initialize()
            tools = await client.list_tools()
            print(f'Available tools: {[t.name for t in tools.tools]}')

asyncio.run(main())
"
```

### TypeScript Examples

```bash
cd examples/typescript

# Install dependencies
npm install

# Build
npm run build

# Run server
node dist/weather-server.js

# Test with MCP Inspector
npx @modelcontextprotocol/inspector node dist/weather-server.js
```



## Using with Claude Desktop

To use these examples with Claude Desktop, add to your configuration:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "weather": {
      "command": "python",
      "args": ["/absolute/path/to/examples/python/weather_server.py"]
    },
    "files": {
      "command": "python",
      "args": ["/absolute/path/to/examples/python/file_server.py"]
    }
  }
}
```

## Learning Path

1. **Start with Weather Server** - Simple tool-based server
2. **Try File Server** - Learn about resources
3. **Build your own** - Create something unique!

## Additional Resources

- [Getting Started Guide](../GETTING_STARTED.md)
- [API Reference](../API_REFERENCE.md)
- [Best Practices](../BEST_PRACTICES.md)
- [Architecture Guide](../ARCHITECTURE.md)

## Contributing Examples

Have a great example? Contributions are welcome!

See [Contributing Guidelines](../CONTRIBUTING.md) for details.
