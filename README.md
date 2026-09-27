# Memolint

**A code reviewer that remembers your team's precedents.**

Every AI code reviewer today has amnesia. It flags the same rejected nitpick on every PR, never learns that your team uses guard clauses, and has no idea that the pattern in this diff caused last month's outage. Memolint fixes that with one addition: a persistent memory, powered by [Hindsight](https://github.com/vectorize-io/hindsight).

- Reviewer says "we don't do type hints on private helpers" once. Memolint never raises it again.
- Reviewer links a finding to a real incident. The next PR with that pattern gets a high-severity warning that names the incident.
- Team conventions become standing rules that shape every future review.

The LLM is stateless. The memory bank is not. That is the whole product.

Runs entirely on free tiers: Groq (or Gemini) for the reviewer, Hindsight Cloud free credits or a self-hosted Hindsight for memory.

## 60-second demo

```bash
memolint demo
```

Three PRs against a fictional `orderflow` service. PR 1 gets a generic review. The team responds: accepts some findings, rejects one, states two conventions. PR 2 already reflects that. The team links the N+1 finding to a past outage. PR 3 is reviewed twice, memory off and memory on, side by side. The difference is the pitch.

## Setup

```bash
git clone <this repo> && cd memolint
python -m venv .venv && . .venv/Scripts/activate   # Windows; on macOS/Linux: source .venv/bin/activate
pip install -e .
cp .env.example .env
```

Fill in `.env`. You need two keys, both free:

| Key | Where | Notes |
|---|---|---|
| `GROQ_API_KEY` | https://console.groq.com/keys | No card. Free tier is ~8K tokens/min, which a review fits in. |
| `HINDSIGHT_BASE_URL` + `HINDSIGHT_API_KEY` | https://ui.hindsight.vectorize.io | Free starter credits. Base URL is in the dashboard. |

Optional: `GEMINI_API_KEY` (set `LLM_PROVIDER=gemini`), `GITHUB_TOKEN` to review and comment on real PRs. Full step-by-step instructions for every key are in [KEYS.md](KEYS.md).

### Fully self-hosted, zero cost forever

Hindsight is open source. Run it locally with Groq as its extraction model and local embeddings:

```bash
docker run -it --pull always --name hindsight --shm-size=1g -p 8888:8888 -p 9999:9999 \
  -e HINDSIGHT_API_LLM_PROVIDER=groq \
  -e HINDSIGHT_API_LLM_API_KEY=$GROQ_API_KEY \
  -e HINDSIGHT_API_LLM_MODEL=openai/gpt-oss-20b \
  -e HINDSIGHT_API_EMBEDDINGS_PROVIDER=local \
  -v hindsight-data:/home/hindsight/.pg0 \
  ghcr.io/vectorize-io/hindsight:latest
```

Then `HINDSIGHT_BASE_URL=http://localhost:8888` and leave `HINDSIGHT_API_KEY` empty. Tip: use a second Groq key for Hindsight so its extraction calls don't share the reviewer's rate limit.

## Usage

```bash
memolint review --diff changes.diff              # review a diff file
memolint review --git main..HEAD                 # review the current branch
memolint review --pr owner/repo#42 --post        # review a GitHub PR and post the review
memolint review --pr owner/repo#42 --no-memory   # same PR, amnesiac mode, for comparison

memolint feedback F2 --reject --note "we don't type-hint private helpers"
memolint feedback F1 --accept --rule "Use get_logger(__name__), never print"
memolint feedback F3 --accept --incident "N+1 in checkout caused the Sept 3 outage"
memolint teach "Prefer guard clauses over nested ifs"
memolint incident "Unbounded IN() list in reports query locked the orders table" --pr 212

memolint learn owner/repo#42     # read human replies on GitHub and learn from them
memolint memories                # what it knows about this repo
memolint ask "what does this team care about in reviews?"
```

Each repository gets its own memory bank, derived from the git remote or `--repo`.

## How Hindsight memory is used

```
                 ┌─────────────────────────────────────────────┐
   PR diff ──►   │  1. recall(query built from the diff)        │ ◄── Hindsight bank
                 │     + list_directives()  (standing rules)    │     per repository
                 │  2. LLM review with memories in the prompt   │
                 │  3. retain(review summary)                   │ ──► Hindsight
                 └─────────────────────────────────────────────┘
   human reply ─► feedback / learn ─► retain(accepted|rejected + why)
   "we always X" ─► teach ─► create_directive + retain(convention)
   "this broke prod" ─► incident ─► retain(incident precedent)
```

Four kinds of memory, tagged so recall results can be grouped in the prompt:

| kind | what it is | why it matters |
|---|---|---|
| `convention` | An explicit team rule. Also stored as a Hindsight **directive**. | Shapes every future review. |
| `feedback` | How a human responded to a specific finding, and why. | Rejections stop the reviewer repeating itself. The most valuable memory. |
| `incident` | A bug or outage tied to a code pattern. | Turns "this looks like an N+1" into "this is the pattern that took checkout down on Sept 3". |
| `review` | Summary of each review posted. | Knows what it already said. |

Before each review, `recall` runs with a query built from the PR title, touched paths and added lines, budgeted to about 1K tokens. Results and directives are injected into the prompt under headings the model is told to treat as binding. The model returns findings with a `precedent` field naming the memory each one is grounded in, plus a `skipped_on_purpose` list showing what it deliberately did not raise. After the review, a summary is retained so the bank grows with every PR.

`memolint ask` uses Hindsight `reflect` to answer questions over the whole bank, for example "what does this team care about?".

## Free-tier budget

Groq's free tier allows about 8K tokens per minute. A review is one model call:

| part | budget |
|---|---|
| system prompt | ~450 tokens |
| recalled memories | ≤1,000 tokens |
| diff (changed hunks only, lockfiles skipped) | ≤2,500 tokens |
| response | ≤1,400 tokens |

Roughly 5K tokens per review, so one review a minute and ~40 a day on one free key. Rate limits trigger a wait, not a crash.

## Layout

```
src/memolint/
  config.py         env + provider presets (groq, gemini, ollama, custom)
  llm.py            OpenAI-compatible client, JSON mode, 429 back-off
  diff.py           diff parsing, file filtering, token budgeting
  memory.py         the Hindsight layer: retain / recall / directives / reflect
  reviewer.py       prompt, review, learn-from-comments
  github_client.py  PR read, review post, comment read
  state.py          local finding ids so `feedback F2` works
  cli.py            commands + the scripted demo
demo/prs/           three hand-written PR diffs for the demo
tests/              parsing and budgeting tests (no network)
```

## Links

- Hindsight on GitHub: https://github.com/vectorize-io/hindsight
- Hindsight docs: https://hindsight.vectorize.io/
- What is agent memory: https://vectorize.io/what-is-agent-memory
