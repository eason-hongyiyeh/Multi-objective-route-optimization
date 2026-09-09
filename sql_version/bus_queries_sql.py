"""SQL-backed query API for the SQLite web version.

The route-planning algorithms are shared with the CSV version, while every data
read in this module is redirected to shopping_bus.db.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path


SQL_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SQL_DIR.parent
DATABASE_PATH = SQL_DIR / "shopping_bus.db"

if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from csv_version import bus_queries as _csv_queries  # noqa: E402


TABLE_COLUMNS = {
    "stops": ("stop_id", "stop_name", "lat", "lon"),
    "route_edges": (
        "edge_id", "route_name", "from_stop_id", "to_stop_id", "travel_time_min"
    ),
    "pois": (
        "poi_id", "poi_name", "poi_type", "rating", "lat", "lon",
        "osm_type", "osm_id", "address", "source",
    ),
    "poi_items": ("item_id", "item_name"),
    "stop_poi_mapping": ("stop_id", "poi_id", "walking_time_min"),
    "poi_item_mapping": ("poi_id", "item_id", "price", "service_time_min"),
}


def _read_sql_table(csv_like_path: Path) -> list[dict[str, object]]:
    """Match the shared algorithm's reader interface using an SQL table."""
    table = csv_like_path.stem
    columns = TABLE_COLUMNS.get(table)
    if columns is None:
        raise ValueError(f"不允許讀取未知資料表：{table}")
    if not DATABASE_PATH.is_file():
        raise FileNotFoundError(
            f"找不到 SQL 資料庫：{DATABASE_PATH}。請先執行 "
            "python sql_database/import_csv_to_sqlite.py"
        )

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"SELECT {', '.join(columns)} FROM {table}"
        ).fetchall()
    return [dict(row) for row in rows]


# The SQL web app runs in its own process. Its shared algorithms therefore use
# this database reader without changing the separately launched CSV web app.
_csv_queries._read_csv = _read_sql_table

Stop = _csv_queries.Stop
RouteStop = _csv_queries.RouteStop
DirectBus = _csv_queries.DirectBus
TransferLeg = _csv_queries.TransferLeg
BusJourney = _csv_queries.BusJourney
NearbyStop = _csv_queries.NearbyStop
ProductPOI = _csv_queries.ProductPOI
PlacePOI = _csv_queries.PlacePOI
ShoppingRoute = _csv_queries.ShoppingRoute
ShoppingTrip = _csv_queries.ShoppingTrip


def list_all_stops():
    return _csv_queries.list_all_stops(SQL_DIR)


def list_routes():
    return _csv_queries.list_routes(SQL_DIR)


def get_route_stop_sequence(route_name: str):
    return _csv_queries.get_route_stop_sequence(route_name, SQL_DIR)


def find_stop_id(query: str):
    return _csv_queries.find_stop_id(query, SQL_DIR)


def find_direct_buses(start_query: str, end_query: str):
    return _csv_queries.find_direct_buses(start_query, end_query, SQL_DIR)


def find_bus_journey(start_query: str, end_query: str):
    return _csv_queries.find_bus_journey(start_query, end_query, SQL_DIR)


def find_product_pois(query: str):
    return _csv_queries.find_product_pois(query, SQL_DIR)


def find_places(query: str):
    return _csv_queries.find_places(query, SQL_DIR)


def find_best_shopping_route(start_query: str, product_poi: ProductPOI):
    return _csv_queries.find_best_shopping_route(start_query, product_poi, SQL_DIR)


def find_best_shopping_trip(start_query: str, end_query: str, product_poi):
    return _csv_queries.find_best_shopping_trip(
        start_query, end_query, product_poi, SQL_DIR
    )
