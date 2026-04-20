import numpy as np
import requests
from datetime import datetime, timedelta
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from utils.data import (
    get_stock_info, get_stock_history,
    get_technical_indicators, get_twse_chip_data,
    get_margin_trading, get_market_summary, analyze_signals
)

app = FastAPI(title="股票分析 API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def clean(obj):
    """把 numpy 型別全部轉成 Python 原生型別"""
    if isinstance(obj, dict):
        return {k: clean(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean(v) for v in obj]
    elif isinstance(obj, (np.integer,)):
        return int(obj)
    elif isinstance(obj, (np.floating,)):
        return None if np.isnan(obj) else float(obj)
    elif isinstance(obj, (np.bool_,)):
        return bool(obj)
    else:
        return obj

"""
股票分析 API — 工具清單
═══════════════════════════════════════════════

【台股 endpoints】
GET /stock/{stock_id}                  基本資料：現價、漲跌、PE、殖利率、市值
GET /stock/{stock_id}/history          K線歷史資料
GET /stock/{stock_id}/technical        技術指標：RSI、MACD、KD、MA5/20/60
GET /stock/{stock_id}/signal           技術訊號分析和綜合評分
GET /stock/{stock_id}/chip             三大法人籌碼：外資、投信、自營商
GET /stock/{stock_id}/margin           融資融券餘額
GET /stock/{stock_id}/support_resistance 支撐壓力位：近期高低點、布林通道、52週高低
GET /stock/{stock_id}/volume_analysis  量價分析：量比、爆量天數、價量關係
GET /stock/{stock_id}/valuation        估值：PE、PB、PS、ROE、ROA、毛利率
GET /stock/{stock_id}/financials       財報：季報、年報、EPS
GET /stock/{stock_id}/revenue          營收趨勢：季度營收和年增率

【美股 endpoints】
GET /us/{symbol}                       基本資料：現價、漲跌、PE、分析師評等
GET /us/{symbol}/technical             技術指標：RSI、MACD、KD、MA
GET /us/{symbol}/signal                技術訊號和綜合評分
GET /us/{symbol}/valuation             估值：PE、PB、ROE、目標價、分析師評等
GET /us/{symbol}/financials            財報：季報、年報

【大盤 endpoints】
GET /market                            台股加權指數現況

【加密貨幣 endpoints】
GET /crypto/{symbol}                   基本資料：現價、漲跌、市值
GET /crypto/{symbol}/kline             K線歷史資料
GET /crypto/{symbol}/funding_rate      資金費率和情緒
GET /crypto/{symbol}/open_interest     未平倉量和趨勢
GET /crypto/{symbol}/long_short        多空比：全局、頂尖交易員、大戶持倉

═══════════════════════════════════════════════
資料來源：
- 台股：yfinance、TWSE 官方 API
- 美股：yfinance
- 加密貨幣：Binance API、CoinGecko API
═══════════════════════════════════════════════
"""

@app.get("/")
def root():
    return {"status": "ok", "message": "股票分析 API 運行中"}

@app.get("/stock/{stock_id}")
def stock_info(stock_id: str):
    return JSONResponse(clean(get_stock_info(stock_id)))

@app.get("/stock/{stock_id}/history")
def stock_history(stock_id: str, period: str = "6mo"):
    df = get_stock_history(stock_id, period=period)
    if df.empty:
        return JSONResponse({"error": "無法取得資料"})
    records = df.reset_index().to_dict(orient="records")
    return JSONResponse(clean(records))

@app.get("/stock/{stock_id}/technical")
def stock_technical(stock_id: str, period: str = "6mo"):
    df = get_stock_history(stock_id, period=period)
    if df.empty:
        return JSONResponse({"error": "無法取得資料"})
    df = get_technical_indicators(df)
    latest = df.iloc[-1]
    result = {
        "RSI":         latest.get("RSI"),
        "MACD":        latest.get("MACD"),
        "MACD_signal": latest.get("MACD_signal"),
        "K":           latest.get("K"),
        "D":           latest.get("D"),
        "MA5":         latest.get("MA5"),
        "MA20":        latest.get("MA20"),
        "MA60":        latest.get("MA60"),
    }
    return JSONResponse(clean(result))

@app.get("/stock/{stock_id}/signal")
def stock_signal(stock_id: str):
    info = get_stock_info(stock_id)
    if "error" in info:
        return JSONResponse(info)
    df = get_stock_history(stock_id, period="6mo")
    df = get_technical_indicators(df)
    signals = analyze_signals(df, info)
    return JSONResponse(clean(signals))

@app.get("/stock/{stock_id}/chip")
def stock_chip(stock_id: str):
    return JSONResponse(clean(get_twse_chip_data(stock_id)))

@app.get("/stock/{stock_id}/margin")
def stock_margin(stock_id: str):
    return JSONResponse(clean(get_margin_trading(stock_id)))

@app.get("/market")
def market():
    return JSONResponse(clean(get_market_summary()))

# ── Support & Resistance ──────────────────────────────────────────────────────

@app.get("/stock/{stock_id}/support_resistance")
def support_resistance(stock_id: str):
    try:
        df = get_stock_history(stock_id, period="3mo")
        if df.empty:
            return JSONResponse({"error": "無法取得資料"})
        df = get_technical_indicators(df)

        close = df["Close"]
        high = df["High"]
        low = df["Low"]
        latest = float(close.iloc[-1])

        period_high = float(high.rolling(20).max().iloc[-1])
        period_low = float(low.rolling(20).min().iloc[-1])

        bb_upper = float(df["BB_upper"].iloc[-1]) if "BB_upper" in df.columns else None
        bb_lower = float(df["BB_lower"].iloc[-1]) if "BB_lower" in df.columns else None

        # 過濾 nan/inf
        import math
        def safe_float(v):
            if v is None:
                return None
            try:
                f = float(v)
                return None if (math.isnan(f) or math.isinf(f)) else f
            except:
                return None

        bb_upper = safe_float(bb_upper)
        bb_lower = safe_float(bb_lower)
        period_high = safe_float(period_high)
        period_low = safe_float(period_low)

        df_1y = get_stock_history(stock_id, period="1y")
        week52_high = safe_float(float(df_1y["High"].max())) if not df_1y.empty else None
        week52_low = safe_float(float(df_1y["Low"].min())) if not df_1y.empty else None

        ma20 = safe_float(float(df["MA20"].iloc[-1])) if "MA20" in df.columns else None
        ma60 = safe_float(float(df["MA60"].iloc[-1])) if "MA60" in df.columns else None

        return JSONResponse(clean({
            "current_price": latest,
            "resistance": {"r1": period_high, "r2": bb_upper, "r3": week52_high},
            "support": {"s1": period_low, "s2": bb_lower, "s3": week52_low},
            "ma_reference": {"ma20": ma20, "ma60": ma60},
            "note": "r1/s1=近20日高低點, r2/s2=布林通道, r3/s3=52週高低點"
        }))
    except Exception as e:
        import traceback
        print(f"[support_resistance 錯誤] {traceback.format_exc()}")
        return JSONResponse({"error": str(e)})

# ── Volume Analysis ───────────────────────────────────────────────────────────

@app.get("/stock/{stock_id}/volume_analysis")
def volume_analysis(stock_id: str):
    try:
        df = get_stock_history(stock_id, period="3mo")
        if df.empty:
            return JSONResponse({"error": "無法取得資料"})

        import math
        def safe_float(v):
            if v is None:
                return None
            try:
                f = float(v)
                return None if (math.isnan(f) or math.isinf(f)) else f
            except:
                return None

        vol = df["Volume"]
        close = df["Close"]
        latest_vol = safe_float(vol.iloc[-1])
        avg_vol_5 = safe_float(vol.rolling(5).mean().iloc[-1])
        avg_vol_20 = safe_float(vol.rolling(20).mean().iloc[-1])
        avg_vol_60 = safe_float(vol.rolling(60).mean().iloc[-1])

        vol_ratio_5 = safe_float(latest_vol / avg_vol_5) if avg_vol_5 else 0
        vol_ratio_20 = safe_float(latest_vol / avg_vol_20) if avg_vol_20 else 0

        recent_5 = df.tail(5)
        surge_days = int((recent_5["Volume"] > (avg_vol_20 or 0) * 1.5).sum())

        price_change = safe_float(close.pct_change().iloc[-1]) or 0
        if price_change > 0 and (vol_ratio_20 or 0) > 1.2:
            price_volume = "價漲量增（強勢）"
        elif price_change > 0 and (vol_ratio_20 or 0) < 0.8:
            price_volume = "價漲量縮（注意）"
        elif price_change < 0 and (vol_ratio_20 or 0) > 1.2:
            price_volume = "價跌量增（弱勢）"
        elif price_change < 0 and (vol_ratio_20 or 0) < 0.8:
            price_volume = "價跌量縮（整理）"
        else:
            price_volume = "量價平穩"

        recent = df.tail(10)
        consecutive_up = 0
        for i in range(len(recent) - 1, -1, -1):
            if recent["Close"].iloc[i] >= recent["Open"].iloc[i]:
                consecutive_up += 1
            else:
                break
        consecutive_down = 0
        for i in range(len(recent) - 1, -1, -1):
            if recent["Close"].iloc[i] < recent["Open"].iloc[i]:
                consecutive_down += 1
            else:
                break

        return JSONResponse(clean({
            "latest_volume": latest_vol,
            "avg_volume": {"ma5": avg_vol_5, "ma20": avg_vol_20, "ma60": avg_vol_60},
            "vol_ratio": {
                "vs_ma5": round(vol_ratio_5, 2) if vol_ratio_5 else None,
                "vs_ma20": round(vol_ratio_20, 2) if vol_ratio_20 else None,
            },
            "surge_days_5": surge_days,
            "price_volume_relation": price_volume,
            "consecutive_up_days": consecutive_up,
            "consecutive_down_days": consecutive_down,
        }))
    except Exception as e:
        import traceback
        print(f"[volume_analysis 錯誤] {traceback.format_exc()}")
        return JSONResponse({"error": str(e)})


# ── Valuation ─────────────────────────────────────────────────────────────────

@app.get("/stock/{stock_id}/valuation")
def valuation(stock_id: str):
    from utils.data import get_tw_stock_symbol
    import yfinance as yf
    symbol = get_tw_stock_symbol(stock_id)
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        hist = ticker.history(period="1y")

        current_price = float(hist["Close"].iloc[-1]) if not hist.empty else None
        eps = info.get("trailingEps")
        pe = info.get("trailingPE")
        pb = info.get("priceToBook")
        ps = info.get("priceToSalesTrailing12Months")
        book_value = info.get("bookValue")
        dividend_yield = info.get("dividendYield")
        payout_ratio = info.get("payoutRatio")
        roe = info.get("returnOnEquity")
        roa = info.get("returnOnAssets")
        profit_margin = info.get("profitMargins")
        revenue_growth = info.get("revenueGrowth")
        earnings_growth = info.get("earningsGrowth")

        # 52週本益比區間估算
        if hist.empty or not eps:
            pe_high = None
            pe_low = None
        else:
            pe_high = round(float(hist["High"].max()) / eps, 2) if eps else None
            pe_low = round(float(hist["Low"].min()) / eps, 2) if eps else None

        return JSONResponse(clean({
            "current_price": current_price,
            "eps": eps,
            "pe_ratio": pe,
            "pe_52w_range": {"high": pe_high, "low": pe_low},
            "pb_ratio": pb,
            "ps_ratio": ps,
            "book_value_per_share": book_value,
            "dividend_yield": round(dividend_yield * 100, 2) if dividend_yield else None,
            "payout_ratio": round(payout_ratio * 100, 2) if payout_ratio else None,
            "roe": round(roe * 100, 2) if roe else None,
            "roa": round(roa * 100, 2) if roa else None,
            "profit_margin": round(profit_margin * 100, 2) if profit_margin else None,
            "revenue_growth_yoy": round(revenue_growth * 100, 2) if revenue_growth else None,
            "earnings_growth_yoy": round(earnings_growth * 100, 2) if earnings_growth else None,
        }))
    except Exception as e:
        return JSONResponse({"error": str(e)})


# ── Financials ────────────────────────────────────────────────────────────────

@app.get("/stock/{stock_id}/financials")
def financials(stock_id: str):
    from utils.data import get_tw_stock_symbol
    import yfinance as yf
    symbol = get_tw_stock_symbol(stock_id)
    try:
        ticker = yf.Ticker(symbol)

        # 季報
        quarterly = ticker.quarterly_financials
        quarterly_income = []
        if quarterly is not None and not quarterly.empty:
            for col in quarterly.columns[:4]:
                row = {}
                row["period"] = str(col)[:10]
                row["revenue"] = clean(quarterly.loc["Total Revenue", col]) if "Total Revenue" in quarterly.index else None
                row["gross_profit"] = clean(quarterly.loc["Gross Profit", col]) if "Gross Profit" in quarterly.index else None
                row["operating_income"] = clean(quarterly.loc["Operating Income", col]) if "Operating Income" in quarterly.index else None
                row["net_income"] = clean(quarterly.loc["Net Income", col]) if "Net Income" in quarterly.index else None
                quarterly_income.append(row)

        # 年報
        annual = ticker.financials
        annual_income = []
        if annual is not None and not annual.empty:
            for col in annual.columns[:3]:
                row = {}
                row["period"] = str(col)[:10]
                row["revenue"] = clean(annual.loc["Total Revenue", col]) if "Total Revenue" in annual.index else None
                row["gross_profit"] = clean(annual.loc["Gross Profit", col]) if "Gross Profit" in annual.index else None
                row["operating_income"] = clean(annual.loc["Operating Income", col]) if "Operating Income" in annual.index else None
                row["net_income"] = clean(annual.loc["Net Income", col]) if "Net Income" in annual.index else None
                annual_income.append(row)

        # EPS
        eps_data = []
        quarterly_eps = ticker.quarterly_earnings
        if quarterly_eps is not None and not quarterly_eps.empty:
            for idx, row in quarterly_eps.head(4).iterrows():
                eps_data.append({
                    "period": str(idx),
                    "actual_eps": clean(row.get("Earnings")),
                    "estimated_eps": clean(row.get("Estimate")),
                })

        return JSONResponse({
            "quarterly": quarterly_income,
            "annual": annual_income,
            "eps_history": eps_data,
        })
    except Exception as e:
        return JSONResponse({"error": str(e)})


# ── Revenue ───────────────────────────────────────────────────────────────────

@app.get("/stock/{stock_id}/revenue")
def revenue(stock_id: str):
    try:
        # 從 TWSE 抓月營收
        url = f"https://www.twse.com.tw/rwd/zh/afterTrading/BWIBBU_d?date=&selectType=ALL&response=json"
        
        # 用 yfinance 的季度營收做替代
        from utils.data import get_tw_stock_symbol
        import yfinance as yf
        symbol = get_tw_stock_symbol(stock_id)
        ticker = yf.Ticker(symbol)

        quarterly = ticker.quarterly_financials
        revenue_data = []

        if quarterly is not None and not quarterly.empty and "Total Revenue" in quarterly.index:
            rev_row = quarterly.loc["Total Revenue"]
            prev = None
            for col in quarterly.columns[:8]:
                val = rev_row[col]
                if val and not (isinstance(val, float) and np.isnan(val)):
                    yoy = None
                    # 找一年前同期
                    try:
                        col_date = col.to_pydatetime()
                        one_year_ago = col_date - timedelta(days=365)
                        closest = min(quarterly.columns, key=lambda x: abs((x.to_pydatetime() - one_year_ago).days))
                        prev_val = rev_row[closest]
                        if prev_val and not (isinstance(prev_val, float) and np.isnan(prev_val)) and prev_val != 0:
                            yoy = round((float(val) - float(prev_val)) / abs(float(prev_val)) * 100, 2)
                    except:
                        pass
                    revenue_data.append({
                        "period": str(col)[:10],
                        "revenue": clean(val),
                        "yoy_growth": yoy,
                    })

        return JSONResponse({"revenue_history": revenue_data})
    except Exception as e:
        return JSONResponse({"error": str(e)})

# ── Crypto Endpoints ──────────────────────────────────────────────────────────

BINANCE_BASE = "https://api.binance.com"
BINANCE_FUTURES = "https://fapi.binance.com"

@app.get("/crypto/{symbol}")
def crypto_info(symbol: str):
    symbol = symbol.upper()
    try:
        # 現貨價格
        ticker = requests.get(f"{BINANCE_BASE}/api/v3/ticker/24hr?symbol={symbol}", timeout=10).json()
        # 市值從 CoinGecko
        coin_id_map = {
            "BTCUSDT": "bitcoin", "ETHUSDT": "ethereum", "BNBUSDT": "binancecoin",
            "SOLUSDT": "solana", "XRPUSDT": "ripple", "ADAUSDT": "cardano",
            "DOGEUSDT": "dogecoin", "AVAXUSDT": "avalanche-2", "DOTUSDT": "polkadot",
            "LINKUSDT": "chainlink", "LTCUSDT": "litecoin", "UNIUSDT": "uniswap",
        }
        market_cap = None
        coin_id = coin_id_map.get(symbol)
        if coin_id:
            cg = requests.get(
                f"https://api.coingecko.com/api/v3/coins/{coin_id}?localization=false&tickers=false&community_data=false&developer_data=false",
                timeout=10
            ).json()
            market_cap = cg.get("market_data", {}).get("market_cap", {}).get("usd")

        return JSONResponse(clean({
            "symbol": symbol,
            "price": float(ticker.get("lastPrice", 0)),
            "change_pct": float(ticker.get("priceChangePercent", 0)),
            "change": float(ticker.get("priceChange", 0)),
            "high_24h": float(ticker.get("highPrice", 0)),
            "low_24h": float(ticker.get("lowPrice", 0)),
            "volume_24h": float(ticker.get("volume", 0)),
            "quote_volume_24h": float(ticker.get("quoteVolume", 0)),
            "market_cap_usd": market_cap,
        }))
    except Exception as e:
        return JSONResponse({"error": str(e)})


@app.get("/crypto/{symbol}/kline")
def crypto_kline(symbol: str, interval: str = "1d", limit: int = 90):
    symbol = symbol.upper()
    try:
        # 支援現貨和合約
        url = f"{BINANCE_FUTURES}/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}"
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            url = f"{BINANCE_BASE}/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
            resp = requests.get(url, timeout=10)
        
        data = resp.json()
        klines = []
        for k in data:
            klines.append({
                "open_time": k[0],
                "open": float(k[1]),
                "high": float(k[2]),
                "low": float(k[3]),
                "close": float(k[4]),
                "volume": float(k[5]),
                "close_time": k[6],
                "quote_volume": float(k[7]),
                "trades": k[8],
            })
        return JSONResponse(klines)
    except Exception as e:
        return JSONResponse({"error": str(e)})


@app.get("/crypto/{symbol}/funding_rate")
def crypto_funding_rate(symbol: str):
    symbol = symbol.upper()
    try:
        # 當前資金費率
        current = requests.get(
            f"{BINANCE_FUTURES}/fapi/v1/premiumIndex?symbol={symbol}", timeout=10
        ).json()
        
        # 歷史資金費率（最近8筆）
        history = requests.get(
            f"{BINANCE_FUTURES}/fapi/v1/fundingRate?symbol={symbol}&limit=8", timeout=10
        ).json()
        
        hist_data = []
        for h in history:
            hist_data.append({
                "funding_time": h.get("fundingTime"),
                "funding_rate": float(h.get("fundingRate", 0)) * 100,
            })

        current_rate = float(current.get("lastFundingRate", 0)) * 100
        next_time = current.get("nextFundingTime")
        mark_price = float(current.get("markPrice", 0))
        index_price = float(current.get("indexPrice", 0))

        # 判斷資金費率情緒
        if current_rate > 0.1:
            sentiment = "多頭過熱，注意回調風險"
        elif current_rate > 0.05:
            sentiment = "偏多，多方支付空方"
        elif current_rate < -0.05:
            sentiment = "偏空，空方支付多方"
        elif current_rate < -0.1:
            sentiment = "空頭過熱，注意反彈風險"
        else:
            sentiment = "中性"

        return JSONResponse(clean({
            "symbol": symbol,
            "current_funding_rate": round(current_rate, 4),
            "next_funding_time": next_time,
            "mark_price": mark_price,
            "index_price": index_price,
            "sentiment": sentiment,
            "history": hist_data,
        }))
    except Exception as e:
        return JSONResponse({"error": str(e)})


@app.get("/crypto/{symbol}/open_interest")
def crypto_open_interest(symbol: str):
    symbol = symbol.upper()
    try:
        # 當前未平倉量
        oi = requests.get(
            f"{BINANCE_FUTURES}/fapi/v1/openInterest?symbol={symbol}", timeout=10
        ).json()

        # 歷史未平倉量（近30筆，每小時）
        oi_hist = requests.get(
            f"{BINANCE_FUTURES}/futures/data/openInterestHist?symbol={symbol}&period=1h&limit=24",
            timeout=10
        ).json()

        hist_data = []
        if isinstance(oi_hist, list):
            for h in oi_hist:
                hist_data.append({
                    "timestamp": h.get("timestamp"),
                    "open_interest": float(h.get("sumOpenInterest", 0)),
                    "open_interest_value": float(h.get("sumOpenInterestValue", 0)),
                })

        current_oi = float(oi.get("openInterest", 0))
        
        # 計算OI變化趨勢
        oi_trend = "無資料"
        if len(hist_data) >= 2:
            oi_change = ((hist_data[-1]["open_interest"] - hist_data[0]["open_interest"])
                        / hist_data[0]["open_interest"] * 100) if hist_data[0]["open_interest"] else 0
            if oi_change > 5:
                oi_trend = f"OI 大幅增加 {oi_change:.1f}%，市場活躍"
            elif oi_change > 0:
                oi_trend = f"OI 小幅增加 {oi_change:.1f}%"
            elif oi_change < -5:
                oi_trend = f"OI 大幅減少 {oi_change:.1f}%，倉位平掉"
            else:
                oi_trend = f"OI 小幅減少 {oi_change:.1f}%"

        return JSONResponse(clean({
            "symbol": symbol,
            "current_open_interest": current_oi,
            "trend_24h": oi_trend,
            "history_1h": hist_data,
        }))
    except Exception as e:
        return JSONResponse({"error": str(e)})


@app.get("/crypto/{symbol}/long_short")
def crypto_long_short(symbol: str):
    symbol = symbol.upper()
    try:
        # 全局多空比
        global_ratio = requests.get(
            f"{BINANCE_FUTURES}/futures/data/globalLongShortAccountRatio?symbol={symbol}&period=1h&limit=24",
            timeout=10
        ).json()

        # 頂尖交易員多空比
        top_ratio = requests.get(
            f"{BINANCE_FUTURES}/futures/data/topLongShortAccountRatio?symbol={symbol}&period=1h&limit=1",
            timeout=10
        ).json()

        # 大戶持倉多空比
        position_ratio = requests.get(
            f"{BINANCE_FUTURES}/futures/data/topLongShortPositionRatio?symbol={symbol}&period=1h&limit=1",
            timeout=10
        ).json()

        latest_global = global_ratio[-1] if isinstance(global_ratio, list) and global_ratio else {}
        latest_top = top_ratio[0] if isinstance(top_ratio, list) and top_ratio else {}
        latest_pos = position_ratio[0] if isinstance(position_ratio, list) and position_ratio else {}

        long_ratio = float(latest_global.get("longAccount", 0)) * 100
        short_ratio = float(latest_global.get("shortAccount", 0)) * 100

        if long_ratio > 65:
            sentiment = "多頭極度樂觀，注意反轉風險"
        elif long_ratio > 55:
            sentiment = "偏多"
        elif long_ratio < 35:
            sentiment = "空頭極度悲觀，注意反彈"
        elif long_ratio < 45:
            sentiment = "偏空"
        else:
            sentiment = "多空均衡"

        hist_data = []
        if isinstance(global_ratio, list):
            for h in global_ratio:
                hist_data.append({
                    "timestamp": h.get("timestamp"),
                    "long_pct": round(float(h.get("longAccount", 0)) * 100, 2),
                    "short_pct": round(float(h.get("shortAccount", 0)) * 100, 2),
                    "ratio": float(h.get("longShortRatio", 0)),
                })

        return JSONResponse(clean({
            "symbol": symbol,
            "global": {
                "long_pct": round(long_ratio, 2),
                "short_pct": round(short_ratio, 2),
                "sentiment": sentiment,
            },
            "top_traders": {
                "long_pct": round(float(latest_top.get("longAccount", 0)) * 100, 2),
                "short_pct": round(float(latest_top.get("shortAccount", 0)) * 100, 2),
            },
            "top_position": {
                "long_pct": round(float(latest_pos.get("longAccount", 0)) * 100, 2),
                "short_pct": round(float(latest_pos.get("shortAccount", 0)) * 100, 2),
            },
            "history_1h": hist_data,
        }))
    except Exception as e:
        return JSONResponse({"error": str(e)})

# ── US Stocks Endpoints ──────────────────────────────────────────────────────────

@app.get("/us/{symbol}")
def us_stock_info(symbol: str):
    import yfinance as yf
    symbol = symbol.upper()
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        hist = ticker.history(period="5d")
        if hist.empty:
            return JSONResponse({"error": f"找不到股票 {symbol}"})
        current_price = float(hist["Close"].iloc[-1])
        prev_price = float(hist["Close"].iloc[-2]) if len(hist) > 1 else current_price
        change = current_price - prev_price
        change_pct = (change / prev_price) * 100
        return JSONResponse(clean({
            "symbol": symbol,
            "name": info.get("longName", info.get("shortName", symbol)),
            "price": round(current_price, 2),
            "change": round(change, 2),
            "change_pct": round(change_pct, 2),
            "volume": hist["Volume"].iloc[-1],
            "high": hist["High"].iloc[-1],
            "low": hist["Low"].iloc[-1],
            "open": hist["Open"].iloc[-1],
            "market_cap": info.get("marketCap", 0),
            "pe_ratio": info.get("trailingPE", None),
            "dividend_yield": info.get("dividendYield", None),
            "52w_high": info.get("fiftyTwoWeekHigh", None),
            "52w_low": info.get("fiftyTwoWeekLow", None),
            "revenue_growth": info.get("revenueGrowth", None),
            "sector": info.get("sector", ""),
            "industry": info.get("industry", ""),
            "analyst_rating": info.get("recommendationKey", ""),
            "target_price": info.get("targetMeanPrice", None),
            "currency": info.get("currency", "USD"),
        }))
    except Exception as e:
        return JSONResponse({"error": str(e)})

@app.get("/us/{symbol}/technical")
def us_technical(symbol: str, period: str = "6mo"):
    import yfinance as yf
    symbol = symbol.upper()
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period)
        if df.empty:
            return JSONResponse({"error": "無法取得資料"})
        df.index = df.index.tz_localize(None)
        df = get_technical_indicators(df)
        latest = df.iloc[-1]
        return JSONResponse(clean({
            "RSI":         latest.get("RSI"),
            "MACD":        latest.get("MACD"),
            "MACD_signal": latest.get("MACD_signal"),
            "K":           latest.get("K"),
            "D":           latest.get("D"),
            "MA5":         latest.get("MA5"),
            "MA20":        latest.get("MA20"),
            "MA60":        latest.get("MA60"),
        }))
    except Exception as e:
        return JSONResponse({"error": str(e)})

@app.get("/us/{symbol}/signal")
def us_signal(symbol: str):
    import yfinance as yf
    symbol = symbol.upper()
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        hist = ticker.history(period="5d")
        if hist.empty:
            return JSONResponse({"error": "無法取得資料"})
        current_price = float(hist["Close"].iloc[-1])
        stock_info = {"price": current_price}
        df = ticker.history(period="6mo")
        df.index = df.index.tz_localize(None)
        df = get_technical_indicators(df)
        signals = analyze_signals(df, stock_info)
        return JSONResponse(clean(signals))
    except Exception as e:
        return JSONResponse({"error": str(e)})

@app.get("/us/{symbol}/valuation")
def us_valuation(symbol: str):
    import yfinance as yf
    symbol = symbol.upper()
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        hist = ticker.history(period="1y")
        current_price = float(hist["Close"].iloc[-1]) if not hist.empty else None
        eps = info.get("trailingEps")
        dividend_yield = info.get("dividendYield")
        roe = info.get("returnOnEquity")
        roa = info.get("returnOnAssets")
        profit_margin = info.get("profitMargins")
        pe_high = round(float(hist["High"].max()) / eps, 2) if not hist.empty and eps else None
        pe_low = round(float(hist["Low"].min()) / eps, 2) if not hist.empty and eps else None
        return JSONResponse(clean({
            "current_price": current_price,
            "eps": eps,
            "pe_ratio": info.get("trailingPE"),
            "pe_52w_range": {"high": pe_high, "low": pe_low},
            "pb_ratio": info.get("priceToBook"),
            "ps_ratio": info.get("priceToSalesTrailing12Months"),
            "dividend_yield": round(dividend_yield * 100, 2) if dividend_yield else None,
            "roe": round(roe * 100, 2) if roe else None,
            "roa": round(roa * 100, 2) if roa else None,
            "profit_margin": round(profit_margin * 100, 2) if profit_margin else None,
            "revenue_growth_yoy": round(info.get("revenueGrowth", 0) * 100, 2) if info.get("revenueGrowth") else None,
            "analyst_rating": info.get("recommendationKey", ""),
            "target_price": info.get("targetMeanPrice", None),
            "analyst_count": info.get("numberOfAnalystOpinions", None),
        }))
    except Exception as e:
        return JSONResponse({"error": str(e)})

@app.get("/us/{symbol}/financials")
def us_financials(symbol: str):
    import yfinance as yf
    symbol = symbol.upper()
    try:
        ticker = yf.Ticker(symbol)
        quarterly = ticker.quarterly_financials
        quarterly_income = []
        if quarterly is not None and not quarterly.empty:
            for col in quarterly.columns[:4]:
                row = {}
                row["period"] = str(col)[:10]
                row["revenue"] = clean(quarterly.loc["Total Revenue", col]) if "Total Revenue" in quarterly.index else None
                row["gross_profit"] = clean(quarterly.loc["Gross Profit", col]) if "Gross Profit" in quarterly.index else None
                row["net_income"] = clean(quarterly.loc["Net Income", col]) if "Net Income" in quarterly.index else None
                quarterly_income.append(row)

        annual = ticker.financials
        annual_income = []
        if annual is not None and not annual.empty:
            for col in annual.columns[:3]:
                row = {}
                row["period"] = str(col)[:10]
                row["revenue"] = clean(annual.loc["Total Revenue", col]) if "Total Revenue" in annual.index else None
                row["gross_profit"] = clean(annual.loc["Gross Profit", col]) if "Gross Profit" in annual.index else None
                row["net_income"] = clean(annual.loc["Net Income", col]) if "Net Income" in annual.index else None
                annual_income.append(row)

        return JSONResponse({
            "quarterly": quarterly_income,
            "annual": annual_income,
        })
    except Exception as e:
        return JSONResponse({"error": str(e)})