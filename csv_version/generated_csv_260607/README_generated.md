# 高雄公車與 POI 測試資料說明

此資料夾提供公車路線、站牌、地點（POI）與商品的測試資料。
所有 CSV 均使用 UTF-8 編碼，可透過 ID 欄位互相關聯。

## CSV 檔案總覽

| 檔案 | 用途 |
| --- | --- |
| `stops.csv` | 公車站牌主檔，記錄站牌名稱與座標 |
| `route_edges.csv` | 公車路線相鄰站點與行車時間 |
| `pois.csv` | 地點（POI）主檔，例如市場、夜市、商圈、便利商店 |
| `stop_poi_mapping.csv` | 站牌與 POI 的鄰近關係及步行時間 |
| `poi_items.csv` | 不重複的商品主檔 |
| `poi_item_mapping.csv` | POI 販售哪些商品、價格及採買時間 |

## stops.csv

用途：記錄所有公車站牌的基本資料。每個站牌只出現一次。

| 欄位 | 說明 |
| --- | --- |
| `stop_id` | 站牌唯一編號，例如 `S001` |
| `stop_name` | 站牌名稱 |
| `lat` | 緯度 |
| `lon` | 經度 |

範例：

```csv
stop_id,stop_name,lat,lon
S001,七賢一路,22.6331,120.3112
```

## route_edges.csv

用途：記錄每條公車路線中兩個相鄰站牌之間的連線，可用來計算直達、
轉乘與完整行程。

| 欄位 | 說明 |
| --- | --- |
| `edge_id` | 路段唯一編號 |
| `route_name` | 公車路線名稱，例如 `88`、`82`、`r30` |
| `from_stop_id` | 此路段起點站牌 ID |
| `to_stop_id` | 此路段終點站牌 ID |
| `travel_time_min` | 此路段預估行車分鐘數 |

範例：

```csv
edge_id,route_name,from_stop_id,to_stop_id,travel_time_min
E001,88,S032,S028,2
```

`from_stop_id` 與 `to_stop_id` 都必須存在於 `stops.csv`。

## pois.csv

用途：記錄可前往或購物的地點，例如市場、夜市、商圈、博物館與便利商店。
目前每個公車站牌都對應一間從 OpenStreetMap 查得的鄰近便利商店。

| 欄位 | 說明 |
| --- | --- |
| `poi_id` | POI 唯一編號，例如 `P001` |
| `poi_name` | 地點名稱 |
| `poi_type` | 地點類型 |
| `rating` | 測試用評分 |
| `lat` | 緯度 |
| `lon` | 經度 |
| `osm_type` | OSM 元素類型，例如 `node`、`way` |
| `osm_id` | OSM 元素 ID |
| `address` | OSM 有提供時記錄店家地址 |
| `source` | 該店家的 OpenStreetMap 頁面 |

範例：

```csv
poi_id,poi_name,poi_type,rating,lat,lon
P001,高雄車站,交通景點,4.4,22.6398,120.3023
```

便利商店資料規則：

- 透過 Overpass API 查詢站牌範圍內的 OSM `shop=convenience`。
- 經緯度、名稱、地址與 OSM ID 來自 OpenStreetMap。
- OSM node 使用節點座標；OSM way/relation 使用 Overpass 回傳的中心座標。
- 每個站牌選擇直線距離最近的便利商店。
- 相同 OSM 類型與 ID 只建立一筆 POI，多個站牌可以共用同一個 `poi_id`。
- `rating` 並非 OSM 資料，仍是 `3.6` 到 `4.8` 的穩定測試值。
- OSM 是社群維護資料，店名、地址、營業狀態與位置仍可能不完整或過期。

## stop_poi_mapping.csv

用途：記錄 POI 鄰近哪些公車站牌，以及從站牌步行到 POI 的時間。
一個 POI 可以對應多個鄰近站牌。便利商店採用一個站牌對應一家最近商店，
但同一家商店可以被多個站牌共用。

`walking_time_min` 是依站牌與店家座標的直線距離，以每分鐘 75 公尺換算，
不是沿道路計算的真實步行導航時間。

| 欄位 | 說明 |
| --- | --- |
| `stop_id` | 站牌 ID，對應 `stops.csv` |
| `poi_id` | POI ID，對應 `pois.csv` |
| `walking_time_min` | 從站牌步行到 POI 的預估分鐘數 |

範例：

```csv
stop_id,poi_id,walking_time_min
S023,P001,2
```

## poi_items.csv

用途：商品主檔。每種商品只定義一次，不記錄販售地點與價格。
目前只保留便利商店合理販售的測試商品，例如飯糰、餅乾、茶葉蛋、
三明治、飲料、泡麵、文具與日用品。

| 欄位 | 說明 |
| --- | --- |
| `item_id` | 商品唯一編號，例如 `I006` |
| `item_name` | 商品名稱，例如 `蘋果` |

範例：

```csv
item_id,item_name
I006,蘋果
```

## poi_item_mapping.csv

用途：記錄哪些 POI 販售哪些商品。這是一張 POI 與商品的多對多關聯表：

- 同一家便利商店可以對應很多個 `item_id`，因此同一個 `poi_id` 會出現多列。
- 同一個商品可以由很多家便利商店販售，因此同一個 `item_id` 也會出現多列。
- 每個「POI + 商品」組合可有自己的價格與採買時間。

| 欄位 | 說明 |
| --- | --- |
| `poi_id` | 販售地點 ID，對應 `pois.csv` |
| `item_id` | 商品 ID，對應 `poi_items.csv` |
| `price` | 此 POI 的測試用商品價格 |
| `service_time_min` | 預估採買所需分鐘數 |

範例：

```csv
poi_id,item_id,price,service_time_min
P003,I006,35,10
P004,I006,40,10
```

以上表示商品 `I006`（蘋果）可在 `P003` 與 `P004` 購買，
兩個 POI 可設定不同價格。

便利商店範例（實際 POI ID 與價格會依 OSM 同步結果變動）：

```csv
poi_id,item_id,price,service_time_min
P016,I001,25,10
P016,I002,44,4
P016,I003,40,10
```

以上三列都使用 `P016`，表示同一家便利商店同時販售瓶裝水、飯糰與餅乾。

## 資料關聯

```text
stops.csv
  ├─ route_edges.csv.from_stop_id
  ├─ route_edges.csv.to_stop_id
  └─ stop_poi_mapping.csv.stop_id

pois.csv
  ├─ stop_poi_mapping.csv.poi_id
  └─ poi_item_mapping.csv.poi_id

poi_items.csv
  └─ poi_item_mapping.csv.item_id
```

## 注意事項

- `r30`、`r31` 分別代表紅30與紅31路線。
- 便利商店座標與 OSM 識別資料來自 OpenStreetMap。
- 原有景點、市場等 POI 座標仍是專案既有資料，尚未全部改為 OSM 資料。
- 評分、商店是否有貨／販售、價格及採買時間是測試資料，不代表真實店況。
- 公車行車時間是測試資料；便利商店步行時間是直線距離估算值。
- 這些資料適合功能展示與課程專案，不適合即時導航或實際消費依據。
- 新增資料時，請先建立主檔 ID，再新增對應的關聯資料。
- 執行根目錄的 `python generate_convenience_store_data.py` 可重新從 Overpass API
  同步 OSM 便利商店，執行時需要網路連線。
- 使用 OpenStreetMap 資料時應保留 OpenStreetMap contributors attribution，
  並遵守 Open Database License（ODbL）。
