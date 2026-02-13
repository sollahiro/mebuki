import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
    CallToolRequestSchema,
    ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";

/**
 * mebuki MCP Server
 * Exposes investment analysis tools to AI models.
 */

const server = new Server(
    {
        name: "mebuki-mcp-server",
        version: "1.0.0",
    },
    {
        capabilities: {
            tools: {},
        },
    }
);

// Helpful for debugging in Claude Desktop logs
console.error("mebuki MCP Server starting...");
console.error(`Current directory: ${process.cwd()}`);
console.error(`MEBUKI_BACKEND_URL: ${process.env.MEBUKI_BACKEND_URL || "http://localhost:8765"}`);

/**
 * List available tools.
 * In mebuki, these will proxy to the FastAPI backend.
 */
server.setRequestHandler(ListToolsRequestSchema, async () => {
    return {
        tools: [
            {
                name: "analyze_stock",
                description: "Get summary financial metrics (ROE, debt ratio, etc.) for a Japanese stock. [Recommended first step]",
                inputSchema: {
                    type: "object",
                    properties: {
                        code: {
                            type: "string",
                            description: "Four-digit or five-digit Japanese stock code (e.g., '7203' or '72030').",
                        },
                    },
                    required: ["code"],
                },
            },
            {
                name: "analyze_securities_report",
                description: "Analyze the latest Securities Report (Yuho) to extract MD&A text. Useful for understanding the 'why' behind the numbers.",
                inputSchema: {
                    type: "object",
                    properties: {
                        code: {
                            type: "string",
                            description: "Four-digit or five-digit Japanese stock code.",
                        },
                    },
                    required: ["code"],
                },
            },
            {
                name: "search_companies",
                description: "Search for Japanese companies to get their stock codes (e.g., '72030'). This tool handles name variations and notation fluctuations. If multiple candidates are returned or the result is ambiguous, you MUST present the candidates to the user and ask them to confirm the correct one before proceeding to analyze.",
                inputSchema: {
                    type: "object",
                    properties: {
                        query: {
                            type: "string",
                            description: "Company name or partial stock code.",
                        },
                    },
                    required: ["query"],
                },
            },
            {
                name: "get_financial_metrics",
                description: "Get calculated financial metrics (ROE, Equity Ratio, etc.) for a specific stock.",
                inputSchema: {
                    type: "object",
                    properties: {
                        code: {
                            type: "string",
                            description: "Four-digit or five-digit Japanese stock code.",
                        },
                    },
                    required: ["code"],
                },
            },
            {
                name: "get_price_history",
                description: "Get daily stock price history to check trends and volatility.",
                inputSchema: {
                    type: "object",
                    properties: {
                        code: {
                            type: "string",
                            description: "Four-digit or five-digit Japanese stock code.",
                        },
                        days: {
                            type: "number",
                            description: "Number of days to fetch (default: 365)",
                        },
                    },
                    required: ["code"],
                },
            },
            {
                name: "list_edinet_documents",
                description: "List recent Securities Reports (Yuho) and other documents from EDINET.",
                inputSchema: {
                    type: "object",
                    properties: {
                        code: {
                            type: "string",
                            description: "Four-digit or five-digit Japanese stock code.",
                        },
                    },
                    required: ["code"],
                },
            },
            {
                name: "get_edinet_xbrl_content",
                description: "Extract MD&A (Management Discussion & Analysis) section from an EDINET XBRL document.",
                inputSchema: {
                    type: "object",
                    properties: {
                        doc_id: {
                            type: "string",
                            description: "Document ID (from list_edinet_documents)",
                        },
                    },
                    required: ["doc_id"],
                },
            },
            {
                name: "mebuki_analyze_financials",
                description: "Provides detailed financial metrics and an analyst guide covering four structural perspectives.",
                inputSchema: {
                    type: "object",
                    properties: {
                        code: {
                            type: "string",
                            description: "Four-digit or five-digit Japanese stock code.",
                        },
                    },
                    required: ["code"],
                },
            },
            {
                name: "get_financial_history",
                description: "Get a time-series table of key financial metrics (Sales, Profit, ROE, FCF, etc.). Recommended after getting an initial overview.",
                inputSchema: {
                    type: "object",
                    properties: {
                        code: {
                            type: "string",
                            description: "Four-digit or five-digit Japanese stock code.",
                        },
                    },
                    required: ["code"],
                },
            },
            {
                name: "get_mebuki_management_policy_criteria",
                description: "Get the specific analyst criteria (prompt guide) for summarizing management policies and strategies from an investor's perspective. No arguments needed.",
                inputSchema: {
                    type: "object",
                    properties: {},
                },
            },
            {
                name: "get_raw_financial_summaries",
                description: "Get raw, comprehensive financial summary data from J-QUANTS. Use this only when detailed indicators in other tools are insufficient.",
                inputSchema: {
                    type: "object",
                    properties: {
                        code: {
                            type: "string",
                            description: "Four-digit or five-digit Japanese stock code.",
                        },
                    },
                    required: ["code"],
                },
            },
        ],
    };
});

server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: args } = request.params;
    const baseUrl = process.env.MEBUKI_BACKEND_URL || "http://localhost:8765";

    try {
        let endpoint = "";

        switch (name) {
            case "analyze_stock": {
                const code = String(args?.code);
                endpoint = `/api/mcp/analyze/${code}`;
                break;
            }
            case "analyze_securities_report": {
                const code = String(args?.code);
                endpoint = `/api/mcp/securities_report/${code}`;
                break;
            }
            case "search_companies": {
                const query = String(args?.query);
                endpoint = `/api/mcp/search_companies?query=${encodeURIComponent(query)}`;
                break;
            }
            case "get_financial_metrics": {
                const code = String(args?.code);
                endpoint = `/api/mcp/metrics/${code}`;
                break;
            }
            case "get_price_history": {
                const code = String(args?.code);
                const days = args?.days ? Number(args.days) : 365;
                endpoint = `/api/mcp/prices/${code}?days=${days}`;
                break;
            }
            case "list_edinet_documents": {
                const code = String(args?.code);
                endpoint = `/api/mcp/edinet/${code}`;
                break;
            }
            case "get_edinet_xbrl_content": {
                const docId = String(args?.doc_id);
                endpoint = `/api/mcp/edinet/xbrl/${docId}`;
                break;
            }
            case "mebuki_analyze_financials": {
                const code = String(args?.code);
                endpoint = `/api/mcp/mebuki_analysis/${code}`;
                break;
            }
            case "get_financial_history": {
                const code = String(args?.code);
                endpoint = `/api/mcp/financial_history/${code}`;
                break;
            }
            case "get_raw_financial_summaries": {
                const code = String(args?.code);
                endpoint = `/api/mcp/financials/${code}`;
                break;
            }
            case "get_mebuki_management_policy_criteria": {
                // This tool returns the guide for the AI to apply to context.
                endpoint = `/api/mcp/management_policy_guide`;
                break;
            }
            default:
                throw new Error(`Tool not found: ${name}`);
        }

        // Call the specialized MCP endpoint in FastAPI
        const response = await fetch(`${baseUrl}${endpoint}`);

        if (!response.ok) {
            let errorMessage = `Error from mebuki backend (${response.status})`;
            try {
                const errorData = await response.json();
                errorMessage = errorData.detail || errorMessage;
            } catch (e) {
                const text = await response.text();
                if (text) errorMessage = text;
            }

            return {
                content: [{ type: "text", text: errorMessage }],
                isError: true,
            };
        }

        const data = await response.json();
        return {
            content: [{ type: "text", text: JSON.stringify(data, null, 2) }],
        };
    } catch (error: any) {
        return {
            content: [{ type: "text", text: `Failed to connect to mebuki backend: ${error.message}` }],
            isError: true,
        };
    }
});

async function main() {
    const transport = new StdioServerTransport();
    await server.connect(transport);
    console.error("mebuki MCP server running on stdio");
}

main().catch((error) => {
    console.error("Server error:", error);
    process.exit(1);
});
