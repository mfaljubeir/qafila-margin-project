# Qafila gross margin

Submitted by: Mishael Fahad AlJubeir — academy: @SDAIAAcademy

The task, rules and grading are in [BRIEF.md](BRIEF.md).

```bash
uv sync
uv run python tools/make_data.py          # data/
uv run python run.py                      # data/ -> warehouse/ (DuckDB + Iceberg)
uv run python tools/check.py              # contract self-check
```

## Design

SQLite and supplier CSVs → DuckDB raw tables → dbt staging views → silver, gold and quality tables → PyIceberg catalog.

| Model | Layer | Grain (one row per ...) | Materialization |
|---|---|---|---|
| `stg_supplier_prices` | staging | supplier price row | view |
| `stg_orders` | staging | eligible delivered order | view |
| `product_cost_history` | silver | SKU and cost version | table |
| `weekly_margin` | gold | ISO week, city and category | table |
| `price_quarantine` | quality | rejected supplier price row | table |

**How the SCD2 history is built:** Supplier prices are sorted by SKU and effective date. Missing weeks keep the previous cost, and unchanged costs do not create a new version. When the same SKU and date appear in multiple files, the last filename wins, so a correction file replaces the original quote.

**How each order line finds its cost:** Each eligible order line is matched to the cost version active on its Riyadh order date. Lines without a matching cost still count toward revenue and line totals, but are excluded from cost and margin calculations.

## Data problems I found

| Problem | Where | Rows affected | What I did |
|---|---|---:|---|
| Invalid supplier costs | Supplier CSVs | 4 | Quarantined with `invalid_cost` |
| Unknown product SKUs | Supplier CSVs | 3 | Quarantined with `unknown_sku` |
| Supplier column name changes | `prices_2026-W39.csv` | 160 | Read `cost_sar` as the cost field alongside `unit_cost` from earlier files |
| Decimal commas | `prices_2026-W38.csv` | 126 | Normalized decimal commas before conversion |
| Arabic digits or decimal mark | `prices_2026-W38.csv` | 34 | Normalized Arabic digits and decimal mark before conversion |

## Tests

| Test | On | What it protects against |
|---|---|---|
| Not-null checks | Cost history and weekly margin | Missing required values |
| Accepted quarantine reasons | Price quarantine | Unexpected rejection reasons |
| No duplicate SKU/date versions | Cost history | Duplicate SCD2 versions |
| No unchanged consecutive costs | Cost history | Unnecessary SCD2 versions |

All 10 dbt tests passed. The provided checker passed 22/22 checks.

## Re-runs and the correction

Running the pipeline twice with unchanged inputs did not create new Iceberg snapshots.

I tested the official correction file, `prices_2026-W39_fix.csv`, containing nine supplier price corrections. The pipeline updated the affected cost history and weekly margin tables while preserving previous Iceberg snapshots.

**Correction validation:**

- Gross margin before correction: SAR 801,016.88
- Gross margin after correction: SAR 803,515.80
- Gross margin change: +SAR 2,498.92
- Independently calculated expected change: +SAR 2,498.92
- Difference between expected and actual change: SAR 0.00
- Revenue, costed revenue, and uncosted line counts remained unchanged.

The previous Iceberg snapshot remained readable after the correction, demonstrating time travel.

I also tested the pipeline with a second generated seed, including re-runs and correction handling.

## Validation Evidence

For detailed testing steps and results, see [TESTING.md](TESTING.md).

The project was validated using a fresh clone, unchanged re-runs,
the official W39 correction file, and a second generated seed.

| Validation | Observed result |
|---|---|
| Fresh pipeline execution | Successful |
| dbt build | 5 models and 10 tests passed (15/15) |
| Provided checker | 22/22 checks passed |
| Initial Iceberg output | 633 cost history rows, 165 margin rows, 7 quarantined rows |
| Unchanged re-run | Tables unchanged; no new Iceberg snapshots |
| Official W39 correction | 9 corrected supplier prices processed |
| Corrected Iceberg output | 637 cost history rows, 165 margin rows, 7 quarantined rows |
| Correction margin impact | +SAR 2,498.92 |
| Independent correction calculation | +SAR 2,498.92; difference SAR 0.00 |
| Iceberg time travel | Previous gold snapshot remained readable |
| Second generated seed | Re-runs and correction handling tested |

### Independent correction reconciliation

| Metric | Before correction | After correction | Change |
|---|---:|---:|---:|
| Margin rows | 165 | 165 | 0 |
| Revenue (SAR) | 3,504,002.19 | 3,504,002.19 | 0.00 |
| Costed revenue (SAR) | 2,455,216.86 | 2,455,216.86 | 0.00 |
| Cost (SAR) | 1,654,199.98 | 1,651,701.06 | -2,498.92 |
| Gross margin (SAR) | 801,016.88 | 803,515.80 | +2,498.92 |
| Uncosted lines | 20,626 | 20,626 | 0 |

The margin change was independently calculated from eligible
delivered order lines using Riyadh-local dates and effective
supplier costs. The expected and actual changes matched exactly.

These results describe the tested datasets and do not claim
coverage of unseen grader cases.

## What I'd do next

With 100× more data, full-table comparisons and overwrites would become expensive. I would look into incremental processing. Daily supplier files would also need more frequent validation and checks for overlapping cost periods.

## AI assistance

I used ChatGPT to help understand the requirements, troubleshoot dbt and Iceberg errors 
