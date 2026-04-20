# 📈 Stock & Crypto Analyst Bot

> Stock & crypto analysis bot for TW/US markets, deployed on GCP with LINE Bot and Claude Desktop MCP integration.

---

## Features

- 🇹🇼 **Taiwan Stock** — Real-time price, technical indicators, chip analysis, margin trading, financials
- 🇺🇸 **US Stock** — Price, RSI/MACD/KD, valuation, financials, analyst ratings
- ₿ **Cryptocurrency** — Price, funding rate, open interest, long/short ratio (via Binance)
- 📊 **Market Overview** — TAIEX index summary
- 🤖 **AI Summary** — Powered by Gemini (Vertex AI) or Claude API
- 💬 **LINE Bot** — Query stocks directly from LINE
- 🖥️ **Claude Desktop MCP** — Use as an MCP server with Claude Desktop

---

## Architecture

```
┌─────────────────────────────────────┐
│           Client Interfaces         │
│   LINE Bot  │  Claude Desktop MCP   │
└──────┬──────┴──────────┬────────────┘
       │                 │
       ▼                 ▼
┌─────────────────────────────────────┐
│         linebot_agent.py            │
│     FastAPI webhook handler         │
│  (Vertex AI / Claude API summary)   │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│            Stock API                │
│   FastAPI (api.py) on Cloud Run     │
│  yfinance │ TWSE API │ Binance API  │
└─────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| API Backend | FastAPI, yfinance, ta, TWSE API, Binance API |
| LINE Bot | LINE Messaging API, FastAPI webhook |
| MCP Server | Anthropic MCP SDK |
| AI Summary | Google Vertex AI (Gemini 2.5 Flash Lite) / Claude API |
| Deployment | Google Cloud Run |
| Frontend (optional) | Streamlit |

---

## Project Structure

```
stock-crypto-analyst-bot/
├── api.py                  # Stock API (FastAPI)
├── linebot_agent.py        # LINE Bot webhook handler
├── mcp_server.py           # Claude Desktop MCP server
├── app.py                  # Streamlit dashboard (optional)
├── utils/
│   └── data.py             # Data fetching & technical indicators
├── Dockerfile.api          # Docker image for API
├── Dockerfile.linebot      # Docker image for LINE Bot
├── cloudbuild.api.yaml     # GCP Cloud Build config for API
├── cloudbuild.linebot.yaml # GCP Cloud Build config for LINE Bot
└── requirements.txt
```

---

## API Endpoints

### Taiwan Stock
| Method | Endpoint | Description |
|---|---|---|
| GET | `/stock/{stock_id}` | Basic info, price, PE, dividend yield |
| GET | `/stock/{stock_id}/technical` | RSI, MACD, KD, MA5/20/60 |
| GET | `/stock/{stock_id}/signal` | Technical signals & score |
| GET | `/stock/{stock_id}/chip` | Institutional investors (foreign, trust, dealer) |
| GET | `/stock/{stock_id}/margin` | Margin trading balance |
| GET | `/stock/{stock_id}/support_resistance` | Support & resistance levels |
| GET | `/stock/{stock_id}/volume_analysis` | Volume analysis |
| GET | `/stock/{stock_id}/valuation` | PE, PB, ROE, profit margin |
| GET | `/stock/{stock_id}/financials` | Quarterly & annual financials |
| GET | `/market` | TAIEX index summary |

### US Stock
| Method | Endpoint | Description |
|---|---|---|
| GET | `/us/{symbol}` | Basic info, analyst rating, target price |
| GET | `/us/{symbol}/technical` | RSI, MACD, KD, MA |
| GET | `/us/{symbol}/signal` | Technical signals & score |
| GET | `/us/{symbol}/valuation` | PE, PB, ROE, analyst rating |
| GET | `/us/{symbol}/financials` | Quarterly & annual financials |

### Cryptocurrency
| Method | Endpoint | Description |
|---|---|---|
| GET | `/crypto/{symbol}` | Price, 24h change, market cap |
| GET | `/crypto/{symbol}/kline` | Candlestick data |
| GET | `/crypto/{symbol}/funding_rate` | Funding rate & sentiment |
| GET | `/crypto/{symbol}/open_interest` | Open interest & trend |
| GET | `/crypto/{symbol}/long_short` | Long/short ratio |

---

## Getting Started

### 1. Clone the repo

```bash
git clone https://github.com/your-username/stock-crypto-analyst-bot.git
cd stock-crypto-analyst-bot
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Set environment variables

Edit `cloudbuild.linebot.yaml`, fill in your credentials in `--set-env-vars`:

\```yaml
- --set-env-vars=LINE_CHANNEL_SECRET=your_secret,LINE_CHANNEL_ACCESS_TOKEN=your_token,ANTHROPIC_API_KEY=your_key
\```

### 4. Run locally

```bash
# Run Stock API
uvicorn api:app --reload --port 8080

# Run LINE Bot
uvicorn linebot_agent:app --reload --port 8081

# Run MCP Server (for Claude Desktop)
python mcp_server.py
```

---

## Deploy to GCP Cloud Run

```bash
# Deploy Stock API
gcloud builds submit --config cloudbuild.api.yaml

# Deploy LINE Bot
gcloud builds submit --config cloudbuild.linebot.yaml
```

---

## Claude Desktop MCP Setup

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "stock-analyst": {
      "command": "python",
      "args": ["/path/to/mcp_server.py"]
    }
  }
}
```

---

## LINE Bot Commands

| Input | Description |
|---|---|
| `2330` | Query Taiwan stock |
| `AAPL` | Query US stock |
| `BTC` / `ETHUSDT` | Query cryptocurrency |
| `大盤` | TAIEX market overview |
| `說明` | Show help menu |
| `切換 gemini` | Switch to Gemini AI mode |
| `切換 claude` | Switch to Claude AI mode |
| `切換 純資料` | Data only mode (fastest) |

---

## Data Sources

- 🇹🇼 Taiwan stocks: [yfinance](https://github.com/ranaroussi/yfinance), [TWSE Official API](https://www.twse.com.tw)
- 🇺🇸 US stocks: [yfinance](https://github.com/ranaroussi/yfinance)
- ₿ Crypto: [Binance API](https://binance-docs.github.io/apidocs/), [CoinGecko API](https://www.coingecko.com/en/api)

---

## Disclaimer

> ⚠️ 本專案提供之資料與分析僅供參考，不構成任何投資建議。投資有風險，請自行評估。
>
> All data and analysis provided are for informational purposes only and do not constitute investment advice.

---

## License

MIT License
