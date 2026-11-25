"""讀取 data/ 與 imports/ 最新候選資料，啟動本機互動地圖。"""
import argparse
from collections import Counter
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
from urllib.parse import parse_qs, quote, urlsplit
import webbrowser
from calculate_market_walks import fingerprint, MAX_WALK_SECONDS
from route_planner import QueryError, RoutePlanner
from itinerary_planner import ItineraryPlanner


ROOT = Path(__file__).resolve().parent
ATTRACTION_FILE = 'AttractionList_with_fee_and_hours.json'
POINT_LIST_FILES = {
    ATTRACTION_FILE: ('Attractions', 'AttractionID'),
    'HotelList.json': ('Hotels', 'HotelID'),
    'RestaurantList.json': ('Restaurants', 'RestaurantID'),
    'AttractionCandidates.json': ('Attractions', 'AttractionID'),
    'RestaurantCandidates.json': ('Restaurants', 'RestaurantID'),
}
CANDIDATE_GROUPS = {
    'AttractionCandidates.json': 'import_attractions',
    'RestaurantCandidates.json': 'import_restaurants',
}
HIDDEN_DATA_FILES = set()
TITLES = {
    'mrt_tracks.geojson': '捷運路線與路線節點',
    'mrt_station.geojson': '捷運車站與站名',
    'airportmrt.geojson': '機場捷運路線、軌道與停靠點',
    'nightmarket.geojson': '夜市',
    'mrt_exits.geojson': '捷運出入口',
    'airport_mrt_exits.geojson': '機場捷運出入口',
    ATTRACTION_FILE: '景點',
    'HotelList.json': '飯店／旅宿',
    'RestaurantList.json': '餐廳',
    'AttractionCandidates.json': '下載景點（待核對）',
    'RestaurantCandidates.json': '下載餐廳（待核對）',
}
COLORS = ('#247a9a', '#8851b0', '#008675', '#b27a1d', '#d1495b')
LAYER_COLORS = {
    'mrt_station.geojson': '#273f4f',
    'airportmrt.geojson': '#8851b0',
    'mrt_tracks.geojson': '#b27a1d',
    'nightmarket.geojson': '#B42365',
    'mrt_exits.geojson': '#0075BE',
    'airport_mrt_exits.geojson': '#8851B0',
    ATTRACTION_FILE: '#0F766E',
    'HotelList.json': '#4F46E5',
    'RestaurantList.json': '#EA580C',
    'AttractionCandidates.json': '#0F766E',
    'RestaurantCandidates.json': '#EA580C',
}
# 衍生出口檔保留供資料作業使用，避免與原始出口在一般地圖重複繪製。
DERIVED_EXIT_FILES = {'mrt_exits_clean.geojson', 'airport_mrt_exits_clean.geojson',
                      'mrt_exits_with_station.geojson'}


def valid_geometry(geometry):
    """驗證 WGS84 經度、緯度及幾何結構，不改寫原始座標。"""
    def point(value):
        return (isinstance(value, list) and len(value) >= 2
                and all(isinstance(v, (int, float)) and not isinstance(v, bool)
                        and math.isfinite(v) for v in value)
                and -180 <= value[0] <= 180 and -90 <= value[1] <= 90)

    def line(value):
        return isinstance(value, list) and len(value) >= 2 and all(point(p) for p in value)

    def polygon(value):
        return (isinstance(value, list) and bool(value)
                and all(line(ring) and len(ring) >= 4 and ring[0] == ring[-1] for ring in value))

    if not isinstance(geometry, dict):
        return False
    kind, coordinates = geometry.get('type'), geometry.get('coordinates')
    checks = {'Point': point, 'LineString': line, 'Polygon': polygon}
    if kind in checks:
        return checks[kind](coordinates)
    multi = {'MultiPoint': point, 'MultiLineString': line, 'MultiPolygon': polygon}
    if kind in multi:
        return (isinstance(coordinates, list) and bool(coordinates)
                and all(multi[kind](part) for part in coordinates))
    if kind == 'GeometryCollection':
        parts = geometry.get('geometries')
        return isinstance(parts, list) and bool(parts) and all(valid_geometry(p) for p in parts)
    return False


def load_geojson(path):
    with Path(path).open(encoding='utf-8-sig') as handle:
        source = json.load(handle)
    return filter_geojson(source)


def load_point_list(path):
    """將景點、旅宿或餐廳清單轉成點位，保留原欄位，不改寫來源檔。"""
    path = Path(path)
    array_name, id_field = POINT_LIST_FILES[path.name]
    with Path(path).open(encoding='utf-8-sig') as handle:
        source = json.load(handle)
    if not isinstance(source, dict) or not isinstance(source.get(array_name), list):
        raise ValueError(f'{TITLES[path.name]} JSON 需要包含 {array_name} 陣列。')
    features = []
    for record in source[array_name]:
        if not isinstance(record, dict):
            features.append(None)
            continue
        lat, lon = record.get('PositionLat'), record.get('PositionLon')
        geometry = None if lat is None or lon is None else {
            'type': 'Point', 'coordinates': [lon, lat]}
        features.append({'type': 'Feature', 'id': record.get(id_field),
                         'properties': record, 'geometry': geometry})
    return filter_geojson({'type': 'FeatureCollection', 'features': features})


def filter_geojson(source):
    if (not isinstance(source, dict) or source.get('type') != 'FeatureCollection'
            or not isinstance(source.get('features'), list)):
        raise ValueError('需要 GeoJSON FeatureCollection 格式。')
    crs = source.get('crs')
    if crs is not None:
        props = crs.get('properties') if isinstance(crs, dict) else None
        name = str(props.get('name', '')) if isinstance(props, dict) else ''
        if not name.upper().endswith(('CRS84', '4326')):
            raise ValueError('座標系統需為 WGS84 經緯度（CRS84 / EPSG:4326）。')
    kept = []
    counts = {'total': len(source['features']), 'missing_geometry': 0,
              'invalid_geometry': 0, 'displayed': 0}
    for feature in source['features']:
        if not isinstance(feature, dict) or feature.get('type') != 'Feature':
            counts['invalid_geometry'] += 1
            continue
        geometry = feature.get('geometry')
        if geometry is None:
            counts['missing_geometry'] += 1
        elif (not valid_geometry(geometry)
              or not isinstance(feature.get('properties', {}), (dict, type(None)))):
            counts['invalid_geometry'] += 1
        else:
            kept.append(feature)
    counts['displayed'] = len(kept)
    counts['geometry_types'] = dict(Counter(f['geometry']['type'] for f in kept))
    return {**source, 'features': kept}, counts


def latest_candidate_paths(imports_dir):
    imports_dir = Path(imports_dir).resolve()
    for folder in sorted(imports_dir.glob('taipei_places_*'), reverse=True):
        paths = [folder / filename for filename in CANDIDATE_GROUPS]
        if folder.is_dir() and all(p.is_file() and p.resolve().is_relative_to(imports_dir) for p in paths):
            return paths
    return []


def build_resources(data_dir=ROOT / 'data', imports_dir=ROOT / 'imports'):
    data_dir = Path(data_dir).resolve()
    if not data_dir.is_dir():
        raise ValueError(f'找不到資料夾：{data_dir}')
    resources, layers = {}, []
    paths = sorted(p for p in data_dir.rglob('*')
                   if p.is_file() and (p.suffix.lower() == '.geojson' or p.name in POINT_LIST_FILES)
                   and p.name not in HIDDEN_DATA_FILES
                   and p.resolve().is_relative_to(data_dir))
    sources = [(path, data_dir, '/data/') for path in paths]
    sources.extend((path, Path(imports_dir).resolve(), '/imports/')
                   for path in latest_candidate_paths(imports_dir))
    point_ids = set()
    for index, (path, base, prefix) in enumerate(sources):
        relative = path.relative_to(base).as_posix()
        info = {'id': ('imports/' if prefix == '/imports/' else '') + relative,
                'name': TITLES.get(path.name, path.stem),
                'url': prefix + quote(relative, safe='/'),
                'color': LAYER_COLORS.get(path.name, COLORS[index % len(COLORS)])}
        if path.name in CANDIDATE_GROUPS:
            info['candidate_group'] = CANDIDATE_GROUPS[path.name]
        try:
            loader = load_point_list if path.name in POINT_LIST_FILES else load_geojson
            data, counts = loader(path)
            if info.get('candidate_group'):
                unique = []
                for feature in data['features']:
                    if feature.get('id') and feature['id'] in point_ids:
                        continue
                    unique.append(feature)
                    if feature.get('id'):
                        point_ids.add(feature['id'])
                counts['duplicate_existing'] = len(data['features']) - len(unique)
                data['features'] = unique
                counts['displayed'] = len(unique)
                counts['geometry_types'] = dict(Counter(f['geometry']['type'] for f in unique))
            elif path.name in POINT_LIST_FILES:
                point_ids.update(f['id'] for f in data['features'] if f.get('id'))
            resources[info['url']] = json.dumps(data, ensure_ascii=False, allow_nan=False).encode('utf-8')
            info.update(counts, error=None)
        except (OSError, UnicodeError, ValueError, RecursionError) as error:
            info.update(error=str(error), total=0, displayed=0, missing_geometry=0, invalid_geometry=0)
        if path.name.lower() not in DERIVED_EXIT_FILES:
            layers.append(info)
    resources['/layers.json'] = json.dumps({'layers': layers}, ensure_ascii=False).encode('utf-8')
    walks = {'results': [], 'status': '步行資料尚未建立。'}
    walking_path = ROOT / 'walking' / 'market_stations.json'
    if walking_path.exists():
        try:
            document = json.loads(walking_path.read_text(encoding='utf-8'))
            markets = json.loads(resources['/data/nightmarket.geojson'])['features']
            stations = json.loads(resources['/data/mrt_station.geojson'])['features']
            stations = [f for f in stations if f['geometry']['type'] == 'Point'
                        and (f['properties'].get('public_transport') == 'station'
                             or f['properties'].get('railway') == 'station')]
            if (document['input_fingerprint'] == fingerprint(markets + stations)
                    and document.get('max_duration_s') == MAX_WALK_SECONDS):
                walks = {**document, 'results': [row for row in document['results']
                         if 0 <= row['duration_s'] <= MAX_WALK_SECONDS], 'status': ''}
            else:
                walks['status'] = '夜市、捷運站資料或步行條件已更新，請重新計算步行路徑。'
        except (OSError, ValueError, KeyError, TypeError):
            walks['status'] = '步行資料無法讀取，請重新計算。'
    resources['/night-market-walks.json'] = json.dumps(walks, ensure_ascii=False).encode('utf-8')
    return resources


class MapHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, resources, planner=None, recommender=None, **kwargs):
        self.resources = resources
        self.planner = planner
        self.recommender = recommender
        super().__init__(*args, **kwargs)

    def do_GET(self):
        request = urlsplit(self.path)
        path = request.path
        if path == '/api/itinerary':
            if self.recommender is None:
                self.send_json({'error': '推薦資料尚未成功載入。'}, 503)
                return
            try:
                if len(self.path) > 4096:
                    raise QueryError('查詢內容過長。')
                params = parse_qs(request.query, keep_blank_values=True, max_num_fields=12)
                if any(len(values) != 1 for values in params.values()):
                    raise QueryError('查詢參數不得重複。')
                result = self.recommender.recommend({key: values[0] for key, values in params.items()})
            except (QueryError, ValueError) as error:
                self.send_json({'error': str(error)}, 400)
            else:
                self.send_json(result)
            return
        if path == '/api/route':
            if self.planner is None:
                self.send_json({'error': '捷運 CSV 尚未成功載入，請檢查查詢區的資料訊息。'}, 503)
                return
            try:
                if len(self.path) > 2048:
                    raise QueryError('查詢內容過長。')
                params = parse_qs(request.query, keep_blank_values=True, max_num_fields=10)
                if any(len(values) != 1 for values in params.values()):
                    raise QueryError('查詢參數不得重複。')
                values = {key: rows[0] for key, rows in params.items()}
                if values.get('holiday', '0') not in ('0', '1'):
                    raise QueryError('假日設定無效。')
                result = self.planner.query(values.get('origin', ''), values.get('destination', ''),
                                            values.get('departure_at', ''), values.get('holiday') == '1',
                                            fare_mode=values.get('fare_mode', 'full_fare'))
            except (QueryError, ValueError) as error:
                self.send_json({'error': str(error)}, 400)
            else:
                self.send_json(result)
            return
        if path in ('/', '/map.html'):
            content, mime = (ROOT / 'map.html').read_bytes(), 'text/html; charset=utf-8'
        elif path == '/route_query.js':
            content, mime = (ROOT / 'route_query.js').read_bytes(), 'text/javascript; charset=utf-8'
        elif path == '/itinerary_query.js':
            content, mime = (ROOT / 'itinerary_query.js').read_bytes(), 'text/javascript; charset=utf-8'
        elif path in self.resources:
            content, mime = self.resources[path], 'application/json; charset=utf-8'
        else:
            self.send_error(404)
            return
        self.send_content(content, mime)

    def send_json(self, value, status=200):
        self.send_content(json.dumps(value, ensure_ascii=False, allow_nan=False).encode('utf-8'),
                          'application/json; charset=utf-8', status)

    def send_content(self, content, mime, status=200):
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(content)))
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, *_args):
        pass


def make_server(port=8765, data_dir=ROOT / 'data', csv_dir=ROOT / 'mrt_excel'):
    resources = build_resources(data_dir)
    planner = None
    try:
        planner = RoutePlanner(csv_dir)
        catalog = planner.catalog()
    except (OSError, ValueError, KeyError) as error:
        catalog = {'error': f'捷運 CSV 讀取失敗：{error}'}
    resources['/api/stations'] = json.dumps(catalog, ensure_ascii=False).encode('utf-8')
    recommender = None
    try:
        if planner is not None:
            recommender = ItineraryPlanner(planner, resources)
        recommendation_catalog = recommender.catalog() if recommender else {'error': '捷運 CSV 尚未成功載入。'}
    except (OSError, ValueError, KeyError) as error:
        recommendation_catalog = {'error': f'推薦資料讀取失敗：{error}'}
    resources['/api/itinerary-options'] = json.dumps(recommendation_catalog, ensure_ascii=False).encode('utf-8')
    return ThreadingHTTPServer(('127.0.0.1', port),
                              partial(MapHandler, resources=resources, planner=planner, recommender=recommender))


def main(argv=None):
    parser = argparse.ArgumentParser(description='將 data/ 裡的捷運、夜市、景點與餐廳顯示在地圖上。')
    parser.add_argument('--port', type=int, default=8765, help='本機連接埠（預設 8765；0 為自動選擇）')
    parser.add_argument('--no-browser', action='store_true', help='只啟動服務，不自動開啟瀏覽器')
    args = parser.parse_args(argv)
    if not 0 <= args.port <= 65535:
        parser.error('--port 須介於 0 與 65535。')
    try:
        server = make_server(args.port)
    except (OSError, ValueError) as error:
        print(f'無法啟動地圖：{error}；若連接埠被占用，可加上 --port 0。')
        return 1
    url = f'http://127.0.0.1:{server.server_port}/'
    print(f'捷運資料地圖：{url}', flush=True)
    print('地圖資料來自 data/ 與 imports/ 最新候選，捷運查詢來自 mrt_excel/；修改資料後請重新啟動。', flush=True)
    print('保持此終端機開啟；按 Ctrl+C 結束。地圖元件與街道底圖需要網路連線。', flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('地圖服務已關閉。')
    finally:
        server.server_close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
