# 餐廳與景點候選資料

在 `mrt-route` 資料夾執行：

```powershell
python fetch_recommendation_data.py
```

僅使用 Python 標準函式庫，不需安裝套件或提供 API Key。預設讀取 `mrt_excel/stops.csv` 的台北車站 `BL12` 座標，查詢周邊 2 公里內的 OpenStreetMap 物件。每次執行另建時間命名的子資料夾，保留之前的結果。

抓取後自動移除缺名稱、無效座標、相同 ID，以及同類同名且 25 公尺內、沒有分店／樓層／街道／門牌衝突的重複點。地址不同者保留待核對，避免誤刪分店；缺營業時間不刪。原始 `overpass_raw.json` 保留追溯，地圖只使用清理後的兩份候選清單。清理統計與移除 ID 在 `fetch_report.json` 的 `cleaning_history`。

只清理已下載資料：`python fetch_recommendation_data.py --clean-latest`。本批餐廳由 2,672 筆變成 2,540 筆（缺名 126、重複 6）；景點由 858 筆變成 341 筆（缺名 511、與既有 ID 重複 6），無效座標 0 筆。

| 輸出檔案 | 內容 |
| --- | --- |
| `overpass_raw.json` | Overpass 原始回應，保留原始標籤，供日後核對或免連網重新整理。 |
| `RestaurantCandidates.json` | 餐廳、速食及美食街候選；包含名稱、座標、料理標籤、原始營業時間、來源及缺漏標記。 |
| `AttractionCandidates.json` | 博物館、公園、花園、觀景點、古蹟、寺廟等候選；包含名稱、座標、原始開放時間、來源及缺漏標記。 |
| `fetch_report.json` | 筆數、缺漏統計、移除原因、查詢條件與資料限制。 |

修改搜尋半徑或中心：

```powershell
python fetch_recommendation_data.py --radius 1500
python fetch_recommendation_data.py --lat 25.04631 --lon 121.517415 --radius 2000
```

免重新下載，以某次的原始回應重新整理（路徑請換成實際的時間資料夾）：

```powershell
python fetch_recommendation_data.py --input imports/taipei_places_時間/overpass_raw.json
```

重新整理時，`--lat`、`--lon`、`--radius` 應與該次查詢一致。參數只用於統計代表點的位置，不會擴大、縮小或補抓原始資料的範圍。

執行 `python mrt_map.py` 後，地圖會讀取名稱排序最新、同時有兩份候選 JSON 的 `taipei_places_*` 資料夾，只顯示這一批，不疊加歷次下載。左側勾選「下載餐廳」「下載景點」，按「查看下載範圍」定位。空心點滑鼠移入顯示名稱，點擊顯示時間、座標、來源與缺漏。原始回應不載入地圖，缺名稱點已從候選清單移除。新增下載結果後請重啟地圖。

營業時間缺漏與待核對情況標記在 `DataIssues`；沒有查到的營業時間保持空白。有時間標籤也不代表已由店家確認。推薦功能會再篩選點位，依每次需求查詢步行路徑；整份資料尚未全部通過 1,200 公尺步行篩選。

`CoordinateType=osm_node` 表示 OSM 節點座標；`osm_bbox_center` 表示物件外框中心，可能不在建物或園區內，也不代表入口。匯入推薦系統前仍需核對可步行抵達的位置與營業時間。

搜尋半徑只是候選查詢條件，**不是步行距離**。之後需以道路步行路徑確認是否符合捷運出口 1,200 公尺範圍，以及景點與餐廳間能否步行串接。

資料來源：[OpenStreetMap contributors](https://www.openstreetmap.org/copyright)，授權為 [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/)。查詢使用 [Overpass API](https://wiki.openstreetmap.org/wiki/Overpass_API/Overpass_QL)。下載後使用本機檔案，不在每次開啟地圖時重新大量查詢。
