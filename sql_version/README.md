# SQLite 資料庫版本

## 環境準備

請先安裝 Python（目前已在 Python 3.12.8 測試）。

以下指令適用於 Windows PowerShell，請在專案根目錄 `Multi-objective-route-optimization` 執行，不是在 `sql_version` 資料夾內執行。

本專案需要 Streamlit 1.63.0。首次使用時，建立虛擬環境並安裝套件（相依套件會自動一併安裝）：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install streamlit==1.63.0
```

每台電腦都需要各自準備環境。如果已經有 `.venv`，可省略建立虛擬環境的指令。SQLite 是 Python 內建模組，不需要另外安裝。

## 準備資料庫

本儲存庫未附上 `shopping_bus.db`，請向專案維護者取得，或從已有完整資料庫的電腦複製，並放到以下位置：

```text
Multi-objective-route-optimization/
└── sql_version/
    └── shopping_bus.db
```

資料庫必須包含 `schema.sql` 定義的資料表及查詢所需資料。只執行 `schema.sql` 建立空白資料表，仍不足以正常使用網頁。

若從另一台電腦複製資料庫，請先正常關閉使用該資料庫的程式；若目的地已有同名資料庫，覆蓋前請先備份。

## 啟動 SQL 網頁版

完成套件安裝及資料庫放置後，在專案根目錄執行：

```powershell
.\.venv\Scripts\python.exe -m streamlit run sql_version/bus_query_app_sql.py
```

上述指令直接使用 `.venv` 中的 Python，不需要先啟用虛擬環境。啟動後，開啟終端機顯示的 Local URL；停止程式時，在終端機按 `Ctrl+C`。

## 檔案說明

- `schema.sql`：資料表、外鍵、檢查條件及索引。
- `bus_queries_sql.py`：SQL 版資料存取與查詢入口。
- `bus_query_app_sql.py`：SQL 版 Streamlit 網頁入口。
- `example_queries.sql`：常用的 SQL JOIN 查詢範例。
- `shopping_bus.db`：執行時需要的 SQLite 資料庫，未包含於本儲存庫，須另外取得。

