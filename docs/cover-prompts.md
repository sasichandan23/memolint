# Dev.to cover image prompts

Dev.to covers render at roughly **1000 x 420** and get cropped to a wide banner, so keep
the subject centred and leave the edges quiet.

Paste into Nano Banana, Gemini image generation, or any generator you prefer.

**Both prompts deliberately ask for no text.** Image models still garble words, and a cover
with a misspelt heading on a technical article looks worse than one with no words at all.
Dev.to already prints your title over the page, so the cover only has to set a mood.

If you want text on the cover anyway, use the rendered versions instead:
`docs/cover-team-lead.png` and `docs/cover-team-member.png`, produced by
`python scripts/make_covers.py`.

---

## Team lead — pairs with "Hindsight made my code reviewer stop repeating rejected advice"

> A wide cinematic illustration, 1000x420, for a technical article about an AI code
> reviewer that stores a team's past decisions.
>
> Scene: a dark editor window on the left, rendered in deep charcoal blue, showing
> abstract blurred lines of code with no legible words. From the right side of that window,
> small glowing cards drift outward and settle into a softly lit archive of stacked slots,
> like a card catalogue made of light. A few cards glow warm orange and are marked with a
> subtle cross; most glow teal. The orange ones sit at the front, closest to the viewer,
> clearly the important ones.
>
> Mood: quiet, precise, engineering-grade. Not futuristic, not neon cyberpunk.
>
> Palette: deep charcoal blue background (#10141a), teal (#5ad1c4) and burnt orange
> (#ff6a3d) as the only accents, soft grey light.
>
> Style: clean vector illustration with subtle depth and glow, flat shapes, restrained.
> Wide composition with the archive centred and generous empty space at the left and
> right edges.
>
> Absolutely no text, no letters, no numbers, no logos, no watermarks, no human figures.

---

## Team member — pairs with "I proved Hindsight worked, then found my test was broken"

> A wide cinematic illustration, 1000x420, for a technical article about a scientific
> comparison that turned out to have a hidden second variable.
>
> Scene: two identical dark terminal windows side by side, perfectly mirrored, each
> showing abstract blurred lines with no legible words. A thin vertical seam of light
> runs between them. The left window is lit in cool teal, the right in warm orange, and
> a faint diagonal glitch or offset runs through the right one, as if it is not quite the
> same machine as the left despite looking identical at a glance.
>
> Mood: a subtle wrongness you notice on second look. Calm, not alarming.
>
> Palette: deep charcoal blue background (#10141a), teal (#5ad1c4) on the left, burnt
> orange (#ff6a3d) on the right, soft grey light.
>
> Style: clean vector illustration with subtle depth and glow, flat shapes, restrained
> geometry. Symmetrical wide composition, generous empty space above and below.
>
> Absolutely no text, no letters, no numbers, no logos, no watermarks, no human figures.

---

## If a generated cover comes back with garbled text

Regenerate with this appended to the prompt:

> The image must contain zero written characters of any kind. Remove all signage,
> labels, captions and UI text. Show only shapes, light and colour.

Or just use the rendered covers, which have correct text because they were drawn rather
than generated.
