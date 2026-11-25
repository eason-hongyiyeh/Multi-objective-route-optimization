/* 無瀏覽器、無外網的票價顯示回歸；只替代 DOM 與 Leaflet。 */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

class Element {
  constructor(tag) {
    this.tag = tag; this.children = []; this.events = {}; this.dataset = {};
    this.style = {}; this.value = ''; this.checked = false; this.text = '';
  }
  set textContent(value) { this.text = String(value); this.children = []; }
  get textContent() { return this.text + this.children.map(c => c.textContent ?? String(c)).join('\n'); }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.text = ''; this.children = children; }
  addEventListener(event, callback) { this.events[event] = callback; }
}

async function renderFare(fare, mode = 'full_fare') {
  const elements = new Map();
  const el = id => { if (!elements.has(id)) elements.set(id, new Element(id)); return elements.get(id); };
  el('itinerary-fare-mode').value = mode;
  let requestedUrl = '';
  const stop = { id: 'BL02', name: '永寧', line_name: '板南線', lat: 24.96, lon: 121.43 };
  const end = { id: 'LB12', name: '鶯桃福德', line_name: '三鶯線', lat: 24.96, lon: 121.33,
    station_codes: ['LB12'], exit_count: 1, attraction_count: 1, restaurant_count: 1 };
  const place = { name: '測試地點', lat: 24.96, lon: 121.33,
    arrival_at: '2026-11-25T10:00:00', departure_at: '2026-11-25T10:30:00', hours_status: 'unknown' };
  const fixture = { total_s: 3600, end_at: '2026-11-25T11:00:00', destination: end,
    transit: { total_s: 2400, origin: stop, destination: end, steps: [], fare },
    exit_buffer_s: 300, walk_s: 120, visit_s: 600, meal_s: 600, reason: '測試資料',
    exit: place, attraction: place, restaurant: place, walks: [], warnings: [] };
  const bounds = { extend() { return this; }, getSouthWest() { return [24,121]; }, getNorthEast() { return [25,122]; } };
  const layer = () => ({ addTo() { return this; }, bindTooltip() { return this; }, bindPopup() { return this; },
    clearLayers() {}, getBounds() { return bounds; } });
  const context = { window: {}, document: { getElementById: el, createElement: tag => new Element(tag) },
    L: { featureGroup: layer, circleMarker: layer, geoJSON: layer, latLngBounds: () => bounds },
    Intl, Date, URLSearchParams, AbortController, setTimeout, clearTimeout,
    fetch: async url => { requestedUrl = url; return ({ ok: true, json: async () => url === '/api/stations'
      ? { stops: [stop, end] } : url === '/api/itinerary-options'
        ? { destinations: [end], default_destination: 'LB12', max_walk_m: 1200 } : fixture }); } };
  const script = fs.readFileSync(path.join(__dirname, '..', 'itinerary_query.js'), 'utf8');
  vm.runInNewContext(script, context, { filename: 'itinerary_query.js' });
  await context.window.setupItineraryQuery({ createPane: () => ({ style: {} }), fitBounds() {}, stop() {} },
    { clearRoute() {}, drawRoute() { return false; } });
  assert.equal(el('itinerary-form').dataset.ready, 'true');
  await el('itinerary-form').events.submit({ preventDefault() {} });
  assert.notEqual(el('itinerary-feedback').className, 'error', el('itinerary-feedback').textContent);
  assert.equal(new URLSearchParams(requestedUrl.split('?')[1]).get('fare_mode'), mode);
  return el('itinerary-results').textContent;
}

async function run() {
  const fare = { total_twd: 55, parts: [
    { system_name: '北捷／環狀線', from_name: '永寧', from_id: 'BL02', to_name: '頂埔', to_id: 'BL01', fare_twd: 20 },
    { system_name: '三鶯線', from_name: '頂埔', from_id: 'LB01', to_name: '鶯桃福德', to_id: 'LB12', fare_twd: 35 }
  ], transfers: [{ from_id: 'BL01', to_id: 'LB01', rule: 'separate_systems', reason: '跨系統分段計費' }],
    assumptions: [], note: '一般全票，不套用優惠。' };
  const normal = await renderFare(fare);
  for (const text of ['捷運全票：NT$ 55', '全票計算明細', 'NT$ 20', 'NT$ 35', '跨系統分段計費', '不套用優惠']) {
    assert.ok(normal.includes(text), text);
  }
  assert.ok(!normal.includes('undefined'));
  assert.ok(!normal.includes('NT$ 47'));
  const missing = await renderFare({ ...fare, total_twd: null,
    assumptions: ['站外轉乘時間待確認，暫不提供總票價。'] });
  assert.ok(missing.includes('捷運全票：資料／轉乘條件待確認'));
  assert.ok(missing.includes('暫不提供總票價'));
  assert.ok(!missing.includes('捷運全票：NT$'));
  const estimated = await renderFare({ ...fare, assumptions: ['站外轉乘以預估步行時間判定。'] });
  assert.ok(estimated.includes('站外轉乘以預估步行時間判定。'));
  const stored = { ...fare, ticket_type: 'stored_value', base_total_twd: 55, discount_twd: 8, total_twd: 47,
    discounts: [{ from_id: 'BL01', to_id: 'LB01', status: 'applied', amount_twd: 8, reason: '同卡 1 小時內直接轉乘' }],
    note: '一般電子票證轉乘優惠' };
  const discount = await renderFare(stored, 'stored_value');
  for (const text of ['捷運票價（一般電子票證）：NT$ 47', '全票合計：NT$ 55', '減 NT$ 8', '票價與轉乘優惠明細', '同卡 1 小時內直接轉乘']) assert.ok(discount.includes(text), text);
  const uncertain = await renderFare({ ...stored, total_twd: null, discount_twd: null, discounts: [] }, 'stored_value');
  assert.ok(uncertain.includes('轉乘優惠：待確認'));
  assert.ok(uncertain.includes('全票合計：NT$ 55'));
  assert.ok(!uncertain.includes('NT$ 47'));
  console.log('PASS: full fare, missing data, estimates, discount, uncertain discount and selected-mode submission (5 cases)');
}

run().catch(error => { console.error(error); process.exitCode = 1; });
