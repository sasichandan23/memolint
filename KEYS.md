# API keys needed to run Memolint

Everything below is free. No credit card is required for any of it.

Two keys are required, one is optional. Copy `.env.example` to `.env` and paste the values in. **Never commit `.env`** — it is already in `.gitignore`.

---

## 1. Hindsight — the memory layer (required)

This is what makes the project what it is. Every team convention, every accepted or rejected review suggestion, and every past incident is stored here and recalled before each review.

**Get it:** https://ui.hindsight.vectorize.io

1. Sign up for an account.
2. Go to **Billing** and enter promo code `MEMHACK99` for $50 in free credits.
3. Create an API key.
4. Copy the base URL shown in the dashboard.

```
HINDSIGHT_BASE_URL=https://...        # from the dashboard
HINDSIGHT_API_KEY=...                 # the key you created
```

**Used in:** `src/memolint/memory.py` — `retain`, `recall`, `reflect`, `create_directive`, `list_memories`.

**Free alternative with no signup:** run Hindsight yourself with Docker. See the self-hosted section in the README. Then set `HINDSIGHT_BASE_URL=http://localhost:8888` and leave the key blank.

---

## 2. Groq — the model that writes the reviews (required)

Reads the diff plus the recalled memories and produces the findings.

**Get it:** https://console.groq.com/keys

1. Sign in with Google or GitHub.
2. Click **Create API Key** and copy it. It starts with `gsk_`.

```
GROQ_API_KEY=gsk_...
LLM_PROVIDER=groq
```

**Used in:** `src/memolint/llm.py` via the OpenAI-compatible client, called from `src/memolint/reviewer.py`.

**Free tier limits:** about 8,000 tokens per minute and 200,000 per day. One review costs roughly 5,000 tokens, so expect about one review per minute and around 40 per day on a single key. Hitting the limit causes a wait and retry, not a crash.

---

## 3. GitHub token — review real pull requests (optional)

Without this, Memolint still reviews diff files and local git branches, which is enough for the demo. With it, Memolint can read a real pull request, post its review as comments, and learn from replies.

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
| `GEMINI_API_KEY` | A second free model provider, in case Groq's daily limit runs out. Get it at https://aistudio.google.com/apikey and set `LLM_PROVIDER=gemini`. |
| `LLM_MODEL` | Override the model. Defaults to `llama-3.3-70b-versatile` on Groq, `gemini-2.5-flash` on Gemini. |
| `MEMOLINT_MAX_DIFF_CHARS` | Shrink the diff budget if you keep hitting rate limits. |

Running a local model instead needs no key at all: install Ollama, then set `LLM_PROVIDER=ollama`.

---

## Check that it works

```bash
memolint init
```

Creates the memory bank. If the Hindsight values are wrong, this is where it fails.

```bash
memolint demo
```

Runs the full three-pull-request walkthrough. This exercises both keys end to end.
