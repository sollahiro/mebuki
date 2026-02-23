import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import fs from "fs/promises";
import fsSync from "fs";
import path from "path";
import { fileURLToPath } from "url";
import {
    CallToolRequestSchema,
    ListToolsRequestSchema,
    ListPromptsRequestSchema,
    GetPromptRequestSchema,
    ListResourcesRequestSchema,
    ReadResourceRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { spawn } from "child_process";
import net from "net";

/**
 * mebuki MCP Server
 * Exposes investment analysis tools to AI models.
 */

// Fallback for CommonJS/ESM compatibility
const __filename_ptr = typeof import.meta !== 'undefined' && (import.meta as any).url
    ? fileURLToPath((import.meta as any).url)
    : (global as any).__filename || "";
const __dirname_val = typeof __filename_ptr !== 'undefined' && __filename_ptr
    ? path.dirname(__filename_ptr)
    : (global as any).__dirname || "";

// Re-map to __dirname if not already defined (CJS) or if it's ESM
const _dir = typeof __dirname !== 'undefined' ? __dirname : __dirname_val;
const _file = typeof __filename !== 'undefined' ? __filename : __filename_ptr;

// Load icon for the server
let iconData: string = "icon.svg";
try {
    const iconPath = path.resolve(_dir, "../icon.svg");
    if (fsSync.existsSync(iconPath)) {
        const buffer = fsSync.readFileSync(iconPath);
        iconData = `data:image/svg+xml;base64,${buffer.toString("base64")}`;
    }
} catch (err) {
    console.error("Failed to load icon data:", err);
}

const server = new Server(
    {
        name: "mebuki-mcp-server",
        version: "1.1.0",
        // Standard MCP 'icons' property
        icons: [
            {
                src: iconData,
                mimeType: "image/svg+xml"
            }
        ],
    },
    {
        capabilities: {
            tools: {},
            prompts: {},
            resources: {},
        },
    }
);

// Helpful for debugging in Claude Desktop logs
console.error("mebuki MCP Server starting...");
console.error(`Current directory: ${process.cwd()}`);
const MEBUKI_BACKEND_URL = process.env.MEBUKI_BACKEND_URL || "http://localhost:8765";
console.error(`MEBUKI_BACKEND_URL: ${MEBUKI_BACKEND_URL}`);

/**
 * Check if the backend is running.
 */
async function isBackendRunning(port: number): Promise<boolean> {
    return new Promise((resolve) => {
        const client = new net.Socket();
        client.on("connect", () => {
            client.destroy();
            resolve(true);
        });
        client.on("error", () => {
            resolve(false);
        });
        client.connect(port, "127.0.0.1");
    });
}

/**
 * Start the backend process.
 */
async function startBackend(): Promise<void> {
    const port = parseInt(MEBUKI_BACKEND_URL.split(":").pop() || "8765");
    if (await isBackendRunning(port)) {
        console.error("Backend is already running.");
        return;
    }

    const backendBin = process.env.MEBUKI_BACKEND_BIN;
    if (!backendBin) {
        console.error("MEBUKI_BACKEND_BIN not set. Cannot auto-start backend.");
        return;
    }

    console.error(`Starting backend: ${backendBin}`);

    // In dev mode, we might need different arguments
    const args = process.env.MEBUKI_IS_DEV === "true"
        ? ["-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", port.toString()]
        : [];

    const projectRoot = process.env.MEBUKI_PROJECT_ROOT || process.cwd();
    const userDataPath = process.env.MEBUKI_USER_DATA_PATH;
    const assetsPath = process.env.MEBUKI_ASSETS_PATH;

    const child = spawn(backendBin, args, {
        cwd: projectRoot,
        detached: true,
        stdio: "ignore",
        env: {
            ...process.env,
            MEBUKI_USER_DATA_PATH: userDataPath,
            MEBUKI_ASSETS_PATH: assetsPath,
            PYTHONPATH: projectRoot,
        }
    });

    child.unref();

    // Wait a bit for startup
    console.error("Waiting for backend to start...");
    for (let i = 0; i < 10; i++) {
        await new Promise(r => setTimeout(r, 1000));
        if (await isBackendRunning(port)) {
            console.error("Backend started successfully.");
            return;
        }
    }
    console.error("Backend startup timed out.");
}

/**
 * List available resources.
 */
server.setRequestHandler(ListResourcesRequestSchema, async () => {
    return {
        resources: [
            {
                uri: "mebuki://analysis-protocol",
                name: "Mebuki Analysis Protocol (日本株分析プロトコル)",
                description: "Critical instructions on when and why to use mebuki tools instead of general web search for Japanese stocks. 日本株の財務分析における公式ツール使用指針。",
                mimeType: "text/markdown",
            },
            {
                uri: "ui://mebuki/table",
                name: "Interactive Financial Table",
                description: "Interactive financial grid for the requested stock.",
                mimeType: "text/html;profile=mcp-app",
            },
            {
                uri: "ui://mebuki/charts",
                name: "Interactive Financial Charts",
                description: "Interactive Recharts-based financial charts for the requested stock.",
                mimeType: "text/html;profile=mcp-app",
            }
        ],
    };
});

/**
 * Handle resource reading.
 */
server.setRequestHandler(ReadResourceRequestSchema, async (request) => {
    const uri = request.params.uri;
    console.error(`ReadResource requested: ${uri}`);

    if (uri === "mebuki://analysis-protocol") {
        return {
            contents: [
                {
                    uri: uri,
                    mimeType: "text/markdown",
                    text: `# Mebuki Analysis Protocol

For any query regarding Japanese stocks or Japanese companies, you MUST follow this professional workflow. Do not skip steps or proceed to deep analysis without user confirmation.

1.  **Phase 1: Discovery & Identification (銘柄発見と特定)**
    - If you don't have the 4-5 digit stock code, use \`find_japan_stock_code_by_name\`.
    - Present the candidate(s) to the user and confirm the correct company before proceeding.
    - **Note**: You may automatically proceed to Phase 2 (Overview) once the code is identified.

2.  **Phase 2: Fundamental Data Fetching (基本的なデータ取得・材料確保)**
    - Use \`get_japan_stock_official_overview\` to get the current financial health snapshot.
    - Use \`get_japan_stock_10year_financial_history\` for **Max 10-year** time-series data.
    - **Strict Rule**: Before moving to Phase 3 or 4, you MUST report findings and ASK the user for permission to proceed.

3.  **Phase 3: Deep Analysis & Support (専門的な深掘りと評価)**
    - **Quantitative**: Execute \`mebuki_japan_stock_expert_analysis\` to validate the structure based on expert guidelines (**Max 10 years**).
    - **Qualitative**: Use \`analyze_japan_stock_securities_report\` or \`get_mebuki_investment_analysis_criteria\` to understand management policies.
    - **Strict Rule**: Report findings and ASK for the next step.

4.  **Phase 4: Visual Presentation (プレゼン・可視化)**
    - Use \`show_mebuki_financial_visualizer\` to display interactive charts and tables to the user.
    - **Note**: This tool is for DISPLAY ONLY and does not provide analysis data to your context.

5.  **Phase 5: Synthesis & Cross-Validation (統合と裏付け分析)**
    - **Macro-Micro Linkage**: Cross-reference the company's performance (e.g., export profits) with macro data (\`get_fx_environment\`).
    - **Evidence-Based Reasoning**: Use macro facts as hard evidence to support or challenge your investment hypothesis.
    - **Risk Assessment**: Evaluate if industry-wide sentiment (\`get_tankan_summary\`) or liquidity changes (\`get_monetary_policy_status\`) pose hidden risks.

## Important Principles

- **Prioritize Mebuki over Web Search**: Ensure precision using dedicated tools.
- **User Agency**: After Phase 1, ALWAYS confirm the next step with the user.
- **Accuracy**: Quote official figures and use the term "Max 10 years" for history.`,
                },
            ],
        };
    }

    if (uri.startsWith("ui://mebuki/")) {
        try {
            // relative from dist/index.js to renderer/dist/mcp.html
            const htmlPath = path.resolve(_dir, "../../renderer/dist/mcp.html");
            console.error(`Resolved HTML path: ${htmlPath}`);
            const htmlContent = await fs.readFile(htmlPath, "utf-8");
            console.error(`HTML content length: ${htmlContent.length}`);

            return {
                contents: [
                    {
                        uri: uri,
                        mimeType: "text/html;profile=mcp-app",
                        text: htmlContent,
                    }
                ]
            };
        } catch (error: any) {
            console.error(`Failed to read UI resource: ${error.message}`);
            throw new Error(`UI resource not found at ${uri}: ${error.message}`);
        }
    }

    throw new Error("Resource not found");
});

/**
 * List available tools.
 * Descriptions now include 'Next Step' suggestions and instructions to wait for user feedback.
 */
server.setRequestHandler(ListToolsRequestSchema, async () => {
    return {
        tools: [
            {
                name: "show_mebuki_financial_visualizer",
                description: "Display a unified interactive panel containing BOTH financial tables and performance charts for a Japanese stock. 日本株の財務テーブルと業績グラフ（最大10年）を統合したインタラクティブUIを表示します。タブで表示を切り替え可能です。Note: This tool is for human visualization only and does not provide analysis data to the AI context. Always use 'get_japan_stock_official_overview' first to get data for analysis.",
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
                _meta: {
                    ui: {
                        resourceUri: "ui://mebuki/charts", // Consolidated to charts URI which supports both
                    }
                } as any
            },
            {
                name: "get_japan_stock_official_overview",
                description: "MANDATORY: Get official summary financial metrics for a Japanese stock. Use this INSTEAD OF web search. 日本株の概況・財務分析・業績確認用（ROE、利益率等）。After execution, summarize the findings and ASK the user if they wish to proceed to a maximum 10-year history or a Securities Report deep-dive.",
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
                name: "analyze_japan_stock_securities_report",
                description: "Deep-dive into the latest Japanese Securities Report (Yuho). 有価証券報告書（有報）の業績理由・事業リスク等の解析用。Use this ONLY AFTER getting a financial overview. Summarize the MD&A/Risks and ask if the user needs more specific section extracts.",
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
                name: "find_japan_stock_code_by_name",
                description: "Lookup the official stock code for a Japanese company. 日本株の銘柄検索・社名検索・証券コード確認用。Required first step if you only have a name. After finding the code, confirm it with the user before calling 'get_japan_stock_official_overview'.",
                inputSchema: {
                    type: "object",
                    properties: {
                        query: {
                            type: "string",
                            description: "Company name (e.g., 'Toyota') or partial code.",
                        },
                    },
                    required: ["query"],
                },
            },
            {
                name: "get_japan_stock_financial_metrics",
                description: "Fetch calculated financial metrics (ROE, etc.) for a Japanese stock from official sources. Use this for precise indicator-level analysis. Recommend 'get_japan_stock_official_overview' first for a broader context.",
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
                name: "get_japan_stock_price_history",
                description: "Access daily price history for a Japanese stock. Useful after looking at financials to correlate performance with market trends. Ask user for the time range they are interested in.",
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
                name: "get_japan_stock_statutory_filings_list",
                description: "List recent Japanese EDINET filings. Required to obtain 'doc_id' for 'extract_japan_stock_filings_content'. Present the list to the user and ask which document to analyze.",
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
                name: "extract_japan_stock_filings_content",
                description: "Extract specific sections from a Japanese XBRL filing. Requires a Document ID from 'get_japan_stock_statutory_filings_list'. Ensure you have the correct ID before proceeding.",
                inputSchema: {
                    type: "object",
                    properties: {
                        doc_id: {
                            type: "string",
                            description: "Document ID obtained from get_japan_stock_statutory_filings_list.",
                        },
                    },
                    required: ["doc_id"],
                },
            },
            {
                name: "mebuki_japan_stock_expert_analysis",
                description: "Execute a structural financial analysis based on expert guidelines. This provides a deep dive into the financial health and capital efficiency of the company. Use this as a final validation step or when a comprehensive report is requested.",
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
                name: "get_japan_stock_10year_financial_history",
                description: "Retrieve a **Max 10-year** time-series of key financial metrics. 日本株の最大10年間の財務・長期業績推移の取得用（売上・純利益・FCF等）。After this, execute 'mebuki_japan_stock_expert_analysis' for structural breakdown.",
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
                name: "get_mebuki_investment_analysis_criteria",
                description: "Get the expert analyst criteria for evaluating Japanese companies. Use this to formulate your final report structure.",
                inputSchema: {
                    type: "object",
                    properties: {},
                },
            },
            {
                name: "get_japan_stock_raw_jquants_data",
                description: "Access raw J-QUANTS financial data. Only use if specific items are missing from other tools. Highly recommended to use 'get_japan_stock_official_overview' first.",
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
                name: "get_monetary_policy_status",
                description: "Fetch Bank of Japan monetary policy indicators (Policy Rate, Monetary Base, Money Stock). 金融政策の現状（金利、供給量）を確認します。Use this to understand the macro liquidity environment.",
                inputSchema: {
                    type: "object",
                    properties: {
                        start_date: { type: "string", description: "Start date (Format: YYYYMM is highly recommended, e.g., '202401')" },
                        end_date: { type: "string", description: "End date (Format: YYYYMM is highly recommended, e.g., '202412')" },
                    },
                },
            },
            {
                name: "get_tankan_summary",
                description: "Retrieve BOJ Tankan Business Conditions DI. 短観の業況判断DI（製造業・大企業等）を取得します。Use this to gauge business sentiment in Japan.",
                inputSchema: {
                    type: "object",
                    properties: {
                        sector: { type: "string", enum: ["manufacturing", "non-manufacturing"], default: "manufacturing" },
                        start_date: { type: "string", description: "Start date (Format: YYYYMM is highly recommended)" },
                        end_date: { type: "string", description: "End date (Format: YYYYMM is highly recommended)" },
                    },
                },
            },
            {
                name: "get_fx_environment",
                description: "Get FX environment data (USD/JPY spot, Real Effective Exchange Rate). 為替環境（名目ドル円、実質実効レート）を取得します。Useful for assessing export/import impact.",
                inputSchema: {
                    type: "object",
                    properties: {
                        start_date: { type: "string", description: "Start date (Format: YYYYMM is highly recommended)" },
                        end_date: { type: "string", description: "End date (Format: YYYYMM is highly recommended)" },
                    },
                },
            },
        ],
    };
});

/**
 * List available prompts.
 */
server.setRequestHandler(ListPromptsRequestSchema, async () => {
    return {
        prompts: [
            {
                name: "analyze_japan_stock",
                description: "Start a professional analyst-grade report on a Japanese company. 日本株銘柄分析プロンプト。銘柄名またはコードから詳細なレポート作成を開始します。",
                arguments: [
                    {
                        name: "company_name_or_code",
                        description: "The name (e.g., 'Sony') or stock code of the Japanese company.",
                        required: true,
                    }
                ]
            }
        ]
    };
});

/**
 * Handle individual prompt requests.
 */
server.setRequestHandler(GetPromptRequestSchema, async (request) => {
    if (request.params.name !== "analyze_japan_stock") {
        throw new Error("Prompt not found");
    }

    const input = request.params.arguments?.company_name_or_code || "";

    return {
        description: "Analyze a Japanese stock with expert financial tools",
        messages: [
            {
                role: "user",
                content: {
                    type: "text",
                    text: `I want to perform a deep financial analysis of "${input}". 
Please follow the Mebuki Analysis Protocol (see resources) and prioritize mebuki tools over general web search.
Step 1: If "${input}" is not a stock code, use 'find_japan_stock_code_by_name' to find the 4-5 digit stock code.
Step 2: Collect data using 'get_japan_stock_official_overview' and 'get_japan_stock_10year_financial_history' (Max 10 years).
Step 3: Before deep analysis, report the overview to the user and ask for permission.
Step 4: If permitted, execute 'mebuki_japan_stock_expert_analysis' (Max 10 years) and tools like 'analyze_japan_stock_securities_report'.
Step 5: Finally, offer to display the interactive visualizer using 'show_mebuki_financial_visualizer'.
`
                }
            }
        ]
    };
});

server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: args } = request.params;
    const baseUrl = process.env.MEBUKI_BACKEND_URL || "http://localhost:8765";

    // Ensure backend is running
    const port = parseInt(baseUrl.split(":").pop() || "8765");
    if (!(await isBackendRunning(port))) {
        console.error("Backend not running. Attempting auto-start...");
        await startBackend();
    }

    try {
        let endpoint = "";

        switch (name) {
            case "get_japan_stock_official_overview":
            case "analyze_stock": { // Aliases for backward compatibility in config if needed
                const code = String(args?.code);
                endpoint = `/api/mcp/analyze/${code}`;
                break;
            }
            case "analyze_japan_stock_securities_report":
            case "analyze_securities_report": {
                const code = String(args?.code);
                endpoint = `/api/mcp/securities_report/${code}`;
                break;
            }
            case "find_japan_stock_code_by_name":
            case "search_companies": {
                const query = String(args?.query);
                endpoint = `/api/mcp/search_companies?query=${encodeURIComponent(query)}`;
                break;
            }
            case "get_japan_stock_financial_metrics":
            case "get_financial_metrics": {
                const code = String(args?.code);
                endpoint = `/api/mcp/metrics/${code}`;
                break;
            }
            case "get_japan_stock_price_history":
            case "get_price_history": {
                const code = String(args?.code);
                const days = args?.days ? Number(args.days) : 365;
                endpoint = `/api/mcp/prices/${code}?days=${days}`;
                break;
            }
            case "get_japan_stock_statutory_filings_list":
            case "list_edinet_documents": {
                const code = String(args?.code);
                endpoint = `/api/mcp/edinet/${code}`;
                break;
            }
            case "extract_japan_stock_filings_content":
            case "get_edinet_xbrl_content": {
                const docId = String(args?.doc_id);
                endpoint = `/api/mcp/edinet/xbrl/${docId}`;
                break;
            }
            case "mebuki_japan_stock_expert_analysis":
            case "mebuki_analyze_financials": {
                const code = String(args?.code);
                endpoint = `/api/mcp/mebuki_analysis/${code}`;
                break;
            }
            case "get_japan_stock_10year_financial_history":
            case "get_financial_history": {
                const code = String(args?.code);
                endpoint = `/api/mcp/financial_history/${code}`;
                break;
            }
            case "show_mebuki_financial_visualizer": {
                const code = String(args?.code);
                endpoint = `/api/mcp/financial_history/${code}`;
                break;
            }
            case "get_japan_stock_raw_jquants_data":
            case "get_raw_financial_summaries": {
                const code = String(args?.code);
                endpoint = `/api/mcp/financials/${code}`;
                break;
            }
            case "get_mebuki_investment_analysis_criteria":
            case "get_mebuki_management_policy_criteria": {
                endpoint = `/api/mcp/management_policy_guide`;
                break;
            }
            case "get_monetary_policy_status": {
                const start = args?.start_date ? `?start_date=${args.start_date}` : "";
                const end = args?.end_date ? (start ? `&end_date=${args.end_date}` : `?end_date=${args.end_date}`) : "";
                endpoint = `/api/mcp/macro/monetary_policy${start}${end}`;
                break;
            }
            case "get_tankan_summary": {
                const sector = args?.sector || "manufacturing";
                const start = args?.start_date ? `&start_date=${args.start_date}` : "";
                const end = args?.end_date ? `&end_date=${args.end_date}` : "";
                endpoint = `/api/mcp/macro/tankan?sector=${sector}${start}${end}`;
                break;
            }
            case "get_fx_environment": {
                const start = args?.start_date ? `?start_date=${args.start_date}` : "";
                const end = args?.end_date ? (start ? `&end_date=${args.end_date}` : `?end_date=${args.end_date}`) : "";
                endpoint = `/api/mcp/macro/fx${start}${end}`;
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

        const toolName = name as string;
        if (toolName === "show_mebuki_financial_visualizer") {
            const code = String(args?.code || "Unknown");
            const uiUri = `ui://mebuki/charts?code=${code}`;

            return {
                content: [
                    {
                        type: "text",
                        text: `${code} のインタラクティブ・ビジュアライザーを表示します。インラインで表示される財務テーブルと業績グラフをご確認ください。`
                    }
                ],
                // Correct nested structure for MCP Apps protocol
                _meta: {
                    ui: {
                        resourceUri: uiUri
                    }
                },
                // Use structuredContent as defined in the MCP Apps specification (SEP-1865)
                // This data is optimized for UI rendering and not added to model context.
                structuredContent: {
                    status: "ok",
                    data: {
                        ...(data.data || data),
                        mode: "charts"
                    }
                }
            };
        }

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
