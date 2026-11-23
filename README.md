# 捷運與周邊地點地圖

| 資料夾／檔案 | 用途 |
| --- | --- |
| [data/](data/README.md) | 存放捷運車站、路線、出口，以及夜市、景點、飯店和餐廳資料。 |
| [walking/](walking/README.md) | 存放夜市步行路線、距離、時間，以及景點步行篩選紀錄。 |
| [mrt_excel/](mrt_excel/README.md) | 捷運站名、路段時間、轉乘步行、票價及發車班表等 CSV，查詢時直接讀取。 |
| [imports/](imports/README.md) | 存放抓取的餐廳與景點候選、原始回應及缺漏報告；地圖顯示最新完整一批候選。 |
| [fetch_recommendation_data.py](fetch_recommendation_data.py) | 抓取並清理 OSM 餐廳與景點；`--clean-latest` 可只清理最新下載資料。 |
| [calculate_market_walks.py](calculate_market_walks.py) | 計算夜市到最近捷運站點的道路步行路徑，保留 20 分鐘（1,200 公尺）內的結果。 |
| [map.html](map.html) | 網頁地圖、遊玩行程推薦表單、圖層勾選與地點資訊。 |
| [itinerary_query.js](itinerary_query.js) | 遊玩推薦表單送出、行程卡片及道路步行路徑顯示。 |
| [itinerary_planner.py](itinerary_planner.py) | 本機條件推薦台北車站周邊 1 個景點＋1 間餐廳，整合捷運班表及道路步行。 |
| [route_query.js](route_query.js) | 繪製推薦行程中的捷運路線；已移除獨立捷運查詢介面。 |
| [route_planner.py](route_planner.py) | 整合 CSV，以 Dijkstra 比較班次，計算預估最早抵達路線與票價。 |
| [mrt_map.py](mrt_map.py) | 啟動本機網站，載入 data/、imports/ 最新候選，提供地圖資料與路線查詢 API。 |

在 `mrt-route` 資料夾執行 `python mrt_map.py`，開啟終端機顯示的網址。左側只保留遊玩行程推薦，捷運搭乘方式、時間與票價會整合在推薦結果中。同名出發站請選搭乘路線；國定假日需手動勾選。修改 CSV 後請重啟程式。

左側最上方「遊玩行程推薦」可選出發站、時間、景點偏好、餐廳關鍵字與可用總時間，再按「推薦遊玩行程」。第一版目的區為台北車站周邊，採本機規則，尚未連接學校 LLM；餐廳關鍵字只比對名稱與料理標籤。藍色虛線為道路步行路徑，每段最多 1,200 公尺、每秒 1 公尺；另外驗證餐廳到所選出口的路徑在 1,200 公尺內。最多比對 3 組可行組合，不宣稱全區最佳解。第一次查詢可能需約 40 秒，路網查詢失敗不改用直線距離。

營業時間僅判讀基本 OSM 時段，無法判讀就顯示待確認；出站、遊玩、用餐時間為表單設定的估計值。票價只包含捷運，不含門票、餐費與回程。建物外框中心、已知非地面樓層與疑似重複點不作為步行目的地。台北車站出口編號與所屬站依 [北捷官方出口表](https://web.metro.taipei/pages2026/WebStation/051/1)，座標沿用現有 OSM 資料；步行由 [Valhalla](https://valhalla.github.io/valhalla/) 查詢並快取於 `walking/.cache/`。

左側「下載餐廳」「下載景點」可勾選顯示 imports/ 最新完整一批資料，按「查看下載範圍」移到該區域。空心點只在滑鼠移入時顯示名稱，點擊可看時間、來源與缺漏；尚未核對營業時間或篩選步行 1,200 公尺。相同 ID 的既有地點不重複顯示。下載新一批資料後請重啟地圖。

機捷平假日使用相同班表。文湖線班表待補；涉及缺少班表的路線只提供已知行駛與轉乘時間。估算不含資料未提供的途中停站時間；票價缺漏會標示「資料待補」。
