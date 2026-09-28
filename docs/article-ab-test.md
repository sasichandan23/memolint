# I proved Hindsight worked, then found my test was broken

My side-by-side comparison showed the agent with memory beating the agent without it. It was also, silently, comparing two different models.

I'd built a reviewer that stores a team's conventions, past feedback and incidents in [Hindsight, the open source agent memory system from Vectorize](https://github.com/vectorize-io/hindsight), then recalls them before reviewing a pull request. To show it worked, I did the obvious thing: run the same diff twice, once with the memory bank connected and once without, and put the two reviews next to each other.

The result looked great. Memory off produced a generic performance warning. Memory on produced a high-severity finding that named a specific past outage. Exactly the story I wanted.

Then I looked at the run log properly.

```
memory off | 839 in / 345 out tokens | via groq
memory on  | 2042 in / 372 out tokens | via gemini
```

Different providers. Different models. My memory experiment had a second variable in it, and I'd been about to publish the result.

## How the second variable got in

The system is built to run on free inference tiers, which means rate limits are a normal operating condition rather than an exception. I'd handled that with a provider chain: try the primary, and if it returns a rate limit that would take too long to wait out, move to the next configured provider and carry on.

```python
except _Exhausted as e:
    remaining = self.configs[idx + 1:]
    if remaining:
        print(f"[llm] {cfg.provider} is rate limited; switching to {remaining[0].provider}")
        continue
```

That's good behaviour for a tool. A long-running review shouldn't die because one provider is having a minute. It's terrible behaviour inside a controlled comparison, because the failover is invisible by design. It logs a line and keeps going, which is what you want at 2am and exactly what you don't want when the whole point of the run is to isolate one variable.

The comparison ran four model calls in close succession. By the fourth, the primary provider's per-minute token budget was gone, the chain did its job, and the second half of my A/B landed on a different model. The result I was looking at was real, in the sense that those outputs genuinely came out of the system. It just wasn't evidence for the claim I was making.

## Two fixes, because there were two problems

The first fix is to make the comparison structurally incapable of switching models. Both halves now share one client, pinned after the first call:

```python
def pin_to_active(self) -> None:
    """Drop the fallbacks and stay on whichever provider last answered.

    Used when several calls must be comparable: switching models halfway through
    an A/B comparison would make the two sides measure different things.
    """
    self.configs = [self.cfg]
```

And if they somehow still differ, the run says so out loud instead of leaving me to notice:

```python
if r3a.provider != r3b.provider:
    console.print(f"[yellow]note:[/] the two halves ran on different providers "
                  f"({r3a.provider} vs {r3b.provider}), so this is not a like-for-like comparison.")
```

That second part matters more than the first. Pinning prevents the known failure. The warning catches the one I haven't thought of yet, and it costs four lines.

The second fix addresses the actual cause. Hitting a rate limit at all was avoidable. I was firing calls as fast as the code could produce them and letting the provider tell me to stop, which wastes a request, costs a retry, and in my case corrupted an experiment. So the client now paces itself against a rolling one-minute window:

```python
def reserve(self, projected: int, *, announce=None) -> None:
    """Wait, if needed, until this call fits inside the rolling one-minute budget."""
    if self.limit <= 0:
        return
    for _ in range(len(self.events) + 1):
        now = self._now()
        if not self.events or self._spent(now) + projected <= self.limit:
            return
        wait = 60.0 - (now - self.events[0][0]) + 0.5
        ...
```

The projection is approximate: characters over four for the prompt, plus the output ceiling. Approximate is fine, because the consequence of being slightly wrong is a voluntary wait rather than a wasted request.

Before pacing, that four-call sequence spent about 80 seconds in retry backoff and switched providers once. After, it completed with no rate limits and every call on the same model.

## The bug that the fix exposed

Writing a test for the pacing logic taught me something I hadn't considered.

My first test monkeypatched `time.sleep` to a no-op and asserted that a wait had been requested. It passed. The suite went from 6 seconds to 68.

The loop was structured as "while we're over budget, sleep and re-check". With sleep patched out, time never advanced, the budget never freed up, and the loop spun. It only terminated because the real clock eventually moved past sixty seconds and the recorded event aged out of the window. My test had been busy-waiting for a full minute and reporting success.

In production this never fires, because `time.sleep` really does sleep. But a loop whose termination depends on a side effect of the thing it's calling is a bad loop regardless. I gave it a bound and an injectable clock:

```python
def __init__(self, tokens_per_min, *, now_fn=time.time, sleep_fn=time.sleep):
    ...
    # Injectable so tests can exercise the waiting logic without real delays.
```

```python
def test_reserve_terminates_even_if_sleeping_does_not_advance_time():
    w = _RateWindow(8000, now_fn=lambda: 1000.0, sleep_fn=lambda s: None)
    w.record(5000)
    w.record(5000)
    w.reserve(8000)  # must return rather than spin
```

The suite is back to six seconds, and the waiting behaviour is tested properly with a fake clock instead of accidentally tested with a real one.

## What the honest comparison looks like

Re-run, both halves on the same model, same diff.

Without memory:

> **F1 MEDIUM — Sequential provider calls in loop**
> The loop calls `_provider_status(refund)` for each refund, which makes a network request per item. Consider fetching all refund statuses in a single batch call.

With memory:

> **F1 HIGH — N+1 external API calls in loop**
> This is the exact shape of the bug that caused the 41-minute checkout outage. You must batch these requests or parallelize them with a bounded concurrency limit.
> *precedent:* one call per item inside a loop exhausted the Postgres connection pool.

The severity moved from medium to high, the finding cites the stored incident, and a separate section lists a suggestion the agent deliberately withheld because this team rejected that class of advice previously.

That's a weaker-sounding claim than "the memory version was dramatically better", and it's the one I can actually defend. The difference is attributable to the memory layer, because nothing else changed.

## What I took from it

**A fallback and an experiment want opposite things.** Resilience means papering over a failure and continuing. Measurement means stopping the moment a condition changes. Any code path that can silently substitute one component for another needs to be disabled, or at minimum surfaced, inside a comparison.

**Log the thing you're varying, on every run.** I only caught this because the review output happened to print which provider answered. That line existed as a convenience. It turned out to be the only reason the flaw was visible at all, and I'd now add it deliberately.

**Prefer waiting on purpose to being told to wait.** Voluntary pacing is cheaper than retry backoff, and it's deterministic, which matters if anything downstream depends on timing.

**A test that passes slowly is telling you something.** The 68-second suite was the real bug report. I nearly shrugged it off as a slow network call.

**Publishing a weaker but sound result beats publishing a strong broken one.** The corrected comparison is less dramatic. It is also the only version worth showing anyone.

None of this is specific to memory systems, but memory is where it bit me, because the whole value proposition rests on a before-and-after that a reader has to trust. If you're building on agent memory, [the Hindsight docs](https://hindsight.vectorize.io/) cover the retain and recall primitives, and Vectorize's overview of [what agent memory is and how it differs from retrieval](https://vectorize.io/what-is-agent-memory) is a useful starting point.

The agent does get meaningfully better when it remembers what a team told it. I just had to fix my measurement before I could honestly say so.

*Code: <REPO_URL>*
