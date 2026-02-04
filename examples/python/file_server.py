"""
File Server - MCP Example

An MCP server that exposes file system resources.
This example demonstrates:
- Resource listing
- Resource reading
- URI-based resource access
- File system security
"""

import asyncio
import os
from pathlib import Path
from typing import Any
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Resource, TextContent, ImageContent

# Configure the base directory that the server can access
# In production, this should be configured securely
BASE_DIR = Path(os.getenv("MCP_FILE_SERVER_BASE_DIR", "/tmp/mcp_files"))


class FileServer:
    """File system MCP server."""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir.resolve()
        self.server = Server("file-server")
        self.setup_handlers()

        # Ensure base directory exists
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def setup_handlers(self):
        """Set up MCP request handlers."""

        @self.server.list_resources()
        async def list_resources() -> list[Resource]:
            """List all accessible files as resources."""
            resources = []

            try:
                for file_path in self.base_dir.rglob("*"):
                    if file_path.is_file():
                        # Create URI for the file
                        relative_path = file_path.relative_to(self.base_dir)
                        uri = f"file:///{relative_path}"

                        # Determine MIME type
                        mime_type = self._get_mime_type(file_path)

                        resources.append(
                            Resource(
                                uri=uri,
                                name=file_path.name,
                                description=f"File: {relative_path}",
                                mimeType=mime_type,
                            )
                        )
            except Exception as e:
                print(f"Error listing resources: {e}")

            return resources

        @self.server.read_resource()
        async def read_resource(uri: str) -> str:
            """Read a file resource."""
            # Extract path from URI
            if not uri.startswith("file:///"):
                raise ValueError(f"Invalid URI format: {uri}")

            relative_path = uri[8:]  # Remove "file:///"
            file_path = (self.base_dir / relative_path).resolve()

            # Security check: ensure path is within base directory
            if not self._is_safe_path(file_path):
                raise PermissionError(
                    f"Access denied: path outside allowed directory"
                )

            # Check if file exists
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {uri}")

            if not file_path.is_file():
                raise ValueError(f"Not a file: {uri}")

            # Read file content
            try:
                # Try to read as text
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                return content
            except UnicodeDecodeError:
                # If binary file, return base64 encoded
                import base64

                with open(file_path, "rb") as f:
                    content = base64.b64encode(f.read()).decode("utf-8")
                return f"[Binary file, base64 encoded]\n{content}"

        @self.server.list_tools()
        async def list_tools():
            """List available file operation tools."""
            return [
                {
                    "name": "search_files",
                    "description": "Search for files by name pattern",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "pattern": {
                                "type": "string",
                                "description": "File name pattern (e.g., '*.txt', 'report*')",
                            }
                        },
                        "required": ["pattern"],
                    },
                },
                {
                    "name": "create_file",
                    "description": "Create a new file with content",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Relative file path",
                            },
                            "content": {
                                "type": "string",
                                "description": "File content",
                            },
                        },
                        "required": ["path", "content"],
                    },
                },
            ]

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict):
            """Execute a file operation tool."""
            if name == "search_files":
                return await self.search_files(arguments.get("pattern", ""))
            elif name == "create_file":
                return await self.create_file(
                    arguments.get("path", ""),
                    arguments.get("content", ""),
                )
            else:
                raise ValueError(f"Unknown tool: {name}")

    def _is_safe_path(self, path: Path) -> bool:
        """Check if path is within the allowed base directory."""
        try:
            path.relative_to(self.base_dir)
            return True
        except ValueError:
            return False

    def _get_mime_type(self, path: Path) -> str:
        """Determine MIME type from file extension."""
        extension = path.suffix.lower()
        mime_types = {
            ".txt": "text/plain",
            ".md": "text/markdown",
            ".json": "application/json",
            ".xml": "application/xml",
            ".html": "text/html",
            ".css": "text/css",
            ".js": "application/javascript",
            ".py": "text/x-python",
            ".pdf": "application/pdf",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
        }
        return mime_types.get(extension, "application/octet-stream")

    async def search_files(self, pattern: str) -> list[TextContent]:
        """Search for files matching a pattern."""
        if not pattern:
            raise ValueError("Pattern is required")

        import fnmatch

        matches = []
        try:
            for file_path in self.base_dir.rglob("*"):
                if file_path.is_file():
                    if fnmatch.fnmatch(file_path.name, pattern):
                        relative_path = file_path.relative_to(self.base_dir)
                        matches.append(str(relative_path))
        except Exception as e:
            return [TextContent(type="text", text=f"Error searching files: {e}")]

        if not matches:
            result = f"No files found matching pattern: {pattern}"
        else:
            result = f"Found {len(matches)} file(s) matching '{pattern}':\n"
            result += "\n".join(f"  - {m}" for m in matches)

        return [TextContent(type="text", text=result)]

    async def create_file(self, path: str, content: str) -> list[TextContent]:
        """Create a new file."""
        if not path:
            raise ValueError("Path is required")

        file_path = (self.base_dir / path).resolve()

        # Security check
        if not self._is_safe_path(file_path):
            raise PermissionError("Access denied: path outside allowed directory")

        # Check if file already exists
        if file_path.exists():
            return [
                TextContent(
                    type="text",
                    text=f"Error: File already exists: {path}",
                )
            ]

        try:
            # Create parent directories if needed
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Write file
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

            return [
                TextContent(
                    type="text",
                    text=f"Successfully created file: {path}",
                )
            ]
        except Exception as e:
            return [
                TextContent(
                    type="text",
                    text=f"Error creating file: {e}",
                )
            ]

    async def run(self):
        """Run the MCP server."""
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options(),
            )


async def main():
    """Main entry point."""
    # You can override the base directory with an environment variable
    base_dir = Path(os.getenv("MCP_FILE_SERVER_BASE_DIR", "/tmp/mcp_files"))

    print(f"Starting File Server with base directory: {base_dir}")
    print("Note: Set MCP_FILE_SERVER_BASE_DIR environment variable to change location")

    server = FileServer(base_dir)
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
