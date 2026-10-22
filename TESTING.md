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

The pipeline was also validated with seed 11, independently
of the default generated dataset.

Generate the alternate dataset:

```bash
uv run python tools/make_data.py --seed 11 --out data_seed11
```

The alternate data must be processed using a separate input
path and Iceberg warehouse/catalog configuration. Do not
run the standard pipeline against its default warehouse
without first isolating the test environment.

Observed results from the earlier seed-11 validation:
- The pipeline completed successfully.
- An unchanged re-run did not introduce new snapshots.
- A supplier cost correction was processed.
- A +SAR 1.00 cost change for an eligible SKU resulted
  in a SAR 59.00 decrease in gross margin.
- The previous Iceberg snapshot remained readable.

These observations are recorded from the earlier test.
They are not a claim that the commands above alone
execute the full isolated seed-11 pipeline.

## 7. Additional dbt quality tests

Two additional singular dbt tests were implemented to
strengthen validation of the Gold reporting model.

### Weekly margin grain uniqueness

Test: `dbt/tests/assert_weekly_margin_unique_grain.sql`

Checks that each combination of `iso_week`, `city`, and
`category` appears only once in `weekly_margin`.

Observed result: **PASS**.

### Source-to-Gold reconciliation

Test: `dbt/tests/assert_weekly_margin_source_reconciliation.sql`

Independently aggregates eligible source order items and
compares their line counts and rounded revenue against
`weekly_margin` at the reporting grain.

The test detects missing or extra reporting groups,
line-count mismatches, and revenue mismatches.

Observed result: **PASS**.

### Full pipeline verification

After adding both tests, the pipeline was executed again:

```bash
uv run python run.py
uv run python tools/check.py
```

Observed results:
- dbt: **5 models and 12 tests passed (17/17)**.
- Official checker: **22/22 checks passed**.
- `silver.product_cost_history`: unchanged.
- `gold.weekly_margin`: unchanged.
- `quality.price_quarantine`: unchanged.
- No new Iceberg snapshots were created during the
  unchanged re-run.

These results were observed on the default generated dataset.
The additional tests have not yet been separately validated
against the official correction dataset.

## Scope of evidence

These are observed results from the validation runs.
They do not guarantee performance on unseen grader data.
