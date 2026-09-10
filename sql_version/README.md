# SQLite 資料庫版本

## 啟動 SQL 網頁版

在專案根目錄執行：

```powershell
streamlit run sql_version/bus_query_app_sql.py
```

## 檔案說明

- `schema.sql`：資料表、外鍵、檢查條件及索引。
- `bus_queries_sql.py`：SQL 版資料存取與查詢入口。
- `bus_query_app_sql.py`：SQL 版 Streamlit 網頁入口。
- `example_queries.sql`：常用的 SQL JOIN 查詢範例。
- `shopping_bus.db`：產生的 SQLite 資料庫檔。

