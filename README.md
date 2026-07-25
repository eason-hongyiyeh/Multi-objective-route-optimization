# 高雄公車與 POI 推薦系統

這是一個以高雄公車路線、站點資料與周邊 POI 為基礎的查詢專題。專案目標是讓使用者可以查詢公車路線、站點、轉乘方式，並結合便利商店或周邊地點資料，找出適合的移動與購物路徑。

## 專題功能

- 查詢所有公車站點與路線。
- 查詢兩站之間是否有直達公車。
- 查詢兩站之間的可行轉乘路徑。
- 查詢站點附近的 POI。
- 查詢特定商品或地點，並結合公車路線推薦行程。

## 公開檔案說明

| 檔案或資料夾 | 用途 |
| --- | --- |
| `README.md` | 專題介紹、檔案說明、公開範圍與上傳提醒。 |
| `.gitignore` | 設定哪些本機檔案不要上傳到 GitHub。 |
| `bus_query_app.py` | Streamlit 網頁介面，讓使用者用視覺化方式查詢路線、站點與 POI。 |
| `bus_queries.py` | 核心查詢邏輯，包含站點查詢、直達路線、轉乘路徑、POI 查詢與推薦計算。 |
| `generate_convenience_store_data.py` | 從 OpenStreetMap / Overpass API 取得便利商店等 POI 資料，並產生整理後的 CSV。 |
| `routes.csv` | 原始公車路線資料。 |
| `routes_with_coordinates.csv` | 加入座標資訊後的公車路線資料。 |
| `generated_csv_260607/` | 已整理好的 CSV 資料集，供查詢程式使用。 |

## `generated_csv_260607/` 內容

| 檔案 | 用途 |
| --- | --- |
| `stops.csv` | 公車站點資料，包含站點 ID、站名、緯度、經度。 |
| `route_edges.csv` | 公車路線中相鄰站點的連接關係與預估行車時間。 |
| `pois.csv` | POI 地點資料，例如便利商店、餐飲或周邊地點。 |
| `poi_items.csv` | 商品或服務項目清單。 |
| `poi_item_mapping.csv` | POI 與商品的對應關係，包含價格與服務時間。 |
| `stop_poi_mapping.csv` | 公車站點與附近 POI 的對應關係，包含步行時間。 |
| `README_generated.md` | 自動產生資料集的欄位說明。 |

## 不公開檔案

以下內容不建議上傳到 GitHub，已經由 `.gitignore` 排除：

| 檔案或資料夾 | 不公開原因 |
| --- | --- |
| `暫放/` | 暫存資料、截圖、Excel 原始檔、舊版程式與舊資料庫，不適合放到公開專案。 |
| `__pycache__/` | Python 自動產生的快取檔，沒有公開價值。 |
| `*.log`、`streamlit*.out`、`streamlit*.err` | 執行紀錄，可能包含本機路徑、錯誤訊息或臨時輸出。 |
| `*.sqlite`、`*.db` | 本機資料庫檔，不易審查內容，公開風險較高。 |
| `.venv/` | 本機 Python 虛擬環境，不應上傳。 |
| `.idea/`、`.vscode/` | 個人編輯器設定，不屬於專題內容。 |
| `.env`、`.env.*`、`secrets.*`、`*.secret` | 可能包含 API key、密碼或私人設定，不能公開。 |
| `.agents/` | Codex 或本機工具產生的工作資料，不屬於專題內容。 |

## 和舊題目程式碼分開

目前父層資料夾 `D:\MyFirstProject` 裡還有其他練習與舊題目資料夾，例如 `datascience/`、`GenerateAI/`、`interestingcoding/`、`Javaprogramming/`、`machine/`、`stairs_homework/`、`transformer_homework/`。

這些不要和本專題一起公開。建議只把下面這個資料夾建立成新的 GitHub repository：

```text
D:\MyFirstProject\myproject
```

不要從父層 `D:\MyFirstProject` 執行：

```powershell
git add .
```

## 執行方式

安裝套件後，可以用 Streamlit 執行：

```powershell
streamlit run bus_query_app.py
```

如果要重新產生 POI 資料，可以執行：

```powershell
python generate_convenience_store_data.py
```

## 上傳 GitHub 前檢查

在 `D:\MyFirstProject\myproject` 裡執行：

```powershell
git status --short
git add --dry-run .
```

確認清單中沒有 `暫放/`、`__pycache__/`、log、SQLite、Excel、截圖或舊題目資料夾後，再正式 commit。

## 資料來源

本專題使用公車路線與站點資料，並透過 OpenStreetMap / Overpass API 取得部分 POI 資訊。若公開使用，建議在正式報告或展示中補上實際資料來源與授權說明。
