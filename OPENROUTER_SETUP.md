# Using OpenRouter with this app

This app doesn't come bundled with an API key — each user connects their **own**
OpenRouter account. That keeps it free for you to run and free (or very cheap)
for anyone trying it, since they use their own credits/free-tier models.

## Option A — Log in with OpenRouter (recommended, no key copy-pasting)

1. Click **"🔑 Log in with OpenRouter"** in the sidebar.
2. If you don't have an OpenRouter account yet, sign up on the page it takes you
   to (free — usually via Google/GitHub).
3. Approve the connection. You're redirected straight back into the app,
   already logged in — the sidebar should show **🟢 Connected to OpenRouter LLM**.

No API key is ever typed or pasted — this uses OpenRouter's OAuth PKCE flow,
which exchanges a one-time login code for a key behind the scenes.

## Option B — Manual API key (fallback)

If login ever fails (see Troubleshooting below), you can generate a key yourself:

1. Go to https://openrouter.ai/keys (create a free account first if needed).
2. Click **"Create Key"**, name it anything (e.g. "csv-analyst-demo"), and copy it.
3. Paste it wherever the app's manual-key fallback field is (if enabled).

## Staying free

- The model picker defaults to models ending in **`:free`** (e.g.
  `google/gemini-2.0-flash-exp:free`) — these cost nothing to use regardless of
  your account's credit balance.
- New OpenRouter accounts also get a small amount of free credit, so even
  non-`:free` models will work briefly without needing to add a payment method.
- Check your balance any time at https://openrouter.ai/credits.

## How the login technically works (PKCE, no client secret)

This app uses OAuth 2.0 **PKCE** (Proof Key for Code Exchange) — the flow
OpenRouter documents at:
`https://openrouter.ai/auth?callback_url=<YOUR_SITE_URL>&code_challenge=<CODE_CHALLENGE>&code_challenge_method=S256`

Why PKCE and not a normal API key field: PKCE doesn't require a backend client
secret, which is why it's safe to use from a simple app like this one with no
server-side secret storage. Each login is scoped to the user who clicks it —
the app developer never sees or stores anyone's key beyond their own browser
session.

Steps the app performs automatically:
1. Generates a random `code_verifier` and its SHA-256 `code_challenge`.
2. Sends the user to OpenRouter's `/auth` page with the `code_challenge`,
   embedding the `code_verifier` in the app's own `callback_url` (as `?v=...`)
   so it survives the redirect even without session persistence.
3. OpenRouter redirects back with a one-time `code`.
4. The app exchanges `code` + `code_verifier` for a real API key via
   `POST https://openrouter.ai/api/v1/auth/keys`.
5. The app pings `GET https://openrouter.ai/api/v1/auth/key` to confirm the
   key is valid — that's what drives the 🟢/🔴 connection indicator.

## Troubleshooting

- **"Login link is missing its verifier"** — you opened an old/bookmarked
  callback URL directly, or something stripped the `v=` query param in
  transit. Just click "Log in with OpenRouter" again from a fresh page load.
- **Stuck on 🔴 Not connected after logging in** — check the "🪵 App logs"
  expander at the bottom of the page for the exact error, then try "Log out"
  and log in again.
- **Deployed somewhere other than localhost** — set `APP_URL` in
  `.streamlit/secrets.toml` to your deployed URL. OpenRouter requires the
  `callback_url` to match exactly.
