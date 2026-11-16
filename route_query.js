/* 起終點查詢介面；既有地點圖層由 map.html 維持。 */
window.setupRouteQuery = async function (map, loaded, colors) {
  const el = id => document.getElementById(id);
  const node = (tag, text, className) => {
    const item = document.createElement(tag);
    if (text !== undefined) item.textContent = text;
    if (className) item.className = className;
    return item;
  };
  const form = el('route-form'), feedback = el('route-feedback'), results = el('route-results');
  const origin = el('route-origin'), destination = el('route-destination'), departure = el('route-departure');
  const submit = el('route-submit');
  const minutes = value => {
    if (value === null || value === undefined) return '待補';
    const whole = Math.round(value), min = Math.floor(whole / 60), sec = whole % 60;
    return sec ? `${min} 分 ${sec} 秒` : `${min} 分鐘`;
  };
  const clock = (value, day) => value ? `${value.slice(0, 10) === day ? '' : value.slice(5, 10) + ' '}${value.slice(11, 19)}` : '待補';
  const stationLabel = s => `${s.name} · ${s.id} · ${s.line_name}`;
  const timeParts = new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Taipei', year: 'numeric',
    month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).formatToParts(new Date());
  const current = Object.fromEntries(timeParts.map(part => [part.type, part.value]));
  departure.value = `${current.year}-${current.month}-${current.day}T${current.hour}:${current.minute}`;
  const response = await fetch('/api/stations');
  const catalog = await response.json();
  if (!response.ok || catalog.error) throw new Error(catalog.error || '無法讀取車站清單');
  const byLabel = new Map(), byCode = new Map();
  for (const stop of catalog.stops) {
    const label = stationLabel(stop);
    byLabel.set(label, stop.id); byCode.set(stop.id, stop);
    const option = node('option'); option.value = label;
    el('route-stations').append(option);
  }
  origin.value = byCode.has('BL12') ? stationLabel(byCode.get('BL12')) : '';
  destination.value = byCode.has('BL22') ? stationLabel(byCode.get('BL22')) : '';
  feedback.textContent = `已載入 ${catalog.stops.length} 個站碼，可輸入站名或站碼查詢。`;
  submit.disabled = false;
  form.dataset.ready = 'true';
  const pane = map.createPane('queryRoute'); pane.style.zIndex = 510;
  const overlay = L.featureGroup().addTo(map);
  let requestNumber = 0, controller = null;

  // 將查詢路段裁切到既有 GeoJSON 軌道；沒有合適線形時才畫示意虛線。
  const geometries = new Map();
  for (const { data } of loaded) for (const feature of data?.features || []) {
    const p = feature.properties || {}, geometry = feature.geometry;
    if (!geometry) continue;
    let id = p.ref;
    if (id === '捷運紅線 (新北投支線)') id = 'R22A';
    if (id === 'G' && String(p.name || '').includes('小碧潭')) id = 'G03A';
    if (p.type !== 'route' || p.route !== 'subway') continue;
    const parts = geometry.type === 'LineString' ? [geometry.coordinates]
      : geometry.type === 'MultiLineString' ? geometry.coordinates : [];
    for (const part of parts) {
      if (!geometries.has(id)) geometries.set(id, []);
      geometries.get(id).push(part);
    }
  }
  const distance = (a, b) => Math.hypot((a[0] - b[0]) * 100900, (a[1] - b[1]) * 111200);
  function project(point, line) {
    let best = null, cumulative = 0;
    for (let i = 1; i < line.length; i++) {
      const a = line[i - 1], b = line[i], dx = (b[0] - a[0]) * 100900, dy = (b[1] - a[1]) * 111200;
      const length = Math.hypot(dx, dy);
      const t = length ? Math.max(0, Math.min(1, ((point[0] - a[0]) * 100900 * dx + (point[1] - a[1]) * 111200 * dy) / (length * length))) : 0;
      const position = [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
      const error = distance(point, position);
      if (!best || error < best.error) best = { error, position, index: i, along: cumulative + length * t };
      cumulative += length;
    }
    return best;
  }
  function shape(a, b, lineId) {
    let best = null;
    for (const line of geometries.get(lineId) || []) {
      const x = project(a, line), y = project(b, line);
      if (!x || !y || x.error > 450 || y.error > 450) continue;
      const length = Math.abs(x.along - y.along);
      if (length < 1 || length > distance(a, b) * 4 + 1000) continue;
      const score = x.error + y.error + length * .01;
      if (best && best.score <= score) continue;
      let points;
      if (x.along <= y.along) points = [x.position, ...line.slice(x.index, y.index), y.position];
      else points = [y.position, ...line.slice(y.index, x.index), x.position].reverse();
      best = { points, score };
    }
    return best ? { points: best.points, schematic: false } : { points: [a, b], schematic: true };
  }
  const toLatLng = s => [s.lat, s.lon];
  function draw(route) {
    overlay.clearLayers();
    let schematic = false;
    for (const step of route.steps) {
      if (step.type === 'walk') {
        L.polyline([toLatLng(step.from_stop), toLatLng(step.to_stop)], { pane: 'queryRoute',
          color: '#333333', weight: 4, dashArray: '4 7' })
          .bindTooltip(node('span', `轉乘步行示意：${minutes(step.duration_s)}`)).addTo(overlay);
      } else {
        const lineId = step.family === 'G-3' ? 'G03A' : step.family === 'R-3' ? 'R22A' : step.line_id;
        for (let i = 1; i < step.stops.length; i++) {
          const a = step.stops[i-1], b = step.stops[i];
          const segment = shape([a.lon, a.lat], [b.lon, b.lat], lineId);
          schematic ||= segment.schematic;
          const points = segment.points.map(p => [p[1], p[0]]);
          L.polyline(points, { pane: 'queryRoute', color: 'white', weight: 11, opacity: .95, interactive: false }).addTo(overlay);
          L.polyline(points, { pane: 'queryRoute', color: colors[lineId] || '#236a58', weight: 7,
            dashArray: segment.schematic ? '7 6' : undefined })
            .bindTooltip(node('span', `${a.name} → ${b.name}${segment.schematic ? '（站點連線示意）' : ''}`)).addTo(overlay);
        }
      }
    }
    const endpoints = new Map();
    for (const step of route.steps) {
      endpoints.set(step.from_id, { stop: step.from_stop, text: step.from_stop.name });
      endpoints.set(step.to_id, { stop: step.to_stop, text: step.to_stop.name });
    }
    endpoints.set(route.origin.id, { stop: route.origin, text: `起點：${route.origin.name}` });
    endpoints.set(route.destination.id, { stop: route.destination,
      text: `${route.origin.id === route.destination.id ? '起終點' : '終點'}：${route.destination.name}` });
    for (const { stop, text } of endpoints.values()) {
      L.circleMarker(toLatLng(stop), { pane: 'queryRoute', radius: 7, color: '#173b45', fillColor: 'white', fillOpacity: 1, weight: 3 })
        .bindTooltip(node('span', text), { permanent: true, direction: 'top', className: 'route-point-label' }).addTo(overlay);
    }
    if (overlay.getBounds().isValid()) map.fitBounds(overlay.getBounds(), { padding: [65, 65], maxZoom: 15 });
    return schematic;
  }
  function render(route) {
    results.replaceChildren(); results.hidden = false;
    const day = route.departure_at.slice(0, 10);
    const summary = node('div', undefined, 'route-summary');
    summary.append(node('div', `${route.origin.name} ${route.origin.id} → ${route.destination.name} ${route.destination.id}`));
    summary.append(node('strong', route.status === 'ok' ? `預估 ${minutes(route.total_s)}` : `已知行駛＋轉乘 ${minutes(route.known_duration_s)}`));
    summary.append(node('div', `搭車 ${minutes(route.ride_s)} · 步行 ${minutes(route.walk_s)}`),
      node('div', `候車 ${minutes(route.wait_s)} · 換車 ${route.transfer_count} 次 · ${route.stop_count} 站間路段`));
    if (route.arrival_at) summary.append(node('div', `預估抵達 ${clock(route.arrival_at, day)}`));
    summary.append(node('div', route.fare.total_twd === null ? '票價：資料待補' : `票價：NT$ ${route.fare.total_twd}`));
    results.append(summary);
    const focus = node('button', '查看全程', 'route-focus'); focus.type = 'button';
    focus.addEventListener('click', () => { if (overlay.getBounds().isValid()) map.fitBounds(overlay.getBounds(), { padding: [65, 65], maxZoom: 15 }); });
    results.append(focus);
    const list = node('ol', undefined, 'route-itinerary');
    let boarded = false;
    for (const step of route.steps) {
      const item = node('li');
      if (step.type === 'walk') {
        item.append(node('div', `${step.from_stop.name} ${step.from_id} → ${step.to_stop.name} ${step.to_id}`),
          node('div', `步行轉乘 ${minutes(step.duration_s)}`));
      } else {
        const heading = node('div', `${boarded ? '換搭' : '搭乘'} ${step.line_name}`, 'ride-heading');
        heading.style.setProperty('--route-color', colors[step.line_id] || '#236a58');
        item.append(heading, node('div', `往 ${step.direction_name} 方向`));
        if (step.branch_walk_s) item.append(node('div', `先在 ${step.from_stop.name} 轉乘步行 ${minutes(step.branch_walk_s)}`));
        item.append(node('div', `${step.from_stop.name} 上車 → ${step.to_stop.name} 下車`));
        if (step.departure_at) item.append(node('div', `候車 ${minutes(step.wait_s)}；${clock(step.departure_at, day)} 發車`),
          node('div', `${clock(step.arrival_at, day)} 抵達 · 搭車 ${minutes(step.ride_s)}`));
        else item.append(node('div', `搭車 ${minutes(step.ride_s)}；候車與抵達時間待補`));
        const detail = node('details'); detail.append(node('summary', `經過 ${step.stops.length} 個站點`),
          node('div', step.stops.map(s => `${s.name} ${s.id}`).join(' → '), 'route-note'));
        item.append(detail); boarded = true;
      }
      list.append(item);
    }
    if (!route.steps.length) list.append(node('li', '起點與終點相同，不需搭乘。'));
    results.append(list);
    const fareInfo = node('details'); fareInfo.append(node('summary', '票價明細'));
    for (const part of route.fare.parts) fareInfo.append(node('div',
      `${part.from_name} ${part.from_id} → ${part.to_name} ${part.to_id}：${part.fare_twd === null ? part.reason : 'NT$ ' + part.fare_twd}`, 'route-note'));
    fareInfo.append(node('p', route.fare.note, 'route-note')); results.append(fareInfo);
    const warnings = [...route.warnings];
    if (draw(route)) warnings.push('部分路段缺少可對應的軌道線形，使用站點連線虛線示意；不影響時間計算。');
    if (route.steps.some(s => s.type === 'walk')) warnings.push('黑色虛線為轉乘連接示意，步行時間取自轉乘表。');
    const notes = node('ul', undefined, 'route-warnings');
    for (const warning of warnings) notes.append(node('li', warning));
    results.append(notes);
  }
  function clear() {
    requestNumber++; controller?.abort(); controller = null;
    overlay.clearLayers(); results.replaceChildren(); results.hidden = true;
    feedback.textContent = ''; feedback.className = ''; submit.disabled = false;
  }
  el('route-clear').addEventListener('click', clear);
  el('route-swap').addEventListener('click', () => {
    clear(); [origin.value, destination.value] = [destination.value, origin.value];
  });
  form.addEventListener('input', clear);
  form.addEventListener('submit', async event => {
    event.preventDefault(); clear();
    const number = ++requestNumber;
    const requestController = new AbortController();
    controller = requestController;
    const timer = setTimeout(() => requestController.abort(), 20000);
    feedback.textContent = '正在比較班次與轉乘路線…'; submit.disabled = true;
    try {
      const params = new URLSearchParams({ origin: byLabel.get(origin.value.trim()) || origin.value.trim(),
        destination: byLabel.get(destination.value.trim()) || destination.value.trim(),
        departure_at: departure.value, holiday: el('route-holiday').checked ? '1' : '0' });
      const response = await fetch(`/api/route?${params}`, { signal: requestController.signal });
      const route = await response.json();
      if (number !== requestNumber) return;
      if (!response.ok || route.error) throw new Error(route.error || '查詢失敗');
      render(route);
      feedback.textContent = route.status === 'ok' ? '查詢完成，已在地圖標示路線。' : '已列出參考路線，班表資訊尚不完整。';
    } catch (error) {
      if (number !== requestNumber) return;
      feedback.textContent = error.name === 'AbortError' ? '查詢逾時，請重試。' : error.message;
      feedback.className = 'error';
    } finally {
      clearTimeout(timer);
      if (number === requestNumber) { submit.disabled = false; controller = null; }
    }
  });
};
