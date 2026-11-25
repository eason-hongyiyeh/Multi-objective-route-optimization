"""以現有資料推薦指定捷運站周邊的一個景點與一間餐廳。"""
from datetime import datetime, timedelta
import json
from pathlib import Path
import re
import threading
import time

from calculate_market_walks import Router, distance
from fetch_recommendation_data import valid_coordinate
from route_planner import QueryError, normalize


ROOT = Path(__file__).resolve().parent
EXIT_SOURCE = 'https://web.metro.taipei/pages2026/WebStation/051/1'
MAIN_EXITS = {
    'node/2793285506': 'M8', 'node/2793285507': 'M1', 'node/2793285508': 'M2',
    'node/3505143594': 'M7', 'node/3505143693': 'M4', 'node/3505143793': 'M3',
    'node/3505143993': 'M5', 'node/3707479441': 'M6',
}
CATEGORIES = {
    'any': {'tourism=museum', 'tourism=gallery', 'tourism=attraction', 'leisure=park',
            'leisure=garden', 'amenity=place_of_worship', 'historic=castle'},
    'museum': {'tourism=museum', 'tourism=gallery'},
    'park': {'leisure=park', 'leisure=garden'},
    'temple': {'amenity=place_of_worship'},
}
DAYS = ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su']


def opening_status(text, arrival, stay_seconds, holiday=False):
    """只判斷可完整解析的基本 OSM 時段，其餘回傳 unknown。"""
    text = str(text or '').strip()
    if text == '24/7':
        return 'open_per_data'
    if not text or holiday:
        return 'unknown'
    rules = []
    for rule in text.split(';'):
        match = re.fullmatch(r'(?:(Mo|Tu|We|Th|Fr|Sa|Su)((?:[-,](?:Mo|Tu|We|Th|Fr|Sa|Su))*)\s+)?(off|(?:\d{2}:\d{2}-\d{2}:\d{2})(?:\s*,\s*\d{2}:\d{2}-\d{2}:\d{2})*)', rule.strip())
        if not match:
            return 'unknown'
        first, rest, spans = match.groups()
        weekdays = set(range(7))
        if first:
            weekdays = set()
            for part in (first + rest).split(','):
                ends = part.split('-')
                start = DAYS.index(ends[0]); end = DAYS.index(ends[-1])
                weekdays.update((start + i) % 7 for i in range((end - start) % 7 + 1))
        ranges = []
        if spans != 'off':
            for span in spans.split(','):
                values = [int(h) * 60 + int(m) for h, m in re.findall(r'(\d{2}):(\d{2})', span)]
                if any(int(m) >= 60 or int(h) > 24 or (int(h) == 24 and int(m) != 0)
                       for h, m in re.findall(r'(\d{2}):(\d{2})', span)):
                    return 'unknown'
                if values[0] == values[1] or values[0] >= 1440:
                    return 'unknown'
                if values[1] <= values[0]:
                    values[1] += 1440
                ranges.append(values)
        rules.append((weekdays, ranges))
    midnight = arrival.replace(hour=0, minute=0, second=0, microsecond=0)
    intervals = []
    for offset in (-1, 0, 1):
        day = midnight + timedelta(days=offset)
        ranges = []
        for weekdays, spans in rules:
            if day.weekday() in weekdays:
                if not spans:
                    ranges.clear()
                else:
                    ranges.extend(spans)
        intervals.extend((day + timedelta(minutes=a), day + timedelta(minutes=b)) for a, b in ranges)
    end = arrival + timedelta(seconds=stay_seconds)
    covered = arrival
    for a, b in sorted(intervals):
        if a <= covered < b:
            covered = b
        if covered >= end:
            return 'open_per_data'
    return 'closed_per_data'


class ItineraryPlanner:
    def __init__(self, planner, resources, router=None):
        self.planner = planner
        self.router = router or Router(timeout=7, snap_limit_m=35)
        self.lock = threading.Lock()
        self.places = {'attraction': [], 'restaurant': []}
        self.exits = []
        self.station_groups = self._station_groups()
        self.group_by_code = {code: group for group in self.station_groups for code in group}
        layers = json.loads(resources['/layers.json'])['layers']
        raw_tags = {}
        for layer in layers:
            if layer.get('candidate_group') and not raw_tags:
                raw_path = ROOT / Path(layer['id']).parent / 'overpass_raw.json'
                if raw_path.is_file():
                    raw = json.loads(raw_path.read_text(encoding='utf-8'))
                    raw_tags = {f"{r.get('type')}/{r.get('id')}": r.get('tags', {}) for r in raw.get('elements', [])}
        seen = set()
        for layer in layers:
            if layer.get('error') or layer['url'] not in resources:
                continue
            data = json.loads(resources[layer['url']])
            for feature in data['features']:
                p = feature.get('properties') or {}
                geometry = feature.get('geometry') or {}
                if geometry.get('type') != 'Point':
                    continue
                lon, lat = geometry['coordinates'][:2]
                if not valid_coordinate(lat, lon):
                    continue
                if layer['id'] in ('mrt_exits.geojson', 'airport_mrt_exits.geojson'):
                    exit_point = self._match_exit(feature, layer['id'])
                    if exit_point:
                        self.exits.append(exit_point)
                kind = 'attraction' if p.get('AttractionID') else 'restaurant' if p.get('RestaurantID') else None
                if not kind:
                    continue
                prefix = 'Attraction' if kind == 'attraction' else 'Restaurant'
                name, record_id = p.get(prefix+'Name'), p.get(prefix+'ID')
                if not name or not str(name).strip() or record_id in seen:
                    continue
                seen.add(record_id)
                osm_key = '/'.join(str(record_id).split('_')[-2:])
                tags = raw_tags.get(osm_key, {})
                coordinate_type = p.get('CoordinateType') or ('osm_bbox_center' if '_OSM_way_' in record_id or '_OSM_relation_' in record_id else 'point')
                level = tags.get('level')
                if coordinate_type == 'osm_bbox_center' or (level is not None and str(level) not in ('0', '0.0')):
                    continue
                if 'possible_duplicate' in p.get('DataIssues', []):
                    continue
                category = p.get('Category') or next((f'{k}={tags[k]}' for k in ('tourism', 'leisure', 'amenity') if k in tags), '')
                self.places[kind].append({'id': record_id, 'name': str(name).strip(), 'lat': lat, 'lon': lon,
                    'category': category, 'hours': p.get('ServiceTimeInfo') or tags.get('opening_hours', ''),
                    'cuisine': p.get('Cuisine', ''), 'source_url': p.get('SourceURL') or
                    (f'https://www.openstreetmap.org/{osm_key}' if '_OSM_' in record_id else ''),
                    'feature': feature})

    def _station_groups(self):
        groups, remaining = [], set(self.planner.stops)
        while remaining:
            code = min(remaining)
            group, pending = {code}, [code]
            while pending:
                current = pending.pop()
                stop = self.planner.stops[current]
                for other, _seconds in self.planner.transfers[current]:
                    peer = self.planner.stops[other]
                    # 跨系統轉乘仍須計算步行，不能把同名機捷／環狀線當成同一月台。
                    if (other in remaining and other not in group
                            and stop['line_id'] not in ('A', 'Y') and peer['line_id'] not in ('A', 'Y')
                            and normalize(stop['name']) == normalize(peer['name'])
                            and distance([stop['lon'], stop['lat']], [peer['lon'], peer['lat']]) <= 100):
                        group.add(other)
                        pending.append(other)
            remaining -= group
            groups.append(tuple(sorted(group)))
        return groups

    def _match_exit(self, feature, source_file):
        p = feature.get('properties') or {}
        if (p.get('access') in ('no', 'private') or p.get('emergency') == 'yes'
                or p.get('station_match_status') in ('review', 'unmatched', 'pending')
                or p.get('coordinate_status') not in (None, 'confirmed')):
            return None
        point = feature['geometry']['coordinates'][:2]
        ref = str(p.get('ref') or p.get('ExitID') or '').strip()
        if not ref:
            return None
        source_id = feature.get('id') or p.get('@id') or p.get('ExitID')
        group, method = None, ''
        code = p.get('StationID') or p.get('station_ref')
        if code:
            code = self.planner.code_lookup.get(normalize(code))
            if code is None:
                return None
            group, method = self.group_by_code[code], 'source_station_code'
        elif source_id in MAIN_EXITS and ref == MAIN_EXITS[source_id] and 'BL12' in self.group_by_code:
            group, method = self.group_by_code['BL12'], 'official_exit_list'
        elif p.get('station_name'):
            matches = {self.group_by_code[c] for c, stop in self.planner.stops.items()
                       if normalize(stop['name']) == normalize(p['station_name'])}
            if len(matches) != 1:
                return None
            group, method = matches.pop(), 'source_station_name'
        else:
            # 不將地下街或缺編號的設施，直接當成附近捷運站的出口。
            if (not re.fullmatch(r'\d{1,2}[A-Za-z]?', ref)
                    or '地下街' in str(p.get('name', ''))):
                return None
            nearby = sorted((min(distance(point, [self.planner.stops[c]['lon'], self.planner.stops[c]['lat']])
                                 for c in g), g) for g in self.station_groups)
            if not nearby or nearby[0][0] > 300 or (len(nearby) > 1 and nearby[1][0] - nearby[0][0] < 50):
                return None
            group, method = nearby[0][1], 'nearest_station'
        gap = min(distance(point, [self.planner.stops[c]['lon'], self.planner.stops[c]['lat']]) for c in group)
        if gap > 600:
            return None
        station = self.planner.stops[group[0]]
        station_name = station['name'] + ('（機場捷運）' if station['line_id'] == 'A' else '')
        source_url = EXIT_SOURCE if method == 'official_exit_list' else p.get('coordinate_source', '')
        if not source_url and re.fullmatch(r'(node|way|relation)/\d+', str(source_id)):
            source_url = f'https://www.openstreetmap.org/{source_id}'
        return {'id': f'{source_file}:{source_id}', 'name': f'{station_name} {ref} 出口',
                'ref': ref, 'lat': point[1], 'lon': point[0], 'station_codes': list(group),
                'station_match_method': method, 'station_distance_m': round(gap, 1),
                'source_file': source_file, 'source_url': source_url, 'feature': feature}

    def _destination(self, value):
        if not isinstance(value, str) or not value.strip() or len(value) > 100:
            raise QueryError('請選擇目的地捷運站。')
        code = self.planner.code_lookup.get(normalize(value))
        if code is None:
            groups = {self.group_by_code[c] for c, stop in self.planner.stops.items()
                      if normalize(stop['name']) == normalize(value)}
            if len(groups) == 1:
                code = next(iter(groups))[0]
            else:
                code = self.planner.resolve(value)
        return self.planner.stops[code]

    def _area(self, destination):
        group = self.group_by_code[destination['id']]
        center = [destination['lon'], destination['lat']]
        exits = [e for e in self.exits if set(e['station_codes']).intersection(group)]
        places = {kind: [p for p in rows if distance(center, [p['lon'], p['lat']]) <= 1300]
                  for kind, rows in self.places.items()}
        return exits, places

    @staticmethod
    def _matches_preference(place, preference):
        return place['category'] in CATEGORIES[preference] or (preference == 'any' and not place['category'])

    @staticmethod
    def public_place(place):
        return {key: value for key, value in place.items() if key != 'feature'}

    def catalog(self):
        destinations = []
        for stop in self.planner.stops.values():
            exits, places = self._area(stop)
            destinations.append({**stop, 'station_codes': list(self.group_by_code[stop['id']]),
                                 'exit_count': len(exits),
                                 'attraction_count': sum(self._matches_preference(p, 'any') for p in places['attraction']),
                                 'restaurant_count': len(places['restaurant'])})
        return {'mode': 'local_rules', 'llm_connected': False, 'destinations': destinations,
                'default_destination': 'BL12',
                'attractions': len(self.places['attraction']), 'restaurants': len(self.places['restaurant']),
                'exit_count': len(self.exits), 'max_walk_m': 1200,
                'note': '依所選車站搜尋現有資料；候選數量不代表已通過步行與營業時間檢查。'}

    def recommend(self, values):
        if not self.lock.acquire(blocking=False):
            raise QueryError('目前有行程正在計算，請稍後再試。')
        try:
            return self._recommend(values)
        finally:
            self.lock.release()

    def _recommend(self, values):
        destination = self._destination(values.get('destination', ''))
        exits, area_places = self._area(destination)
        area_name = destination['name']
        if not exits:
            raise QueryError(f'{area_name}目前沒有可用且能配對的出口資料，無法安排步行行程；請先補齊或確認該站出口。')
        preference = values.get('preference', 'any')
        if preference not in CATEGORIES:
            raise QueryError('景點偏好無效。')
        holiday = values.get('holiday', '0')
        if holiday not in ('0', '1'):
            raise QueryError('假日設定無效。')
        def integer(key, default, minimum, maximum):
            value = str(values.get(key, default))
            if not re.fullmatch(r'\d{1,4}', value) or not minimum <= int(value) <= maximum:
                raise QueryError(f'{key} 必須介於 {minimum}～{maximum}。')
            return int(value)
        budget_s = integer('budget_min', 240, 30, 720) * 60
        visit_s = integer('visit_min', 60, 10, 180) * 60
        meal_s = integer('meal_min', 60, 10, 180) * 60
        exit_s = integer('exit_min', 5, 0, 30) * 60
        food = str(values.get('food', '')).strip().casefold()
        if len(food) > 40:
            raise QueryError('餐廳關鍵字最多 40 個字。')
        center = [destination['lon'], destination['lat']]
        attractions = [p for p in area_places['attraction'] if self._matches_preference(p, preference)]
        attractions.sort(key=lambda p: (not bool(p['hours']), distance(center, [p['lon'], p['lat']]), p['id']))
        food_words = {'牛肉麵': ['beef_noodle'], '拉麵': ['ramen'], '日式': ['japanese'],
                      '素食': ['vegetarian', 'vegan'], '早餐': ['breakfast'], '台式': ['taiwanese']}
        restaurants = [p for p in area_places['restaurant']
                       if not food or any(term in (p['name']+' '+p['cuisine']).casefold()
                                          for term in [food, *food_words.get(food, [])])]
        if not attractions or not restaurants:
            missing = '、'.join(label for label, rows in [('景點', attractions), ('餐廳', restaurants)] if not rows)
            raise QueryError(f'{area_name}周邊沒有符合條件的{missing}候選資料。可調整偏好或關鍵字；若仍無資料，需要補充該區資料，不會改推薦台北車站。')
        origin, departure = values.get('origin', ''), values.get('departure_at', '')
        origin = self.planner.resolve(origin)
        transit_options, route_errors = [], []
        for code in self.group_by_code[destination['id']]:
            try:
                route = self.planner.query(origin, code, departure, holiday == '1')
            except QueryError as error:
                route_errors.append(str(error))
                continue
            if route['status'] == 'ok':
                transit_options.append(route)
        if not transit_options:
            if len(route_errors) == len(self.group_by_code[destination['id']]):
                raise QueryError(route_errors[0])
            raise QueryError(f'指定起點到{area_name}在此時段沒有完整可用班次，無法排定抵達時間；請確認班表或調整出發時間。')
        transit = min(transit_options, key=lambda r: r['total_s'])
        start = datetime.fromisoformat(transit['departure_at'])
        at_exit = datetime.fromisoformat(transit['arrival_at']) + timedelta(seconds=exit_s)
        deadline, calls, failed = time.monotonic()+40, 0, 0
        best, compared, cache = None, 0, {}
        def walk(a, b):
            nonlocal calls, failed
            key = (a['id'], b['id'])
            if key in cache:
                return cache[key]
            if calls >= 12 or time.monotonic() >= deadline:
                return None
            calls += 1
            try:
                result = self.router.route(a['feature'], b['feature'])
                if not 0 < result['distance_m'] <= 1200:
                    result = None
            except OSError as error:
                raise QueryError('步行路由服務無法連線，請檢查網路後重試；未使用直線距離代替步行。') from error
            except RuntimeError as error:
                raise QueryError('步行路由服務暫時無法使用，請稍後重試；未使用直線距離代替步行。') from error
            except (ValueError, KeyError, IndexError, TypeError):
                failed += 1
                result = None
            cache[key] = result
            return result
        examined = 0
        for attraction in attractions:
            if examined >= 6 or compared >= 3 or calls >= 12 or time.monotonic() >= deadline:
                break
            if opening_status(attraction['hours'], at_exit, visit_s, holiday == '1') == 'closed_per_data':
                continue
            examined += 1
            exit_candidates = sorted(exits, key=lambda e: distance([e['lon'], e['lat']], [attraction['lon'], attraction['lat']]))
            first, exit_point = None, None
            for exit_point in exit_candidates[:2]:
                first = walk(exit_point, attraction)
                if first:
                    break
            if not first:
                continue
            visit_at = at_exit + timedelta(seconds=first['duration_s'])
            attraction_status = opening_status(attraction['hours'], visit_at, visit_s, holiday == '1')
            if attraction_status == 'closed_per_data':
                continue
            nearby = sorted(restaurants, key=lambda p: (not bool(p['hours']),
                            distance([p['lon'], p['lat']], [attraction['lon'], attraction['lat']]), p['id']))
            for restaurant in nearby[:4]:
                if calls >= 12 or time.monotonic() >= deadline:
                    break
                if distance([restaurant['lon'], restaurant['lat']], [attraction['lon'], attraction['lat']]) > 1200:
                    continue
                second = walk(attraction, restaurant)
                if not second:
                    continue
                meal_at = visit_at + timedelta(seconds=visit_s+second['duration_s'])
                restaurant_status = opening_status(restaurant['hours'], meal_at, meal_s, holiday == '1')
                if restaurant_status == 'closed_per_data':
                    continue
                exit_to_restaurant = walk(exit_point, restaurant)
                if not exit_to_restaurant:
                    continue
                end = meal_at + timedelta(seconds=meal_s)
                total_s = int((end-start).total_seconds())
                if total_s > budget_s:
                    continue
                compared += 1
                unknown = (attraction_status == 'unknown') + (restaurant_status == 'unknown')
                score = (unknown, first['duration_s']+second['duration_s'])
                if best is None or score < best[0]:
                    best = (score, {'transit': transit, 'exit': self.public_place(exit_point),
                        'attraction': {**self.public_place(attraction), 'arrival_at': visit_at.isoformat(),
                                       'departure_at': (visit_at+timedelta(seconds=visit_s)).isoformat(), 'hours_status': attraction_status},
                        'restaurant': {**self.public_place(restaurant), 'arrival_at': meal_at.isoformat(),
                                       'departure_at': end.isoformat(), 'hours_status': restaurant_status},
                        'walks': [dict(first, from_name=exit_point['name'], to_name=attraction['name']),
                                  dict(second, from_name=attraction['name'], to_name=restaurant['name'])],
                        'restaurant_exit_distance_m': exit_to_restaurant['distance_m'],
                        'departure_at': start.isoformat(), 'end_at': end.isoformat(), 'total_s': total_s,
                        'walk_s': first['duration_s']+second['duration_s'],
                        'exit_buffer_s': exit_s, 'visit_s': visit_s, 'meal_s': meal_s})
                break
        if best is None:
            raise QueryError(f'{area_name}周邊這次沒有找到符合時間、營業時段及每段步行 1,200 公尺內的完整組合。部分點可能無法接上步行路網；可增加可用時間、改偏好或出發時段再試。')
        result = best[1]
        exit_note = (f"所選出口依最近車站座標配對，距站點 {result['exit']['station_distance_m']} 公尺；不是官方出口歸屬確認。"
                     if result['exit']['station_match_method'] == 'nearest_station'
                     else '所選出口依來源站碼／站名或既有官方出口表配對，座標沿用原資料。')
        result.update(status='ok', mode='local_rules', destination=destination,
                      compared_count=compared, routing_checks=calls,
                      failed_routes=failed,
                      reason=f'依所選偏好比對 {compared} 組可行行程，優先選時段可判讀的資料，再比較兩段步行時間；不是全區所有組合的最佳解。',
                      warnings=[
                          '目前使用本機條件推薦，尚未連接學校 LLM。',
                          '營業時間依 OSM 資料判讀，未由店家再次確認；無法判讀者標示待確認，請出發前核對。',
                          '步行採 OSM / Valhalla 路網、每秒 1 公尺；未含紅綠燈、排隊與地點內部動線。',
                          '道路起終點最多吸附 35 公尺；步行目的地為現有點位，仍需核對實際入口。',
                          exit_note,
                          '出站、景點停留與用餐時間為表單設定的預留時間；總時間不含回程。',
                          '只提供捷運票價，餐費與景點門票尚未估算。',
                          *transit['warnings'],
                      ])
        return result
