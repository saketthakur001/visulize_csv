# Goal

CSV Analyst Agent — a Streamlit demo for recruiters/interviewers to try in ~10 seconds:

1. Upload a CSV (or click "Try demo data" for a seeded sample).
2. Ask a question in plain English.
3. An LLM (via OpenRouter) writes pandas/matplotlib code.
4. The code runs, and the chart/table + the generated code are both shown.

Login is via OpenRouter's OAuth PKCE flow (the URL the user originally shared) —
no manual API key pasting. Defaults to a free-tier model so it costs nothing
even on a brand-new OpenRouter account.
