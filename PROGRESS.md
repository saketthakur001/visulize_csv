# Progress

## Done
- Core app: upload CSV → ask question → LLM (via OpenRouter) writes pandas/matplotlib code → code executes → chart/table + generated code shown. (`app.py`)
- Seeded demo dataset (`sample_data/sales.csv`) with a "🧪 Try demo data" button so testers don't need their own file.
- OpenRouter OAuth PKCE login in the sidebar (no manual API key entry).
- Live connection status (🟢/🔴) that actually pings OpenRouter's `/auth/key` endpoint to confirm the key works, not just that one is present — also shows credit limit/usage.
- Fixed a bug where the OAuth `?code=` redirect was silently ignored on the second script rerun (the exchange logic was gated behind `"api_key" not in session_state`, which became true only once).

## Known limitations / next steps
- `APP_URL` (used as the OAuth `callback_url`) defaults to `http://localhost:8501`. If deployed, set `APP_URL` in `.streamlit/secrets.toml` to the deployed URL — OpenRouter requires an exact match.
- No persistence across page reloads — logging out or refreshing loses the session (Streamlit session state is per-browser-tab-session, not saved to disk).
- Code execution uses `exec()` in a restricted globals dict (`df`, `pd`, `plt`, `st` only) — not a full sandbox. Fine for a personal demo; would need real sandboxing before opening this up to untrusted public users.
