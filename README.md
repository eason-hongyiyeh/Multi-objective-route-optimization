# 捷運與周邊地點地圖

| 資料夾／檔案 | 用途 |
| --- | --- |
| [data/](data/README.md) | 存放捷運車站、路線、出口，以及夜市、景點、飯店和餐廳資料。 |
| [walking/](walking/README.md) | 存放夜市步行路線、距離、時間，以及景點步行篩選紀錄。 |
| [mrt_excel/](mrt_excel/README.md) | 捷運站名、路段時間、轉乘步行、票價及發車班表等 CSV，查詢時直接讀取。 |
| [assign_exit_station.py](assign_exit_station.py) | 保留已確認的出口所屬車站，其餘依最近車站位置配對站名，輸出結果供檢查。 |
| [calculate_market_walks.py](calculate_market_walks.py) | 計算夜市到最近捷運站點的道路步行路徑，保留 20 分鐘（1,200 公尺）內的結果。 |
| [clean_exits.py](clean_exits.py) | 檢查出口座標、移除無效座標與完全重複的資料，另外輸出清理檔。 |
| [map.html](map.html) | 網頁地圖畫面、起終點表單、圖層勾選、地點資訊與步行路線顯示。 |
| [route_query.js](route_query.js) | 送出起終點及出發時間，顯示搭乘步驟、時間、票價與地圖路線。 |
| [route_planner.py](route_planner.py) | 整合 CSV，以 Dijkstra 比較班次，計算預估最早抵達路線與票價。 |
| [mrt_map.py](mrt_map.py) | 啟動本機網站，提供地圖資料與路線查詢 API。 |
| [tests/test_route_planner.py](tests/test_route_planner.py) | 檢查路線、候車、轉乘、跨午夜班次、票價及 API。 |

在 `mrt-route` 資料夾執行 `python mrt_map.py`，開啟終端機顯示的網址。左側選擇起點、終點及臺灣出發時間，再按「查詢路線」。同名站請選搭乘路線；國定假日需手動勾選。修改 CSV 後請重啟程式。

機捷平假日使用相同班表。文湖線班表待補；涉及缺少班表的路線只提供已知行駛與轉乘時間。估算不含資料未提供的途中停站時間；票價缺漏會標示「資料待補」。

執行檢查：`python -B -m unittest discover -s tests -v`。
