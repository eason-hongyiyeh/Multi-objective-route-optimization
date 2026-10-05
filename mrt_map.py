"""讀取 data/ 的軌道、出入口 GeoJSON，搭配車站 CSV 顯示本機地圖。"""
import argparse
import csv
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import webbrowser


ROOT = Path(__file__).resolve().parent
COLORS = {'BR': '#a66c2c', 'R': '#d92c40', 'G': '#00865b', 'O': '#e99a10', 'BL': '#0075be'}


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


def load_network(data_dir=ROOT / 'taipei_mrt'):
    data_dir = Path(data_dir)
    lines = {row['line_id']: {'id': row['line_id'], 'name': row['line_name'],
                             'color': COLORS.get(row['line_id'], '#526579')}
             for row in read_csv(data_dir / 'lines.csv')}
    stops, stations = {}, {}
    for row in read_csv(data_dir / 'stops.csv'):
        code, name, line = row['stop_id'], row['stop_name'], row['line_id']
        lat, lon = float(row['lat']), float(row['lon'])
        if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError(f'{code} 的經緯度無效。')
        if code in stops or line not in lines:
            raise ValueError(f'{code} 的站碼重複或所屬路線不存在。')
        stops[code] = {'code': code, 'name': name, 'line': line, 'lat': lat, 'lon': lon}
        # 同名且同座標的轉乘站合併；若未來座標不同，則保留各自標記。
        key = (name, lat, lon)
        station = stations.setdefault(key, {'name': name, 'lat': lat, 'lon': lon, 'codes': [], 'lines': []})
        station['codes'].append(code)
        if line not in station['lines']:
            station['lines'].append(line)
    if not stops:
        raise ValueError('沒有可顯示的車站。')
    return {'lines': list(lines.values()), 'stops': stops, 'stations': list(stations.values())}


def valid_geometry(geometry):
    """GeoJSON 順序為經度、緯度；只驗證，不改寫來源座標。"""
    def point(value):
        return (isinstance(value, list) and len(value) >= 2
                and all(isinstance(v, (int, float)) and math.isfinite(v) for v in value[:2])
                and -180 <= value[0] <= 180 and -90 <= value[1] <= 90)

    def line(value):
        return isinstance(value, list) and len(value) >= 2 and all(point(p) for p in value)

    def polygon(value):
        return (isinstance(value, list) and bool(value)
                and all(line(ring) and len(ring) >= 4 and ring[0] == ring[-1] for ring in value))

    if not isinstance(geometry, dict):
        return False
    coordinates = geometry.get('coordinates')
    kind = geometry.get('type')
    checks = {'Point': point, 'LineString': line, 'Polygon': polygon}
    if kind in checks:
        return checks[kind](coordinates)
    multi = {'MultiLineString': line, 'MultiPolygon': polygon}
    return (kind in multi and isinstance(coordinates, list) and bool(coordinates)
            and all(multi[kind](part) for part in coordinates))


def load_geojson(path, allowed_types):
    with Path(path).open(encoding='utf-8-sig') as handle:
        source = json.load(handle)
    if source.get('type') != 'FeatureCollection' or not isinstance(source.get('features'), list):
        raise ValueError(f'{Path(path).name} 不是 GeoJSON FeatureCollection。')
    kept = []
    counts = {'total': len(source['features']), 'missing_geometry': 0, 'unsupported_geometry': 0,
              'invalid_geometry': 0, 'displayed': 0}
    for feature in source['features']:
        if not isinstance(feature, dict) or feature.get('type') != 'Feature':
            counts['invalid_geometry'] += 1
            continue
        geometry = feature.get('geometry')
        if geometry is None:
            counts['missing_geometry'] += 1
        elif not isinstance(geometry, dict):
            counts['invalid_geometry'] += 1
        elif geometry.get('type') not in allowed_types:
            counts['unsupported_geometry'] += 1
        elif not valid_geometry(geometry):
            counts['invalid_geometry'] += 1
        else:
            kept.append(feature)
    counts['displayed'] = len(kept)
    return {**source, 'features': kept, 'display_summary': counts}


class MapHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, resources, **kwargs):
        self.resources = resources
        super().__init__(*args, **kwargs)

    def do_GET(self):
        path = self.path.split('?', 1)[0]
        if path in ('/', '/map.html'):
            content = (ROOT / 'map.html').read_bytes()
            mime = 'text/html; charset=utf-8'
        elif path in self.resources:
            content = self.resources[path]
            mime = 'application/json; charset=utf-8'
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(content)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, *_args):
        pass


def make_server(port=8765):
    resources = {'/network.json': load_network(),
                 '/data/mrt_tracks.geojson': load_geojson(ROOT / 'data/mrt_tracks.geojson',
                     {'LineString', 'MultiLineString', 'Polygon', 'MultiPolygon'}),
                 '/data/mrt_exits.geojson': load_geojson(ROOT / 'data/mrt_exits.geojson', {'Point'})}
    encoded = {url: json.dumps(data, ensure_ascii=False, allow_nan=False).encode('utf-8')
               for url, data in resources.items()}
    return ThreadingHTTPServer(('127.0.0.1', port), partial(MapHandler, resources=encoded))


def main(argv=None):
    parser = argparse.ArgumentParser(description='開啟台北捷運互動地圖。')
    parser.add_argument('--port', type=int, default=8765, help='本機連接埠（預設 8765；0 為自動選擇）')
    parser.add_argument('--no-browser', action='store_true', help='只啟動服務，不自動開啟瀏覽器')
    args = parser.parse_args(argv)
    if not 0 <= args.port <= 65535:
        parser.error('--port 須介於 0 與 65535。')
    try:
        server = make_server(args.port)
    except (OSError, ValueError, KeyError) as error:
        print(f'無法啟動地圖：{error}；若連接埠被占用，可加上 --port 0。')
        return 1
    url = f'http://127.0.0.1:{server.server_port}/'
    print(f'捷運地圖：{url}', flush=True)
    print('保持此終端機開啟；按 Ctrl+C 結束。街道底圖需要網路連線。', flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n地圖服務已關閉。')
    finally:
        server.server_close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
