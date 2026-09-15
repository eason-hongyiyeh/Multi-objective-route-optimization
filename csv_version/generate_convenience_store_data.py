"""Refresh OSM convenience stores within 100 m; preserve sources and unknown values."""
import argparse
import csv
import json
import math
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "generated_csv_260607"
SOURCE_DIR = DATA_DIR / "sources"
RADIUS_M = 100
OVERPASS_URLS = ["https://overpass.private.coffee/api/interpreter",
                 "https://overpass-api.de/api/interpreter",
                 "https://maps.mail.ru/osm/tools/overpass/api/interpreter"]
ROUTER = "https://routing.openstreetmap.de/routed-foot/route/v1/foot/"
ITEMS = {"I001": "瓶裝水", "I002": "飯糰", "I003": "餅乾", "I004": "堅果",
         "I008": "茶葉蛋", "I009": "三明治", "I010": "口罩", "I011": "OK繃",
         "I013": "衛生紙", "I014": "咖啡", "I015": "泡麵", "I017": "瓶裝飲料",
         "I021": "糖果", "I022": "牛奶", "I023": "雨傘", "I024": "電池",
         "I025": "牙刷", "I027": "便當", "I028": "麵包", "I029": "優格",
         "I030": "冰淇淋", "I031": "關東煮"}


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def write_csv(path, fields, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def haversine_meters(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 2 * 6_371_000 * math.asin(math.sqrt(min(1, max(0, a))))


def download(url):
    request = urllib.request.Request(url, headers={"User-Agent": "KaohsiungBusPOIResearch/1.0"})
    with urllib.request.urlopen(request, timeout=50) as response:
        data = json.load(response)
    return {"fetched_at": datetime.now(timezone.utc).isoformat(), "url": url, "response": data}


def save_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fetch_osm(stops):
    bbox = (min(float(s["lat"]) for s in stops) - .002,
            min(float(s["lon"]) for s in stops) - .002,
            max(float(s["lat"]) for s in stops) + .002,
            max(float(s["lon"]) for s in stops) + .002)
    query = '[out:json][timeout:35];nwr["shop"="convenience"](%s);out center tags;' % ",".join(map(str, bbox))
    errors = []
    for endpoint in OVERPASS_URLS:
        try:
            data = download(endpoint + "?" + urllib.parse.urlencode({"data": query}))
            if data["response"].get("remark") or not data["response"].get("elements"):
                raise ValueError("Incomplete or empty Overpass response")
            data["query"] = query
            save_json(SOURCE_DIR / "osm_convenience.json", data)
            return data
        except (OSError, ValueError) as error:
            print(f"Overpass failed: {endpoint}: {error}", flush=True)
            errors.append(str(error))
    raise RuntimeError("Unable to refresh OSM: " + "; ".join(errors))


def select_stores(stops, payload):
    stores, excluded = {}, []
    for element in payload["response"]["elements"]:
        tags = element.get("tags", {})
        key = f"{element['type']}/{element['id']}"
        name = tags.get("name:zh") or tags.get("name") or tags.get("brand") or ""
        identity = " ".join(str(v) for v in tags.values()).lower()
        reason = ""
        if any(word in identity for word in ("蝦皮", "shopee", "福利社", "台灣菸酒", "臺灣菸酒")):
            reason = "非本次一般便利商店範圍"
        elif tags.get("access") in ("private", "no"):
            reason = "非對外開放"
        elif tags.get("disused") == "yes" or tags.get("abandoned") == "yes":
            reason = "已標示停用"
        elif not name:
            reason = "缺少店名，待確認"
        pos = element if "lat" in element else element.get("center", {})
        if not pos:
            reason = "缺少座標"
        if reason:
            excluded.append(dict(osm_key=key, name=name, reason=reason))
            continue
        distances = [(s["stop_id"], haversine_meters(float(s["lat"]), float(s["lon"]), pos["lat"], pos["lon"])) for s in stops]
        links = [(sid, distance) for sid, distance in distances if distance <= RADIUS_M]
        if not links:
            continue
        branch = tags.get("branch") or ""
        if branch and branch not in name:
            name += " " + branch
        stores[key] = dict(name=name, lat=pos["lat"], lon=pos["lon"], links=links,
                          address=tags.get("addr:full") or "".join(tags.get(k, "") for k in ("addr:city", "addr:district", "addr:street", "addr:housenumber")))
    return stores, excluded


def walking_url(stop, store):
    return ROUTER + f"{stop['lon']},{stop['lat']};{store['lon']},{store['lat']}?overview=full&geometries=geojson&steps=false"


def walking_values(envelope, straight_distance_m=0):
    data = envelope["response"]
    if data.get("code") != "Ok" or not data.get("routes"):
        return {"time_status": "routing_failed"}
    route = data["routes"][0]
    snaps = [point["distance"] for point in data["waypoints"]]
    result = dict(route_distance_m=round(route["distance"], 2), route_duration_s=round(route["duration"], 2),
                  start_snap_m=round(snaps[0], 2), end_snap_m=round(snaps[1], 2))
    # Remote road points are not verified shop entrances; never invent an access path.
    if (max(snaps) > 30 or route["distance"] <= 0 or route["duration"] <= 0
            or route["distance"] + .01 < straight_distance_m):
        return result | {"time_status": "endpoint_needs_review"}
    return result | {"walking_time_min": math.ceil(route["duration"] / 60), "time_status": "road_network_estimate"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch-osm", action="store_true")
    parser.add_argument("--fetch-walking", action="store_true")
    parser.add_argument("--sources-only", action="store_true")
    parser.add_argument("--renumber-pois", action="store_true", help="Renumber this snapshot from P001 and rebuild both link tables")
    parser.add_argument("--walking-mode", choices=("road", "unknown"), default="road")
    args = parser.parse_args()
    SOURCE_DIR.mkdir(exist_ok=True)
    stops = read_csv(DATA_DIR / "stops.csv")
    payload = fetch_osm(stops) if args.fetch_osm else json.loads((SOURCE_DIR / "osm_convenience.json").read_text(encoding="utf-8"))
    if args.sources_only:
        print(f"OSM features: {len(payload['response']['elements'])}")
        return
    stores, excluded = select_stores(stops, payload)
    stop_by_id = {s["stop_id"]: s for s in stops}
    old_pois = read_csv(DATA_DIR / "pois.csv")
    old_ids = {f"{p['osm_type']}/{p['osm_id']}": p["poi_id"] for p in old_pois if p.get("osm_id")}
    next_id = max([int(p["poi_id"][1:]) for p in old_pois] + [0]) + 1
    if args.renumber_pois:
        ordered_keys = sorted(stores, key=lambda key: (int(old_ids.get(key, "P999999999")[1:]), key))
        old_ids = {key: f"P{index:03d}" for index, key in enumerate(ordered_keys, 1)}
        next_id = len(old_ids) + 1
    cache_path = SOURCE_DIR / "walking_routes.json"
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    pois, links, inventory = [], [], []
    for key, store in sorted(stores.items()):
        poi_id = old_ids.get(key)
        if poi_id is None:
            poi_id = f"P{next_id:03d}"
            next_id += 1
        osm_type, osm_id = key.split("/")
        pois.append(dict(poi_id=poi_id, poi_name=store["name"], poi_type="便利商店", rating="",
                         lat=store["lat"], lon=store["lon"], osm_type=osm_type, osm_id=osm_id,
                         address=store["address"], source="https://www.openstreetmap.org/" + key,
                         fetched_at=payload["fetched_at"], verification_status="osm_record_not_field_verified"))
        for sid, distance in store["links"]:
            link = dict(stop_id=sid, poi_id=poi_id, walking_time_min="", straight_distance_m=round(distance, 3),
                        route_distance_m="", route_duration_s="", start_snap_m="", end_snap_m="",
                        time_status="not_measured", source="", fetched_at="")
            if args.walking_mode == "road":
                url = walking_url(stop_by_id[sid], store)
                if url not in cache and args.fetch_walking:
                    try:
                        print(f"Walking: {sid} -> {poi_id}", flush=True)
                        cache[url] = download(url)
                        save_json(cache_path, cache)
                    except (OSError, ValueError) as error:
                        print(f"Walking lookup failed: {error}", flush=True)
                    finally:
                        time.sleep(1.1)
                if url in cache:
                    link.update(walking_values(cache[url], distance))
                    link.update(source=url, fetched_at=cache[url]["fetched_at"])
                else:
                    link["time_status"] = "routing_unavailable"
            links.append(link)
        for item_id in ITEMS:
            inventory.append(dict(poi_id=poi_id, item_id=item_id, price="", service_time_min="", availability_status="typical_assortment_unverified"))
    write_csv(DATA_DIR / "pois.csv", ["poi_id", "poi_name", "poi_type", "rating", "lat", "lon", "osm_type", "osm_id", "address", "source", "fetched_at", "verification_status"], sorted(pois, key=lambda r: r["poi_id"]))
    write_csv(DATA_DIR / "poi_items.csv", ["item_id", "item_name"], [dict(item_id=k, item_name=v) for k, v in ITEMS.items()])
    write_csv(DATA_DIR / "poi_item_mapping.csv", ["poi_id", "item_id", "price", "service_time_min", "availability_status"], sorted(inventory, key=lambda r: (r["poi_id"], r["item_id"])))
    write_csv(DATA_DIR / "stop_poi_mapping.csv", ["stop_id", "poi_id", "walking_time_min", "straight_distance_m", "route_distance_m", "route_duration_s", "start_snap_m", "end_snap_m", "time_status", "source", "fetched_at"], sorted(links, key=lambda r: (r["stop_id"], r["poi_id"])))
    coverage = [dict(stop_id=s["stop_id"], stop_name=s["stop_name"], store_count=sum(r["stop_id"] == s["stop_id"] for r in links), coordinate_status="legacy_coordinates_unverified", completeness="osm_snapshot_only") for s in stops]
    write_csv(DATA_DIR / "stop_store_coverage.csv", ["stop_id", "stop_name", "store_count", "coordinate_status", "completeness"], coverage)
    save_json(SOURCE_DIR / "excluded_osm_features.json", excluded)
    print(f"Selected {len(pois)} stores; {len(links)} stop/store links; {sum(r['store_count'] == 0 for r in coverage)} stops without a mapped store within 100 m.")


if __name__ == "__main__":
    main()
