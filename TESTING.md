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

### Revalidation after supplier correction

The official supplier correction file was generated using:

```bash
uv run python tools/make_data.py --add-correction
```

The pipeline and checker were then executed:

```bash
uv run python run.py
uv run python tools/check.py
```

Observed results:
- dbt: **5 models and 12 tests passed (17/17)**.
- Official checker: **22/22 checks passed**.
- Both additional Gold-model tests: **PASS**.
- `silver.product_cost_history`: **637 rows**.
- `gold.weekly_margin`: **165 rows**.
- `quality.price_quarantine`: **7 rows**.
- Silver and Gold Iceberg tables were updated.

This confirms the additional tests also passed on the
supplier-correction dataset.


### Idempotency after supplier correction

The pipeline and official checker were run again without
changing the corrected input data.

Observed results:
- dbt: **17/17 passed**, including all 12 data tests.
- Official checker: **22/22 passed**.
- `silver.product_cost_history`: **Unchanged**.
- `gold.weekly_margin`: **Unchanged**.
- `quality.price_quarantine`: **Unchanged**.
- Gold Iceberg snapshot count remained at **3**.

This confirms that an unchanged re-run after the supplier
correction did not rewrite the three Iceberg tables.

## 8. Independent Gold reconciliation

An independent Python validator was implemented in
`tools/reconcile_gold.py`.

Unlike the dbt tests, this validator reads the original
SQLite and supplier CSV inputs directly, reconstructs
effective supplier costs, calculates the Gold reporting
metrics, and compares them with the published Iceberg table.

Run:

```bash
uv run python tools/reconcile_gold.py
```

### Supplier-correction dataset

Observed results:
- Expected reporting groups: **165**.
- Actual Iceberg Gold groups: **165**.
- Financial metric mismatches: **0**.
- Duplicate reporting groups: **none detected**.
- Result: **PASS**.

The validator compares line counts, total revenue,
costed revenue, total cost, gross margin, and uncosted
line counts at each reporting grain.

### Negative test

A temporary test injected a SAR 1.00 discrepancy into
the independently calculated revenue of one group,
without modifying the pipeline or Iceberg data.

Observed results:
- Detected mismatches: **1**.
- Field: `revenue_sar`.
- Expected failure exit code: **1**.

This confirms the validator detects an intentional
financial discrepancy instead of silently passing.

## Scope of evidence

These are observed results from the validation runs.
They do not guarantee performance on unseen grader data.

### Baseline dataset independent reconciliation

The default dataset was generated in a separate directory,
then processed using an isolated Iceberg warehouse.

All three commands completed with exit code 0:

```bash
uv run python tools/make_data.py --out /content/qafila-base-validation-data
uv run python run.py --data-dir /content/qafila-base-validation-data --warehouse /content/qafila-base-validation-warehouse
uv run python tools/reconcile_gold.py --data-dir /content/qafila-base-validation-data --warehouse /content/qafila-base-validation-warehouse
```

Result: **PASS**. The baseline validation did not modify
the supplier-correction warehouse.

## 9. SCD2 and Gold financial consistency tests

Two additional dbt singular tests were implemented.

### SCD2 interval integrity

File: `dbt/tests/assert_cost_history_intervals.sql`

Validates that each cost version has valid date boundaries,
that its end date matches the next version's start date,
and that only the final version for each SKU is current.

Observed result: **PASS**.

### Gold financial consistency

File: `dbt/tests/assert_weekly_margin_consistency.sql`

Validates non-null financial metrics, valid uncosted-line
counts, and the relationship:

`margin_sar = costed_revenue_sar - cost_sar`

with a SAR 0.01 tolerance.

Observed result: **PASS**.

### Full verification after both additions

Observed results:
- dbt build: **5 models and 14 tests passed (19/19)**.
- dbt warnings: **0**.
- dbt errors: **0**.
- Full pipeline: **exit code 0**.
- Official checker: **exit code 0**.
- Independent Gold reconciliation: **exit code 0**.

These results apply to the tested dataset. Earlier sections
preserve the historical results from previous validation runs.
