window.setupItineraryQuery = async function (map, routeUI) {
  const el = id => document.getElementById(id);
  const node = (tag, text, cls) => {
    const item = document.createElement(tag);
    if (text !== undefined) item.textContent = text;
    if (cls) item.className = cls;
    return item;
  };
  const form = el('itinerary-form'), feedback = el('itinerary-feedback'), results = el('itinerary-results');
  const submit = el('itinerary-submit');
  const minutes = seconds => {
    const whole = Math.round(seconds);
    return `${Math.floor(whole / 60)} 分${whole % 60 ? ` ${whole % 60} 秒` : ''}`;
  };
  const clock = value => value.replace('T', ' ');
  const hoursText = status => status === 'open_per_data' ? '依來源時段可安排，仍請出發前核對' : '營業／開放時段待確認';
  const pane = map.createPane('itinerary'); pane.style.zIndex = 520;
  const overlay = L.featureGroup().addTo(map);
  let controller = null, number = 0;
  function clear() {
    number++; controller?.abort(); controller = null;
    overlay.clearLayers(); results.replaceChildren(); results.hidden = true;
    routeUI.clearRoute();
    feedback.textContent = ''; feedback.className = ''; submit.disabled = false;
  }
  function render(result) {
    routeUI.clearRoute();
    const schematic = routeUI.drawRoute(result.transit, false);
    results.replaceChildren(); results.hidden = false;
    const summary = node('div', undefined, 'route-summary');
    summary.append(node('strong', `全程預估 ${minutes(result.total_s)}`),
      node('div', `交通 ${minutes(result.transit.total_s + result.exit_buffer_s + result.walk_s)} · 景點 ${minutes(result.visit_s)} · 用餐 ${minutes(result.meal_s)}`),
      node('div', `預估結束：${clock(result.end_at)}`),
      node('div', result.transit.fare.total_twd === null ? '捷運票價：資料待補' : `捷運票價：NT$ ${result.transit.fare.total_twd}（不含餐費、門票）`));
    results.append(summary, node('p', result.reason, 'route-note'));
    const transit = node('details'); transit.open = true;
    transit.append(node('summary', `${result.transit.origin.name} → 台北車站：搭乘方式`));
    const steps = node('ol', undefined, 'route-itinerary');
    for (const step of result.transit.steps) {
      const item = node('li');
      if (step.type === 'walk') {
        item.append(node('div', `${step.from_stop.name} ${step.from_id} → ${step.to_stop.name} ${step.to_id}`),
          node('div', `轉乘步行 ${minutes(step.duration_s)}`));
      } else {
        item.append(node('div', `${step.line_name} · 往 ${step.direction_name}`),
          node('div', `${step.from_stop.name} 上車 → ${step.to_stop.name} 下車`),
          node('div', `${clock(step.departure_at)} 發車 · ${clock(step.arrival_at)} 抵達`),
          node('div', `候車 ${minutes(step.wait_s)} · 搭車 ${minutes(step.ride_s)}`));
        if (step.branch_walk_s) item.append(node('div', `換月台步行 ${minutes(step.branch_walk_s)}`));
      }
      steps.append(item);
    }
    if (!result.transit.steps.length) steps.append(node('li', '已在台北車站，不需搭乘捷運。'));
    transit.append(steps, node('p', `由 ${result.exit.name} 開始地面步行；出站預留 ${minutes(result.exit_buffer_s)}（估計）。`, 'route-note'));
    results.append(transit);
    const places = [result.exit, result.attraction, result.restaurant];
    const labels = [result.exit.name, `① ${result.attraction.name}`, `② ${result.restaurant.name}`];
    for (let i = 0; i < places.length; i++) {
      const place = places[i], popup = node('div');
      popup.append(node('strong', labels[i]));
      if (place.hours_status) popup.append(node('p', hoursText(place.hours_status)));
      L.circleMarker([place.lat, place.lon], { pane: 'itinerary', radius: 8,
        color: '#fff', weight: 2, fillColor: ['#0075BE', '#0F766E', '#EA580C'][i], fillOpacity: 1 })
        .bindTooltip(node('span', labels[i]), { permanent: true, direction: 'top' }).bindPopup(popup).addTo(overlay);
    }
    for (const [index, walk] of result.walks.entries()) {
      const description = `${walk.from_name} → ${walk.to_name}：${walk.distance_m.toLocaleString()} 公尺 · ${minutes(walk.duration_s)}`;
      L.geoJSON(walk.geometry, { style: { pane: 'itinerary', color: '#0891B2', weight: 5, dashArray: '7 5' } })
        .bindTooltip(node('span', description)).addTo(overlay);
      const place = index === 0 ? result.attraction : result.restaurant;
      const card = node('section', undefined, 'itinerary-card');
      card.append(node('h3', `${index + 1}. ${place.name}`), node('div', description),
        node('div', `${clock(place.arrival_at)} ～ ${clock(place.departure_at)}`),
        node('div', hoursText(place.hours_status)), node('div', `來源時段：${place.hours || '未提供'}`));
      if (/^https:\/\/www\.openstreetmap\.org\/(node|way|relation)\/\d+$/.test(place.source_url || '')) {
        const link = node('a', '查看地點來源'); link.href = place.source_url; link.target = '_blank'; link.rel = 'noopener noreferrer'; card.append(link);
      }
      const focus = node('button', '在地圖查看', 'route-focus'); focus.type = 'button';
      focus.addEventListener('click', () => map.setView([place.lat, place.lon], 17));
      card.append(node('br'), focus); results.append(card);
    }
    const bounds = L.latLngBounds(overlay.getBounds());
    const allBounds = L.latLngBounds(bounds.getSouthWest(), bounds.getNorthEast());
    allBounds.extend([result.transit.origin.lat, result.transit.origin.lon]);
    for (const step of result.transit.steps) for (const stop of step.stops || [step.from_stop, step.to_stop]) allBounds.extend([stop.lat, stop.lon]);
    const actions = node('div', undefined, 'route-actions');
    for (const [title, area] of [['查看遊玩範圍', bounds], ['查看全程', allBounds]]) {
      const button = node('button', title); button.type = 'button';
      button.addEventListener('click', () => map.fitBounds(area, { padding: [45, 45], maxZoom: 16 })); actions.append(button);
    }
    results.append(actions);
    const notes = node('details'); notes.append(node('summary', '計算條件與待確認資料'));
    const warnings = node('ul', undefined, 'route-warnings');
    for (const warning of result.warnings) warnings.append(node('li', warning));
    for (const walk of result.walks) {
      warnings.append(node('li', `${walk.from_name} → ${walk.to_name}：接路偏移 ${walk.snap_offsets_m?.join('／') || '未提供'} 公尺。`));
      if (walk.note) warnings.append(node('li', walk.note));
    }
    if (schematic) warnings.append(node('li', '部分捷運路段缺少線形，捷運虛線為示意；藍色步行線使用道路路徑。'));
    notes.append(warnings); results.append(notes);
    map.stop(); map.fitBounds(bounds, { padding: [50, 50], maxZoom: 16, animate: false });
  }
  try {
    const [catalog, options] = await Promise.all(['/api/stations', '/api/itinerary-options'].map(async url => {
      const response = await fetch(url); const data = await response.json();
      if (!response.ok || data.error) throw new Error(data.error || '資料載入失敗');
      return data;
    }));
    const labels = new Map(catalog.stops.map(s => [`${s.name} · ${s.id} · ${s.line_name}`, s.id]));
    const stationList = el('itinerary-stations'); stationList.replaceChildren();
    for (const label of labels.keys()) {
      const option = node('option'); option.value = label; stationList.append(option);
    }
    const origin = catalog.stops.find(s => s.id === 'BL07') || catalog.stops[0];
    el('itinerary-origin').value = `${origin.name} · ${origin.id} · ${origin.line_name}`;
    const timeParts = new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Taipei', year: 'numeric',
      month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).formatToParts(new Date());
    const current = Object.fromEntries(timeParts.map(part => [part.type, part.value]));
    el('itinerary-departure').value = `${current.year}-${current.month}-${current.day}T${current.hour}:${current.minute}`;
    feedback.textContent = `可開始推薦。每段道路步行上限 ${options.max_walk_m.toLocaleString()} 公尺，時段缺漏會標示待確認。`;
    submit.disabled = false; form.dataset.ready = 'true';
    el('itinerary-clear').addEventListener('click', () => clear());
    form.addEventListener('input', () => clear());
    form.addEventListener('submit', async event => {
      event.preventDefault(); clear();
      const current = ++number, request = new AbortController(); controller = request;
      const timer = setTimeout(() => request.abort(), 65000);
      submit.disabled = true; feedback.textContent = '正在比對景點、餐廳、捷運班表與道路步行路徑，首次查詢可能需要約 40 秒…';
      try {
        const params = new URLSearchParams({ origin: labels.get(el('itinerary-origin').value.trim()) || el('itinerary-origin').value.trim(),
          departure_at: el('itinerary-departure').value, holiday: el('itinerary-holiday').checked ? '1' : '0',
          preference: el('itinerary-preference').value, food: el('itinerary-food').value,
          budget_min: el('itinerary-budget').value, visit_min: el('itinerary-visit').value,
          meal_min: el('itinerary-meal').value, exit_min: el('itinerary-exit').value });
        const response = await fetch(`/api/itinerary?${params}`, { signal: request.signal }); const data = await response.json();
        if (current !== number) return;
        if (!response.ok || data.error) throw new Error(data.error || '推薦失敗');
        render(data); feedback.textContent = '已推薦 1 個景點＋1 間餐廳，藍色虛線為道路步行路徑。';
      } catch (error) {
        if (current !== number) return;
        feedback.textContent = error.name === 'AbortError' ? '查詢逾時，請稍後重試。' : error.message; feedback.className = 'error';
      } finally {
        clearTimeout(timer); if (current === number) { controller = null; submit.disabled = false; }
      }
    });
  } catch (error) {
    feedback.textContent = `推薦介面載入失敗：${error.message}`; feedback.className = 'error'; submit.disabled = true;
  }
};
