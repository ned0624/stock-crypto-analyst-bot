import yfinance as yf
import requests
import pandas as pd
import ta
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings("ignore")


def get_tw_stock_symbol(stock_id: str) -> str:
    stock_id = stock_id.strip()
    if not stock_id.endswith(".TW") and not stock_id.endswith(".TWO"):
        return f"{stock_id}.TW"
    return stock_id


def get_stock_info(stock_id: str) -> dict:
    symbol = get_tw_stock_symbol(stock_id)
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        hist = ticker.history(period="5d")
        if hist.empty:
            return {"error": f"找不到股票 {stock_id}"}
        current_price = hist["Close"].iloc[-1]
        prev_price = hist["Close"].iloc[-2] if len(hist) > 1 else current_price
        change = current_price - prev_price
        change_pct = (change / prev_price) * 100
        return {
            "stock_id": stock_id,
            "symbol": symbol,
            "name": info.get("longName", info.get("shortName", stock_id)),
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
        }
    except Exception as e:
        return {"error": str(e)}


def get_stock_history(stock_id: str, period: str = "6mo", interval: str = "1d") -> pd.DataFrame:
    symbol = get_tw_stock_symbol(stock_id)
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval=interval)
        df.index = pd.to_datetime(df.index)
        df.index = df.index.tz_localize(None)
        return df
    except Exception:
        return pd.DataFrame()


def get_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or len(df) < 20:
        return df
    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"]
    df["MA5"]  = close.rolling(5).mean()
    df["MA10"] = close.rolling(10).mean()
    df["MA20"] = close.rolling(20).mean()
    df["MA60"] = close.rolling(60).mean()
    bb = ta.volatility.BollingerBands(close, window=20, window_dev=2)
    df["BB_upper"] = bb.bollinger_hband()
    df["BB_mid"]   = bb.bollinger_mavg()
    df["BB_lower"] = bb.bollinger_lband()
    df["RSI"] = ta.momentum.RSIIndicator(close, window=14).rsi()
    macd_ind = ta.trend.MACD(close, window_slow=26, window_fast=12, window_sign=9)
    df["MACD"]        = macd_ind.macd()
    df["MACD_signal"] = macd_ind.macd_signal()
    df["MACD_hist"]   = macd_ind.macd_diff()
    stoch = ta.momentum.StochasticOscillator(high, low, close, window=9, smooth_window=3)
    df["K"] = stoch.stoch()
    df["D"] = stoch.stoch_signal()
    df["Vol_MA5"] = volume.rolling(5).mean()
    return df


def get_twse_chip_data(stock_id: str) -> dict:
    try:
        for days_back in range(0, 10):
            date = datetime.now() - timedelta(days=days_back)
            if date.weekday() >= 5:
                continue
            date_str = date.strftime("%Y%m%d")
            url = f"https://www.twse.com.tw/rwd/zh/fund/T86?date={date_str}&selectType=ALLBUT0999&response=json"
            resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            data = resp.json()

            if data.get("stat") == "OK" and data.get("data"):
                result = {"date": date_str}
                for row in data["data"]:
                    if row[0] == stock_id:
                        try:
                            def to_int(s):
                                return int(s.replace(",", "").replace(" ", "")) // 1000

                            # 外資（外陸資 + 外資自營商）
                            result["foreign_net"] = to_int(row[4])

                            # 投信
                            result["trust_net"] = to_int(row[10])  # 投信買賣超

                            # 自營商
                            result["dealer_net"] = to_int(row[11])

                            # 三大法人合計
                            result["total_net"] = to_int(row[18])  # 直接用官方合計

                        except Exception as e:
                            print(f"[chip 解析錯誤] {str(e)}, row={row}")
                        break
                return result

        return {"error": "近10個交易日無資料"}
    except Exception as e:
        return {"error": str(e)}


def get_margin_trading(stock_id: str) -> dict:
    headers = {"User-Agent": "Mozilla/5.0"}

    for days_back in range(0, 10):
        date = datetime.now() - timedelta(days=days_back)
        if date.weekday() >= 5:
            continue
        date_str = date.strftime("%Y%m%d")

        url = f"https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?date={date_str}&selectType=ALL&response=csv"
        try:
            r = requests.get(url, timeout=10, headers=headers)
            if r.status_code != 200 or len(r.content) < 100:
                continue

            text = r.content.decode("big5", errors="ignore")

            for line in text.splitlines():
                # 去掉引號和等號，取得純文字
                clean = line.replace('="', '"').strip()
                cols = [c.strip().strip('"') for c in clean.split(",")]

                if cols[0] == stock_id:
                    def to_int(s):
                        try:
                            return int(s.replace(",", ""))
                        except:
                            return 0
                        
                    margin_y = to_int(cols[5])  # 融資前日餘額
                    margin_t = to_int(cols[6])  # 融資今日餘額
                    short_sell_y = to_int(cols[11]) # 融券前日餘額
                    short_sell_t = to_int(cols[12]) # 融券今日餘額

                    return {
                        "date": date_str,                        
                        "margin_balance": margin_t - margin_y,
                        "short_balance":  short_sell_t - short_sell_y,
                    }
        except Exception as e:
            print(f"[margin 錯誤] {str(e)}")
            continue

    return {}


def get_market_summary() -> dict:
    try:
        hist = yf.Ticker("^TWII").history(period="5d")
        if not hist.empty:
            c = hist["Close"].iloc[-1]; p = hist["Close"].iloc[-2] if len(hist) > 1 else c
            chg = c - p
            return {"taiex": round(c,2), "taiex_change": round(chg,2),
                    "taiex_change_pct": round(chg/p*100,2), "taiex_volume": hist["Volume"].iloc[-1]}
    except Exception:
        pass
    return {}


def analyze_signals(df: pd.DataFrame, info: dict) -> dict:
    if df.empty or len(df) < 20:
        return {}
    latest = df.iloc[-1]; prev = df.iloc[-2]
    signals = []; score = 0
    rsi = latest.get("RSI")
    if pd.notna(rsi):
        if rsi < 30:
            signals.append({"type": "buy", "msg": f"RSI {rsi:.1f} 超賣區，技術面反彈機會"}); score += 20
        elif rsi > 70:
            signals.append({"type": "sell", "msg": f"RSI {rsi:.1f} 超買區，注意短線拉回"}); score -= 20
        else:
            signals.append({"type": "neutral", "msg": f"RSI {rsi:.1f} 中性"}); score += 5
    macd = latest.get("MACD"); ms = latest.get("MACD_signal")
    pm = prev.get("MACD"); pms = prev.get("MACD_signal")
    if all(pd.notna(v) for v in [macd, ms, pm, pms]):
        if macd > ms and pm <= pms:
            signals.append({"type": "buy", "msg": "MACD 黃金交叉，多頭訊號"}); score += 25
        elif macd < ms and pm >= pms:
            signals.append({"type": "sell", "msg": "MACD 死亡交叉，空頭訊號"}); score -= 25
        elif macd > ms:
            signals.append({"type": "buy", "msg": "MACD 多頭排列延續"}); score += 10
    ma5 = latest.get("MA5"); ma20 = latest.get("MA20"); price = latest["Close"]
    if pd.notna(ma5) and pd.notna(ma20):
        if price > ma5 > ma20:
            signals.append({"type": "buy", "msg": "均線多頭排列，趨勢向上"}); score += 15
        elif price < ma5 < ma20:
            signals.append({"type": "sell", "msg": "均線空頭排列，趨勢向下"}); score -= 15
    k = latest.get("K"); d = latest.get("D")
    if pd.notna(k) and pd.notna(d):
        if k > d and k < 20:
            signals.append({"type": "buy", "msg": f"KD 低檔黃金交叉 (K={k:.1f})"}); score += 20
        elif k < d and k > 80:
            signals.append({"type": "sell", "msg": f"KD 高檔死亡交叉 (K={k:.1f})"}); score -= 20
    vol = latest["Volume"]; vma = latest.get("Vol_MA5")
    if pd.notna(vma) and vma > 0:
        ratio = vol / vma
        if ratio > 1.5:
            signals.append({"type": "buy" if score > 0 else "sell", "msg": f"成交量爆量 {ratio:.1f}x 均量"})
    if score >= 40: v, vc = "🟢 強烈買進", "#3fb950"
    elif score >= 15: v, vc = "🟡 偏多觀望", "#d29922"
    elif score >= -15: v, vc = "⚪ 中性持平", "#8b949e"
    elif score >= -40: v, vc = "🟠 偏空觀望", "#f0883e"
    else: v, vc = "🔴 強烈賣出", "#f85149"
    return {"signals": signals, "score": score, "verdict": v, "verdict_color": vc}

def build_analysis_prompt(stock_id: str, info: dict, df, chip: dict, signals: dict) -> str:
    latest = df.iloc[-1] if not df.empty else {}
    pe = info.get("pe_ratio", "N/A")
    div_yield = f"{info['dividend_yield']*100:.2f}%" if info.get("dividend_yield") else "N/A"
    rev_growth = f"{info['revenue_growth']*100:.1f}%" if info.get("revenue_growth") else "N/A"
    rsi = round(latest.get("RSI", 0), 1) if pd.notna(latest.get("RSI")) else "N/A"
    macd = round(latest.get("MACD", 0), 4) if pd.notna(latest.get("MACD")) else "N/A"
    macd_sig = round(latest.get("MACD_signal", 0), 4) if pd.notna(latest.get("MACD_signal")) else "N/A"
    k_val = round(latest.get("K", 0), 1) if pd.notna(latest.get("K")) else "N/A"
    d_val = round(latest.get("D", 0), 1) if pd.notna(latest.get("D")) else "N/A"
    ma5 = round(latest.get("MA5", 0), 2) if pd.notna(latest.get("MA5")) else "N/A"
    ma20 = round(latest.get("MA20", 0), 2) if pd.notna(latest.get("MA20")) else "N/A"
    ma60 = round(latest.get("MA60", 0), 2) if pd.notna(latest.get("MA60")) else "N/A"
    chip_info = (f"籌碼面：\n- 外資買賣超：{chip.get('foreign_net', 'N/A'):,} 張\n"
                 f"- 投信買賣超：{chip.get('trust_net', 'N/A')} 張\n"
                 f"- 三大法人合計：{chip.get('total_net', 'N/A')} 張"
                 if chip.get("foreign_net") is not None else "籌碼面：今日資料尚未公告")
    signal_summary = "\n".join([f"- [{s['type'].upper()}] {s['msg']}" for s in signals.get("signals", [])])
    return f"""你是一位資深台股分析師，請針對以下股票數據提供專業分析報告。

股票：{info.get('name', stock_id)} ({stock_id})
收盤價：${info.get('price')}，漲跌：{info.get('change_pct', 0):+.2f}%
PE：{pe}，殖利率：{div_yield}，營收年增率：{rev_growth}
RSI：{rsi}，MACD：{macd}/Signal：{macd_sig}，K：{k_val}/D：{d_val}
MA5：{ma5}，MA20：{ma20}，MA60：{ma60}
{chip_info}
技術訊號：{signal_summary}
綜合評分：{signals.get('score', 0):+d}，結論：{signals.get('verdict', 'N/A')}

請用繁體中文依照以下格式回答：
## 📊 整體評估
## 🔍 技術面分析
## 🏦 籌碼面分析
## 💰 基本面觀點
## ⚠️ 風險提示
## 🎯 操作建議（含支撐壓力參考價）

注意：僅供參考，不構成投資建議。"""