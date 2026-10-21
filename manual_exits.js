/* 人工校正介面；來源位置只供比對，正式座標必須由使用者點選或輸入。 */
window.setupManualExitEditor = async function (map) {
  const host = document.getElementById('manual-exit-controls');
  host.innerHTML = `
    <details class="manual-panel" id="manual-panel" open>
      <summary id="manual-title">缺漏出口人工校正</summary>
      <p class="manual-muted" id="manual-summary">正在讀取…</p>
      <details><summary>原始資料問題統計</summary><div id="manual-issues" class="manual-muted"></div></details>
      <label class="manual-check"><input id="manual-show" type="checkbox" checked>顯示人工確認出口（綠色）</label>
      <label class="manual-field">篩選處理狀態<select id="manual-filter"><option value="">全部</option></select></label>
      <div id="manual-list" class="manual-list" aria-label="待校正出口清單"></div>
      <p class="manual-muted">點清單移到車站附近。藍色是車站參考點、灰色是 OSM 參考位置，均非人工確認出口。</p>
      <form id="manual-form" class="manual-form" hidden>
        <h2 id="manual-selected-title"></h2>
        <div id="manual-facts" class="manual-facts"></div>
        <p id="manual-warning" class="manual-warning"></p>
        <details><summary>出口名稱與車站資料（可修正）</summary>
          <label class="manual-field">出口名稱<input id="manual-exit-name" maxlength="300"></label>
          <label class="manual-field">車站名稱<input id="manual-station-name" maxlength="300"></label>
          <label class="manual-field">車站代碼<input id="manual-station-ref" maxlength="300"></label>
          <label class="manual-field">出口編號（不明可留空）<input id="manual-exit-number" maxlength="300"></label>
          <label class="manual-field">交通系統<select id="manual-system"></select></label>
        </details>
        <div class="manual-actions">
          <button type="button" id="manual-locate">開始在地圖定位</button>
          <button type="button" id="manual-clear">清除座標</button>
          <button type="button" id="manual-reset-location">清除並重新定位</button>
        </div>
        <p id="manual-position-notice" class="manual-warning" role="status" hidden></p>
        <p class="manual-muted">下方只填實際出口位置，不會自動帶入車站中心或 OSM 參考座標。橘點是目前編輯的位置。</p>
        <label class="manual-field">WGS84 經度 longitude<input id="manual-lon" type="number" step="any" min="-180" max="180"></label>
        <label class="manual-field">WGS84 緯度 latitude<input id="manual-lat" type="number" step="any" min="-90" max="90"></label>
        <label class="manual-field">處理狀態<select id="manual-status"></select></label>
        <label class="manual-check"><input id="manual-position-confirmed" type="checkbox">已核對實際出口位置及所屬車站</label>
        <label class="manual-check"><input id="manual-in-service" type="checkbox">此出口已開放通行</label>
        <label class="manual-field">查證來源（已確認時必填）<textarea id="manual-source" rows="2" maxlength="2000" placeholder="官方出口圖網址，或現勘日期與紀錄等"></textarea></label>
        <label class="manual-field">備註<textarea id="manual-notes" rows="2" maxlength="3000" placeholder="例如：出口仍在施工，依現場圍籬確認"></textarea></label>
        <div class="manual-actions"><button class="manual-primary" id="manual-save" type="submit">儲存此筆校正</button></div>
        <button id="manual-reload" type="button">捨棄此筆未存變更並重讀</button>
      </form>
      <p id="manual-message" role="status" aria-live="polite"></p>
      <a href="/data/manual_verified_exits.geojson" target="_blank" rel="noopener">查看已儲存 GeoJSON</a>
    </details>`;
  const $ = id => document.getElementById('manual-' + id);
  const el = (tag, text) => { const e = document.createElement(tag); e.textContent = text; return e; };
  const banner = el('div', '定位模式：請在右側地圖點選實際出口位置；點選後仍需核對並儲存。');
  banner.id = 'manual-locate-banner'; banner.hidden = true;
  map.getContainer().parentElement.append(banner);
  map.createPane('manual-exits').style.zIndex = 540;
  const focusLayer = L.layerGroup().addTo(map), verifiedLayer = L.layerGroup().addTo(map);
  let data, selected = null, locating = false, saving = false, positionMethod = '';
  const drafts = new Map(); // 切換清單保留未存表單，但不寫入正式檔案。
  const fields = {
    exit_name: 'exit-name', station_name: 'station-name', station_ref: 'station-ref',
    exit_number: 'exit-number', transit_system: 'system', verification_status: 'status',
    verification_source: 'source', notes: 'notes', position_confirmed: 'position-confirmed', in_service: 'in-service'
  };
  function message(text, error = false) { $('message').textContent = text; $('message').dataset.error = String(error); }
  async function jsonRequest(url, options) {
    const response = await fetch(url, { cache: 'no-store', ...options });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || `HTTP ${response.status}`);
    return result;
  }
  function entryTitle(entry) {
    const v = entry.values;
    return [v.station_name || '車站待確認', v.station_ref, v.exit_number ? `出口 ${v.exit_number}` : '出口編號未提供'].filter(Boolean).join(' · ');
  }
  function setLocating(value) {
    locating = value; banner.hidden = !value;
    map.getContainer().classList.toggle('manual-locating', value);
    $('locate').textContent = value ? '停止地圖定位' : '開始在地圖定位';
    $('locate').setAttribute('aria-pressed', String(value));
  }
  function validPoint(c) {
    return c && c.length === 2 && c.every(Number.isFinite) && Math.abs(c[0]) <= 180 && Math.abs(c[1]) <= 90;
  }
  function values() {
    const v = {};
    for (const [key, id] of Object.entries(fields)) v[key] = $(id).type === 'checkbox' ? $(id).checked : $(id).value;
    const lon = $('lon').value.trim(), lat = $('lat').value.trim();
    v.coordinates = !lon && !lat ? null : [lon ? Number(lon) : NaN, lat ? Number(lat) : NaN];
    v.position_method = positionMethod;
    return v;
  }
  function fill(v) {
    for (const [key, id] of Object.entries(fields)) {
      if ($(id).type === 'checkbox') $(id).checked = Boolean(v[key]);
      else $(id).value = v[key] || '';
    }
    $('lon').value = v.coordinates?.[0] ?? '';
    $('lat').value = v.coordinates?.[1] ?? '';
    positionMethod = v.position_method || '';
  }
  function markDirty() {
    if (!selected) return;
    drafts.set(selected.id, values());
    message('此筆有未儲存變更，請按「儲存此筆校正」。');
    renderList(); drawVerified();
  }
  function positionChanged(text) {
    $('position-confirmed').checked = false;
    if (['confirmed', 'not_found'].includes($('status').value)) $('status').value = 'pending';
    $('position-notice').hidden = false;
    $('position-notice').textContent = text;
    markDirty(); drawFocus();
  }
  function clearPosition(relocate = false) {
    if (!selected || saving) return;
    $('lon').value = ''; $('lat').value = ''; positionMethod = '';
    // 清除／換點先退回待確認；正式檔案仍由使用者按儲存後更新。
    positionChanged(relocate
      ? '舊座標已從編輯畫面清除，請在地圖點選新位置，再核對並儲存。'
      : '座標已清空，請按「儲存此筆校正」保存清除結果；也可以重新定位。');
    setLocating(relocate);
  }
  function marker(coords, color, label, className, layer, interactive = false) {
    const point = L.circleMarker([coords[1], coords[0]], { pane: 'manual-exits', radius: 8,
      color: '#fff', weight: 2, fillColor: color, fillOpacity: 1, interactive, className }).addTo(layer);
    point.bindTooltip(el('span', label), { permanent: true, direction: 'right', offset: [10, 0] });
    return point;
  }
  function drawFocus() {
    focusLayer.clearLayers();
    if (!selected || !$('panel').open) return;
    if (validPoint(selected.station_coordinates)) marker(selected.station_coordinates, '#2563eb',
      `${selected.values.station_name}：車站參考點，非出口`, 'manual-station-point', focusLayer);
    if (validPoint(selected.reference_coordinates)) marker(selected.reference_coordinates, '#737d86',
      'OSM 參考位置，待核對', 'manual-reference-point', focusLayer);
    const c = values().coordinates;
    if (validPoint(c)) marker(c, '#e67e13', '目前編輯位置（以儲存結果為準）', 'manual-draft-point', focusLayer);
  }
  function renderList() {
    $('list').replaceChildren();
    const shown = data.entries.filter(e => !$('filter').value || e.values.verification_status === $('filter').value);
    for (const entry of shown) {
      const button = el('button', ''); button.type = 'button'; button.className = 'manual-item'; button.dataset.id = entry.id;
      button.setAttribute('aria-pressed', String(selected?.id === entry.id));
      button.append(el('span', entryTitle(entry)));
      button.append(el('small', `${data.statuses[entry.values.verification_status]}${drafts.has(entry.id) ? ' · 未儲存變更' : ''}`));
      button.disabled = saving;
      button.addEventListener('click', () => select(entry));
      $('list').append(button);
    }
    if (!shown.length) $('list').append(el('p', '此篩選條件沒有資料。'));
    $('title').textContent = `缺漏出口人工校正（${data.entries.length}）`;
    const saved = data.entries.filter(e => e.saved).length, eligible = data.entries.filter(e => e.routing_eligible).length;
    $('summary').textContent = `已儲存 ${saved} 筆 · 可供出口步行計算 ${eligible} 筆`;
  }
  function drawVerified() {
    verifiedLayer.clearLayers();
    for (const entry of data.entries) {
      if (entry.values.verification_status !== 'confirmed' || !validPoint(entry.values.coordinates) || !entry.saved) continue;
      const draft = drafts.get(entry.id);
      if (draft && (draft.verification_status !== 'confirmed' || !draft.position_confirmed
          || JSON.stringify(draft.coordinates) !== JSON.stringify(entry.values.coordinates))) continue;
      const content = el('div', '');
      content.append(el('strong', entryTitle(entry)), el('p', `人工確認：${entry.saved_at}`),
        el('p', `查證來源：${entry.values.verification_source}`),
        el('p', `WGS84 [經度, 緯度]：${entry.values.coordinates.join(', ')}`),
        el('p', entry.routing_eligible ? '可供出口步行計算' : '不列入捷運出口步行計算'));
      const reset = el('button', '清除並重新定位'); reset.type = 'button'; reset.className = 'walk-button';
      reset.addEventListener('click', () => {
        if (saving) return;
        map.closePopup(); $('panel').open = true; select(entry, false);
        clearPosition(true); $('form').scrollIntoView({ block: 'nearest' });
      });
      content.append(reset); L.DomEvent.disableClickPropagation(content);
      marker(entry.values.coordinates, '#198754', entryTitle(entry), 'manual-verified-point', verifiedLayer, true).bindPopup(content);
    }
  }
  function link(parent, title, url) {
    if (!/^https?:\/\//i.test(url || '')) { if (url) parent.append(el('p', `${title}：${url}`)); return; }
    const p = el('p', ''), a = el('a', title); a.href = url; a.target = '_blank'; a.rel = 'noopener'; p.append(a); parent.append(p);
  }
  function select(entry, pan = true) {
    selected = entry; setLocating(false); $('form').hidden = false; $('position-notice').hidden = true;
    $('selected-title').textContent = entryTitle(entry); fill(drafts.get(entry.id) || entry.values);
    const facts = $('facts'); facts.replaceChildren();
    const original = entry.original.properties;
    facts.append(el('p', `出口原名：${original.name || original.ExitName_zh || '未提供'}`),
      el('p', `來源：${entry.source_file} · ${entry.id}`),
      el('p', `車站：${entry.values.station_name || '未提供'} · ${entry.values.station_ref || '站碼未提供'}`),
      el('p', `OSM 參考經緯度：${entry.reference_coordinates?.join(', ') || '未提供'}（未確認）`));
    if (entry.reference_checked_on) facts.append(el('p', `參考資料查詢日：${entry.reference_checked_on}`));
    link(facts, '查看出口 OSM 原始資料', entry.source_url);
    link(facts, '查看車站對照來源', entry.station_source);
    $('warning').textContent = '原始資料問題：' + entry.issues.map(i => data.issue_labels[i] || i).join('；') +
      (entry.station_match_status === 'position_candidate' ? '。所列車站只是位置候選，請先人工確認歸屬。' : '') +
      (entry.view_kind === 'source_reference' ? '。無可用車站座標，僅移至 OSM 來源附近。' : '');
    renderList(); drawFocus(); drawVerified();
    if (pan && validPoint(entry.view_coordinates)) map.setView([entry.view_coordinates[1], entry.view_coordinates[0]], 18);
    message(drafts.has(entry.id) ? '已恢復此頁暫存的變更，尚未寫入檔案。' : entry.saved
      ? `已儲存：${entry.saved_at}。${entry.routing_eligible ? '可供出口步行計算。' : '不參與出口步行計算。'}`
      : '尚無人工儲存紀錄；請核對資料後儲存。');
  }
  async function load() {
    data = await jsonRequest('/manual-exits.json');
    $('issues').replaceChildren(...Object.entries(data.issue_counts).map(([issue, count]) => el('p', `${data.issue_labels[issue]}：${count} 筆`)),
      el('p', '同一筆可同時有多項問題；以上是原始資料狀態，不會隨人工確認改寫。'));
    for (const [target, options] of [['status', data.statuses], ['system', data.systems]]) {
      $(target).replaceChildren(...Object.entries(options).map(([value, title]) => new Option(title, value)));
    }
    const filter = $('filter').value;
    $('filter').replaceChildren(new Option('全部', ''), ...Object.entries(data.statuses).map(([value, title]) => new Option(title, value)));
    $('filter').value = filter; renderList(); drawVerified();
    if (data.orphan_ids.length) message(`有 ${data.orphan_ids.length} 筆人工紀錄已無對應來源，請檢查 GeoJSON。`, true);
    host.dataset.ready = 'true';
  }
  $('filter').addEventListener('change', renderList);
  $('show').addEventListener('change', () => $('show').checked ? verifiedLayer.addTo(map) : map.removeLayer(verifiedLayer));
  $('panel').addEventListener('toggle', () => { if (!$('panel').open) setLocating(false); drawFocus(); });
  $('locate').addEventListener('click', () => setLocating(!locating));
  $('clear').addEventListener('click', () => clearPosition());
  $('reset-location').addEventListener('click', () => clearPosition(true));
  $('form').addEventListener('input', event => {
    if (['manual-lon', 'manual-lat'].includes(event.target.id)) {
      positionMethod = 'typed_coordinates';
      positionChanged('座標已變更。請重新核對位置、選擇處理狀態並儲存。');
      return;
    }
    if (['manual-station-name', 'manual-station-ref', 'manual-system', 'manual-exit-number'].includes(event.target.id)) {
      $('position-confirmed').checked = false;
    }
    markDirty(); drawFocus();
  });
  map.on('click', event => {
    if (!locating || !selected || saving) return;
    $('lon').value = event.latlng.lng.toFixed(7); $('lat').value = event.latlng.lat.toFixed(7);
    positionMethod = 'map_click';
    setLocating(false); positionChanged('已選取新位置。確認正確後選「已確認」、勾選核對項目並儲存。');
  });
  $('form').addEventListener('submit', async event => {
    event.preventDefault(); if (!selected || saving) return;
    const v = values();
    if (v.coordinates !== null && !validPoint(v.coordinates)) { message('請完整填寫有效 WGS84 經度與緯度，或清除兩個欄位。', true); return; }
    saving = true; setLocating(false); renderList();
    const inputs = [...$('form').querySelectorAll('input, select, textarea, button')];
    inputs.forEach(e => e.disabled = true); $('save').textContent = '正在儲存…';
    try {
      const result = await jsonRequest('/manual-exits.json', { method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Manual-Edit-Token': data.csrf_token },
        body: JSON.stringify({ id: selected.id, revision: selected.revision, ...v }) });
      data.entries = data.entries.map(e => e.id === result.entry.id ? result.entry : e);
      drafts.delete(result.entry.id); select(result.entry, false);
      message(`已儲存至 ${result.output_file}（${result.entry.saved_at}）。${result.entry.routing_eligible ? '可供出口步行計算。' : '不參與出口步行計算。'}`);
    } catch (error) { message(`儲存失敗：${error.message}`, true); }
    finally { saving = false; inputs.forEach(e => e.disabled = false); $('save').textContent = '儲存此筆校正'; renderList(); }
  });
  $('reload').addEventListener('click', async () => {
    const id = selected?.id;
    try {
      await load(); drafts.delete(id);
      const entry = data.entries.find(e => e.id === id);
      if (entry) select(entry, false);
      else { selected = null; $('form').hidden = true; focusLayer.clearLayers(); message('此筆已不在待校正來源中。'); }
    } catch (error) { message(`重新讀取失敗：${error.message}`, true); }
  });
  window.addEventListener('beforeunload', event => { if (drafts.size || saving) { event.preventDefault(); event.returnValue = ''; } });
  try { await load(); }
  catch (error) { message(`人工校正資料載入失敗：${error.message}。原有地圖仍可使用。`, true); }
};
