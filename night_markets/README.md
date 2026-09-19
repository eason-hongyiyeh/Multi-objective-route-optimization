# 大台北夜市 CSV 資料

收錄臺北市、新北市、基隆市的夜市與夜間攤販街區，整理日期為 **2026-09-19**。共 **64 筆**：臺北市 20 筆、新北市 41 筆、基隆市 3 筆。

清單合併官方市場名冊、官方觀光景點與民間夜市目錄，補入地方型夜市並排除可辨識的重複項目。**這不是保證涵蓋所有臨時夜市、且全部仍在營業的名冊**；新開幕、搬遷、停業與來源未收錄的夜市仍可能遺漏。本版未提供可供程式判斷的營業日、時段或即時營業狀態，不能假設每天都能造訪。

## 檔案用途

| 檔案 | 用途 | 筆數 |
| --- | --- | ---: |
| `night_markets.csv` | 夜市名稱、行政區、地址與 WGS84 座標。 | 64 |
| `market_stops.csv` | 夜市與一公里內捷運站碼的候選關聯。 | 65 |
| `market_sources.csv` | 各夜市名冊來源、座標來源、位置品質與查核註記。 | 64 |
| `excluded_candidates.csv` | 排除或合併的候選項目及原因；不是任務點主表。 | 4 |

## night_markets.csv

| 欄位 | 說明 |
| --- | --- |
| `market_id` | 夜市唯一 ID，例如 `NM001`；後續維護不要因排序而重新編號。 |
| `market_name` | 夜市名稱。 |
| `city`、`district` | 縣市與行政區。 |
| `address` | 夜市營業範圍或地址，不一定是單一門牌。 |
| `lat`、`lon` | WGS84 十進位緯度與經度；小數位數不代表實測精度。 |

艋舺夜市以廣州街、梧州街等分區分別收錄，集合名稱不再額外建立任務點。五股工業區夜市依五工二路所在地記為新莊區。基隆廟口夜市包含相連的愛四路夜市，不再重複列一筆。

## market_stops.csv

| 欄位 | 說明 |
| --- | --- |
| `market_id` | 關聯 `night_markets.market_id`。 |
| `stop_id` | 關聯 `../taipei_mrt/stops.csv` 的 `stop_id`。 |
| `straight_distance_m` | 夜市代表點與車站代表點之間的球面直線距離，四捨五入至公尺。 |

`market_id` 加 `stop_id` 是複合主鍵。一個夜市可對應多站，一站也可對應多個夜市。使用 Haversine 公式、地球平均半徑 6,371,008.8 公尺，篩選未四捨五入前的距離 ≤ 1,000 公尺。

目前 29 個夜市有候選站關聯。**候選關聯不是已確認可走的道路，也不是步行時間。** 隔河、出口位置與道路障礙尚未處理。沒有關聯代表沒有符合條件的站或位置待確認，不代表夜市不存在或無法搭其他交通工具抵達。

## market_sources.csv

`market_id` 同時是主鍵與夜市外鍵，一個夜市一筆來源紀錄。

| 欄位 | 說明 |
| --- | --- |
| `source_url` | 確認夜市名稱或營業範圍的來源。 |
| `coordinate_source_url` | 座標的實際來源，可能與名冊來源不同。 |
| `coordinate_type` | 座標取得方式與限制，見下表。 |
| `verification` | `official_listing` 為官方名冊列載；`community_listing` 為民間目錄列載，均不等於實地營業查核。 |
| `retrieved_at` | 本次取得資料日期，不是來源最後更新日期。 |
| `note` | 轉換方法、修正與查核事項。 |

| coordinate_type | 意義 |
| --- | --- |
| `official_representative_point` | 官方代表座標，可能是街區中心，不是入口。 |
| `published_point` | 民間公開頁面座標，未實測。 |
| `approximate_street_point` | 6 筆僅有道路代表點，須再定位夜市實際範圍。 |
| `location_needs_review` | 2 筆官方地址與民間座標版本不同，須再核對。 |

最後兩類共 8 筆保留於名冊，但**不產生 `market_stops` 候選關聯**。精準路線規劃前先確認這些點位，並補上道路及營業時段資料。

## excluded_candidates.csv

`market_name` 為候選名稱，`disposition` 為處理方式，`reason` 為原因，`source_url` 為來源。本檔是整理紀錄，沒有主表外鍵，不應直接加入路線任務。

## 資料來源與重建

- [臺北市攤販集中場開放資料](https://data.taipei/dataset/detail?id=c013d9ec-a550-46bd-ac60-45f085930706)：挑選夜市，將原始度分秒轉為十進位。
- [新北市政府市場處夜市名冊](https://www.newtaipeimarket.ntpc.gov.tw/tc/mapNight.aspx?id=74&mid=26)：核對 18 個官方列載夜市。
- [新北市觀光旅遊網](https://newtaipei.travel/zh-tw/attractions/list)：取得 7 個景點官方座標，各列提供直接來源連結。
- [今夜有市](https://tonightmarkets.com/night-markets)：補充地方夜市，只整理名稱、地址與座標等事實欄位，不轉載介紹文章。
- [OpenStreetMap](https://www.openstreetmap.org/copyright)：6 筆道路代表座標由 Nominatim 查詢取得，© OpenStreetMap contributors，依 ODbL 提供；各筆保留原始圖徵連結。再利用時須保留來源並遵循相應授權。

公開資料也可能有錯誤，已修正可辨識的行政區及重複名稱，其他未發現的錯誤仍可能存在。原始快照與重建工具位於儲存庫外的 `myproject/sources/night_market_fare/`，不會隨此儲存庫 push；核心資料可直接讀取，不需要原始快照。

捷運票價見 [`../taipei_mrt/fares.csv`](../taipei_mrt/fares.csv)，其費用是進出站一趟的費用，並非夜市入場費或相鄰站邊權重。
