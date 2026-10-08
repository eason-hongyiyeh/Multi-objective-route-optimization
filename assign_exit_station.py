"""以最近車站座標配對出口，不修改輸入檔案或地圖程式。

在 mrt-route/ 執行：python assign_exit_station.py（只需 Python 標準函式庫）。
讀取 data/mrt_station.geojson 與 data/mrt_exits_clean.geojson，輸出：
  data/mrt_exits_with_station.geojson
  data/exit_station_review.csv

距離使用 Haversine 球面直線距離，並非步行路徑長度。
station_name 一律為最近的候選車站原名；matched 也只是距離門檻配對，
不等於官方確認歸屬。review / unmatched 必須人工確認。
保留原本 data_status，讓清理階段的缺漏與本次配對結果分別記錄。
"""

from collections import Counter
from copy import deepcopy
import csv
import io
import json
import math
from pathlib import Path
import sys

from clean_exits import add_property, valid_point


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / 'data'
EARTH_RADIUS_M = 6_371_008.8
MATCHED_MAX_M = 300
REVIEW_MAX_M = 600
NAME_FIELDS = ('name:zh-Hant', 'name:zh', 'name', 'name:en')
REVIEW_FIELDS = ('出口編號', '配對車站', '距離', '經度', '緯度',
                 '配對狀態', '出口來源ID', '出口原名', '配對站碼', '配對車站ID')


def read_collection(path):
    document = json.loads(path.read_text(encoding='utf-8-sig'))
    if (not isinstance(document, dict) or document.get('type') != 'FeatureCollection'
            or not isinstance(document.get('features'), list)):
        raise ValueError(f'{path.name} 須為 GeoJSON FeatureCollection。')
    crs = document.get('crs')
    if crs is not None:
        properties = crs.get('properties') if isinstance(crs, dict) else None
        name = properties.get('name', '') if isinstance(properties, dict) else ''
        if str(name).upper() not in (
            'EPSG:4326', 'CRS84', 'OGC:CRS84', 'URN:OGC:DEF:CRS:OGC:1.3:CRS84',
            'URN:OGC:DEF:CRS:OGC::CRS84', 'URN:OGC:DEF:CRS:EPSG::4326',
            'URN:OGC:DEF:CRS:EPSG:6.6:4326',
        ):
            raise ValueError(f'{path.name} 座標系統須為 WGS84 經緯度。')
    return document


def validate_features(features, label):
    """不悄悄丟棄資料；輸入有問題時先中止，避免輸出不完整配對。"""
    for index, feature in enumerate(features, start=1):
        if (not isinstance(feature, dict) or feature.get('type') != 'Feature'
                or not valid_point(feature.get('geometry'))):
            raise ValueError(f'{label}第 {index} 筆需要有效的 Point [longitude, latitude]。')
        if not isinstance(feature.get('properties'), dict):
            raise ValueError(f'{label}第 {index} 筆 properties 須為物件。')


def feature_name(feature):
    properties = feature['properties']
    return next((properties[key] for key in NAME_FIELDS
                 if isinstance(properties.get(key), str) and properties[key].strip()), None)


def source_id(feature):
    return feature.get('id') or feature['properties'].get('@id', '')


def distance_m(first, second):
    """兩組 [longitude, latitude] 的球面距離，單位為公尺。"""
    lon1, lat1 = map(math.radians, first)
    lon2, lat2 = map(math.radians, second)
    haversine = (math.sin((lat2 - lat1) / 2) ** 2
                 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(min(1.0, max(0.0, haversine))))


def match_status(distance):
    # 先用未四捨五入的距離分類：300 歸 matched，600 歸 review。
    if distance <= MATCHED_MAX_M:
        return 'matched'
    if distance <= REVIEW_MAX_M:
        return 'review'
    return 'unmatched'


def assign_stations(station_document, exit_document):
    stations, exits = station_document['features'], exit_document['features']
    validate_features(stations, '車站')
    validate_features(exits, '出口')
    if not stations:
        raise ValueError('車站檔沒有可供配對的車站。')
    for index, station in enumerate(stations, start=1):
        if feature_name(station) is None:
            raise ValueError(f'第 {index} 筆車站沒有站名；請補齊來源資料後再配對。')

    output = deepcopy(exit_document)
    review_rows, distances = [], []
    counts = Counter()
    for feature in output['features']:
        coordinates = feature['geometry']['coordinates']
        # 檢查檔案中的每一站。距離完全相同時保留來源檔排序的第一站。
        distance, station = min(
            ((distance_m(coordinates, station['geometry']['coordinates']), station)
             for station in stations), key=lambda item: item[0])
        name, status = feature_name(station), match_status(distance)
        properties = feature['properties']
        add_property(properties, 'station_name', name)
        add_property(properties, 'station_distance_m', distance)
        add_property(properties, 'station_match_status', status)
        distances.append(distance)
        counts[status] += 1
        if status != 'matched':
            review_rows.append({
                '出口編號': properties.get('ref', ''), '配對車站': name,
                '距離': distance, '經度': coordinates[0], '緯度': coordinates[1],
                '配對狀態': status, '出口來源ID': source_id(feature),
                '出口原名': feature_name(feature) or '',
                '配對站碼': station['properties'].get('ref', ''),
                '配對車站ID': source_id(station),
            })
    # 先列最遠的出口；距離欄位同 GeoJSON，單位為公尺。
    review_rows.sort(key=lambda row: row['距離'], reverse=True)
    stats = {'total': len(exits), **{key: counts[key] for key in ('matched', 'review', 'unmatched')},
             'average_distance_m': math.fsum(distances) / len(distances) if distances else None,
             'max_distance_m': max(distances) if distances else None}
    return output, review_rows, stats


def main():
    station_path = DATA_DIR / 'mrt_station.geojson'
    exit_path = DATA_DIR / 'mrt_exits_clean.geojson'
    output_path = DATA_DIR / 'mrt_exits_with_station.geojson'
    review_path = DATA_DIR / 'exit_station_review.csv'
    try:
        for path in (output_path, review_path):
            if path.is_symlink() or (path.exists() and any(
                    path.samefile(original) for original in (station_path, exit_path))):
                raise ValueError(f'{path.name} 不可連結至原始檔或其他檔案。')
        output, review_rows, stats = assign_stations(
            read_collection(station_path), read_collection(exit_path))
        geojson = json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
        csv_buffer = io.StringIO(newline='')
        writer = csv.DictWriter(csv_buffer, fieldnames=REVIEW_FIELDS)
        writer.writeheader()
        writer.writerows(review_rows)
        output_path.write_text(geojson, encoding='utf-8')
        # UTF-8 BOM 方便在 Windows Excel 開啟中文；CSV 保留實際距離。
        with review_path.open('w', encoding='utf-8-sig', newline='') as handle:
            handle.write(csv_buffer.getvalue())
    except (OSError, UnicodeError, ValueError) as error:
        print(f'配對失敗：{error}', file=sys.stderr)
        return 1

    print(f'出口總數：{stats["total"]}')
    for status in ('matched', 'review', 'unmatched'):
        print(f'{status}：{stats[status]}')
    for key, label in (('average_distance_m', '平均出口到車站距離'), ('max_distance_m', '最大距離')):
        value = stats[key]
        print(f'{label}：{value:.2f} 公尺' if value is not None else f'{label}：無出口資料')
    print(f'\n輸出：data/{output_path.name}')
    print(f'人工確認清單：data/{review_path.name}（{len(review_rows)} 筆）')
    print('距離為球面直線距離，不是步行距離；station_name 是最近候選車站的來源名稱。')
    print('matched：<= 300 公尺；review：> 300 且 <= 600 公尺；unmatched：> 600 公尺。')
    print('review / unmatched 請人工確認；原有 data_status 保留清理階段的缺漏標記。')
    print('原始檔保持不變；重跑會覆寫上述兩份輸出檔。')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
