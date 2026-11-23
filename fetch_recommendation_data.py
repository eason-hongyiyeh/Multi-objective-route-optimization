"""下載 OSM 餐廳及景點候選至 imports/，地圖重啟後載入最新一批。"""
import argparse
from collections import Counter
import csv
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent
ENDPOINT = 'https://overpass-api.de/api/interpreter'
MAX_RESPONSE_BYTES = 25 * 1024 * 1024
FOOD = {'restaurant', 'fast_food', 'food_court'}
TOURISM = {'attraction', 'museum', 'gallery', 'viewpoint', 'zoo', 'theme_park', 'aquarium'}
HISTORIC = {'monument', 'memorial', 'ruins', 'archaeological_site', 'castle', 'building'}
ISSUE_NAMES = {
    'missing_name': '缺名稱',
    'missing_opening_hours': '缺營業／開放時間',
    'representative_coordinate': '座標為物件外框中心，非已確認入口',
    'representative_point_outside_radius': '代表點在搜尋半徑外，需核對物件範圍',
    'possible_duplicate': '疑似與其他 OSM 點重複',
    'existing_project_record': '與專案現有資料 ID 相同',
    'possible_existing_project_record': '疑似與專案現有資料重複',
}


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def valid_coordinate(lat, lon):
    return (all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
                for v in (lat, lon)) and -90 <= lat <= 90 and -180 <= lon <= 180)


def distance_m(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    value = math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2
    return 6371008.8 * 2 * math.asin(min(1, math.sqrt(value)))


def default_center():
    with (ROOT / 'mrt_excel' / 'stops.csv').open(encoding='utf-8-sig', newline='') as handle:
        for row in csv.DictReader(handle):
            if row['stop_id'] == 'BL12':
                return float(row['lat']), float(row['lon'])
    raise ValueError('stops.csv 找不到 BL12；請用 --lat 與 --lon 指定搜尋中心。')


def make_query(lat, lon, radius):
    around = f'(around:{radius},{lat:.7f},{lon:.7f})'
    return '\n'.join([
        '[out:json][timeout:40];', '(',
        f'  nwr["amenity"~"^({"|".join(sorted(FOOD))})$"]{around};',
        f'  nwr["tourism"~"^({"|".join(sorted(TOURISM))})$"]{around};',
        f'  nwr["leisure"~"^(park|garden)$"]{around};',
        f'  nwr["historic"~"^({"|".join(sorted(HISTORIC))})$"]{around};',
        f'  nwr["amenity"="place_of_worship"]["religion"~"^(buddhist|taoist|chinese_folk)$"]{around};',
        ');', 'out body center qt;',
    ])


def validate_response(document):
    if not isinstance(document, dict) or not isinstance(document.get('elements'), list):
        raise ValueError('Overpass 回傳格式錯誤：缺少 elements 陣列。')
    if document.get('remark'):
        raise ValueError(f'Overpass 未完整完成查詢，未輸出部分結果：{document["remark"]}')


def download(query, endpoint):
    request = Request(endpoint, data=urlencode({'data': query}).encode(), headers={
        'User-Agent': 'MrtRouteCandidateImport/1.0 (local educational data preparation)',
        'Content-Type': 'application/x-www-form-urlencoded; charset=utf-8',
        'Accept': 'application/json',
    })
    for attempt in range(2):
        try:
            with urlopen(request, timeout=55) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise ValueError('回傳超過 25 MB，請縮小 --radius。')
            document = json.loads(raw)
            validate_response(document)
            return document
        except HTTPError as error:
            if attempt == 0 and error.code in (429, 502, 503, 504):
                delay = error.headers.get('Retry-After', '5')
                seconds = int(delay) if delay.isdigit() else 5
                if seconds <= 15:
                    print(f'服務暫時忙碌（HTTP {error.code}），{max(3, seconds)} 秒後重試一次。', flush=True)
                    time.sleep(max(3, seconds))
                    continue
            raise RuntimeError(f'下載失敗：HTTP {error.code}。請稍後重試；本次不輸出候選檔。') from error


def category(tags):
    if tags.get('amenity') in FOOD:
        return 'restaurant', f'amenity={tags["amenity"]}'
    if tags.get('tourism') in TOURISM:
        return 'attraction', f'tourism={tags["tourism"]}'
    if tags.get('leisure') in ('park', 'garden'):
        return 'attraction', f'leisure={tags["leisure"]}'
    if tags.get('historic') in HISTORIC:
        return 'attraction', f'historic={tags["historic"]}'
    if tags.get('amenity') == 'place_of_worship' and tags.get('religion') in ('buddhist', 'taoist', 'chinese_folk'):
        return 'attraction', 'amenity=place_of_worship'
    return None, None


def normalize_name(value):
    return re.sub(r'\s+', '', str(value).replace('臺', '台')).casefold()


def existing_records():
    result = {}
    for kind, filename, array, prefix in [
        ('restaurant', 'RestaurantList.json', 'Restaurants', 'Restaurant'),
        ('attraction', 'AttractionList_with_fee_and_hours.json', 'Attractions', 'Attraction'),
    ]:
        path = ROOT / 'data' / filename
        if not path.exists():
            result[kind] = []
            continue
        document = read_json(path)
        if not isinstance(document, dict) or not isinstance(document.get(array), list):
            raise ValueError(f'{path.name} 格式錯誤，無法核對既有資料。')
        result[kind] = [(r.get(prefix+'ID'), normalize_name(r.get(prefix+'Name', '')),
                         r.get('PositionLat'), r.get('PositionLon'))
                        for r in document[array] if isinstance(r, dict)]
    return result


def convert(document, lat, lon, radius, existing):
    validate_response(document)
    groups = {'restaurant': [], 'attraction': []}
    removed, seen = [], set()
    for element in document['elements']:
        if not isinstance(element, dict):
            removed.append({'reason': 'invalid_element'}); continue
        kind, number = element.get('type'), element.get('id')
        if kind not in ('node', 'way', 'relation') or type(number) is not int or number <= 0:
            removed.append({'reason': 'invalid_osm_id'}); continue
        osm_id = f'{kind}/{number}'
        if osm_id in seen:
            removed.append({'osm_id': osm_id, 'reason': 'duplicate_osm_id'}); continue
        seen.add(osm_id)
        tags = element.get('tags') or {}
        if not isinstance(tags, dict):
            removed.append({'osm_id': osm_id, 'reason': 'invalid_tags'}); continue
        point = element if kind == 'node' else element.get('center')
        if not isinstance(point, dict) or not valid_coordinate(point.get('lat'), point.get('lon')):
            removed.append({'osm_id': osm_id, 'reason': 'invalid_coordinates'}); continue
        if (tags.get('access') in ('private', 'no')
                or any(tags.get(k) == 'yes' for k in ('disused', 'abandoned', 'demolished', 'construction'))):
            removed.append({'osm_id': osm_id, 'reason': 'restricted_or_inactive'}); continue
        group, subtype = category(tags)
        if group is None:
            removed.append({'osm_id': osm_id, 'reason': 'outside_selected_categories'}); continue
        prefix = 'Restaurant' if group == 'restaurant' else 'Attraction'
        record_id = f'{prefix}_OSM_{kind}_{number}'
        name = next((tags.get(k).strip() for k in ('name:zh-Hant', 'name:zh', 'name', 'name:en')
                     if isinstance(tags.get(k), str) and tags[k].strip()), '')
        hours = str(tags.get('opening_hours') or '').strip()
        issues = []
        if not name: issues.append('missing_name')
        if not hours: issues.append('missing_opening_hours')
        if kind != 'node': issues.append('representative_coordinate')
        radial = distance_m((lat, lon), (point['lat'], point['lon']))
        if radial > radius + 5: issues.append('representative_point_outside_radius')
        matches = []
        for old_id, old_name, old_lat, old_lon in existing.get(group, []):
            if old_id == record_id:
                matches.append(old_id)
                if 'existing_project_record' not in issues: issues.append('existing_project_record')
            elif name and old_name == normalize_name(name) and valid_coordinate(old_lat, old_lon):
                if distance_m((old_lat, old_lon), (point['lat'], point['lon'])) <= 75:
                    matches.append(old_id)
                    if 'possible_existing_project_record' not in issues: issues.append('possible_existing_project_record')
        record = {prefix+'ID': record_id, prefix+'Name': name,
                  'PositionLat': point['lat'], 'PositionLon': point['lon'],
                  'Category': subtype, 'ServiceTimeInfo': hours,
                  'CoordinateType': 'osm_node' if kind == 'node' else 'osm_bbox_center',
                  'SourceURL': f'https://www.openstreetmap.org/{osm_id}', 'DataIssues': issues}
        if group == 'restaurant': record['Cuisine'] = str(tags.get('cuisine') or '')
        if matches: record['ExistingRecordIDs'] = matches
        groups[group].append(record)
    for group, records in groups.items():
        prefix = 'Restaurant' if group == 'restaurant' else 'Attraction'
        buckets = {}
        for record in records:
            name = normalize_name(record[prefix+'Name'])
            if name: buckets.setdefault(name, []).append(record)
        for bucket in buckets.values():
            for index, record in enumerate(bucket):
                for other in bucket[index+1:]:
                    if distance_m((record['PositionLat'], record['PositionLon']),
                                  (other['PositionLat'], other['PositionLon'])) <= 25:
                        for a, b in ((record, other), (other, record)):
                            if 'possible_duplicate' not in a['DataIssues']: a['DataIssues'].append('possible_duplicate')
                            a.setdefault('PossibleDuplicateIDs', []).append(b[prefix+'ID'])
        records.sort(key=lambda r: (r[prefix+'Name'], r[prefix+'ID']))
    return groups, removed


def clean_candidates(groups, document, existing):
    tags_by_id = {f"{e.get('type')}/{e.get('id')}": e.get('tags', {})
                  for e in document.get('elements', []) if isinstance(e, dict)}
    def tags(record):
        return tags_by_id.get('/'.join(record.get('SourceURL', '').split('/')[-2:]), {})
    def conflict(a, b):
        fields = ('branch', 'level', 'addr:street', 'addr:housenumber', 'addr:unit')
        return any(a.get(k) and b.get(k) and normalize_name(a[k]) != normalize_name(b[k]) for k in fields)
    removed, stats = [], {}
    for kind, records in groups.items():
        prefix = 'Restaurant' if kind == 'restaurant' else 'Attraction'
        id_field, name_field = prefix + 'ID', prefix + 'Name'
        existing_ids = {r[0] for r in existing.get(kind, [])}
        kept, seen, buckets = [], set(), {}
        counts = Counter()
        ordered = sorted(records, key=lambda r: (
            -bool(r.get('ServiceTimeInfo')), -len(tags(r)), str(r.get(id_field, ''))))
        for record in ordered:
            reason, duplicate = None, None
            if not str(record.get(name_field) or '').strip():
                reason = 'missing_name'
            elif not valid_coordinate(record.get('PositionLat'), record.get('PositionLon')):
                reason = 'invalid_coordinates'
            elif record.get(id_field) in existing_ids:
                reason = 'duplicate_existing_id'
            elif record.get(id_field) in seen:
                reason = 'duplicate_id'
            else:
                for old in buckets.get(normalize_name(record[name_field]), []):
                    if (normalize_name(old[name_field]) == normalize_name(record[name_field])
                            and old.get('Category') == record.get('Category')
                            and distance_m((old['PositionLat'], old['PositionLon']),
                                           (record['PositionLat'], record['PositionLon'])) <= 25
                            and not conflict(tags(old), tags(record))):
                        duplicate, reason = old[id_field], 'duplicate_nearby_name'
                        break
            if reason:
                counts[reason] += 1
                removed.append({'id': record.get(id_field), 'name': record.get(name_field),
                                'reason': reason, 'kept_id': duplicate})
            else:
                kept.append(record)
                buckets.setdefault(normalize_name(record[name_field]), []).append(record)
                seen.add(record.get(id_field))
        kept_ids = {r[id_field] for r in kept}
        for record in kept:
            duplicates = [key for key in record.get('PossibleDuplicateIDs', []) if key in kept_ids]
            if duplicates:
                record['PossibleDuplicateIDs'] = duplicates
            else:
                record.pop('PossibleDuplicateIDs', None)
                record['DataIssues'] = [v for v in record.get('DataIssues', []) if v != 'possible_duplicate']
        groups[kind] = sorted(kept, key=lambda r: (r[name_field], r[id_field]))
        stats[kind] = {'before': len(records), 'after': len(kept), 'removed': dict(counts)}
    return groups, {'statistics': stats, 'removed_records': removed,
                    'rule': '移除缺名稱、無效座標、相同 ID；同類同名且 25 公尺內、分店／樓層／街道／門牌無衝突時保留一筆。地址衝突者保留供核對。'}


def clean_latest():
    for folder in sorted((ROOT / 'imports').glob('taipei_places_*'), reverse=True):
        filenames = {'restaurant': ('RestaurantCandidates.json', 'Restaurants'),
                     'attraction': ('AttractionCandidates.json', 'Attractions')}
        if not all((folder / name).is_file() for name, _ in filenames.values()):
            continue
        documents = {kind: read_json(folder / name) for kind, (name, _) in filenames.items()}
        groups = {kind: documents[kind][array] for kind, (_, array) in filenames.items()}
        groups, cleaning = clean_candidates(groups, read_json(folder / 'overpass_raw.json'), existing_records())
        cleaning['cleaned_at'] = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
        for kind, (name, array) in filenames.items():
            documents[kind][array] = groups[kind]
            documents[kind]['cleaned_at'] = cleaning['cleaned_at']
            (folder / name).write_text(json.dumps(documents[kind], ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')
        report = read_json(folder / 'fetch_report.json')
        report.setdefault('download_excluded_count', report['excluded_count'])
        report.setdefault('cleaning_history', []).append(cleaning)
        report['excluded_count'] = report['download_excluded_count'] + sum(len(item['removed_records']) for item in report['cleaning_history'])
        report['current_record_count'] = sum(len(records) for records in groups.values())
        for kind, records in groups.items():
            issues = Counter(issue for r in records for issue in r.get('DataIssues', []))
            report['summary'][kind] = {'count': len(records), 'issue_counts': {key: issues[key] for key in ISSUE_NAMES}}
        (folder / 'fetch_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        print(json.dumps(cleaning['statistics'], ensure_ascii=False, indent=2))
        print(f'已清理：{folder}；原始下載回應保留供追溯，不載入地圖。')
        return 0
    raise ValueError('imports/ 找不到完整候選資料。')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--radius', type=int, default=2000, help='搜尋半徑，單位公尺（100～5000，預設 2000）；不是步行距離')
    parser.add_argument('--lat', type=float, help='搜尋中心緯度，需與 --lon 一起指定')
    parser.add_argument('--lon', type=float, help='搜尋中心經度，需與 --lat 一起指定')
    parser.add_argument('--endpoint', default=ENDPOINT, help='Overpass HTTPS API 網址')
    parser.add_argument('--input', type=Path, help='改用之前下載的 Overpass JSON，免重新連網')
    parser.add_argument('--clean-latest', action='store_true', help='清理最新候選檔，不重新下載')
    args = parser.parse_args(argv)
    if not 100 <= args.radius <= 5000: parser.error('--radius 需介於 100～5000 公尺。')
    if (args.lat is None) != (args.lon is None): parser.error('--lat 與 --lon 必須一起指定。')
    parsed = urlsplit(args.endpoint)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        parser.error('--endpoint 需為不含帳密與查詢字串的 HTTPS API 網址。')
    try:
        if args.clean_latest:
            if args.input:
                parser.error('--clean-latest 不能與 --input 一起使用。')
            return clean_latest()
        lat, lon = default_center() if args.lat is None else (args.lat, args.lon)
        if not valid_coordinate(lat, lon): parser.error('搜尋中心經緯度無效。')
        query = make_query(lat, lon, args.radius)
        existing = existing_records()
        print(f'搜尋中心：{lat:.7f}, {lon:.7f}；半徑：{args.radius} 公尺（非步行距離）', flush=True)
        print('讀取既有原始回應…' if args.input else '正在向 OpenStreetMap Overpass 下載候選資料…', flush=True)
        document = read_json(args.input) if args.input else download(query, args.endpoint)
        groups, removed = convert(document, lat, lon, args.radius, existing)
        groups, cleaning = clean_candidates(groups, document, existing)
        now = datetime.now(timezone(timedelta(hours=8)))
        metadata = {
            'source': 'OpenStreetMap contributors', 'source_url': 'https://www.openstreetmap.org',
            'license': 'ODbL-1.0', 'license_url': 'https://opendatacommons.org/licenses/odbl/1-0/',
            'processed_at': now.isoformat(timespec='seconds'),
            'downloaded_at': None if args.input else now.isoformat(timespec='seconds'),
            'osm_base_timestamp': document.get('osm3s', {}).get('timestamp_osm_base'),
            'center': {'lat': lat, 'lon': lon}, 'radius_m': args.radius,
            'walking_status': 'not_calculated', 'opening_hours_status': 'unverified_osm',
        }
        summary = {}
        for kind, records in groups.items():
            counts = Counter(issue for r in records for issue in r['DataIssues'])
            summary[kind] = {'count': len(records), 'issue_counts': {k: counts[k] for k in ISSUE_NAMES}}
        report = {**metadata, 'raw_element_count': len(document['elements']), 'summary': summary,
                  'cleaning_history': [cleaning],
                  'download_excluded_count': len(removed),
                  'excluded_count': len(removed) + len(cleaning['removed_records']), 'excluded_records': removed,
                  'current_record_count': sum(len(records) for records in groups.values()),
                  'issue_meanings': ISSUE_NAMES, 'endpoint': None if args.input else args.endpoint,
                  'query': None if args.input else query,
                  'input_file': str(args.input.resolve()) if args.input else None,
                  'notes': [
                      '這是餐廳與景點候選資料，可在地圖檢視；未驗證營業狀態、未計算步行路徑。',
                      '營業時間原樣取自 OSM；空值保持空值，不以 LLM 補造。',
                      'way / relation 座標是外框中心，可能不在物件內，也不是已確認的入口。',
                      cleaning['rule'],
                      '依 ID 或同名且 75 公尺內的座標比對專案既有資料；不覆寫也不自動重新加入。',
                      '搜尋半徑用於取得候選，不代表沿道路走路不超過 1200 公尺。',
                      '使用 --input 時只重新整理原始回應，不代表重新抓取或更改原始搜尋範圍。',
                  ]}
        folder = ROOT / 'imports' / ('taipei_places_' + now.strftime('%Y%m%d_%H%M%S_%f'))
        folder.mkdir(parents=True, exist_ok=False)
        outputs = {
            'overpass_raw.json': document,
            'RestaurantCandidates.json': {**metadata, 'Restaurants': groups['restaurant']},
            'AttractionCandidates.json': {**metadata, 'Attractions': groups['attraction']},
            'fetch_report.json': report,
        }
        for filename, data in outputs.items():
            (folder / filename).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')
        print(f'原始物件：{len(document["elements"])}；移除缺名稱／無效／重複／非候選物件：{report["excluded_count"]}')
        for kind, label in [('restaurant', '餐廳'), ('attraction', '景點')]:
            stats = summary[kind]
            print(f'{label}候選：{stats["count"]} 筆')
            for issue, count in stats['issue_counts'].items():
                print(f'  {ISSUE_NAMES[issue]}：{count} 筆')
        print(f'輸出資料夾：{folder}')
        print('請重新啟動 python mrt_map.py 查看最新候選；尚未通過步行 1200 公尺篩選。')
        return 0
    except (OSError, ValueError, RuntimeError, URLError) as error:
        print(f'抓取失敗：{error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
