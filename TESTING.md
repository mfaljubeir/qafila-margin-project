# Testing and Validation

This document records the validation performed for the
Qafila Gross Margin data engineering project.

## 1. Fresh run

From a fresh clone of the repository:

```bash
uv sync
uv run python tools/make_data.py
uv run python run.py
uv run python tools/check.py
```

Observed results:
- dbt: 5 models and 10 tests passed (15/15).
- Provided checker: 22/22 checks passed.
- Iceberg tables created:
  - silver.product_cost_history: 633 rows
  - gold.weekly_margin: 165 rows
  - quality.price_quarantine: 7 rows

## 2. Idempotency

Run the pipeline again without changing the inputs:

```bash
uv run python run.py
uv run python tools/check.py
```

Observed result:
- All three Iceberg tables remained unchanged.
- No new Iceberg snapshots were created.
- The checker passed 22/22 checks.

## 3. Official supplier correction

Apply the official correction:

```bash
uv run python tools/make_data.py --add-correction
uv run python run.py
uv run python tools/check.py
```

Observed results:
- Nine corrected supplier price rows were processed.
- dbt: 15/15 passed.
- Checker: 22/22 passed.
- Cost history increased from 633 to 637 rows.
- Weekly margin remained at 165 rows.
- Quarantine remained at 7 rows.

## 4. Independent correction reconciliation

The pre-correction and post-correction Iceberg outputs
were compared using a separate baseline warehouse.
The margin impact was independently recalculated from
eligible delivered order lines, Riyadh-local order dates,
and the effective supplier costs.

| Metric | Before | After | Change |
|---|---:|---:|---:|
| Weekly margin rows | 165 | 165 | 0 |
| Revenue (SAR) | 3,504,002.19 | 3,504,002.19 | 0.00 |
| Costed revenue (SAR) | 2,455,216.86 | 2,455,216.86 | 0.00 |
| Cost (SAR) | 1,654,199.98 | 1,651,701.06 | -2,498.92 |
| Gross margin (SAR) | 801,016.88 | 803,515.80 | +2,498.92 |
| Uncosted lines | 20,626 | 20,626 | 0 |

Expected margin change: +SAR 2,498.92.
Actual margin change: +SAR 2,498.92.
Difference: SAR 0.00.

The nine affected SKUs were reconciled against their
eligible order quantities and old/new effective costs.

## 5. Iceberg time travel

The following snapshots were observed for
gold.weekly_margin:

- Before correction: 8059199374499567252
- After correction: 3609388587380340945

The earlier snapshot remained readable after the
correction and retained the pre-correction margin.

## 6. Second generated seed

The pipeline was also tested using a second generated
seed, including unchanged re-runs and a supplier
cost correction.

This was a separate validation experiment, not part
of the primary baseline and official correction results.

## Scope of evidence

These are observed results from the validation runs.
They do not guarantee performance on unseen grader data.
