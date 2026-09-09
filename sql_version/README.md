# SQLite 資料庫版本

這個資料夾是專題目前使用的 SQL 儲存層。`bus_queries_sql.py` 執行時會直接讀取
`shopping_bus.db`，不會讀取 CSV。`../csv_version/generated_csv_260607/` 內的 6 個 CSV
只保留作為首次建庫或日後重新匯入的來源。

## 啟動 SQL 網頁版

在專案根目錄執行：

```powershell
streamlit run sql_version/bus_query_app_sql.py
```

SQL 網頁版會直接查詢本資料夾的 `shopping_bus.db`。原本的 CSV 網頁版仍可獨立執行：

```powershell
streamlit run csv_version/bus_query_app.py
```

## 建立或更新資料庫

在專案根目錄執行：

```powershell
python sql_version/import_csv_to_sqlite.py
```

每次執行都會清空資料表後重新匯入，因此 CSV 更新後再執行一次即可同步。
也可以指定其他來源及輸出路徑：

```powershell
python sql_version/import_csv_to_sqlite.py --csv-dir csv_version/generated_csv_260607 --db sql_version/shopping_bus.db
```

## 檔案說明

- `schema.sql`：資料表、外鍵、檢查條件及索引。
- `import_csv_to_sqlite.py`：使用 Python 內建 `sqlite3` 匯入 CSV，不需安裝套件。
- `bus_queries_sql.py`：SQL 版資料存取與查詢入口。
- `bus_query_app_sql.py`：SQL 版 Streamlit 網頁入口。
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
