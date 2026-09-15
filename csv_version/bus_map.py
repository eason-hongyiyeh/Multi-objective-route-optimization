"""Map the coordinates in the CSV files without replacing or geocoding them."""
import csv
import math
import json
from pathlib import Path

import streamlit as st

try:
    from .generate_convenience_store_data import stop_coordinate_status
except ImportError:
    from generate_convenience_store_data import stop_coordinate_status

DATA_DIR = Path(__file__).resolve().parent / "generated_csv_260607"


def load_map_points(data_dir=DATA_DIR):
    points = []
    for filename, kind, id_field, name_field, color in (
        ("stops.csv", "站牌", "stop_id", "stop_name", [37, 99, 235, 235]),
        ("pois.csv", "便利商店", "poi_id", "poi_name", [5, 150, 105, 245]),
    ):
        with (data_dir / filename).open(encoding="utf-8-sig", newline="") as file:
            for row in csv.DictReader(file):
                lat, lon = float(row["lat"]), float(row["lon"])
                if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
                    raise ValueError(f"{filename}: {row[id_field]} 座標無效，請先修正資料")
                points.append(dict(
                    id=row[id_field], name=row[name_field], kind=kind, lat=lat, lon=lon,
                    color=color, title=f"{row[id_field]}｜{row[name_field]}",
                    address=row.get("address") or "未提供地址",
                    coordinate_source=("使用者提供的更正座標，尚未核對官方站位"
                                       if stop_coordinate_status(row, data_dir) == "user_provided_not_officially_verified"
                                       else "專案既有站牌座標，尚未核對官方站位")
                                      if kind == "站牌" else "OpenStreetMap 地圖紀錄，尚未現場核實",
                    source=row.get("source", ""), fetched_at=row.get("fetched_at", ""),
                ))
    return points


def map_payload(points, *, show_stops=True, show_stores=True, show_radius=False, show_labels=True):
    return dict(
        points=[p for p in points if (p["kind"] == "站牌" and show_stops) or (p["kind"] == "便利商店" and show_stores)],
        radius_centres=[p for p in points if p["kind"] == "站牌"] if show_radius and show_stops else [],
        radius_m=100, show_labels=show_labels, bounds=[[p["lat"], p["lon"]] for p in points],
    )


def build_map(points, **options):
    # Protect the JSON script boundary; popup content is also rendered via textContent.
    payload = json.dumps(map_payload(points, **options), ensure_ascii=False).replace("<", "\\u003c")
    template = """<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
 integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin="">
<style>
html,body {margin:0;font-family:Arial,"Microsoft JhengHei",sans-serif}
#map {height:610px;width:100%;border-radius:8px}
.map-label {font-size:12px;font-weight:600;white-space:nowrap;text-shadow:0 0 3px white,0 0 3px white}
.place-details {white-space:pre-line;font-size:13px;line-height:1.6}
#status {position:absolute;top:8px;left:55px;z-index:1000;background:white;padding:5px}
</style></head><body><div id="map" aria-label="站牌與便利商店地圖"></div><div id="status">載入街道底圖…</div>
<script id="map-data" type="application/json">__MAP_DATA__</script>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
 integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
<script>
const status = document.getElementById("status");
if (!window.L) {
  status.textContent = "地圖元件載入失敗，請確認網路可連線至 unpkg.com。";
} else {
  const data = JSON.parse(document.getElementById("map-data").textContent);
  const map = L.map("map");
  if (data.bounds.length) map.fitBounds(data.bounds, {padding:[45,45],maxZoom:15});
  else map.setView([22.64,120.30],13);
  const tiles = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom:19,
    attribution:'&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors'
  }).addTo(map);
  let tileFailed = false;
  tiles.on("load", () => {if (!tileFailed) status.style.display="none";});
  tiles.on("tileerror", () => {tileFailed=true;status.style.display="block";status.textContent="部分底圖載入失敗；標記仍依 CSV 座標顯示。";});
  data.radius_centres.forEach(p => L.circle([p.lat,p.lon], {
    radius:data.radius_m,color:"#2563eb",weight:1,fillOpacity:0.06,interactive:false,className:"stop-radius"
  }).addTo(map));
  data.points.forEach(p => {
    const color = p.kind === "站牌" ? "#2563eb" : "#059669";
    const details = document.createElement("div");
    details.className="place-details";
    details.textContent=p.title+"\\n"+p.kind+"｜"+p.lat+", "+p.lon+"\\n"+p.address+"\\n"+p.coordinate_source;
    const marker = L.circleMarker([p.lat,p.lon], {
      radius:6,color:"white",weight:1.5,fillColor:color,fillOpacity:1,className:"location-marker"
    }).addTo(map).bindTooltip(details).bindPopup(details.cloneNode(true));
    marker.getElement().dataset.locationId=p.id;
    if (data.show_labels) {
      const label = document.createElement("span");
      label.textContent=p.id; label.style.color=color;
      L.marker([p.lat,p.lon], {
        icon:L.divIcon({className:"map-label",html:label.outerHTML,iconSize:[50,18],iconAnchor:[-8,18]}),
        interactive:false,keyboard:false
      }).addTo(map);
    }
  });
  L.control.scale({imperial:false}).addTo(map);
  new ResizeObserver(() => map.invalidateSize()).observe(document.getElementById("map"));
}
</script></body></html>"""
    return template.replace("__MAP_DATA__", payload)


def render_map():
    st.subheader("站牌與便利商店位置")
    st.caption("藍色 S：站牌　｜　綠色 P：便利商店。拖曳可移動、滾輪可縮放，滑鼠停在圓點上可看名稱與座標。")
    try:
        points = load_map_points()
    except (OSError, ValueError, KeyError) as error:
        st.error(f"無法載入地圖資料：{error}")
        return
    stops = [p for p in points if p["kind"] == "站牌"]
    stores = [p for p in points if p["kind"] == "便利商店"]
    st.caption(f"資料共 {len(stops)} 個站牌、{len(stores)} 家便利商店；位置直接取自資料檔的經緯度。")
    controls = st.columns(4)
    show_stops = controls[0].checkbox("顯示站牌", value=True, key="map_show_stops")
    show_stores = controls[1].checkbox("顯示便利商店", value=True, key="map_show_stores")
    show_radius = controls[2].checkbox("顯示站牌 100 公尺範圍", key="map_show_radius")
    show_labels = controls[3].checkbox("顯示編號", value=True, key="map_show_labels")
    st.iframe(build_map(points, show_stops=show_stops, show_stores=show_stores,
                        show_radius=show_radius, show_labels=show_labels), height=620)
    st.info("店家位置來自 OSM 紀錄；站牌採專案既有座標及使用者提供的更正，尚未核對官方站位。地圖呈現目前資料的位置，不能保證店家仍營業、入口正確或沒有漏店。")
    st.caption("100 公尺圓圈表示直線範圍，不是步行路線。底圖使用 OpenStreetMap，地圖元件與街道底圖需要網路連線。© OpenStreetMap contributors。")
    with st.expander("查看便利商店座標與原始來源"):
        st.dataframe(
            [{"編號": p["id"], "名稱": p["name"], "緯度": p["lat"], "經度": p["lon"],
              "地址": p["address"], "來源": p["source"], "資料下載時間（UTC）": p["fetched_at"]} for p in stores],
            hide_index=True, width="stretch",
            column_config={"來源": st.column_config.LinkColumn("OSM 來源", display_text="查看原始地圖")},
        )
    st.markdown("[OpenStreetMap 資料授權](https://www.openstreetmap.org/copyright) · [回報地圖問題](https://www.openstreetmap.org/fixthemap)")
