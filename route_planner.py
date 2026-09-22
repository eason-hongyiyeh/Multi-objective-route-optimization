"""讀取捷運資料、建立時間成本，並以終端機查詢最短時間路線。"""
import argparse
import csv
from dataclasses import dataclass
import difflib
import math
from pathlib import Path
import sys
from time import perf_counter
import unicodedata

from dijkstra import Transition, dijkstra
from astar import astar
from bfs import bfs
from floyd_warshall import floyd_warshall
from k_shortest_paths import k_shortest_paths
from brute_force import brute_force


DATA_DIR = Path(__file__).resolve().parent / 'taipei_mrt'
ALGORITHMS = {
    'dijkstra': ('Dijkstra', dijkstra),
    'astar': ('A*', astar),
    'bfs': ('BFS（最少邊數，不保證最短時間）', bfs),
    'floyd-warshall': ('Floyd–Warshall', floyd_warshall),
    'k-shortest': ('K-shortest paths（Yen）', k_shortest_paths),
    'brute-force': ('Brute force（DFS 窮舉＋剪枝）', brute_force),
}


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
    transfer_seconds: int = 0
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


BRANCH_TRANSFER_TIMES = {
    '新北投支線換車': 180,
    '小碧潭支線換車': 180,
    '迴龍方向與蘆洲方向換車': 60,
    '同線換向': 180,
}


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
        for row in read_csv(data_dir / 'route_edges.csv'):
            source, target = row['from_stop_id'], row['to_stop_id']
            if source not in self.stops or target not in self.stops:
                raise ValueError(f'route_edges.csv 引用不存在的站碼：{source} → {target}')
            if (source, target) in seen:
                raise ValueError(f'重複路段：{source} → {target}')
            seen.add((source, target))
            seconds = int(row['travel_time_s'])
            if seconds <= 0:
                raise ValueError(f'行駛時間必須大於零：{source} → {target}')
            self.graph[source].append(Edge(target, seconds, 0, False))

        transfer_file = data_dir / 'transfer_walking.csv'
        if not transfer_file.exists():
            transfer_file = data_dir / 'transfers.csv'
        self.transfer_times = {}
        for row in read_csv(transfer_file):
            source, target = row['from_stop_id'], row['to_stop_id']
            # 環狀線尚未納入主線路網。
            if source not in self.stops or target not in self.stops:
                continue
            transfer_sec = int(row.get('transfer_time_s', 180))
            if transfer_sec < 0:
                raise ValueError(f'轉乘時間不可為負數：{source} → {target}')
            self.transfer_times[source, target] = transfer_sec
            # 支線換車時間另行套用，不能把既有行車邊改成步行邊。
            if source == target or (source, target) in seen:
                continue
            if normalize(self.stops[source].name) != normalize(self.stops[target].name):
                raise ValueError(f'轉乘邊必須位於同一車站：{source} → {target}')
            seen.add((source, target))
            self.graph[source].append(Edge(target, 0, transfer_sec, True))
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

    def _step(self, previous, current, edge, transfer_seconds):
        if edge.is_transfer:
            note = f'{self.lines[self.stops[current].line_id]} → {self.lines[self.stops[edge.target].line_id]}'
            default_time = edge.transfer_seconds
        else:
            note = branch_change(previous, current, edge.target)
            default_time = BRANCH_TRANSFER_TIMES.get(note, 180) if note else 0
            if note:
                key = (current, current)
                for junction, branch in [('R22', 'R22A'), ('G03', 'G03A')]:
                    if current == junction:
                        key = (branch, current) if previous == branch else (current, branch)
                default_time = self.transfer_times.get(key, default_time)
        extra = default_time if transfer_seconds is None else (transfer_seconds if note else 0)
        return Step(current, edge.target, edge.ride_seconds, extra, note)

    def _journey(self, source, target, steps):
        if (source, target) not in self.fares:
            raise ValueError(f'缺少起訖站票價：{source} → {target}。')
        return Journey(source, target, tuple(steps), self.fares[source, target])

    def build_search_graph(self, transfer_seconds=None):
        """統一套用捷運規則，讓不同演算法使用相同狀態與成本。"""
        if transfer_seconds is not None and (not isinstance(transfer_seconds, int) or transfer_seconds < 0):
            raise ValueError('轉乘秒數須為非負整數。')
        # 保留到達方向，才能計入同線支線換車；空字串代表剛進站或轉乘。
        states = {(stop_id, '') for stop_id in self.stops}
        for source, edges in self.graph.items():
            for edge in edges:
                if not edge.is_transfer:
                    states.add((edge.target, source))
        graph = {}
        for current, previous in sorted(states):
            transitions = []
            for edge in self.graph[current]:
                step = self._step(previous, current, edge, transfer_seconds)
                target = (edge.target, '' if edge.is_transfer else current)
                cost = (step.ride_seconds + step.transfer_seconds,
                        int(bool(step.transfer_note)), int(not edge.is_transfer))
                transitions.append(Transition(target, cost, step))
            graph[current, previous] = tuple(transitions)
        return graph

    def shortest_time(self, start_query, end_query, transfer_seconds=None, *, algorithm=dijkstra):
        """預設用 Dijkstra；algorithm 可替換成具有相同介面的搜尋函式。"""
        starts = self.resolve(start_query)
        ends = set(self.resolve(end_query))
        graph = self.build_search_graph(transfer_seconds)
        result = algorithm(graph, [(source, '') for source in starts],
                           {state for state in graph if state[0] in ends})
        if result is None:
            raise ValueError('現有路網找不到可達路線。')
        return self.journey_from_result(result)

    def journey_from_result(self, result):
        source, target = result.nodes[0][0], result.nodes[-1][0]
        if not result.edges:
            return Journey(source, target, (), 0)
        return self._journey(source, target, [edge.data for edge in result.edges])

    def compare(self, start_query, end_query, transfer_seconds=None, *, algorithms=None, k=3):
        """建一次路網，各演算法共用相同輸入；計時含演算法前處理。"""
        starts = [(source, '') for source in self.resolve(start_query)]
        ends = set(self.resolve(end_query))
        graph = self.build_search_graph(transfer_seconds)
        goals = {state for state in graph if state[0] in ends}
        reports = []
        for name in (ALGORITHMS if algorithms is None else algorithms):
            label, search = ALGORITHMS[name]
            begun = perf_counter()
            try:
                if name == 'k-shortest':
                    results = search(graph, starts, goals, k=1 if set(starts) & goals else k)
                else:
                    result = search(graph, starts, goals)
                    results = [] if result is None else [result]
                elapsed = perf_counter() - begun
                reports.append({'name': name, 'label': label, 'results': results,
                                'journeys': [self.journey_from_result(r) for r in results],
                                'elapsed': elapsed, 'error': None})
            except RuntimeError as error:
                reports.append({'name': name, 'label': label, 'results': [],
                                'journeys': [], 'elapsed': perf_counter() - begun, 'error': str(error)})
        return reports


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
    print(f'預估旅程時間：{duration(journey.total_seconds)}')
    print(f'  行駛：{duration(journey.ride_seconds)}；轉乘估算：{duration(journey.transfer_seconds)}')
    print(f'轉乘／換車：{journey.transfer_count} 次')
    for step in journey.steps:
        if step.transfer_note:
            print(f'  {planner.stops[step.source].name}：{step.transfer_note}')
    print(f'票價：NT$ {journey.fare_twd}')
    if not journey.steps:
        print('起終點是同一站，視為不搭車；不是同站刷卡進出的票價。')
    print()


def display_comparison(planner, reports):
    baseline_report = next((report for name in ('brute-force', 'dijkstra') for report in reports
                            if report['name'] == name and report['results']), None)
    baseline = baseline_report['results'][0].cost if baseline_report else None
    baseline_label = baseline_report['label'] if baseline_report else '對照組'
    for report in reports:
        print(f"\n=== {report['label']} ===")
        print(f"計算耗時：{report['elapsed'] * 1000:.3f} ms")
        if report['error']:
            print(report['error'])
            continue
        if not report['results']:
            print('現有路網找不到可達路線。')
        for index, journey in enumerate(report['journeys'], 1):
            if report['name'] == 'k-shortest':
                print(f'第 {index} 條路線')
            display(planner, journey)
    print(f'比較摘要（旅程時間／票價／換車次數／與 {baseline_label} 時間差）')
    for report in reports:
        if report['error']:
            print(f"{report['label']}：未執行完成")
        for index, (result, journey) in enumerate(zip(report['results'], report['journeys']), 1):
            suffix = f' #{index}' if report['name'] == 'k-shortest' else ''
            difference = f'{result.cost[0] - baseline[0]:+d} 秒' if baseline is not None else '未比較'
            print(f"{report['label']}{suffix}：{duration(journey.total_seconds)}／"
                  f"NT$ {journey.fare_twd}／{journey.transfer_count} 次／{difference}")
            if (baseline is not None and report['name'] not in {baseline_report['name'], 'bfs'}
                    and index == 1):
                print(f'  時間、換車次數及行駛路段數與 {baseline_label} 一致。' if result.cost == baseline
                      else f'  注意：最短成本與 {baseline_label} 不一致，需檢查。')


def positive_int(value):
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError('k 必須是正整數。') from None
    if number < 1:
        raise argparse.ArgumentTypeError('k 必須是正整數。')
    return number


def transfer_minutes(value):
    try:
        minutes = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError('轉乘分鐘數須為非負數。') from None
    if not math.isfinite(minutes) or minutes < 0 or minutes > 1440:
        raise argparse.ArgumentTypeError('轉乘分鐘數須介於 0 與 1440。')
    return math.floor(minutes * 60 + 0.5)


def main(argv=None):
    parser = argparse.ArgumentParser(description='比較捷運路徑演算法的路線、時間與票價。')
    parser.add_argument('--start', help='起站名稱或站碼')
    parser.add_argument('--end', help='終站名稱或站碼')
    parser.add_argument('--algorithm', choices=['all', *ALGORITHMS], default='all',
                        help='選擇演算法；預設 all 一次比較全部')
    parser.add_argument('--k', type=positive_int, default=3, help='K-shortest 最多列出幾條路線（預設 3）')
    parser.add_argument('--transfer-minutes', type=transfer_minutes, default=None,
                        metavar='MINUTES', help='自訂每次轉乘／換車的估算分鐘數；設為 0 可比較純行駛時間（預設使用轉乘 CSV 秒數）')
    args = parser.parse_args(argv)
    if (args.start is None) != (args.end is None):
        parser.error('--start 和 --end 必須一起提供。')
    try:
        planner = Planner()
    except (OSError, ValueError, KeyError) as error:
        print(f'無法載入捷運資料：{error}', file=sys.stderr)
        return 1
    print('捷運路徑演算法比較')
    if args.transfer_minutes is None:
        print('轉乘／換車採用轉乘 CSV 的步行秒數，未提供時使用預設估算；不含候車、停站及進出站時間。')
    else:
        print(f'每次轉乘／換車估算 {duration(args.transfer_minutes)}；不含候車、停站及進出站步行時間。')
    def run_query(start, end):
        selected = None if args.algorithm == 'all' else [args.algorithm]
        reports = planner.compare(start, end, args.transfer_minutes, algorithms=selected, k=args.k)
        display_comparison(planner, reports)
        return 1 if any(r['error'] or not r['results'] for r in reports) else 0

    if args.start is not None:
        try:
            return run_query(args.start, args.end)
        except ValueError as error:
            print(error, file=sys.stderr)
            return 1
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
                run_query(start, end)
            except ValueError as error:
                print(error)
    except (EOFError, KeyboardInterrupt):
        print()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
