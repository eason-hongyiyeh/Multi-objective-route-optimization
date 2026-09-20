# 大台北地區夜市 CSV 資料


## 檔案用途

| 檔案 | 用途 | 筆數 |
| --- | --- | ---: |
| `night_markets.csv` | 夜市名稱、行政區、地址與 WGS84 座標。 | 61 |
| `market_stops.csv` | 夜市與一公里內捷運站碼的候選關聯。 | 65 |

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
| `market_id` | 關聯 `night_markets.market_id`。 |
| `stop_id` | 關聯 `../taipei_mrt/stops.csv` 的 `stop_id`。 |
| `straight_distance_m` | 夜市代表點與車站代表點之間的球面直線距離，四捨五入至公尺。 |

`market_id` 加 `stop_id` 是複合主鍵。一個夜市可對應多站，一站也可對應多個夜市。使用 Haversine 公式、地球平均半徑 6,371,008.8 公尺，篩選未四捨五入前的距離 ≤ 1,000 公尺。
