"""一般全票與一般電子票證轉乘計費；保留原價與折扣明細。

只讀取既有起訖票價；不以相鄰站票價相加，也不修改來源 CSV。
站外轉乘 gate_elapsed_s 可提供出閘至入閘的秒數；沒有時使用 duration_s
作為規劃估計，絕不把下一班車的候車時間算進 20 分鐘。
規則來源與適用範圍見 docs/full_fare.md。
"""
import math


OUTSIDE_TRANSFER_LIMIT_S = 20 * 60
SANYING_DISCOUNT_LIMIT_S = 60 * 60
SANYING_DISCOUNT_PAIR = frozenset(('BL01', 'LB01'))
FARE_MODES = {'full_fare', 'stored_value'}
OUTSIDE_TRANSFERS = {
    frozenset(('BL07', 'Y16')),  # 板橋
    frozenset(('BL08', 'Y17')),  # 新埔／新埔民生
}
SYSTEM_NAMES = {'metro': '北捷／環狀線', 'airport': '機場捷運', 'sanying': '三鶯線'}
FULL_FARE_NOTE = (
    '一般全票，未套用電子票證轉乘折扣、優待票或定期票。'
    '北捷與環狀線符合轉乘條件時按同一旅次起訖查表；'
    '機場捷運、三鶯線各自分段計費，再加總。'
    '票價取自本機 CSV，不包含逾時停留等額外費用。'
)
STORED_VALUE_NOTE = (
    '以同一張悠遊卡／一卡通／icash 一般卡計算。'
    '北捷與三鶯線於 1 小時內直接轉乘減 8 元；機捷不套用此優惠。'
    '北捷／環狀線原有同旅次計費規則不變。'
    '不含敬老、兒童等優待票、定期票、常客回饋或逾時停留費用。'
)


class FareCalculator:
    def __init__(self, fares, stops, transfer_pairs):
        self.fares = fares
        self.stops = stops
        self.transfer_pairs = set(transfer_pairs)

    def _system(self, code):
        line = self.stops[code]['line_id']
        if line == 'A':
            return 'airport'
        if line == 'LB':
            return 'sanying'
        if line in {'BL', 'BR', 'R', 'G', 'O', 'Y'}:
            return 'metro'
        raise ValueError(f'尚未定義計費系統：{line}')

    @staticmethod
    def _elapsed(walk):
        measured = 'gate_elapsed_s' in walk
        seconds = walk.get('gate_elapsed_s') if measured else walk.get('duration_s')
        if (not isinstance(seconds, (int, float)) or isinstance(seconds, bool)
                or not math.isfinite(seconds) or seconds < 0):
            seconds = None
        return seconds, 'gate_interval' if measured else 'estimated_walk'

    def _transfer(self, walk):
        a, b = walk['from_id'], walk['to_id']
        event = {'from_id': a, 'to_id': b}
        if (a, b) not in self.transfer_pairs:
            return {**event, 'rule': 'unverified_transfer', 'merge': None,
                    'reason': '轉乘關係尚未收錄，無法判斷是否可合併計費。'}
        if self._system(a) != self._system(b):
            return {**event, 'rule': 'separate_systems', 'merge': False,
                    'reason': '跨獨立計費系統，先分段計算全票；轉乘優惠另外列出。'}
        if frozenset((a, b)) not in OUTSIDE_TRANSFERS:
            return {**event, 'rule': 'in_station', 'merge': True,
                    'reason': '站內轉乘，沿用同一旅次起訖票價。'}

        seconds, basis = self._elapsed(walk)
        event.update(limit_s=OUTSIDE_TRANSFER_LIMIT_S, time_basis=basis)
        if seconds is None:
            return {**event, 'rule': 'outside_time_unknown', 'elapsed_s': None,
                    'merge': None, 'reason': '站外轉乘時間待確認，不能判定是否在 20 分鐘內。'}
        within = seconds <= OUTSIDE_TRANSFER_LIMIT_S
        return {**event, 'rule': 'outside_within_limit' if within else 'outside_timeout',
                'elapsed_s': seconds, 'merge': within,
                'reason': '指定站外轉乘在 20 分鐘內，合併起訖計費。' if within else
                          '指定站外轉乘超過 20 分鐘，前後旅次分開計費。'}

    def _discount(self, walk, part_index):
        seconds, basis = self._elapsed(walk)
        result = {'from_id': walk['from_id'], 'to_id': walk['to_id'],
                  'part_index': part_index, 'rule': 'sanying_transfer',
                  'limit_s': SANYING_DISCOUNT_LIMIT_S, 'elapsed_s': seconds,
                  'time_basis': basis, 'amount_twd': 0}
        same_card = walk.get('same_card', True)
        interrupted = walk.get('interrupted_transfer', False)
        if same_card is False or interrupted is True:
            return {**result, 'status': 'ineligible',
                    'reason': '未使用同一張票卡或轉乘已中斷，不適用 8 元轉乘優惠。'}
        if type(same_card) is not bool or type(interrupted) is not bool or seconds is None:
            return {**result, 'status': 'unknown', 'amount_twd': None,
                    'reason': '票卡、直接轉乘或出入閘時間待確認，尚不能確定轉乘優惠。'}
        if seconds > SANYING_DISCOUNT_LIMIT_S:
            return {**result, 'status': 'ineligible',
                    'reason': '出閘至入閘超過 1 小時，不適用 8 元轉乘優惠。'}
        return {**result, 'status': 'applied', 'amount_twd': 8,
                'reason': '同一張合適的一般電子票證，1 小時內北捷與三鶯線直接轉乘，減 8 元。'}

    def calculate(self, steps, fare_mode='full_fare'):
        if not isinstance(fare_mode, str) or fare_mode not in FARE_MODES:
            raise ValueError('票價模式須為 full_fare 或 stored_value。')
        segments, events, assumptions, discounts = [], [], [], []
        previous = None
        walks = []
        uncertain = False
        for step in steps:
            if step['type'] == 'walk':
                if previous is not None:
                    walks.append(step)
                continue
            if step['type'] != 'ride':
                raise ValueError('票價計算只接受搭乘與轉乘步行步驟。')
            a, b = step['from_id'], step['to_id']
            system = self._system(a)
            if system != self._system(b):
                raise ValueError('單一搭乘步驟不可跨越不同計費系統。')
            merge = previous is not None and segments[-1]['system'] == system
            if previous is not None:
                cursor = previous['to_id']
                for walk in walks:
                    if walk['from_id'] != cursor:
                        raise ValueError('票價計算的轉乘步驟不連續。')
                    cursor = walk['to_id']
                    event = self._transfer(walk)
                    events.append(event)
                    merge = merge and event['merge'] is True
                    uncertain |= event['merge'] is None
                    if event.get('time_basis') == 'estimated_walk':
                        assumptions.append('站外轉乘以預估步行時間判定；實際須於出閘後 20 分鐘內進入相對應車站，且單程票須依指定閘門規定轉乘。候車時間不計入此期限。')
                    if event['merge'] is None:
                        assumptions.append(event['reason'])
                if cursor != a:
                    raise ValueError('票價計算的搭乘步驟缺少轉乘連接。')
            if merge:
                segments[-1]['to_id'] = b
            else:
                segments.append({'system': system, 'system_name': SYSTEM_NAMES[system],
                                 'from_id': a, 'to_id': b})
            # 優惠只在兩段實際搭乘之間直接經頂埔轉乘時套用，不能跨越其他交通段。
            if (fare_mode == 'stored_value' and previous is not None and len(walks) == 1
                    and frozenset((walks[0]['from_id'], walks[0]['to_id'])) == SANYING_DISCOUNT_PAIR
                    and (walks[0]['from_id'], walks[0]['to_id']) in self.transfer_pairs):
                discount = self._discount(walks[0], len(segments) - 1)
                discounts.append(discount)
                if discount['time_basis'] == 'estimated_walk':
                    assumptions.append('三鶯線轉乘優惠以預估步行時間判定；實際須使用同一張合適票卡，於出閘後 1 小時內直接轉乘入閘。候車時間不計入此期限。')
                if discount['status'] == 'unknown':
                    assumptions.append(discount['reason'])
            previous = step
            walks = []

        complete = not uncertain
        for segment in segments:
            a, b = segment['from_id'], segment['to_id']
            fare = self.fares.get((a, b))
            reason = ''
            if fare is None:
                reason = '票價表未收錄這組起訖，不能以逐站票價相加代替。'
            elif fare == 0 and self.stops[a]['name'] != self.stops[b]['name']:
                fare = None
                reason = '不同車站的來源票價為 0，需核對。'
            segment.update(fare_twd=fare, reason=reason,
                           from_name=self.stops[a]['name'], to_name=self.stops[b]['name'],
                           discount_twd=0, net_fare_twd=fare)
            complete &= fare is not None
        base_total = sum(s['fare_twd'] for s in segments) if complete else None
        discount_known = True
        for discount in discounts:
            segment = segments[discount['part_index']]
            if discount['status'] == 'applied':
                if segment['fare_twd'] is None:
                    discount.update(status='unknown', amount_twd=None, reason='搭乘區段票價待補，尚不能計算實際折扣。')
                else:
                    discount['amount_twd'] = min(discount['amount_twd'], segment['fare_twd'])
            if discount['amount_twd'] is None:
                discount_known = False
                segment['discount_twd'] = segment['net_fare_twd'] = None
            else:
                segment['discount_twd'] = discount['amount_twd']
                segment['net_fare_twd'] = segment['fare_twd'] - discount['amount_twd'] if segment['fare_twd'] is not None else None
        total_discount = sum(d['amount_twd'] for d in discounts) if discount_known else None
        complete &= discount_known
        if uncertain:
            assumptions.append('下列分段金額僅供核對；轉乘條件未確認前不提供總票價。')
        return {'status': 'ok' if complete else 'missing', 'ticket_type': fare_mode,
                'base_total_twd': base_total, 'discount_twd': total_discount,
                'total_twd': base_total - total_discount if complete else None,
                'parts': segments, 'transfers': events, 'discounts': discounts,
                'assumptions': list(dict.fromkeys(assumptions)),
                'note': (FULL_FARE_NOTE if fare_mode == 'full_fare' else STORED_VALUE_NOTE)
                        if segments else '沒有搭乘區段，未計搭車票價；此處不代表同站刷卡進出的收費。'}
