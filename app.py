import base64
import hashlib
import io
import json
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
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #EDF2F1;
            --grid-line: rgba(22, 35, 46, 0.055);
            --surface: #FFFFFF;
            --border: #D6DEDB;
            --ink: #14211D;
            --ink-muted: #55665F;
            --ink-faint: #8A9992;
            --accent: #D9720F;
            --accent-hover: #B85F09;
            --accent-soft: #FBE6CE;
            --accent-soft-border: #F0C58C;
            --ok: #2F8F5B;
            --err: #C4472B;

            --side-bg: #12211E;
            --side-bg-raised: #1B302B;
            --side-border: #2C453D;
            --side-text: #E4ECE8;
            --side-muted: #86988F;
        }

        html, body, [class*="css"] {
            font-family: 'IBM Plex Sans', -apple-system, sans-serif;
            color: var(--ink);
        }
        .stApp {
            background-color: var(--bg);
            background-image:
                linear-gradient(var(--grid-line) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid-line) 1px, transparent 1px);
            background-size: 28px 28px;
        }

        .block-container { padding-top: 2rem; padding-bottom: 3rem; max-width: 980px; }

        code, .stCodeBlock, .stCode, pre { font-family: 'JetBrains Mono', monospace !important; }

        /* Window chrome — the app reads as an open editor/terminal session, not a form */
        .win-chrome {
            display: flex; align-items: center; gap: 0.5rem;
            background: var(--ink); border-radius: 8px 8px 0 0;
            padding: 0.55rem 0.85rem; margin-bottom: 0;
        }
        .win-dot { width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0; }
        .win-dot.r { background: #E5544B; } .win-dot.y { background: #E5B93F; } .win-dot.g { background: #3FA66A; }
        .win-file {
            font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; color: var(--side-muted);
            margin-left: 0.4rem;
        }
        .win-body {
            background: var(--surface); border: 1px solid var(--ink);
            border-top: none; border-radius: 0 0 8px 8px;
            padding: 1.1rem 1.3rem 1.3rem;
            box-shadow: 0 3px 0 rgba(20, 33, 29, 0.06);
            margin-bottom: 1.6rem;
        }
        .app-title {
            font-family: 'JetBrains Mono', monospace; font-size: 1.15rem; font-weight: 700;
            letter-spacing: -0.01em; color: var(--ink);
        }
        .app-subtitle { color: var(--ink-muted); font-size: 0.875rem; margin: 0.35rem 0 0; }

        /* Eyebrow / step labels — rendered as a shell prompt */
        .eyebrow {
            display: flex; align-items: baseline; gap: 0.5rem;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.8rem; font-weight: 600;
            color: var(--ink-muted); margin-bottom: 0.85rem;
        }
        .eyebrow .prompt { color: var(--accent); font-weight: 700; }
        .eyebrow .step-label { color: var(--ink); text-transform: none; letter-spacing: 0; }

        /* Card-style containers */
        div[data-testid="stVerticalBlockBorderWrapper"] {
            background: var(--surface);
            border: 1px solid var(--border) !important;
            border-radius: 6px !important;
            box-shadow: none !important;
        }
        div[data-testid="stVerticalBlockBorderWrapper"] > div { padding: 1.1rem 1.2rem; }

        /* Sidebar — dark ink, matches the window chrome */
        section[data-testid="stSidebar"] {
            background: var(--side-bg);
            border-right: 1px solid var(--side-border);
        }
        section[data-testid="stSidebar"] * { color: var(--side-text); }
        section[data-testid="stSidebar"] .eyebrow { color: var(--side-muted); }
        section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p { color: var(--side-muted) !important; font-size: 0.8rem; }
        section[data-testid="stSidebar"] hr { border-top: 1px solid var(--side-border); }
        section[data-testid="stSidebar"] .stButton > button {
            background: var(--side-bg-raised); border: 1px solid var(--side-border); color: var(--side-text);
        }
        section[data-testid="stSidebar"] .stButton > button:hover { border-color: var(--side-muted); background: #24382F; }
        /* Selectbox/slider internals are theme-driven (see [theme.sidebar] in config.toml),
           not reachable by page-level CSS — no override needed here. */

        h3 {
            font-family: 'JetBrains Mono', monospace !important;
            font-size: 0.9rem !important; font-weight: 600 !important; color: var(--ink) !important; letter-spacing: 0;
        }

        /* Buttons */
        .stButton > button {
            border-radius: 5px;
            font-weight: 500;
            font-size: 0.875rem;
            border: 1px solid var(--border);
            color: var(--ink);
            transition: none;
        }
        .stButton > button:hover { border-color: var(--accent); background: var(--accent-soft); }
        .stButton > button[kind="primary"] {
            background: var(--accent);
            border: 1px solid var(--accent-hover);
            color: #FFFFFF;
        }
        .stButton > button[kind="primary"]:hover { background: var(--accent-hover); }
        .stButton > button[kind="primary"]:disabled { background: #DDE6E2; border-color: #DDE6E2; color: var(--ink-faint); }

        /* Status pill */
        .status-pill {
            display: inline-flex; align-items: center; gap: 0.4rem;
            padding: 0.25rem 0.6rem; border-radius: 5px;
            font-family: 'JetBrains Mono', monospace;
            font-weight: 500; font-size: 0.78rem;
        }
        .status-pill.connected { background: rgba(63, 166, 106, 0.16); color: #4FC886; }
        .status-pill.disconnected { background: var(--side-bg-raised); color: var(--side-muted); border: 1px solid var(--side-border); }
        .status-dot { width: 6px; height: 6px; border-radius: 50%; display: inline-block; }
        .status-dot.connected { background: #4FC886; box-shadow: 0 0 5px rgba(79, 200, 134, 0.7); }
        .status-dot.disconnected { background: var(--side-muted); }

        /* Inputs */
        .stTextInput > div > div > input, .stSelectbox > div > div {
            border-radius: 5px !important;
            border-color: var(--border) !important;
        }
        .stTextInput > div > div > input:focus { border-color: var(--accent) !important; box-shadow: 0 0 0 1px var(--accent) !important; }
        div[data-testid="stTextInput"] input { font-family: 'JetBrains Mono', monospace; }

        /* Slider — recolor from Streamlit's default indigo to the accent */
        div[data-testid="stSlider"] div[role="slider"] { background-color: var(--accent) !important; border-color: var(--accent) !important; }
        div[data-testid="stSlider"] div[data-baseweb="slider"] > div > div:nth-child(2) { background: var(--accent) !important; }

        section.main > div > div > hr { border-top: 1px dashed var(--border); margin: 2rem 0; }

        .app-footer { color: var(--ink-faint); font-size: 0.8rem; text-align: center; margin-top: 0.5rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="win-chrome">
        <span class="win-dot r"></span><span class="win-dot y"></span><span class="win-dot g"></span>
        <span class="win-file">~/session · csv_analyst.py</span>
    </div>
    <div class="win-body">
        <div class="app-title">df = pd.read_csv(...)  →  agent</div>
        <div class="app-subtitle">Upload a CSV, ask a question in plain English, get back working pandas code and a chart.</div>
    </div>
    """,
    unsafe_allow_html=True,
)


def style_chart(fig, ax):
    """Apply the app's light, minimal look to a matplotlib chart."""
    fig.patch.set_facecolor("#FFFFFF")
    ax.set_facecolor("#FFFFFF")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#D6DEDB")
    ax.spines["bottom"].set_color("#D6DEDB")
    ax.tick_params(colors="#55665F", labelsize=9)
    ax.grid(True, axis="y", color="#EDF2F1", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.title.set_color("#14211D")
    ax.title.set_fontweight("medium")
    ax.xaxis.label.set_color("#14211D")
    ax.yaxis.label.set_color("#14211D")
    return fig, ax


ACCENT_COLORS = ["#D9720F", "#2E6E5C", "#3B5266", "#B85F09", "#7A4A2B", "#5C7A6E"]
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

# Restore a previously saved login from localStorage, so the user doesn't have to go
# through the OpenRouter OAuth dance again on every page reload / new session. Only
# attempted once per session, and skipped mid-OAuth-redirect (there's nothing to
# restore yet in that case, and it would double up with the exchange logic below).
if "tried_restore" not in st.session_state:
    st.session_state.tried_restore = False

if not st.session_state.api_key and not st.session_state.tried_restore and "code" not in params:
    saved_key = st_javascript("localStorage.getItem('or_api_key')", key="restore_key")
    # saved_key == 0 is st_javascript's sentinel while it waits for the browser round-trip
    # (it triggers its own rerun once the real value arrives). Never st.stop() here — if
    # that round-trip stalls for any reason, blocking would blank the entire page (no
    # sidebar, no content) instead of just leaving the login unrestored for this pass.
    if saved_key != 0:
        st.session_state.tried_restore = True
        if saved_key:
            st.session_state.api_key = saved_key
            log("Restored saved login from this browser", "success")

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
    if "verifier_wait_attempts" not in st.session_state:
        st.session_state.verifier_wait_attempts = 0

    log("Received OAuth redirect with code, fetching verifier from localStorage")
    verifier = st_javascript("localStorage.getItem('or_pkce_verifier')", key="fetch_verifier")
    if verifier == 0 and st.session_state.verifier_wait_attempts < 20:
        # st_javascript's sentinel while it waits for the browser round-trip; the
        # component will trigger a rerun once the real value comes back. Capped so a
        # stalled round-trip degrades to a clear error instead of blanking the page
        # forever.
        st.session_state.verifier_wait_attempts += 1
        st.info("Finishing login...")
        st.stop()
    elif verifier == 0:
        st.error("Login is taking unexpectedly long — please refresh and try logging in again.")
        log("Key exchange abandoned: verifier fetch never resolved", "error")
        st.query_params.clear()
    elif verifier:
        try:
            st.session_state.api_key = exchange_code_for_key(params["code"], verifier)
            log("Key exchange succeeded", "success")
            # Save the key so a future page load/reload can skip the OAuth dance
            # entirely — see the restore block above.
            components.html(
                f"<script>window.localStorage.setItem('or_api_key', {json.dumps(st.session_state.api_key)});</script>",
                height=0,
            )
        except Exception as e:
            st.error(f"Login failed: {e}")
            log(f"Key exchange failed: {e}", "error")
    else:
        st.error("Couldn't recover the login verifier from this browser — please try logging in again.")
        log("Key exchange skipped: localStorage had no verifier", "error")
    st.query_params.clear()

with st.sidebar:
    st.markdown('<div class="eyebrow"><span class="prompt">$</span><span class="step-label">account</span></div>', unsafe_allow_html=True)

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
            st.session_state.tried_restore = True
            check_connection.clear()
            components.html(
                "<script>window.localStorage.removeItem('or_api_key');</script>",
                height=0,
            )
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
            f"<script>window.localStorage.setItem('or_pkce_verifier', {json.dumps(verifier)});</script>",
            height=0,
        )
        auth_url = (
            "https://openrouter.ai/auth"
            f"?callback_url={quote(APP_URL, safe='')}"
            f"&code_challenge={challenge}"
            "&code_challenge_method=S256"
        )
        # Streamlit Cloud itself renders this app inside a sandboxed iframe
        # (sandbox="allow-forms allow-modals allow-popups allow-popups-to-escape-sandbox
        # allow-same-origin allow-scripts allow-downloads" — no allow-top-navigation).
        # target="_top"/"_self" are both silently blocked by that sandbox (Chrome logs
        # "Unsafe attempt to initiate navigation ... sandboxed" and does nothing — no
        # request ever leaves the browser). allow-popups-to-escape-sandbox IS granted,
        # so target="_blank" opens an unsandboxed tab instead; it's same-origin as the
        # iframe, so the PKCE verifier written to localStorage above is still readable
        # after the redirect back.
        st.markdown(
            f'''<a href="{auth_url}" target="_blank" style="
                display:block; text-align:center; padding:0.5rem 1rem; margin-top:0.6rem;
                background:var(--accent); color:white;
                border-radius:7px; font-size:0.875rem;
                text-decoration:none; font-weight:500;">Continue with OpenRouter</a>''',
            unsafe_allow_html=True,
        )
        st.caption("New accounts get free credits, and free-tier models cost nothing either way.")

        with st.expander("Or paste an API key instead"):
            st.caption("If the login button doesn't work (some networks block OAuth-style redirect links), grab a free key from [openrouter.ai/keys](https://openrouter.ai/keys) and paste it here.")
            manual_key = st.text_input("OpenRouter API key", type="password", key="manual_key_input", label_visibility="collapsed", placeholder="sk-or-...")
            if st.button("Use this key", use_container_width=True) and manual_key:
                st.session_state.api_key = manual_key
                check_connection.clear()
                components.html(
                    f"<script>window.localStorage.setItem('or_api_key', {json.dumps(manual_key)});</script>",
                    height=0,
                )
                log("API key set manually", "success")
                st.rerun()

    api_key = st.session_state.api_key
    free_models = get_free_models()
    model_choices = free_models + ["openai/gpt-4o-mini", "anthropic/claude-3.5-haiku"]
    model = st.selectbox(
        "Model",
        model_choices,
        index=0,
        help="Models ending in :free cost nothing to use. This list is fetched live from OpenRouter.",
    )
    max_retries = st.slider(
        "Self-repair attempts",
        min_value=1,
        max_value=4,
        value=3,
        help="If the model's generated code errors out, feed the error back and let it try again, up to this many attempts.",
    )
    st.markdown("---")
    st.caption("Streamlit + OpenRouter")

st.markdown('<div class="eyebrow"><span class="prompt">$</span><span class="step-label">01 · upload data</span></div>', unsafe_allow_html=True)
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
    st.markdown('<div style="height:1.5rem"></div><div class="eyebrow"><span class="prompt">$</span><span class="step-label">02 · preview</span></div>', unsafe_allow_html=True)
    with st.container(border=True):
        st.dataframe(df.head(20), use_container_width=True)

        with st.expander("Columns & dtypes"):
            st.write(df.dtypes.astype(str))

    st.markdown('<div style="height:1.5rem"></div><div class="eyebrow"><span class="prompt">$</span><span class="step-label">03 · ask a question</span></div>', unsafe_allow_html=True)
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

        def extract_code(raw_text):
            match = re.search(r"```(?:python)?\s*(.*?)```", raw_text, re.DOTALL)
            return match.group(1).strip() if match else raw_text.strip()

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ]

        log(f"Analyze requested — model={model}, question={question!r}, max_retries={max_retries}")

        st.markdown('<div style="height:1.5rem"></div><div class="eyebrow"><span class="prompt">$</span><span class="step-label">04 · agent trace</span></div>', unsafe_allow_html=True)

        final_code = None
        succeeded = False

        with st.status("Starting agent...", expanded=True) as status:
            st.caption(f"Dataset: {df.shape[0]} rows × {df.shape[1]} columns · Model: `{model}`")

            for attempt in range(1, max_retries + 1):
                status.update(label=f"Calling {model} to write pandas code — attempt {attempt}/{max_retries}")
                try:
                    resp = client.chat.completions.create(model=model, messages=messages, temperature=0)
                    raw = resp.choices[0].message.content
                except Exception as e:
                    status.update(label="LLM call failed", state="error")
                    st.error(f"LLM call failed: {e}")
                    log(f"LLM call failed: {e}", "error")
                    break

                code = extract_code(raw)
                final_code = code
                log(f"LLM call succeeded (attempt {attempt})", "success")

                st.markdown(f"**Attempt {attempt} — generated code**")
                st.code(code, language="python")

                status.update(label=f"Executing generated code — attempt {attempt}/{max_retries}")
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
                    st.success(f"Execution succeeded on attempt {attempt}")
                    status.update(
                        label=f"Done — succeeded on attempt {attempt}/{max_retries}",
                        state="complete",
                    )
                    log(f"Generated code executed successfully (attempt {attempt})", "success")
                    succeeded = True
                    break
                except Exception as e:
                    st.error(f"Execution failed: {e}")
                    log(f"Execution error (attempt {attempt}): {e}", "error")
                    if attempt < max_retries:
                        st.info("Sending the error back to the model so it can fix its own code...")
                        messages.append({"role": "assistant", "content": raw})
                        messages.append(
                            {
                                "role": "user",
                                "content": f"That code raised this error when run:\n{e}\n\n"
                                "Fix it and return the corrected code as a single python code block.",
                            }
                        )
                    else:
                        status.update(
                            label=f"Failed — gave up after {max_retries} attempts",
                            state="error",
                        )

        if final_code:
            st.session_state.history.append(
                {"question": question, "code": final_code, "succeeded": succeeded}
            )

    if st.session_state.history:
        st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)
        with st.expander("History"):
            for i, h in enumerate(reversed(st.session_state.history), 1):
                mark = "✓" if h.get("succeeded") else "✗"
                st.markdown(f"**{i}. {mark} {h['question']}**")
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
