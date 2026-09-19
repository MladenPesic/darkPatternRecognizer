# darkPatternRecognizer — Project Plan

**Status:** Phase 0 cleanup complete. Data collection and labeling complete. Modelling
not started.
**Repo:** https://github.com/MladenPesic/darkPatternRecognizer
**Last updated:** 17 September 2026

---

## 0. How to work on this project

**The repository owner writes the implementation code.** This is a learning
project built to demonstrate skills for hiring, so authorship matters. Claude
Code's role is to review code, explain concepts, argue against weak design
choices, and help debug — not to generate implementation unprompted. Ask before
writing code into a file.

**Explain before removing.** Phase 0 involves deleting code. For every deletion,
state what it does, why it is no longer needed, and what breaks — then wait for
approval. Do not batch deletions into a single silent commit.

**Deviation protocol.** If any part of this plan looks wrong, say so. State
plainly: what this document specifies, what you would do instead, and the
reasoning. Do not silently substitute a different approach. Disagreement is
useful; unannounced substitution is not.

**Work on a branch, merge through a pull request.** From Phase A onward, start
each phase with `git checkout -b phase-<x>-<topic>` off an up-to-date `main`,
and open a PR when the phase is done. `main` is protected by a rule requiring
pull requests; the Phase 0 commit (`d539ec1`) was pushed directly only because
admin rights bypassed it. Do not repeat that. The PR trail is also part of what
this repository is meant to evidence.

---

## 1. What this project is

Detecting **dark patterns** — manipulative interface design that pushes users
toward unintended purchases — in live e-commerce pages.

The research question is narrower than the title suggests, and it came out of a
failure:

> A DistilBERT text classifier fine-tuned on the public `ec-darkpattern` dataset
> (Yada et al.) reaches ~0.97 accuracy under cross-validation. Applied to live
> page elements, the same model scored **~2.5% precision**. It had learned
> *commercial language = dark pattern*.
>
> **With labels derived from element text alone, does adding geometry help a
> model generalise to a brand it has never seen?**

The question was narrowed on 17 September 2026. `label_elements.py` labels each
unique text once, from the text alone — the labeler never sees the page. A
geometry feature therefore cannot be credited with information the text lacks,
because the answer key does not contain it: two copies of `"18 hrs"` carry the
same label whether one is a countdown and the other a delivery estimate. What
the data can test is generalisation — with ~60 positive templates in training,
does geometry help on an unseen brand? See §8 D5.

Everything below serves answering that question credibly.

---

## 2. Current state

### Pipeline

| Stage | File | State |
|---|---|---|
| Capture | `capture.py` | working |
| LLM labeling | `label_elements.py` | working, run complete |
| Text baseline (Phase 3) | `train_classifier.py`, `classifier.py` | trained, known-weak, kept as baseline |
| Fusion model (Phase 4) | `train_fusion.py` | **incomplete — stops after computing class weights** |

### Schema

`scans` — `id`, `date_time`, `url`, `html_pointer`, `status`, `page_width`,
`page_height`

`elements` — `id`, `scan_id`, `element_type`, `element_text`,
`geometry_x/y/width/height`, `llm_label`, `llm_reason`

Notes:
- `is_visible` was dropped in Phase 0. `checkVisibility()` returned
  `true` for 100% of extracted elements, because the leaf-node filter already
  excludes hidden nodes — `innerText` is empty for anything unrendered. Hidden
  elements *do* appear in the data, but as `geometry_width = 0`. **Filter with
  `geometry_width > 0 AND geometry_height > 0`.**
- `darkpattern_label` / `confidence` held Phase 3 predictions. Dropped in Phase 0;
  the Phase 3 baseline (B2) runs offline over the test split instead.
- No `domain` column. Derive with `split_part(url, '/', 3)`.
- `llm_category` was dropped from the schema but is still requested in the
  labeling prompt. Deliberate: making the model name the tactic before emitting
  0/1 improves borderline consistency. The output is discarded.

### Capture method

Human-in-the-loop. A real Chrome instance is driven manually; pressing Enter
snapshots the current page. Deliberate — dark patterns cluster in cart and
checkout flows unreachable by a crawler.

Selector: `button, a, h1–h6, p, span, div, label, li, small, strong, em`, with a
leaf-node filter (skip any element whose child carries text) and a 500-character
cap.

---

## 3. Dataset facts

Measure against these; do not re-derive from assumptions.

**Volume** (visible elements only, `geometry_width > 0 AND geometry_height > 0`):

| | rows | unique texts |
|---|---|---|
| label 0 | 44,947 | 14,500 |
| label 1 | 1,030 | 179 |

Text-level positive rate **1.2%**; row-level **2.24%**.

### The template collapse — most important fact in this document

The 179 positive texts collapse to **~60 templates** once digits are
normalised. Top five:

| template | variants |
|---|---|
| `N added to cart N mins ago` | 40 |
| `N people viewing now` | 19 |
| `N left` | 12 |
| `only N left` | 8 |
| `N rsd off expires in` | 8 |

The top four account for 79 of 179. Fifteen templates appear exactly once.

**Consequences:**
1. Any split at the text level leaks. `"22 people viewing now"` in train and
   `"43 people viewing now"` in test is the same string with a different integer.
2. The effective positive class size is ~60, not 179.
3. Anywhere diversity is reported, normalise digits first:
   `regexp_replace(lower(text), '\d+', 'N', 'g')`.

### Positives by domain

DHgate 70, Temu 35 (together **59%**), SHEIN 14, Macy's 9, Old Navy 8, Gap 7,
Banggood 7, AliExpress 7, then a tail of 1–4.

**Zero positives, non-trivial volume:** Patagonia (485 texts), Zalando (645),
Muji (306), H&M (384), Burlington (228), Zara (163).

That last group is the most valuable part of the dataset. Phase 3 failed because
it never saw enough calm commercial pages to learn that commerce ≠ manipulation.
These domains are the control group.

### Known labeling edge cases

Documented, deliberately **not corrected**. Useful for the writeup, not for
relabeling:

- **Purchase limits** — `"Max. Order: 2 Piece"`, `"Max. 1 pcs/shopper"`. The
  rubric does not cover purchase caps.
- **Weasel discounts** — `"Up to 35% off"` vs `"40% off"`. The "up to" hedge is
  not a written rule.
- **Timeframe granularity** — the cutoff between `"4 mins ago"` and
  `"bought in last month"` is undefined.
- **Context-dependent strings** — `"18 hrs"` is likely a delivery estimate.
  *Text alone cannot disambiguate this; position might.* Use as a worked example
  of the project's core hypothesis.
- **Scraped customer reviews.** User-generated content is present in the
  dataset. It is not interface design. Decide whether it belongs in the label
  space.

---

## 4. Phase 0 — Cleanup pass — COMPLETE (17 September 2026)

Kept as a record of what was removed and why. Also removed, beyond the list
below: the per-scan Gemini page report (`get_llm_report()` and the `llm_report`
column) — unused downstream and an LLM call on every capture. A report-on-demand
feature may return in Phase E.

**Do this first, before any modelling work.** Read the repository, identify dead
and unnecessary code, and propose removals with reasoning. Wait for approval on
each before deleting.

### 0.1 Remove screenshot capture and storage

Screenshots are no longer captured or stored. **Raw HTML archiving stays** — it
is the raw layer that allows elements to be re-extracted from past scans if the
selector ever changes, without re-scraping.

Remove:
- the `page.screenshot(full_page=True)` call in `capture_page()`
- the screenshot entry from the `files_to_upload` list in
  `upload_files_to_storage()`
- `screenshot_pointer` from `update_scan_row()` and from the `scans` table
- any screenshot objects left in the Supabase storage bucket

Keep: `page.content()`, the HTML upload, `html_pointer`, the `supabase` client
and dependency, and `policies.sql`. `upload_files_to_storage()` now handles one
file instead of two — simplify its signature accordingly rather than leaving a
single-item loop.

`capture_page()` then returns `html_text, html_content, extracted_data, dims`.

Expected effect: scans get noticeably faster. Full-page screenshots on long
pages were the slowest step in the capture loop.

### 0.2 Drop `is_visible`

Constant `true` across the dataset. Remove from the extraction JS, the INSERT,
and the table.

### 0.3 Remove the Phase 3 classifier from the capture loop

If still wired in: `classify_elements()` and `from classifier import predict`
come out of `skeleton_test.py`. **Keep `classifier.py`** — the model is needed as
a baseline in Phase B, run offline over the test split.

### 0.4 Portability and hygiene

- Chrome executable path and profile dir are hardcoded to a Windows machine in
  `main()`. Move to env vars.
- `classifier.py` loads the model at import time. `models/` is gitignored, so
  this breaks import on a fresh clone. Make it lazy.
- `requirements.txt` is a full `pip freeze` of a JupyterLab environment. Trim to
  direct dependencies.
- `for set in [...]` in `train_fusion.py` shadows the builtin.
- `skeleton_test.py` is the main entry point and badly named. Renaming is
  optional; if done, use `git mv` to preserve history.

### 0.5 Commit

Once removals are approved and applied, commit and push before starting Phase A.
Keep this as its own commit — a clean "remove storage layer and dead code" diff
is easier to review than cleanup mixed into modelling work.

---

## 5. Phase A — Freeze the dataset split

Nothing downstream is meaningful until this is right.

**All collected brands are retained.** No domain is excluded from the dataset —
the split assigns brands to train/val/test, it does not drop them.

### A1. Brand grouping

Hosts do not map 1:1 to retailers. Build an explicit mapping — a dict, not a
regex — so grouping decisions are visible and reviewable:

```
www.hm.com, www2.hm.com                                  -> hm
www.zara.com, account.zara.com                           -> zara
www.zalando.co.uk, www.zalando.com, accounts.zalando.com -> zalando
www.gap.com, oldnavy.gap.com                             -> gap
www.banggood.com, m.banggood.com                         -> banggood
roe.shein.com                                            -> shein
```

Gap and Old Navy share a parent and a platform; treating them as independent
would leak templates. Record the reasoning either way.

### A2. Split assignment

Split **by brand, drawn randomly under constraints** — not by hand.
*(Decided 19 September 2026; this reverses the earlier recommendation to assign
brands by hand.)*

Grouping by brand is non-negotiable: the ~60 positive templates differ only by
digits, so a row- or text-level split puts `"22 people viewing now"` in train and
`"43 people viewing now"` in test, and recall then measures memorisation. Worse
for this project, elements from one brand share a page template, so geometry
features leak position as well as phrasing — the fusion arm would score highest
having learned nothing transferable. And since the claim is generalisation to an
unseen brand (§1), an ungrouped split has nothing left to measure.

Hand-picking the test brands is a separate matter, and it invites the objection
that the test set was chosen to flatter the result. Draw it instead:

- `GroupShuffleSplit` (or equivalent) with **brand as the group** and a fixed
  seed, roughly 60/20/20 by brand.
- **Redraw until the constraints hold:** test contains at least 25 positives,
  and at least two zero-positive brands. With 59% of positives in two domains a
  naive draw can leave test nearly empty, which is what the hand-assignment was
  guarding against; the constraint handles it without choosing the winner.
- Record the seed, the number of draws rejected, and the final assignment.

**Stronger, if time allows:** draw several constraint-satisfying splits with
different seeds and report each metric as a mean and spread across them. One
split with ~35 test positives is a noisy measurement; five make the ablation far
harder to dismiss. Pick one split as canonical for error analysis.

Write the assignment to a committed file (`splits.json` or similar). It must not
be regenerated at runtime — a split that changes between runs invalidates every
comparison.

### A3. Leakage assertion

**Hard failures** — the script exits non-zero:
- any brand appears in more than one split
- any scan_id appears in more than one split
- test positive count falls below 25

**Reported, not fatal:** the share of test positive templates (digit-normalised)
that also occur in train. This cannot be driven to zero — `only N left` appears
on unrelated sites — and forcing it to zero would mean discarding the common
patterns the task is about. Print the number and carry it into the results.

Because that overlap exists, D4 breaks the test metrics into two groups:
positives whose template was **seen in train** and those whose template is
**unseen**. The unseen group is the honest measure of generalisation, and it is
where geometry should help if the hypothesis holds.

**Deliverable:** `splits.json`, a split-building script, and a passing leakage
assertion.

---

## 6. Phase B — Baselines

Three baselines, evaluated on the identical frozen split. Without these the
fusion result means nothing.

**B1. Keyword/regex baseline.** Hand-written patterns for `left`, `sold`,
`viewing now`, `ends in`, `expires`. This is the bar to beat. Given the template
collapse it may score well — if fusion cannot beat regex, that is the finding
and it should be reported honestly.

**B2. Phase 3 model (`classifier.py`), run offline over the test split.**
Trained on `ec-darkpattern`, not on this data. Documents the distribution-shift
result with a number.

*Prerequisite — the model artifact and its training data were lost with an old
laptop and must be restored before B2 can run:*

1. Download `dataset/dataset.tsv` from
   [yamanalab/ec-darkpattern](https://github.com/yamanalab/ec-darkpattern)
   (Apache-2.0) to `data/ec-darkpattern/dataset.tsv`.
2. Run `python train_classifier.py` to rebuild `models/darkpattern-distilbert`.
   The venv is CPU-only, so start it early in the session; it is slow.
3. Record in `DECISIONS.md` that this is a **retrained** model, not the one that
   originally scored ~2.5% precision. Same script, same seed, different machine
   — so B2's numbers are a reproduction, not the original measurement.

**B3. Text-only on this project's labels.** Same encoder and head as the fusion
model, text features only. This is the real control — B2 is a different dataset
and cannot isolate the contribution of geometry.

---

## 7. Phase C — Fusion model

### C1. Architecture

**Do not fine-tune a full transformer on ~60 positive templates.** It will
memorise them. Use a frozen encoder as a feature extractor:

1. Frozen DistilBERT (or a sentence-transformer) → mean-pooled embedding
2. Geometry feature vector, standardised
3. Concatenate → small MLP head (one or two hidden layers) or gradient boosting

Cache the embeddings to disk. They never change, and recomputing them each run
wastes hours.

All three arms — text-only, geometry-only, fusion — must use the **same head
architecture, same split, same seeds**. Otherwise the comparison measures
architecture rather than features.

### C2. Geometry features

Already in `train_fusion.py`: `x_norm`, `y_norm`, `area_norm`, `aspect_ratio`,
`text_count` (repetition of the same text within a scan).

Worth adding:
- `is_above_fold` — viewport height was not captured, so use a documented
  constant (e.g. 900px) and note the approximation
- `y_norm_log` — positions are heavily skewed toward the top
- `element_type` one-hot — cheap, but it is DOM structure rather than geometry;
  keep it as a separate arm or state clearly that it is included

Normalise by the stored `page_width` / `page_height` from `scans`. These are
measured at capture time — do not infer page size from the largest element.

### C3. Class imbalance

At 2.24% positive rows, handle explicitly: class weights (already computed in
`train_fusion.py`), or focal loss, or threshold tuning on validation. Choose one
and justify it. Do not resample in a way that duplicates templates.

---

## 8. Phase D — Evaluation

### D1. Metrics

**Accuracy is meaningless here** — predicting all-zero scores 97.8%.

Report:
- **PR-AUC** (primary)
- precision, recall, F1 at a validation-tuned threshold
- the absolute count of test positives, always, next to every metric
- bootstrap confidence intervals — with ~35 test positives, point estimates are
  unstable and stating them bare is misleading

### D2. The headline evaluation

**False positive rate on the zero-positive brands that landed in the test
split** (candidates: Patagonia, Muji, Zalando, H&M, Burlington, Zara — which of
them are in test is decided by the draw in A2, and the constraint guarantees at
least two). Measure this on test brands only; a brand used in training cannot
measure false positives. This directly measures the failure that motivated the
whole project. Phase 3 scored ~2.5% precision because it fired constantly on ordinary
commercial text. A low FP rate here is the result worth leading with.

### D3. Ablation table

| arm | features | PR-AUC | P | R | F1 | FP rate on calm brands |
|---|---|---|---|---|---|---|
| regex | — | | | | | |
| Phase 3 | text (ec-darkpattern) | | | | | |
| text-only | text (this data) | | | | | |
| geometry-only | geometry | | | | | |
| **fusion** | text + geometry | | | | | |

### D4. Error analysis

Group errors by digit-normalised template. Which templates does fusion catch
that text-only misses? If geometry helps, expect the gain on position-stable
widgets (`N people viewing now`, `N added to cart N mins ago`) that sit in fixed
spots on product cards. That is the mechanism the hypothesis predicts — confirm
or refute it explicitly.

### D5. Honest framing

Two limits, both stated in the README.

First, the labels were produced from text alone, so no result here can show that
geometry carries information the text does not. The claim the data supports is
about generalisation to unseen brands.

Second, with ~60 templates and 59% of positives from two domains, the defensible
claim is **"geometry helps on this dataset"**, not "geometry helps. Precision about what the data supports is
the skill being demonstrated.

---

## 9. Phase E — Serving

Only once the model is evaluated.

**E1. Inference API.** FastAPI, one endpoint: accept a URL, run the existing
capture, score each element, return flagged elements with bounding boxes and
scores. Reuse `capture.py`'s capture rather than reimplementing it.

**E2. Visual demo — highest portfolio value per hour of work.** Capture a page,
score its elements, and draw boxes over the flagged ones on a screenshot taken
at demo time. Since stored screenshots are being removed (Phase 0.1), this is
generated live rather than read from storage. One annotated image communicates
the entire project to someone who will not read the README. Build it before any
other frontend work.

**E3. Containerisation.** Dockerfile including the Playwright base image.
Chromium dependencies are the awkward part.

---

## 10. Phase F — Data layer

Relevant to the data-engineering skills this project is meant to evidence.

Current state is a single Postgres instance with two tables and ad-hoc queries.
Reasonable at this volume — do not over-engineer it into a warehouse it does not
need.

What is worth building:

**F1. dbt project over Supabase Postgres.** `stg_scans`, `stg_elements`,
`dim_brand` (the mapping from A1), `fct_elements` with derived geometry
features. Adds tested, documented, version-controlled transformations — which is
what "warehousing" means on a CV, rather than a star schema over 45k rows.

**F2. Data quality tests.** Non-null geometry on visible elements, label values
in `{0,1}`, no orphan `scan_id`, brand mapping covers every host. dbt tests
cover this natively.

**F3. Feature extraction as a dbt model**, not Python. Geometry normalisation is
pure SQL. Moving it into the warehouse layer means the features are reproducible
and inspectable, and the training script just reads a table.

---

## 11. Phase G — Repository presentation

**G1. README.** Lead with the failure: 0.97 accuracy in-distribution, 2.5%
precision in the wild, and the experiment designed to address it. A diagnosed
negative result reads better than an unqualified success claim.

**G2. `DECISIONS.md`.** Short entries: what was decided, what the alternatives
were, why. Candidates already accumulated: wiping the v1 dataset and re-scraping
after the collector changed, testing `is_visible` and dropping it when it proved
constant, rubric v1.1's narrowing of the purchase-count rule, dropping
screenshots while keeping the raw HTML archive, grouping Gap with Old Navy, the
test-split assignment.

**G3. `RUBRIC.md`.** Append the edge cases from §3 as open questions with
reasoning.

**G4. Results notebook.** The ablation table, PR curves, error analysis, and at
least one annotated screenshot.

**G5. Reproducibility.** Trimmed `requirements.txt`, `.env.example`, and setup
instructions verified on a clean clone.

---

## 12. Order of work

1. **Phase 0** — cleanup pass. Propose, explain, get approval, delete.
2. **Commit and push.**
3. **Phase A** — freeze the split. Blocks everything after it.
4. **Phase B** — baselines, especially B1 (regex) and B3 (text-only on this data).
5. **Phase C** — fusion model.
6. **Phase D** — evaluation and ablation.
7. **Phase E2** — annotated demo.
8. **Phase F** — dbt layer.
9. **Phase G** — writeup.

Phases E, F and G can be reordered by whichever skill needs the most evidence.
A through D cannot — each depends on the last.

---

## 13. Decision log for this phase

Record the answers in `DECISIONS.md` as they are made:

- **Decided 19 Sep 2026:** brands are grouped, and the test set is drawn
  randomly under constraints rather than hand-picked (§5 A2). Record the seed,
  the rejected-draw count, and the resulting assignment.
- Whether Gap and Old Navy are one brand or two
- Fusion head: MLP or gradient boosting
- Imbalance strategy: class weights, focal loss, or threshold tuning
- Whether scraped customer reviews stay in the dataset
