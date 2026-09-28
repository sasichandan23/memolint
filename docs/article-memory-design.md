# Hindsight made my code reviewer stop repeating rejected advice

The thing that finally made our automated reviewer useful wasn't a better model. It was storing the suggestions we turned down.

Every AI code reviewer I've used has the same defect. It reads a diff, produces a competent list of observations, and forgets the exchange. Next week it reads another diff from the same repository and tells you the thing you already declined, in the same confident tone. The model isn't wrong exactly. It has no way to know this team decided, months ago and for good reasons, that private helpers don't get type hints.

I built Memolint to fix precisely that, and the interesting part turned out to be the taxonomy of what to remember rather than the reviewing itself.

## What the system actually is

Memolint is a command-line reviewer. It takes a diff, a git range, or a pull request, and produces findings. That part is unremarkable; any competent prompt does it.

The part that matters sits either side of the model call. Before reviewing, it queries a memory bank for what the team has said that bears on this change. Afterwards, once a human responds, it writes back what happened. The memory layer is [Hindsight, Vectorize's open source memory system for AI agents](https://github.com/vectorize-io/hindsight), which gives me three primitives: `retain` to store, `recall` to retrieve against a query, and `reflect` to reason over the whole bank.

The model stays stateless. The bank does not. One bank per repository, so the reviewer's opinions are scoped to the team that formed them.

## Four kinds of memory, and one of them does most of the work

My first version retained everything as undifferentiated text. Recall then surfaced the agent's own previous reviews far more often than anything a human had said. It was mostly remembering itself talking.

The fix was to classify what goes in, and tag it so recall results can be grouped when they're rendered into the prompt:

| kind | what it is |
|---|---|
| `convention` | An explicit team rule, also stored as a Hindsight directive |
| `feedback` | How a human responded to a specific finding, and why |
| `incident` | A bug or outage tied to a code pattern |
| `review` | A summary of each review posted |

`feedback` is the one that earns its keep, and specifically the rejections. An accepted suggestion tells you the reviewer was already right. A rejected one tells you something you could not have derived from the code:

```python
def record_feedback(self, finding, verdict, note, pr_ref):
    where = f"{finding.get('file')}:{finding.get('line')}"
    text = (
        f"Reviewer {verdict} the suggestion '{finding.get('title')}' on {where} "
        f"in {pr_ref}. Suggestion was: {finding.get('body', '')[:300]}"
    )
    if note:
        text += f" Reviewer said: {note}"
    if verdict == "rejected":
        text += " Do not raise this kind of suggestion again for this team unless the rule changes."
    self._retain(text, kind="feedback", extra_tags=["feedback", verdict, f"pr:{pr_ref}"])
```

That trailing sentence on rejections is doing real work. Without it, the model treats the rejection as trivia about the past. With it, the rejection reads as an instruction about the future.

Conventions get stored twice: once as an ordinary memory, and once as a Hindsight directive, which is a standing instruction attached to the bank rather than a fact to be retrieved by similarity. That distinction matters. "Use guard clauses instead of nested conditionals" should apply to every review whether or not the diff happens to be similar to the one that produced the rule. Similarity search is the wrong retrieval mechanism for a rule.

## Recall is a budget problem, not a search problem

The naive approach is to recall everything. That's wrong twice over: the prompt has a ceiling, and irrelevant memories dilute the ones that matter.

I build a query from what the diff is actually about, and cap what comes back:

```python
def build_recall_query(bundle):
    added = []
    for f in bundle.files:
        for line in f.patch.splitlines():
            if line.startswith("+") and line.strip("+ ").strip():
                added.append(line[1:].strip())
    snippet = " ".join(added)[:600]
    return (
        f"Code review of '{bundle.title}' touching {', '.join(bundle.paths[:8])}. "
        f"Team conventions, past review feedback, rejected suggestions, and incidents "
        f"relevant to: {snippet}"
    )
```

Added lines matter more than removed ones, since a review is about what's arriving. Recall gets a 1,000 token ceiling and the diff gets 2,500, which keeps a review between 1,000 and 2,300 input tokens, memories included.

Results come back tagged, get grouped by kind, and render under headings the system prompt treats as binding rather than advisory. There's a real difference between telling a model "here is some context" and telling it "these are rules this team has already settled".

## Teach it to match on shape, not on wording

The best behaviour I got out of the system came from one paragraph in the prompt, and it took me embarrassingly long to write.

A recorded incident said that per-row database queries inside a loop had exhausted a connection pool. A later change made one external API call per item inside a loop. Those are the same bug. The reviewer flagged the performance issue, correctly, and completely failed to connect it to the incident, because the words didn't overlap: one said "database query", the other said "API request".

So I stopped describing what to recall and started describing how to match:

```
- Incidents are the highest-value memory you have. Match them on the SHAPE of the bug,
  not on exact wording: "one database query per item inside a loop" and "one network
  call per item inside a loop" are the same shape. If a change repeats the shape of a
  past incident, the finding is "high" severity and its "precedent" must name that
  incident and what it cost.
```

After that change, the same diff produced this, unprompted:

> **F1 HIGH — N+1 external API calls in loop**
> The loop calls `_provider_status(refund)` for every refund, which makes one external API request per item. This is the exact shape of the bug that caused the 41-minute checkout outage. You must batch these requests or parallelize them to avoid exhausting the connection pool.

The generic reviewer says this will be slow. The one with memory says this is the thing that took us down, and names the cost. Only one of those gets a change prioritised.

## The before and after, concretely

Same model, same diff, memory disabled then enabled.

Without memory, a single medium-severity finding about sequential network calls in a loop. Accurate, forgettable, and indistinguishable from what any static analysis vendor would emit.

With memory, three things change. The finding is high severity and cites the incident. Every finding carries a `precedent` field naming the stored rule behind it. And a separate section lists what the reviewer deliberately chose not to raise:

> **Deliberately not raised (learned from you)**
> *Would have said:* Add type hints to private helper functions `_refunds_for` and `_provider_status`
> *Why not:* Team convention states that private helpers do not require type hints; only public functions need them.

That table is the feature I did not plan and now consider essential. Silence is invisible: if the agent stops mentioning something, you cannot tell whether it learned or just got distracted. Making suppression explicit turns an absence into evidence, and gives reviewers somewhere to correct the agent when it over-generalises from one rejection.

## What I'd tell someone building this

**Classify memories on the way in.** Retrieval quality is decided at write time. Once everything is undifferentiated text, no amount of clever querying separates "a human told us this" from "we said this ourselves last Tuesday".

**Store the negative cases.** Most memory systems get pointed at successes. Rejections carry more information per byte than anything else my agent stores, because they encode a judgment you cannot recover from the codebase.

**Rules and facts need different retrieval.** Similarity search is right for "what do we know about this file" and wrong for "what does this team always do". Hindsight's directives handle the second case, and separating the two removed a whole class of inconsistency.

**Prompt for the matching rule, not just the content.** Giving a model relevant memories is not the same as telling it how to decide that a memory is relevant. The shape-matching paragraph changed behaviour more than any amount of additional context.

**Budget recall like you budget tokens, because you are.** More retrieved memories is not better. The ceiling forces a ranking, and the ranking is what makes the good ones visible.

None of this is specific to code review. Any agent that serves the same people repeatedly accumulates the same class of knowledge: what they accepted, what they refused, and what hurt them before. [The Hindsight documentation](https://hindsight.vectorize.io/) covers the retain and recall mechanics, and Vectorize's write-up on [what agent memory actually means](https://vectorize.io/what-is-agent-memory) explains why this is a different problem from retrieval-augmented generation over documents.

The model I'm running is not the smartest one available. It doesn't need to be. It just needs to remember what we told it.

*Code: https://github.com/WaifuPuller/MemoLint*
