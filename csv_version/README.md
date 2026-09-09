# CSV 版本

這個資料夾包含原本以 CSV 儲存及讀取資料的版本。

在專案根目錄啟動網頁：

```powershell
streamlit run csv_version/bus_query_app.py
```

主要檔案：

- `bus_query_app.py`：CSV 版 Streamlit 網頁。
- `bus_queries.py`：CSV 資料讀取及公車查詢邏輯。
- `generated_csv_260607/`：網頁目前使用的 6 份資料。
- `generate_convenience_store_data.py`：CSV 資料產生工具。
- `routes.csv`、`routes_with_coordinates.csv`：路線原始資料。
