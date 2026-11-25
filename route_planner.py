"""讀取 mrt_excel 的 CSV，以班表、行駛及轉乘時間查詢路線（不改寫來源）。"""
from bisect import bisect_left
from collections import defaultdict
import csv
from datetime import datetime, timedelta
from functools import lru_cache
import heapq
import itertools
import math
from pathlib import Path

from fare_calculator import FARE_MODES, FareCalculator


ROOT = Path(__file__).resolve().parent
SERVICE_TYPES = {'weekday', 'weekend_holiday', 'saturday', 'sunday_holiday', 'daily', 'unspecified'}


class QueryError(ValueError):
    pass


def normalize(value):
    return str(value).strip().replace('臺', '台').upper()


def service_matches(service, day, holiday=False):
    if service == 'daily':
        return True
    if holiday or day.weekday() == 6:
        return service in ('weekend_holiday', 'sunday_holiday')
    if day.weekday() == 5:
        return service in ('weekend_holiday', 'saturday')
    return service == 'weekday'


class RoutePlanner:
    def __init__(self, csv_dir=ROOT / 'mrt_excel'):
        self.csv_dir = Path(csv_dir)
        self.counts = {}
        self.issues = []
        self.lines = {r['line_id']: r['line_name'] for r in self._read('lines.csv', ('line_id', 'line_name'))}
        self.stops = {}
        for row in self._read('stops.csv', ('stop_id', 'stop_name', 'lat', 'lon', 'line_id')):
            code = row['stop_id']
            lat, lon = float(row['lat']), float(row['lon'])
            if code in self.stops or row['line_id'] not in self.lines:
                raise ValueError(f'車站代碼重複或路線不存在：{code}')
            if not math.isfinite(lat) or not math.isfinite(lon) or not (-90 <= lat <= 90 and -180 <= lon <= 180):
                raise ValueError(f'車站座標無效：{code}')
            self.stops[code] = {'id': code, 'name': row['stop_name'], 'line_id': row['line_id'],
                                'line_name': self.lines[row['line_id']], 'lat': lat, 'lon': lon}
        self.code_lookup = {normalize(code): code for code in self.stops}
        self.rides = {}
        self.adjacency = defaultdict(list)
        duplicates = 0
        for row in self._read('route_edges.csv', ('from_stop_id', 'to_stop_id', 'travel_time_s')):
            a, b = self._pair(row)
            seconds = self._seconds(row['travel_time_s'])
            if seconds == 0 or self.stops[a]['line_id'] != self.stops[b]['line_id']:
                raise ValueError(f'行駛路段無效：{a} → {b}')
            if (a, b) in self.rides:
                if self.rides[a, b] != seconds:
                    raise ValueError(f'同一路段有不同秒數：{a} → {b}')
                duplicates += 1
                continue
            self.rides[a, b] = seconds
            self.adjacency[a].append((b, seconds))
        if duplicates:
            self.issues.append(f'行駛表有 {duplicates} 筆同方向、同秒數的重複路段，載入時去重。')
        self.transfers = defaultdict(list)
        self.branch_walk = {}
        seen = {}
        for row in self._read('transfer_walking.csv', ('from_stop_id', 'to_stop_id', 'transfer_time_s')):
            a, b = self._pair(row)
            seconds = self._seconds(row['transfer_time_s'])
            if (a, b) in seen:
                if seen[a, b] != seconds:
                    raise ValueError(f'轉乘秒數衝突：{a} → {b}')
                continue
            seen[a, b] = seconds
            # 舊轉乘表以支線終點代碼表示換月台；不可變成走到終點的捷徑。
            if {a, b} == {'R22', 'R22A'}:
                self.branch_walk['R', 'R-3'] = seen.get(('R22', 'R22A'), 0)
                self.branch_walk['R-3', 'R'] = seen.get(('R22A', 'R22'), 0)
            elif {a, b} == {'G03', 'G03A'}:
                self.branch_walk['G', 'G-3'] = seen.get(('G03', 'G03A'), 0)
                self.branch_walk['G-3', 'G'] = seen.get(('G03A', 'G03'), 0)
            elif (a, b) in self.rides:
                raise ValueError(f'轉乘和行駛路段重疊，請確認：{a} → {b}')
            else:
                self.transfers[a].append((b, seconds))
        self.fares = {}
        for row in self._read('fares.csv', ('from_stop_id', 'to_stop_id', 'fare_twd')):
            pair = self._pair(row)
            value = self._seconds(row['fare_twd'])
            if pair in self.fares and self.fares[pair] != value:
                raise ValueError(f'票價重複且不同：{pair}')
            self.fares[pair] = value
        self.timetables = defaultdict(lambda: defaultdict(set))
        self.patterns = defaultdict(list)
        invalid_departures = 0
        for row in self._read('station_departures.csv', ('route_id', 'stop_id', 'destination_stop_id',
                                                        'service_type', 'departure_time', 'departure_day_offset')):
            a = self._code(row['stop_id'])
            b = self._code(row['destination_stop_id'])
            route = row['route_id']
            service = row['service_type']
            if service not in SERVICE_TYPES:
                raise ValueError(f'無法識別的班表日別：{service}')
            if a == b:
                invalid_departures += 1
                continue
            # 使用者已確認機場捷運平假日相同，僅將機捷 unspecified 視為每日適用。
            if service == 'unspecified' and self.stops[a]['line_id'] == 'A':
                service = 'daily'
            elif service == 'unspecified':
                invalid_departures += 1
                continue
            hour, minute = map(int, row['departure_time'].split(':'))
            offset = int(row['departure_day_offset'])
            if not (0 <= hour < 24 and 0 <= minute < 60 and offset in (0, 1)):
                raise ValueError(f'發車時間格式無效：{row}')
            self.timetables[route, a, b][service].add(offset * 86400 + hour * 3600 + minute * 60)
        for key in self.timetables:
            route, start, destination = key
            path = self._line_path(start, destination)
            if not path:
                raise ValueError(f'班表方向缺少行駛路段：{key}')
            self.patterns[start].append({'key': key, 'route_id': route, 'family': self._family(route),
                                         'destination': destination, 'path': path})
        # 缺班表的路線仍提供純行駛時間備援，但不宣稱已計算候車或抵達時間。
        scheduled_lines = {self.stops[a]['line_id'] for _r, a, _b in self.timetables}
        self.unscheduled_lines = sorted(set(self.lines) - scheduled_lines)
        for line in self.unscheduled_lines:
            terminals = [code for code, stop in self.stops.items() if stop['line_id'] == line
                         and len(self.adjacency[code]) == 1]
            for start, stop in self.stops.items():
                if stop['line_id'] != line:
                    continue
                for destination in terminals:
                    if destination == start:
                        continue
                    path = self._line_path(start, destination)
                    if path:
                        self.patterns[start].append({'key': None, 'route_id': line, 'family': line,
                                                     'destination': destination, 'path': path})
        if invalid_departures:
            self.issues.append(f'{invalid_departures} 筆無法辨識方向或日別的班次未用於查詢。')
        self.issues.extend([
            '環狀線與北捷間的跨線票價若未收錄，顯示票價待補。',
            '機場捷運 unspecified 班表依使用者確認，視為平日、假日相同；現有路段不含直達車專用行駛時間。',
        ])

    def _read(self, filename, required):
        with (self.csv_dir / filename).open(encoding='utf-8-sig', newline='') as handle:
            reader = csv.DictReader(handle)
            if not set(required) <= set(reader.fieldnames or ()):
                raise ValueError(f'{filename} 缺少必要欄位')
            rows = []
            for number, row in enumerate(reader, 2):
                extra = row.pop(None, [])
                if any(str(v).strip() for v in extra):
                    raise ValueError(f'{filename} 第 {number} 行有多餘欄位')
                if any(row.get(k) is None or not row[k].strip() for k in required):
                    raise ValueError(f'{filename} 第 {number} 行缺少內容')
                rows.append({k: v.strip() if isinstance(v, str) else v for k, v in row.items()})
        self.counts[filename] = len(rows)
        return rows

    @staticmethod
    def _seconds(value):
        seconds = int(value)
        if seconds < 0:
            raise ValueError('秒數／金額不得為負數')
        return seconds

    def _code(self, value):
        code = self.code_lookup.get(normalize(value))
        if code is None:
            raise ValueError(f'表格引用了不存在的站碼：{value}')
        return code

    def _pair(self, row):
        return self._code(row['from_stop_id']), self._code(row['to_stop_id'])

    @staticmethod
    def _family(route):
        return route if route in ('R-3', 'G-3', 'O-1', 'O-2') else route.split('-')[0]

    @lru_cache(maxsize=8192)
    def _line_path(self, start, destination):
        """沿同一路線資料找站序，不穿越任何轉乘連接。"""
        queue = [(0, start, (start,))]
        seen = set()
        while queue:
            cost, stop, path = heapq.heappop(queue)
            if stop in seen:
                continue
            seen.add(stop)
            if stop == destination:
                return path
            for nxt, seconds in self.adjacency[stop]:
                if nxt not in seen:
                    heapq.heappush(queue, (cost + seconds, nxt, path + (nxt,)))
        return ()

    def catalog(self):
        return {'stops': list(self.stops.values()), 'lines': self.lines, 'files': self.counts,
                'issues': self.issues, 'unscheduled_lines': self.unscheduled_lines}

    def resolve(self, value):
        if not isinstance(value, str) or len(value) > 100:
            raise QueryError('請輸入有效站名或站碼。')
        code = self.code_lookup.get(normalize(value))
        if code:
            return code
        found = [code for code, s in self.stops.items() if normalize(s['name']) == normalize(value)]
        if len(found) == 1:
            return found[0]
        if found:
            choices = '、'.join(f'{c} {self.stops[c]["line_name"]}' for c in found)
            raise QueryError(f'{value} 有多個搭乘位置，請選擇站碼：{choices}')
        raise QueryError(f'找不到「{value}」，請從站名建議清單選擇。')

    def _branch_seconds(self, stop, previous, family):
        if stop in ('R22', 'G03'):
            return self.branch_walk.get((previous, family), 0)
        return 0

    # _search()：搜尋路線與轉乘
    def _search(self, origin, destination, start_time, timed, holiday=False):
        base = datetime.combine(start_time.date(), datetime.min.time())
        start_seconds = int((start_time - base).total_seconds())
        horizon = start_seconds + 86400
        next_times = {}

        def departures(pattern):
            key = pattern['key']
            if key not in next_times:
                values = set()
                for offset in (-1, 0, 1):
                    day = base.date() + timedelta(days=offset)
                    for service, times in self.timetables.get(key, {}).items():
                        if service_matches(service, day, holiday and offset == 0):
                            values.update(offset * 86400 + second for second in times)
                next_times[key] = sorted(values)
            return next_times[key]

        initial = (origin, '')
        best = {initial: (start_seconds, 0, 0)}
        parents = {}
        counter = itertools.count()
        queue = [(best[initial], next(counter), initial)]
        target = None

        def relax(state, cost, parent, step):
            if cost[0] <= horizon and (state not in best or cost < best[state]):
                best[state] = cost
                parents[state] = (parent, step)
                heapq.heappush(queue, (cost, next(counter), state))

        while queue:
            cost, _, state = heapq.heappop(queue)
            if best.get(state) != cost:
                continue
            stop, previous = state
            now, boardings, walks = cost
            if stop == destination:
                target = state
                break
            for nxt, seconds in self.transfers[stop]:
                relax((nxt, previous), (now + seconds, boardings, walks + 1), state,
                      {'type': 'walk', 'from_id': stop, 'to_id': nxt, 'duration_s': seconds,
                       'start_s': now, 'end_s': now + seconds})
            for pattern in self.patterns[stop]:
                if timed and pattern['key'] is None:
                    continue
                family = pattern['family']
                branch = self._branch_seconds(stop, previous, family)
                ready = now + branch
                if timed:
                    options = departures(pattern)
                    # 找下一班發車時間、計算候車
                    index = bisect_left(options, ready)
                    if index == len(options):
                        continue
                    departure = options[index]
                else:
                    departure = ready
                ride_seconds = 0
                path = pattern['path']
                # 沿目的站方向累加行駛時間
                for index in range(1, len(path)):
                    ride_seconds += self.rides[path[index-1], path[index]]
                    nxt = path[index]
                    arrival = departure + ride_seconds
                    relax((nxt, family), (arrival, boardings + 1, walks), state,
                          {'type': 'ride', 'from_id': stop, 'to_id': nxt, 'path': list(path[:index+1]),
                           'line_id': self.stops[stop]['line_id'], 'route_id': pattern['route_id'],
                           'family': family, 'direction_id': pattern['destination'],
                           'ride_s': ride_seconds, 'wait_s': departure - ready if timed else None,
                           'branch_walk_s': branch, 'ready_s': now,
                           'start_s': departure, 'end_s': arrival})
        if target is None:
            return None
        steps = []
        while target != initial:
            target, step = parents[target]
            steps.append(step)
        steps.reverse()
        return steps, base

    def _fare(self, steps, fare_mode='full_fare'):
        transfer_pairs = ((a, b) for a, targets in self.transfers.items() for b, _ in targets)
        return FareCalculator(self.fares, self.stops, transfer_pairs).calculate(steps, fare_mode)

    def query(self, origin, destination, departure_at, holiday=False, fare_mode='full_fare'):
        if not isinstance(fare_mode, str) or fare_mode not in FARE_MODES:
            raise QueryError('票價模式須為 full_fare 或 stored_value。')
        origin, destination = self.resolve(origin), self.resolve(destination)
        try:
            if not isinstance(departure_at, str) or len(departure_at) != 16:
                raise ValueError
            start_time = datetime.strptime(departure_at, '%Y-%m-%dT%H:%M')
        except (ValueError, TypeError):
            raise QueryError('出發時間請使用 YYYY-MM-DDTHH:MM（臺灣時間）。') from None
        if type(holiday) is not bool:
            raise QueryError('假日設定必須為布林值。')
        result = self._search(origin, destination, start_time, True, holiday)
        status = 'ok'
        if result is None:
            result = self._search(origin, destination, start_time, False)
            if result is None:
                raise QueryError('現有路段與轉乘資料無法連接這兩站。')
            missing = any(s['type'] == 'ride' and s['line_id'] in self.unscheduled_lines for s in result[0])
            status = 'schedule_incomplete' if missing else 'no_departure'
        steps, base = result
        rides = [s for s in steps if s['type'] == 'ride']
        timetable_estimated = any(s['route_id'].startswith('BR-EST-') for s in rides)
        ride_s = sum(s['ride_s'] for s in rides)
        walk_s = sum(s['duration_s'] for s in steps if s['type'] == 'walk') + sum(s['branch_walk_s'] for s in rides)
        wait_s = sum(s['wait_s'] or 0 for s in rides) if status == 'ok' else None

        def iso(seconds):
            return (base + timedelta(seconds=seconds)).isoformat(timespec='seconds')

        output = []
        for step in steps:
            item = dict(step)
            item.update(from_stop=self.stops[step['from_id']], to_stop=self.stops[step['to_id']])
            item['departure_at'] = iso(step['start_s']) if status == 'ok' else None
            item['arrival_at'] = iso(step['end_s']) if status == 'ok' else None
            if step['type'] == 'ride':
                item['line_name'] = {'R-3': '新北投支線', 'G-3': '小碧潭支線'}.get(step['family'], self.lines[step['line_id']])
                item['timetable_estimated'] = step['route_id'].startswith('BR-EST-')
                item['direction_name'] = self.stops[step['direction_id']]['name']
                item['stops'] = [self.stops[code] for code in step['path']]
            output.append(item)
        warnings = []
        if timetable_estimated:
            warnings.append('文湖線班次依使用者提供的班距及兩端首末班推算：平日尖峰 3 分鐘、離峰與假日 7 分鐘、23:00 後 12 分鐘；不是官方逐班時刻。沿途時刻按行駛秒數向上取整至分鐘，未含途中停站或中途站始發列車。')
        if status == 'schedule_incomplete':
            warnings.append('路線包含尚未提供班表的車站，目前只能提供行駛＋轉乘時間，候車及抵達時間待補。')
        elif status == 'no_departure':
            warnings.append('指定時間後 24 小時內無法組成完整班次；下列僅為路網參考路線。')
        if self.unscheduled_lines and status == 'ok' and rides:
            warnings.append('文湖線班表待補；最早抵達結果僅比較已有班表的路線。')
        if any(s['line_id'] == 'A' for s in rides):
            warnings.append('機捷按平假日相同班表與現有逐站行駛時間估算，未計入直達車專用路段。')
        if rides:
            warnings.append('依各站發車表及路段秒數估算，未含資料未提供的途中停站時間、進出站步行；非即時列車資訊。')
        arrival = output[-1]['arrival_at'] if output else start_time.isoformat(timespec='seconds')
        return {'status': status, 'origin': self.stops[origin], 'destination': self.stops[destination],
                'timetable_estimated': timetable_estimated,
                'departure_at': start_time.isoformat(timespec='seconds'), 'arrival_at': arrival if status == 'ok' else None,
                'ride_s': ride_s, 'walk_s': walk_s, 'wait_s': wait_s,
                # 加總行駛＋步行＋候車時間
                'total_s': ride_s + walk_s + wait_s if wait_s is not None else None,
                'known_duration_s': ride_s + walk_s, 'transfer_count': max(0, len(rides) - 1),
                'stop_count': sum(len(s['path']) - 1 for s in rides), 'steps': output,
                'fare': self._fare(steps, fare_mode), 'warnings': warnings}
