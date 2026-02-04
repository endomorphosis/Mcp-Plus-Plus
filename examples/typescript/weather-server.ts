/**
 * Weather Server - MCP Example (TypeScript)
 * 
 * A simple MCP server that provides weather information tools.
 * This example demonstrates:
 * - Tool definition with input schemas
 * - Tool execution with validation
 * - Error handling
 * - Async operations
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";

// Mock weather data (in real implementation, use weather API)
const MOCK_WEATHER_DATA: Record<string, {
  temp: number;
  condition: string;
  humidity: number;
}> = {
  "san francisco": { temp: 18, condition: "Partly Cloudy", humidity: 65 },
  "new york": { temp: 22, condition: "Sunny", humidity: 55 },
  "london": { temp: 12, condition: "Rainy", humidity: 80 },
  "tokyo": { temp: 25, condition: "Clear", humidity: 60 },
};

class WeatherServer {
  private server: Server;

  constructor() {
    this.server = new Server(
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

    this.setupHandlers();
  }

  private setupHandlers(): void {
    // List available tools
    this.server.setRequestHandler(ListToolsRequestSchema, async () => {
      return {
        tools: [
          {
            name: "get_current_weather",
            description: "Get current weather for a location",
            inputSchema: {
              type: "object",
              properties: {
                location: {
                  type: "string",
                  description: "City name (e.g., 'San Francisco', 'New York')",
                },
                units: {
                  type: "string",
                  enum: ["celsius", "fahrenheit"],
                  description: "Temperature units",
                  default: "celsius",
                },
              },
              required: ["location"],
            },
          },
          {
            name: "get_forecast",
            description: "Get weather forecast for the next 7 days",
            inputSchema: {
              type: "object",
              properties: {
                location: {
                  type: "string",
                  description: "City name",
                },
                days: {
                  type: "integer",
                  minimum: 1,
                  maximum: 7,
                  description: "Number of days (1-7)",
                  default: 3,
                },
              },
              required: ["location"],
            },
          },
        ],
      };
    });

    // Handle tool calls
    this.server.setRequestHandler(CallToolRequestSchema, async (request) => {
      const { name, arguments: args } = request.params;

      try {
        if (name === "get_current_weather") {
          return await this.getCurrentWeather(
            args.location as string,
            (args.units as string) || "celsius"
          );
        } else if (name === "get_forecast") {
          return await this.getForecast(
            args.location as string,
            (args.days as number) || 3
          );
        } else {
          throw new Error(`Unknown tool: ${name}`);
        }
      } catch (error) {
        return {
          content: [
            {
              type: "text",
              text: `Error: ${error instanceof Error ? error.message : String(error)}`,
            },
          ],
          isError: true,
        };
      }
    });
  }

  private async getCurrentWeather(
    location: string,
    units: string
  ): Promise<{ content: Array<{ type: string; text: string }> }> {
    if (!location) {
      throw new Error("Location is required");
    }

    // Normalize location
    const locationKey = location.toLowerCase().trim();

    // Get weather data
    const weather = MOCK_WEATHER_DATA[locationKey];
    if (!weather) {
      return {
        content: [
          {
            type: "text",
            text: `Weather data not available for '${location}'. Available locations: ${Object.keys(
              MOCK_WEATHER_DATA
            ).join(", ")}`,
          },
        ],
      };
    }

    // Convert temperature if needed
    let temp = weather.temp;
    let tempStr: string;
    if (units === "fahrenheit") {
      temp = (temp * 9) / 5 + 32;
      tempStr = `${temp.toFixed(1)}°F`;
    } else {
      tempStr = `${temp}°C`;
    }

    // Format response
    const response = [
      `Current weather in ${location.charAt(0).toUpperCase() + location.slice(1)}:`,
      `Temperature: ${tempStr}`,
      `Condition: ${weather.condition}`,
      `Humidity: ${weather.humidity}%`,
    ].join("\n");

    return {
      content: [
        {
          type: "text",
          text: response,
        },
      ],
    };
  }

  private async getForecast(
    location: string,
    days: number
  ): Promise<{ content: Array<{ type: string; text: string }> }> {
    if (!location) {
      throw new Error("Location is required");
    }

    if (days < 1 || days > 7) {
      throw new Error("Days must be between 1 and 7");
    }

    const locationKey = location.toLowerCase().trim();
    const baseWeather = MOCK_WEATHER_DATA[locationKey];

    if (!baseWeather) {
      return {
        content: [
          {
            type: "text",
            text: `Weather data not available for '${location}'`,
          },
        ],
      };
    }

    // Generate mock forecast
    const forecastLines = [
      `Weather forecast for ${location.charAt(0).toUpperCase() + location.slice(1)} (${days} days):`,
      "",
    ];

    for (let day = 1; day <= days; day++) {
      // Vary temperature slightly for each day
      const tempVariation = (day % 3) - 1;
      const temp = baseWeather.temp + tempVariation;

      forecastLines.push(
        `Day ${day}:`,
        `  Temperature: ${temp}°C`,
        `  Condition: ${baseWeather.condition}`,
        `  Humidity: ${baseWeather.humidity}%`,
        ""
      );
    }

    return {
      content: [
        {
          type: "text",
          text: forecastLines.join("\n").trim(),
        },
      ],
    };
  }

  async run(): Promise<void> {
    const transport = new StdioServerTransport();
    await this.server.connect(transport);
    console.error("Weather MCP Server running on stdio");
  }
}

// Main entry point
async function main() {
  const server = new WeatherServer();
  await server.run();
}

main().catch((error) => {
  console.error("Server error:", error);
  process.exit(1);
});
