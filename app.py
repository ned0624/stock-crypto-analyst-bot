import streamlit as st

st.set_page_config(
    page_title="AI 股票分析師",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;700&display=swap');

    * { font-family: 'Noto Sans TC', sans-serif; }
    .main { background-color: #0d1117; }

    .metric-card {
        background: linear-gradient(135deg, #161b22 0%, #1f2937 100%);
        border: 1px solid #30363d;
        border-radius: 12px;
        padding: 20px;
        margin: 8px 0;
    }

    .tag { display:inline-block; padding:2px 10px; border-radius:20px; font-size:12px; font-weight:600; margin:2px; }
    .tag-buy     { background:rgba(63,185,80,0.15);  color:#3fb950; border:1px solid #3fb950; }
    .tag-sell    { background:rgba(248,81,73,0.15);  color:#f85149; border:1px solid #f85149; }
    .tag-neutral { background:rgba(139,148,158,0.15);color:#8b949e; border:1px solid #8b949e; }

    .signal-box {
        background: #161b22;
        border-left: 4px solid #58a6ff;
        padding: 12px 16px;
        border-radius: 0 8px 8px 0;
        margin: 8px 0;
    }

    .analysis-report {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 12px;
        padding: 24px;
        line-height: 1.8;
        color: #c9d1d9;
    }

    h1, h2, h3 { color: #e6edf3; }
    p, li { color: #8b949e; }

    [data-testid="stMetricValue"] { font-size:28px; font-weight:700; }

    .stTextInput > div > div > input {
        background-color: #21262d;
        border: 1px solid #30363d;
        color: #e6edf3;
        border-radius: 8px;
    }
    .stSelectbox > div > div {
        background-color: #21262d;
        border: 1px solid #30363d;
        color: #e6edf3;
    }

    /* ── Sidebar ── */
    div[data-testid="stSidebar"] {
        background-color: #161b22;
        border-right: 1px solid #30363d;
    }

    /* 主內容區的綠色 CTA 按鈕 */
    .main .stButton > button {
        background: linear-gradient(135deg, #238636, #2ea043) !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        padding: 10px 24px !important;
    }
    .main .stButton > button:hover {
        background: linear-gradient(135deg, #2ea043, #3fb950) !important;
    }

    /* ── Sidebar 按鈕：所有狀態灰色 ── */
    div[data-testid="stSidebar"] button,
    div[data-testid="stSidebar"] button:hover,
    div[data-testid="stSidebar"] button:focus,
    div[data-testid="stSidebar"] button:active,
    div[data-testid="stSidebar"] button:focus-visible {
        background: transparent !important;
        color: #8b949e !important;
        border: 1px solid #30363d !important;
        border-radius: 8px !important;
        font-weight: 400 !important;
        box-shadow: none !important;
        outline: none !important;
    }

    /* 選中的頁面（active page） */
    div[data-testid="stSidebar"] button[kind="primary"],
    div[data-testid="stSidebar"] button[kind="primary"]:focus,
    div[data-testid="stSidebar"] button[kind="primary"]:active,
    div[data-testid="stSidebar"] button[kind="primary"]:focus-visible {
        background: #2d333b !important;
        color: #e6edf3 !important;
        border: 1px solid #444c56 !important;
        border-left: 3px solid #58a6ff !important;
        border-radius: 0 8px 8px 0 !important;
        font-weight: 600 !important;
        box-shadow: none !important;
        outline: none !important;
    }
    div[data-testid="stSidebar"] button[kind="primary"]:hover {
        background: #373e47 !important;
        color: #e6edf3 !important;
        border-left: 3px solid #58a6ff !important;
        border-radius: 0 8px 8px 0 !important;
    }
</style>
""", unsafe_allow_html=True)


def main():
    with st.sidebar:
        st.markdown("## 📈 AI 股票分析師")
        st.markdown("---")

        if "page" not in st.session_state:
            st.session_state.page = "🏠 個股分析"

        pages = [
            ("🏠", "個股分析"),
            ("📊", "技術指標"),
            ("🏦", "籌碼分析"),
            ("📰", "市場掃描"),
            ("🤖", "AI 深度分析"),
        ]

        for icon, name in pages:
            full_name = f"{icon} {name}"
            is_active = st.session_state.page == full_name
            label = f"| {icon} {name}" if is_active else f"  {icon} {name}"
            if st.button(label, key=full_name, use_container_width=True):
                st.session_state.page = full_name
                st.rerun()

        st.markdown("---")
        st.markdown("**資料來源**")
        st.markdown("- Yahoo Finance\n- TWSE 官方 API\n- ta（技術指標）")
        st.markdown("---")
        st.caption("v1.0 · 資料僅供參考")

    page = st.session_state.page

    if page == "🏠 個股分析":
        from modules import stock_overview; stock_overview.show()
    elif page == "📊 技術指標":
        from modules import technical; technical.show()
    elif page == "🏦 籌碼分析":
        from modules import chip; chip.show()
    elif page == "📰 市場掃描":
        from modules import market_scan; market_scan.show()
    elif page == "🤖 AI 深度分析":
        from modules import ai_analysis; ai_analysis.show()


if __name__ == "__main__":
    main()