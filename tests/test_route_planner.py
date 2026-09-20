import contextlib
import io
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from route_planner import Edge, Planner, Stop, main


class PlannerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.planner = Planner()

    def test_station_names_codes_and_variants(self):
        p = self.planner
        self.assertEqual(p.resolve(' 臺北車站 '), ('BL12', 'R10'))
        self.assertEqual(p.resolve('南京復興站'), ('BR11', 'G16'))
        self.assertEqual(p.resolve('br11'), p.resolve('南京復興'))
        self.assertNotEqual(p.resolve('BR11'), p.resolve('BL11'))

    def test_same_physical_station_requires_no_journey(self):
        journey = self.planner.shortest_time('BR11', 'G16')
        self.assertEqual((journey.total_seconds, journey.transfer_count, journey.fare_twd), (0, 0, 0))

    def test_adjacent_stations_and_whole_journey_fare(self):
        p = self.planner
        journey = p.shortest_time('動物園', '木柵')
        self.assertEqual(journey.total_seconds, 67)
        self.assertEqual(journey.transfer_count, 0)
        journey = p.shortest_time('西門', '動物園')
        self.assertEqual(journey.fare_twd, p.fares[journey.start, journey.end])
        self.assertEqual(journey.fare_twd, 35)
        self.assertLess(journey.fare_twd, sum(p.fares[s.source, s.target] for s in journey.steps))

    def test_branch_changes_cannot_be_avoided_by_turning_back(self):
        # A return trip via O11 costs 144 riding seconds; it must still incur a train change.
        for start, end, expected in [('台北橋', '三重國小', 127 + 151 + 180),
                                     ('新北投', '奇岩', 157 + 91 + 180),
                                     ('小碧潭', '新店區公所', 203 + 81 + 180)]:
            with self.subTest(start=start, end=end):
                result = self.planner.shortest_time(start, end)
                self.assertEqual(result.total_seconds, expected)
                self.assertEqual(result.transfer_count, 1)
                self.assertEqual(len(result.steps), 2)
        self.assertEqual(self.planner.shortest_time('北投', '新北投').transfer_count, 0)
        self.assertEqual(self.planner.shortest_time('台北橋', '民權西路').transfer_count, 0)

    def test_time_objective_and_transfer_penalty_change_the_route(self):
        # Fast route takes three train edges and one transfer; slow route has only two edges.
        p = Planner.__new__(Planner)
        p.stops = {key: Stop(key, name, line) for key, name, line in [
            ('A', '起點', 'L'), ('B', '換車', 'L'), ('C', '換車', 'M'),
            ('D', '終點', 'M'), ('E', '繞路', 'L'), ('F', '中途', 'L')]}
        p.names = {'起點': ['A'], '換車': ['B', 'C'], '終點': ['D'], '繞路': ['E'], '中途': ['F']}
        p.lines = {'L': '甲線', 'M': '乙線'}
        p.graph = {'A': [Edge('E', 50), Edge('F', 5)], 'F': [Edge('B', 5)],
                   'B': [Edge('C', 0, True)], 'C': [Edge('D', 10)],
                   'E': [Edge('D', 50)], 'D': []}
        p.fares = {('A', 'D'): 30}
        fast = p.shortest_time('起點', '終點', 0)
        self.assertEqual(fast.total_seconds, 20)
        self.assertEqual(fast.transfer_count, 1)
        slow = p.shortest_time('起點', '終點', 180)
        self.assertEqual(slow.total_seconds, 100)
        self.assertEqual(slow.transfer_count, 0)
        with self.assertRaisesRegex(ValueError, '找不到可達路線'):
            p.shortest_time('終點', '起點')  # Directed edges must not be silently reversed.

    def test_zero_transfer_times_against_independent_floyd_warshall(self):
        p = self.planner
        ids = list(p.stops)
        index = {code: i for i, code in enumerate(ids)}
        n = len(ids)
        distances = [[float('inf')] * n for _ in range(n)]
        for code in ids:
            distances[index[code]][index[code]] = 0
            for edge in p.graph[code]:
                distances[index[code]][index[edge.target]] = edge.ride_seconds
        for k in range(n):
            for i in range(n):
                if distances[i][k] == float('inf'):
                    continue
                for j in range(n):
                    distances[i][j] = min(distances[i][j], distances[i][k] + distances[k][j])
        examples = [('BL01', 'BR01'), ('R22A', 'G03A'), ('O21', 'O54'),
                    ('BR11', 'BL11'), ('R01', 'R28'), ('BR24', 'O01'), ('O10', 'R12')]
        for start, end in examples:
            with self.subTest(start=start, end=end):
                expected = min(distances[index[s]][index[t]] for s in p.resolve(start) for t in p.resolve(end))
                self.assertEqual(p.shortest_time(start, end, 0).total_seconds, expected)

    def test_all_stations_reachable_with_valid_costs(self):
        p = self.planner
        for name in p.names:
            with self.subTest(name=name):
                journey = p.shortest_time('西門', name)
                self.assertEqual(journey.total_seconds, journey.ride_seconds + journey.transfer_count * 180)
                self.assertEqual(p.stops[journey.end].name.replace('臺', '台').upper(), name)
                for step in journey.steps:
                    self.assertTrue(any(e.target == step.target for e in p.graph[step.source]))

    def test_invalid_input_and_missing_fare_are_not_fabricated(self):
        p = self.planner
        with self.assertRaisesRegex(ValueError, '找不到車站'):
            p.shortest_time('基隆', '西門')
        with self.assertRaises(ValueError):
            p.shortest_time('西門', '台北車站', -1)
        with patch.object(p, 'fares', {}):
            with self.assertRaisesRegex(ValueError, '缺少起訖站票價'):
                p.shortest_time('動物園', '木柵')

    def test_interactive_recovery_and_multiple_queries(self):
        output = io.StringIO()
        with patch('builtins.input', side_effect=['不存在的站', '西門', '台北車站', 'list', 'BR01', 'BR02', 'q']):
            with contextlib.redirect_stdout(output):
                self.assertEqual(main([]), 0)
        self.assertIn('找不到車站', output.getvalue())
        self.assertEqual(output.getvalue().count('預估最短時間'), 2)

    def test_cli_runs_outside_project_directory(self):
        script = Path(__file__).resolve().parents[1] / 'route_planner.py'
        result = subprocess.run([sys.executable, str(script), '--start', 'BR01', '--end', 'BR02'],
                                cwd=script.parent.parent, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
