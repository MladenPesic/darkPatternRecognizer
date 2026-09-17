# Dark Pattern Recognizer

Detecting **dark patterns** — manipulative interface design that pushes users toward
unintended purchases — on live e-commerce pages.

> **Status: in progress.** The dataset is collected and labeled; the model is not trained
> yet. See [`PROJECT_PLAN.md`](PROJECT_PLAN.md) for the current phase and what comes next.
> No results are claimed below.

---

## The question this project asks

A published text classifier for this task — Yada et al.'s `ec-darkpattern`, built on Mathur
et al.'s 2019 corpus — reaches ~0.97 accuracy under cross-validation. Fine-tuned here and
pointed at live pages, the same approach scored roughly **2.5% precision**.

It had learned *commercial language = dark pattern*. On a curated corpus that correlation
holds. On a real storefront, where nearly every element is commercial, it collapses.

That failure defines the work:

> **With labels derived from element text alone, does adding geometry help a model
> generalise to a brand it has never seen?**

The narrower phrasing is deliberate. Ground truth comes from an LLM shown the text and
nothing else, so geometry can never be credited with information the text lacks — the
answer key does not contain it. What this dataset *can* test is generalisation: trained on
roughly 60 positive templates, does a model that also sees position and size hold up on an
unseen brand?

The planned comparison is text-only vs. geometry-only vs. fusion, on an identical
domain-grouped split.

---

## Pipeline

| Stage | Script | What it does |
|---|---|---|
| Capture | `capture.py` | Opens a real browser you drive by hand. On Enter, snapshots the current page: HTML, page dimensions, and every leaf text element with its bounding box. |
| Label | `label_elements.py` | Sends unique element texts to Gemini in batches, labeled strictly per `RUBRIC.md`. |
| Train (text) | `train_classifier.py` | DistilBERT fine-tune on `ec-darkpattern`. The Phase 3 baseline. |
| Train (fusion) | `train_fusion.py` | Text embedding + geometry features. **Incomplete.** |

Capture is interactive rather than a crawler on purpose: the densest dark patterns live in
cart and checkout flows that a plain GET request never reaches.

---

## Dataset

Collected from 25 e-commerce brands across three strata — aggressive marketplaces
(Temu, Wish, AliExpress, DHgate, Banggood, SHEIN, Alibaba), mass retail (Target, Best Buy,
Walmart, Macy's, Gap, Old Navy, Burlington), and deliberately low-pressure brands
(Apple, Muji, Patagonia, Nordstrom, Uniqlo).

Visible elements only (`geometry_width > 0 AND geometry_height > 0`):

| | rows | unique texts |
|---|---|---|
| label 0 | 44,947 | 14,500 |
| label 1 | 1,030 | 179 |

The low-pressure brands are the control group. Patagonia (485 texts), Zalando (645), Muji
(306) and H&M (384) produced **zero** positives — evidence that the labeler fires on
manipulative phrasing rather than on commerce, which is precisely what the Phase 3 model
failed to do.

**One caveat that shapes everything downstream:** the 179 positive texts collapse to roughly
60 templates once digits are normalised. `N added to cart N mins ago` alone accounts for 40
of them. Any train/test split at the text level therefore leaks, and the split must be
grouped by brand.

---

## Ground truth

Labels come from an LLM applying [`RUBRIC.md`](RUBRIC.md), which is the single source of
truth for what counts. It carries a version number and a changelog, and the labeling prompt
must match it.

This is not bureaucracy. Rubric v1.0 labeled *all* purchase counts as dark patterns; on real
data that made 92% of the positive class a single regex-solvable pattern, which would have
made the fusion comparison meaningless — text alone would score near-perfectly and geometry
could add nothing. Narrowing the rule in v1.1 invalidated every label produced under it, and
the corpus was re-collected from scratch.

**Rule:** change `RUBRIC.md`, then the prompt, then re-label — in that order.

---

## Setup

```bash
git clone https://github.com/MladenPesic/darkPatternRecognizer
cd darkPatternRecognizer

python -m venv venv
source venv/bin/activate          # Windows (Git Bash): source venv/Scripts/activate

pip install -r requirements.txt
playwright install chromium

cp .env.example .env              # then fill in your credentials
```

Capture drives a real Chrome over the DevTools protocol rather than a Playwright browser,
so `CHROME_PATH` and `CHROME_PROFILE_DIR` in `.env` must point at your local Chrome
executable and a scratch profile directory.

Run `schema.sql` against a fresh Postgres/Supabase instance to create the tables.

```bash
python capture.py                 # capture (Enter to snapshot, 'close' to quit)
python label_elements.py          # label unlabeled elements per RUBRIC.md
```

---

## Data model

`scans` — one row per captured page: URL, HTML pointer, status lifecycle
(`pending` → `completed` / `failed`), and the page dimensions measured at capture time.

`elements` — one row per leaf text element: type, text, bounding box, and the LLM label
with its reason.

Page dimensions are **measured at capture time**, not inferred from the largest element
bounding box. Every normalised geometry feature divides by them, so a noisy denominator
would directly weaken the hypothesis under test.

---

## Known gaps

- `train_fusion.py` is incomplete — it builds features and splits, but has no model head.
- The train/test split is not yet frozen. It must be grouped by brand, not by row or text.
- Metrics beyond accuracy (precision, recall, F1, PR-AUC) are not yet reported. Accuracy is
  meaningless here: predicting all-zero scores 97.8%.
- LLM labels are the ground truth and have not been independently validated at scale.
- Those labels were produced from element text alone, so they cannot reward geometry for
  information the text does not carry. The comparison measures generalisation to unseen
  brands, not extra signal. Settling that would need a test set labelled by a human looking
  at elements in place on the page.
- 59% of positives come from two domains (DHgate and Temu), so any result will be specific
  to this dataset rather than a general claim.

---

## Stack

Playwright · Google Gemini · Supabase / PostgreSQL · psycopg · PyTorch · Transformers

## References

- Mathur et al. (2019), *Dark Patterns at Scale* — the taxonomy this rubric follows.
- Yada et al. (2022), *Dark patterns in e-commerce: a dataset and its baseline evaluations*
  — source of `data/ec-darkpattern/`
  ([yamanalab/ec-darkpattern](https://github.com/yamanalab/ec-darkpattern)).
