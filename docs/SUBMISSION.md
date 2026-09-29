# Submission checklist

Submission repo: https://github.com/WaifuPuller/MemoLint

## Ready

- [x] Code, documented, MIT licensed, 29 tests passing
- [x] `README.md` explains how Hindsight memory is used, with the retain/recall flow
- [x] Demo video rendered: `docs/memolint-edit.mp4`, 2:09, 1080p, with audio
- [x] Thumbnail rendered: `docs/thumbnail.png`, 1280x720
- [x] Two articles written: `docs/article-memory-design.md`, `docs/article-ab-test.md`
- [x] Two LinkedIn posts written: `docs/linkedin-posts.md`
- [x] Backing track is synthesised, so there is nothing to licence

## Copy-paste packs

Everything each of you needs is in its own folder, one file per destination:

```
docs/submit/team lead/      article.md  linkedin.txt  reddit.txt  README.md
docs/submit/team member/    article.md  linkedin.txt  reddit.txt  README.md
```

Each file holds only the text to paste. The README in each folder has the steps.
Regenerate them after editing any article with `python scripts/build_submit_packs.py`.

## Three different texts, three different places

Do not paste the same thing everywhere. They are separate deliverables:

| Place | What goes there | Count |
|---|---|---|
| Dev.to / Medium / Hashnode | The full article, ~1,400 words | one per member |
| LinkedIn | The short post, under 800 characters. Article URL goes in the first comment, not the body | one per member |
| Reddit | A link post pointing at the article. No body text | one per member, different subreddits. **The submission form asks for these** |
| YouTube | The video | one per team |

A LinkedIn *article* and a LinkedIn *post* are different features. The post is the short one.

Minimum for eligibility: one article and one LinkedIn post each, plus one team video.
The submission form also asks for the Reddit links, so treat those as required too.

Only these four subreddits are allowed: r/llmdevs, r/sideproject, r/aiagents, r/aimemory.

Publish the article first, since the LinkedIn comment and the Reddit post both need its URL.

## Left to do, in order

**1. Add a repository description on GitHub.** The About box is empty. Judges see it first.

> A code reviewer that remembers your team's precedents. Built on Hindsight agent memory.

**2. Upload the video to YouTube, public.** Use `docs/thumbnail.png` as the thumbnail.
Title and description are at the bottom of `docs/VIDEO.md`. Pick one title:

- I gave my code reviewer a memory, and it remembered an outage
- Same model, same diff, two completely different reviews
- My AI reviewer stopped repeating the suggestion I rejected

**3. Each member publishes their article.** Medium, Dev.to, Hashnode or a LinkedIn
article. Must be public and linkable. Paste the markdown and check the headings and
links survived the paste.

Suggested split, since the second is a debugging story and should belong to whoever
lived it:

| Member | Article |
|---|---|
| Team lead | `article-memory-design.md` |
| Sasi Chandan | `article-ab-test.md` |

**4. Each member posts on LinkedIn.** Text in `docs/linkedin-posts.md`. Then two
comments on your own post: first the article URL, second
`https://github.com/vectorize-io/hindsight`.

**5. Submit the article as a link post to one subreddit.** r/llmdevs, r/sideproject,
r/aiagents or r/aimemory.

**6. Every member completes the Profile Review Form.** This is the team lead's
responsibility to chase, and it is easy to forget.

**7. Submit the final project form.** One submission per team, and only one.

## Two rules that disqualify

The word "hackathon" must not appear in any article or social post, including
hashtags. Both articles and both posts have been checked and are clean. If you edit
them, check again.

Only one final submission per team. Agree who presses submit.

## If a judge asks how to run it

```bash
git clone https://github.com/WaifuPuller/MemoLint && cd MemoLint
python -m venv .venv && . .venv/Scripts/activate
pip install -e .
cp .env.example .env     # add a free Groq key and a Hindsight key, see KEYS.md
memolint demo
```

A full transcript of that run is checked in at `docs/sample-demo-output.txt`, so the
behaviour is verifiable without any keys at all.
