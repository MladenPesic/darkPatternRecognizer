# Dark Pattern Labeling Rubric

**Single source of truth** for what counts as a dark pattern in this project.
Both the Gemini labeling prompt (`label_elements.py`) and any manual labeling MUST follow
this file. When a new edge case comes up: decide it here first, then update the prompt —
never make the call ad hoc, or the training labels and the gold test set silently diverge.

**Version:** 1.0 — 2026-07-26

---

## 1. The task

Binary classification of a single web-page **element text** (the visible text of one
`button` / `a` / `h1` / `h2` / `h3` element as captured by the scraper).

- `1` = the text employs a manipulative tactic
- `0` = it does not

---

## 2. Core definition

> **Label 1** if the text, *as written*, employs a manipulative **tactic**: manufactured
> urgency/scarcity, engineered social pressure, confirmshaming/guilt, forced action, or
> misdirection.
>
> **Label 0** otherwise: neutral UI text, or transparent marketing/offers that inform
> without pressuring, guilting, or deceiving.

### Three governing principles

1. **Tactic, not topic.** The *subject* being commercial is irrelevant. Sales, discounts,
   and prices are normal e-commerce content. Only flag manipulative *phrasing*.
   *(This exists because the Phase 3 text classifier learned "commercial = dark" and scored
   ~2.5% precision on real pages. Do not reproduce that bias.)*

2. **Judge the text on its face.** The classifier only ever sees the string — it cannot
   verify whether "Only 2 left" is true. So label the *tactic in the phrasing*, never
   unverifiable truth or intent.

3. **Tone reinforces, it does not decide.** `!` and ALL-CAPS amplify a manipulative
   reading but are not sufficient alone. `Welcome!` and `FREE SHIPPING!` are still `0`.

---

## 3. Categories

`urgency` · `scarcity` · `social_proof` · `confirmshaming` · `forced_action` ·
`misdirection` · `none`

---

## 4. Decided cases

### Label 0

| Text | Why |
|---|---|
| `Add to cart` | neutral UI |
| `Sale Price` | static label, no tactic |
| `Free shipping on orders over $50` | transparent offer |
| `Sign up for 10% off your first order` | transparent offer |
| `19 sold` | trivial cumulative count, no pressure |
| `4.8 out of five stars · 37,375 reviews` | factual aggregate stat |
| `Welcome!` / `FREE SHIPPING!` | loud tone, no tactic |
| `OVER 1,000 LOCATIONS` | informational claim |
| `Watch (& Shop) from Anywhere` | brand tagline |

### Label 1

| Text | Category | Why |
|---|---|---|
| `Hurry! These savings end soon` | urgency | manufactured time pressure |
| `Sale ends in 09:59` (countdown) | urgency | live deadline pressure |
| `Only 2 left in stock!` | scarcity | scarcity tactic |
| `Only few left` | scarcity | scarcity tactic |
| `Hot Deal` / `Lowest price since launch` | urgency | manufactured deal-urgency framing |
| `127 people are viewing this right now` | social_proof | fabricated real-time pressure |
| `400K+ sold` (large cumulative count) | social_proof | scale used to drive purchase |
| `No thanks, I'll pay full price` | confirmshaming | guilt-framed decline |
| `Too Good to Last` | urgency | FOMO framing |
| `More Can't-Miss Deals` | urgency | FOMO framing |

### Mixed blocks (important — this is common)

If a mostly-benign block (e.g. a product card with title, price, rating) contains an
**embedded tactic phrase**, label the whole element `1` and cite the specific phrase in
`reason`.

> `CABRRR Straight Fit Men Grey Jeans 69% off 1,299 ₹396 3.9 (203) Only few left`
> → `1`, `scarcity`, reason: *"embedded 'Only few left'"*

---

## 5. Open questions (unresolved — decide before they matter)

- **`#1 Bestseller` = 0 but `400K+ sold` = 1.** Both are static popularity claims. The
  current working distinction is *numeric scale* (a large number pressures; a badge
  describes), but this boundary is thin. Where exactly does a cumulative count flip from
  `0` to `1`? (`19 sold` = 0, `400K+` = 1 — what about `1,000`?)
- **Price anchoring alone** (struck-through price + `-50%`, with no urgency/scarcity/
  social-proof phrase). Currently treated as `0` under tactic-not-topic, but Mathur's
  taxonomy treats misleading reference pricing as a dark pattern.

---

## 6. Change log

- **1.0 (2026-07-26)** — initial version. Consolidates decisions made during Phase 3/4
  labeling. Key decision: large cumulative sold-counts (`400K+ sold`) = `1`; this
  supersedes earlier manual labels which marked them `0`. The manual gold set must be
  updated to match.
