"""Build the SQLite database from the project's six generated CSV files."""

from __future__ import annotations

import argparse
import csv
import sqlite3
from pathlib import Path


HERE = Path(__file__).resolve().parent
PROJECT_DIR = HERE.parent
DEFAULT_CSV_DIR = PROJECT_DIR / "csv_version" / "generated_csv_260607"
DEFAULT_DB_PATH = HERE / "shopping_bus.db"
SCHEMA_PATH = HERE / "schema.sql"

TABLES = (
    ("stops", ("stop_id", "stop_name", "lat", "lon")),
    (
        "pois",
        (
            "poi_id",
            "poi_name",
            "poi_type",
            "rating",
            "lat",
            "lon",
            "osm_type",
            "osm_id",
            "address",
            "source",
        ),
    ),
    ("poi_items", ("item_id", "item_name")),
    (
        "route_edges",
        ("edge_id", "route_name", "from_stop_id", "to_stop_id", "travel_time_min"),
    ),
    ("stop_poi_mapping", ("stop_id", "poi_id", "walking_time_min")),
    ("poi_item_mapping", ("poi_id", "item_id", "price", "service_time_min")),
)


def read_rows(csv_path: Path, columns: tuple[str, ...]) -> list[tuple[object, ...]]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames != list(columns):
            raise ValueError(
                f"{csv_path.name} 欄位不符：預期 {list(columns)}，實際 {reader.fieldnames}"
            )
        return [tuple(row[column].strip() or None for column in columns) for row in reader]


def build_database(csv_dir: Path, db_path: Path) -> dict[str, int]:
    if not csv_dir.is_dir():
        raise FileNotFoundError(f"找不到 CSV 資料夾：{csv_dir}")

    db_path.parent.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    with sqlite3.connect(db_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

        # Rebuilding in this order keeps foreign-key relationships valid.
        for table, _ in reversed(TABLES):
            connection.execute(f"DELETE FROM {table}")

        for table, columns in TABLES:
            rows = read_rows(csv_dir / f"{table}.csv", columns)
            placeholders = ", ".join("?" for _ in columns)
            column_names = ", ".join(columns)
            connection.executemany(
                f"INSERT INTO {table} ({column_names}) VALUES ({placeholders})", rows
            )
            counts[table] = len(rows)

        violations = connection.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise RuntimeError(f"外鍵檢查失敗：{violations}")

    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="將專案 CSV 匯入 SQLite")
    parser.add_argument("--csv-dir", type=Path, default=DEFAULT_CSV_DIR)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    args = parser.parse_args()

    counts = build_database(args.csv_dir.resolve(), args.db.resolve())
    print(f"資料庫已建立：{args.db.resolve()}")
    for table, count in counts.items():
        print(f"  {table}: {count} 筆")


if __name__ == "__main__":
    main()
