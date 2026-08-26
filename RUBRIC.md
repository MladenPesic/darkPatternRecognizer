# Dark Pattern Labeling Rubric

**Single source of truth** for what counts as a dark pattern in this project.
Both the Gemini labeling prompt (`label_elements.py`) and any manual labeling MUST follow
this file. When a new edge case comes up: decide it here first, then update the prompt —
never make the call ad hoc, or the training labels and the gold test set silently diverge.

**Version:** 1.1 — 2026-07-26

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
| `4.8 out of five stars · 37,375 reviews` | factual aggregate stat (ratings alone, no count) |
| `400K+ sold` / `7 bought this` | static cumulative total, no timeframe (see §4.1) |
| `Cyber Sale in July` / `Christmas in July Sale` | a sale's *name* is not a tactic |
| `Currently Trending` | section header, descriptive |
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
| `127 people are viewing this right now` | social_proof | real-time activity pressure |
| `3 people bought this in the last hour` — **activity-framed** counts only | social_proof | live-activity pressure (see §4.1) |
| `No thanks, I'll pay full price` | confirmshaming | guilt-framed decline |
| `Too Good to Last` | urgency | FOMO framing |
| `More Can't-Miss Deals` | urgency | FOMO framing |

### 4.1 Purchase / activity counts — RESOLVED (v1.1)

The line is **activity vs. aggregate**, not magnitude.

| | Label | Why |
|---|---|---|
| **Activity / recency-framed** — implies live or recent activity | **1** `social_proof` | manufactured real-time bandwagon pressure |
| **Static cumulative total** — a lifetime aggregate stat | **0** | a product statistic, not a pressure tactic |

**The test question:** *does the text imply a timeframe or live activity?*
- `127 people are viewing this right now` → **1**
- `3 people bought this in the last hour` → **1**
- `Selling fast` / `In high demand` → **1**
- `400K+ sold` → **0** (lifetime total)
- `7 bought this` / `19 sold` → **0** (no timeframe implied)
- `4.8 stars, 37,375 reviews` → **0** (quality stat, not purchase activity)

**Rationale:** Mathur et al. (2019) flag **"activity messages"** under Social Proof —
recency-framed notifications of live activity — and found these are dark patterns *even when
truthful*, because the manipulation is the pressure framing, not falsehood. A static lifetime
aggregate is not an activity message; it is closer to a product spec.

**Why this was narrowed (v1.0 → v1.1):** v1.0 labeled *all* counts `1`. Measured against real
data that made **92% of the positive class a single pattern** (530/577), essentially
`text contains "sold"` — trivially solvable by regex, which would make the Phase 4
fusion-vs-text-only comparison meaningless (text-only would score near-perfect and geometry
could add nothing). Narrowing to activity-framed restores urgency/scarcity/confirmshaming as
the meaningful bulk of positives — the cases where layout signal actually matters.

*Watch for:* marketplace sites (Temu/AliExpress/Alibaba/Wish) supply almost all count-style
positives; keep site diversity in collection so the model doesn't learn "marketplace product
card = dark pattern" as a shortcut.

### Mixed blocks (important — this is common)

If a mostly-benign block (e.g. a product card with title, price, rating) contains an
**embedded tactic phrase**, label the whole element `1` and cite the specific phrase in
`reason`.

> `CABRRR Straight Fit Men Grey Jeans 69% off 1,299 ₹396 3.9 (203) Only few left`
> → `1`, `scarcity`, reason: *"embedded 'Only few left'"*

---

## 5. Open questions (unresolved — decide before they matter)

- **`#1 Bestseller` = 0 but any purchase count = 1.** Resolved pragmatically in §4.1: a
  *count* of purchases is activity data used for bandwagon pressure; a *badge* is a static
  descriptive claim. The line is defensible but not airtight — revisit if it causes label noise.
- **Price anchoring alone** (struck-through price + `-50%`, with no urgency/scarcity/
  social-proof phrase). Currently treated as `0` under tactic-not-topic, but Mathur's
  taxonomy treats misleading reference pricing as a dark pattern.

---

## 6. Change log

- **1.1 (2026-07-26)** — narrowed the purchase-count rule (§4.1) from "all counts = 1" to
  "activity/recency-framed = 1, static cumulative totals = 0", after a full labeling run
  showed the broad rule made 92% of positives a single regex-solvable pattern. Added
  `Cyber Sale in July` / `Currently Trending` = 0 to kill sale-name and section-header drift.
  **All labels produced under v1.0 are stale and must be regenerated.**

- **1.0 (2026-07-26)** — initial version. Consolidates decisions made during Phase 3/4
  labeling. Key decision: large cumulative sold-counts (`400K+ sold`) = `1`; this
  supersedes earlier manual labels which marked them `0`. The manual gold set must be
  updated to match.
