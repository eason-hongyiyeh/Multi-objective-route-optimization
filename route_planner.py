"""以本地 CSV 查詢捷運最短時間路線；只使用 Python 標準函式庫。"""
import argparse
import csv
from dataclasses import dataclass
import difflib
import heapq
from itertools import count
import math
from pathlib import Path
import sys
import unicodedata


DATA_DIR = Path(__file__).resolve().parent / 'taipei_mrt'


def normalize(text):
    return ''.join(unicodedata.normalize('NFKC', text).split()).replace('臺', '台').upper()


@dataclass(frozen=True)
class Stop:
    stop_id: str
    name: str
    line_id: str


@dataclass(frozen=True)
class Edge:
    target: str
    ride_seconds: int
    is_transfer: bool = False


@dataclass(frozen=True)
class Step:
    source: str
    target: str
    ride_seconds: int
    transfer_seconds: int
    transfer_note: str = ''


@dataclass(frozen=True)
class Journey:
    start: str
    end: str
    steps: tuple
    fare_twd: int

    @property
    def ride_seconds(self):
        return sum(step.ride_seconds for step in self.steps)

    @property
    def transfer_seconds(self):
        return sum(step.transfer_seconds for step in self.steps)

    @property
    def total_seconds(self):
        return self.ride_seconds + self.transfer_seconds

    @property
    def transfer_count(self):
        return sum(bool(step.transfer_note) for step in self.steps)


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


def branch_change(previous, current, target):
    """同線換向或支線換車；起站直接上車不計轉乘。"""
    if not previous:
        return ''
    if target == previous:
        return '同線換向'
    for junction, branch, label in [('R22', 'R22A', '新北投支線換車'),
                                    ('G03', 'G03A', '小碧潭支線換車')]:
        if current == junction and ((previous == branch) != (target == branch)):
            return label
    if current == 'O12' and {previous, target} == {'O13', 'O50'}:
        return '迴龍方向與蘆洲方向換車'
    return ''


class Planner:
    def __init__(self, data_dir=DATA_DIR):
        data_dir = Path(data_dir)
        self.stops = {}
        self.names = {}
        for row in read_csv(data_dir / 'stops.csv'):
            stop = Stop(row['stop_id'], row['stop_name'], row['line_id'])
            if stop.stop_id in self.stops:
                raise ValueError(f'重複站碼：{stop.stop_id}')
            self.stops[stop.stop_id] = stop
            self.names.setdefault(normalize(stop.name), []).append(stop.stop_id)
        self.lines = {r['line_id']: r['line_name'] for r in read_csv(data_dir / 'lines.csv')}
        self.graph = {stop_id: [] for stop_id in self.stops}
        seen = set()
        for filename, transfer in [('route_edges.csv', False), ('transfers.csv', True)]:
            for row in read_csv(data_dir / filename):
                source, target = row['from_stop_id'], row['to_stop_id']
                if source not in self.stops or target not in self.stops:
                    raise ValueError(f'{filename} 引用不存在的站碼：{source} → {target}')
                if (source, target) in seen:
                    raise ValueError(f'重複路段：{source} → {target}')
                seen.add((source, target))
                seconds = 0 if transfer else int(row['travel_time_s'])
                if not transfer and seconds <= 0:
                    raise ValueError(f'行駛時間必須大於零：{source} → {target}')
                if transfer and normalize(self.stops[source].name) != normalize(self.stops[target].name):
                    raise ValueError(f'轉乘邊必須位於同一車站：{source} → {target}')
                self.graph[source].append(Edge(target, seconds, transfer))
        self.fares = {}
        for row in read_csv(data_dir / 'fares.csv'):
            key = (row['from_stop_id'], row['to_stop_id'])
            fare = int(row['fare_twd'])
            if key in self.fares or fare < 0 or any(code not in self.stops for code in key):
                raise ValueError(f'票價資料有誤：{key}')
            self.fares[key] = fare

    def resolve(self, query):
        key = normalize(query)
        # 站碼也視為整座車站；起點自動選擇搭乘路線，不先收取轉乘時間。
        if key in self.stops:
            key = normalize(self.stops[key].name)
        if key not in self.names and key.endswith('站'):
            key = key[:-1]
        if key not in self.names:
            matches = difflib.get_close_matches(key, self.names, n=3, cutoff=0.4)
            hint = '，可能是：' + '、'.join(self.stops[self.names[k][0]].name for k in matches) if matches else ''
            raise ValueError(f'找不到車站「{query}」{hint}。請輸入站名或完整站碼。')
        return tuple(sorted(self.names[key]))

    def shortest_time(self, start_query, end_query, transfer_seconds=180):
        if not isinstance(transfer_seconds, int) or transfer_seconds < 0:
            raise ValueError('轉乘秒數須為非負整數。')
        starts, ends = self.resolve(start_query), set(self.resolve(end_query))
        shared = set(starts) & ends
        if shared:
            station = min(shared)
            return Journey(station, station, (), 0)
        # 狀態包含從哪一站抵達，以正確計算同線支線換車和換向。
        serial = count()
        best, parents, queue = {}, {}, []
        for source in starts:
            state = (source, '')
            best[state] = (0, 0, 0)  # 總秒數、換車次數、行駛路段數
            heapq.heappush(queue, (best[state], next(serial), state))
        final = None
        while queue:
            cost, _, state = heapq.heappop(queue)
            if best[state] != cost:
                continue
            current, previous = state
            if current in ends:
                final = state
                break
            for edge in self.graph[current]:
                if edge.is_transfer:
                    note = f'{self.lines[self.stops[current].line_id]} → {self.lines[self.stops[edge.target].line_id]}'
                else:
                    note = branch_change(previous, current, edge.target)
                extra = transfer_seconds if note else 0
                step = Step(current, edge.target, edge.ride_seconds, extra, note)
                candidate = (cost[0] + edge.ride_seconds + extra,
                             cost[1] + bool(note), cost[2] + (not edge.is_transfer))
                target_state = (edge.target, '' if edge.is_transfer else current)
                if target_state not in best or candidate < best[target_state]:
                    best[target_state] = candidate
                    parents[target_state] = (state, step)
                    heapq.heappush(queue, (candidate, next(serial), target_state))
        if final is None:
            raise ValueError('現有路網找不到可達路線。')
        steps = []
        state = final
        while state in parents:
            state, step = parents[state]
            steps.append(step)
        steps.reverse()
        source, target = state[0], final[0]
        if (source, target) not in self.fares:
            raise ValueError(f'缺少起訖站票價：{source} → {target}。')
        return Journey(source, target, tuple(steps), self.fares[source, target])


def duration(seconds):
    minutes, seconds = divmod(seconds, 60)
    return f'{minutes} 分 {seconds:02d} 秒'


def display(planner, journey):
    names = [planner.stops[journey.start].name]
    for step in journey.steps:
        name = planner.stops[step.target].name
        if name != names[-1]:
            names.append(name)
    print('\n路線：' + ' → '.join(names))
    print(f'預估最短時間：{duration(journey.total_seconds)}')
    print(f'  行駛：{duration(journey.ride_seconds)}；轉乘估算：{duration(journey.transfer_seconds)}')
    print(f'轉乘／換車：{journey.transfer_count} 次')
    for step in journey.steps:
        if step.transfer_note:
            print(f'  {planner.stops[step.source].name}：{step.transfer_note}')
    print(f'票價：NT$ {journey.fare_twd}')
    if not journey.steps:
        print('起終點是同一站，視為不搭車；不是同站刷卡進出的票價。')
    print()


def transfer_minutes(value):
    try:
        minutes = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError('轉乘分鐘數須為非負數。') from None
    if not math.isfinite(minutes) or minutes < 0 or minutes > 1440:
        raise argparse.ArgumentTypeError('轉乘分鐘數須介於 0 與 1440。')
    return math.floor(minutes * 60 + 0.5)


def main(argv=None):
    parser = argparse.ArgumentParser(description='查詢本地捷運資料中的最短時間路線與起訖票價。')
    parser.add_argument('--start', help='起站名稱或站碼')
    parser.add_argument('--end', help='終站名稱或站碼')
    parser.add_argument('--transfer-minutes', type=transfer_minutes, default=180,
                        metavar='MINUTES', help='每次轉乘／換車的估算分鐘數，預設 3；設為 0 可比較純行駛時間')
    args = parser.parse_args(argv)
    if (args.start is None) != (args.end is None):
        parser.error('--start 和 --end 必須一起提供。')
    try:
        planner = Planner()
    except (OSError, ValueError, KeyError) as error:
        print(f'無法載入捷運資料：{error}', file=sys.stderr)
        return 1
    print('捷運最短時間查詢（本地 CSV）')
    print(f'每次轉乘／換車估算 {duration(args.transfer_minutes)}；不含候車、停站及進出站步行時間。')
    print('票價讀取本地 fares.csv 的起訖票價，不逐段相加。')
    print('票價資料期間：2026-08-30～2026-09-28（含廣慈／奉天宮期間優惠）。')
    if args.start is not None:
        try:
            display(planner, planner.shortest_time(args.start, args.end, args.transfer_minutes))
        except ValueError as error:
            print(error, file=sys.stderr)
            return 1
        return 0
    print('輸入站名或站碼（如：西門、BL11）；輸入 q 離開，輸入 list 列出站名。')
    try:
        while True:
            start = input('\n起站：').strip()
            if start.lower() in {'q', 'quit', 'exit'}:
                break
            if start.lower() == 'list':
                print('、'.join(sorted({s.name for s in planner.stops.values()})))
                continue
            try:
                planner.resolve(start)
            except ValueError as error:
                print(error)
                continue
            end = input('終站：').strip()
            if end.lower() in {'q', 'quit', 'exit'}:
                break
            try:
                display(planner, planner.shortest_time(start, end, args.transfer_minutes))
            except ValueError as error:
                print(error)
    except (EOFError, KeyboardInterrupt):
        print()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
