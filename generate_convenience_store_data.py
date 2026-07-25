import csv
import hashlib
import json
import math
import random
import urllib.parse
import urllib.request
from urllib.error import HTTPError, URLError
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parent / "generated_csv_20260607"
OVERPASS_URLS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
SEARCH_PADDING_DEGREES = 0.01
WALKING_SPEED_METERS_PER_MINUTE = 75

CORE_ITEM_IDS = {
    "I001",
    "I002",
    "I003",
    "I008",
    "I009",
    "I013",
    "I014",
    "I015",
    "I017",
    "I021",
    "I022",
}

BASE_PRICES = {
    "I001": 25,
    "I002": 39,
    "I003": 45,
    "I004": 79,
    "I005": 69,
    "I006": 35,
    "I007": 30,
    "I008": 13,
    "I009": 49,
    "I010": 50,
    "I011": 45,
    "I012": 39,
    "I013": 35,
    "I014": 45,
    "I015": 39,
    "I016": 129,
    "I017": 35,
    "I018": 20,
    "I019": 15,
    "I020": 49,
    "I021": 35,
    "I022": 35,
    "I023": 199,
    "I024": 89,
    "I025": 49,
    "I026": 59,
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def fetch_osm_stores(stops: list[dict[str, str]]) -> list[dict[str, object]]:
    latitudes = [float(stop["lat"]) for stop in stops]
    longitudes = [float(stop["lon"]) for stop in stops]
    bbox = (
        min(latitudes) - SEARCH_PADDING_DEGREES,
        min(longitudes) - SEARCH_PADDING_DEGREES,
        max(latitudes) + SEARCH_PADDING_DEGREES,
        max(longitudes) + SEARCH_PADDING_DEGREES,
    )
    query = f"""
[out:json][timeout:90];
(
  node["shop"="convenience"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
  way["shop"="convenience"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
  relation["shop"="convenience"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
);
out center tags;
"""
    payload = None
    errors = []
    for overpass_url in OVERPASS_URLS:
        request = urllib.request.Request(
            overpass_url,
            data=urllib.parse.urlencode({"data": query}).encode("utf-8"),
            headers={"User-Agent": "KaohsiungBusPOIPrototype/1.0"},
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                payload = json.load(response)
            break
        except (HTTPError, URLError, TimeoutError) as error:
            errors.append(f"{overpass_url}: {error}")
    if payload is None:
        raise RuntimeError("All Overpass endpoints failed: " + "; ".join(errors))

    stores = []
    seen_osm_keys = set()
    for element in payload.get("elements", []):
        osm_type = element.get("type")
        osm_id = element.get("id")
        osm_key = f"{osm_type}/{osm_id}"
        if osm_key in seen_osm_keys:
            continue
        seen_osm_keys.add(osm_key)

        latitude = element.get("lat") or element.get("center", {}).get("lat")
        longitude = element.get("lon") or element.get("center", {}).get("lon")
        if latitude is None or longitude is None:
            continue

        tags = element.get("tags", {})
        name = (
            tags.get("name:zh")
            or tags.get("name")
            or tags.get("brand")
            or tags.get("operator")
            or f"便利商店（OSM {osm_key}）"
        )
        address_parts = [
            tags.get("addr:city"),
            tags.get("addr:district"),
            tags.get("addr:street"),
            tags.get("addr:housenumber"),
        ]
        stores.append(
            {
                "osm_type": osm_type,
                "osm_id": str(osm_id),
                "osm_key": osm_key,
                "name": name.strip(),
                "address": "".join(part for part in address_parts if part),
                "lat": float(latitude),
                "lon": float(longitude),
            }
        )

    if not stores:
        raise RuntimeError("Overpass did not return any shop=convenience features.")
    return stores


def haversine_meters(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    earth_radius = 6_371_000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    value = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return 2 * earth_radius * math.atan2(math.sqrt(value), math.sqrt(1 - value))


def deterministic_rng(value: str) -> random.Random:
    seed = int.from_bytes(hashlib.sha256(value.encode("utf-8")).digest()[:8], "big")
    return random.Random(seed)


def adjusted_price(item_id: str, rng: random.Random) -> int:
    variation = rng.choice([-5, 0, 0, 0, 5, 10])
    return max(10, BASE_PRICES[item_id] + variation)


def main() -> None:
    stops = read_csv(DATA_DIR / "stops.csv")
    all_pois = read_csv(DATA_DIR / "pois.csv")
    base_pois = [
        row for row in all_pois if row["poi_type"].strip() != "便利商店"
    ]
    base_poi_ids = {row["poi_id"].strip() for row in base_pois}
    base_stop_links = [
        row
        for row in read_csv(DATA_DIR / "stop_poi_mapping.csv")
        if row["poi_id"].strip() in base_poi_ids
    ]
    base_item_links = [
        row
        for row in read_csv(DATA_DIR / "poi_item_mapping.csv")
        if row["poi_id"].strip() in base_poi_ids
    ]
    valid_item_ids = {
        row["item_id"].strip() for row in read_csv(DATA_DIR / "poi_items.csv")
    }
    optional_item_ids = sorted(valid_item_ids - CORE_ITEM_IDS)

    osm_stores = fetch_osm_stores(stops)
    nearest_store_by_stop = {}
    for stop in stops:
        stop_lat = float(stop["lat"])
        stop_lon = float(stop["lon"])
        nearest_store = min(
            osm_stores,
            key=lambda store: haversine_meters(
                stop_lat,
                stop_lon,
                store["lat"],
                store["lon"],
            ),
        )
        distance = haversine_meters(
            stop_lat,
            stop_lon,
            nearest_store["lat"],
            nearest_store["lon"],
        )
        nearest_store_by_stop[stop["stop_id"]] = (nearest_store, distance)

    selected_stores = {
        store["osm_key"]: store
        for store, _ in nearest_store_by_stop.values()
    }
    next_poi_number = max(int(row["poi_id"][1:]) for row in base_pois) + 1
    poi_id_by_osm_key = {
        osm_key: f"P{next_poi_number + index:03d}"
        for index, osm_key in enumerate(sorted(selected_stores))
    }

    store_pois = []
    for osm_key in sorted(selected_stores):
        store = selected_stores[osm_key]
        rating_rng = deterministic_rng(f"rating:{osm_key}")
        store_pois.append(
            {
                "poi_id": poi_id_by_osm_key[osm_key],
                "poi_name": store["name"],
                "poi_type": "便利商店",
                "rating": f"{rating_rng.uniform(3.6, 4.8):.1f}",
                "lat": f"{store['lat']:.7f}",
                "lon": f"{store['lon']:.7f}",
                "osm_type": store["osm_type"],
                "osm_id": store["osm_id"],
                "address": store["address"],
                "source": f"https://www.openstreetmap.org/{osm_key}",
            }
        )

    poi_rows = []
    for poi in base_pois:
        poi_rows.append(
            {
                "poi_id": poi["poi_id"],
                "poi_name": poi["poi_name"],
                "poi_type": poi["poi_type"],
                "rating": poi["rating"],
                "lat": poi["lat"],
                "lon": poi["lon"],
                "osm_type": poi.get("osm_type", ""),
                "osm_id": poi.get("osm_id", ""),
                "address": poi.get("address", ""),
                "source": poi.get("source", ""),
            }
        )
    poi_rows.extend(store_pois)

    stop_link_rows = list(base_stop_links)
    for stop in stops:
        store, distance = nearest_store_by_stop[stop["stop_id"]]
        stop_link_rows.append(
            {
                "stop_id": stop["stop_id"],
                "poi_id": poi_id_by_osm_key[store["osm_key"]],
                "walking_time_min": max(
                    1,
                    math.ceil(distance / WALKING_SPEED_METERS_PER_MINUTE),
                ),
            }
        )

    item_link_rows = list(base_item_links)
    for osm_key in sorted(selected_stores):
        poi_id = poi_id_by_osm_key[osm_key]
        inventory_rng = deterministic_rng(f"inventory:{osm_key}")
        extra_count = min(inventory_rng.randint(6, 11), len(optional_item_ids))
        item_ids = CORE_ITEM_IDS | set(
            inventory_rng.sample(optional_item_ids, extra_count)
        )
        for item_id in sorted(item_ids):
            item_link_rows.append(
                {
                    "poi_id": poi_id,
                    "item_id": item_id,
                    "price": adjusted_price(item_id, inventory_rng),
                    "service_time_min": inventory_rng.randint(3, 10),
                }
            )

    write_csv(
        DATA_DIR / "pois.csv",
        [
            "poi_id",
            "poi_name",
            "poi_type",
            "rating",
            "lat",
            "lon",
            "osm_type",
            "osm_id",
            "address",
            "source",
        ],
        poi_rows,
    )
    write_csv(
        DATA_DIR / "stop_poi_mapping.csv",
        ["stop_id", "poi_id", "walking_time_min"],
        stop_link_rows,
    )
    write_csv(
        DATA_DIR / "poi_item_mapping.csv",
        ["poi_id", "item_id", "price", "service_time_min"],
        item_link_rows,
    )

    print(
        f"Fetched {len(osm_stores)} OSM convenience stores; "
        f"selected {len(selected_stores)} unique stores for {len(stops)} stops."
    )


if __name__ == "__main__":
    main()
