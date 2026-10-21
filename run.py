"""Qafila gross margin pipeline: raw files -> DuckDB -> dbt -> Iceberg.

    uv run python run.py --data-dir data --warehouse warehouse

Must work on an empty warehouse folder, and must be safe to run again on the same one.
The grader runs it on a dataset you haven't seen, so never hard-code file names, row counts or SKUs.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

import duckdb
from pyiceberg.catalog.sql import SqlCatalog

DBT_DIR = Path(__file__).resolve().parent / "dbt"


def get_catalog(warehouse: Path) -> SqlCatalog:
    """The Iceberg catalog the grader reads. Don't change the name, the URI or the warehouse."""
    warehouse.mkdir(parents=True, exist_ok=True)
    return SqlCatalog("qafila", uri=f"sqlite:///{(warehouse / 'catalog.db').as_posix()}", warehouse=warehouse.resolve().as_posix())


def ingest(data_dir: Path, db: Path) -> None:
    """Step 1: land the sources in DuckDB, schema `raw`, exactly as they arrive.

    - From data_dir/qafila_oltp.sqlite: orders, order_items, products, stores.
    - Every data_dir/suppliers/prices_*.csv, keeping the file name of each row.

    Running this twice must not duplicate anything.
    """
    with duckdb.connect(str(db)) as con:  # closes the file before dbt opens it
        con.sql("CREATE SCHEMA IF NOT EXISTS raw")

        sqlite_file = data_dir / "qafila_oltp.sqlite"

        for table in ("orders", "order_items", "products", "stores"):
            con.execute(f"""
                CREATE OR REPLACE TABLE raw.{table} AS
                SELECT * FROM sqlite_scan('{sqlite_file}', '{table}')
            """)

        supplier_files = sorted((data_dir / "suppliers").glob("prices_*.csv"))

        if not supplier_files:
            raise FileNotFoundError("No supplier price files found")

        con.execute("""
            CREATE OR REPLACE TABLE raw.supplier_prices AS
            SELECT *
            FROM read_csv_auto(
                ?,
                union_by_name = true,
                filename = true
            )
        """, [[str(path) for path in supplier_files]])



def transform(db: Path) -> None:
    """Steps 2-4: build and test the dbt project in dbt/ against the DuckDB file.

    dbt runs in its own process: in this one it would keep the DuckDB file open and block publish().
    """
    env = {**os.environ, "QAFILA_DUCKDB": str(db.resolve())}
    cmd = [sys.executable, "-c", "from dbt.cli.main import cli; cli()",
           "build", "--project-dir", str(DBT_DIR), "--profiles-dir", str(DBT_DIR)]
    if subprocess.run(cmd, env=env).returncode != 0:
        raise SystemExit("dbt build failed")


def publish(db: Path, warehouse: Path) -> None:
    """Publish dbt results to Iceberg while preserving table history."""
    import pyarrow as pa

    catalog = get_catalog(warehouse)

    models = [
        ("silver", "product_cost_history"),
        ("gold", "weekly_margin"),
        ("quality", "price_quarantine"),
    ]

    with duckdb.connect(str(db), read_only=True) as con:
        for namespace, name in models:
            identifier = (namespace, name)

            # Read the dbt model from DuckDB.
            data = con.execute(
                f'SELECT * FROM "{namespace}"."{name}"'
            ).fetch_arrow_table()

            # Create the namespace if this is the first run.
            if namespace not in {
                ns[0] for ns in catalog.list_namespaces()
            }:
                catalog.create_namespace(namespace)

            if not catalog.table_exists(identifier):
                # First run: create the Iceberg table.
                catalog.create_table(
                    identifier=identifier,
                    schema=data.schema,
                )
                table = catalog.load_table(identifier)
                table.append(data)
                print(f"Created {namespace}.{name}")
            else:
                table = catalog.load_table(identifier)

                # Compare rows without relying on their order.
                old_data = table.scan().to_arrow()

                def sorted_rows(arrow_table):
                    return sorted(
                        repr(row)
                        for row in arrow_table.to_pylist()
                    )

                if sorted_rows(old_data) == sorted_rows(data):
                    print(f"Unchanged {namespace}.{name}")
                else:
                    # Overwrite creates a new snapshot.
                    table.overwrite(data)
                    print(f"Updated {namespace}.{name}")

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data-dir", type=Path, default=Path("data"))
    ap.add_argument("--warehouse", type=Path, default=Path("warehouse"))
    args = ap.parse_args()

    args.warehouse.mkdir(parents=True, exist_ok=True)
    db = args.warehouse / "qafila.duckdb"
    ingest(args.data_dir, db)
    transform(db)
    publish(db, args.warehouse)
    print(f"done: {args.warehouse.resolve()}")


if __name__ == "__main__":
    main()
