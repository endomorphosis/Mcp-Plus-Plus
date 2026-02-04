# MCP Examples

This directory contains example implementations of MCP servers and clients in various programming languages.

## Directory Structure

```
examples/
├── python/
│   ├── weather_server.py       # Simple weather tool server
│   ├── file_server.py          # File system resource server
│   └── database_server.py      # Database integration example
├── typescript/
│   ├── weather-server.ts       # Weather server in TypeScript
│   ├── github-server.ts        # GitHub API integration
│   └── client-example.ts       # Client usage examples
└── java/
    ├── WeatherServer.java      # Weather server in Java
    └── ClientExample.java      # Java client examples
```

## Examples Overview

### Weather Server
A simple MCP server that provides weather information tools.

**Features:**
- Get current temperature
- Get weather forecast
- Get weather alerts

**Languages:** Python, TypeScript, Java

### File Server
An MCP server that exposes file system resources.

**Features:**
- List files in directory
- Read file contents
- Search files by pattern

**Languages:** Python

### Database Server
An MCP server for database operations.

**Features:**
- Query database
- List tables
- Get table schema

**Languages:** Python

### GitHub Server
Integration with GitHub API as an MCP server.

**Features:**
- List repositories
- Get repository info
- Create issues

**Languages:** TypeScript

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

### Java Examples

```bash
cd examples/java

# Build with Maven
mvn clean package

# Run server
java -jar target/weather-server.jar

# Or with Gradle
./gradlew run
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
3. **Explore Database Server** - Advanced patterns
4. **Build your own** - Create something unique!

## Additional Resources

- [Getting Started Guide](../GETTING_STARTED.md)
- [API Reference](../API_REFERENCE.md)
- [Best Practices](../BEST_PRACTICES.md)
- [Architecture Guide](../ARCHITECTURE.md)

## Contributing Examples

Have a great example? Contributions are welcome!

See [Contributing Guidelines](../CONTRIBUTING.md) for details.
