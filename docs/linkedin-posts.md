# LinkedIn posts

One per team member, matching the article each of you publishes. Both are under 800
characters so nothing is hidden behind "see more" on mobile.

**How to post**

1. Publish the article first.
2. Post the text below. The repo link stays in the main post.
3. First comment: the article URL.
4. Second comment: `https://github.com/vectorize-io/hindsight`

The word that disqualifies is not in either post. Keep it that way if you edit.

---

## Post A — pairs with `article-memory-design.md`

> The most valuable thing my code reviewer remembers isn't what it got right.
>
> It's what my team turned down.
>
> I gave it a persistent memory with Hindsight. What to store mattered more than which model:
>
> → Accepted suggestions teach you little. It was already right.
>
> → Rejections encode a judgment you can't read off the codebase.
>
> → Rules belong in directives, not similarity search. A convention applies even when the diff looks unfamiliar.
>
> → Incidents need shape matching. "One DB query per item in a loop" and "one API call per item in a loop" are the same bug.
>
> Before: a generic warning about sequential calls.
> After: high severity, naming the outage that pattern caused.
>
> The model is stateless. The bank isn't.
>
> Code: https://github.com/WaifuPuller/MemoLint
>
> #AIAgents #AgentMemory #LLM #AI

---

## Post B — pairs with `article-ab-test.md`

> My before/after test showed the memory layer winning.
>
> Then I checked which model each half ran on.
>
> Different ones. Rate-limit failover had swapped models mid-comparison, and I nearly published it as evidence.
>
> What I changed:
>
> → Pinned both halves to one provider. A fallback and an experiment want opposite things: one hides a failure, the other must stop on one.
>
> → Made the run warn if the halves still differ. Four lines.
>
> → Paced requests against a rolling token budget rather than waiting to be rate limited.
>
> → Found a test passing while busy-waiting a full minute: I'd mocked sleep in a loop that needed the clock to move.
>
> Hindsight does make the reviewer better. I had to fix the measurement first.
>
> Code: https://github.com/WaifuPuller/MemoLint
>
> #AIAgents #AgentMemory #AIMemory #LLM
