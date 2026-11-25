"""圖片案例、站外轉乘邊界與既有路線 API 的全票回歸測試。"""
from copy import deepcopy
from functools import partial
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading
import unittest
from urllib.parse import urlencode
from urllib.request import urlopen
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fare_calculator import FareCalculator
from mrt_map import MapHandler
from route_planner import RoutePlanner
from itinerary_planner import ItineraryPlanner


def ride(a, b, **kwargs):
    return {'type': 'ride', 'from_id': a, 'to_id': b, **kwargs}


def walk(a, b, seconds, **kwargs):
    return {'type': 'walk', 'from_id': a, 'to_id': b, 'duration_s': seconds, **kwargs}


def via_banqiao(seconds=660, **kwargs):
    return [ride('R11', 'R10'), walk('R10', 'BL12', 240),
            ride('BL12', 'BL07'), walk('BL07', 'Y16', seconds, **kwargs),
            ride('Y16', 'Y18')]


def reverse_steps(steps):
    return [{**s, 'from_id': s['to_id'], 'to_id': s['from_id']} for s in reversed(steps)]


def via_sanying(seconds=120, **kwargs):
    return [ride('BL02', 'BL01'), walk('BL01', 'LB01', seconds, **kwargs), ride('LB01', 'LB12')]


class FareTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.planner = RoutePlanner()
        cls.transfer_pairs = {(a, b) for a, targets in cls.planner.transfers.items() for b, _ in targets}

    def assert_fare(self, steps, expected, parts=None):
        result = self.planner._fare(steps)
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['ticket_type'], 'full_fare')
        self.assertEqual(result['discount_twd'], 0)
        self.assertEqual(result['total_twd'], expected)
        if parts is not None:
            self.assertEqual([p['fare_twd'] for p in result['parts']], parts)
        return result

    def test_taipei_internal_transfer_is_one_od(self):
        result = self.assert_fare([ride('BL12', 'BL11'), walk('BL11', 'G12', 120),
                                  ride('G12', 'G14'), walk('G14', 'R11', 180),
                                  ride('R11', 'R15')], 20, [20])
        self.assertEqual((result['parts'][0]['from_id'], result['parts'][0]['to_id']), ('BL12', 'R15'))

    def test_circular_line_internal(self):
        self.assert_fare([ride('Y07', 'Y20')], 40, [40])

    def test_in_station_transfer_to_circular_is_one_od(self):
        steps = [ride('G03', 'G04'), walk('G04', 'Y07', 180), ride('Y07', 'Y08')]
        for route in (steps, reverse_steps(steps)):
            with self.subTest(route=route):
                self.assert_fare(route, 20, [20])

    def test_in_station_transfer_has_no_twenty_minute_rule(self):
        self.assert_fare([ride('G03', 'G04'), walk('G04', 'Y07', 1201), ride('Y07', 'Y08')], 20)

    def test_outside_transfer_within_limit(self):
        for seconds in (660, 1199, 1200):
            for steps in (via_banqiao(seconds), reverse_steps(via_banqiao(seconds))):
                with self.subTest(seconds=seconds, origin=steps[0]['from_id']):
                    result = self.assert_fare(steps, 25, [25])
                    outside = [t for t in result['transfers'] if 'limit_s' in t]
                    self.assertEqual([t['rule'] for t in outside], ['outside_within_limit'])
                    self.assertTrue(result['assumptions'])

    def test_outside_transfer_timeout_splits_full_fares(self):
        for steps in (via_banqiao(1201), reverse_steps(via_banqiao(1201))):
            with self.subTest(origin=steps[0]['from_id']):
                result = self.assert_fare(steps, 50)
                self.assertEqual(sorted(p['fare_twd'] for p in result['parts']), [20, 30])
                self.assertTrue(any(t['rule'] == 'outside_timeout' for t in result['transfers']))

    def test_xinpu_pair_has_same_twenty_minute_rule(self):
        for seconds in (1200, 1201):
            steps = [ride('BL12', 'BL08'), walk('BL08', 'Y17', seconds), ride('Y17', 'Y18')]
            for route in (steps, reverse_steps(steps)):
                with self.subTest(seconds=seconds, origin=route[0]['from_id']):
                    fares = self.planner.fares
                    expected = fares['BL12', 'Y18'] if seconds <= 1200 else fares['BL12', 'BL08'] + fares['Y17', 'Y18']
                    self.assert_fare(route, expected)

    def test_train_wait_is_not_gate_transfer_time(self):
        steps = via_banqiao(660)
        steps[-1]['wait_s'] = 2400
        self.assert_fare(steps, 25)

    def test_provided_gate_interval_takes_precedence(self):
        result = self.assert_fare(via_banqiao(660, gate_elapsed_s=1201), 50)
        self.assertFalse(result['assumptions'])
        self.assertEqual(result['transfers'][-1]['time_basis'], 'gate_interval')
        self.assert_fare(via_banqiao(1500, gate_elapsed_s=1200), 25)

    def test_unknown_gate_interval_does_not_claim_total(self):
        for value in (None, -1, True, '660', float('nan'), float('inf')):
            with self.subTest(value=value):
                result = self.planner._fare(via_banqiao(660, gate_elapsed_s=value))
                self.assertEqual(result['status'], 'missing')
                self.assertIsNone(result['total_twd'])
                self.assertTrue(result['assumptions'])
                json.dumps(result, allow_nan=False)

    def test_missing_estimated_time_does_not_claim_total(self):
        self.assertIsNone(self.planner._fare(via_banqiao(None))['total_twd'])

    def test_airport_internal_and_train_type_do_not_change_fare(self):
        for route_id in ('A-1', 'A-EXPRESS'):
            with self.subTest(route_id=route_id):
                self.assert_fare([ride('A1', 'A22', route_id=route_id)], 155, [155])

    def test_airport_transfer_charges_each_system(self):
        steps = [ride('BL22', 'BL12'), walk('BL12', 'A1', 750), ride('A1', 'A22')]
        self.assert_fare(steps, 185, [30, 155])
        self.assert_fare(reverse_steps(steps), 185, [155, 30])

    def test_sanying_internal(self):
        self.assert_fare([ride('LB01', 'LB12')], 35, [35])

    def test_sanying_transfer_full_fare_without_eight_dollar_discount(self):
        steps = [ride('BL02', 'BL01'), walk('BL01', 'LB01', 120), ride('LB01', 'LB12')]
        for route in (steps, reverse_steps(steps)):
            with self.subTest(origin=route[0]['from_id']):
                result = self.assert_fare(route, 55)
                self.assertEqual({p['system'] for p in result['parts']}, {'metro', 'sanying'})

    def test_metro_airport_metro_are_three_paid_segments(self):
        steps = [ride('BL22', 'BL12'), walk('BL12', 'A1', 750), ride('A1', 'A3'),
                 walk('A3', 'Y20', 300), ride('Y20', 'Y18')]
        values = [self.planner.fares[a,b] for a,b in [('BL22','BL12'),('A1','A3'),('Y20','Y18')]]
        self.assert_fare(steps, sum(values), values)

    def test_missing_od_does_not_sum_intermediate_station_fares(self):
        fares = dict(self.planner.fares)
        del fares['G03', 'Y08']
        calculator = FareCalculator(fares, self.planner.stops, self.transfer_pairs)
        result = calculator.calculate([ride('G03', 'G04'), walk('G04', 'Y07', 180), ride('Y07', 'Y08')])
        self.assertEqual(result['status'], 'missing')
        self.assertIsNone(result['total_twd'])
        self.assertEqual(len(result['parts']), 1)

    def test_missing_one_system_does_not_return_partial_total(self):
        fares = dict(self.planner.fares)
        del fares['LB01', 'LB12']
        result = FareCalculator(fares, self.planner.stops, self.transfer_pairs).calculate([
            ride('BL02', 'BL01'), walk('BL01', 'LB01', 120), ride('LB01', 'LB12')])
        self.assertIsNone(result['total_twd'])
        self.assertEqual(result['parts'][0]['fare_twd'], 20)

    def test_invalid_zero_is_not_a_free_trip(self):
        fares = dict(self.planner.fares)
        fares['R01', 'R02'] = 0
        result = FareCalculator(fares, self.planner.stops, self.transfer_pairs).calculate([ride('R01', 'R02')])
        self.assertIsNone(result['total_twd'])

    def test_unregistered_transfer_is_not_assumed_to_be_in_station(self):
        result = self.planner._fare([ride('BL12', 'BL07'), walk('BL07', 'Y17', 100), ride('Y17', 'Y18')])
        self.assertEqual(result['status'], 'missing')
        self.assertIsNone(result['total_twd'])

    def test_disconnected_steps_are_rejected(self):
        with self.assertRaises(ValueError):
            self.planner._fare([ride('BL02', 'BL01'), ride('LB01', 'LB12')])

    def test_no_rides_does_not_invent_a_boarding(self):
        self.assert_fare([], 0, [])
        self.assert_fare([walk('G04', 'Y07', 180)], 0, [])

    def test_fare_calculation_does_not_mutate_steps_or_table(self):
        steps = via_banqiao()
        before_steps, before_fares = deepcopy(steps), dict(self.planner.fares)
        self.planner._fare(steps)
        self.assertEqual(steps, before_steps)
        self.assertEqual(self.planner.fares, before_fares)

    def test_actual_route_queries(self):
        cases = [('BL02','LB12',55), ('LB12','BL02',55), ('BL12','R15',20),
                 ('Y07','Y20',40), ('G03','Y08',20), ('R11','Y18',25),
                 ('A1','A22',155), ('BL22','A22',185), ('LB01','LB12',35)]
        for a,b,expected in cases:
            with self.subTest(origin=a, destination=b):
                result = self.planner.query(a,b,'2026-11-25T09:00')
                self.assertEqual(result['status'], 'ok')
                self.assertEqual(result['fare']['total_twd'], expected)

    def test_route_api_returns_full_fare_parts(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), partial(MapHandler, resources={}, planner=self.planner))
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            params = urlencode({'origin':'BL02', 'destination':'LB12', 'departure_at':'2026-11-25T09:00'})
            with urlopen(f'http://127.0.0.1:{server.server_port}/api/route?{params}', timeout=5) as response:
                result = json.load(response)
            self.assertEqual(result['fare']['total_twd'], 55)
            self.assertEqual(result['fare']['ticket_type'], 'full_fare')
            self.assertEqual([p['fare_twd'] for p in result['fare']['parts']], [20,35])
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=5)

    def test_stored_value_discount_both_directions_and_hour_boundary(self):
        for seconds, expected in [(120,47), (3599,47), (3600,47), (3601,55)]:
            for steps in (via_sanying(seconds), reverse_steps(via_sanying(seconds))):
                with self.subTest(seconds=seconds, origin=steps[0]['from_id']):
                    fare = self.planner._fare(steps, 'stored_value')
                    self.assertEqual(fare['status'], 'ok')
                    self.assertEqual(fare['base_total_twd'], 55)
                    self.assertEqual(fare['total_twd'], expected)
                    self.assertEqual(fare['discount_twd'], 55 - expected)
                    self.assertEqual(sum(p['net_fare_twd'] for p in fare['parts']), expected)
                    self.assertEqual(sum(p['fare_twd'] for p in fare['parts']), 55)
                    self.assertTrue(fare['assumptions'])

    def test_discount_excludes_train_wait(self):
        steps = via_sanying()
        steps[-1]['wait_s'] = 7200
        self.assertEqual(self.planner._fare(steps, 'stored_value')['total_twd'], 47)

    def test_discount_uses_gate_interval_when_provided(self):
        fare = self.planner._fare(via_sanying(120, gate_elapsed_s=3601), 'stored_value')
        self.assertEqual(fare['total_twd'], 55)
        self.assertEqual(fare['discounts'][0]['time_basis'], 'gate_interval')
        fare = self.planner._fare(via_sanying(4000, gate_elapsed_s=3600), 'stored_value')
        self.assertEqual(fare['total_twd'], 47)

    def test_discount_unknown_time_retains_full_fare_but_not_net_total(self):
        for value in (None, True, -1, '120', float('nan'), float('inf')):
            with self.subTest(value=value):
                fare = self.planner._fare(via_sanying(gate_elapsed_s=value), 'stored_value')
                self.assertEqual(fare['status'], 'missing')
                self.assertEqual(fare['base_total_twd'], 55)
                self.assertIsNone(fare['discount_twd'])
                self.assertIsNone(fare['total_twd'])
                json.dumps(fare, allow_nan=False)

    def test_same_card_and_uninterrupted_transfer_required(self):
        for condition in ({'same_card':False}, {'interrupted_transfer':True}):
            with self.subTest(condition=condition):
                fare = self.planner._fare(via_sanying(**condition), 'stored_value')
                self.assertEqual(fare['total_twd'], 55)
                self.assertEqual(fare['discount_twd'], 0)
                self.assertEqual(fare['discounts'][0]['status'], 'ineligible')
        for condition in ({'same_card':None}, {'same_card':'yes'}, {'interrupted_transfer':None}):
            with self.subTest(condition=condition):
                self.assertIsNone(self.planner._fare(via_sanying(**condition), 'stored_value')['total_twd'])

    def test_no_discount_for_ineligible_systems_or_single_line(self):
        cases = [([ride('LB01','LB12')],35), ([ride('A1','A22')],155),
                 ([ride('BL22','BL12'),walk('BL12','A1',750),ride('A1','A22')],185),
                 (via_banqiao(),25)]
        for steps,expected in cases:
            with self.subTest(steps=steps):
                fare = self.planner._fare(steps, 'stored_value')
                self.assertEqual(fare['total_twd'],expected)
                self.assertEqual(fare['discount_twd'],0)
                self.assertEqual(fare['discounts'],[])

    def test_discount_not_applied_across_multiple_walk_connections(self):
        steps = [ride('BL02','BL01'), walk('BL01','LB01',120),
                 walk('LB01','BL01',120), walk('BL01','LB01',120), ride('LB01','LB12')]
        fare = self.planner._fare(steps,'stored_value')
        self.assertEqual(fare['total_twd'],55)
        self.assertEqual(fare['discounts'],[])

    def test_discount_amount_never_exceeds_following_fare(self):
        fares = dict(self.planner.fares)
        fares['LB01','LB12'] = 5
        fare = FareCalculator(fares,self.planner.stops,self.transfer_pairs).calculate(via_sanying(),'stored_value')
        self.assertEqual(fare['discount_twd'],5)
        self.assertEqual(fare['total_twd'],20)
        self.assertEqual(fare['parts'][1]['net_fare_twd'],0)

    def test_discount_missing_fare_never_invents_net_amount(self):
        fares = dict(self.planner.fares)
        del fares['LB01','LB12']
        fare = FareCalculator(fares,self.planner.stops,self.transfer_pairs).calculate(via_sanying(),'stored_value')
        self.assertIsNone(fare['base_total_twd'])
        self.assertIsNone(fare['total_twd'])
        self.assertIsNone(fare['discount_twd'])

    def test_invalid_fare_mode_is_rejected(self):
        for mode in ('', 'senior', 'student', None, []):
            with self.subTest(mode=mode):
                with self.assertRaises(ValueError):
                    self.planner.query('BL02','LB12','2026-11-25T09:00',fare_mode=mode)

    def test_discount_does_not_change_route_or_full_fare_default(self):
        full = self.planner.query('BL02','LB12','2026-11-25T09:00')
        discounted = self.planner.query('BL02','LB12','2026-11-25T09:00',fare_mode='stored_value')
        self.assertEqual(full['fare']['total_twd'],55)
        self.assertEqual(discounted['fare']['total_twd'],47)
        self.assertEqual({k:v for k,v in full.items() if k!='fare'}, {k:v for k,v in discounted.items() if k!='fare'})

    def test_itinerary_passes_fare_mode_to_route_planner(self):
        class ReachedRoutePlanner(Exception):
            pass
        for mode in ('full_fare','stored_value'):
            with self.subTest(mode=mode):
                captured = {}
                class PlannerSpy:
                    def resolve(self, value): return value
                    def query(self, *args, **kwargs):
                        captured.update(kwargs)
                        raise ReachedRoutePlanner
                recommender = ItineraryPlanner.__new__(ItineraryPlanner)
                recommender.planner = PlannerSpy()
                recommender._destination = lambda _: {'id':'LB12','name':'鶯桃福德','lat':24.96,'lon':121.33}
                place = {'hours':'','name':'test','cuisine':'','lon':121.33,'lat':24.96,'id':'test'}
                recommender._area = lambda _: ([place],{'attraction':[place],'restaurant':[place]})
                recommender._matches_preference = lambda *_: True
                recommender.group_by_code = {'LB12':('LB12',)}
                with self.assertRaises(ReachedRoutePlanner):
                    recommender._recommend({'origin':'BL02','destination':'LB12','departure_at':'2026-11-25T09:00','fare_mode':mode})
                self.assertEqual(captured['fare_mode'],mode)

    def test_route_api_accepts_discount_mode_and_rejects_invalid_mode(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), partial(MapHandler, resources={}, planner=self.planner))
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            base = {'origin':'BL02','destination':'LB12','departure_at':'2026-11-25T09:00'}
            for mode,expected in [('full_fare',55),('stored_value',47)]:
                params = urlencode({**base,'fare_mode':mode})
                with urlopen(f'http://127.0.0.1:{server.server_port}/api/route?{params}',timeout=5) as response:
                    fare=json.load(response)['fare']
                self.assertEqual(fare['total_twd'],expected)
                self.assertEqual(fare['base_total_twd'],55)
            with self.assertRaises(HTTPError) as error:
                urlopen(f'http://127.0.0.1:{server.server_port}/api/route?'+urlencode({**base,'fare_mode':'invalid'}),timeout=5)
            self.assertEqual(error.exception.code,400)
            error.exception.close()
        finally:
            server.shutdown(); server.server_close(); worker.join(timeout=5)


if __name__ == '__main__':
    unittest.main()
