# 高雄公車與 POI 推薦系統

這是一個結合高雄公車路線、站點與周邊 POI（興趣點）資料的查詢系統。使用者可以查詢公車路線、直達或轉乘方式、站點附近地點，並依照指定商品或地點取得移動路線建議。

## 主要功能

- 查詢公車站點與路線
- 查詢兩站之間的直達及轉乘方式
- 查詢站點附近的 POI
- 結合商品、地點與公車路線提供行程建議
- 使用 Streamlit 提供網頁操作介面

## 專案檔案

| 檔案或資料夾 | 說明 |
| --- | --- |
| `bus_query_app.py` | Streamlit 網頁介面 |
| `bus_queries.py` | 站點、路線、轉乘與 POI 的核心查詢邏輯 |
| `generate_convenience_store_data.py` | 取得並整理便利商店等 POI 資料 |
| `routes.csv` | 公車路線原始資料 |
| `routes_with_coordinates.csv` | 含座標資訊的公車路線資料 |
| `generated_csv_260607/` | 查詢系統使用的站點、路線、POI 與商品 CSV 資料 |

## 執行方式

安裝所需的 Python 套件後執行：

```powershell
streamlit run bus_query_app.py
```

## 資料來源

專案使用公車路線與站點資料，部分 POI 資訊透過 OpenStreetMap／Overpass API 取得。

> 這個儲存庫會隨著學習進度持續新增與更新。