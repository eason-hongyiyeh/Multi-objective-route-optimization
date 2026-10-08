"""讀取 data/ 的 GeoJSON，啟動本機互動地圖；只使用 Python 標準函式庫。"""
import argparse
from collections import Counter
import csv
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
from urllib.parse import quote
import webbrowser
from calculate_market_walks import fingerprint, MAX_WALK_SECONDS


ROOT = Path(__file__).resolve().parent
TITLES = {
    'mrt_tracks.geojson': '捷運路線與路線節點',
    'mrt_station.geojson': '捷運車站與站名',
    'airportmrt.geojson': '機場捷運路線、軌道與停靠點',
    'nightmarket.geojson': '夜市',
    'mrt_exits.geojson': '捷運出入口',
    'airport_mrt_exits.geojson': '機場捷運出入口',
}
COLORS = ('#247a9a', '#8851b0', '#008675', '#b27a1d', '#d1495b')
LAYER_COLORS = {
    'mrt_station.geojson': '#273f4f',
    'airportmrt.geojson': '#8851b0',
    'mrt_tracks.geojson': '#b27a1d',
    'nightmarket.geojson': '#B42365',
    'mrt_exits.geojson': '#0075BE',
    'airport_mrt_exits.geojson': '#8851B0',
}
# 衍生出口檔保留供資料作業使用，避免與原始出口在一般地圖重複繪製。
DERIVED_EXIT_FILES = {'mrt_exits_clean.geojson', 'airport_mrt_exits_clean.geojson',
                      'mrt_exits_with_station.geojson'}


def load_exit_reviews(data_dir, resources):
    """以 CSV 的車站 ID 連結來源座標，只提供檢查畫面，不重算或改寫配對。"""
    result = {'reviews': [], 'errors': [], 'total': 0}
    required = {'出口編號', '配對車站', '距離', '經度', '緯度', '配對狀態',
                '出口來源ID', '出口原名', '配對站碼', '配對車站ID'}
    try:
        stations = json.loads(resources['/data/mrt_station.geojson'])['features']
        by_id = {str(f.get('id') or (f.get('properties') or {}).get('@id')): f
                 for f in stations if f['geometry']['type'] == 'Point'}
        with (Path(data_dir) / 'exit_station_review.csv').open(encoding='utf-8-sig', newline='') as handle:
            reader = csv.DictReader(handle)
            if not required.issubset(reader.fieldnames or []):
                raise ValueError('CSV 缺少欄位：' + '、'.join(sorted(required - set(reader.fieldnames or []))))
            for row in reader:
                if (row.get('配對狀態') or '').strip() != 'review':
                    continue
                result['total'] += 1
                try:
                    station_id = (row.get('配對車站ID') or '').strip()
                    exit_id = (row.get('出口來源ID') or '').strip()
                    if not exit_id:
                        raise ValueError('缺少出口來源 ID')
                    if not station_id or station_id not in by_id:
                        raise ValueError(f'找不到配對車站 ID：{station_id or "未提供"}')
                    coordinates = [float(row['經度']), float(row['緯度'])]
                    if not valid_geometry({'type': 'Point', 'coordinates': coordinates}):
                        raise ValueError('出口經緯度無效')
                    distance = float(row['距離'])
                    if not math.isfinite(distance) or distance < 0:
                        raise ValueError('距離須為有效的非負公尺數')
                    result['reviews'].append({
                        'number': result['total'], 'exit_ref': row['出口編號'] or '',
                        'exit_name': row['出口原名'] or '', 'exit_id': exit_id,
                        'station_name': row['配對車站'] or '', 'station_ref': row['配對站碼'] or '',
                        'station_id': station_id, 'distance_m': distance,
                        'exit_coordinates': coordinates,
                        'station_coordinates': by_id[station_id]['geometry']['coordinates'][:2],
                    })
                except (ValueError, TypeError, KeyError) as error:
                    result['errors'].append(f'CSV 第 {reader.line_num} 行：{error}')
    except (OSError, UnicodeError, ValueError, KeyError, csv.Error) as error:
        result['reviews'] = []
        result['errors'].append(f'出口配對檢查資料無法載入：{error}')
    return result


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


def build_resources(data_dir=ROOT / 'data'):
    data_dir = Path(data_dir).resolve()
    if not data_dir.is_dir():
        raise ValueError(f'找不到資料夾：{data_dir}')
    resources, layers = {}, []
    paths = sorted(p for p in data_dir.rglob('*')
                   if p.is_file() and p.suffix.lower() == '.geojson'
                   and p.resolve().is_relative_to(data_dir))
    for index, path in enumerate(paths):
        relative = path.relative_to(data_dir).as_posix()
        info = {'id': relative, 'name': TITLES.get(path.name, path.stem),
                'url': '/data/' + quote(relative, safe='/'),
                'color': LAYER_COLORS.get(path.name, COLORS[index % len(COLORS)])}
        try:
            data, counts = load_geojson(path)
            resources[info['url']] = json.dumps(data, ensure_ascii=False, allow_nan=False).encode('utf-8')
            info.update(counts, error=None)
        except (OSError, UnicodeError, ValueError, RecursionError) as error:
            info.update(error=str(error), total=0, displayed=0, missing_geometry=0, invalid_geometry=0)
        if path.name.lower() not in DERIVED_EXIT_FILES:
            layers.append(info)
    resources['/layers.json'] = json.dumps({'layers': layers}, ensure_ascii=False).encode('utf-8')
    resources['/exit-station-review.json'] = json.dumps(
        load_exit_reviews(data_dir, resources), ensure_ascii=False, allow_nan=False).encode('utf-8')
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
    def __init__(self, *args, resources, **kwargs):
        self.resources = resources
        super().__init__(*args, **kwargs)

    def do_GET(self):
        path = self.path.split('?', 1)[0]
        if path in ('/', '/map.html'):
            content, mime = (ROOT / 'map.html').read_bytes(), 'text/html; charset=utf-8'
        elif path in self.resources:
            content, mime = self.resources[path], 'application/json; charset=utf-8'
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(content)))
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, *_args):
        pass


def make_server(port=8765, data_dir=ROOT / 'data'):
    resources = build_resources(data_dir)
    return ThreadingHTTPServer(('127.0.0.1', port),
                              partial(MapHandler, resources=resources))


def main(argv=None):
    parser = argparse.ArgumentParser(description='將 data/ 裡的 GeoJSON 顯示在地圖上。')
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
    print('資料來自 data/；新增或修改資料後請重新啟動。', flush=True)
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
