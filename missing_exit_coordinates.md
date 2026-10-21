# 缺少座標的出口資料核對

來源查詢日期：2026-10-19。專案資料：`data/mrt_exits.geojson`。

最初核對時共有 22 筆 `geometry: null`，以相同節點 ID 查詢 OpenStreetMap 官方 API 均可讀到參考座標，並非 OSM 沒有座標。依使用者要求移除 LG09、LG10 共 5 筆後，目前專案保留 17 筆。下表只列出這 17 筆待校正出口；參考座標尚未經人工確認，不自動寫入正式出口位置。未取得當時的匯出查詢，無法斷定是匯出範圍設定還是後續處理造成 null。

目前 12 筆有 OSM `stop_area` 車站關聯，另外 5 筆只能用位置比對，仍需人工確認。下表的 OSM 連結可逐筆核對；不把座標最近當成已核准配對。

## 逐筆清單

| OSM 節點 | 原始名稱 | 原始出口編號 | 所屬車站／候選車站 | 判定依據 | OSM 經度、緯度 |
| --- | --- | --- | --- | --- | --- |
| [4302077472](https://www.openstreetmap.org/node/4302077472) | 汐科火車站北入口 | 未提供 | 汐科（臺鐵） | [OSM 車站關聯 8038846](https://www.openstreetmap.org/relation/8038846) | 121.6526564, 25.0640415 |
| [4399019831](https://www.openstreetmap.org/node/4399019831) | 未提供 | 1 | 體育大學 A7（機場捷運） | [OSM 車站關聯 8487054](https://www.openstreetmap.org/relation/8487054) | 121.3851265, 25.0411551 |
| [4399019832](https://www.openstreetmap.org/node/4399019832) | 未提供 | 2 | 體育大學 A7（機場捷運） | [OSM 車站關聯 8487054](https://www.openstreetmap.org/relation/8487054) | 121.3856723, 25.0412177 |
| [6181694198](https://www.openstreetmap.org/node/6181694198) | 出口 1 | 1 | 泰山貴和 A6（機場捷運） | [OSM 車站關聯 8487061](https://www.openstreetmap.org/relation/8487061) | 121.4222254, 25.0331881 |
| [8044395053](https://www.openstreetmap.org/node/8044395053) | 未提供 | 未提供 | 淡江大學（淡海輕軌） | [OSM 車站關聯 12822080](https://www.openstreetmap.org/relation/12822080) | 121.455859, 25.1768885 |
| [8044395064](https://www.openstreetmap.org/node/8044395064) | 未提供 | 未提供 | 淡金北新（淡海輕軌） | [OSM 車站關聯 12822077](https://www.openstreetmap.org/relation/12822077) | 121.4523339, 25.180867 |
| [8044437776](https://www.openstreetmap.org/node/8044437776) | 未提供 | 未提供 | 竿蓁林（淡海輕軌）【待確認】 | OSM 節點位置與車站點位／站體位置比對；出口未加入車站關聯 | 121.4561252, 25.1625618 |
| [8044442692](https://www.openstreetmap.org/node/8044442692) | 未提供 | 2 | 淡金鄧公（淡海輕軌） | [OSM 車站關聯 12822112](https://www.openstreetmap.org/relation/12822112) | 121.4606018, 25.1692274 |
| [8044442693](https://www.openstreetmap.org/node/8044442693) | 未提供 | 1 | 淡金鄧公（淡海輕軌） | [OSM 車站關聯 12822112](https://www.openstreetmap.org/relation/12822112) | 121.4605804, 25.1690053 |
| [8664518337](https://www.openstreetmap.org/node/8664518337) | 出口 1 | 1 | 泰山 A5（機場捷運） | [OSM 車站關聯 8487059](https://www.openstreetmap.org/relation/8487059) | 121.4396828, 25.0528702 |
| [8664518338](https://www.openstreetmap.org/node/8664518338) | 出口 3 | 3 | 泰山 A5（機場捷運） | [OSM 車站關聯 8487059](https://www.openstreetmap.org/relation/8487059) | 121.4397431, 25.0526096 |
| [8664518339](https://www.openstreetmap.org/node/8664518339) | 出口 2 | 2 | 泰山 A5（機場捷運） | [OSM 車站關聯 8487059](https://www.openstreetmap.org/relation/8487059) | 121.439774, 25.0529485 |
| [9373325210](https://www.openstreetmap.org/node/9373325210) | 未提供 | 1 | 幸福 Y19（環狀線）【待確認】 | OSM 節點位置與車站點位／站體位置比對；出口未加入車站關聯 | 121.4603162, 25.0500787 |
| [9373325211](https://www.openstreetmap.org/node/9373325211) | 未提供 | 2 | 幸福 Y19（環狀線）【待確認】 | OSM 節點位置與車站點位／站體位置比對；出口未加入車站關聯 | 121.4603242, 25.0497968 |
| [9864977723](https://www.openstreetmap.org/node/9864977723) | 出口 4 | 4 | 泰山 A5（機場捷運） | [OSM 車站關聯 8487059](https://www.openstreetmap.org/relation/8487059) | 121.4389776, 25.0530568 |
| [9952975582](https://www.openstreetmap.org/node/9952975582) | 未提供 | 1 | 新莊副都心 A4（機場捷運）【待確認】 | OSM 節點位置與車站點位／站體位置比對；出口未加入車站關聯 | 121.4460421, 25.0592762 |
| [9952975595](https://www.openstreetmap.org/node/9952975595) | 未提供 | 2 | 新莊副都心 A4（機場捷運）【待確認】 | OSM 節點位置與車站點位／站體位置比對；出口未加入車站關聯 | 121.4464575, 25.0588799 |

## 位置比對的限制

- 新莊副都心兩筆距專案車站點約 27、77 公尺；[桃園捷運官方出口資訊](https://www.tymetro.com.tw/tymetro-new/tw/_pages/travel-guide/A4/A15)列有 1、2 號出口。OSM 出口節點未直接加入該站關聯，仍標為待確認。
- 幸福兩筆距專案車站點約 37、42 公尺，位於 OSM 幸福站站體附近；[新北捷運幸福站頁面](https://www.ntmetro.com.tw/basic/?mode=detail&node=808)可供核對。OSM 出口節點未直接加入該站關聯，仍標為待確認。
- 竿蓁林候選依據是出口節點附近的 [OSM 竿蓁林站點](https://www.openstreetmap.org/node/6155745375)與站體，來源未提供出口編號，也沒有直接車站關聯，仍需確認。

## 已移除資料的原始來源

LG09 的 C1、C2，以及 LG10 的 A、B、C 已依使用者要求，從專案 `data/mrt_exits.geojson` 與 `data/exit_review_context.json` 移除。人工校正檔沒有這 5 筆紀錄，無須刪除其他人工成果。這裡僅保留來源對照，不作為地圖資料載入。

- 原始下載檔：`D:\OSM\mrt_exits.geojson`，仍保留原內容，這 5 筆在第 496～500 行。
- 專案原先使用的副本：`data/mrt_exits.geojson`，已刪除這 5 筆。
- 副本檔頭記載 `generator: overpass-turbo`，資料來自 OpenStreetMap；`timestamp` 為 `2026-09-30T12:19:51Z`。
- 移除前這 5 筆均有 `construction: yes`、`railway: subway_entrance`，且 `geometry: null`。

| 車站 | 出口 | OSM 原始節點 |
| --- | --- | --- |
| LG09 | C1 | [13604848314](https://www.openstreetmap.org/node/13604848314) |
| LG09 | C2 | [13604848309](https://www.openstreetmap.org/node/13604848309) |
| LG10 | A | [13604848315](https://www.openstreetmap.org/node/13604848315) |
| LG10 | B | [13604848316](https://www.openstreetmap.org/node/13604848316) |
| LG10 | C | [13604848317](https://www.openstreetmap.org/node/13604848317) |
