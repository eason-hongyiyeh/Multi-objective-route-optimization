"""缺漏出口的人工校正、獨立儲存與步行候選篩選（僅使用標準函式庫）。"""
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone, timedelta
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
from threading import RLock


MANUAL_FILE = 'manual_verified_exits.geojson'
STATUSES = {
    'confirmed': '已確認', 'pending': '待確認', 'not_found': '查無座標',
    'not_operational': '未營運／規劃中', 'not_exit': '非實際出口',
}
SYSTEMS = {'metro': '一般捷運', 'airport_mrt': '機場捷運',
           'light_rail': '輕軌', 'rail': '臺鐵', 'unknown': '未確認'}
ISSUES = {
    'missing_coordinates': '原檔缺座標', 'invalid_coordinates': '原檔座標無效',
    'missing_exit_number': '缺出口編號', 'exit_number_in_name': '編號僅在名稱中，ref 欄位缺少',
    'station_match_pending': '車站歸屬待確認', 'missing_station_name': '缺所屬車站資訊',
    'imprecise_coordinates': '來源座標精度不足', 'position_unverified': '出口實際位置待確認',
    'not_operational': '原檔標記施工／未營運', 'outside_mrt_scope': '臺鐵入口，非捷運',
}


class ConflictError(ValueError):
    pass


def valid_coordinates(value):
    return (isinstance(value, list) and len(value) == 2
            and all(isinstance(v, (float, int)) and not isinstance(v, bool)
                    and math.isfinite(v) for v in value)
            and -180 <= value[0] <= 180 and -90 <= value[1] <= 90)


def point_coordinates(feature):
    g = feature.get('geometry')
    if isinstance(g, dict) and g.get('type') == 'Point' and valid_coordinates(g.get('coordinates')):
        return g['coordinates']
    return None


def feature_id(feature):
    p = feature.get('properties') or {}
    return str(feature.get('id') or p.get('@id') or p.get('ExitID') or '')


def eligible_for_routing(feature):
    """不能只信任 routing_eligible 旗標；重新驗證人工確認條件。"""
    p = feature.get('properties') or {}
    return bool(point_coordinates(feature) and p.get('verification_status') == 'confirmed'
                and p.get('position_confirmed') is True and p.get('in_service') is True
                and p.get('transit_system') in ('metro', 'airport_mrt', 'light_rail')
                and p.get('station_name') and p.get('verification_source')
                and p.get('position_method') in ('map_click', 'typed_coordinates')
                and p.get('verified_at'))


def load_verified_exits(path):
    """供後續最短步行路徑計算使用；待確認、停用及臺鐵入口一律排除。"""
    path = Path(path)
    if not path.exists():
        return []
    document = read_collection(path)
    return [f for f in document['features'] if eligible_for_routing(f)]


def read_collection(path):
    document = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if (not isinstance(document, dict) or document.get('type') != 'FeatureCollection'
            or not isinstance(document.get('features'), list)):
        raise ValueError(f'{Path(path).name} 須為 GeoJSON FeatureCollection。')
    if any(not isinstance(f, dict) or f.get('type') != 'Feature'
           or not isinstance(f.get('properties'), dict) for f in document['features']):
        raise ValueError(f'{Path(path).name} 包含無效 Feature。')
    return document


def revision(original, context, saved):
    content = json.dumps([original, context, saved], ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def exit_number(properties):
    if properties.get('ref') or properties.get('ExitID'):
        return str(properties.get('ref') or properties['ExitID']), False
    name = str(properties.get('name') or properties.get('ExitName_zh') or '')
    for pattern in (r'([A-Z]?\d+)\s*(?:號)?出入口', r'出入口\s*([A-Z]\d*|\d+)',
                    r'出口\s*([A-Z]?\d+)', r'(\d+)號出口'):
        match = re.search(pattern, name)
        if match:
            return match.group(1), True
    return '', False


class ManualExitStore:
    def __init__(self, data_dir):
        self.data_dir = Path(data_dir).resolve()
        self.path = self.data_dir / MANUAL_FILE
        self.lock = RLock()

    def _read(self):
        context_path = self.data_dir / 'exit_review_context.json'
        context = json.loads(context_path.read_text(encoding='utf-8'))['entries'] if context_path.exists() else {}
        originals = {}
        for filename in ('mrt_exits.geojson', 'airport_mrt_exits.geojson'):
            path = self.data_dir / filename
            if not path.exists():
                continue
            for feature in read_collection(path)['features']:
                key = feature_id(feature)
                if key and (key in context or not point_coordinates(feature)):
                    if key in originals:
                        raise ValueError(f'出口來源 ID 重複：{key}')
                    originals[key] = (feature, filename)
        document = read_collection(self.path) if self.path.exists() else {
            'type': 'FeatureCollection', 'schema_version': 1, 'features': []}
        saved = {}
        for f in document['features']:
            key, p = feature_id(f), f['properties']
            if not key or key in saved:
                raise ValueError('人工紀錄含空白或重複 ID，請先檢查檔案。')
            if p.get('verification_status') not in STATUSES:
                raise ValueError(f'人工紀錄狀態無效：{key}')
            if p['verification_status'] != 'confirmed' and f.get('geometry') is not None:
                raise ValueError(f'未確認出口不能含正式 geometry：{key}')
            if p['verification_status'] == 'confirmed' and not point_coordinates(f):
                raise ValueError(f'已確認出口缺少有效座標：{key}')
            saved[key] = f
        return context, originals, document, saved

    def _entry(self, key, original, filename, context, saved):
        c, p = context.get(key, {}), original['properties']
        number, from_name = exit_number(p)
        issues = ['position_unverified']
        if original.get('geometry') is None:
            issues.append('missing_coordinates')
        elif not point_coordinates(original):
            issues.append('invalid_coordinates')
        if not number:
            issues.append('missing_exit_number')
        elif from_name:
            issues.append('exit_number_in_name')
        if c.get('station_match_status') == 'position_candidate':
            issues.append('station_match_pending')
        if not c.get('station_name') and not p.get('StationName_zh'):
            issues.append('missing_station_name')
        reference = c.get('reference_coordinates') or point_coordinates(original)
        if reference and all(round(v, 3) == v for v in reference):
            issues.append('imprecise_coordinates')
        construction = p.get('construction') in ('yes', True) or p.get('proposed') in ('yes', True)
        if construction:
            issues.append('not_operational')
        if c.get('transit_system') == 'rail':
            issues.append('outside_mrt_scope')
        defaults = {
            'exit_name': p.get('name') or p.get('ExitName_zh') or '', 'exit_number': number,
            'station_name': c.get('station_name') or p.get('StationName_zh') or '',
            'station_ref': c.get('station_ref') or p.get('StationID') or '',
            'transit_system': c.get('transit_system', 'airport_mrt' if filename.startswith('airport') else 'unknown'),
            'verification_status': 'not_operational' if construction else 'pending',
            'verification_source': '', 'notes': '', 'in_service': False,
            'position_confirmed': False, 'position_method': '', 'coordinates': None,
        }
        if saved:
            s = saved['properties']
            defaults.update({k: s[k] for k in defaults if k in s})
            defaults['coordinates'] = point_coordinates(saved) or s.get('draft_coordinates')
        station_coordinates = c.get('station_coordinates')
        return {
            'id': key, 'source_file': filename, 'original': original,
            'source_url': c.get('reference_source', ''), 'reference_coordinates': reference,
            'reference_checked_on': c.get('reference_checked_on', ''),
            'station_match_status': c.get('station_match_status', 'unknown'),
            'station_source': c.get('station_source', ''),
            'station_coordinates': station_coordinates,
            'view_coordinates': station_coordinates or reference,
            'view_kind': 'station' if station_coordinates else 'source_reference',
            'issues': issues, 'values': defaults, 'saved': bool(saved),
            'saved_at': saved['properties'].get('reviewed_at') if saved else None,
            'routing_eligible': eligible_for_routing(saved) if saved else False,
            'revision': revision(original, c, saved),
        }

    def snapshot(self):
        with self.lock:
            context, originals, document, saved = self._read()
            entries = [self._entry(k, f, filename, context, saved.get(k))
                       for k, (f, filename) in originals.items()]
            return {'entries': entries, 'statuses': STATUSES, 'systems': SYSTEMS, 'issue_labels': ISSUES,
                    'issue_counts': dict(Counter(i for e in entries for i in e['issues'])),
                    'saved_count': len(saved), 'eligible_count': sum(eligible_for_routing(f) for f in saved.values()),
                    'orphan_ids': sorted(set(saved) - set(originals)), 'output_file': 'data/' + MANUAL_FILE}

    def collection(self, routing_only=False):
        with self.lock:
            _, _, document, _ = self._read()
            return {**document, 'features': [f for f in document['features'] if eligible_for_routing(f)]} if routing_only else document

    def save(self, payload):
        if not isinstance(payload, dict):
            raise ValueError('儲存內容須為 JSON 物件。')
        with self.lock:
            context, originals, document, saved = self._read()
            key = payload.get('id')
            if not isinstance(key, str) or key not in originals:
                raise ValueError('找不到待校正出口，請重新載入。')
            original, filename = originals[key]
            if payload.get('revision') != revision(original, context.get(key, {}), saved.get(key)):
                raise ConflictError('此筆資料已被其他頁面或原始檔更新；請重新載入後再編輯。')
            def text(field, maximum=300):
                value = payload.get(field, '')
                if not isinstance(value, str) or len(value) > maximum:
                    raise ValueError(f'{field} 須為不超過 {maximum} 字的文字。')
                return value.strip()
            status, system = text('verification_status'), text('transit_system')
            if status not in STATUSES or system not in SYSTEMS:
                raise ValueError('請選擇有效的狀態與交通系統。')
            coordinates = payload.get('coordinates')
            if coordinates is not None and not valid_coordinates(coordinates):
                raise ValueError('座標須為有效 WGS84 [經度, 緯度]，經度 ±180、緯度 ±90。')
            method = text('position_method')
            if coordinates is not None and method not in ('map_click', 'typed_coordinates'):
                raise ValueError('請在地圖點選或手動輸入實際位置，不能使用車站中心自動配對。')
            station, evidence = text('station_name'), text('verification_source', 2000)
            confirmed, in_service = payload.get('position_confirmed') is True, payload.get('in_service') is True
            if status == 'confirmed' and not (coordinates and station and evidence and confirmed and in_service):
                raise ValueError('已確認須有實際座標、車站名稱、查證來源，並勾選位置已核對及已開放通行。')
            if status == 'confirmed' and system == 'unknown':
                raise ValueError('已確認出口須選擇所屬交通系統。')
            if status == 'not_found' and coordinates is not None:
                raise ValueError('查無座標時請先清除手動座標。')
            if status in ('not_operational', 'not_exit') and in_service:
                raise ValueError('未營運或非實際出口不得標記為已開放通行。')
            if status in ('not_operational', 'not_exit') and not (evidence or text('notes', 3000)):
                raise ValueError('請填寫狀態判定的來源或備註。')
            now = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
            properties = deepcopy(original['properties'])
            properties.update({
                'source_id': key, 'source_file': filename, 'original_properties': deepcopy(original['properties']),
                'original_geometry': deepcopy(original.get('geometry')), 'source': 'manual_review',
                'exit_name': text('exit_name'), 'exit_number': text('exit_number'),
                'station_name': station, 'station_ref': text('station_ref'), 'transit_system': system,
                'verification_status': status, 'verification_source': evidence, 'notes': text('notes', 3000),
                'position_method': method if coordinates else '',
                'position_confirmed': confirmed if status == 'confirmed' else False,
                'in_service': in_service, 'reviewed_at': now,
                'verified_at': now if status == 'confirmed' else None,
                'draft_coordinates': coordinates if status != 'confirmed' else None,
                'reference_context': deepcopy(context.get(key, {})),
            })
            feature = {'type': 'Feature', 'id': key, 'properties': properties,
                       'geometry': {'type': 'Point', 'coordinates': coordinates} if status == 'confirmed' else None}
            properties['routing_eligible'] = eligible_for_routing(feature)
            saved[key] = feature
            document = {**document, 'schema_version': 1, 'updated_at': now, 'features': list(saved.values())}
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=self.data_dir,
                                                 prefix='.manual-exits-', suffix='.tmp', delete=False) as handle:
                    temporary = Path(handle.name)
                    json.dump(document, handle, ensure_ascii=False, indent=2, allow_nan=False)
                    handle.write('\n'); handle.flush(); os.fsync(handle.fileno())
                os.replace(temporary, self.path)
            finally:
                if temporary and temporary.exists():
                    temporary.unlink()
            return self._entry(key, original, filename, context, feature)
