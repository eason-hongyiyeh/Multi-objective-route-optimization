# data：地圖資料

這個資料夾存放捷運、出口、夜市、景點、飯店與餐廳資料，由專案根目錄的 `mrt_map.py` 讀取。



| 檔案 | 筆數 | 內容與用途 |
| --- | ---: | --- |
| [airport_mrt_exits.geojson](airport_mrt_exits.geojson) | 36 | 機場捷運出入口 |
| [airportmrt.geojson](airportmrt.geojson) | 117 | 機場捷運路線 |
| [AttractionList_with_fee_and_hours.json](AttractionList_with_fee_and_hours.json) | 31 | 景點 |

| [HotelList.json](HotelList.json) | 314 | 飯店／旅宿 |
| [mrt_exits.geojson](mrt_exits.geojson) | 510 | 捷運出入口 |
| [mrt_station.geojson](mrt_station.geojson) | 158 | 捷運車站點 |
| [mrt_tracks.geojson](mrt_tracks.geojson) | 256 | 捷運路線 |
| [nightmarket.geojson](nightmarket.geojson) | 17 | 夜市 |
| [RestaurantList.json](RestaurantList.json) | 17 | 餐廳 |

新增或更新資料後，請重新啟動 `python mrt_map.py`，再重新整理網頁。

