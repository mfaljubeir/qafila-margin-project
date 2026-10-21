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
|---|---|---|---|
| Invalid supplier costs | Supplier CSVs | 4 | Quarantined with `invalid_cost` |
| Unknown product SKUs | Supplier CSVs | 3 | Quarantined with `unknown_sku` |
| Supplier column name changes | Week 39 CSV | 160 | Read `unit_cost` and `cost_sar` into one normalized cost field |
| Different cost number formats | Supplier prices | Varies | Normalized commas and Arabic decimal digits before conversion |

## Tests

| Test | On | What it protects against |
|---|---|---|
| Not-null checks | Cost history and weekly margin | Missing required values |
| Accepted quarantine reasons | Price quarantine | Unexpected rejection reasons |
| No duplicate SKU/date versions | Cost history | Duplicate SCD2 versions |
| No unchanged consecutive costs | Cost history | Unnecessary SCD2 versions |

All 10 dbt tests passed. The provided checker passed 22/22 checks.

## Re-runs and the correction

Running the pipeline twice with unchanged data left all three Iceberg tables unchanged.

A test correction increased one supplier cost by SAR 1. The original gold snapshot was `5576987117744296487`, with total margin of SAR 801,016.88. After the correction, snapshot `8540595361163887495` had total margin of SAR 800,967.88, a decrease of SAR 49. The earlier snapshot remained readable.

The temporary correction file was removed after testing.

I also tested with seed 11 using a separate data directory and warehouse.
The checker passed 22/22 checks, and all 10 dbt tests passed.
Running the same pipeline again left all three Iceberg tables unchanged.

For seed 11, I tested a supplier correction that increased one cost
from SAR 9.97 to SAR 10.97. The original gold snapshot
`8713210089906842885` had total margin of SAR 748,231.25.
After correction, snapshot `4882154044542120267` had total
margin of SAR 748,172.25, a decrease of SAR 59.
The original snapshot remained readable.
The temporary correction file was removed.

## What I'd do next

With 100× more data, full-table comparisons and overwrites would become expensive. I would look into incremental processing. Daily supplier files would also need more frequent validation and checks for overlapping cost periods.

## AI assistance

I used ChatGPT to help understand the requirements, work through the Python and SQL implementation, and troubleshoot dbt and Iceberg errors. I ran the pipeline and tests in Colab and checked the results.
