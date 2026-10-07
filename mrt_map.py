"""讀取 data/ 的 GeoJSON，啟動本機互動地圖；只使用 Python 標準函式庫。"""
import argparse
from collections import Counter
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
from urllib.parse import quote
import webbrowser


ROOT = Path(__file__).resolve().parent
TITLES = {
    'mrt_tracks.geojson': '捷運軌道與設施',
    'mrt_station.geojson': '捷運車站與站名',
    'airportmrt.geojson': '機場捷運軌道',
}
COLORS = ('#247a9a', '#8851b0', '#008675', '#b27a1d', '#d1495b')
LAYER_COLORS = {
    'mrt_station.geojson': '#273f4f',
    'airportmrt.geojson': '#8851b0',
    'mrt_tracks.geojson': '#b27a1d',
}


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
        layers.append(info)
    resources['/layers.json'] = json.dumps({'layers': layers}, ensure_ascii=False).encode('utf-8')
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
