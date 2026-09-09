# 高雄公車與 POI 推薦系統

這是一個結合高雄公車路線、站牌、周邊地點與商品資料的查詢系統。
專案分成 CSV 與 SQL 兩個版本，兩者都可以使用 Streamlit 在網頁上操作。

## 資料夾說明

| 資料夾 | 用途 | 備註 |
| --- | --- | --- |
| `.agents/` | Codex／開發代理工具使用的專案設定資料，不屬於系統的業務程式。 | 隱藏 |
| `csv_version/` | CSV 版本。包含 Streamlit 網頁、查詢程式、CSV 產生工具、路線原始資料，以及系統實際讀取的 CSV 資料。 |
| `sql_version/` | SQL 版本。包含 Streamlit 網頁、SQL 查詢程式、SQLite 資料庫、建表語法、CSV 匯入工具及 SQL 查詢範例。 |
| `暫放/` | 尚未正式使用或留存參考的舊程式、舊資料庫、圖片、試算表與歷史資料。 | 隱藏 |
| `.local-git-excludes/` | 隱藏資料。 | 隱藏 |
| `.git/` | Git 版本控制資料，由 Git 自動管理，請勿手動修改。 | 隱藏 |

## CSV 版本

CSV 版本會直接讀取 `csv_version/generated_csv_260607/` 裡的資料。

```powershell
streamlit run csv_version/bus_query_app.py
```

詳細內容請參考 `csv_version/README.md`。

## SQL 版本

SQL 版本會讀取 `sql_version/shopping_bus.db` SQLite 資料庫。

```powershell
streamlit run sql_version/bus_query_app_sql.py
```

詳細內容請參考 `sql_version/README.md`。

## 主要功能

- 查詢公車站牌與路線
- 查詢兩站之間的直達及轉乘方式
- 查詢站牌附近的 POI
- 根據商品或地點提供公車行程建議
- 透過 Streamlit 網頁操作

## 資料來源

專案使用公車路線與站牌資料；部分 POI 資訊透過 OpenStreetMap／Overpass API 取得。
