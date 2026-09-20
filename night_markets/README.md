# 大台北地區夜市 CSV 資料


## 檔案用途

| 檔案 | 用途 | 筆數 |
| --- | --- | ---: |
| `night_markets.csv` | 夜市名稱、行政區、地址與 WGS84 座標。 | 61 |
| `market_stops.csv` | 每個夜市在步行一公里內最近的一個捷運站碼。 | 26 |

## night_markets.csv

| 欄位 | 說明 |
| --- | --- |
| `market_id` | 夜市唯一 ID，例如 `NM001`；後續維護不要因排序而重新編號。 |
| `market_name` | 夜市名稱。 |
| `city`、`district` | 縣市與行政區。 |
| `address` | 每個夜市只留一個代表地址。 |
| `lat`、`lon` | 每個夜市一組 WGS84 十進位緯度與經度；小數位數不代表實測精度。 |

## market_stops.csv

| 欄位 | 說明 |
| --- | --- |
| `market_id` | 主鍵，關聯 `night_markets.market_id`；每個夜市最多一筆。 |
| `stop_id` | 關聯 `../taipei_mrt/stops.csv` 的 `stop_id`。 |
| `walking_distance_m` | 捷運站附近路網點到夜市附近路網點的步行路線長度，四捨五入至公尺。 |


