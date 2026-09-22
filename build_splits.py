import os
import sys
import json
import re
import random
from urllib.parse import urlparse

import pandas as pd
import psycopg
from dotenv import load_dotenv

load_dotenv()

CACHE_PATH = 'data/build_splits_data.csv'   # delete this file to re-query the database
SPLITS_PATH = 'splits.json'

N_SEEDS = 200
N_TEST_BRANDS = 5
N_SPLITS = 5
N_FOLDS = 5
MIN_TEST_TEMPLATES = 12
MIN_TEST_ZERO_BRANDS = 2
MIN_TRAIN_TEMPLATES = 45

query = """
    SELECT
        scans.url,
        elements.scan_id,
        elements.llm_label,
        elements.element_text
    FROM scans
    JOIN elements
        ON scans.id = elements.scan_id
    WHERE
        elements.llm_label IS NOT NULL
        AND elements.geometry_width > 0
        AND elements.geometry_height > 0
"""

if not os.path.exists(CACHE_PATH):
    with psycopg.connect(os.getenv('DATABASE_URL'), connect_timeout=10) as conn:
        with conn.cursor() as cursor:
            cursor.execute(query)
            data = cursor.fetchall()
    df = pd.DataFrame.from_records(data, columns=['url', 'scan_id', 'llm_label', 'element_text'])
    df.to_csv(CACHE_PATH, index=False)

df = pd.read_csv(CACHE_PATH, dtype={'element_text': str, 'url': str}, keep_default_na=False)
df['host'] = df['url'].apply(lambda x: urlparse(str(x)).hostname)


def normalize_template(text):
    return re.sub(r'\d+', 'N', text.lower())


df['template'] = df['element_text'].apply(normalize_template)
with open('brands.json', 'r', encoding='utf8') as f:
    brands = json.load(f)

domain_to_brand = {}
for item in brands['mappings']:
    for domain in item['domains']:
        domain_to_brand[domain] = item['brand']

df['brand'] = df['host'].map(domain_to_brand)
unknown = df.loc[df['brand'].isna(), 'host'].unique()
if len(unknown):
    raise ValueError(f"hosts missing from brands.json: {sorted(unknown)}")

labels = set(df['llm_label'].unique())
if not labels <= {0, 1}:
    raise ValueError(f"unexpected llm_label values: {sorted(labels)}")

grouped = df.groupby('brand').agg(
    positive_templates=('template', lambda x: set(x[df.loc[x.index, 'llm_label'] == 1])),
    positive_rows=('llm_label', 'sum'),
    total_rows=('brand', 'size'),
    scan_ids=('scan_id', lambda x: set(x))
)

ALL_BRANDS = sorted(grouped.index)
ZERO_POSITIVE_BRANDS = set(grouped.loc[grouped['positive_templates'].apply(len) == 0].index)


def union_templates(brand_list, grouped):
    return set().union(*grouped.loc[brand_list, 'positive_templates'])


# --- the draw ---------------------------------------------------------------

results = []
for seed in range(N_SEEDS):
    brand_names = list(ALL_BRANDS)              # fresh copy: shuffle works in place
    random.Random(seed).shuffle(brand_names)
    test = brand_names[:N_TEST_BRANDS]
    train = brand_names[N_TEST_BRANDS:]
    results.append({
        'seed': seed,
        'rule1': len(union_templates(test, grouped)) >= MIN_TEST_TEMPLATES,
        'rule2': len(set(test) & ZERO_POSITIVE_BRANDS) >= MIN_TEST_ZERO_BRANDS,
        'rule3': len(union_templates(train, grouped)) >= MIN_TRAIN_TEMPLATES,
        'train': train,
        'test': test,
    })

results_df = pd.DataFrame(results)
results_df['rules_passed'] = results_df[['rule1', 'rule2', 'rule3']].all(axis=1)
num_passed = int(results_df['rules_passed'].sum())
print(f"{num_passed} of {N_SEEDS} seeds passed all rules")
print(results_df[['rule1', 'rule2', 'rule3']].mean().to_string())
if num_passed < N_SPLITS:
    raise RuntimeError(f"only {num_passed} seeds passed all rules; need {N_SPLITS}")

first_accepted = results_df.loc[results_df['rules_passed']].head(N_SPLITS)


# --- folds ------------------------------------------------------------------

def make_folds(train_brands, grouped, n_folds=N_FOLDS):
    # Biggest positive brands first. Brand name breaks ties, so the order never changes.
    ordered = sorted(train_brands, key=lambda b: (-grouped.loc[b, 'positive_rows'], b))

    folds = {str(k): [] for k in range(1, n_folds + 1)}
    for i, brand in enumerate(ordered):
        fold_number = i % n_folds + 1          # i=0→1, 1→2, 2→3, 3→4, 4→5, 5→1, 6→2 ...
        folds[str(fold_number)].append(brand)

    for k, members in folds.items():
        if grouped.loc[members, 'positive_rows'].sum() == 0:
            raise ValueError(f"fold {k} has no positive rows: {members}")
    return folds


# --- step A: build and write splits.json ------------------------------------

def summarise(brand_list, grouped):
    part = grouped.loc[brand_list]
    return {
        'brands': len(brand_list),
        'rows': int(part['total_rows'].sum()),
        'positive_rows': int(part['positive_rows'].sum()),
        'positive_templates': len(union_templates(brand_list, grouped)),
        'zero_positive_brands': len(set(brand_list) & ZERO_POSITIVE_BRANDS),
    }


splits = []
for _, row in first_accepted.iterrows():
    test, train = sorted(row['test']), sorted(row['train'])
    shared = union_templates(test, grouped) & union_templates(train, grouped)
    splits.append({
        'seed': int(row['seed']),
        'canonical': len(splits) == 0,
        'test': test,
        'train': train,
        'folds': make_folds(train, grouped),
        'counts': {
            'test': summarise(test, grouped),
            'train': summarise(train, grouped),
        },
        'reported': {'test_templates_also_in_train': len(shared)},
    })

output = {
    'brands_source': 'brands.json',
    'seeds_scanned': N_SEEDS,
    'seeds_accepted': num_passed,
    'selection_rule': f'first {N_SPLITS} accepted seeds, ascending',
    'selected_seeds': [s['seed'] for s in splits],
    'canonical_seed': splits[0]['seed'],
    'rules': {
        'test_brands': N_TEST_BRANDS,
        'min_test_positive_templates': MIN_TEST_TEMPLATES,
        'min_test_zero_positive_brands': MIN_TEST_ZERO_BRANDS,
        'min_train_positive_templates': MIN_TRAIN_TEMPLATES,
    },
    'splits': splits,
}

if os.path.exists(SPLITS_PATH) and '--force' not in sys.argv:
    with open(SPLITS_PATH, encoding='utf8') as f:
        existing = json.load(f)
    if existing != output:
        print(f"WARNING: the data no longer reproduces {SPLITS_PATH}. "
              f"The committed file stays authoritative; its counts may be stale.")
    print(f"{SPLITS_PATH} is frozen, not overwriting (pass --force to regenerate)")
else:
    with open(SPLITS_PATH, 'w', encoding='utf8') as f:
        json.dump(output, f, indent=2)
        f.write('\n')
    print(f"wrote {SPLITS_PATH}")


# --- step B: verify the file on disk ----------------------------------------

def verify_splits(path, grouped):
    with open(path, encoding='utf8') as f:
        saved = json.load(f)
    rules = saved['rules']
    all_brands = set(grouped.index)

    for split in saved['splits']:
        seed = split['seed']
        test, train = set(split['test']), set(split['train'])

        if test & train:
            raise ValueError(f"seed {seed}: brands in both test and train: {sorted(test & train)}")
        if test | train != all_brands:
            raise ValueError(f"seed {seed}: missing brands {sorted(all_brands - (test | train))}, "
                             f"unknown brands {sorted((test | train) - all_brands)}")

        fold_members = [b for members in split['folds'].values() for b in members]
        if len(fold_members) != len(set(fold_members)):
            raise ValueError(f"seed {seed}: a brand appears in more than one fold")
        if set(fold_members) != train:
            raise ValueError(f"seed {seed}: folds do not cover exactly the train brands")

        # Brand grouping should make this impossible; checked because A3 requires it.
        test_scans = set().union(*grouped.loc[sorted(test), 'scan_ids'])
        train_scans = set().union(*grouped.loc[sorted(train), 'scan_ids'])
        if test_scans & train_scans:
            raise ValueError(f"seed {seed}: scan_ids in both test and train: "
                             f"{sorted(test_scans & train_scans)}")

        test_templates = union_templates(sorted(test), grouped)
        if len(test_templates) < rules['min_test_positive_templates']:
            raise ValueError(f"seed {seed}: test has {len(test_templates)} positive templates")
        if len(test & ZERO_POSITIVE_BRANDS) < rules['min_test_zero_positive_brands']:
            raise ValueError(f"seed {seed}: test has too few zero-positive brands")
        if len(union_templates(sorted(train), grouped)) < rules['min_train_positive_templates']:
            raise ValueError(f"seed {seed}: train has too few positive templates")

        print(f"seed {seed:>3}: test {sorted(test)} | "
              f"{len(test_templates)} test templates, "
              f"{split['reported']['test_templates_also_in_train']} also in train")

    print("all split checks passed")


verify_splits(SPLITS_PATH, grouped)