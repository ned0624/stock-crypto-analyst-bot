from fastapi import FastAPI, Request, HTTPException
import hashlib
import hmac
import base64
import requests
import json
import os
import time
import concurrent.futures
import re
import warnings
warnings.filterwarnings("ignore")
import vertexai
from vertexai.generative_models import GenerativeModel
import asyncio

# ── 設定 ──────────────────────────────────────────────────────────────────────
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GEMINI_PROJECT = os.getenv("GEMINI_PROJECT", "stock-analysis-493612")
GEMINI_LOCATION = os.getenv("GEMINI_LOCATION", "us-central1")
STOCK_API_BASE = "https://stock-api-618661878536.asia-east1.run.app"
DEFAULT_MODE = os.getenv("AI_MODE", "vertex")

app = FastAPI()

# ── 用戶模式管理 ──────────────────────────────────────────────────────────────
user_mode: dict = {}

def get_user_mode(user_id: str) -> str:
    return user_mode.get(user_id, DEFAULT_MODE)

def set_user_mode(user_id: str, mode: str):
    user_mode[user_id] = mode

# ── 識別輸入類型 ──────────────────────────────────────────────────────────────
COINS = ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "AVAX", "DOT", "LINK", "LTC", "UNI"]
# 常見美股代號（用於識別）
US_STOCKS = [
    "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "NVDA", "META", "TSLA",
    "AVGO", "JPM", "V", "MA", "UNH", "JNJ", "XOM", "PG", "HD", "CVX",
    "MRK", "ABBV", "PEP", "KO", "COST", "WMT", "BAC", "MCD", "AMD",
    "INTC", "QCOM", "CRM", "NFLX", "DIS", "PYPL", "UBER", "SPOT",
]

def identify_input(msg: str) -> tuple:
    clean_msg = re.sub(r'(分析|查詢|查|看|幫我|請問|告訴我|的)', '', msg).strip()
    upper = clean_msg.upper()

    # 台股代號（4-6位純數字）
    if re.fullmatch(r'\d{4,6}[A-Za-z]?', clean_msg):
        return ('stock', clean_msg)

    # 數字在句子中
    match = re.search(r'\b(\d{4,6}[A-Za-z]?)\b', clean_msg)
    if match:
        return ('stock', match.group(1))

    # 加密貨幣 XXXUSDT 格式
    if upper.endswith("USDT"):
        return ('crypto', upper)

    # 加密貨幣縮寫
    for coin in COINS:
        if coin == upper or coin in upper.split():
            return ('crypto', coin + "USDT")

    # 美股代號（純英文大寫 1-5 字母）
    if re.fullmatch(r'[A-Z]{1,5}', upper):
        return ('us_stock', upper)

    # 美股在清單裡
    for stock in US_STOCKS:
        if stock == upper:
            return ('us_stock', upper)

    # 大盤
    if any(k in msg for k in ["大盤", "加權", "指數", "台股大盤"]):
        return ('market', None)

    return ('unknown', None)

# ── 平行抓資料 ────────────────────────────────────────────────────────────────
def fetch_url(url: str, timeout: int = 10) -> dict:
    try:
        r = requests.get(url, timeout=timeout)
        print(f"[fetch] {url} → {r.status_code}")
        return r.json()
    except Exception as e:
        print(f"[fetch 失敗] {url} → {str(e)}")
        return {"error": str(e)}

def fetch_all_stock(stock_id: str) -> dict:
    urls = {
        "info":               f"{STOCK_API_BASE}/stock/{stock_id}",
        "signal":             f"{STOCK_API_BASE}/stock/{stock_id}/signal",
        "chip":               f"{STOCK_API_BASE}/stock/{stock_id}/chip",
        "technical":          f"{STOCK_API_BASE}/stock/{stock_id}/technical",
        "margin":             f"{STOCK_API_BASE}/stock/{stock_id}/margin",
        "valuation":          f"{STOCK_API_BASE}/stock/{stock_id}/valuation",
        "support_resistance": f"{STOCK_API_BASE}/stock/{stock_id}/support_resistance",
        "volume":             f"{STOCK_API_BASE}/stock/{stock_id}/volume_analysis",
        "financials":         f"{STOCK_API_BASE}/stock/{stock_id}/financials",
    }
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=9) as executor:
        futures = {executor.submit(fetch_url, url, 10): key for key, url in urls.items()}
        for future in concurrent.futures.as_completed(futures):
            key = futures[future]
            try:
                results[key] = future.result()
            except Exception as e:
                results[key] = {"error": str(e)}
    return results

def fetch_all_us_stock(symbol: str) -> dict:
    urls = {
        "info":      f"{STOCK_API_BASE}/us/{symbol}",
        "technical": f"{STOCK_API_BASE}/us/{symbol}/technical",
        "signal":    f"{STOCK_API_BASE}/us/{symbol}/signal",
        "valuation": f"{STOCK_API_BASE}/us/{symbol}/valuation",
        "financials":f"{STOCK_API_BASE}/us/{symbol}/financials",
    }
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(fetch_url, url, 10): key for key, url in urls.items()}
        for future in concurrent.futures.as_completed(futures):
            key = futures[future]
            try:
                results[key] = future.result()
            except Exception as e:
                results[key] = {"error": str(e)}
    return results

def fetch_all_crypto(symbol: str) -> dict:
    urls = {
        "info":          f"{STOCK_API_BASE}/crypto/{symbol}",
        "funding_rate":  f"{STOCK_API_BASE}/crypto/{symbol}/funding_rate",
        "open_interest": f"{STOCK_API_BASE}/crypto/{symbol}/open_interest",
        "long_short":    f"{STOCK_API_BASE}/crypto/{symbol}/long_short",
    }
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(fetch_url, url, 10): key for key, url in urls.items()}
        for future in concurrent.futures.as_completed(futures):
            key = futures[future]
            try:
                results[key] = future.result()
            except Exception as e:
                results[key] = {"error": str(e)}
    return results

# ── 格式化輸出 ────────────────────────────────────────────────────────────────
def format_stock_data(stock_id: str, data: dict) -> str:
    info = data.get("info", {})
    signal = data.get("signal", {})
    chip = data.get("chip", {})
    tech = data.get("technical", {})
    sr = data.get("support_resistance", {})
    vol = data.get("volume", {})
    margin = data.get("margin", {})
    val = data.get("valuation", {})
    fin = data.get("financials", {})

    lines = []

    # 基本資料
    name = info.get("name", stock_id)
    price = info.get("price", "N/A")
    change = info.get("change", 0)
    change_pct = info.get("change_pct", 0)
    arrow = "📈" if change >= 0 else "📉"
    lines.append(f"📊 {name} ({stock_id})")
    lines.append(f"{arrow} 股價：{price} 元（{change_pct:+.2f}%）")
    if info.get("pe_ratio"):
        div = info.get("dividend_yield", 0) or 0
        div_pct = div if div > 1 else div * 100
        lines.append(f"💰 PE：{info['pe_ratio']:.1f}　殖利率：{div_pct:.2f}%")
    if info.get("market_cap"):
        lines.append(f"🏢 市值：{info['market_cap']/1e12:.2f} 兆")
    lines.append("")

    # 估值
    if val and "error" not in val:
        val_items = []
        if val.get("pb_ratio"):
            val_items.append(f"PB：{val['pb_ratio']:.1f}")
        if val.get("roe"):
            val_items.append(f"ROE：{val['roe']:.1f}%")
        if val.get("profit_margin"):
            val_items.append(f"毛利：{val['profit_margin']:.1f}%")
        if val.get("revenue_growth_yoy"):
            val_items.append(f"營收YoY：{val['revenue_growth_yoy']:.1f}%")
        if val_items:
            lines.append(f"📈 估值　{'　'.join(val_items)}")
            lines.append("")

    # 技術指標
    if tech and "error" not in tech:
        lines.append("📉 技術指標")
        if tech.get("RSI"):
            rsi = tech["RSI"]
            rsi_label = "超買⚠️" if rsi > 70 else ("超賣✅" if rsi < 30 else "中性")
            lines.append(f"　RSI：{rsi:.1f}（{rsi_label}）")
        if tech.get("K") and tech.get("D"):
            lines.append(f"　KD：K={tech['K']:.1f} D={tech['D']:.1f}")
        if tech.get("MA5") and tech.get("MA20"):
            lines.append(f"　MA5：{tech['MA5']:.0f}　MA20：{tech['MA20']:.0f}")
        if tech.get("MA60"):
            lines.append(f"　MA60：{tech['MA60']:.0f}")
        lines.append("")

    # 技術訊號
    if signal and "error" not in signal:
        verdict = signal.get("verdict", "")
        score = signal.get("score", 0)
        lines.append(f"🎯 技術評分：{score:+d}　{verdict}")
        sigs = signal.get("signals", [])[:3]
        for s in sigs:
            icon = "📈" if s["type"] == "buy" else ("📉" if s["type"] == "sell" else "➡️")
            lines.append(f"　{icon} {s['msg']}")
        lines.append("")

    # 籌碼
    if chip and "error" not in chip and chip.get("foreign_net") is not None:
        lines.append(f"🏦 籌碼（{chip.get('date','')}）")
        lines.append(f"　外資：{chip.get('foreign_net', 0):+,} 張")
        # 外資自營商有資料才顯示
        if chip.get("foreign_si_net"):
            lines.append(f"　外資自營：{chip.get('foreign_si_net', 0):+,} 張")
        lines.append(f"　投信：{chip.get('trust_net', 0):+,} 張")
        lines.append(f"　自營商：{chip.get('dealer_net', 0):+,} 張")
        lines.append(f"　三大法人合計：{chip.get('total_net', 0):+,} 張")
        lines.append("")

    # 融資融券
    if margin and "error" not in margin:
        mb = margin.get("margin_balance", 0) or 0
        sb = margin.get("short_balance", 0) or 0
        if mb or sb:
            lines.append(f"💳 融資：{mb:,} 張　融券：{sb:,} 張")
            lines.append("")

    # 支撐壓力
    if sr and "error" not in sr:
        res = sr.get("resistance", {})
        sup = sr.get("support", {})
        if res.get("r1") and sup.get("s1"):
            lines.append(f"📌 壓力：{res.get('r1','N/A')}　支撐：{sup.get('s1','N/A')}")
            lines.append("")

    # 量價
    if vol and "error" not in vol:
        pv = vol.get("price_volume_relation", "")
        vr = vol.get("vol_ratio", {}).get("vs_ma20", 0) or 0
        if pv:
            lines.append(f"📦 量價：{pv}（均量比：{vr:.1f}x）")
            lines.append("")

    # 財報 EPS
    if fin and "error" not in fin:
        eps_list = fin.get("eps_history", [])[:2]
        if eps_list:
            lines.append("📋 近期 EPS")
            for e in eps_list:
                actual = e.get("actual_eps", "N/A")
                period = str(e.get("period", ""))[:7]
                lines.append(f"　{period}：{actual}")
            lines.append("")
    
    # 無法取得的資料
    failed = []
    if not vol or "error" in vol:
        failed.append("量價分析")
    if not sr or "error" in sr:
        failed.append("支撐壓力")
    if not margin or "error" in margin:
        failed.append("融資融券")
    if not fin or "error" in fin:
        failed.append("財報")
    if not val or "error" in val:
        failed.append("估值")
    if not chip or "error" in chip or chip.get("foreign_net") is None:
        failed.append("籌碼")

    if failed:
        lines.append(f"⚠️ 以下資料無法取得：{'、'.join(failed)}")
        lines.append("")

    lines.append("⚠️ 僅供參考，不構成投資建議")
    return "\n".join(lines)

def format_us_stock_data(symbol: str, data: dict) -> str:
    info = data.get("info", {})
    signal = data.get("signal", {})
    tech = data.get("technical", {})
    val = data.get("valuation", {})
    fin = data.get("financials", {})

    lines = []

    # 基本資料
    name = info.get("name", symbol)
    price = info.get("price", "N/A")
    change = info.get("change", 0)
    change_pct = info.get("change_pct", 0)
    arrow = "📈" if change >= 0 else "📉"
    lines.append(f"🇺🇸 {name} ({symbol})")
    lines.append(f"{arrow} 股價：${price:,.2f}（{change_pct:+.2f}%）")
    if info.get("pe_ratio"):
        lines.append(f"💰 PE：{info['pe_ratio']:.1f}")
    if info.get("market_cap"):
        lines.append(f"🏢 市值：${info['market_cap']/1e9:.1f}B")
    if info.get("sector"):
        lines.append(f"🏭 產業：{info['sector']}")

    # 分析師評等
    rating = info.get("analyst_rating", "")
    target = info.get("target_price")
    if rating or target:
        rating_emoji = {
            "buy": "🟢", "strong_buy": "🟢🟢",
            "hold": "🟡", "sell": "🔴", "strong_sell": "🔴🔴"
        }.get(rating, "⚪")
        rating_text = f"分析師：{rating_emoji} {rating}"
        if target:
            rating_text += f"　目標價：${target:.1f}"
        lines.append(rating_text)
    lines.append("")

    # 估值
    if val and "error" not in val:
        val_items = []
        if val.get("pb_ratio"):
            val_items.append(f"PB：{val['pb_ratio']:.1f}")
        if val.get("roe"):
            val_items.append(f"ROE：{val['roe']:.1f}%")
        if val.get("profit_margin"):
            val_items.append(f"毛利：{val['profit_margin']:.1f}%")
        if val.get("revenue_growth_yoy"):
            val_items.append(f"營收YoY：{val['revenue_growth_yoy']:.1f}%")
        if val_items:
            lines.append(f"📈 估值　{'　'.join(val_items)}")
            lines.append("")

    # 技術指標
    if tech and "error" not in tech:
        lines.append("📉 技術指標")
        if tech.get("RSI"):
            rsi = tech["RSI"]
            rsi_label = "超買⚠️" if rsi > 70 else ("超賣✅" if rsi < 30 else "中性")
            lines.append(f"　RSI：{rsi:.1f}（{rsi_label}）")
        if tech.get("K") and tech.get("D"):
            lines.append(f"　KD：K={tech['K']:.1f} D={tech['D']:.1f}")
        if tech.get("MA5") and tech.get("MA20"):
            lines.append(f"　MA5：{tech['MA5']:.1f}　MA20：{tech['MA20']:.1f}")
        lines.append("")

    # 技術訊號
    if signal and "error" not in signal:
        verdict = signal.get("verdict", "")
        score = signal.get("score", 0)
        lines.append(f"🎯 技術評分：{score:+d}　{verdict}")
        sigs = signal.get("signals", [])[:3]
        for s in sigs:
            icon = "📈" if s["type"] == "buy" else ("📉" if s["type"] == "sell" else "➡️")
            lines.append(f"　{icon} {s['msg']}")
        lines.append("")

    # 財報
    if fin and "error" not in fin:
        quarterly = fin.get("quarterly", [])[:2]
        if quarterly:
            lines.append("📋 近期季報（美元）")
            for q in quarterly:
                period = str(q.get("period", ""))[:7]
                rev = q.get("revenue")
                net = q.get("net_income")
                rev_str = f"${rev/1e9:.1f}B" if rev else "N/A"
                net_str = f"${net/1e9:.1f}B" if net else "N/A"
                lines.append(f"　{period}　營收：{rev_str}　淨利：{net_str}")
            lines.append("")

    # 無法取得的資料
    failed = []
    if not tech or "error" in tech:
        failed.append("技術指標")
    if not val or "error" in val:
        failed.append("估值")
    if not fin or "error" in fin:
        failed.append("財報")
    if failed:
        lines.append(f"⚠️ 以下資料無法取得：{'、'.join(failed)}")
        lines.append("")

    lines.append("⚠️ 僅供參考，不構成投資建議")
    return "\n".join(lines)

def format_crypto_data(symbol: str, data: dict) -> str:
    info = data.get("info", {})
    fr = data.get("funding_rate", {})
    oi = data.get("open_interest", {})
    ls = data.get("long_short", {})

    coin = symbol.replace("USDT", "")
    lines = []

    price = info.get("price", "N/A")
    change_pct = info.get("change_pct", 0)
    arrow = "📈" if change_pct >= 0 else "📉"
    lines.append(f"₿ {coin}/USDT")
    lines.append(f"{arrow} 價格：${price:,.2f}（{change_pct:+.2f}%）")
    if info.get("high_24h"):
        lines.append(f"　24h 高：${info['high_24h']:,.2f}　低：${info['low_24h']:,.2f}")
    if info.get("market_cap_usd"):
        lines.append(f"🏢 市值：${info['market_cap_usd']/1e9:.1f}B")
    lines.append("")

    if fr and "error" not in fr:
        rate = fr.get("current_funding_rate", 0)
        sentiment = fr.get("sentiment", "")
        rate_icon = "🔴" if rate > 0.05 else ("🟢" if rate < -0.05 else "🟡")
        lines.append(f"💸 資金費率：{rate:+.4f}% {rate_icon}")
        lines.append(f"　{sentiment}")
        lines.append("")

    if oi and "error" not in oi:
        current_oi = oi.get("current_open_interest", 0)
        trend = oi.get("trend_24h", "")
        lines.append(f"📊 未平倉量：{current_oi:,.0f}")
        if trend:
            lines.append(f"　{trend}")
        lines.append("")

    if ls and "error" not in ls:
        g = ls.get("global", {})
        long_pct = g.get("long_pct", 0)
        short_pct = g.get("short_pct", 0)
        sentiment = g.get("sentiment", "")
        lines.append(f"⚖️ 多空比")
        lines.append(f"　多：{long_pct:.1f}%　空：{short_pct:.1f}%")
        lines.append(f"　{sentiment}")
        top = ls.get("top_traders", {})
        if top.get("long_pct"):
            lines.append(f"　頂尖交易員：多 {top['long_pct']:.1f}% / 空 {top['short_pct']:.1f}%")
        lines.append("")

    lines.append("⚠️ 僅供參考，不構成投資建議")
    return "\n".join(lines)


def format_market_data(data: dict) -> str:
    lines = []
    taiex = data.get("taiex", "N/A")
    change = data.get("taiex_change", 0)
    change_pct = data.get("taiex_change_pct", 0)
    arrow = "📈" if change >= 0 else "📉"
    lines.append(f"📊 台股加權指數")
    lines.append(f"{arrow} {taiex:,.2f}（{change_pct:+.2f}%）")
    lines.append("⚠️ 僅供參考")
    return "\n".join(lines)

# ── AI 呼叫 ───────────────────────────────────────────────────────────────────
def call_claude(prompt: str) -> str:
    import anthropic
    claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    for attempt in range(3):
        try:
            response = claude.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=400,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            print(f"[Claude] 錯誤 attempt {attempt}：{str(e)}")
            if attempt < 2:
                time.sleep(3)
                continue
            return ""

def call_vertex(prompt: str) -> str:
    for attempt in range(3):
        try:
            model = GenerativeModel("gemini-2.5-flash-lite")
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            print(f"[Vertex] 錯誤 attempt {attempt}：{str(e)}")
            if attempt < 2:
                time.sleep(3)
                continue
            return ""

def call_ai(prompt: str, mode: str) -> str:
    if mode == "claude_api":
        return call_claude(prompt)
    return call_vertex(prompt)

# ── AI 總結 ───────────────────────────────────────────────────────────────────
def ai_summary(raw: dict, input_type: str, mode: str) -> str:
    type_name = {
        "stock": "台股",
        "us_stock": "美股",
        "crypto": "加密貨幣"
    }.get(input_type, "股票")
    
    prompt = f"""根據以下{type_name}資料給出2-3句簡短總結和操作建議。
不用重複資料數字，只給結論和建議。
不能使用markdown符號，用emoji，繁體中文。

資料：{json.dumps(raw, ensure_ascii=False)}"""

    print(f"[AI Summary] 開始，模式：{mode}")
    result = call_ai(prompt, mode)
    print(f"[AI Summary] 結果長度：{len(result) if result else 0}")

    if result:
        mode_label = {
            "vertex": "🔵 Gemini 2.5 Flash Lite",
            "claude_api": "🟠 Claude Haiku 4.5",
            "no_ai": "📊 純資料模式",
        }
        return f"\n🤖 AI 總結\n{result}\n\n─────────────\n{mode_label.get(mode, mode)}"
    return ""

# ── Line 回覆 ─────────────────────────────────────────────────────────────────
PERSISTENT_QUICK_REPLY = {
    "items": [
        {"type": "action", "action": {"type": "message", "label": "📖 說明",   "text": "說明"}},
        {"type": "action", "action": {"type": "message", "label": "🔵 Gemini", "text": "切換 gemini"}},
        {"type": "action", "action": {"type": "message", "label": "🟠 Claude", "text": "切換 claude"}},
        {"type": "action", "action": {"type": "message", "label": "⚡ 純資料", "text": "切換 純資料"}},
    ]
}

def reply_to_line(reply_token: str, text: str = None, messages: list = None):
    if messages is None:
        if len(text) > 4990:
            text = text[:4990] + "..."
        messages = [{"type": "text", "text": text}]
    if "quickReply" not in messages[-1]:
        messages[-1]["quickReply"] = PERSISTENT_QUICK_REPLY
    resp = requests.post(
        "https://api.line.me/v2/bot/message/reply",
        headers={
            "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
            "Content-Type": "application/json"
        },
        json={"replyToken": reply_token, "messages": messages}
    )
    print(f"Line reply status: {resp.status_code}")

def reply_or_push(reply_token: str, user_id: str, text: str = None, messages: list = None):
    if messages is None:
        if len(text) > 4990:
            text = text[:4990] + "..."
        messages = [{"type": "text", "text": text}]
    if "quickReply" not in messages[-1]:
        messages[-1]["quickReply"] = PERSISTENT_QUICK_REPLY
    resp = requests.post(
        "https://api.line.me/v2/bot/message/reply",
        headers={
            "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
            "Content-Type": "application/json"
        },
        json={"replyToken": reply_token, "messages": messages}
    )
    print(f"Line reply status: {resp.status_code}")

    if resp.status_code != 200:
        print(f"[Reply 失敗] 改用 push，原因：{resp.text}")
        text_content = messages[0].get("text", "") if messages else (text or "")
        if text_content:
            push_resp = requests.post(
                "https://api.line.me/v2/bot/message/push",
                headers={
                    "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
                    "Content-Type": "application/json"
                },
                json={"to": user_id, "messages": [{"type": "text", "text": text_content}]}
            )
            print(f"Line push status: {push_resp.status_code}")

# ── 指令處理 ──────────────────────────────────────────────────────────────────
def reply_mode_menu(reply_token: str, user_id: str):
    current = get_user_mode(user_id)
    names = {
        "vertex": "Vertex AI（Gemini）",
        "claude_api": "Claude API（Haiku）",
        "no_ai": "純資料模式"
    }
    reply_to_line(reply_token, messages=[{
        "type": "text",
        "text": f"🤖 目前模式：{names.get(current, current)}\n請選擇要切換的模式：",
        "quickReply": {"items": [
            {"type": "action", "action": {"type": "message", "label": "🔵 Vertex（Gemini）", "text": "切換 gemini"}},
            {"type": "action", "action": {"type": "message", "label": "🟠 Claude（Haiku）", "text": "切換 claude"}},
            {"type": "action", "action": {"type": "message", "label": "📊 純資料（最快）", "text": "切換 純資料"}},
        ]}
    }])

def reply_help_menu(reply_token: str):
    reply_to_line(reply_token, messages=[{
        "type": "text",
        "text": ("📖 使用說明\n\n"
                "查詢台股：輸入股票代號\n"
                "例：2330、2317、0050\n\n"
                "查詢美股：輸入英文代號\n"
                "例：AAPL、NVDA、TSLA\n\n"
                "查詢加密貨幣：輸入幣種\n"
                "例：BTC、ETHUSDT\n\n"
                "查大盤：輸入「大盤」\n\n"
                "⚙️ 模式：\n"
                "🔵 Gemini\n"
                "🟠 Claude\n"
                "📊 純資料 — 最快，無AI\n\n"
                "「模式」→ 切換模式\n\n"
                "⚠️ 僅供參考，不構成投資建議"),
        "quickReply": {"items": [
            {"type": "action", "action": {"type": "message", "label": "🤖 切換模式", "text": "模式"}},
            {"type": "action", "action": {"type": "message", "label": "📈 查台積電", "text": "2330"}},
            {"type": "action", "action": {"type": "message", "label": "₿ 查比特幣", "text": "BTC"}},
            {"type": "action", "action": {"type": "message", "label": "📊 查大盤", "text": "大盤"}},
        ]}
    }])

def handle_command(user_id: str, msg: str, reply_token: str = None):
    m = msg.strip().lower()

    if m in ["模式", "mode", "/mode"]:
        if reply_token:
            reply_mode_menu(reply_token, user_id)
            return "HANDLED"

    if m in ["切換 gemini", "/gemini", "gemini模式"]:
        set_user_mode(user_id, "vertex")
        if reply_token:
            reply_to_line(reply_token, messages=[{
                "type": "text",
                "text": "✅ 已切換到 Vertex AI（Gemini）模式",
                "quickReply": {"items": [
                    {"type": "action", "action": {"type": "message", "label": "📈 查台積電", "text": "2330"}},
                    {"type": "action", "action": {"type": "message", "label": "₿ 查比特幣", "text": "BTCUSDT"}},
                    {"type": "action", "action": {"type": "message", "label": "📊 查大盤", "text": "大盤"}},
                ]}
            }])
            return "HANDLED"

    if m in ["切換 claude", "/claude", "claude模式"]:
        if not ANTHROPIC_API_KEY:
            return "❌ 未設定 Claude API Key"
        set_user_mode(user_id, "claude_api")
        if reply_token:
            reply_to_line(reply_token, messages=[{
                "type": "text",
                "text": "✅ 已切換到 Claude API（Haiku）模式",
                "quickReply": {"items": [
                    {"type": "action", "action": {"type": "message", "label": "📈 查台積電", "text": "2330"}},
                    {"type": "action", "action": {"type": "message", "label": "₿ 查比特幣", "text": "BTCUSDT"}},
                    {"type": "action", "action": {"type": "message", "label": "📊 查大盤", "text": "大盤"}},
                ]}
            }])
            return "HANDLED"

    if m in ["切換 純資料", "純資料", "/純資料", "no_ai", "/no_ai"]:
        set_user_mode(user_id, "no_ai")
        if reply_token:
            reply_to_line(reply_token, messages=[{
                "type": "text",
                "text": "✅ 已切換到純資料模式\n不使用 AI，速度最快 ⚡",
                "quickReply": {"items": [
                    {"type": "action", "action": {"type": "message", "label": "📈 查台積電", "text": "2330"}},
                    {"type": "action", "action": {"type": "message", "label": "₿ 查比特幣", "text": "BTC"}},
                    {"type": "action", "action": {"type": "message", "label": "📊 查大盤", "text": "大盤"}},
                ]}
            }])
            return "HANDLED"

    if m in ["說明", "help", "/help", "?", "幫助", "/幫助"]:
        if reply_token:
            reply_help_menu(reply_token)
            return "HANDLED"

    return None

# ── 資料驗證 ──────────────────────────────────────────────────────────────────
def is_data_valid(data: dict, input_type: str) -> bool:
    if input_type in ["stock", "us_stock"]:
        info = data.get("info", {})
        if "error" in info:
            return False
        if info.get("price") in [None, "N/A"]:
            return False
        return True
    elif input_type == "crypto":
        info = data.get("info", {})
        if "error" in info:
            return False
        if info.get("price") in [None, "N/A", 0]:
            return False
        return True
    return False

# ── 主要處理流程 ──────────────────────────────────────────────────────────────
def process_and_reply(user_msg: str, reply_token: str, user_id: str):
    print(f"=== 開始處理：{user_msg} ===")

    mode = get_user_mode(user_id)
    if mode == "vertex" and not GEMINI_PROJECT:
        mode = "no_ai"
    if mode == "claude_api" and not ANTHROPIC_API_KEY:
        mode = "no_ai"
    print(f"[模式] {mode}")

    try:
        cmd_reply = handle_command(user_id, user_msg, reply_token)
        if cmd_reply == "HANDLED":
            return
        if cmd_reply:
            reply_or_push(reply_token, user_id, text=cmd_reply)
            return

        input_type, value = identify_input(user_msg)
        print(f"[識別] 類型：{input_type}，值：{value}")

        if input_type == "stock":
            data = fetch_all_stock(value)

            if not is_data_valid(data, "stock"):
                reply_to_line(reply_token, text=f"❌ 無法取得 {value} 的資料\n請確認股票代號是否正確")
                return

            if mode == "no_ai":
                reply_or_push(reply_token, user_id, text=format_stock_data(value, data))
            else:
                with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                    future_format = executor.submit(format_stock_data, value, data)
                    future_ai = executor.submit(ai_summary, data, "stock", mode)
                    formatted = future_format.result()
                    summary = future_ai.result()  # 不設 timeout

                combined = f"{formatted}\n\n{summary}" if summary else formatted
                reply_or_push(reply_token, user_id, text=combined)
        
        elif input_type == "us_stock":
            data = fetch_all_us_stock(value)

            if not is_data_valid(data, "us_stock"):
                reply_to_line(reply_token, text=f"❌ 無法取得 {value} 的資料\n請確認美股代號是否正確")
                return

            if mode == "no_ai":
                reply_or_push(reply_token, user_id, text=format_us_stock_data(value, data))
            else:
                with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                    future_format = executor.submit(format_us_stock_data, value, data)
                    future_ai = executor.submit(ai_summary, data, "us_stock", mode)
                    formatted = future_format.result()
                    summary = future_ai.result()

                combined = f"{formatted}\n\n{summary}" if summary else formatted
                reply_or_push(reply_token, user_id, text=combined)

        elif input_type == "crypto":
            data = fetch_all_crypto(value)

            if not is_data_valid(data, "crypto"):
                reply_to_line(reply_token, text=f"❌ 無法取得 {value} 的資料\n請確認幣種代號是否正確")
                return

            if mode == "no_ai":
                reply_or_push(reply_token, user_id, text=format_crypto_data(value, data))
            else:
                with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                    future_format = executor.submit(format_crypto_data, value, data)
                    future_ai = executor.submit(ai_summary, data, "crypto", mode)
                    formatted = future_format.result()
                    summary = future_ai.result()  # 不設 timeout

                combined = f"{formatted}\n\n{summary}" if summary else formatted
                reply_or_push(reply_token, user_id, text=combined)

        elif input_type == "market":
            data = fetch_url(f"{STOCK_API_BASE}/market")
            reply_or_push(reply_token, user_id, text=format_market_data(data))

        else:
            reply_or_push(reply_token, user_id, messages=[{
                "type": "text",
                "text": "😅 我不太理解你的問題\n\n可以試試：\n📈 股票代號：2330\n₿ 加密貨幣：BTC\n📊 大盤：大盤",
                "quickReply": {"items": [
                    {"type": "action", "action": {"type": "message", "label": "📈 查台積電", "text": "2330"}},
                    {"type": "action", "action": {"type": "message", "label": "₿ 查比特幣", "text": "BTC"}},
                    {"type": "action", "action": {"type": "message", "label": "📊 查大盤", "text": "大盤"}},
                    {"type": "action", "action": {"type": "message", "label": "📖 說明", "text": "幫助"}},
                ]}
            }])

    except Exception as e:
        print(f"=== 錯誤：{str(e)} ===")
        import traceback
        print(traceback.format_exc())
        try:
            reply_or_push(reply_token, user_id, text=f"發生錯誤：{str(e)[:100]}")
        except:
            pass

# ── Webhook ───────────────────────────────────────────────────────────────────
def verify_signature(body: bytes, signature: str) -> bool:
    h = hmac.new(LINE_CHANNEL_SECRET.encode("utf-8"), body, hashlib.sha256).digest()
    return hmac.compare_digest(base64.b64encode(h).decode("utf-8"), signature)

@app.on_event("startup")
async def startup_event():
    print("[Startup] 初始化 Vertex AI...")
    try:
        vertexai.init(project=GEMINI_PROJECT, location=GEMINI_LOCATION)
        model = GenerativeModel("gemini-2.5-flash-lite")
        print("[Startup] Vertex AI 初始化完成")
    except Exception as e:
        print(f"[Startup] Vertex AI 初始化失敗：{str(e)}")

@app.post("/webhook")
async def webhook(request: Request):
    signature = request.headers.get("X-Line-Signature", "")
    body = await request.body()
    if not verify_signature(body, signature):
        raise HTTPException(status_code=400, detail="Invalid signature")

    events = json.loads(body)["events"]
    print(f"=== 收到 {len(events)} 個事件 ===")

    for event in events:
        if event["type"] == "message" and event["message"]["type"] == "text":
            user_msg = event["message"]["text"]
            reply_token = event["replyToken"]
            user_id = event["source"]["userId"]
            await asyncio.to_thread(process_and_reply, user_msg, reply_token, user_id)
    
        elif event["type"] == "follow":
            reply_token = event["replyToken"]
            reply_to_line(reply_token, messages=[{
                "type": "text",
                "text": "👋 歡迎加入！\n\n輸入股票代號即可查詢\n例：2330、AAPL、BTC\n\n輸入「說明」查看完整功能",
                "quickReply": PERSISTENT_QUICK_REPLY
        }])

    return {"status": "ok"}

@app.get("/")
def root():
    return {"status": f"Line Bot Agent 運行中（預設模式：{DEFAULT_MODE}）"}