"""Launch the existing Streamlit interface with the SQL query backend."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

SQL_DIR = Path(__file__).resolve().parent
if str(SQL_DIR) not in sys.path:
    sys.path.insert(0, str(SQL_DIR))

import bus_queries_sql
import streamlit as st


# bus_query_app imports a module named bus_queries. For this standalone SQL
# process, provide the SQL implementation under that name and reuse the same UI.
sys.modules["bus_queries"] = bus_queries_sql
runpy.run_path(str(SQL_DIR.parent / "csv_version" / "bus_query_app.py"))
st.sidebar.success("目前資料來源：SQLite（shopping_bus.db）")
