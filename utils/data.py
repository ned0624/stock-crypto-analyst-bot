import yfinance as yf
import requests
import pandas as pd
import ta
import threading
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings("ignore")

_symbol_cache: dict = {}
_symbol_cache_lock = threading.Lock()

def get_tw_stock_symbol(stock_id: str) -> tuple:
    """回傳 (symbol, market)，market 為 'TW' 或 'TWO'"""
    stock_id = stock_id.strip()

    # 已有 suffix 的情況
    if stock_id.endswith(".TWO"):
        return stock_id, "TWO"
    if stock_id.endswith(".TW"):
        return stock_id, "TW"

    # 查快取（無鎖快速路徑）
    if stock_id in _symbol_cache:
        return _symbol_cache[stock_id]

    # 加鎖，避免多執行緒同時呼叫 yfinance
    with _symbol_cache_lock:
        if stock_id in _symbol_cache:
            return _symbol_cache[stock_id]

        for suffix, market in [(".TW", "TW"), (".TWO", "TWO")]:
            symbol = f"{stock_id}{suffix}"
            try:
                hist = yf.Ticker(symbol).history(period="2d")
                if not hist.empty:
                    result = (symbol, market)
                    _symbol_cache[stock_id] = result
                    return result
            except Exception:
                continue

        result = (f"{stock_id}.TW", "TW")
        _symbol_cache[stock_id] = result
        return result


def get_stock_info(stock_id: str) -> dict:
    symbol, market = get_tw_stock_symbol(stock_id)
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="5d", timeout=10)  # ← 加 timeout
        if hist.empty:
            return {"error": f"找不到股票 {stock_id}"}

        current_price = float(hist["Close"].iloc[-1])
        prev_price = float(hist["Close"].iloc[-2]) if len(hist) > 1 else current_price
        change = current_price - prev_price
        change_pct = (change / prev_price) * 100

        # info 可能很慢，用 timeout 保護
        try:
            info = ticker.fast_info  # ← 改用 fast_info，比 info 快很多
            name = stock_id
            market_cap = getattr(info, 'market_cap', 0) or 0
            pe_ratio = getattr(info, 'pe_ratio', None)
            dividend_yield = None
            week52_high = getattr(info, 'year_high', None)
            week52_low = getattr(info, 'year_low', None)
        except Exception:
            name = stock_id
            market_cap = 0
            pe_ratio = None
            dividend_yield = None
            week52_high = None
            week52_low = None

        # TWSE 即時 API 補名稱
        try:
            if market == "TWO":
                ex_ch = f"otc_{stock_id}.tw"
            else:
                ex_ch = f"tse_{stock_id}.tw"
            r = requests.get(
                f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch={ex_ch}",
                headers={"User-Agent": "Mozilla/5.0"}, timeout=5
            )
            msg = r.json().get("msgArray", [])
            if msg:
                name = msg[0].get("n", stock_id)
        except Exception:
            pass

        return {
            "stock_id": stock_id,
            "symbol": symbol,
            "name": name,
            "price": round(current_price, 2),
            "change": round(change, 2),
            "change_pct": round(change_pct, 2),
            "volume": int(hist["Volume"].iloc[-1]),
            "high": float(hist["High"].iloc[-1]),
            "low": float(hist["Low"].iloc[-1]),
            "open": float(hist["Open"].iloc[-1]),
            "market_cap": market_cap,
            "pe_ratio": pe_ratio,
            "dividend_yield": dividend_yield,
            "52w_high": week52_high,
            "52w_low": week52_low,
            "revenue_growth": None,
            "sector": "",
            "industry": "",
        }
    except Exception as e:
        return {"error": str(e)}


def get_stock_history(stock_id: str, period: str = "6mo", interval: str = "1d") -> pd.DataFrame:
    symbol, _ = get_tw_stock_symbol(stock_id)
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


def get_twse_chip_data(stock_id: str, market: str = "TW") -> dict:
    try:
        for days_back in range(0, 10):
            date = datetime.now() - timedelta(days=days_back)
            if date.weekday() >= 5:
                continue
            date_str = date.strftime("%Y%m%d")

            if market == "TWO":
                roc_date = f"{date.year - 1911}/{date.month:02d}/{date.day:02d}"
                url = "https://www.tpex.org.tw/web/stock/3insti/daily_trade/3itrade_hedge_result.php"
                params = {"l": "zh-tw", "se": "EW", "t": "D", "d": roc_date, "s": "0,asc"}
                resp = requests.get(url, params=params, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
                data = resp.json()
                tables = data.get("tables", [])
                rows = tables[0].get("data", []) if tables else []
                if not rows:
                    continue
            else:
                url = f"https://www.twse.com.tw/rwd/zh/fund/T86?date={date_str}&selectType=ALLBUT0999&response=json"
                resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
                data = resp.json()
                if data.get("stat") != "OK" or not data.get("data"):
                    continue
                rows = data["data"]

            for row in rows:
                if str(row[0]).strip() == stock_id:
                    try:
                        if market == "TWO":
                            def to_int_tpex(s):
                                return int(str(s).replace(",", "").replace(" ", "")) // 1000
                            return {
                                "date": date_str,
                                "foreign_net": to_int_tpex(row[4]),
                                "trust_net":   to_int_tpex(row[13]),
                                "dealer_net":  to_int_tpex(row[22]),
                                "total_net":   to_int_tpex(row[23]),
                            }
                        else:
                            def to_int(s):
                                return int(s.replace(",", "").replace(" ", "")) // 1000
                            return {
                                "date": date_str,
                                "foreign_net": to_int(row[4]),
                                "trust_net":   to_int(row[10]),
                                "dealer_net":  to_int(row[11]),
                                "total_net":   to_int(row[18]),
                            }
                    except Exception as e:
                        print(f"[chip 解析錯誤] {str(e)}, row={row}")
                    break

        return {"error": "近10個交易日無資料"}
    except Exception as e:
        return {"error": str(e)}


def get_margin_trading(stock_id: str, market: str = "TW") -> dict:
    try:
        for days_back in range(0, 10):
            date = datetime.now() - timedelta(days=days_back)
            if date.weekday() >= 5:
                continue
            date_str = date.strftime("%Y%m%d")

            if market == "TWO":
                roc_date = f"{date.year - 1911}/{date.month:02d}/{date.day:02d}"
                url = "https://www.tpex.org.tw/web/stock/margin_trading/margin_balance/margin_bal_result.php"
                params = {"l": "zh-tw", "d": roc_date, "s": "0,asc"}
                resp = requests.get(url, params=params, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
                data = resp.json()
                tables = data.get("tables", [])
                rows = tables[0].get("data", []) if tables else []
                if not rows:
                    continue
            else:
                url = f"https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?date={date_str}&selectType=ALL&response=json"
                resp = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
                data = resp.json()
                tables = data.get("tables", [])
                # tables[0]=信用交易統計彙總, tables[1]=每支股票融資融券明細
                rows = tables[1].get("data", []) if len(tables) > 1 else []
                print(f"[margin] {date_str} stat={data.get('stat')} rows={len(rows)}")
                if data.get("stat") != "OK" or not rows:
                    continue

            for row in rows:
                if str(row[0]).strip() == stock_id:
                    if market == "TWO":
                        return {
                            "date": date_str,
                            "margin_buy":     int(str(row[3]).replace(",", "")),
                            "margin_sell":    int(str(row[4]).replace(",", "")),
                            "margin_balance": int(str(row[6]).replace(",", "")),
                            "short_sell":     int(str(row[11]).replace(",", "")),
                            "short_buy":      int(str(row[12]).replace(",", "")),
                            "short_balance":  int(str(row[14]).replace(",", "")),
                        }
                    else:
                        # 新格式 fields: [代號,名稱,融資買進,融資賣出,現金償還,前日餘額,今日餘額,限額,融券買進,融券賣出,現券償還,前日餘額,今日餘額,限額,資券互抵,註記]
                        return {
                            "date": date_str,
                            "margin_buy":     int(str(row[2]).replace(",", "")),
                            "margin_sell":    int(str(row[3]).replace(",", "")),
                            "margin_balance": int(str(row[6]).replace(",", "")),
                            "short_sell":     int(str(row[9]).replace(",", "")),
                            "short_buy":      int(str(row[8]).replace(",", "")),
                            "short_balance":  int(str(row[12]).replace(",", "")),
                        }

        return {}
    except Exception as e:
        print(f"[margin 錯誤] {str(e)}")
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