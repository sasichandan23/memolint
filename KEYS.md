# API keys needed to run Memolint

Four keys, all free, none require a credit card. Get all four: the two "optional" ones cost two minutes each and both make the project better.

Copy `.env.example` to `.env` and paste the values in. **Never commit `.env`** — it is already in `.gitignore`.

| # | Service | What it does | Needed? |
|---|---|---|---|
| 1 | Hindsight | Stores and recalls everything the reviewer learns | Required |
| 2 | Groq | Writes the reviews | Required |
| 3 | Google AI Studio | Takes over automatically when Groq hits its daily cap | Strongly recommended |
| 4 | GitHub | Review real pull requests and learn from replies | Recommended |

---

## 1. Hindsight — the memory layer

This is what makes the project what it is. Every team convention, every accepted or rejected review suggestion, and every past incident is stored here and recalled before each review.

**Get it:** https://ui.hindsight.vectorize.io

1. Sign up for an account.
2. Go to **Billing** and enter promo code `MEMHACK99` for $50 in free credits.
3. Create an API key.

```
HINDSIGHT_BASE_URL=https://api.hindsight.vectorize.io
HINDSIGHT_API_KEY=hsk_...             # the key you created
```

The base URL above is the Hindsight Cloud API endpoint, verified working. The dashboard
address (`ui.hindsight.vectorize.io`) is the web interface, not the API.

**Used in:** `src/memolint/memory.py` — `retain`, `recall`, `reflect`, `create_directive`, `list_memories`.

**Free alternative with no signup:** run Hindsight yourself with Docker. See the self-hosted section in the README. Then set `HINDSIGHT_BASE_URL=http://localhost:8888` and leave the key blank.

---

## 2. Groq — the model that writes the reviews

Reads the diff plus the recalled memories and produces the findings.

**Get it:** https://console.groq.com/keys

1. Sign in with Google or GitHub.
2. Click **Create API Key** and copy it. It starts with `gsk_`.

```
GROQ_API_KEY=gsk_...
LLM_PROVIDER=groq
```

**Used in:** `src/memolint/llm.py`, called from `src/memolint/reviewer.py`.

**Free tier limits:** about 8,000 tokens per minute and 200,000 per day. One review costs roughly 5,000 tokens, so expect about one review per minute and around 40 per day on a single key.

---

## 3. Google AI Studio — the automatic backup model

Not a manual switch. If Groq returns a rate limit that would take more than 90 seconds to clear, Memolint moves to Gemini mid-run and keeps going. A short burst limit is waited out on Groq instead. The review output prints which provider answered.

This matters most during a live demo, where hitting a daily cap with no fallback means a dead terminal in front of an audience.

**Get it:** https://aistudio.google.com/apikey

1. Sign in with a Google account.
2. Click **Create API key** and copy it.

```
GEMINI_API_KEY=...
```

Nothing else to configure. Leave `LLM_PROVIDER=groq`; the fallback is automatic. To make Gemini the primary instead, set `LLM_PROVIDER=gemini` and Groq becomes the backup.

**Used in:** `src/memolint/config.py` builds the provider chain, `src/memolint/llm.py` walks it.

---

## 4. GitHub token — review real pull requests

Without this, Memolint still reviews diff files and local git branches, which is enough for the demo. With it, Memolint can read a real pull request, post its review as inline comments, and learn from the replies people leave.

**Get it:** https://github.com/settings/tokens

1. Choose **Fine-grained tokens**, then **Generate new token**.
2. Select only the repository you want reviewed.
3. Set permissions: **Contents → Read-only**, **Pull requests → Read and write**.

```
GITHUB_TOKEN=github_pat_...
```

**Used in:** `src/memolint/github_client.py`, for the `review --pr`, `review --post`, and `learn` commands.

---

## Optional extras

| Variable | Why you might set it |
|---|---|
| `LLM_MODEL` | Override the model for the primary provider. Defaults to `qwen/qwen3.8-27b` on Groq, `gemini-3.8-flash` on Gemini. |
| `OLLAMA_API_KEY` | Set to any value to allow failing over to a local Ollama server. Off by default so the chain never ends in a dead localhost call. |
| `MEMOLINT_MAX_DIFF_CHARS` | Shrink the diff budget if you keep hitting rate limits. |

Running entirely on a local model needs no key at all: install Ollama, then set `LLM_PROVIDER=ollama`.

---

## Check that it works

```bash
memolint init
```

Creates the memory bank. If the Hindsight values are wrong, this is where it fails.

```bash
memolint demo
```

Runs the full three-pull-request walkthrough. This exercises Hindsight and the model chain end to end.
