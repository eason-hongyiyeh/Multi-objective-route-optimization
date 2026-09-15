# CSV 版本

這個資料夾提供直接讀取 CSV 的高雄公車與便利商店查詢程式，不需要建立 SQLite 資料庫。

## 功能

- 在互動地圖查看站牌與便利商店位置、編號及來源，切換站牌的 100 公尺範圍。
- 查看站牌清單、各路線站序、直達及轉乘方案。
- 搜尋便利商店與一般商品，安排途中採買行程。

地圖位置依資料檔座標顯示；資料查核狀態、各時間估算的限制與欄位定義，請查看
[generated_csv_260607 資料說明](generated_csv_260607/README_generated.md)。

## 檔案與資料夾

| 名稱 | 用途 |
| --- | --- |
| `bus_query_app.py` | Streamlit 網頁入口，整合地圖與查詢分頁 |
| `bus_map.py` | 讀取座標並繪製互動地圖、標記及範圍圈 |
| `bus_queries.py` | CSV 資料讀取、路線搜尋與採買行程邏輯 |
| `generate_convenience_store_data.py` | 同步 OSM 便利商店，產生商品及關聯資料 |
| `estimate_bus_travel_times.py` | 計算公車站間的運動模型估算時間 |
| `test_data_quality.py` | 資料關聯、距離篩選及時間模型的回歸檢查 |
| `test_bus_map.py` | 地圖座標、圖層及篩選的檢查 |
| `generated_csv_260607/` | 網頁實際使用的資料與來源快照；欄位說明見該資料夾 README |
| `routes.csv` | 既有路線原始資料 |
| `routes_with_coordinates.csv` | 既有附座標路線原始資料；網頁不直接讀取此檔 |
| `__init__.py` | 讓此資料夾可作為 Python 套件匯入 |

## 環境準備與啟動

以下指令適用於 Windows PowerShell，皆在專案根目錄 `Multi-objective-route-optimization` 執行。
目前使用 Python 3.12.8 與 Streamlit 1.63.0。

首次建立環境並安裝套件：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install streamlit==1.63.0
```

地圖使用 Leaflet 1.9.4，透過網頁載入，無需額外安裝 Python 地圖套件。
如果已有這個專案的虛擬環境，可直接啟動：

```powershell
.\.venv\Scripts\python.exe -m streamlit run csv_version/bus_query_app.py
```

不需要先啟用虛擬環境。開啟終端機顯示的 Local URL；停止程式按 `Ctrl+C`。

## 地圖操作

開啟「站牌與商店地圖」分頁，藍色 S 為站牌、綠色 P 為便利商店。
可拖曳、縮放，滑鼠停在標記上查看名稱、座標與來源狀態；地圖下方可展開商店清單並開啟 OSM 原始來源。
四個勾選框可切換站牌、店家、100 公尺圓圈與編號。

地圖透過 Streamlit 內嵌 Leaflet，搭配 OpenStreetMap 街道底圖；目前設定不需 API 金鑰。
瀏覽器需能連線到 unpkg.com 載入地圖元件，以及 tile.openstreetmap.org 載入底圖；CSV 表格仍可直接查看。
底圖只載入目前畫面需要的圖磚；請遵守 [OpenStreetMap 圖磚使用規則](https://operations.osmfoundation.org/policies/tiles/)，不要用來大量下載或離線預抓。
[Leaflet 地圖元件說明](https://leafletjs.com/examples/quick-start/)。

## 資料更新工具

以下工具會覆寫輸出資料，執行前請先備份手工修正或實測資料。

```powershell
# 以已保存的來源快照重新產生便利商店與關聯資料，不連網
.\.venv\Scripts\python.exe csv_version/generate_convenience_store_data.py

# 更新 OSM，並查詢未快取的步行路徑（需網路）
.\.venv\Scripts\python.exe csv_version/generate_convenience_store_data.py --fetch-osm --fetch-walking

# 將 POI 重編為 P001 起算，連同兩張關聯表重建
.\.venv\Scripts\python.exe csv_version/generate_convenience_store_data.py --renumber-pois

# 將步行時間留空，等待實測
.\.venv\Scripts\python.exe csv_version/generate_convenience_store_data.py --walking-mode unknown

# 重算公車模型時間；可用 --help 查看參數
.\.venv\Scripts\python.exe csv_version/estimate_bus_travel_times.py
```

同步工具以完整導航查詢網址快取。要重新查詢既有路徑，先備份並移走資料夾中的 `sources/walking_routes.json`，再執行含 `--fetch-walking` 的指令。公共導航查詢依序執行，間隔至少 1.1 秒。
這些工具只更新 CSV 版，不會自動同步 SQL 版資料庫。

## 檢查

```powershell
.\.venv\Scripts\python.exe -m unittest csv_version.test_data_quality csv_version.test_bus_map -v
```
