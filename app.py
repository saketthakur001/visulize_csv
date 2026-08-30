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
from streamlit_javascript import st_javascript
from openai import OpenAI

st.set_page_config(page_title="CSV Analyst Agent", page_icon="📊", layout="wide")

st.markdown(
    """
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #FAFAFA;
            --surface: #FFFFFF;
            --border: #E4E4E7;
            --text: #18181B;
            --text-muted: #71717A;
            --text-faint: #A1A1AA;
            --accent: #4338CA;
            --accent-hover: #3730A3;
            --success-bg: #F0FDF4; --success-text: #15803D;
            --error-bg: #FEF2F2; --error-text: #B91C1C;
        }

        html, body, [class*="css"] {
            font-family: 'Inter', -apple-system, sans-serif;
            color: var(--text);
        }
        .stApp { background: var(--bg); }

        .block-container { padding-top: 2.5rem; padding-bottom: 3rem; max-width: 980px; }

        /* Header */
        .app-header { display: flex; align-items: center; gap: 0.6rem; margin-bottom: 0.15rem; }
        .app-mark {
            width: 26px; height: 26px; border-radius: 7px; background: var(--text);
            display: flex; align-items: center; justify-content: center; flex-shrink: 0;
        }
        .app-mark svg { width: 14px; height: 14px; }
        .app-title { font-size: 1.3rem; font-weight: 600; letter-spacing: -0.02em; color: var(--text); }
        .app-subtitle { color: var(--text-muted); font-size: 0.875rem; margin: 0.3rem 0 1.75rem 34px; }

        /* Eyebrow / step labels */
        .eyebrow {
            display: flex; align-items: center; gap: 0.5rem;
            font-size: 0.7rem; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase;
            color: var(--text-faint); margin-bottom: 0.85rem;
        }
        .eyebrow .step-num {
            width: 18px; height: 18px; border-radius: 5px; background: var(--bg); border: 1px solid var(--border);
            display: inline-flex; align-items: center; justify-content: center;
            font-size: 0.65rem; font-weight: 600; color: var(--text-muted); text-transform: none; letter-spacing: 0;
        }

        /* Card-style containers — flat, bordered, no shadow */
        div[data-testid="stVerticalBlockBorderWrapper"] {
            background: var(--surface);
            border: 1px solid var(--border) !important;
            border-radius: 10px !important;
            box-shadow: none !important;
        }
        div[data-testid="stVerticalBlockBorderWrapper"] > div { padding: 1.1rem 1.2rem; }

        section[data-testid="stSidebar"] {
            background: var(--surface);
            border-right: 1px solid var(--border);
        }
        section[data-testid="stSidebar"] .stMarkdown p { font-size: 0.875rem; }

        h3 { font-size: 0.95rem !important; font-weight: 600 !important; color: var(--text) !important; letter-spacing: -0.01em; }

        /* Buttons */
        .stButton > button {
            border-radius: 7px;
            font-weight: 500;
            font-size: 0.875rem;
            border: 1px solid var(--border);
            color: var(--text);
            transition: none;
        }
        .stButton > button:hover { border-color: var(--text-faint); background: var(--bg); }
        .stButton > button[kind="primary"] {
            background-color: var(--accent);
            border: 1px solid var(--accent);
            color: #FFFFFF;
        }
        .stButton > button[kind="primary"]:hover { background-color: var(--accent-hover); border-color: var(--accent-hover); }
        .stButton > button[kind="primary"]:disabled { background-color: #E4E4E7; border-color: #E4E4E7; color: var(--text-faint); }

        /* Status pill */
        .status-pill {
            display: inline-flex; align-items: center; gap: 0.4rem;
            padding: 0.25rem 0.6rem; border-radius: 6px;
            font-weight: 500; font-size: 0.8rem;
        }
        .status-pill.connected { background: var(--success-bg); color: var(--success-text); }
        .status-pill.disconnected { background: var(--bg); color: var(--text-muted); border: 1px solid var(--border); }
        .status-dot { width: 6px; height: 6px; border-radius: 50%; display: inline-block; }
        .status-dot.connected { background: #16A34A; }
        .status-dot.disconnected { background: var(--text-faint); }

        /* Inputs */
        .stTextInput > div > div > input, .stSelectbox > div > div {
            border-radius: 7px !important;
            border-color: var(--border) !important;
        }
        .stTextInput > div > div > input:focus { border-color: var(--accent) !important; box-shadow: 0 0 0 1px var(--accent) !important; }

        section.main > div > div > hr { border-top: 1px solid var(--border); margin: 2rem 0; }

        .app-footer { color: var(--text-faint); font-size: 0.8rem; text-align: center; margin-top: 0.5rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="app-header">
        <span class="app-mark">
            <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect x="3" y="12" width="4" height="9" rx="1" fill="white"/>
                <rect x="10" y="7" width="4" height="14" rx="1" fill="white"/>
                <rect x="17" y="3" width="4" height="18" rx="1" fill="white"/>
            </svg>
        </span>
        <span class="app-title">CSV Analyst</span>
    </div>
    <div class="app-subtitle">Upload a CSV, ask a question in plain English, get back working pandas code and a chart.</div>
    """,
    unsafe_allow_html=True,
)


def style_chart(fig, ax):
    """Apply the app's light, minimal look to a matplotlib chart."""
    fig.patch.set_facecolor("#FFFFFF")
    ax.set_facecolor("#FFFFFF")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#E4E4E7")
    ax.spines["bottom"].set_color("#E4E4E7")
    ax.tick_params(colors="#71717A", labelsize=9)
    ax.grid(True, axis="y", color="#F4F4F5", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.title.set_color("#18181B")
    ax.title.set_fontweight("medium")
    ax.xaxis.label.set_color("#3F3F46")
    ax.yaxis.label.set_color("#3F3F46")
    return fig, ax


ACCENT_COLORS = ["#4338CA", "#A1A1AA", "#0891B2", "#B45309", "#B91C1C", "#6D28D9"]
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


FALLBACK_FREE_MODELS = [
    "z-ai/glm-5.2:free",
    "google/gemma-4-31b-it:free",
    "minimax/minimax-m3:free",
]


@st.cache_data(ttl=3600, show_spinner=False)
def get_free_models():
    """Free-tier model IDs churn on OpenRouter (renamed/retired often), so fetch the
    live list instead of hardcoding — falls back to a static list if the call fails."""
    try:
        resp = requests.get("https://openrouter.ai/api/v1/models", timeout=10)
        resp.raise_for_status()
        ids = sorted(m["id"] for m in resp.json()["data"] if m["id"].endswith(":free"))
        return ids or FALLBACK_FREE_MODELS
    except (requests.RequestException, KeyError, ValueError):
        return FALLBACK_FREE_MODELS


params = st.query_params
if "api_key" not in st.session_state:
    st.session_state.api_key = None

# The redirect to openrouter.ai and back is a full cross-origin page load, which kills
# the WebSocket and starts a brand-new Streamlit session — session_state from before the
# redirect is gone. OpenRouter also strips any query string we add to callback_url and
# only appends its own "code" param, so we can't round-trip the verifier through the URL
# either. Instead the verifier is stashed in the browser's localStorage (which *does*
# survive a full page reload) before the redirect, and read back with st_javascript,
# which returns the JS value straight into Python — no iframe navigation involved (that
# approach silently failed: Streamlit's component iframe sandbox blocks a script-driven
# top-level navigation without a real user click).
if not st.session_state.api_key and "code" in params:
    log("Received OAuth redirect with code, fetching verifier from localStorage")
    verifier = st_javascript("localStorage.getItem('or_pkce_verifier')", key="fetch_verifier")
    if verifier == 0:
        # st_javascript's sentinel while it waits for the browser round-trip; the
        # component will trigger a rerun once the real value comes back.
        st.info("Finishing login...")
        st.stop()
    elif verifier:
        try:
            st.session_state.api_key = exchange_code_for_key(params["code"], verifier)
            log("Key exchange succeeded", "success")
        except Exception as e:
            st.error(f"Login failed: {e}")
            log(f"Key exchange failed: {e}", "error")
    else:
        st.error("Couldn't recover the login verifier from this browser — please try logging in again.")
        log("Key exchange skipped: localStorage had no verifier", "error")
    st.query_params.clear()

with st.sidebar:
    st.markdown('<div class="eyebrow">Account</div>', unsafe_allow_html=True)

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
                display:block; text-align:center; padding:0.5rem 1rem; margin-top:0.6rem;
                background-color:#4338CA; color:white; border-radius:7px; font-size:0.875rem;
                text-decoration:none; font-weight:500;">Continue with OpenRouter</a>''',
            unsafe_allow_html=True,
        )
        st.caption("New accounts get free credits, and free-tier models cost nothing either way.")

    api_key = st.session_state.api_key
    free_models = get_free_models()
    model_choices = free_models + ["openai/gpt-4o-mini", "anthropic/claude-3.5-haiku"]
    model = st.selectbox(
        "Model",
        model_choices,
        index=0,
        help="Models ending in :free cost nothing to use. This list is fetched live from OpenRouter.",
    )
    st.markdown("---")
    st.caption("Streamlit + OpenRouter")

st.markdown('<div class="eyebrow"><span class="step-num">1</span>Upload data</div>', unsafe_allow_html=True)
with st.container(border=True):
    col1, col2 = st.columns([3, 1])
    with col1:
        uploaded = st.file_uploader("CSV file", type=["csv"], label_visibility="collapsed")
    with col2:
        if st.button("Use demo dataset", use_container_width=True):
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
    st.markdown('<div style="height:1.5rem"></div><div class="eyebrow"><span class="step-num">2</span>Preview</div>', unsafe_allow_html=True)
    with st.container(border=True):
        st.dataframe(df.head(20), use_container_width=True)

        with st.expander("Columns & dtypes"):
            st.write(df.dtypes.astype(str))

    st.markdown('<div style="height:1.5rem"></div><div class="eyebrow"><span class="step-num">3</span>Ask a question</div>', unsafe_allow_html=True)
    with st.container(border=True):
        question = st.text_input(
            "Question",
            placeholder="e.g. Show me monthly revenue trend, or revenue by region as a bar chart",
            label_visibility="collapsed",
        )

        go = st.button("Run analysis", type="primary", disabled=not (question and api_key))

        if not api_key:
            st.caption("Log in with OpenRouter in the sidebar to run the agent.")

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

        st.markdown('<div style="height:1.5rem"></div><div class="eyebrow"><span class="step-num">4</span>Result</div>', unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown("**Generated code**")
            st.code(code, language="python")

            st.markdown("**Output**")
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
        st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)
        with st.expander("History"):
            for i, h in enumerate(reversed(st.session_state.history), 1):
                st.markdown(f"**{i}. {h['question']}**")
                st.code(h["code"], language="python")
else:
    st.markdown('<div style="height:1.5rem"></div>', unsafe_allow_html=True)
    with st.container(border=True):
        st.caption("Upload a CSV or use the demo dataset above to get started.")

st.markdown("---")
entries = st.session_state.get("log_entries", [])
with st.expander(f"Activity log ({len(entries)})", expanded=False):
    if not entries:
        st.caption("No events yet.")
    else:
        labels = {"info": "INFO", "success": "OK", "error": "ERR"}
        for e in reversed(entries[-50:]):
            st.text(f"{e['time']}  {labels.get(e['level'], '·'):>4}  {e['message']}")
