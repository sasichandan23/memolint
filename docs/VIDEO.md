# Video plan

Target: 2:45. Fast, cut to music, no slow narration. The whole video exists to land one
contrast: the same model, the same diff, reviewed twice, and the second one knows things.

## Before you record

Capture a fresh transcript, then rehearse the playback speed.

```bash
memolint reset --repo demo/orderflow --yes
MEMOLINT_FORCE_COLOR=1 memolint demo --auto > docs/demo-transcript.ansi
memolint replay docs/demo-transcript.ansi --marks
```

Record the replay, not the live demo. A live run includes API latency and rate-limit
waits; the replay has the same output with a rhythm you control.

```bash
memolint replay docs/demo-transcript.ansi --speed 1.4 --countdown 3
```

Terminal setup: font size 18 or higher, dark theme, window about 100 columns, notifications
off, everything else closed. Record at 1080p or better.

To shoot a single section, use the cue points:

```bash
memolint replay docs/demo-transcript.ansi --start 155 --stop 184 --speed 1.2
```

| Cue line | Section |
|---|---|
| 1 | PR #1: Add coupon validation |
| 59 | The team responds |
| 66 | PR #2: Add order export for finance |
| 129 | The team responds |
| 134 | PR #3: Add refund summary endpoint |
| 138 | memory OFF |
| 155 | memory ON |
| 184 | What the reviewer now knows |

## Before you submit: set the repo URL

The end card shows a repo URL, and the submission repo is published by the team lead under
a different name from this working copy. Nothing is hardcoded, so once that repo exists,
re-render with it:

```bash
python scripts/beat_edit.py --bpm 150 --audio docs/track.wav   --repo https://github.com/WaifuPuller/MemoLint --out docs/memolint-edit.mp4
```

Or set it once and forget the flag:

```bash
export MEMOLINT_REPO_URL=https://github.com/WaifuPuller/MemoLint
```

The URL is resolved in this order: `--repo`, then `MEMOLINT_REPO_URL`, then this checkout's
own git remote. Rendering takes a few minutes and nothing else changes, so do this last,
after the repo is final. The card shrinks the text to fit, so a long URL is safe. Update the
YouTube description at the bottom of this file to match.

## The edit

Music: one upbeat track, around 100-120 BPM, starting quiet. Cut on the beat. Suggested
free sources: YouTube Audio Library, Pixabay Music. Duck the music under every voice line.

`[TEXT]` is an on-screen caption. `[CUT]` is a hard cut on the beat.

---

**0:00-0:10 — Cold open. No intro, no name, no greeting.**

Screen: the memory OFF panel, then immediately the memory ON panel, side by side or hard
cut between them. Freeze on the one line that matters.

> Voice: "Same model. Same code. One of these reviewers has been here before."

`[TEXT] same model. same diff.`
`[CUT]`

---

**0:10-0:25 — The problem, stated once.**

Screen: scroll fast through a generic review, the kind every tool writes.

> Voice: "Every AI reviewer starts from zero on every pull request. It doesn't know your
> conventions. It repeats the suggestion you rejected last week. It has no idea this
> pattern took production down in September."

`[TEXT] it forgets everything`

---

**0:25-0:40 — Name it and move.**

Screen: the repo, then one clean shot of the architecture: diff plus memory going into the
model, memories going back out.

> Voice: "So I gave it a memory. Memolint reviews code, and Hindsight remembers what your
> team said about it."

`[TEXT] Memolint | code review with a memory`

---

**0:40-1:15 — PR 1. Cold.**

Screen: replay from line 1, speed 1.6. Let findings land, don't read them out.

> Voice: "First pull request. The bank is empty, so this is a normal review. Then a human
> answers: one suggestion is right, one is wrong for this team, and two conventions get
> written down."

`[TEXT] 0 memories`
Hold on `rule stored: no type hints on private helpers`.
`[CUT]`

---

**1:15-1:50 — PR 2. It changed.**

Screen: replay from line 66, speed 1.4. Highlight the `precedent:` lines with a zoom or a
box. Then hold on the "Deliberately not raised" table.

> Voice: "Second pull request, different file. Now every finding cites the rule behind it.
> And it is quietly not raising the one we rejected, with the reason attached."

`[TEXT] 15 memories recalled`
`[TEXT] it stopped repeating itself`
`[CUT]`

---

**1:50-2:25 — The payoff.**

Screen: replay 138 to 184. Play memory OFF fully, beat of silence, then memory ON.

> Voice: "Third pull request, reviewed twice. Memory off: a generic performance warning.
> Memory on, same model, same diff."

Zoom on: *"This is the exact shape of the 2026-09-03 checkout outage."*

> Voice: "It connected a per-item API call to an outage caused by a per-item database
> query. Nobody told it those were the same bug. It matched the shape."

`[TEXT] it remembered the outage`

---

**2:25-2:45 — Close.**

Screen: `memolint ask "what does this team care about?"` output, then the repo URL.

> Voice: "The model is stateless. The memory isn't. That's the whole trick, and it runs
> entirely on free tiers."

`[TEXT]` the submission repo URL

---

## What surprised me, if you want one honest line

The first version of this demo scored itself wrong: the memory-off half ran on Groq and the
memory-on half fell back to Gemini after a rate limit, so it was comparing two models and
calling it memory. Pinning both halves to one provider was the difference between a demo
and a measurement.

## YouTube titles

1. I gave my code reviewer a memory, and it remembered an outage
2. Same model, same diff, two completely different reviews
3. My AI reviewer stopped repeating the suggestion I rejected
4. Teaching a code reviewer what my team actually cares about
5. The code reviewer that connected a bug to a three-week-old outage

## Thumbnail prompt

Paste into Nano Banana with a photo of one or more team members attached.

> Generate a viral YouTube thumbnail, 16:9. Left half: a dark terminal showing a generic
> code review comment, greyed out and marked with a red X. Right half: the same terminal
> glowing, showing a review comment that references a past production outage, marked with a
> green check. Between them, large bold text reading "SAME MODEL". Place the attached person
> at the bottom right, looking at the right-hand screen with a surprised expression. High
> contrast, saturated colours, thick readable text, no small print.

## Description

Paste under the video, with the repo URL filled in.

> An AI code reviewer that remembers. Most review bots start from zero on every pull
> request: they repeat suggestions your team already rejected and know nothing about the
> bugs that hurt you before. This one stores team conventions, reviewer feedback and past
> incidents in an agent memory layer, then recalls them before each review. In this demo the
> same model reviews the same diff twice, and the version with memory connects a per-item
> API call to an outage caused by a per-item database query.
>
> Code: https://github.com/WaifuPuller/MemoLint
> Hindsight: https://github.com/vectorize-io/hindsight
> Docs: https://hindsight.vectorize.io/
> Agent memory: https://vectorize.io/what-is-agent-memory
