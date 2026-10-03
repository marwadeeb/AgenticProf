/* Paper-to-Playground page runtime (generic; nothing paper-specific). Builds the controls described in SPEC,
 * re-runs the generated compute/view/readout/insight and live INVARIANTS on every change, loads exploration
 * presets, applies zero-token reader settings and re-runs the generated TESTS in the browser. */
(function () {
  'use strict';
  var SPEC = window.__P2P_SPEC__ || { controls: [], explorations: [] };
  var C = Array.isArray(SPEC.controls) ? SPEC.controls : [];
  var M = (typeof MODEL !== 'undefined' && MODEL) ? MODEL : null;
  var READY = !!(M && typeof M.compute === 'function' && typeof M.view === 'function');
  var TAG = /&lt;(\/?)(sub|sup|i|b|em|strong|code|br)\s*\/?&gt;/gi;
  var state = P2P.defaults(C), deps = {}, raf = 0, prevVals = {};
  C.forEach(function (c) {
    ['length', 'rows', 'cols'].forEach(function (k) { if (typeof c[k] === 'string') (deps[c[k]] = deps[c[k]] || []).push(c); });
  });

  function $(id) { return document.getElementById(id); }
  function esc(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
  function rich(s) { return esc(s === undefined || s === null ? '' : s).replace(TAG, function (m, sl, t) { return '<' + sl + t.toLowerCase() + '>'; }); }
  function plain(s) { return String(s === undefined || s === null ? '' : s).replace(/<[^>]*>/g, ''); }
  function clone(x) { return JSON.parse(JSON.stringify(x)); }
  function isNum(x) { return typeof x === 'number' && isFinite(x); }
  function numOf(s) { var m = String(s).replace(/\u2212/g, '-').match(/-?\d+(\.\d+)?(e[-+]?\d+)?/i); return m ? parseFloat(m[0]) : NaN; }
  function decimals(c) {
    var s = String(c.step === undefined ? '' : c.step), i;
    if (s.indexOf('e-') >= 0) return Math.min(8, parseInt(s.split('e-')[1], 10) || 3);
    i = s.indexOf('.');
    return i < 0 ? 0 : Math.min(8, s.length - i - 1);
  }
  function show(c, v) { return isNum(v) ? v.toFixed(decimals(c)) : String(v); }
  function clamp(c, v) { if (isNum(c.min) && v < c.min) v = c.min; if (isNum(c.max) && v > c.max) v = c.max; return v; }
  function el(tag, attrs, html) {
    var e = document.createElement(tag), k;
    if (attrs) for (k in attrs) if (attrs[k] !== undefined && attrs[k] !== null) e.setAttribute(k, attrs[k]);
    if (html !== undefined) e.innerHTML = html;
    return e;
  }
  function fmtVal(v) { return typeof v === 'number' ? V.fmt(v, 4) : (v === undefined || v === null ? '\u2014' : String(v)); }
  function showError(msg) { var b = $('p2p-error'); b.textContent = msg; b.hidden = false; }
  function hideError() { var b = $('p2p-error'); if (!b.hidden) { b.hidden = true; b.textContent = ''; } }
  function setStatus(msg) { var s = $('p2p-status'); s.textContent = msg || ''; s.hidden = !msg; }
  function val(id, d) { var e = $(id); if (!e) return d; return e.type === 'checkbox' ? e.checked : e.value; }

  function getCell(c, i, j) { var v = state[c.id] || []; return c.type === 'matrix' ? (v[i] || [])[j] : v[j]; }
  function setCell(c, i, j, v) {
    var a = state[c.id];
    if (!a) return;
    if (c.type === 'matrix') { if (a[i]) a[i][j] = v; } else a[j] = v;
    changed(c);
  }
  function buildGrid(c, host) {
    host = host || $('grid-' + c.id);
    if (!host) return;
    var isM = c.type === 'matrix', vals = state[c.id] || [], rows = isM ? vals : [vals];
    var R = rows.length, K = R ? rows[0].length : 0, i, j, h = '', iid;
    var cl = (isM ? c.col_labels : c.labels) || [], rl = c.row_labels || [];
    var lim = (isNum(c.min) ? ' min="' + c.min + '"' : '') + (isNum(c.max) ? ' max="' + c.max + '"' : '') + ' step="' + (isNum(c.step) && c.step > 0 ? c.step : 'any') + '"';
    h += '<thead><tr>' + (isM ? '<th></th>' : '');
    for (j = 0; j < K; j++) h += '<th>' + rich(cl[j] !== undefined ? cl[j] : String(j + 1)) + '</th>';
    h += '</tr></thead><tbody>';
    for (i = 0; i < R; i++) {
      h += '<tr>' + (isM ? '<th>' + rich(rl[i] !== undefined ? rl[i] : String(i + 1)) + '</th>' : '');
      for (j = 0; j < K; j++) {
        iid = isM ? ('in-' + c.id + '-' + (i + 1) + '-' + (j + 1)) : ('in-' + c.id + '-' + (j + 1));
        h += '<td><input type="number" id="' + iid + '" data-i="' + i + '" data-j="' + j + '"' + lim + ' value="' + esc(rows[i][j]) +
          '" aria-label="' + esc(plain(c.label || c.id)) + (isM ? ' row ' + (i + 1) : '') + ' entry ' + (j + 1) + '"></td>';
      }
      h += '</tr>';
    }
    var t = document.createElement('table');
    t.className = 'gridin';
    t.innerHTML = h + '</tbody>';
    host.innerHTML = '';
    host.appendChild(t);
    t.addEventListener('input', function (ev) {
      var inp = ev.target; if (!inp || inp.tagName !== 'INPUT') return;
      var v = parseFloat(inp.value); if (!isFinite(v)) return;
      setCell(c, +inp.getAttribute('data-i'), +inp.getAttribute('data-j'), v);
    });
    t.addEventListener('change', function (ev) {
      var inp = ev.target; if (!inp || inp.tagName !== 'INPUT') return;
      var i2 = +inp.getAttribute('data-i'), j2 = +inp.getAttribute('data-j'), v = parseFloat(inp.value);
      if (!isFinite(v)) v = getCell(c, i2, j2);
      v = clamp(c, v); inp.value = v; setCell(c, i2, j2, v);
    });
  }
  function buildControls() {
    var host = $('p2p-controls');
    host.innerHTML = '';
    C.forEach(function (c) {
      var box = el('div', { 'class': 'ctrl ctrl-' + c.type, id: 'ctrl-' + c.id, 'data-control': c.id }), head = el('div', { 'class': 'ctrl-head' });
      box.appendChild(head);
      if (c.type === 'toggle') {
        var sw = el('label', { 'class': 'switch' }), cb = el('input', { type: 'checkbox', id: 'in-' + c.id });
        cb.checked = !!state[c.id];
        sw.appendChild(cb);
        sw.appendChild(el('span', { 'class': 'knob', 'aria-hidden': 'true' }));
        sw.appendChild(el('span', null, rich(c.label || c.id)));
        head.appendChild(sw);
        var st = el('span', { 'class': 'state' }, cb.checked ? 'on' : 'off');
        head.appendChild(st);
        cb.addEventListener('change', function () { state[c.id] = cb.checked; st.textContent = cb.checked ? 'on' : 'off'; changed(c); });
      } else {
        head.appendChild(el('label', (c.type === 'vector' || c.type === 'matrix') ? null : { 'for': 'in-' + c.id }, rich(c.label || c.id)));
      }
      if (c.type === 'slider') {
        var nb = el('input', { type: 'number', 'class': 'num', id: 'num-' + c.id, min: c.min, max: c.max, step: c.step, 'aria-label': plain(c.label || c.id) + ' (exact value)' });
        nb.value = show(c, state[c.id]);
        head.appendChild(nb);
        var rg = el('input', { type: 'range', id: 'in-' + c.id, min: c.min, max: c.max, step: c.step });
        rg.value = state[c.id];
        box.appendChild(rg);
        box.appendChild(el('div', { 'class': 'ends' }, '<span>' + esc(show(c, c.min)) + '</span><span>' + esc(show(c, c.max)) + '</span>'));
        rg.addEventListener('input', function () {
          var v = parseFloat(rg.value); if (!isFinite(v)) return;
          state[c.id] = v; nb.value = show(c, v); changed(c);
        });
        nb.addEventListener('change', function () {
          var v = parseFloat(nb.value); if (!isFinite(v)) v = state[c.id];
          v = clamp(c, v); state[c.id] = v; nb.value = show(c, v); rg.value = v; changed(c);
        });
      } else if (c.type === 'number') {
        var ni = el('input', { type: 'number', 'class': 'num wide', id: 'in-' + c.id, min: c.min, max: c.max, step: c.step });
        ni.value = show(c, state[c.id]);
        box.appendChild(ni);
        ni.addEventListener('input', function () { var v = parseFloat(ni.value); if (isFinite(v)) { state[c.id] = v; changed(c); } });
        ni.addEventListener('change', function () {
          var v = parseFloat(ni.value); if (!isFinite(v)) v = state[c.id];
          v = clamp(c, v); state[c.id] = v; ni.value = show(c, v); changed(c);
        });
      } else if (c.type === 'select') {
        var sel = el('select', { id: 'in-' + c.id });
        (c.options || []).forEach(function (o, i) {
          var op = el('option', { value: String(i) }, rich(o.label !== undefined ? o.label : o.value));
          if (String(o.value) === String(state[c.id])) op.selected = true;
          sel.appendChild(op);
        });
        box.appendChild(sel);
        sel.addEventListener('change', function () { var o = c.options[+sel.value]; if (o) { state[c.id] = o.value; changed(c); } });
      } else if (c.type === 'vector' || c.type === 'matrix') {
        var gw = el('div', { 'class': 'gridwrap', id: 'grid-' + c.id });
        box.appendChild(gw);
        buildGrid(c, gw);
      }
      if (c.help) box.appendChild(el('div', { 'class': 'ctrl-help' }, rich(c.help)));
      host.appendChild(box);
    });
  }
  function changed(c) {
    if (deps[c.id]) { state = P2P.normalize(C, state); deps[c.id].forEach(function (g) { buildGrid(g); }); }
    if (!raf) raf = window.requestAnimationFrame(function () { raf = 0; update(); });
  }
  function renderReadout(rows) {
    var host = $('p2p-readout'), scal = [], tabs = [], h = '', next = {};
    (Array.isArray(rows) ? rows : []).forEach(function (row) { if (row && row.table) tabs.push(row.table); else if (row) scal.push(row); });
    if (scal.length) {
      h += '<ol class="chain">' + scal.map(function (s, i) {
        var txt = fmtVal(s.value), key = plain(s.label) + '#' + i, now = numOf(txt), was = prevVals[key], cls = '', delta = '';
        next[key] = now;
        if (isFinite(now) && isFinite(was) && Math.abs(now - was) > 1e-12 * Math.max(1, Math.abs(was))) {
          cls = ' changed';
          delta = '<span class="delta ' + (now > was ? 'up' : 'down') + '" aria-label="' + (now > was ? 'increased' : 'decreased') + '">' + (now > was ? '\u25B2' : '\u25BC') + '</span>';
        }
        return '<li class="kv-item' + cls + '" id="ro-' + (i + 1) + '"><div class="kv-label"><span class="stepn">' + (i + 1) + '</span>' + rich(s.label) + '</div>' +
          '<div class="kv-value">' + rich(txt) + delta + '</div>' + (s.formula ? '<div class="kv-formula details">' + rich(s.formula) + '</div>' : '') +
          (s.note ? '<div class="kv-note details">' + rich(s.note) + '</div>' : '') + '</li>';
      }).join('') + '</ol>';
    }
    tabs.forEach(function (t) {
      h += '<div class="tblw">' + (t.title ? '<div class="tblt">' + rich(t.title) + '</div>' : '') + '<table class="tbl"><thead><tr>' +
        (t.headers || []).map(function (x) { return '<th>' + rich(x) + '</th>'; }).join('') + '</tr></thead><tbody>' +
        (t.rows || []).map(function (rw) { return '<tr>' + (Array.isArray(rw) ? rw : [rw]).map(function (x) { return '<td>' + rich(fmtVal(x)) + '</td>'; }).join('') + '</tr>'; }).join('') +
        '</tbody></table></div>';
    });
    prevVals = next;
    host.innerHTML = h || '<p class="muted">No intermediate values for this state.</p>';
  }
  function renderLive(r) {
    var host = $('p2p-live-checks'), I = (M && Array.isArray(M.invariants)) ? M.invariants : [], h = '';
    if (!host) return;
    if (!I.length || r === null) { host.hidden = true; return; }
    I.forEach(function (inv, i) {
      var ok = false, err = '';
      try { ok = !!inv.check(r, clone(state)); } catch (e) { err = e && e.message ? e.message : String(e); }
      h += '<span class="chip ' + (ok ? 'ok' : 'bad') + '" id="live-check-' + (i + 1) + '"' + (err ? ' title="' + esc(err) + '"' : '') + '>' +
        (ok ? '\u2713 ' : '\u2717 ') + rich((inv && inv.name) || ('Check ' + (i + 1))) + '</span>';
    });
    host.innerHTML = '<span class="live-label">Live checks for the current input:</span> ' + h;
    host.hidden = false;
  }
  function update() {
    state = P2P.normalize(C, state);
    if (!READY) { showError('The interactive part of this page failed to load (generated code error). The explanation text remains valid.'); return; }
    var r, ib = $('p2p-insight'), s;
    try { r = M.compute(clone(state)); } catch (e) { renderLive(null); showError('compute() failed for this input: ' + (e && e.message)); return; }
    try { $('p2p-visual').innerHTML = String(M.view(clone(state), r)); } catch (e2) { showError('Drawing failed: ' + (e2 && e2.message)); return; }
    try { renderReadout(M.readout ? M.readout(clone(state), r) : []); } catch (e3) { $('p2p-readout').innerHTML = '<p class="muted">readout() failed: ' + esc(e3 && e3.message) + '</p>'; }
    try { s = M.insight ? M.insight(clone(state), r) : ''; ib.innerHTML = s ? rich(s) : ''; ib.hidden = !s; } catch (e4) { ib.hidden = true; }
    renderLive(r);
    hideError();
  }
  function applyPreset(i) {
    var e = (SPEC.explorations || [])[i];
    if (!e) return;
    state = P2P.merge(C, P2P.defaults(C), e.preset || {});
    buildControls();
    update();
    setStatus('Loaded exploration ' + (i + 1) + ': ' + plain(e.title) + '. Now follow its "Change" step.');
    var pg = $('playground');
    pg.scrollIntoView({ behavior: 'smooth', block: 'start' });
    pg.classList.remove('flash'); void pg.offsetWidth; pg.classList.add('flash');
  }
  function runChecks() {
    var host = $('p2p-tests'), sum = $('p2p-tests-summary');
    if (!READY) { sum.textContent = 'Checks could not run because the interactive code failed to load.'; sum.className = 'tests-summary bad'; return; }
    var T = Array.isArray(M.tests) ? M.tests : [], base = P2P.defaults(C), pass = 0, h = '';
    T.forEach(function (t, i) {
      var ok = false, err = '', params = '';
      try { var p = P2P.merge(C, base, (t && t.params) || {}, true); ok = !!t.check(M.compute(clone(p)), p); } catch (e) { err = e && e.message ? e.message : String(e); }
      if (ok) pass++;
      if (t && t.params && Object.keys(t.params).length) { params = JSON.stringify(t.params); if (params.length > 90) params = params.slice(0, 87) + '...'; }
      h += '<li class="' + (ok ? 'pass' : 'fail') + '" id="test-' + (i + 1) + '"><span class="badge">' + (ok ? 'PASS' : 'FAIL') + '</span><span>' + rich((t && t.name) || ('Check ' + (i + 1))) + '</span>' +
        (params ? '<code>' + esc(params) + '</code>' : '') + (err ? '<span class="terr">' + esc(err) + '</span>' : '') + '</li>';
    });
    host.innerHTML = h || '<li class="muted">No checks were defined.</li>';
    sum.innerHTML = T.length ? '<b>' + pass + ' / ' + T.length + '</b> checks pass, recomputed now in your browser from the same code that drives the playground.' : '';
    sum.className = 'tests-summary ' + (pass === T.length ? 'ok' : 'bad');
  }
  function readHash() {
    var map = { theme: 'set-theme', palette: 'set-palette', size: 'set-size', details: 'set-details', predict: 'set-predict' };
    String(window.location.hash || '').replace(/^#/, '').split('&').forEach(function (kv) {
      var parts = kv.split('='), e = map[parts[0]] ? $(map[parts[0]]) : null, v;
      if (!e || parts.length < 2) return;
      v = decodeURIComponent(parts[1]);
      if (e.type === 'checkbox') e.checked = (v === '1' || v === 'true');
      else if (Array.prototype.some.call(e.options, function (o) { return o.value === v; })) e.value = v;
    });
  }
  function applySettings(rerender) {
    var b = document.body;
    b.classList.toggle('dark', val('set-theme', 'light') === 'dark');
    if (V.setPalette) V.setPalette(val('set-palette', 'standard'));
    b.style.zoom = String(val('set-size', '1'));
    b.classList.toggle('hide-details', !val('set-details', true));
    b.classList.toggle('predict', !!val('set-predict', false));
    if (rerender) update();
  }
  function init() {
    readHash();
    applySettings(false);
    buildControls();
    ['set-theme', 'set-palette', 'set-size', 'set-details', 'set-predict'].forEach(function (id) {
      var e = $(id); if (e) e.addEventListener('change', function () { applySettings(true); });
    });
    $('p2p-reset').addEventListener('click', function () { state = P2P.defaults(C); buildControls(); update(); setStatus('Reset to the default values.'); });
    Array.prototype.forEach.call(document.querySelectorAll('[data-explore]'), function (b) {
      b.addEventListener('click', function () { applyPreset(+b.getAttribute('data-explore')); });
    });
    Array.prototype.forEach.call(document.querySelectorAll('[data-reveal]'), function (b) {
      b.addEventListener('click', function () { var a = $('answer-' + b.getAttribute('data-reveal')); if (a) a.classList.add('shown'); b.disabled = true; b.textContent = 'Revealed'; });
    });
    update();
    runChecks();
  }
  window.p2p = {
    controls: C.map(function (c) { return c.id; }),
    get: function () { return clone(state); },
    set: function (id, v) { var o = {}; o[id] = v; state = P2P.merge(C, state, o); buildControls(); update(); return clone(state); },
    load: function (i) { applyPreset(i); }
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
