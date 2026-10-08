"""清理捷運出入口；在 mrt-route/ 執行 python clean_exits.py，無須額外套件。

原始檔保持不變，結果寫入 data/ 下的兩份 *_clean.geojson。
只接受 WGS84 二維 Point [longitude, latitude]，不交換座標或猜測站名。
完全重複指整筆 Feature 內容相同（忽略 JSON 欄位順序）；同座標的不同出口保留。
data_status 一律為陣列；缺漏統計以移除無效座標、去重後的輸出資料為準。
missing_station_name 表示缺少明確站名欄位，不把 name 的出口描述當成站名。
"""

from copy import deepcopy
import json
import math
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / 'data'
DATASETS = (
    ('mrt_exits.geojson', 'mrt_exits_clean.geojson', 'OSM', 'ref'),
    ('airport_mrt_exits.geojson', 'airport_mrt_exits_clean.geojson',
     'Taoyuan Metro Open Data', 'ExitID'),
)
# 只接受明確的站名欄位；name、ref、StationID 不能代替站名。
STATION_NAME_FIELDS = (
    'StationName_zh', 'StationName_en', 'station_name',
    'station_name:zh', 'station_name:zh-Hant', 'station_name:en',
    'station:name', 'station:name:zh', 'station:name:en',
)


def valid_point(geometry):
    """檢查經度在前、緯度在後的二維座標；不自動修正順序。"""
    if not isinstance(geometry, dict) or geometry.get('type') != 'Point':
        return False
    coordinates = geometry.get('coordinates')
    if not isinstance(coordinates, list) or len(coordinates) != 2:
        return False
    if not all(isinstance(value, (int, float)) and not isinstance(value, bool)
               and math.isfinite(value) for value in coordinates):
        return False
    longitude, latitude = coordinates
    return -180 <= longitude <= 180 and -90 <= latitude <= 90


def has_value(value):
    """空字串、null、布林值及複合物件不能當成出口編號。"""
    if isinstance(value, str):
        return bool(value.strip())
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def add_property(properties, key, value):
    """新增標記；遇到同名原始欄位時，另存原值，避免遺失來源資訊。"""
    if key in properties and properties[key] != value:
        backup = f'original_{key}'
        suffix = 2
        while backup in properties:
            backup = f'original_{key}_{suffix}'
            suffix += 1
        properties[backup] = properties[key]
    properties[key] = value


def clean_collection(document, source, exit_number_field):
    """回傳新的 FeatureCollection 及統計，不變更傳入的資料。"""
    if (not isinstance(document, dict) or document.get('type') != 'FeatureCollection'
            or not isinstance(document.get('features'), list)):
        raise ValueError('需要 GeoJSON FeatureCollection 格式。')
    if document.get('crs') is not None:
        crs = document['crs']
        properties = crs.get('properties') if isinstance(crs, dict) else None
        name = properties.get('name', '') if isinstance(properties, dict) else ''
        if str(name).upper() not in (
            'EPSG:4326', 'CRS84', 'OGC:CRS84', 'URN:OGC:DEF:CRS:OGC:1.3:CRS84',
            'URN:OGC:DEF:CRS:OGC::CRS84', 'URN:OGC:DEF:CRS:EPSG::4326',
            'URN:OGC:DEF:CRS:EPSG:6.6:4326',
        ):
            raise ValueError('僅支援 WGS84 經緯度（CRS84 / EPSG:4326），不自動轉換。')

    stats = dict(original=len(document['features']), output=0, invalid_coordinates=0,
                 duplicates=0, missing_exit_number=0, missing_station_name=0)
    cleaned, seen = [], set()
    for index, feature in enumerate(document['features'], start=1):
        if not isinstance(feature, dict) or feature.get('type') != 'Feature':
            raise ValueError(f'第 {index} 筆不是 GeoJSON Feature。')
        if not valid_point(feature.get('geometry')):
            stats['invalid_coordinates'] += 1
            continue
        original_properties = feature.get('properties')
        if original_properties is not None and not isinstance(original_properties, dict):
            raise ValueError(f'第 {index} 筆 properties 須為物件或 null。')
        # 包含來源 ID 與所有屬性，避免誤刪同位置的不同出入口。
        signature = json.dumps(feature, sort_keys=True, ensure_ascii=False, allow_nan=False)
        if signature in seen:
            stats['duplicates'] += 1
            continue
        seen.add(signature)

        result = deepcopy(feature)
        properties = result.get('properties') or {}
        result['properties'] = properties
        issues = []
        if not has_value(properties.get(exit_number_field)):
            issues.append('missing_exit_number')
            stats['missing_exit_number'] += 1
        if not any(isinstance(properties.get(key), str) and properties[key].strip()
                   for key in STATION_NAME_FIELDS):
            issues.append('missing_station_name')
            stats['missing_station_name'] += 1
        add_property(properties, 'source', source)
        add_property(properties, 'data_status', issues or ['ok'])
        cleaned.append(result)

    # 保留來源著作權、時間及其他中繼資料；刪除篩選後可能過期的集合範圍。
    output = deepcopy(document)
    output.pop('bbox', None)
    output['features'] = cleaned
    stats['output'] = len(cleaned)
    return output, stats


def main():
    jobs = []
    try:
        # 先驗證兩份來源，避免第二份來源有錯時只產生第一份清理結果。
        for input_name, output_name, source, number_field in DATASETS:
            input_path, output_path = DATA_DIR / input_name, DATA_DIR / output_name
            if output_path.is_symlink() or (output_path.exists()
                                            and output_path.samefile(input_path)):
                raise ValueError(f'{output_name} 不能連結至原始檔或其他檔案。')
            document = json.loads(input_path.read_text(encoding='utf-8-sig'))
            output, stats = clean_collection(document, source, number_field)
            content = json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
            jobs.append((input_name, output_path, content, stats))
        for _input_name, output_path, content, _stats in jobs:
            output_path.write_text(content, encoding='utf-8')
    except (OSError, UnicodeError, ValueError) as error:
        print(f'清理失敗：{error}', file=sys.stderr)
        return 1

    for input_name, output_path, _content, stats in jobs:
        print(f'\n{input_name} -> data/{output_path.name}')
        for key, label in (
            ('original', '原始筆數'), ('output', '輸出筆數'),
            ('invalid_coordinates', '移除無效座標'), ('duplicates', '移除重複資料'),
            ('missing_exit_number', '缺出口編號'), ('missing_station_name', '缺站名'),
        ):
            print(f'  {label}：{stats[key]}')
    print('\n缺漏筆數以清理後資料計算，同一筆可能同時缺編號與站名。')
    print('站名只檢查明確站名欄位；不從出口名稱、座標或站碼猜測。')
    print('原始檔保持不變；重跑會覆寫上述兩份清理檔。')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
