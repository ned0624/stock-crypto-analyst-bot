import asyncio
import requests
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

STOCK_API_BASE = "https://stock-api-618661878536.asia-east1.run.app"

app = Server("stock-analysis")

# ── 定義工具 ──────────────────────────────────────────────────────────────────
SOURCE = "claude_desktop"

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    print(f"[{SOURCE}] 呼叫工具：{name}")

@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="get_stock_info",
            description="取得台股股票基本資料：現價、漲跌、PE、殖利率、市值",
            inputSchema={
                "type": "object",
                "properties": {
                    "stock_id": {"type": "string", "description": "台股股票代號，例如 2330"}
                },
                "required": ["stock_id"]
            }
        ),
        Tool(
            name="get_stock_technical",
            description="取得技術指標：RSI、MACD、KD、均線MA5/MA20/MA60",
            inputSchema={
                "type": "object",
                "properties": {
                    "stock_id": {"type": "string", "description": "台股股票代號"},
                    "period": {"type": "string", "description": "時間範圍，例如 3mo、6mo、1y", "default": "6mo"}
                },
                "required": ["stock_id"]
            }
        ),
        Tool(
            name="get_stock_signal",
            description="取得技術訊號分析和綜合評分，判斷買賣方向",
            inputSchema={
                "type": "object",
                "properties": {
                    "stock_id": {"type": "string", "description": "台股股票代號"}
                },
                "required": ["stock_id"]
            }
        ),
        Tool(
            name="get_stock_chip",
            description="取得三大法人籌碼：外資、投信、自營商買賣超張數",
            inputSchema={
                "type": "object",
                "properties": {
                    "stock_id": {"type": "string", "description": "台股股票代號"}
                },
                "required": ["stock_id"]
            }
        ),
        Tool(
            name="get_stock_margin",
            description="取得融資融券資料：融資餘額、融券餘額",
            inputSchema={
                "type": "object",
                "properties": {
                    "stock_id": {"type": "string", "description": "台股股票代號"}
                },
                "required": ["stock_id"]
            }
        ),
        Tool(
            name="get_support_resistance",
            description="取得支撐壓力位：近期高低點、布林通道、52週高低",
            inputSchema={
                "type": "object",
                "properties": {
                    "stock_id": {"type": "string", "description": "台股股票代號"}
                },
                "required": ["stock_id"]
            }
        ),
        Tool(
            name="get_volume_analysis",
            description="取得量價分析：量比、爆量天數、價量關係",
            inputSchema={
                "type": "object",
                "properties": {
                    "stock_id": {"type": "string", "description": "台股股票代號"}
                },
                "required": ["stock_id"]
            }
        ),
        Tool(
            name="get_valuation",
            description="取得估值資料：PE、PB、PS、ROE、ROA、毛利率",
            inputSchema={
                "type": "object",
                "properties": {
                    "stock_id": {"type": "string", "description": "台股股票代號"}
                },
                "required": ["stock_id"]
            }
        ),
        Tool(
            name="get_financials",
            description="取得財報資料：季報、年報營收、毛利、淨利、EPS",
            inputSchema={
                "type": "object",
                "properties": {
                    "stock_id": {"type": "string", "description": "台股股票代號"}
                },
                "required": ["stock_id"]
            }
        ),
        Tool(
            name="get_revenue",
            description="取得營收趨勢：季度營收和年增率",
            inputSchema={
                "type": "object",
                "properties": {
                    "stock_id": {"type": "string", "description": "台股股票代號"}
                },
                "required": ["stock_id"]
            }
        ),
        Tool(
            name="get_market",
            description="取得台股大盤指數現況",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
    ]

# ── 執行工具 ──────────────────────────────────────────────────────────────────

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        if name == "get_stock_info":
            r = requests.get(f"{STOCK_API_BASE}/stock/{arguments['stock_id']}", timeout=10)
            result = r.json()

        elif name == "get_stock_technical":
            period = arguments.get("period", "6mo")
            r = requests.get(f"{STOCK_API_BASE}/stock/{arguments['stock_id']}/technical?period={period}", timeout=15)
            result = r.json()

        elif name == "get_stock_signal":
            r = requests.get(f"{STOCK_API_BASE}/stock/{arguments['stock_id']}/signal", timeout=15)
            result = r.json()

        elif name == "get_stock_chip":
            r = requests.get(f"{STOCK_API_BASE}/stock/{arguments['stock_id']}/chip", timeout=10)
            result = r.json()

        elif name == "get_stock_margin":
            r = requests.get(f"{STOCK_API_BASE}/stock/{arguments['stock_id']}/margin", timeout=10)
            result = r.json()

        elif name == "get_support_resistance":
            r = requests.get(f"{STOCK_API_BASE}/stock/{arguments['stock_id']}/support_resistance", timeout=15)
            result = r.json()

        elif name == "get_volume_analysis":
            r = requests.get(f"{STOCK_API_BASE}/stock/{arguments['stock_id']}/volume_analysis", timeout=15)
            result = r.json()

        elif name == "get_valuation":
            r = requests.get(f"{STOCK_API_BASE}/stock/{arguments['stock_id']}/valuation", timeout=15)
            result = r.json()

        elif name == "get_financials":
            r = requests.get(f"{STOCK_API_BASE}/stock/{arguments['stock_id']}/financials", timeout=15)
            result = r.json()

        elif name == "get_revenue":
            r = requests.get(f"{STOCK_API_BASE}/stock/{arguments['stock_id']}/revenue", timeout=15)
            result = r.json()

        elif name == "get_market":
            r = requests.get(f"{STOCK_API_BASE}/market", timeout=10)
            result = r.json()

        else:
            result = {"error": f"未知工具：{name}"}

        import json
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

    except Exception as e:
        return [TextContent(type="text", text=f"錯誤：{str(e)}")]

# ── 啟動 ──────────────────────────────────────────────────────────────────────

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())