# OpenRouter integration — dev notes

Engineering notes from building the OAuth PKCE login in this app. Read this
before touching the login flow again — several "obvious" approaches were
tried and confirmed broken through actual testing, not guesswork.

## The flow, at a glance

1. App generates a random `code_verifier` + its SHA-256 `code_challenge`.
2. Sends the browser to:
   `https://openrouter.ai/auth?callback_url=<APP_URL>&code_challenge=<challenge>&code_challenge_method=S256`
3. User approves on OpenRouter's site.
4. OpenRouter redirects back to `<APP_URL>?code=<one-time code>`.
5. App exchanges `code` + `code_verifier` for a real API key:
   `POST https://openrouter.ai/api/v1/auth/keys`
   body: `{"code": ..., "code_verifier": ..., "code_challenge_method": "S256"}`
6. App verifies the key works via `GET https://openrouter.ai/api/v1/auth/key`
   (Bearer auth) — this is what drives the 🟢/🔴 connection indicator.

## Things that DON'T work (confirmed by testing, not assumption)

- **Relying on `st.session_state` to survive the redirect.**
  The trip to `openrouter.ai` and back is a full cross-origin page load. It
  kills the WebSocket connection, and Streamlit starts a **brand new session**
  with empty `session_state` on return. Anything stored in session_state
  before redirecting (like the PKCE verifier) is gone.

- **Embedding extra query params in `callback_url` to round-trip data**
  (e.g. `callback_url=https://app?v=<verifier>`).
  OpenRouter strips the existing query string from `callback_url` and only
  appends its own `?code=...`. Confirmed via live testing — the `v` param
  never survives the round trip. Don't rely on this.

- **`st.link_button` for the login link.**
  It renders `target="_blank"` (opens a new tab). A new tab is a *separate*
  Streamlit session from the start, so anything session-based is doomed
  twice over. Use a plain `<a target="_self">` styled as a button instead.

- **Navigating the top-level page from inside a `components.html` iframe**
  (e.g. `window.parent.location.replace(...)` run automatically on load).
  Streamlit's component iframe sandbox blocks a script-driven top-level
  navigation unless it's tied to a real user click (user activation). This
  fails *silently* — no exception, no console error visible to the app, the
  page just sits there (this produced the "Finishing login..." stuck state).

## What DOES work

- **Browser `localStorage` as the bridge across the redirect.**
  Unlike session_state, localStorage survives a full page reload (it's tied
  to the browser origin, not the WebSocket session). Save the verifier here
  right before sending the user to OpenRouter.

- **`streamlit_javascript.st_javascript(...)` to read it back.**
  This reads a JS expression's result straight into Python without any
  navigation — it uses Streamlit's component postMessage channel, not
  `location.replace`, so it isn't subject to the top-navigation sandbox
  restriction above. Returns a sentinel (`0`) on the first call while it
  waits for the JS round trip; `st.stop()` on that value and let the
  component's internal rerun deliver the real value next pass.

- **Same-tab navigation for the login link** (`target="_self"`), so the
  redirect-back page shares origin/storage context cleanly with the page
  that saved the verifier.

## Current known-good implementation

See `app.py`:
- `make_pkce_pair()` — generates verifier/challenge.
- Login link section (in the sidebar, "not connected" branch) — saves the
  verifier to `localStorage['or_pkce_verifier']` via `components.html`,
  builds `auth_url` with a **plain** `callback_url` (no extra params).
- Top-level block handling `?code=` — reads the verifier back with
  `st_javascript`, then calls `exchange_code_for_key()`.
- `check_connection()` — pings `/auth/key` to confirm the key actually works
  (cached 30s via `st.cache_data`) and drives the 🟢/🔴 indicator.

## Staying on free usage

- Default model list favors `:free`-suffixed models (e.g.
  `google/gemini-2.0-flash-exp:free`) — these cost nothing regardless of
  account balance.
- New OpenRouter accounts also get a small free credit grant.
- Check balance: `GET /auth/key` response includes `limit` and `usage`
  (also shown live in the sidebar once connected).

## If login breaks again

1. Check the in-app **🪵 App logs** expander at the bottom of the page first
   — it timestamps every step (redirect received, verifier fetch, key
   exchange, connection check) without needing terminal access.
2. If stuck on "Finishing login..." — check browser devtools console for JS
   errors on the `st_javascript` component, and confirm `localStorage` isn't
   blocked (private browsing / strict site-data settings can block it).
3. If "Not connected" after a successful-looking login — the key was
   returned but `/auth/key` validation failed; log out and retry, or check
   openrouter.ai/keys directly to confirm the key exists on their end.
4. Deployed (not localhost)? `APP_URL` must exactly match where the app is
   actually served — set it in `.streamlit/secrets.toml`.
