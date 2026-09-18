# 台北捷運 CSV 資料說明

## 官方路網圖

[開啟台北捷運官方路網圖（PDF）](taipei_mrt_route_map.pdf)。下載日期：2026-09-18；來源：[臺北捷運官方中英文路網圖](https://web.metro.taipei/QRCode/Routemap-TWEN.pdf)。
此圖包含周邊軌道系統的轉乘資訊，顯示範圍大於本資料集的五條主線與支線。

這個資料夾整理台北捷運的車站、路線、停靠順序、站間行駛時間與轉乘關聯，供查詢或路線最佳化使用。
資料快照下載日期為 **2026-09-17**；各項資料的更新日期以 CSV 欄位為準。

範圍包含文湖線、淡水信義線、松山新店線、中和新蘆線、板南線，以及新北投、小碧潭支線與區間車，並包含廣慈／奉天宮站。
整理後的路網不包含環狀線、淡海輕軌、安坑輕軌、機場捷運及貓空纜車。

## 每個 CSV 的用途

筆數不含第一列欄位名稱。

| 檔案 | 筆數 | 內容與用途 |
| --- | ---: | --- |
| [stops.csv](stops.csv) | 122 | 車站主檔：站碼、中文站名、座標與所屬主線。 |
| [lines.csv](lines.csv) | 5 | 主線主檔：主線代碼與名稱。 |
| [routes.csv](routes.csv) | 11 | 營運路線：區分同一主線上的不同起迄區間與支線。 |
| [route_stops.csv](route_stops.csv) | 370 | 每條營運路線、每個方向的停靠站順序。 |
| [route_edges.csv](route_edges.csv) | 234 | 去除重複站對後的相鄰站有向路段與行駛秒數，可用於建立路網。 |
| [transfers.csv](transfers.csv) | 26 | 同一車站不同站碼間的有向轉乘關聯。 |
| [data_sources.csv](data_sources.csv) | 4 | 資料來源、官方下載網址、下載時間與授權資訊。 |
| [data_dictionary.csv](data_dictionary.csv) | — | 上述六份路網資料的逐欄定義；以 `file` 和 `column` 查找。 |
| [README.csv](README.csv) | — | 本資料集的摘要、處理規則與限制，方便在試算表閱讀。 |
| [sources/stations.csv](sources/stations.csv) | 110 | 官方車站主檔的來源快照，保留來源欄位與值。 |
| [sources/lines.csv](sources/lines.csv) | 8 | 官方路線站序的來源快照，包含分支與支線記錄。 |
| [sources/routes.csv](sources/routes.csv) | 22 | 官方營運路線站序的來源快照，每個方向各一筆。 |
| [sources/times.csv](sources/times.csv) | 187 | 官方站間行駛與停靠時間的來源快照，另含環狀線記錄。 |

一般查詢與運算使用資料夾根目錄的六份路網 CSV；`sources/` 用於核對來源。
同名檔案的欄位結構不同，例如 `lines.csv` 是主線主檔，`sources/lines.csv` 是官方路線站序。

## 1. stops.csv：車站主檔

每列代表一個**站碼**，唯一識別欄位是 `stop_id`。
轉乘站可能有多個站碼，例如大安站的 `BR09` 與 `R05` 分成兩列；兩個站碼之間的轉乘關聯記錄在 `transfers.csv`。
本資料共有 122 個站碼，對應 109 個不同站名。

| 欄位 | 說明 |
| --- | --- |
| `stop_id` | 捷運站碼，例如 `BL01`、`R05`。其他表使用這個欄位關聯車站。 |
| `stop_name` | 中文站名。 |
| `lat`、`lon` | 車站代表點緯度、經度，使用 WGS84 十進位度。 |
| `line_id` | 所屬主線代碼，關聯 `lines.csv`。 |

座標為車站代表點，不是個別月台或出入口。官方合併記錄的轉乘站碼會共享座標。
車站主檔僅保留 `stop_id`、`stop_name`、`lat`、`lon`、`line_id` 五個欄位；英文站名、官方地址、原始站碼與更新日期可查閱工作區的 [sources/stations.csv](../../sources/stations.csv)。

## 2. lines.csv：主線主檔

每列代表一條主線，唯一識別欄位是 `line_id`。

| 代碼 | 名稱 |
| --- | --- |
| `BR` | 文湖線 |
| `R` | 淡水信義線 |
| `G` | 松山新店線 |
| `O` | 中和新蘆線 |
| `BL` | 板南線 |

| 欄位 | 說明 |
| --- | --- |
| `line_id` | 主線代碼，供其他表關聯。 |
| `line_name` | 主線中文名稱。 |

新北投支線歸入 `R`，小碧潭支線歸入 `G`；具體營運區間記錄在 `routes.csv`。

## 3. routes.csv：營運路線

每列代表一種起迄區間，唯一識別欄位是 `route_id`。
例如同屬中和新蘆線 `O`，`O-1` 為南勢角－迴龍，`O-2` 為南勢角－蘆洲。
這張表記錄全程車、區間車與支線的營運區間，不只記錄分支。
起點與終點不一定相鄰；中途停靠站查 `route_stops.csv`，分支與哪個站相連則查 `route_edges.csv`。

| 欄位 | 說明 |
| --- | --- |
| `route_id` | 官方營運路線代碼，例如 `O-1`、`O-2`、`R-3`。 |
| `line_id` | 所屬主線，關聯 `lines.csv`。 |
| `from_stop_id` | 方向 `0` 的起點站碼，關聯 `stops.csv`。 |
| `to_stop_id` | 方向 `0` 的終點站碼，關聯 `stops.csv`。 |

本表僅保留上述四個欄位，每條營運路線只列一次；兩個行駛方向的站序由 `route_stops.csv` 提供。
起迄站名稱可透過 `stops.csv` 查詢；單方向停靠站數可由 `route_stops.csv` 篩選路線及方向後計算。

## 4. route_stops.csv：路線停靠站順序

每列代表某條營運路線、某個方向的其中一個停靠站。
組合鍵為 `route_id + direction + stop_sequence`。

| 欄位 | 說明 |
| --- | --- |
| `route_id` | 營運路線代碼，關聯 `routes.csv`。 |
| `direction` | `0` 表示從 `routes.csv` 的 `from_stop_id` 行駛到 `to_stop_id`；`1` 表示反方向。 |
| `stop_sequence` | 停靠順序，從 `1` 開始。 |
| `stop_id` | 停靠站碼，關聯 `stops.csv`。 |

本表僅保留 `route_id`、`direction`、`stop_sequence`、`stop_id` 四個欄位。
查詢一條路線時，先篩選 `route_id` 和 `direction`，再依 `stop_sequence` 數值排序。
同一個站碼可出現在多條路線與兩個方向中，這是正常的多對多關係。

`0`、`1` 用來區分同一營運區間的往返方向，不是北上／南下，也不是主線／支線：

| 營運路線 | `direction=0` | `direction=1` |
| --- | --- | --- |
| `BR-1` | 動物園 → 南港展覽館 | 南港展覽館 → 動物園 |
| `O-2` | 南勢角 → 蘆洲 | 蘆洲 → 南勢角 |
| `R-3` | 北投 → 新北投 | 新北投 → 北投 |

兩個方向的 `stop_sequence` 都從 `1` 開始，並沿該方向遞增；同一條路線的兩份站序互為反向。

## 5. route_edges.csv：相鄰站路段與行駛時間

每列代表一個**有方向的相鄰站路段**，唯一識別欄位是 `edge_id`。
例如 `BR01 → BR02` 與 `BR02 → BR01` 分開記錄；相同起點與終點的路段只保留一筆，不依營運路線重複列出。

| 欄位 | 說明 |
| --- | --- |
| `edge_id` | 路段唯一短流水號，目前為 `E001`～`E234`，不包含路線或站碼資訊。 |
| `from_stop_id` | 路段起點站碼，關聯 `stops.csv` 的 `stop_id`。 |
| `to_stop_id` | 路段終點站碼，關聯 `stops.csv` 的 `stop_id`。 |
| `travel_time_s` | 兩站間的純行駛秒數。 |

本表僅保留上述四個欄位，單純負責站間連接與行駛時間。路段方向由 `from_stop_id → to_stop_id` 表示，
`from_stop_id + to_stop_id` 的有序組合在本表中唯一。

原有 348 筆營運路線路段已按有向站對合併成 234 筆，所有重複站對的行駛秒數經確認一致。
例如 `R05 → R06` 原先分別屬於 `R-1` 與 `R-2` 的兩筆記錄，現在合併為一筆 74 秒路段。
新 ID 依站對在原表首次出現的順序編為 `E001` 起的流水號；之後排序不應重新編號，新路段可接續新增 ID。

```csv
edge_id,from_stop_id,to_stop_id,travel_time_s
E001,BR01,BR02,67
```

程式可沿路徑加總各路段秒數，得到純行駛時間。分支仍由站點之間的連接表示；
若需判斷列車能否直達或計算換車成本，另以 `routes.csv`、`route_stops.csv` 及營運規則處理，本表不直接記錄這些資訊。

`travel_time_s` **不含候車、停站或轉乘時間**。若要計算完整旅行時間，需要另外設定或取得這些時間；分鐘數可由秒數除以 60 換算。
來源停站秒數仍可查閱工作區的 [sources/times.csv](../../sources/times.csv)，本表不儲存停站時間。

合併後的 234 筆資料中，117 筆可對應官方同方向行駛時間，另 117 筆沿用反方向秒數作為推定。
精簡後不再逐列保存時間來源狀態，因此不可將所有秒數都視為官方提供的該方向實測值；
需要核對時，請依營運區間與起訖站名比對來源時間資料。

## 6. transfers.csv：轉乘關聯

每列代表同一車站內，從一個站碼連接到另一個站碼的方向，唯一識別欄位是 `transfer_id`。
例如大安站 `BR09 → R05` 與 `R05 → BR09` 各一筆。

| 欄位 | 說明 |
| --- | --- |
| `transfer_id` | 有向轉乘關聯 ID。 |
| `from_stop_id` | 轉乘起點站碼，關聯 `stops.csv` 的 `stop_id`。 |
| `to_stop_id` | 轉乘終點站碼，關聯 `stops.csv` 的 `stop_id`。 |

本表只保留上述三個欄位，用來表示哪些站碼之間可以轉乘；站名與所屬路線可透過 `stops.csv` 查詢。
目前 26 筆有向關聯由官方來源中的同名車站推導，正反方向分列，共對應 13 組轉乘站碼。
本表不提供轉乘耗時。若最佳路線的目標包含總旅行時間，需在程式中另外設定轉乘步行與候車時間，
或另建時間資料表；沒有時間欄位不代表轉乘只需 0 分鐘。

這份表不包含站外步行轉乘。北投與七張的主線、支線共用起站站碼，換車與候車時間仍需另外建模；
不能只因站碼相同就認定可以免等待直通。

## 7. data_sources.csv：資料來源

每列是一份官方來源，唯一識別欄位是 `source_id`。

| 欄位 | 說明 |
| --- | --- |
| `source_id`、`title` | 來源代碼及資料集名稱。 |
| `dataset_url`、`download_url` | 官方資料介紹頁面及檔案下載網址。 |
| `provider` | 資料提供機關。 |
| `original_encoding` | 官方下載檔原本使用的編碼。 |
| `local_file` | 對應的本地來源快照路徑，相對於本資料夾。 |
| `downloaded_at` | 本次快照記錄時間，使用含 UTC 時區的 ISO 8601 格式。 |
| `license`、`license_url` | 授權名稱與授權條款連結。 |

其他表若出現 `source_id=stations;lines`，表示同時使用兩份來源，應以分號拆開後查找。

## 8. data_dictionary.csv 與 README.csv：說明資料

`data_dictionary.csv` 每列說明一個欄位：

| 欄位 | 說明 |
| --- | --- |
| `file` | 被說明的 CSV 檔名。 |
| `column` | 該檔案中的欄位名稱。 |
| `description` | 欄位意義、單位或處理規則。 |

這份字典涵蓋六份整理後的路網資料。來源快照與說明檔的欄位請參考本 README。

`README.csv` 使用 `item`（說明主題）與 `description`（說明內容），可直接以 Excel 閱讀資料集摘要。

## 9. sources/：官方來源快照

四份來源檔的逐欄說明、字串格式範例與分支解讀方式，請見 [sources/README.md](sources/README.md)。

以下檔案保留官方欄位及值，只統一成 UTF-8 BOM 編碼與 CSV 序列化格式。
部分欄位內仍包含引號、大括號或整段站序字串，並非整理後的一欄一值結構。

| 檔案 | 原始欄位與意義 |
| --- | --- |
| `sources/stations.csv` | `SEQNO` 為來源序號；`StationID` 為原始站碼；`StationName` 包含中英文名稱；`StationPosition` 順序為經度、緯度；`StationAddress` 為地址；`BikeAllowOnHoliday` 為假日自行車開放旗標；`UpdateTime` 為更新日期。 |
| `sources/lines.csv` | `SEQNO` 為來源序號；`LineID` 為來源路線代碼；`Stations` 包含站序、站碼與站名；`UpdateTime` 為更新日期；`Valid Time` 為來源有效日期。來源中的支線代碼保留原樣。 |
| `sources/routes.csv` | `SEQNO` 為來源序號；`RouteID` 為營運路線；`LineID` 為所屬主線；`Direction` 為方向；`Stations` 為整段停靠站序；`UpdateTime` 為更新日期。 |
| `sources/times.csv` | `SeqNo` 為各營運區間內的序號；`stationbus` 為營運區間名稱；`stationA`、`stationB` 為起訖站；`traveltime`、`stoptime` 分別為行駛及停站秒數；`UpdateTime`、`EffectiveDate` 分別為更新及生效日期。 |

來源日期保留 `YYYYMMDD` 格式。`sources/times.csv` 中的環狀線列僅作來源留存，未匯入本資料夾的標準化路網。

## 資料表如何連接

| 從哪個欄位查找 | 對應到哪張表 |
| --- | --- |
| `routes.line_id`、`stops.line_id` | `lines.line_id` |
| `route_stops.route_id` | `routes.route_id` |
| `route_stops.stop_id` | `stops.stop_id` |
| `routes`、`route_edges`、`transfers` 的 `from_stop_id` / `to_stop_id` | `stops.stop_id` |
| 各表拆開後的 `source_id` | `data_sources.source_id` |

例如要查詢「蘆洲往南勢角沿途車站」，先在 `routes.csv` 找到 `O-2`，
再從 `route_stops.csv` 找出首站為 `O54` 的方向，按站序排序，最後以 `stop_id` 查 `stops.csv` 取得站名。
需要行駛時間時，依相鄰站序取得起訖站碼，再以 `from_stop_id + to_stop_id` 查找 `route_edges.csv`，不需指定營運路線。

## 讀取方式與資料限制

全部 CSV 使用 **UTF-8 BOM**，可以用 Excel 開啟。Python 標準函式庫讀取範例：

```python
import csv
from pathlib import Path

# 假設從專案根目錄 Multi-objective-route-optimization 執行。
folder = Path("csv_version/taipei_mrt")
with (folder / "stops.csv").open(encoding="utf-8-sig", newline="") as f:
    stops = list(csv.DictReader(f))
```

`csv.DictReader` 讀入的值都是字串，數值欄位需自行轉換。空白時間表示未知，不應直接轉成零。

本次整理保留以下處理記錄：

- 小碧潭在官方車站主檔記為 `G01A`，本資料依路線站序統一成 `G03A`；原值可在 `sources/stations.csv` 的 `StationID` 查閱。
- 東門在官方車站主檔只有 `R07`，本資料依路線站序補足 `O06`，共用東門的車站座標；配對方式記錄於本說明。
- 目前有 117 筆去重後的路段沿用反方向行駛秒數作為推定；四欄版 `route_edges.csv` 不逐列保存此狀態，假設與筆數記錄於第 5 節。
- 轉乘關聯由同名站推導，沒有提供實測的轉乘步行時間。

這是獨立的捷運基礎路網資料集，可直接使用 CSV 進行查詢與運算。
使用轉乘資料時需另外處理路線狀態、候車時間與未知的轉乘時間。

資料提供機關為臺北大眾捷運股份有限公司；來源連結請見 [data_sources.csv](data_sources.csv)，
授權條款為[政府資料開放授權條款第 1 版](https://data.gov.tw/license)。
