# Decisions

Short record of choices that are not obvious from the code: what was decided,
what the alternatives were, and why. See `PROJECT_PLAN.md` for the phase each
decision belongs to.

---

## 2026-09-19 — Gap and Old Navy are one brand

**Decided:** `www.gap.com` and `oldnavy.gap.com` map to a single brand, `gap`,
in `brands.json`. The train/val/test split treats them as one group, so both
always land in the same split.

**Alternative:** treat them as two independent brands. That would give 25
brands instead of 24 and one more brand available to the test draw.

**Why:** Old Navy is a Gap Inc. label and the two sites run on the same
e-commerce platform, so they share page structure and widget phrasing. If one
went to train and the other to test, the test score would partly measure the
same widget on the same template — which is the leak Phase A exists to prevent.
The split is grouped by brand precisely because elements from one page template
leak both phrasing and geometry (`PROJECT_PLAN.md` §5 A2).

**Cost, recorded honestly:** merging them makes `gap` the second-largest source
of positives (152 positive rows: 99 from gap.com, 53 from oldnavy.gap.com,
12 digit-normalised positive templates). A draw that puts `gap` in test moves a
large block of positives out of train in one step. This is a real loss of
draw stability, accepted because the alternative is a leak.

---

## 2026-09-22 — Split constraints are counted in templates, not rows

**Decided:** the rules the random draw must satisfy are counted in
**digit-normalised positive templates**, combined as a **union** across brands:

| # | applies to | rule |
|---|---|---|
| 1 | test | at least 12 positive templates |
| 2 | test | at least 2 zero-positive brands |
| 3 | train | at least 45 of the 82 positive templates |

**Alternative:** `PROJECT_PLAN.md` originally said "test contains at least 25
positives", without saying whether that meant rows or texts.

**Why:** the unit matters more than the number. dhgate has 513 positive rows but
only 12 distinct templates — the rest are the same widget with different digits.
A draw can pass "25 positive rows" while giving test only 3 distinct templates,
which would mean reporting recall over three widgets. Templates are the unit
§3 already argues is the real class size.

The union matters too: the 24 brands' template counts sum to 90, but the true
union is 82, because 6 templates appear on two brands and 1 on three. Summing
would let a draw claim templates it does not have.

**Rule 3 was added because the original rules constrained only test.** A draw
putting dhgate, gap and temu in test passes rules 1 and 2 while leaving train
with ~89 positive rows. The model would then score badly, and no one could tell
whether geometry was useless or training data was simply starved.

**Recorded honestly:** rule 3 was specified in advance and **never bound** — all
200 seeds satisfied it. It is kept as a guard against the rare catastrophic draw,
not because it shaped the result. Rule 2 is the binding constraint (36% of draws
pass it); rule 1 passes 82.5% of the time.

---

## 2026-09-22 — No fixed validation set; cross-validation inside train

**Decided:** the split is **19 train / 5 test**, with no held-out validation
brands. The decision threshold is tuned on out-of-fold predictions from
**5-fold cross-validation grouped by brand** inside the 19 train brands. Folds
are built by sorting train brands by positive rows (descending, brand name
breaking ties) and dealing them round-robin into 5 folds. The fold assignment is
recorded in `splits.json`.

**Alternative:** the 60/20/20 split in `PROJECT_PLAN.md` §5 A2 — 14 train, 5
validation, 5 test.

**Why:** the validation set exists to tune the decision threshold. With 24
brands, a random 5-brand validation set can contain almost no positives — 6 of
24 brands have zero positives and another 6 have only 1–2 positive templates. A
threshold tuned on 3 positive examples is noise, and every precision, recall and
F1 number in the ablation table would rest on it. Cross-validation inside train
tunes the threshold on all 19 brands instead of 5, and keeps the no-leak
property because a brand is never in both sides of a fold.

**Cost:** slightly more code in Phase C, and one more thing to record. This
supersedes the 60/20/20 in the plan; §5, §7 C3 and §8 D1 were updated.

---

## 2026-09-22 — Five splits, drawn by rule, seed 5 canonical

**Decided:** seeds 0–199 were scanned; **46 satisfied all three rules**. The
**first five accepted seeds in ascending order — 5, 6, 7, 9, 15** — are the
splits. **Seed 5 is canonical** for error analysis and the annotated demo. Every
metric is reported as a mean and spread across the five.

**Alternative:** a single split. `PROJECT_PLAN.md` §5 A2 lists multiple splits as
"stronger, if time allows".

**Why:** test is small. The canonical split has 266 positive rows, but they come
from three brands and 29 templates, and across the five accepted splits test
positives range from 42 to 537. A single point estimate from one draw is
unstable and a reader who knows the field will say so. Phase C caches frozen
encoder embeddings, so each extra run is a small head on cached features — the
cost is minutes, not hours.

**The selection rule was fixed before looking at any split:** lowest-numbered
accepted seeds, no judgement. This is the whole point of drawing rather than
hand-picking, and choosing among accepted seeds afterwards would quietly undo it.

---

## 2026-09-22 — Known limitations of the frozen split

Not decisions, but properties of the split that belong in the README rather than
being discovered by a reader.

**The five splits are not independent.** They are drawn from the same 24 brands,
so their test sets overlap. The spread across them measures sensitivity to the
draw, not five independent experiments.

**The D2 false-positive result is mostly zalando.** Only 6 brands have zero
positives, and rule 2 pulls 2–3 of them into every test set, so overlap is
forced. Across the five splits zalando appears in test 4 times, muji, burlington
and patagonia twice each, hm and zara once. All six calm brands are covered at
least once, but the repeated measurements are dominated by one brand.

**dhgate dominates threshold tuning.** In the canonical split dhgate holds 513
of train's 764 positive rows. Because folds group whole brands, the fold holding
dhgate carries roughly two thirds of the positives, so the threshold chosen from
pooled out-of-fold predictions is largely dhgate's threshold. Sorted dealing
spreads brands evenly; it cannot split one brand.

**Seed 9 is thin.** It passes the rules with 42 positive rows, 12 templates, of
which only 7 are unseen in train. It stays in — dropping an accepted split
because it looks weak would be hand-picking. Expect it to be the noisiest of the
five.
