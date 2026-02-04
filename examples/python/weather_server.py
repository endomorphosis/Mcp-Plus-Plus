"""
Weather Server - MCP Example

A simple MCP server that provides weather information tools.
This example demonstrates:
- Tool definition with input schemas
- Tool execution with validation
- Error handling
- Async operations
"""

import asyncio
import os
from typing import Any
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# In a real implementation, you would use a weather API like OpenWeatherMap
# For this example, we'll use mock data
MOCK_WEATHER_DATA = {
    "san francisco": {"temp": 18, "condition": "Partly Cloudy", "humidity": 65},
    "new york": {"temp": 22, "condition": "Sunny", "humidity": 55},
    "london": {"temp": 12, "condition": "Rainy", "humidity": 80},
    "tokyo": {"temp": 25, "condition": "Clear", "humidity": 60},
}


class WeatherServer:
    """Weather information MCP server."""

    def __init__(self):
        self.server = Server("weather-server")
        self.setup_handlers()

    def setup_handlers(self):
        """Set up MCP request handlers."""

        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            """List available weather tools."""
            return [
                Tool(
                    name="get_current_weather",
                    description="Get current weather for a location",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "location": {
                                "type": "string",
                                "description": "City name (e.g., 'San Francisco', 'New York')",
                            },
                            "units": {
                                "type": "string",
                                "enum": ["celsius", "fahrenheit"],
                                "description": "Temperature units",
                                "default": "celsius",
                            },
                        },
                        "required": ["location"],
                    },
                ),
                Tool(
                    name="get_forecast",
                    description="Get weather forecast for the next 7 days",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "location": {
                                "type": "string",
                                "description": "City name",
                            },
                            "days": {
                                "type": "integer",
                                "minimum": 1,
                                "maximum": 7,
                                "description": "Number of days (1-7)",
                                "default": 3,
                            },
                        },
                        "required": ["location"],
                    },
                ),
            ]

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict) -> list[TextContent]:
            """Execute a weather tool."""
            try:
                if name == "get_current_weather":
                    return await self.get_current_weather(
                        arguments.get("location", ""),
                        arguments.get("units", "celsius"),
                    )
                elif name == "get_forecast":
                    return await self.get_forecast(
                        arguments.get("location", ""),
                        arguments.get("days", 3),
                    )
                else:
                    raise ValueError(f"Unknown tool: {name}")
            except Exception as e:
                return [
                    TextContent(
                        type="text",
                        text=f"Error: {str(e)}",
                    )
                ]

    async def get_current_weather(
        self, location: str, units: str
    ) -> list[TextContent]:
        """Get current weather for a location."""
        if not location:
            raise ValueError("Location is required")

        # Normalize location
        location_key = location.lower().strip()

        # Get weather data (in real implementation, call weather API)
        weather = MOCK_WEATHER_DATA.get(location_key)
        if not weather:
            return [
                TextContent(
                    type="text",
                    text=f"Weather data not available for '{location}'. "
                    f"Available locations: {', '.join(MOCK_WEATHER_DATA.keys())}",
                )
            ]

        # Convert temperature if needed
        temp = weather["temp"]
        if units == "fahrenheit":
            temp = (temp * 9 / 5) + 32
            temp_str = f"{temp:.1f}°F"
        else:
            temp_str = f"{temp}°C"

        # Format response
        response = (
            f"Current weather in {location.title()}:\n"
            f"Temperature: {temp_str}\n"
            f"Condition: {weather['condition']}\n"
            f"Humidity: {weather['humidity']}%"
        )

        return [TextContent(type="text", text=response)]

    async def get_forecast(self, location: str, days: int) -> list[TextContent]:
        """Get weather forecast for a location."""
        if not location:
            raise ValueError("Location is required")

        if days < 1 or days > 7:
            raise ValueError("Days must be between 1 and 7")

        location_key = location.lower().strip()
        base_weather = MOCK_WEATHER_DATA.get(location_key)

        if not base_weather:
            return [
                TextContent(
                    type="text",
                    text=f"Weather data not available for '{location}'",
                )
            ]

        # Generate mock forecast
        forecast_text = f"Weather forecast for {location.title()} ({days} days):\n\n"

        for day in range(1, days + 1):
            # Vary the temperature slightly for each day
            temp_variation = (day % 3) - 1
            temp = base_weather["temp"] + temp_variation

            forecast_text += (
                f"Day {day}:\n"
                f"  Temperature: {temp}°C\n"
                f"  Condition: {base_weather['condition']}\n"
                f"  Humidity: {base_weather['humidity']}%\n\n"
            )

        return [TextContent(type="text", text=forecast_text.strip())]

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
    server = WeatherServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
