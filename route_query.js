/* 在推薦行程中繪製捷運路線。 */
window.createTransitOverlay = function (map, loaded, colors) {
  const node = (tag, text, className) => {
    const item = document.createElement(tag);
    if (text !== undefined) item.textContent = text;
    if (className) item.className = className;
    return item;
  };
  const minutes = value => {
    const whole = Math.round(value), min = Math.floor(whole / 60), sec = whole % 60;
    return sec ? `${min} 分 ${sec} 秒` : `${min} 分鐘`;
  };
  const pane = map.createPane('queryRoute'); pane.style.zIndex = 510;
  const overlay = L.featureGroup().addTo(map);

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
  function draw(route, fit = true) {
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
    if (fit && overlay.getBounds().isValid()) map.fitBounds(overlay.getBounds(), { padding: [65, 65], maxZoom: 15 });
    return schematic;
  }
  return { drawRoute: draw, clearRoute: () => overlay.clearLayers() };
};
