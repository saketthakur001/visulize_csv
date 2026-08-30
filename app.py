import base64
import hashlib
import io
import re
import secrets
import contextlib
from datetime import datetime
from urllib.parse import quote

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import requests
import streamlit as st
import streamlit.components.v1 as components
from openai import OpenAI

st.set_page_config(page_title="CSV Analyst Agent", page_icon="📊", layout="wide")

st.markdown(
    """
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

        .block-container { padding-top: 2rem; max-width: 1100px; }

        h1 { font-weight: 700 !important; color: #1F2937 !important; }
        .app-subtitle { color: #6B7280; font-size: 0.95rem; margin-top: -0.6rem; margin-bottom: 1.5rem; }
        .app-header-rule { border: none; border-top: 1px solid #E5E7EB; margin: 0 0 1.5rem 0; }

        /* Card-style containers */
        div[data-testid="stVerticalBlockBorderWrapper"] {
            background: #FFFFFF;
            border: 1px solid #E5E7EB !important;
            border-radius: 12px !important;
            box-shadow: 0 1px 3px rgba(0,0,0,0.06);
            padding: 0.25rem;
        }

        section[data-testid="stSidebar"] {
            background: #FFFFFF;
            border-right: 1px solid #E5E7EB;
        }

        /* Buttons */
        .stButton > button {
            border-radius: 8px;
            font-weight: 600;
            border: 1px solid #E5E7EB;
        }
        .stButton > button[kind="primary"] {
            background-color: #4F46E5;
            border: none;
        }
        .stButton > button[kind="primary"]:hover {
            background-color: #4338CA;
        }

        /* Status pill */
        .status-pill {
            display: inline-flex; align-items: center; gap: 0.4rem;
            padding: 0.3rem 0.7rem; border-radius: 999px;
            font-weight: 600; font-size: 0.85rem;
        }
        .status-pill.connected { background: #ECFDF5; color: #047857; }
        .status-pill.disconnected { background: #FEF2F2; color: #B91C1C; }
        .status-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
        .status-dot.connected { background: #10B981; }
        .status-dot.disconnected { background: #EF4444; }

        /* Inputs */
        .stTextInput > div > div > input {
            border-radius: 8px;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("📊 CSV Analyst Agent")
st.markdown(
    '<div class="app-subtitle">Upload a CSV, ask a question in plain English — the agent writes pandas code, runs it, and shows the chart.</div>',
    unsafe_allow_html=True,
)
st.markdown('<hr class="app-header-rule">', unsafe_allow_html=True)


def style_chart(fig, ax):
    """Apply the app's light, indigo-accented look to a matplotlib chart."""
    fig.patch.set_facecolor("#FFFFFF")
    ax.set_facecolor("#FFFFFF")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#E5E7EB")
    ax.spines["bottom"].set_color("#E5E7EB")
    ax.tick_params(colors="#6B7280", labelsize=9)
    ax.grid(True, axis="y", color="#E5E7EB", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.title.set_color("#1F2937")
    ax.xaxis.label.set_color("#374151")
    ax.yaxis.label.set_color("#374151")
    return fig, ax


ACCENT_COLORS = ["#4F46E5", "#0EA5E9", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6"]
plt.rcParams["axes.prop_cycle"] = plt.cycler(color=ACCENT_COLORS)
plt.rcParams["font.family"] = "sans-serif"

# --- OpenRouter PKCE login (no manual API key needed) ---
# Set this to the URL this app is actually served at (must match exactly, no trailing slash).
try:
    APP_URL = st.secrets["APP_URL"]
except (FileNotFoundError, KeyError):
    APP_URL = "http://localhost:8501"


def log(message: str, level: str = "info"):
    if "log_entries" not in st.session_state:
        st.session_state.log_entries = []
    st.session_state.log_entries.append(
        {"time": datetime.now().strftime("%H:%M:%S"), "level": level, "message": message}
    )


def make_pkce_pair():
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


def exchange_code_for_key(code: str, verifier: str) -> str:
    resp = requests.post(
        "https://openrouter.ai/api/v1/auth/keys",
        json={"code": code, "code_verifier": verifier, "code_challenge_method": "S256"},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["key"]


@st.cache_data(ttl=30, show_spinner=False)
def check_connection(key: str):
    """Ping OpenRouter to confirm the key is live. Cached briefly so it isn't re-checked on every rerun."""
    if not key:
        return False, None
    try:
        resp = requests.get(
            "https://openrouter.ai/api/v1/auth/key",
            headers={"Authorization": f"Bearer {key}"},
            timeout=10,
        )
        if resp.ok:
            return True, resp.json().get("data", {})
        return False, None
    except requests.RequestException:
        return False, None


params = st.query_params
if "api_key" not in st.session_state:
    st.session_state.api_key = None

# The redirect to openrouter.ai and back is a full cross-origin page load, which kills
# the WebSocket and starts a brand-new Streamlit session — session_state from before the
# redirect is gone. OpenRouter also strips any query string we add to callback_url and
# only appends its own "code" param, so we can't round-trip the verifier through the URL
# either. Instead the verifier is stashed in the browser's localStorage (which *does*
# survive a full page reload) before the redirect, and fetched back via a tiny JS bridge
# that appends it to the URL as "v" and reloads once more, so Python can read it normally.
if not st.session_state.api_key and "code" in params:
    if "v" in params:
        log("Received OAuth redirect with code + verifier, attempting key exchange")
        if params["v"]:
            try:
                st.session_state.api_key = exchange_code_for_key(params["code"], params["v"])
                log("Key exchange succeeded", "success")
            except Exception as e:
                st.error(f"Login failed: {e}")
                log(f"Key exchange failed: {e}", "error")
        else:
            st.error("Couldn't recover the login verifier from this browser — please try logging in again.")
            log("Key exchange skipped: localStorage had no verifier", "error")
        st.query_params.clear()
    else:
        log("Received OAuth redirect with code, fetching verifier from localStorage")
        components.html(
            """
            <script>
            const v = window.localStorage.getItem('or_pkce_verifier') || '';
            const url = new URL(window.parent.location.href);
            url.searchParams.set('v', v);
            window.parent.location.replace(url.toString());
            </script>
            """,
            height=0,
        )
        st.info("Finishing login...")
        st.stop()

with st.sidebar:
    st.header("Setup")

    if st.session_state.api_key:
        connected, info = check_connection(st.session_state.api_key)
        if connected:
            st.markdown(
                '<span class="status-pill connected"><span class="status-dot connected"></span>Connected to OpenRouter LLM</span>',
                unsafe_allow_html=True,
            )
            if info and info.get("limit") is not None:
                st.caption(f"Credit limit: {info['limit']} · Used: {info.get('usage', 0)}")
        else:
            st.markdown(
                '<span class="status-pill disconnected"><span class="status-dot disconnected"></span>Not connected</span>',
                unsafe_allow_html=True,
            )
            st.caption("Key present but OpenRouter didn't validate it. Try logging out and back in.")
            log("Connection check to OpenRouter /auth/key failed", "error")
        if st.button("Log out"):
            st.session_state.api_key = None
            check_connection.clear()
            st.rerun()
    else:
        st.markdown(
            '<span class="status-pill disconnected"><span class="status-dot disconnected"></span>Not connected</span>',
            unsafe_allow_html=True,
        )
        verifier, challenge = make_pkce_pair()
        # Stash the verifier in the browser's localStorage — OpenRouter strips any query
        # string we add to callback_url, so we can't round-trip it through the URL. This
        # is re-run (and re-saved) on every rerun while logged out, which is fine — only
        # the value present at the moment the link is clicked matters.
        components.html(
            f"<script>window.localStorage.setItem('or_pkce_verifier', '{verifier}');</script>",
            height=0,
        )
        auth_url = (
            "https://openrouter.ai/auth"
            f"?callback_url={quote(APP_URL, safe='')}"
            f"&code_challenge={challenge}"
            "&code_challenge_method=S256"
        )
        # Must navigate in the SAME tab (target="_self") so the localStorage write above
        # (tied to this tab/origin) is what the redirect-back page reads.
        st.markdown(
            f'''<a href="{auth_url}" target="_self" style="
                display:block; text-align:center; padding:0.55rem 1rem; margin-top:0.5rem;
                background-color:#4F46E5; color:white; border-radius:8px;
                text-decoration:none; font-weight:600;">🔑 Log in with OpenRouter</a>''',
            unsafe_allow_html=True,
        )
        st.caption("New accounts get free credits, and free-tier models cost nothing either way.")

    api_key = st.session_state.api_key
    model = st.selectbox(
        "Model",
        [
            "google/gemini-2.0-flash-exp:free",
            "meta-llama/llama-3.3-70b-instruct:free",
            "openai/gpt-4o-mini",
            "anthropic/claude-3.5-haiku",
        ],
        index=0,
        help="Models ending in :free cost nothing to use.",
    )
    st.markdown("---")
    st.markdown("Built with Streamlit + OpenRouter")

with st.container(border=True):
    col1, col2 = st.columns([3, 1])
    with col1:
        uploaded = st.file_uploader("Upload CSV", type=["csv"])
    with col2:
        st.markdown("<div style='height:1.85rem'></div>", unsafe_allow_html=True)
        if st.button("🧪 Try demo data", use_container_width=True):
            st.session_state.use_demo = True

if "history" not in st.session_state:
    st.session_state.history = []
if "use_demo" not in st.session_state:
    st.session_state.use_demo = False

if uploaded:
    st.session_state.use_demo = False

if uploaded or st.session_state.use_demo:
    if uploaded:
        df = pd.read_csv(uploaded)
    else:
        df = pd.read_csv("sample_data/sales.csv")
        st.caption("Using demo dataset: sample sales data by region, product, and rep. Upload your own CSV to replace it.")
    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
    with st.container(border=True):
        st.subheader("Preview")
        st.dataframe(df.head(20), use_container_width=True)

        with st.expander("Columns & dtypes"):
            st.write(df.dtypes.astype(str))

    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
    with st.container(border=True):
        question = st.text_input(
            "Ask a question about this data",
            placeholder="e.g. Show me monthly revenue trend, or revenue by region as a bar chart",
        )

        go = st.button("Analyze", type="primary", disabled=not (question and api_key))

        if not api_key:
            st.info("Log in with OpenRouter in the sidebar to run the agent.")

    if go:
        client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)

        schema = f"Columns: {list(df.columns)}\nDtypes:\n{df.dtypes.to_string()}\nSample rows:\n{df.head(5).to_string()}"

        system_prompt = f"""You are a data analyst. You are given a pandas DataFrame called `df` already loaded in memory.

{schema}

Write Python code that answers the user's question. Rules:
- Use the existing variable `df` — do not redefine or reload it.
- Use matplotlib (`plt`) for any chart. Create a figure with `fig, ax = plt.subplots()` and plot on `ax`.
- Right before `st.pyplot(fig)`, call `style_chart(fig, ax)` — it's already available and applies this app's visual theme to the chart.
- End with `st.pyplot(fig)` if you made a chart, and/or `result = ...` for a tabular/scalar answer.
- Only output a single Python code block, no explanation, no markdown outside the code block.
- Keep code short and correct. Do not import pandas or matplotlib, they're already available as pd, plt, st.
"""

        log(f"Analyze requested — model={model}, question={question!r}")
        with st.spinner("Agent is writing code..."):
            try:
                resp = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": question},
                    ],
                    temperature=0,
                )
                raw = resp.choices[0].message.content
                log("LLM call succeeded", "success")
            except Exception as e:
                st.error(f"LLM call failed: {e}")
                log(f"LLM call failed: {e}", "error")
                st.stop()

        match = re.search(r"```(?:python)?\s*(.*?)```", raw, re.DOTALL)
        code = match.group(1).strip() if match else raw.strip()

        st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
        with st.container(border=True):
            st.subheader("Generated code")
            st.code(code, language="python")

            st.subheader("Result")
            safe_globals = {"df": df.copy(), "pd": pd, "plt": plt, "st": st, "style_chart": style_chart}
            stdout = io.StringIO()
            try:
                with contextlib.redirect_stdout(stdout):
                    exec(code, safe_globals)
                if stdout.getvalue():
                    st.text(stdout.getvalue())
                if "result" in safe_globals:
                    result = safe_globals["result"]
                    if isinstance(result, (pd.DataFrame, pd.Series)):
                        st.dataframe(result, use_container_width=True)
                    else:
                        st.write(result)
                log("Generated code executed successfully", "success")
            except Exception as e:
                st.error(f"Execution error: {e}")
                log(f"Execution error: {e}", "error")

        st.session_state.history.append({"question": question, "code": code})

    if st.session_state.history:
        st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
        with st.expander("History"):
            for i, h in enumerate(reversed(st.session_state.history), 1):
                st.markdown(f"**{i}. {h['question']}**")
                st.code(h["code"], language="python")
else:
    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
    with st.container(border=True):
        st.info("Upload a CSV or click \"🧪 Try demo data\" to get started.")

st.markdown("---")
entries = st.session_state.get("log_entries", [])
with st.expander(f"🪵 App logs ({len(entries)})", expanded=False):
    if not entries:
        st.caption("No events yet.")
    else:
        icons = {"info": "ℹ️", "success": "✅", "error": "🔴"}
        for e in reversed(entries[-50:]):
            st.text(f"{e['time']}  {icons.get(e['level'], '•')}  {e['message']}")
