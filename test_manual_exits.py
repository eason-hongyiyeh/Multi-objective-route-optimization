"""執行：python -m unittest -v test_manual_exits；所有寫入皆在暫存資料夾。"""
from copy import deepcopy
import hashlib
from http.client import HTTPConnection
import json
from pathlib import Path
import tempfile
from threading import Thread
import unittest
from unittest.mock import patch

from calculate_market_walks import Router, routing_target_allowed
from manual_exits import ManualExitStore, MANUAL_FILE, ConflictError, eligible_for_routing, load_verified_exits
from mrt_map import make_server


class ManualExitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.originals = {
            'mrt_exits.geojson': {'type': 'FeatureCollection', 'features': [
                {'type': 'Feature', 'id': 'node/1', 'geometry': None,
                 'properties': {'@id': 'node/1', 'railway': 'subway_entrance', 'ref': '1', 'source': 'OSM'}},
                {'type': 'Feature', 'id': 'node/2', 'geometry': None,
                 'properties': {'@id': 'node/2', 'railway': 'subway_entrance', 'name': '測試站 C2出入口', 'construction': 'yes'}}]},
            'airport_mrt_exits.geojson': {'type': 'FeatureCollection', 'features': []},
        }
        for name, document in self.originals.items():
            (self.directory / name).write_text(json.dumps(document), encoding='utf-8')
        context = {'entries': {'node/1': {'station_name': '測試站', 'station_ref': 'T1', 'transit_system': 'metro',
                    'station_coordinates': [121.5, 25.0], 'reference_coordinates': [121.501, 25.001],
                    'station_match_status': 'position_candidate'},
                    'node/2': {'station_name': '測試站', 'transit_system': 'metro', 'station_match_status': 'source_name'}}}
        (self.directory / 'exit_review_context.json').write_text(json.dumps(context), encoding='utf-8')
        self.original_hashes = {name: hashlib.sha256((self.directory / name).read_bytes()).hexdigest() for name in self.originals}
        self.store = ManualExitStore(self.directory)

    def payload(self, key='node/1', **changes):
        entry = next(e for e in self.store.snapshot()['entries'] if e['id'] == key)
        result = {**entry['values'], 'id': key, 'revision': entry['revision']}
        result.update(changes)
        return result

    def confirmation(self, **changes):
        fields = {'verification_status': 'confirmed', 'coordinates': [121.5011234, 25.0011234],
                  'position_method': 'map_click', 'verification_source': '測試用現勘紀錄',
                  'position_confirmed': True, 'in_service': True}
        fields.update(changes)
        return self.payload(**fields)

    def test_source_reference_never_becomes_exit_geometry(self):
        snapshot = self.store.snapshot()
        entry = snapshot['entries'][0]
        self.assertEqual(entry['view_coordinates'], [121.5, 25.0])
        self.assertIsNone(entry['values']['coordinates'])
        self.assertFalse(entry['routing_eligible'])
        self.assertIn('station_match_pending', entry['issues'])
        self.assertIn('exit_number_in_name', snapshot['entries'][1]['issues'])
        self.assertEqual(snapshot['entries'][1]['values']['verification_status'], 'not_operational')
        self.assertEqual(snapshot['entries'][1]['values']['exit_number'], 'C2')

    def test_pending_draft_has_no_formal_geometry(self):
        self.store.save(self.payload(coordinates=[121.51, 25.01], position_method='typed_coordinates'))
        feature = self.store.collection()['features'][0]
        self.assertIsNone(feature['geometry'])
        self.assertEqual(feature['properties']['draft_coordinates'], [121.51, 25.01])
        self.assertEqual(load_verified_exits(self.directory / MANUAL_FILE), [])
        reloaded = ManualExitStore(self.directory).snapshot()['entries'][0]
        self.assertEqual(reloaded['values']['coordinates'], [121.51, 25.01])

    def test_confirm_save_persists_sources_and_originals(self):
        entry = self.store.save(self.confirmation())
        self.assertTrue(entry['routing_eligible'])
        features = load_verified_exits(self.directory / MANUAL_FILE)
        self.assertEqual(len(features), 1)
        p = features[0]['properties']
        self.assertEqual(p['original_properties'], self.originals['mrt_exits.geojson']['features'][0]['properties'])
        self.assertEqual(p['verification_source'], '測試用現勘紀錄')
        self.assertIsNotNone(p['verified_at'])
        self.assertEqual(ManualExitStore(self.directory).snapshot()['eligible_count'], 1)
        for name, digest in self.original_hashes.items():
            self.assertEqual(hashlib.sha256((self.directory / name).read_bytes()).hexdigest(), digest)

    def test_confirm_requires_explicit_position_evidence_and_service(self):
        invalid = [{'coordinates': None}, {'verification_source': ''}, {'station_name': ''},
                   {'position_confirmed': False}, {'in_service': False}, {'transit_system': 'unknown'},
                   {'position_method': ''}, {'coordinates': [25, 121]}, {'coordinates': [True, 25]},
                   {'coordinates': [float('nan'), 25]}, {'coordinates': [121, float('inf')]}]
        for changes in invalid:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.store.save(self.confirmation(**changes))
        self.assertFalse((self.directory / MANUAL_FILE).exists())

    def test_revoking_confirmation_removes_routing_and_formal_point(self):
        self.store.save(self.confirmation())
        self.store.save(self.payload(verification_status='pending'))
        feature = self.store.collection()['features'][0]
        self.assertIsNone(feature['geometry'])
        self.assertFalse(feature['properties']['position_confirmed'])
        self.assertIsNone(feature['properties']['verified_at'])
        self.assertEqual(self.store.collection(routing_only=True)['features'], [])

    def test_all_exclusion_statuses_and_rail_are_blocked(self):
        for status in ('pending', 'not_found', 'not_operational', 'not_exit'):
            with self.subTest(status=status):
                entry = self.store.save(self.payload(verification_status=status, notes='人工查證記錄',
                                                    coordinates=None, in_service=False))
                self.assertFalse(entry['routing_eligible'])
                self.assertIsNone(self.store.collection()['features'][0]['geometry'])
        entry = self.store.save(self.confirmation(transit_system='rail'))
        self.assertEqual(entry['values']['verification_status'], 'confirmed')
        self.assertFalse(entry['routing_eligible'])

    def test_clear_saved_coordinates_then_set_new_position(self):
        self.store.save(self.confirmation())
        self.store.save(self.payload(verification_status='pending', coordinates=None,
                                    position_method='', position_confirmed=False))
        reloaded = ManualExitStore(self.directory)
        entry = reloaded.snapshot()['entries'][0]
        self.assertIsNone(entry['values']['coordinates'])
        self.assertEqual(reloaded.collection(routing_only=True)['features'], [])
        feature = reloaded.collection()['features'][0]
        self.assertIsNone(feature['geometry'])
        self.assertIsNone(feature['properties']['draft_coordinates'])
        new_position = [121.5023456, 25.0023456]
        self.store.save(self.confirmation(coordinates=new_position))
        saved = reloaded.collection()['features']
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0]['geometry']['coordinates'], new_position)
        self.assertTrue(eligible_for_routing(saved[0]))
        self.assertEqual(saved[0]['properties']['reference_context']['reference_coordinates'], [121.501, 25.001])

    def test_not_found_and_out_of_service_cannot_contradict_fields(self):
        for changes in ({'verification_status': 'not_found', 'coordinates': [121, 25], 'position_method': 'map_click'},
                        {'verification_status': 'not_operational', 'in_service': True, 'notes': '施工'},
                        {'verification_status': 'not_exit'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.store.save(self.payload(**changes))

    def test_save_another_record_preserves_existing_one(self):
        self.store.save(self.confirmation())
        self.store.save(self.payload('node/2', verification_status='not_operational', notes='施工中，測試紀錄'))
        self.assertEqual(len(self.store.collection()['features']), 2)
        self.assertEqual(len(self.store.collection(routing_only=True)['features']), 1)

    def test_stale_revision_rejected(self):
        stale = self.confirmation()
        self.store.save(self.payload(notes='另一頁已修改'))
        with self.assertRaises(ConflictError):
            self.store.save(stale)
        self.assertEqual(self.store.snapshot()['entries'][0]['values']['notes'], '另一頁已修改')

    def test_source_change_rejected_without_overwriting(self):
        stale = self.confirmation()
        path = self.directory / 'mrt_exits.geojson'
        document = json.loads(path.read_text(encoding='utf-8'))
        document['features'][0]['properties']['ref'] = '2'
        path.write_text(json.dumps(document), encoding='utf-8')
        with self.assertRaises(ConflictError):
            self.store.save(stale)
        self.assertFalse((self.directory / MANUAL_FILE).exists())

    def test_failed_write_keeps_saved_file(self):
        self.store.save(self.payload(notes='原紀錄'))
        before = self.store.path.read_bytes()
        with patch('manual_exits.os.replace', side_effect=PermissionError('locked')):
            with self.assertRaises(PermissionError):
                self.store.save(self.confirmation())
        self.assertEqual(self.store.path.read_bytes(), before)
        self.assertEqual(list(self.directory.glob('.manual-exits-*.tmp')), [])

    def test_broken_file_is_not_silently_overwritten(self):
        self.store.path.write_text('{broken', encoding='utf-8')
        with self.assertRaises(ValueError):
            self.store.snapshot()
        self.assertEqual(self.store.path.read_text(encoding='utf-8'), '{broken')

    def test_routing_rechecks_eligibility_not_just_cached_flag(self):
        self.store.save(self.confirmation())
        original = self.store.collection()['features'][0]
        self.assertTrue(routing_target_allowed(original))
        for field, value in (('verification_status', 'pending'), ('position_confirmed', False), ('in_service', False),
                             ('verification_source', ''), ('verified_at', None), ('transit_system', 'rail')):
            with self.subTest(field=field):
                feature = deepcopy(original)
                feature['properties'][field] = value
                feature['properties']['routing_eligible'] = True
                self.assertFalse(eligible_for_routing(feature))
                self.assertFalse(routing_target_allowed(feature))
                # route 必須在讀座標／快取或呼叫網路之前拒絕，不需建立 Router 的快取目錄。
                with self.assertRaises(ValueError):
                    Router.__new__(Router).route({}, feature)
        self.assertFalse(routing_target_allowed(self.originals['mrt_exits.geojson']['features'][0]))
        self.assertTrue(routing_target_allowed({'properties': {'railway': 'station'}}))

    def test_http_save_reload_and_request_protection(self):
        server = make_server(0, self.directory)
        worker = Thread(target=server.serve_forever, daemon=True); worker.start()
        self.addCleanup(server.server_close)
        self.addCleanup(worker.join, 2)
        self.addCleanup(server.shutdown)
        host = f'127.0.0.1:{server.server_port}'
        def request(method, path, body=None, headers=None):
            connection = HTTPConnection('127.0.0.1', server.server_port, timeout=5)
            try:
                connection.request(method, path, body=body, headers=headers or {})
                response = connection.getresponse()
                return response.status, json.loads(response.read())
            finally:
                connection.close()
        status, snapshot = request('GET', '/manual-exits.json')
        self.assertEqual(status, 200)
        body = json.dumps(self.confirmation())
        headers = {'Content-Type': 'application/json', 'Origin': 'http://' + host,
                   'X-Manual-Edit-Token': snapshot['csrf_token']}
        for wrong in ({**headers, 'Origin': 'https://untrusted.example'}, {**headers, 'X-Manual-Edit-Token': ''}):
            self.assertEqual(request('POST', '/manual-exits.json', body, wrong)[0], 403)
        self.assertEqual(request('POST', '/manual-exits.json', body, headers)[0], 200)
        self.assertEqual(request('POST', '/manual-exits.json', body, headers)[0], 409)
        self.assertEqual(len(request('GET', '/routing-exits.json')[1]['features']), 1)
        self.assertEqual(len(request('GET', '/data/' + MANUAL_FILE)[1]['features']), 1)
        status, latest = request('GET', '/manual-exits.json')
        self.assertTrue(latest['entries'][0]['saved'])


if __name__ == '__main__':
    unittest.main()
