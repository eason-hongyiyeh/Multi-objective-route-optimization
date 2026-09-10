# SQLite 資料庫版本

SQL 版的介面與演算法已獨立，執行時不需要 `csv_version` 的程式或 CSV 資料。
`bus_query_app_sql.py` 負責完整網頁介面；`bus_queries_sql.py` 直接讀取 SQLite，並包含路線演算法：

- `get_route_stop_sequence()`：整理路線站序。
- `find_direct_buses()`：查詢直達公車。
- `find_bus_journey()`：計算路徑，優先減少轉乘，再比較行車時間及站數。
- `find_best_shopping_route()`、`find_best_shopping_trip()`：選擇購物行程。

## 啟動 SQL 網頁版

在專案根目錄執行：

```powershell
streamlit run sql_version/bus_query_app_sql.py
```

SQL 網頁版會直接查詢本資料夾的 `shopping_bus.db`。原本的 CSV 網頁版仍可獨立執行：

```powershell
streamlit run csv_version/bus_query_app.py
```

## 維護資料庫

使用 SQL 的 `INSERT INTO`、`UPDATE` 與 `DELETE` 維護資料，並備份 `shopping_bus.db`。
`schema.sql` 可建立空資料庫結構，但不包含資料；修改該檔不會自動更新現有資料庫。

## 檔案說明

- `schema.sql`：資料表、外鍵、檢查條件及索引。
- `bus_queries_sql.py`：SQLite 資料讀取、路線演算法與購物行程查詢。
- `bus_query_app_sql.py`：獨立的 Streamlit 網頁介面。
- `example_queries.sql`：常用的 SQL JOIN 查詢範例。
- `shopping_bus.db`：產生的 SQLite 資料庫檔。

注意：目前專案的本機 Git 排除規則包含 `*.sqlite`，但不包含 `*.db`，因此這個
`shopping_bus.db` 可以正常由 Git 追蹤。如果不想提交資料庫檔，可把 `*.db` 加到
`.local-git-excludes`。

## 查看資料庫內容

### 直接瀏覽資料表

1. 按 `Ctrl + Shift + P`，執行 `SQLite: Open Database`，選擇本資料夾的 `shopping_bus.db`。
2. 在左側檔案總管的 `SQLITE EXPLORER` 展開資料庫。
3. 在想看的資料表（例如 `stops`）按右鍵，選擇 `Show Table`。

資料庫已出現在 SQLite Explorer 時，直接選資料表即可；若重新開啟 VS Code 後沒有顯示，再執行 Open Database。

### 執行 SQL 查詢

開啟 `example_queries.sql` 或自己的 `.sql` 檔，使用 `SQLite: Use Database` 將目前 SQL 文件連結到 `shopping_bus.db`。
之後在 SQL 編輯區按 `Ctrl + Shift + Q` 即可執行整份查詢（SQLite 擴充套件的預設快捷鍵）。若文件尚未連結資料庫，依提示選擇資料庫。
只想執行其中一段時，反白選取該段 SQL，再按右鍵選擇 `Run Selected Query`。

例如查看所有站牌：

```sql
SELECT * FROM stops;
```
