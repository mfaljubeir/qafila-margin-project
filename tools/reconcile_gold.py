"""Independently reconcile source data against Iceberg Gold output."""

import argparse
import csv
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta, date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from zoneinfo import ZoneInfo

from pyiceberg.catalog.sql import SqlCatalog


def money(value):
    return Decimal(str(value)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def parse_cost(value):
    if value is None:
        return None
    text = str(value).strip().replace("٫", ".").replace(",", ".")
    text = text.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
    try:
        return money(text)
    except Exception:
        return None


def read_source(data_dir):
    with sqlite3.connect(data_dir / "qafila_oltp.sqlite") as con:
        con.row_factory = sqlite3.Row
        products = {
            r["product_id"]: dict(r)
            for r in con.execute("select * from products")
        }
        stores = {
            r["store_id"]: dict(r)
            for r in con.execute("select * from stores")
        }
        orders = {
            r["order_id"]: dict(r)
            for r in con.execute("select * from orders")
        }
        items = [dict(r) for r in con.execute("select * from order_items")]

    known_skus = {str(p["sku"]).strip() for p in products.values()}
    candidates = {}

    for path in sorted((data_dir / "suppliers").glob("prices_*.csv")):
        with path.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                sku = str(row.get("sku") or "").strip()
                cost = parse_cost(row.get("unit_cost") or row.get("cost_sar"))
                if sku not in known_skus or cost is None or cost <= 0:
                    continue
                effective = date.fromisoformat(row["valid_from"].strip())
                key = (sku, effective)
                previous = candidates.get(key)
                if previous is None or path.name > previous[0]:
                    candidates[key] = (path.name, cost)

    history = defaultdict(list)
    for (sku, effective), (_, cost) in sorted(candidates.items()):
        versions = history[sku]
        if not versions or versions[-1][1] != cost:
            versions.append((effective, cost))

    return products, stores, orders, items, history


def calculate(data_dir):
    products, stores, orders, items, history = read_source(data_dir)
    result = defaultdict(lambda: {
        "lines": 0, "revenue_sar": Decimal(0),
        "costed_revenue_sar": Decimal(0),
        "cost_sar": Decimal(0), "uncosted_lines": 0
    })

    for item in items:
        order = orders[item["order_id"]]
        if order["status"] != "delivered" or item["quantity"] <= 0:
            continue

        raw_time = datetime.fromisoformat(order["created_at"].replace("Z", "+00:00"))
        local_time = raw_time + timedelta(hours=3)
        order_date = local_time.date()
        if order_date < date(2026, 8, 31):
            continue

        product = products[item["product_id"]]
        sku = str(product["sku"]).strip()
        city = stores[order["store_id"]]["city"]
        category = product["category"]
        week = order_date.isocalendar().week
        key = (week, city, category)

        revenue = money(
            Decimal(str(item["quantity"])) * Decimal(str(item["unit_price"]))
            - Decimal(str(item["discount"]))
        )
        record = result[key]
        record["lines"] += 1
        record["revenue_sar"] += revenue

        effective_cost = None
        for start, cost in history.get(sku, []):
            if start <= order_date:
                effective_cost = cost
            else:
                break

        if effective_cost is None:
            record["uncosted_lines"] += 1
        else:
            record["costed_revenue_sar"] += revenue
            record["cost_sar"] += Decimal(item["quantity"]) * effective_cost

    for row in result.values():
        for field in ("revenue_sar", "costed_revenue_sar", "cost_sar"):
            row[field] = money(row[field])
        row["margin_sar"] = money(
            row["costed_revenue_sar"] - row["cost_sar"]
        )

    return result


def compare(data_dir, warehouse):
    expected = calculate(data_dir)
    catalog = SqlCatalog(
        "qafila",
        uri=f"sqlite:///{(warehouse / 'catalog.db').resolve().as_posix()}",
        warehouse=warehouse.resolve().as_posix(),
    )
    actual_rows = catalog.load_table(
        ("gold", "weekly_margin")
    ).scan().to_arrow().to_pylist()

    actual = {
        (int(r["iso_week"]), r["city"], r["category"]): r
        for r in actual_rows
    }

    if len(actual) != len(actual_rows):
        raise SystemExit(
            "FAIL: duplicate reporting groups found in Gold."
        )

    fields = (
        "lines", "revenue_sar", "costed_revenue_sar",
        "cost_sar", "margin_sar", "uncosted_lines"
    )
    mismatches = []

    for key in sorted(set(expected) | set(actual)):
        e, a = expected.get(key), actual.get(key)
        if e is None or a is None:
            mismatches.append((key, "missing group", e, a))
            continue
        for field in fields:
            left = e[field]
            right = a[field]
            if field not in ("lines", "uncosted_lines"):
                right = money(right)
            if left != right:
                mismatches.append((key, field, left, right))

    print(f"Expected groups: {len(expected)}")
    print(f"Actual Gold groups: {len(actual_rows)}")
    print(f"Mismatches: {len(mismatches)}")
    for mismatch in mismatches[:20]:
        print("MISMATCH:", mismatch)
    if mismatches:
        raise SystemExit(1)
    print("PASS: all Gold groups and financial metrics reconcile.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--warehouse", type=Path, default=Path("warehouse"))
    args = parser.parse_args()
    compare(args.data_dir, args.warehouse)
