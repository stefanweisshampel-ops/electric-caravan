/* Gespann-Lader – Web-App
 * Karte: MapLibre GL + OpenFreeMap · Bewertungen: Supabase (oder Demo-Modus im Browser)
 */
(function () {
  'use strict';
  const CFG = window.GL_CONFIG || {};

  // ---------- helpers ----------
  const $ = (s) => document.querySelector(s);
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const norm = (s) => String(s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')
    .replace(/ß/g, 'ss').replace(/ae/g, 'a').replace(/oe/g, 'o').replace(/ue/g, 'u');
  const fmtKm = (v) => (v < 10 ? v.toFixed(1).replace('.', ',') : Math.round(v)) + ' km';
  const fmtEur = (v) => v.toFixed(2).replace('.', ',') + ' €';
  const fmtDate = (t) => { try { return new Date(t).toLocaleDateString('de-DE'); } catch (e) { return ''; } };
  const KX = 111.32 * Math.cos(51 * Math.PI / 180), KY = 110.57;
  const dist = (a, b, c, d) => Math.hypot((a - c) * KY, (b - d) * KX);
  const COLORS = { ja: '#1f8f4e', eng: '#d48806', nein: '#cf3d3d', open: '#3a6ea5', truck: '#9aa1a9' };
  const STATUS_TXT = { ja: 'Durchfahrt möglich', eng: 'Nur wenn wenig los', nein: 'Abkoppeln nötig' };
  let toastT = null;
  function toast(msg, ms) {
    const t = $('#toast'); t.textContent = msg; t.style.display = 'block';
    clearTimeout(toastT); toastT = setTimeout(() => { t.style.display = 'none'; }, ms || 2800);
  }
  function store(k, v) {
    try {
      if (v === undefined) return JSON.parse(localStorage.getItem(k));
      localStorage.setItem(k, JSON.stringify(v));
    } catch (e) { return null; }
    return null;
  }
  function debounce(fn, ms) { let t; return function () { clearTimeout(t); t = setTimeout(fn, ms); }; }
  async function fetchJson(url, ms) {
    const ctl = typeof AbortController !== 'undefined' ? new AbortController() : null;
    const tm = ctl ? setTimeout(() => ctl.abort(), ms || 15000) : null;
    try {
      const r = await fetch(url, ctl ? { signal: ctl.signal } : {});
      if (!r.ok) throw new Error(url + ' ' + r.status);
      return await r.json();
    } finally { if (tm) clearTimeout(tm); }
  }

  // ---------- state ----------
  const DEFAULTS = { minKw: 100, stat: 'alle', hideTruck: true, mw: false, term: false, rest: false, op: '', maxPrice: 0.62, hideUnknown: false, adac: true, motion: false };
  const F = Object.assign({}, DEFAULTS, store('gl-filter-v4') || {});
  let sites = [], places = [], axes = {}, MW = [], STAND = {}, PSTAND = '';
  const grid = new Map();
  const siteByKey = new Map();
  const AS = new Set();
  let map = null, mapReady = false, hasGlyphs = true;
  let route = null, detail = null, pending = null, saving = false;
  // backend
  let backend = 'demo', sb = null, user = null;
  let ratedSites = new Set();   // sites with community stats
  let mineSites = new Set();    // sites with own rating
  let notesCache = new Map();   // statKey -> [{status,note,updated_at,is_mine}]

  // ---------- data ----------
  const keyOf = (cc, lat, lon) => cc + '-' + lat.toFixed(4) + '_' + lon.toFixed(4);
  const cellOf = (lat, lon) => Math.round(lat / 0.01) + ':' + Math.round(lon / 0.01);

  function decodeCountry(cc, d) {
    STAND[cc] = d.stand; PSTAND = d.priceStand || PSTAND;
    Object.assign(axes, d.axes || {});
    const prices = d.prices || [], adac = d.adac || {}, motion = d.motion || {}, opPrice = d.opPrice || [];
    d.places.forEach((p) => places.push([p[0], p[1], p[2], p[3], p[4], cc]));
    d.sites.forEach((r) => {
      const fl = r[8];
      const A = {}; (r[12] || []).forEach(([a, p]) => { A[a] = p; AS.add(a); });
      const pi = opPrice[r[2]];
      const s = {
        i: sites.length, cc, lat: r[0], lon: r[1], op: d.ops[r[2]], name: r[3], addr: r[4], extra: r[5], kw: r[6], n: r[7],
        ccs: !!(fl & 1), cha: !!(fl & 2), mcs: !!(fl & 4), term: !!(fl & 8), h24: !!(fl & 16), truck: !!(fl & 32),
        rest: !!(fl & 64), tnear: !!(fl & 128), hours: r[9], since: r[10], mw: r[11], A,
        price: pi >= 0 ? prices[pi] : null, adac: pi >= 0 && adac[prices[pi].k] != null ? adac[prices[pi].k] : null,
        motion: pi >= 0 && motion[prices[pi].k] != null ? motion[prices[pi].k] : null,
        st: null, statKey: null, mine: null,
      };
      s.key = keyOf(cc, s.lat, s.lon);
      const parts = s.addr.split(', ');
      s.city = (parts[parts.length - 1] || '').replace(/^\d{4,5}\s*/, '');
      s.search = norm(s.op + ' ' + s.name);
      siteByKey.set(s.key, s);
      const c = cellOf(s.lat, s.lon);
      if (!grid.has(c)) grid.set(c, []);
      grid.get(c).push(s);
      sites.push(s);
    });
  }
  function nearestSite(lat, lon, maxKm) {
    let best = null, bd = maxKm;
    const cy = Math.round(lat / 0.01), cx = Math.round(lon / 0.01);
    for (let dy = -2; dy <= 2; dy++) for (let dx = -2; dx <= 2; dx++) {
      (grid.get((cy + dy) + ':' + (cx + dx)) || []).forEach((s) => {
        const dd = dist(lat, lon, s.lat, s.lon); if (dd < bd) { bd = dd; best = s; }
      });
    }
    return best;
  }
  function siteFor(key, lat, lon) {
    return siteByKey.get(key) || (typeof lat === 'number' && typeof lon === 'number' ? nearestSite(lat, lon, 0.15) : null);
  }

  // ---------- ratings ----------
  function statusOf(s) {
    const st = s.st;
    if (!st || !(st.ja + st.eng + st.nein)) return null;
    const m = Math.max(st.ja, st.eng, st.nein);
    if (st.nein === m) return 'nein';   // bei Gleichstand die vorsichtigere Einschätzung
    if (st.eng === m) return 'eng';
    return 'ja';
  }
  function applyStats(rows) {
    ratedSites.forEach((s) => { s.st = null; s.statKey = null; });
    ratedSites = new Set();
    (rows || []).forEach((r) => {
      const s = siteFor(r.site_key, r.lat, r.lon); if (!s) return;
      const st = s.st || { ja: 0, eng: 0, nein: 0, last: null };
      st.ja += r.n_ja | 0; st.eng += r.n_eng | 0; st.nein += r.n_nein | 0;
      if (!st.last || (r.last_at && r.last_at > st.last)) st.last = r.last_at;
      s.st = st; s.statKey = s.statKey || r.site_key; ratedSites.add(s);
    });
    refreshAll();
  }
  function applyMine(rows) {
    mineSites.forEach((s) => { s.mine = null; });
    mineSites = new Set();
    (rows || []).forEach((r) => {
      const s = siteFor(r.site_key, r.lat, r.lon); if (!s) return;
      s.mine = { key: r.site_key, status: r.status, note: r.note || '', t: r.updated_at };
      mineSites.add(s);
    });
    renderAcct();
    refreshAll();
  }

  // backend: Supabase
  function initBackend() {
    if (CFG.supabaseUrl && CFG.supabaseAnonKey && window.supabase && window.supabase.createClient) {
      backend = 'supabase';
      sb = window.supabase.createClient(CFG.supabaseUrl, CFG.supabaseAnonKey);
      sb.auth.getSession().then(({ data }) => setUser(data && data.session ? data.session.user : null));
      sb.auth.onAuthStateChange((ev, session) => setUser(session ? session.user : null));
      loadStats();
    } else {
      backend = 'demo';
      loadDemo();
    }
    renderAcct();
  }
  async function loadStats() {
    if (backend !== 'supabase') return;
    const { data, error } = await sb.rpc('site_stats');
    if (error) { toast('Bewertungen konnten nicht geladen werden.', 4000); return; }
    applyStats(data);
  }
  async function loadMine() {
    if (backend !== 'supabase') return;
    if (!user) { applyMine([]); return; }
    const { data, error } = await sb.from('ratings').select('site_key,status,note,updated_at,lat,lon');
    if (!error) applyMine(data);
  }
  let lastUserId = undefined;
  function setUser(u) {
    const id = u ? u.id : null;
    user = u;
    if (u) loginSent = null;
    renderAcct();
    if (id === lastUserId) return;
    lastUserId = id;
    loadMine();
    if (detail) { notesCache.delete(detail.statKey || detail.key); renderDetail(); loadNotes(detail); }
  }
  // Anmeldung per E-Mail-Link
  let loginSent = null, loginBusy = false;
  async function sendLogin(email) {
    email = (email || '').trim();
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) { toast('Bitte eine gültige E-Mail-Adresse eingeben.'); return; }
    if (loginBusy) return;
    loginBusy = true;
    const { error } = await sb.auth.signInWithOtp({ email, options: { emailRedirectTo: location.origin + location.pathname } });
    loginBusy = false;
    if (error) {
      const m = /(\d+)\s*second/i.exec(error.message || '');
      toast(m ? 'Bitte warte noch ' + m[1] + ' Sekunden, dann kannst du den Link erneut anfordern.'
        : 'Anmelde-Link konnte nicht verschickt werden: ' + error.message, 6000);
      return;
    }
    loginSent = { email };
    rerenderLogin();
  }
  function loginHtml(p, intro) {
    if (loginSent) {
      return '<div class="sent"><b>Link verschickt an ' + esc(loginSent.email) + '.</b><br>' +
        'Öffne die E-Mail und tippe auf den Link – am besten auf diesem Gerät. ' +
        'Nichts angekommen? Schau bitte auch im <b>Spam- oder Werbung-Ordner</b> nach, die Mail kann ein paar Minuten brauchen. ' +
        'Falls sie dort liegt, markiere sie als „kein Spam“, dann kommen die nächsten Links sicher an.' +
        '<div class="act"><button class="btn ghost" id="' + p + 'resend">Erneut senden</button><button class="btn link" id="' + p + 'other">Andere Adresse</button></div></div>';
    }
    return (intro ? '<div class="note" style="margin-top:0">' + intro + '</div>' : '') +
      '<div class="login"><input id="' + p + 'email" type="email" autocomplete="email" placeholder="E-Mail-Adresse"><button class="btn" id="' + p + 'send">Link senden</button></div>' +
      '<div class="note">Die Anmelde-Mail landet manchmal im Spam-Ordner – schau dort nach, falls sie nicht im Posteingang ist.</div>';
  }
  function bindLogin(p) {
    const el = (id) => document.getElementById(p + id);
    const on = (id, fn) => { if (el(id)) el(id).addEventListener('click', fn); };
    on('send', () => sendLogin(el('email').value));
    on('resend', () => sendLogin(loginSent && loginSent.email));
    on('other', () => { loginSent = null; rerenderLogin(); });
    if (el('email')) el('email').addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); sendLogin(el('email').value); } });
  }
  function rerenderLogin() { renderAcct(); if (detail) renderDetail(); }
  async function logout() { if (sb) await sb.auth.signOut(); toast('Abgemeldet'); }

  // backend: demo (nur dieser Browser)
  function demoStore(v) { return v === undefined ? (store('gl-demo-ratings') || {}) : store('gl-demo-ratings', v); }
  function loadDemo() {
    const all = demoStore();
    const rows = Object.keys(all).map((k) => Object.assign({ site_key: k }, all[k]));
    applyStats(rows.map((r) => ({ site_key: r.site_key, lat: r.lat, lon: r.lon, n_ja: r.status === 'ja' ? 1 : 0, n_eng: r.status === 'eng' ? 1 : 0, n_nein: r.status === 'nein' ? 1 : 0, last_at: r.updated_at })));
    applyMine(rows);
  }

  async function loadNotes(s) {
    const key = s.statKey || s.key;
    if (backend !== 'supabase' || !s.st) return;
    const { data, error } = await sb.rpc('site_ratings', { p_site_key: key });
    if (error) return;
    notesCache.set(key, data || []);
    if (detail === s) renderDetail();
  }

  async function saveRating() {
    const s = detail; if (!s || saving) return;
    const note = ($('#note') ? $('#note').value : '').trim().slice(0, 300);
    if (!pending) { toast('Wähle zuerst eine Bewertung.'); return; }
    const key = s.mine ? s.mine.key : s.key;
    if (s.mine && s.mine.status === pending && s.mine.note === note) { toast('Keine Änderung.'); return; }
    saving = true; renderDetail();
    try {
      if (backend === 'supabase') {
        if (!user) throw new Error('nicht angemeldet');
        const row = { site_key: key, country: s.cc, lat: s.lat, lon: s.lon, status: pending, note, site_name: (s.name || s.op).slice(0, 120), user_id: user.id };
        const { error } = await sb.from('ratings').upsert(row, { onConflict: 'site_key,user_id' });
        if (error) throw error;
        notesCache.delete(s.statKey || s.key);
        await Promise.all([loadMine(), loadStats()]);
        loadNotes(s);
      } else {
        const all = demoStore();
        all[key] = { lat: s.lat, lon: s.lon, status: pending, note, updated_at: new Date().toISOString() };
        demoStore(all); loadDemo();
      }
      toast('Gespeichert – danke!');
    } catch (e) {
      toast('Speichern fehlgeschlagen: ' + (e && e.message ? e.message : 'unbekannter Fehler'), 5000);
    }
    saving = false; if (detail === s) renderDetail();
  }
  async function deleteRating() {
    const s = detail; if (!s || !s.mine || saving) return;
    saving = true; renderDetail();
    try {
      if (backend === 'supabase') {
        const { error } = await sb.from('ratings').delete().eq('site_key', s.mine.key);
        if (error) throw error;
        notesCache.delete(s.statKey || s.key);
        await Promise.all([loadMine(), loadStats()]);
        loadNotes(s);
      } else {
        const all = demoStore(); delete all[s.mine.key]; demoStore(all); loadDemo();
      }
      pending = null; toast('Bewertung gelöscht');
    } catch (e) { toast('Löschen fehlgeschlagen.'); }
    saving = false; if (detail === s) renderDetail();
  }
  async function sendReport(reason) {
    const s = detail; if (!s || backend !== 'supabase' || !user) return;
    const { error } = await sb.from('reports').insert({ site_key: s.statKey || s.key, reason: (reason || '').slice(0, 500) });
    toast(error ? 'Meldung konnte nicht gesendet werden.' : 'Danke, die Meldung ist eingegangen.');
  }

  // ---------- prices ----------
  function bestPrice(s) {
    const p = s.price; if (!p) return null;
    const c = [];
    if (p.adhoc) c.push(p.adhoc[0]);
    if (p.app) c.push(p.app[0]);
    if (F.adac && s.adac != null) c.push(s.adac);
    if (F.motion && s.motion != null) c.push(s.motion);
    return c.length ? Math.min.apply(null, c) : null;
  }
  const priceShort = (s) => { const b = bestPrice(s); return b == null ? 'Preis ?' : 'ab ' + fmtEur(b); };

  // ---------- filtering ----------
  function passes(s) {
    if (s.truck && F.hideTruck) return false;
    if (s.kw < F.minKw) return false;
    if (F.mw && !(s.mw != null && s.mw <= 3)) return false;
    if (F.term && !s.term) return false;
    if (F.rest && !s.rest) return false;
    if (F.op && !s.search.includes(norm(F.op))) return false;
    if (F.maxPrice != null) {
      const bp = bestPrice(s);
      if (bp == null) { if (F.hideUnknown) return false; } else if (bp > F.maxPrice + 1e-9) return false;
    }
    const st = statusOf(s);
    if (F.stat === 'ja' && st !== 'ja') return false;
    if (F.stat === 'offen' && st) return false;
    if (F.stat === 'ohne-nein' && st === 'nein') return false;
    if (route && s.A[route.a] === undefined) return false;
    return true;
  }
  const filterActive = () => Object.keys(DEFAULTS).some((k) => F[k] !== DEFAULTS[k]);
  const colorKey = (s) => (s.truck ? 'truck' : (statusOf(s) || 'open'));
  const colorOf = (s) => COLORS[colorKey(s)];

  // ---------- map ----------
  const FALLBACK_STYLE = { version: 8, sources: {}, layers: [{ id: 'bg', type: 'background', paint: { 'background-color': '#eef0ee' } }] };
  async function loadStyle() {
    if (!CFG.mapStyle) return null;
    try { return await fetchJson(CFG.mapStyle, 8000); } catch (e) { return null; }
  }
  function isWide() { return window.innerWidth >= 900; }
  function sheetPx() { return $('#sheet').getBoundingClientRect().height; }
  function padding() {
    return isWide() ? { top: 70, left: 430, right: 60, bottom: 30 } : { top: 70, left: 24, right: 24, bottom: Math.round(sheetPx()) + 12 };
  }
  function viewOffset() { return isWide() ? [215, 0] : [0, -Math.round(sheetPx() / 2 - 30)]; }

  async function initMap() {
    let style = await loadStyle();
    if (!style) { hasGlyphs = false; style = FALLBACK_STYLE; toast('Die Hintergrundkarte konnte nicht geladen werden – die Ladestationen werden trotzdem angezeigt.', 5000); }
    map = new maplibregl.Map({
      container: 'map', style, center: [10.4, 51.2], zoom: 5, minZoom: 3, maxZoom: 18,
      attributionControl: false, dragRotate: false, pitchWithRotate: false, touchPitch: false,
    });
    map.touchZoomRotate.disableRotation();
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
    map.addControl(new maplibregl.GeolocateControl({ positionOptions: { enableHighAccuracy: true }, trackUserLocation: false, showAccuracyCircle: false }), 'top-right');
    map.addControl(new maplibregl.AttributionControl({ compact: true }), 'top-right');
    await new Promise((res) => { if (map.loaded()) res(); else map.once('load', res); });
    map.addSource('route', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
    map.addLayer({ id: 'route-line', type: 'line', source: 'route', paint: { 'line-color': '#1f4fa3', 'line-width': ['interpolate', ['linear'], ['zoom'], 5, 4, 10, 8], 'line-opacity': 0.45 }, layout: { 'line-cap': 'round', 'line-join': 'round' } });
    map.addSource('sites', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
    map.addLayer({
      id: 'sites-c', type: 'circle', source: 'sites',
      layout: { 'circle-sort-key': ['get', 'o'] },
      paint: {
        'circle-color': ['match', ['get', 'c'], 'ja', COLORS.ja, 'eng', COLORS.eng, 'nein', COLORS.nein, 'truck', COLORS.truck, COLORS.open],
        'circle-radius': ['interpolate', ['linear'], ['zoom'], 4, ['case', ['==', ['get', 'r'], 1], 3.4, 1.8], 7, ['case', ['==', ['get', 'r'], 1], 5, 3.4], 10, ['case', ['==', ['get', 'r'], 1], 8, 6], 14, ['case', ['==', ['get', 'r'], 1], 11, 9]],
        'circle-stroke-color': '#ffffff',
        'circle-stroke-width': ['interpolate', ['linear'], ['zoom'], 5, 0.5, 9, 1.5],
      },
    });
    map.addSource('sel', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
    map.addLayer({ id: 'sel-ring', type: 'circle', source: 'sel', paint: { 'circle-radius': 15, 'circle-color': 'rgba(0,0,0,0)', 'circle-stroke-color': '#1d2329', 'circle-stroke-width': 2.5 } });
    if (hasGlyphs) {
      map.addLayer({
        id: 'sites-l', type: 'symbol', source: 'sites', minzoom: 12,
        layout: { 'text-field': ['get', 'n'], 'text-font': ['Noto Sans Regular'], 'text-size': 11.5, 'text-anchor': 'left', 'text-offset': [1.1, 0], 'text-optional': true, 'text-max-width': 14 },
        paint: { 'text-color': '#1d2329', 'text-halo-color': '#ffffff', 'text-halo-width': 1.6 },
      });
    }
    map.on('click', (e) => {
      const p = e.point;
      const fs = map.queryRenderedFeatures([[p.x - 14, p.y - 14], [p.x + 14, p.y + 14]], { layers: ['sites-c'] });
      if (!fs.length) return;
      let best = fs[0], bd = Infinity;
      fs.forEach((f) => { const q = map.project(f.geometry.coordinates); const d = Math.hypot(q.x - p.x, q.y - p.y); if (d < bd) { bd = d; best = f; } });
      openDetail(sites[best.properties.i], false);
    });
    map.on('mousemove', 'sites-c', () => { map.getCanvas().style.cursor = 'pointer'; });
    map.on('mouseleave', 'sites-c', () => { map.getCanvas().style.cursor = ''; });
    map.on('moveend', debounce(() => { if (!detail && !route) renderList(); }, 120));
    mapReady = true;
    fitBox([[5.9, 47.3], [15.0, 55.0]], false);
  }
  function fitBox(box, animate) {
    if (!map) return;
    map.fitBounds(box, { padding: padding(), duration: animate === false ? 0 : 700, maxZoom: 13 });
  }
  function fitTo(points) {
    if (!points.length) return;
    let w = 180, s = 90, e = -180, n = -90;
    points.forEach(([lat, lon]) => { w = Math.min(w, lon); e = Math.max(e, lon); s = Math.min(s, lat); n = Math.max(n, lat); });
    fitBox([[w, s], [e, n]]);
  }
  function focusSite(s, zoom) {
    map.easeTo({ center: [s.lon, s.lat], zoom: Math.max(map.getZoom(), zoom || 14), offset: viewOffset(), duration: 650 });
  }
  function redrawMarkers() {
    $('#fbadge').style.display = filterActive() ? 'block' : 'none';
    if (!mapReady) return;
    const vis = sites.filter(passes);
    if (detail && !vis.includes(detail)) vis.push(detail);
    map.getSource('sites').setData({
      type: 'FeatureCollection',
      features: vis.map((s) => ({
        type: 'Feature', geometry: { type: 'Point', coordinates: [s.lon, s.lat] },
        properties: { i: s.i, c: colorKey(s), r: s.st ? 1 : 0, o: s.st ? 2 : (s.truck ? 0 : 1), n: s.name || s.op },
      })),
    });
    map.getSource('sel').setData({ type: 'FeatureCollection', features: detail ? [{ type: 'Feature', geometry: { type: 'Point', coordinates: [detail.lon, detail.lat] }, properties: {} }] : [] });
  }
  function refreshAll() {
    redrawMarkers();
    if (detail) renderDetail(); else renderList();
  }

  // ---------- sheet ----------
  const sheet = $('#sheet');
  function setSheet(sz) { sheet.classList.remove('small', 'big'); if (sz !== 'mid') sheet.classList.add(sz); }
  function sheetSize() { return sheet.classList.contains('small') ? 'small' : sheet.classList.contains('big') ? 'big' : 'mid'; }
  $('#grab').addEventListener('click', () => { const s = sheetSize(); setSheet(s === 'mid' ? 'big' : s === 'big' ? 'small' : 'mid'); });
  let y0 = null;
  $('#grab').addEventListener('touchstart', (e) => { y0 = e.touches[0].clientY; }, { passive: true });
  $('#grab').addEventListener('touchend', (e) => {
    if (y0 == null) return; const dy = e.changedTouches[0].clientY - y0; y0 = null;
    if (Math.abs(dy) < 25) return;
    const s = sheetSize();
    if (dy < 0) setSheet(s === 'small' ? 'mid' : 'big'); else setSheet(s === 'big' ? 'mid' : 'small');
  });

  const legalHtml = '<div class="legal"><a href="/autobahn/">Autobahnen</a> · <a href="/ratgeber/">Ratgeber</a> · <a href="impressum.html">Impressum</a> · <a href="datenschutz.html">Datenschutz</a></div>';
  function rowHtml(s, extra) {
    const st = statusOf(s);
    const sub = [];
    if (!route && s.mw != null && s.mw <= 3) sub.push(fmtKm(s.mw) + ' zur Autobahn');
    if (st) { const n = s.st.ja + s.st.eng + s.st.nein; sub.push(STATUS_TXT[st] + (n > 1 ? ' (' + n + ' Bewertungen)' : '')); }
    if (s.truck) sub.push('Lkw-Ladepark');
    if (s.term) sub.push('Kartenterminal');
    if (s.rest) sub.push('Autohof/Rastanlage');
    return '<button class="row" data-i="' + s.i + '">' +
      '<span class="dot" style="background:' + colorOf(s) + '"></span>' +
      '<span style="min-width:0"><div class="t">' + esc(s.name || s.op) + '</div>' +
      '<div class="m">' + esc((s.name ? s.op + ' · ' : '') + s.city) + '</div>' +
      (sub.length || extra ? '<div class="m">' + (extra ? extra + (sub.length ? ' · ' : '') : '') + esc(sub.join(' · ')) + '</div>' : '') +
      '</span><span class="kw"><b>' + s.kw + ' kW</b>' + esc(priceShort(s)) + '</span></button>';
  }
  function bindRows() {
    $('#body').querySelectorAll('.row').forEach((b) => b.addEventListener('click', () => openDetail(sites[+b.dataset.i], true)));
  }
  function renderList() {
    if (route) return renderRoute();
    const head = $('#sheethead'), body = $('#body');
    if (!mapReady) { head.innerHTML = '<h2>Schnelllader</h2>'; body.innerHTML = '<div class="empty">Karte wird geladen …</div>'; return; }
    const z = map.getZoom(), b = map.getBounds(), c = map.getCenter();
    const inView = sites.filter((s) => passes(s) && b.contains([s.lon, s.lat]));
    head.innerHTML = '<h2>Schnelllader</h2><span class="sub">' + inView.length.toLocaleString('de-DE') + ' im Ausschnitt' + (backend === 'demo' ? ' · Demo-Modus' : '') + '</span>';
    if (z < 8 && inView.length > 150) {
      body.innerHTML = '<div class="empty">Suche oben einen <b>Ort</b> oder eine <b>Autobahn</b> (z. B. „A9“), nutze die Standort-Taste oder zoome in die Karte.<br><br>' +
        'Tippe einen Standort an, prüfe ihn per Luftbild und bewerte ihn: <b>Durchfahrt</b>, <b>nur wenn wenig los</b> oder <b>abkoppeln</b>. ' +
        'Bisher bewertet: <b>' + ratedSites.size.toLocaleString('de-DE') + '</b> Standort' + (ratedSites.size === 1 ? '' : 'e') + (mineSites.size ? ', davon <b>' + mineSites.size + '</b> von dir' : '') + '.</div>' + legalHtml;
      return;
    }
    inView.forEach((s) => { s._d = dist(c.lat, c.lng, s.lat, s.lon); });
    inView.sort((a, b2) => a._d - b2._d);
    const shown = inView.slice(0, 120);
    body.innerHTML = (shown.length ? shown.map((s) => rowHtml(s)).join('') +
      (inView.length > shown.length ? '<div class="empty">Die ' + shown.length + ' nächsten zur Kartenmitte. Zoome hinein für mehr.</div>' : '')
      : '<div class="empty">Keine Schnelllader mit diesen Filtern im Ausschnitt.</div>') + legalHtml;
    bindRows();
  }
  function dirLabel(a, dir) {
    const o = axes[a] || 'ns';
    if (o === 'ns') return dir > 0 ? 'Süd → Nord' : 'Nord → Süd';
    return dir > 0 ? 'West → Ost' : 'Ost → West';
  }
  function renderRoute() {
    const head = $('#sheethead'), body = $('#body');
    const list = sites.filter(passes).sort((a, b) => (a.A[route.a] - b.A[route.a]) * route.dir);
    head.innerHTML = '<h2><span class="shield">' + esc(route.a) + '</span></h2><span class="sub">' + list.length + ' Schnelllader ≤ 3 km · ' + dirLabel(route.a, route.dir) + '</span>';
    $('#rcdir').textContent = dirLabel(route.a, route.dir);
    if (!list.length) { body.innerHTML = '<div class="empty">Keine Schnelllader mit diesen Filtern entlang der ' + esc(route.a) + '.</div>' + legalHtml; return; }
    let prev = null;
    body.innerHTML = list.map((s) => {
      const gk = prev == null ? 0 : Math.round(Math.abs(s.A[route.a] - prev));
      prev = s.A[route.a];
      const off = s.mw != null ? fmtKm(s.mw) + ' von der Autobahn' : '';
      return rowHtml(s, esc([gk >= 1 ? '+' + gk + ' km' : '', off].filter(Boolean).join(' · ')));
    }).join('') + '<div class="empty">Abstände ungefähr, entlang der Autobahnachse gemessen.</div>' + legalHtml;
    bindRows();
  }
  function startRoute(a) {
    route = { a, dir: store('gl-dir-' + a) || 1 };
    detail = null;
    if (mapReady) {
      map.getSource('route').setData({ type: 'FeatureCollection', features: MW.filter(([as]) => as.includes(a)).map(([, l]) => ({ type: 'Feature', geometry: { type: 'LineString', coordinates: l }, properties: {} })) });
    }
    $('#rcname').textContent = a;
    $('#routechip').style.display = 'flex'; document.body.classList.add('route');
    if (sheetSize() === 'small') setSheet('mid');
    redrawMarkers(); renderList();
    setHash(a);
    fitTo(sites.filter((s) => s.A[a] !== undefined).map((s) => [s.lat, s.lon]));
  }
  function endRoute() {
    route = null;
    if (mapReady) map.getSource('route').setData({ type: 'FeatureCollection', features: [] });
    $('#routechip').style.display = 'none'; document.body.classList.remove('route');
    redrawMarkers(); renderList();
    setHash('');
  }
  $('#rcx').addEventListener('click', endRoute);
  $('#rcflip').addEventListener('click', () => { route.dir *= -1; store('gl-dir-' + route.a, route.dir); if (!detail) renderList(); });

  // ---------- detail ----------
  function openDetail(s, fly) {
    detail = s; pending = s.mine ? s.mine.status : null;
    if (sheetSize() === 'small') setSheet('mid');
    redrawMarkers();
    renderDetail();
    loadNotes(s);
    setHash('s=' + s.key);
    if (fly) focusSite(s, 15);
  }
  function closeDetail() { detail = null; pending = null; redrawMarkers(); renderList(); setHash(route ? route.a : ''); }

  // ---------- teilbare Links: #A9 oder #s=DE-51.5000_11.9000 ----------
  function setHash(h) {
    try {
      if (/access_token|error_description/.test(location.hash)) return;  // Anmelde-Link noch nicht verarbeitet
      history.replaceState(null, '', h ? '#' + h : location.pathname + location.search);
    } catch (e) { /* egal */ }
  }
  function applyHash() {
    let h = '';
    try { h = decodeURIComponent(location.hash.slice(1)); } catch (e) { return; }
    if (!h || /access_token|error/.test(h)) return;
    const am = /^a\s*(\d{1,3})$/i.exec(h);
    if (am && AS.has('A' + am[1])) { q.value = 'A' + am[1]; startRoute('A' + am[1]); return; }
    const sm = /^s=([A-Z]{2}-[-0-9.]+_[-0-9.]+)$/.exec(h);
    if (sm && siteByKey.has(sm[1])) {
      openDetail(siteByKey.get(sm[1]), true);
    }
  }
  window.addEventListener('hashchange', applyHash);

  const ICON = {
    sat: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="3"/><path d="M3 15l5-5 4 4 3-3 6 6"/></svg>',
    sv: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="6" r="3"/><path d="M8 21l1-8h6l1 8M6 17c-2 .5-3 1.2-3 2 0 1.7 4 3 9 3s9-1.3 9-3c0-.8-1-1.5-3-2"/></svg>',
    nav: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><path d="M3 11l18-8-8 18-2-8-8-2z"/></svg>',
  };
  function priceHtml(s) {
    const p = s.price;
    if (!p) return '<div class="sec price"><h4>Preis ohne Abo</h4><div class="note" style="margin-top:0">Für diesen Betreiber ist kein Preis hinterlegt. Verbindlich ist der Preis, der vor dem Start an der Säule oder in der App angezeigt wird.</div></div>';
    const rng = (r) => r[0] === r[1] ? fmtEur(r[0]) : fmtEur(r[0]) + ' – ' + fmtEur(r[1]);
    const rows = [['Ad hoc (Karte/QR)', p.adhoc ? rng(p.adhoc) : 'unbekannt']];
    if (p.app) rows.push(['App ohne Grundgebühr' + (p.appName ? ' (' + p.appName + ')' : ''), rng(p.app)]);
    if (s.adac != null) rows.push(['ADAC e-Charge (Mitglieder)', fmtEur(s.adac) + (F.adac ? '' : ' – im Filter ausgeschaltet')]);
    if (s.motion != null) rows.push(['IONITY Motion (Abo 5,99 €/Monat)', 'ab ' + fmtEur(s.motion) + (F.motion ? '' : ' – im Filter ausgeschaltet')]);
    const b = bestPrice(s);
    return '<div class="sec price"><h4>Preise <span class="pbest' + (b != null && F.maxPrice != null && b > F.maxPrice ? ' over' : '') + '">' + (b != null ? 'ab ' + fmtEur(b) : '') + '</span></h4>' +
      '<table>' + rows.map(([k, v]) => '<tr><td>' + esc(k) + '</td><td>' + esc(v) + '</td></tr>').join('') + '</table>' +
      (p.note ? '<div class="note" style="margin-top:6px">' + esc(p.note) + '</div>' : '') +
      '<div class="note" style="margin-top:6px">Betreiberpreis für ' + esc(p.label) + ', Schnellladen (DC). Quelle: ' + esc(p.src) + '. Verbindlich ist der Preis vor dem Ladestart.</div></div>';
  }
  function communityHtml(s) {
    const st = s.st;
    if (!st) return '<div class="note" style="margin-top:0">Noch keine Bewertung. Sei die erste Person, die diesen Standort bewertet.</div>';
    const tally = '<div class="tally">' +
      (st.ja ? '<span class="ja">' + st.ja + '× Durchfahrt</span>' : '') +
      (st.eng ? '<span class="eng">' + st.eng + '× nur wenn wenig los</span>' : '') +
      (st.nein ? '<span class="nein">' + st.nein + '× abkoppeln</span>' : '') + '</div>';
    const notes = backend === 'demo'
      ? (s.mine && s.mine.note ? [{ status: s.mine.status, note: s.mine.note, updated_at: s.mine.t, is_mine: true }] : [])
      : (notesCache.get(s.statKey || s.key) || []).filter((r) => r.note);
    return tally + (notes.length ? '<ul class="notes">' + notes.slice(0, 10).map((r) =>
      '<li>' + esc(r.note) + '<small>' + esc(STATUS_TXT[r.status] || '') + ' · ' + fmtDate(r.updated_at) + (r.is_mine ? ' · deine Bewertung' : '') + '</small></li>').join('') + '</ul>' : '') +
      (st.last ? '<div class="note" style="margin-top:6px">Zuletzt bewertet am ' + fmtDate(st.last) + '.</div>' : '');
  }
  function rateFormHtml(s) {
    if (backend === 'supabase' && !user) {
      return loginHtml('l', 'Zum Bewerten kurz anmelden – ohne Passwort, du bekommst einen Link per E-Mail.');
    }
    const dis = saving ? ' disabled' : '';
    const m = s.mine;
    return '<div class="rbtns">' +
      '<button data-s="ja"' + dis + '>Durchfahrt<br>möglich</button>' +
      '<button data-s="eng"' + dis + '>Nur wenn<br>wenig los</button>' +
      '<button data-s="nein"' + dis + '>Abkoppeln<br>nötig</button></div>' +
      '<textarea class="n" id="note" maxlength="300" placeholder="Notiz, z. B. „Durchfahrt nur an Säule 3“ oder „Einfahrt zu eng“"' + dis + '>' + esc(m ? m.note : '') + '</textarea>' +
      '<div class="act"><button class="btn" id="save"' + dis + '>' + (m ? 'Bewertung ändern' : 'Speichern') + '</button>' +
      (m ? '<button class="btn ghost" id="del"' + dis + '>Löschen</button>' : '') +
      (backend === 'supabase' && s.st ? '<button class="btn link" id="rep">Falsche Angabe melden</button>' : '') +
      '<span class="meta">' + (m && m.t ? 'von dir am ' + fmtDate(m.t) : '') + '</span></div>' +
      '<div id="repbox" style="display:none"><textarea class="n" id="repreason" maxlength="500" placeholder="Was stimmt nicht?"></textarea><div class="act"><button class="btn ghost" id="repsend">Meldung senden</button></div></div>' +
      (backend === 'demo' ? '<div class="note">Demo-Modus: Es ist noch keine Datenbank verbunden. Deine Bewertung wird nur in diesem Browser gespeichert.</div>' : '');
  }
  function renderDetail() {
    const s = detail; if (!s) return;
    const head = $('#sheethead'), body = $('#body');
    const keepScroll = body.dataset.site === String(s.i) ? body.scrollTop : 0;
    const noteDraft = $('#note') && body.dataset.site === String(s.i) ? $('#note').value : null;
    head.innerHTML = '<button class="backbtn" id="back">‹ ' + (route ? esc(route.a) + '-Liste' : 'Liste') + '</button>';
    $('#back').addEventListener('click', closeDetail);
    const chips = [];
    chips.push('<span class="chip">bis ' + s.kw + ' kW</span>');
    chips.push('<span class="chip">' + s.n + ' Ladepunkt' + (s.n === 1 ? '' : 'e') + '</span>');
    const plugs = [s.ccs && 'CCS', s.cha && 'CHAdeMO', s.mcs && 'MCS'].filter(Boolean).join(' · ');
    if (plugs) chips.push('<span class="chip">' + plugs + '</span>');
    if (s.term) chips.push('<span class="chip">Kartenterminal</span>');
    chips.push('<span class="chip">' + (s.h24 ? '24/7' : esc(s.hours || 'Öffnungszeiten unbekannt')) + '</span>');
    Object.keys(s.A).sort((a, b) => +a.slice(1) - +b.slice(1)).forEach((a) => chips.push('<span class="chip mwc">' + esc(a) + '</span>'));
    if (s.mw != null) chips.push('<span class="chip mwc">' + fmtKm(s.mw) + ' zur Autobahn</span>');
    if (s.rest) chips.push('<span class="chip hint">Autohof / Rastanlage</span>');
    if (s.tnear) chips.push('<span class="chip hint">Lkw-Ladepark nebenan</span>');
    if (s.since) chips.push('<span class="chip">seit ' + esc(s.since.slice(0, 7).split('-').reverse().join('/')) + '</span>');
    const ll = s.lat + ',' + s.lon;
    const links = [
      ['https://www.google.com/maps/@?api=1&map_action=map&center=' + ll + '&zoom=19&basemap=satellite', ICON.sat, 'Luftbild Google'],
      ['https://maps.apple.com/?ll=' + ll + '&z=19&t=k', ICON.sat, 'Luftbild Apple'],
      ['https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=' + ll, ICON.sv, 'Street View'],
      ['https://www.google.com/maps/dir/?api=1&destination=' + ll + '&travelmode=driving', ICON.nav, 'Navigation'],
    ].map(([h, ic, t]) => '<a href="' + h + '" target="_blank" rel="noopener">' + ic + '<span>' + t + '</span></a>').join('');
    body.innerHTML = '<div class="det">' +
      '<h3>' + esc(s.name || s.op) + '</h3>' +
      (s.name ? '<div class="op">' + esc(s.op) + '</div>' : '') +
      '<div class="addr">' + esc(s.addr) + '</div>' +
      (s.extra ? '<div class="extra">' + esc(s.extra) + '</div>' : '') +
      (s.truck ? '<div class="warn"><b>Lkw-Ladepark.</b> Pkw-Ladekarten funktionieren hier meist nicht.</div>' : '') +
      '<div class="chips">' + chips.join('') + '</div>' +
      '<div class="links">' + links + '</div>' +
      '<div class="sec"><h4>Mit Gespann – Bewertungen</h4>' + communityHtml(s) + '</div>' +
      '<div class="sec"><h4>' + (s.mine ? 'Deine Bewertung' : 'Selbst bewerten') + '</h4>' + rateFormHtml(s) + '</div>' +
      priceHtml(s) +
      '<div class="note">Stationsdaten laut Ladesäulenregister der Bundesnetzagentur, Stand ' + esc((STAND[s.cc] || '').split('-').reverse().join('.')) +
      '. Ob man mit Anhänger durchfahren kann, steht in keinem amtlichen Datensatz – die Bewertungen stammen von Nutzerinnen und Nutzern.</div></div>' + legalHtml;
    body.dataset.site = String(s.i);
    body.scrollTop = keepScroll;
    if (noteDraft != null && $('#note')) $('#note').value = noteDraft;
    body.querySelectorAll('.rbtns button').forEach((b) => {
      b.classList.toggle('on', b.dataset.s === pending);
      b.addEventListener('click', () => {
        pending = b.dataset.s;
        body.querySelectorAll('.rbtns button').forEach((x) => x.classList.toggle('on', x.dataset.s === pending));
      });
    });
    const on = (id, fn) => { const el = $('#' + id); if (el) el.addEventListener('click', fn); };
    on('save', saveRating);
    on('del', deleteRating);
    bindLogin('l');
    on('rep', () => { $('#repbox').style.display = 'block'; });
    on('repsend', () => { sendReport($('#repreason').value); $('#repbox').style.display = 'none'; });
  }

  // ---------- account ----------
  function renderAcct() {
    const el = $('#acct'); if (!el) return;
    $('#ibadge').style.display = (backend === 'supabase' && user) ? 'block' : 'none';
    if (backend === 'demo') {
      el.innerHTML = '<b>Demo-Modus.</b> Es ist noch keine Datenbank verbunden (siehe <code>config.js</code>). Bewertungen werden nur in diesem Browser gespeichert.';
      return;
    }
    if (!user) {
      el.innerHTML = '<b>Nicht angemeldet.</b> Zum Bewerten mit E-Mail anmelden – ohne Passwort, du bekommst einen Link.' + loginHtml('a', '');
      bindLogin('a');
      return;
    }
    el.innerHTML = 'Angemeldet als <b>' + esc(user.email || '') + '</b><br>Deine Bewertungen: <b>' + mineSites.size + '</b>' +
      '<div class="act"><button class="btn ghost" id="alogout">Abmelden</button></div>';
    $('#alogout').addEventListener('click', logout);
  }

  // ---------- search ----------
  const q = $('#q'), sugg = $('#sugg');
  let suggItems = [];
  function renderSugg() {
    const v = q.value.trim();
    $('#qclear').style.display = v ? 'block' : 'none';
    if (!v) { sugg.style.display = 'none'; return; }
    const items = [];
    const am = v.match(/^a\s*(\d{1,3})$/i);
    if (am) {
      const pre = 'A' + am[1];
      [...AS].filter((a) => a === pre || a.startsWith(pre)).sort((a, b) => (a === pre ? -1 : 0) - (b === pre ? -1 : 0) || +a.slice(1) - +b.slice(1)).slice(0, 5)
        .forEach((a) => items.push({ type: 'a', a, html: '<span class="shield">' + a + '</span> Schnelllader entlang der ' + a }));
    }
    const nv = norm(v);
    if (nv.length >= 2) {
      const starts = [], contains = [];
      for (const p of places) {
        const n = norm(p[0]);
        if (n.startsWith(nv)) starts.push(p); else if (nv.length >= 3 && n.includes(nv)) contains.push(p);
        if (starts.length >= 8) break;
      }
      starts.concat(contains).slice(0, 8 - Math.min(items.length, 3)).forEach((p) =>
        items.push({ type: 'p', p, html: esc(p[0]) + '<span class="k">' + esc(p[1] || p[5]) + '</span>' }));
    }
    suggItems = items;
    if (!items.length) { sugg.innerHTML = '<button disabled>Nichts gefunden</button>'; sugg.style.display = 'block'; return; }
    sugg.innerHTML = items.map((it, i) => '<button data-k="' + i + '">' + it.html + '</button>').join('');
    sugg.style.display = 'block';
    sugg.querySelectorAll('button[data-k]').forEach((b) => b.addEventListener('click', () => pick(suggItems[+b.dataset.k])));
  }
  function pick(it) {
    if (!it) return;
    sugg.style.display = 'none'; q.blur();
    if (it.type === 'a') { q.value = it.a; startRoute(it.a); return; }
    q.value = it.p[0];
    if (route) endRoute();
    detail = null; redrawMarkers();
    if (sheetSize() === 'small') setSheet('mid');
    map.easeTo({ center: [it.p[3], it.p[2]], zoom: 11, offset: viewOffset(), duration: 800 });
  }
  q.addEventListener('input', renderSugg);
  q.addEventListener('focus', renderSugg);
  q.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); pick(suggItems[0]); } if (e.key === 'Escape') { sugg.style.display = 'none'; q.blur(); } });
  $('#qclear').addEventListener('click', () => { q.value = ''; renderSugg(); q.focus(); });
  document.addEventListener('click', (e) => { if (!$('#searchwrap').contains(e.target)) sugg.style.display = 'none'; });

  // ---------- filter panel ----------
  function syncFilterUi() {
    $('#fkw').querySelectorAll('button').forEach((b) => b.classList.toggle('on', +b.dataset.v === F.minKw));
    $('#fstat').querySelectorAll('button').forEach((b) => b.classList.toggle('on', b.dataset.v === F.stat));
    $('#fprice').querySelectorAll('button').forEach((b) => b.classList.toggle('on', (b.dataset.v === 'x' ? null : +b.dataset.v) === F.maxPrice));
    $('#ftruck').checked = F.hideTruck; $('#fmw').checked = F.mw; $('#fterm').checked = F.term; $('#frest').checked = F.rest;
    $('#funk').checked = F.hideUnknown; $('#fadac').checked = F.adac; $('#fmotion').checked = F.motion;
    $('#fop').value = F.op;
  }
  function filterChanged() { store('gl-filter-v4', F); syncFilterUi(); refreshAll(); }
  $('#fkw').addEventListener('click', (e) => { const b = e.target.closest('button'); if (b) { F.minKw = +b.dataset.v; filterChanged(); } });
  $('#fstat').addEventListener('click', (e) => { const b = e.target.closest('button'); if (b) { F.stat = b.dataset.v; filterChanged(); } });
  $('#fprice').addEventListener('click', (e) => { const b = e.target.closest('button'); if (b) { F.maxPrice = b.dataset.v === 'x' ? null : +b.dataset.v; filterChanged(); } });
  $('#ftruck').addEventListener('change', (e) => { F.hideTruck = e.target.checked; filterChanged(); });
  $('#fmw').addEventListener('change', (e) => { F.mw = e.target.checked; filterChanged(); });
  $('#fterm').addEventListener('change', (e) => { F.term = e.target.checked; filterChanged(); });
  $('#frest').addEventListener('change', (e) => { F.rest = e.target.checked; filterChanged(); });
  $('#funk').addEventListener('change', (e) => { F.hideUnknown = e.target.checked; filterChanged(); });
  $('#fadac').addEventListener('change', (e) => { F.adac = e.target.checked; filterChanged(); });
  $('#fmotion').addEventListener('change', (e) => { F.motion = e.target.checked; filterChanged(); });
  $('#fop').addEventListener('input', debounce(() => { F.op = $('#fop').value.trim(); filterChanged(); }, 250));
  $('#freset').addEventListener('click', () => { Object.assign(F, DEFAULTS); filterChanged(); });
  $('#fbtn').addEventListener('click', () => { syncFilterUi(); $('#fmodal').classList.add('open'); });
  $('#fclose').addEventListener('click', () => $('#fmodal').classList.remove('open'));
  $('#fmodal').addEventListener('click', (e) => { if (e.target.id === 'fmodal') $('#fmodal').classList.remove('open'); });
  $('#ibtn').addEventListener('click', () => { renderAcct(); $('#imodal').classList.add('open'); });
  $('#iclose').addEventListener('click', () => $('#imodal').classList.remove('open'));
  $('#imodal').addEventListener('click', (e) => { if (e.target.id === 'imodal') $('#imodal').classList.remove('open'); });

  // ---------- boot ----------
  async function boot() {
    try {
      const V = '?v=' + (window.GL_VERSION || Date.now());
      const countries = await fetchJson('data/countries.json' + V);
      const [datas, mw] = await Promise.all([
        Promise.all(countries.map((c) => fetchJson(c.file + V, 60000).then((d) => [c.code, d]))),
        fetchJson('data/mw.json' + V).catch(() => []),
      ]);
      datas.forEach(([cc, d]) => decodeCountry(cc, d));
      MW = mw;
      places.sort((a, b) => b[4] - a[4]);
    } catch (e) {
      $('#loading').textContent = 'Die Ladesäulendaten konnten nicht geladen werden.';
      return;
    }
    const nCar = sites.filter((s) => !s.truck).length;
    $('#istand').innerHTML = '<b>Datenstand:</b> ' + Object.keys(STAND).map((cc) => cc + ' ' + esc(String(STAND[cc]).split('-').reverse().join('.'))).join(', ') +
      ' · ' + nCar.toLocaleString('de-DE') + ' Pkw-Schnellladestandorte ab 50 kW · Preise recherchiert am ' + esc(PSTAND) + '.';
    $('#loading').style.display = 'none';
    renderList();
    initBackend();
    try { await initMap(); } catch (e) { toast('Die Karte konnte nicht gestartet werden.', 5000); }
    redrawMarkers();
    renderList();
    applyHash();
  }
  boot();
})();
