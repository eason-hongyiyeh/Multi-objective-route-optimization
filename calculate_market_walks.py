"""以 Valhalla 步行路網尋找 20 分鐘內最近的捷運站，時間按 1 m/s 換算。"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import time
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / 'data' / 'nightmarket.geojson'
STATIONS = ROOT / 'data' / 'mrt_station.geojson'
OUTPUT = ROOT / 'walking'
ENDPOINT = 'https://valhalla1.openstreetmap.de/route'
SPEED_MPS = 1
MAX_WALK_SECONDS = 20 * 60
SNAP_LIMIT_M = 150
def source_id(feature):
    return feature.get('id') or feature['properties']['@id']


def fingerprint(features):
    content = [(source_id(f), f['geometry']['coordinates'], f['properties']) for f in features]
    return hashlib.sha256(json.dumps(content, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def feature_name(feature):
    p = feature['properties']
    return p.get('name:zh-Hant') or p.get('name:zh') or p.get('name') or source_id(feature)


def distance(a, b):
    """大圓距離僅用於候選下界及檢查吸附偏移，不作為步行距離。"""
    lon1, lat1, lon2, lat2 = map(math.radians, (*a[:2], *b[:2]))
    value = math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2
    return 6371000 * 2 * math.asin(min(1, math.sqrt(value)))


def decode_shape(encoded):
    coordinates, index, lat, lon = [], 0, 0, 0
    while index < len(encoded):
        values = []
        for _ in range(2):
            value = shift = 0
            while True:
                part = ord(encoded[index]) - 63
                index += 1
                value |= (part & 31) << shift
                shift += 5
                if part < 32:
                    break
            values.append(~(value >> 1) if value & 1 else value >> 1)
        lat += values[0]
        lon += values[1]
        coordinates.append([lon / 1e6, lat / 1e6])
    return coordinates


class Router:
    def __init__(self, refresh=False):
        self.cache_dir = OUTPUT / '.cache'
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.refresh = refresh
        self.last_request = 0
        self.requests = 0

    def route(self, origin, target):
        a, b = origin['geometry']['coordinates'], target['geometry']['coordinates']
        payload = {
            'locations': [{'lat':c[1], 'lon':c[0], 'search_cutoff':SNAP_LIMIT_M} for c in (a,b)],
            'costing':'pedestrian',
            'costing_options':{'pedestrian':{'shortest':True, 'walking_speed':3.6, 'use_ferry':0}},
            'units':'kilometers',
        }
        encoded = json.dumps(payload, separators=(',', ':'))
        key = hashlib.sha256((ENDPOINT + encoded).encode()).hexdigest()
        cache = self.cache_dir / (key + '.json')
        if cache.exists() and not self.refresh:
            data = json.loads(cache.read_text(encoding='utf-8'))
        else:
            time.sleep(max(0, 1.1 - (time.monotonic() - self.last_request)))
            self.last_request = time.monotonic()
            request = Request(ENDPOINT + '?json=' + quote(encoded, safe=''),
                              headers={'User-Agent':'MrtNightMarketWalking/1.0 (local educational map)'})
            try:
                with urlopen(request, timeout=40) as response:
                    data = json.load(response)
            except HTTPError as error:
                raise RuntimeError(f'路由服務 HTTP {error.code}: {error.read().decode()}') from error
            cache.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
            self.requests += 1
        trip = data['trip']
        if trip.get('status') != 0:
            raise ValueError(f'無法取得步行路線：{data}')
        if trip.get('warnings'):
            raise ValueError(f'路由設定未被完整接受：{trip["warnings"]}')
        if trip['summary'].get('has_ferry'):
            raise ValueError(f'{feature_name(origin)} → {feature_name(target)} 路線包含渡輪，不能當作純步行')
        coordinates = decode_shape(trip['legs'][0]['shape'])
        offsets = [distance(a, coordinates[0]), distance(b, coordinates[-1])]
        if max(offsets) > SNAP_LIMIT_M:
            raise ValueError(f'路網吸附距離過大：{offsets}')
        if any(m['travel_mode'] != 'pedestrian' for leg in trip['legs'] for m in leg['maneuvers']):
            raise ValueError('回傳路線包含非步行交通方式')
        meters = round(trip['summary']['length'] * 1000)
        result = {'distance_m':meters, 'duration_s':meters / SPEED_MPS,
                  'geometry':{'type':'LineString', 'coordinates':coordinates}}
        if trip['summary'].get('has_time_restrictions'):
            result['note'] = '路徑含有時段限制的路段，請留意現場通行狀況。'
        return result



def calculate(features, stations, router):
    results = []
    for index, origin in enumerate(features):
        a = origin['geometry']['coordinates']
        candidates = sorted(stations,
                            key=lambda f:distance(a, f['geometry']['coordinates']))
        best = None
        evaluated = 0
        for target in candidates:
            # 扣除兩端最大吸附距離，加上 1% 球面誤差裕量；不是只查直線最近的一個。
            lower_bound = distance(a, target['geometry']['coordinates']) * .99 - 2 * SNAP_LIMIT_M
            limit_m = min(best['distance_m'] if best else math.inf, MAX_WALK_SECONDS * SPEED_MPS)
            if lower_bound > limit_m + 2:
                break
            route = router.route(origin, target)
            evaluated += 1
            if route['duration_s'] <= MAX_WALK_SECONDS and (best is None or route['distance_m'] < best['distance_m']):
                best = {**route, 'market_id':source_id(origin), 'station_id':source_id(target),
                        'station_name':feature_name(target), 'station_code':target['properties'].get('ref', '')}
        if best is None:
            print(f'{index+1}/{len(features)} {feature_name(origin)}：20 分鐘內沒有捷運站', flush=True)
            continue
        results.append(best)
        print(f'{index+1}/{len(features)} {feature_name(origin)} → {best["station_name"]} ({best["station_code"]}): '
              f'{best["distance_m"]} m, {best["duration_s"] / 60:.2f} min ({evaluated} candidates)', flush=True)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh', action='store_true', help='重新查詢路網，不使用本機回應快取')
    args = parser.parse_args()
    features = json.loads(INPUT.read_text(encoding='utf-8-sig'))['features']
    router = Router(args.refresh)
    stations = json.loads(STATIONS.read_text(encoding='utf-8-sig'))['features']
    stations = [f for f in stations if f['geometry']['type'] == 'Point'
                and (f['properties'].get('public_transport') == 'station'
                     or f['properties'].get('railway') == 'station')]
    if not stations:
        raise ValueError('找不到可比較的捷運站資料')
    results = calculate(features, stations, router)
    document = {'input_fingerprint':fingerprint(features + stations), 'speed_mps':SPEED_MPS,
                'max_duration_s':MAX_WALK_SECONDS, 'calculated_market_ids':[source_id(f) for f in features],
                'results':results}
    OUTPUT.mkdir(exist_ok=True)
    (OUTPUT / 'market_stations.json').write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'完成：{len(features)} 個起點中，{len(results)} 筆符合 20 分鐘上限，新增 {router.requests} 次路由查詢。')


if __name__ == '__main__':
    main()
