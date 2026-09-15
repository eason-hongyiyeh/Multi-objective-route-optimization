# CSV 版本

這個資料夾包含原本以 CSV 儲存及讀取資料的版本。

## 最新資料整理

便利商店、POI 連續編號、100 公尺篩選、步行時間與公車等加減速模型，請查看
[資料來源與計算說明](generated_csv_260607/README_generated.md)。

- [便利商店清單](generated_csv_260607/pois.csv)
- [站牌與店家的步行資料](generated_csv_260607/stop_poi_mapping.csv)
- [每個站牌的店家筆數](generated_csv_260607/stop_store_coverage.csv)

POI 已重編為 P001–P011，兩張關聯表也同步更新；店家為 OSM 地圖紀錄，尚未逐店核實營業狀態及是否漏店。

54 個公車路段已依現有座標的直線距離、最高 50 km/h、加速與減速度大小各 1 m/s² 估算。長路段前後各約 96.45 公尺加速／減速；不足約 192.90 公尺時在中點開始減速，最高速度低於 50 km/h。數值供模型行程使用，未含道路繞行、紅綠燈及上下客時間，不是實際車程。

在專案根目錄執行以下指令可重算（會覆寫全部路段的時間欄位）：

```powershell
python csv_version/estimate_bus_travel_times.py
```

## 啟動網頁

在專案根目錄啟動網頁：

```powershell
streamlit run csv_version/bus_query_app.py
```

主要檔案：

- `bus_query_app.py`：CSV 版 Streamlit 網頁。
- `bus_queries.py`：CSV 資料讀取及公車查詢邏輯。
- `generated_csv_260607/`：網頁目前使用的 6 份資料。
- `generate_convenience_store_data.py`：CSV 資料產生工具。
- `estimate_bus_travel_times.py`：以直線站距與等加減速模型估算公車站間時間。
- `routes.csv`、`routes_with_coordinates.csv`：路線原始資料。
