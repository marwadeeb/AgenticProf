/* Paper-to-Playground runtime library (generic; contains nothing paper-specific).
 * V   - small helpers that build SVG markup as strings; generated view() code uses them.
 * P2P - parameter normalisation shared by the generated page and the offline checker.
 * Every function is named (v_*, p2p_*) so that error stack traces can be attributed. */
var V = (function () {
  'use strict';
  var C = {
    ink: '#1e293b', muted: '#64748b', grid: '#e2e8f0', axis: '#94a3b8', bg: '#ffffff', panel: '#f8fafc',
    blue: '#2563eb', orange: '#ea580c', green: '#16a34a', red: '#dc2626', purple: '#7c3aed',
    teal: '#0d9488', pink: '#db2777', gray: '#6b7280', yellow: '#ca8a04'
  };
  C.series = [C.blue, C.orange, C.green, C.red, C.purple, C.teal, C.pink, C.gray];
  var ALIAS = { size: 'font-size', anchor: 'text-anchor', weight: 'font-weight', dash: 'stroke-dasharray',
    sw: 'stroke-width', baseline: 'dominant-baseline', family: 'font-family', cls: 'class' };
  var SKIP = { head: 1, label: 1, textColor: 1 };
  var HAS = Object.prototype.hasOwnProperty;
  var SLICE = Array.prototype.slice;

  function v_isObj(a) { return a !== null && typeof a === 'object' && !Array.isArray(a); }
  function v_num(v, d) { return (typeof v === 'number' && isFinite(v)) ? v : d; }
  function v_esc(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }
  function v_r2(v) { return typeof v === 'number' ? Math.round(v * 100) / 100 : v; }
  function v_kids(list) {
    var out = [];
    function v_walk(x) {
      var i;
      if (Array.isArray(x)) { for (i = 0; i < x.length; i++) v_walk(x[i]); }
      else if (x !== null && x !== undefined && x !== false && x !== true && x !== '') out.push(String(x));
    }
    v_walk(list);
    return out.join('');
  }
  function v_attrs(def, user, colorKey) {
    var m = {}, srcs = [v_isObj(def) ? def : {}, v_isObj(user) ? user : {}], i, k, key, s = '';
    for (i = 0; i < 2; i++) {
      for (k in srcs[i]) {
        if (!HAS.call(srcs[i], k) || HAS.call(SKIP, k)) continue;
        key = k === 'color' ? (colorKey || 'fill') : (HAS.call(ALIAS, k) ? ALIAS[k] : k);
        m[key] = srcs[i][k];
      }
    }
    for (k in m) {
      if (!HAS.call(m, k) || m[k] === undefined || m[k] === null || m[k] === false) continue;
      s += ' ' + k + '="' + v_esc(v_r2(m[k])) + '"';
    }
    return s;
  }
  function v_fmt(x, d) {
    if (typeof x !== 'number') return String(x);
    if (x !== x) return 'NaN';
    if (x === Infinity) return '\u221e';
    if (x === -Infinity) return '-\u221e';
    d = (typeof d === 'number' && isFinite(d)) ? Math.max(0, Math.min(10, Math.round(d))) : 3;
    var ax = Math.abs(x);
    if (ax < 1e-12) return (0).toFixed(d);
    if (ax >= 1e7 || (d > 0 && ax < 0.5 * Math.pow(10, -d))) return x.toExponential(Math.max(1, Math.min(3, d)));
    var s = x.toFixed(d);
    if (/^-0(\.0+)?$/.test(s)) s = s.slice(1);
    return s;
  }
  function v_scale(d0, d1, r0, r1) {
    var k = (d1 - d0) === 0 ? 0 : (r1 - r0) / (d1 - d0), mid = (r0 + r1) / 2;
    return function v_scaled(v) { return k === 0 ? mid : r0 + (v - d0) * k; };
  }
  function v_linspace(a, b, n) {
    n = Math.max(2, Math.round(v_num(n, 2)));
    var out = [], i;
    for (i = 0; i < n; i++) out.push(a + (b - a) * i / (n - 1));
    return out;
  }
  function v_range(n) { var out = [], i; for (i = 0; i < n; i++) out.push(i); return out; }
  function v_ticks(a, b, n) {
    n = n || 5;
    if (!(isFinite(a) && isFinite(b))) return [];
    if (a === b) return [a];
    if (a > b) { var t = a; a = b; b = t; }
    var raw = (b - a) / n, step = Math.pow(10, Math.floor(Math.log(raw) / Math.LN10)), err = raw / step;
    if (err >= 7.5) step *= 10; else if (err >= 3.5) step *= 5; else if (err >= 1.5) step *= 2;
    var out = [], v = Math.ceil(a / step - 1e-9) * step, i = 0;
    for (; v <= b + step * 1e-6 && i < 60; v += step, i++) out.push(Math.abs(v) < step * 1e-9 ? 0 : parseFloat(v.toPrecision(12)));
    return out;
  }
  function v_tickDigits(ts) {
    if (ts.length < 2) return 2;
    var st = Math.abs(ts[1] - ts[0]);
    if (!(st > 0)) return 2;
    return Math.max(0, Math.min(6, -Math.floor(Math.log(st) / Math.LN10 + 1e-9)));
  }
  function v_hex(c) {
    c = String(c).replace('#', '');
    if (c.length === 3) c = c[0] + c[0] + c[1] + c[1] + c[2] + c[2];
    var n = parseInt(c, 16);
    if (!isFinite(n)) n = 0;
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  }
  function v_mix(a, b, t) {
    t = Math.max(0, Math.min(1, +t || 0));
    var A = v_hex(a), B = v_hex(b), o = '#', i, v;
    for (i = 0; i < 3; i++) { v = Math.round(A[i] + (B[i] - A[i]) * t); o += (v < 16 ? '0' : '') + v.toString(16); }
    return o;
  }
  function v_heat(v, lo, hi) {
    lo = v_num(lo, 0); hi = v_num(hi, 1);
    return v_mix(PAL.heatLo, PAL.heatHi, hi === lo ? 0.5 : (v - lo) / (hi - lo));
  }
  function v_div(v, m) {
    m = Math.abs(v_num(m, 1)) || 1;
    var t = Math.max(-1, Math.min(1, v / m));
    return t >= 0 ? v_mix('#f8fafc', PAL.divPos, t) : v_mix('#f8fafc', PAL.divNeg, -t);
  }
  function v_ink(bg) { var c = v_hex(bg); return (0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]) / 255 > 0.58 ? C.ink : '#ffffff'; }

  var DEF = { blue: C.blue, orange: C.orange, green: C.green, red: C.red, purple: C.purple, teal: C.teal,
    pink: C.pink, gray: C.gray, yellow: C.yellow, ink: C.ink, muted: C.muted };
  var PAL = { heatLo: '#f1f5f9', heatHi: '#1d4ed8', divNeg: '#dc2626', divPos: '#2563eb' };
  var PALETTES = {
    standard: { colors: {}, heatLo: '#f1f5f9', heatHi: '#1d4ed8', divNeg: '#dc2626', divPos: '#2563eb' },
    colorblind: { colors: { blue: '#0072B2', orange: '#E69F00', green: '#009E73', red: '#D55E00', purple: '#CC79A7',
      teal: '#56B4E9', pink: '#882255', gray: '#666666', yellow: '#B8A000' }, heatLo: '#f7fbff', heatHi: '#08306b', divNeg: '#D55E00', divPos: '#0072B2' },
    contrast: { colors: { blue: '#0033cc', orange: '#c2410c', green: '#047857', red: '#b91c1c', purple: '#6d28d9', teal: '#0e7490',
      pink: '#be185d', gray: '#374151', yellow: '#a16207', ink: '#000000', muted: '#334155' }, heatLo: '#ffffff', heatHi: '#000080', divNeg: '#b91c1c', divPos: '#0033cc' },
    grayscale: { colors: { blue: '#1f2937', orange: '#6b7280', green: '#4b5563', red: '#111827', purple: '#9ca3af', teal: '#374151',
      pink: '#6b7280', gray: '#9ca3af', yellow: '#d1d5db' }, heatLo: '#f9fafb', heatHi: '#111827', divNeg: '#6b7280', divPos: '#111827' }
  };
  function v_setPalette(name) {
    var P = HAS.call(PALETTES, name) ? PALETTES[name] : PALETTES.standard, k;
    for (k in DEF) if (HAS.call(DEF, k)) C[k] = HAS.call(P.colors, k) ? P.colors[k] : DEF[k];
    C.series = [C.blue, C.orange, C.green, C.red, C.purple, C.teal, C.pink, C.gray];
    PAL.heatLo = P.heatLo; PAL.heatHi = P.heatHi; PAL.divNeg = P.divNeg; PAL.divPos = P.divPos;
    return HAS.call(PALETTES, name) ? name : 'standard';
  }
  function v_svg(w, h) {
    return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ' + v_r2(v_num(w, 760)) + ' ' + v_r2(v_num(h, 420)) +
      '" role="img" font-family="system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif" font-size="13" style="width:100%;height:auto;display:block">' +
      v_kids(SLICE.call(arguments, 2)) + '</svg>';
  }
  function v_g(a) {
    var parts = SLICE.call(arguments, 1);
    if (!v_isObj(a)) { parts.unshift(a); a = null; }
    return '<g' + v_attrs(null, a) + '>' + v_kids(parts) + '</g>';
  }
  function v_translate(x, y) {
    return '<g transform="translate(' + v_r2(x) + ',' + v_r2(y) + ')">' + v_kids(SLICE.call(arguments, 2)) + '</g>';
  }
  function v_rect(x, y, w, h, a) {
    if (w < 0) { x += w; w = -w; }
    if (h < 0) { y += h; h = -h; }
    return '<rect' + v_attrs({ x: x, y: y, width: w, height: h, fill: C.blue }, a, 'fill') + '/>';
  }
  function v_circle(cx, cy, r, a) { return '<circle' + v_attrs({ cx: cx, cy: cy, r: Math.abs(r), fill: C.blue }, a, 'fill') + '/>'; }
  function v_line(x1, y1, x2, y2, a) {
    return '<line' + v_attrs({ x1: x1, y1: y1, x2: x2, y2: y2, stroke: C.ink, 'stroke-width': 1.5 }, a, 'stroke') + '/>';
  }
  function v_pts(p) {
    var s = [], i;
    p = Array.isArray(p) ? p : [];
    for (i = 0; i < p.length; i++) s.push(v_r2(p[i][0]) + ',' + v_r2(p[i][1]));
    return s.join(' ');
  }
  function v_polyline(p, a) {
    return '<polyline' + v_attrs({ points: v_pts(p), fill: 'none', stroke: C.blue, 'stroke-width': 2, 'stroke-linejoin': 'round', 'stroke-linecap': 'round' }, a, 'stroke') + '/>';
  }
  function v_polygon(p, a) { return '<polygon' + v_attrs({ points: v_pts(p), fill: C.blue }, a, 'fill') + '/>'; }
  function v_path(d, a) { return '<path' + v_attrs({ d: d, fill: 'none', stroke: C.ink, 'stroke-width': 1.5 }, a, 'stroke') + '/>'; }
  function v_text(x, y, s, a) {
    var str = (s === undefined || s === null) ? '' : String(s), lines = str.split('\n'), body = '', i;
    if (lines.length === 1) body = v_esc(str);
    else for (i = 0; i < lines.length; i++) body += '<tspan x="' + v_r2(x) + '" dy="' + (i ? '1.25em' : '0') + '">' + v_esc(lines[i]) + '</tspan>';
    return '<text' + v_attrs({ x: x, y: y, fill: C.ink, 'font-size': 13 }, a, 'fill') + '>' + body + '</text>';
  }
  function v_arrow(x1, y1, x2, y2, a) {
    a = v_isObj(a) ? a : {};
    var col = a.color || a.stroke || C.ink, sw = +(a.sw || a['stroke-width'] || 1.6), hs = +(a.head || (7 + 2 * sw));
    var dx = x2 - x1, dy = y2 - y1, L = Math.sqrt(dx * dx + dy * dy);
    if (L !== L) return v_line(x1, y1, x2, y2, a);
    if (L === 0) return '';
    var ux = dx / L, uy = dy / L, hl = Math.min(hs, L * 0.6), bx = x2 - ux * hl, by = y2 - uy * hl, px = -uy * hl * 0.45, py = ux * hl * 0.45;
    return '<g>' + v_line(x1, y1, bx, by, a) + v_polygon([[x2, y2], [bx + px, by + py], [bx - px, by - py]], { fill: col, stroke: 'none', opacity: a.opacity }) + '</g>';
  }
  function v_box(x, y, w, h, label, a) {
    a = v_isObj(a) ? a : {};
    return '<g>' + v_rect(x, y, w, h, { fill: a.fill || '#eff6ff', stroke: a.stroke || a.color || C.blue, 'stroke-width': a.sw || 1.5, rx: a.rx === undefined ? 8 : a.rx, opacity: a.opacity }) +
      ((label === undefined || label === null || label === '') ? '' : v_text(x + w / 2, y + h / 2, label, { anchor: 'middle', baseline: 'central', size: a.size || 13, weight: a.weight || 600, fill: a.textColor || C.ink })) + '</g>';
  }
  function v_node(cx, cy, r, label, a) {
    a = v_isObj(a) ? a : {};
    return '<g>' + v_circle(cx, cy, r, { fill: a.fill || '#eff6ff', stroke: a.stroke || a.color || C.blue, 'stroke-width': a.sw || 1.8, opacity: a.opacity }) +
      ((label === undefined || label === null || label === '') ? '' : v_text(cx, cy, label, { anchor: 'middle', baseline: 'central', size: a.size || 13, weight: a.weight || 600, fill: a.textColor || C.ink })) + '</g>';
  }
  function v_legend(x, y, items, a) {
    a = v_isObj(a) ? a : {};
    var parts = [], i, it, yy, col, gap = a.gap || 18;
    items = Array.isArray(items) ? items : [];
    for (i = 0; i < items.length; i++) {
      it = items[i] || {}; yy = y + i * gap; col = it.color || C.series[i % C.series.length];
      if (it.dash || it.line) parts.push(v_line(x, yy, x + 16, yy, { stroke: col, 'stroke-width': 2.5, dash: it.dash }));
      else parts.push(v_rect(x + 2, yy - 6, 12, 12, { fill: col, rx: 2 }));
      parts.push(v_text(x + 22, yy, it.label === undefined ? '' : it.label, { size: a.size || 12, baseline: 'central' }));
    }
    return '<g>' + parts.join('') + '</g>';
  }
  function v_axes(o) {
    o = v_isObj(o) ? o : {};
    var x = v_num(o.x, 60), y = v_num(o.y, 30), w = v_num(o.w, 300), h = v_num(o.h, 200);
    var xmin = v_num(o.xmin, 0), xmax = v_num(o.xmax, 1), ymin = v_num(o.ymin, 0), ymax = v_num(o.ymax, 1), t, i, px;
    if (xmax < xmin) { t = xmin; xmin = xmax; xmax = t; }
    if (ymax < ymin) { t = ymin; ymin = ymax; ymax = t; }
    if (xmax === xmin) { xmin -= 0.5; xmax += 0.5; }
    if (ymax === ymin) { ymin -= 0.5; ymax += 0.5; }
    var sx = v_scale(xmin, xmax, x, x + w), sy = v_scale(ymin, ymax, y + h, y), parts = [];
    var xt = Array.isArray(o.xticks) ? o.xticks : ((o.xticks === false || o.xticks === 0) ? [] : v_ticks(xmin, xmax, v_num(o.xticks, 6)));
    var yt = Array.isArray(o.yticks) ? o.yticks : ((o.yticks === false || o.yticks === 0) ? [] : v_ticks(ymin, ymax, v_num(o.yticks, 5)));
    var xd = v_tickDigits(xt), yd = v_tickDigits(yt), xl = Array.isArray(o.xtickLabels) ? o.xtickLabels : null;
    parts.push(v_rect(x, y, w, h, { fill: '#ffffff', stroke: 'none' }));
    for (i = 0; i < yt.length; i++) {
      t = yt[i]; if (!(t >= ymin - 1e-12 && t <= ymax + 1e-12)) continue;
      px = sy(t);
      if (o.grid !== false) parts.push(v_line(x, px, x + w, px, { stroke: C.grid, 'stroke-width': 1 }));
      parts.push(v_text(x - 8, px, typeof o.yfmt === 'function' ? o.yfmt(t) : v_fmt(t, yd), { anchor: 'end', baseline: 'central', size: 11, fill: C.muted }));
    }
    for (i = 0; i < xt.length; i++) {
      t = xt[i]; if (!(t >= xmin - 1e-12 && t <= xmax + 1e-12)) continue;
      px = sx(t);
      if (o.grid !== false) parts.push(v_line(px, y, px, y + h, { stroke: C.grid, 'stroke-width': 1 }));
      parts.push(v_text(px, y + h + 16, xl ? (xl[i] === undefined ? '' : xl[i]) : (typeof o.xfmt === 'function' ? o.xfmt(t) : v_fmt(t, xd)), { anchor: 'middle', size: 11, fill: C.muted }));
    }
    if (ymin < 0 && ymax > 0) parts.push(v_line(x, sy(0), x + w, sy(0), { stroke: C.axis, 'stroke-width': 1.2 }));
    if (xmin < 0 && xmax > 0) parts.push(v_line(sx(0), y, sx(0), y + h, { stroke: C.axis, 'stroke-width': 1.2 }));
    parts.push(v_line(x, y + h, x + w, y + h, { stroke: C.axis, 'stroke-width': 1.2 }));
    parts.push(v_line(x, y, x, y + h, { stroke: C.axis, 'stroke-width': 1.2 }));
    if (o.xlabel) parts.push(v_text(x + w / 2, y + h + 36, o.xlabel, { anchor: 'middle', size: 12.5 }));
    if (o.ylabel) parts.push(v_text(0, 0, o.ylabel, { anchor: 'middle', size: 12.5, transform: 'translate(' + v_r2(x - v_num(o.ylabelOffset, 46)) + ',' + v_r2(y + h / 2) + ') rotate(-90)' }));
    if (o.title) parts.push(v_text(x, y - 12, o.title, { size: 13.5, weight: 600 }));
    return { svg: parts.join(''), sx: sx, sy: sy, x: x, y: y, w: w, h: h, xmin: xmin, xmax: xmax, ymin: ymin, ymax: ymax };
  }
  function v_ok(v) { return v !== null && v !== undefined && v !== '' && isFinite(v); }
  function v_lineChart(o) {
    o = v_isObj(o) ? o : {};
    var S = Array.isArray(o.series) ? o.series : [], P = Array.isArray(o.points) ? o.points : [];
    var xs = [], ys = [], i, j, s, n;
    for (i = 0; i < S.length; i++) {
      s = S[i] || {}; n = Math.min((s.xs || []).length, (s.ys || []).length);
      for (j = 0; j < n; j++) if (v_ok(s.xs[j]) && v_ok(s.ys[j])) { xs.push(+s.xs[j]); ys.push(+s.ys[j]); }
    }
    for (i = 0; i < P.length; i++) if (P[i] && v_ok(P[i].x) && v_ok(P[i].y)) { xs.push(+P[i].x); ys.push(+P[i].y); }
    var dxmin = xs.length ? Math.min.apply(null, xs) : 0, dxmax = xs.length ? Math.max.apply(null, xs) : 1;
    var dymin = ys.length ? Math.min.apply(null, ys) : 0, dymax = ys.length ? Math.max.apply(null, ys) : 1;
    var pad = (dymax - dymin) * 0.08 || 0.5;
    var ax = v_axes({ x: o.x, y: o.y, w: o.w, h: o.h, xmin: v_num(o.xmin, dxmin), xmax: v_num(o.xmax, dxmax),
      ymin: v_num(o.ymin, (dymin >= 0 && dymin - pad < 0) ? 0 : dymin - pad), ymax: v_num(o.ymax, dymax + pad),
      xlabel: o.xlabel, ylabel: o.ylabel, title: o.title, xticks: o.xticks, yticks: o.yticks, xfmt: o.xfmt, yfmt: o.yfmt,
      grid: o.grid, xtickLabels: o.xtickLabels, ylabelOffset: o.ylabelOffset });
    var cid = 'clip' + Math.round(ax.x) + '_' + Math.round(ax.y) + '_' + Math.round(ax.w) + '_' + Math.round(ax.h);
    var body = [], top = [], HL = Array.isArray(o.hlines) ? o.hlines : [], VL = Array.isArray(o.vlines) ? o.vlines : [], q, col;
    for (i = 0; i < HL.length; i++) {
      if (!HL[i]) continue; q = ax.sy(HL[i].y); col = HL[i].color || C.muted;
      body.push(v_line(ax.x, q, ax.x + ax.w, q, { stroke: col, 'stroke-width': 1.2, dash: '5 4' }));
      if (HL[i].label) top.push(v_text(ax.x + ax.w - 4, q - 5, HL[i].label, { anchor: 'end', size: 11, fill: col }));
    }
    for (i = 0; i < VL.length; i++) {
      if (!VL[i]) continue; q = ax.sx(VL[i].x); col = VL[i].color || C.muted;
      body.push(v_line(q, ax.y, q, ax.y + ax.h, { stroke: col, 'stroke-width': 1.2, dash: '5 4' }));
      if (VL[i].label) top.push(v_text(q + 4, ax.y + 12, VL[i].label, { size: 11, fill: col }));
    }
    for (i = 0; i < S.length; i++) {
      s = S[i] || {}; col = s.color || C.series[i % C.series.length];
      var run = [], runs = [], m = Math.min((s.xs || []).length, (s.ys || []).length), k;
      for (j = 0; j < m; j++) {
        if (v_ok(s.xs[j]) && v_ok(s.ys[j])) run.push([ax.sx(+s.xs[j]), ax.sy(+s.ys[j])]);
        else { if (run.length) runs.push(run); run = []; }
      }
      if (run.length) runs.push(run);
      for (j = 0; j < runs.length; j++) {
        if (runs[j].length > 1) body.push(v_polyline(runs[j], { stroke: col, 'stroke-width': v_num(s.width, 2.4), dash: s.dash, opacity: s.opacity }));
        if (s.markers || runs[j].length === 1) for (k = 0; k < runs[j].length; k++) body.push(v_circle(runs[j][k][0], runs[j][k][1], 3.2, { fill: col }));
      }
    }
    for (i = 0; i < P.length; i++) {
      var pt = P[i] || {}, pc = pt.color || C.red;
      if (!(v_ok(pt.x) && v_ok(pt.y))) { top.push(v_text(ax.x + 6, ax.y + 14 + 14 * i, 'point ' + (pt.label || i) + ': ' + pt.x + ', ' + pt.y, { size: 11, fill: C.red })); continue; }
      body.push(v_circle(ax.sx(+pt.x), ax.sy(+pt.y), v_num(pt.r, 5.5), { fill: pc, stroke: '#ffffff', 'stroke-width': 1.5 }));
      if (pt.label !== undefined && pt.label !== '') top.push(v_text(ax.sx(+pt.x) + 8, ax.sy(+pt.y) - 8, pt.label, { size: 12, weight: 600, fill: pc }));
    }
    var named = [], legend = '', lw = 0;
    for (i = 0; i < S.length; i++) if (S[i] && S[i].label) named.push({ label: S[i].label, color: S[i].color || C.series[i % C.series.length], dash: S[i].dash, line: true });
    if (o.legend !== false && named.length && (named.length > 1 || o.legend)) {
      for (i = 0; i < named.length; i++) lw = Math.max(lw, String(named[i].label).length);
      var lx = (v_isObj(o.legend) && v_ok(o.legend.x)) ? o.legend.x : ax.x + ax.w - (lw * 6.6 + 34);
      var ly = (v_isObj(o.legend) && v_ok(o.legend.y)) ? o.legend.y : ax.y + 14;
      legend = v_rect(lx - 6, ly - 11, lw * 6.6 + 36, named.length * 18 + 4, { fill: '#ffffff', opacity: 0.88, rx: 6 }) + v_legend(lx, ly, named);
    }
    return ax.svg + '<defs><clipPath id="' + cid + '"><rect x="' + v_r2(ax.x - 6) + '" y="' + v_r2(ax.y - 6) + '" width="' + v_r2(ax.w + 12) + '" height="' + v_r2(ax.h + 12) +
      '"/></clipPath></defs><g clip-path="url(#' + cid + ')">' + body.join('') + '</g>' + top.join('') + legend;
  }
  function v_barChart(o) {
    o = v_isObj(o) ? o : {};
    var labels = Array.isArray(o.labels) ? o.labels : [], S = Array.isArray(o.series) ? o.series : [{ values: Array.isArray(o.values) ? o.values : [], label: o.label, color: o.color }];
    var ns = Math.max(1, S.length), n = labels.length, i, k, vals = [], sv;
    for (k = 0; k < S.length; k++) { sv = (S[k] && S[k].values) || []; n = Math.max(n, sv.length); for (i = 0; i < sv.length; i++) if (v_ok(sv[i])) vals.push(+sv[i]); }
    var dmin = vals.length ? Math.min.apply(null, vals) : 0, dmax = vals.length ? Math.max.apply(null, vals) : 1;
    var ymin = v_num(o.ymin, Math.min(0, dmin)), ymax = v_num(o.ymax, Math.max(0, dmax));
    if (o.ymax === undefined) ymax = ymax + ((ymax - ymin) * 0.14 || 1);
    if (o.ymin === undefined && ymin < 0) ymin = ymin - (ymax - ymin) * 0.1;
    var ax = v_axes({ x: o.x, y: o.y, w: o.w, h: o.h, xmin: 0, xmax: Math.max(1, n), ymin: ymin, ymax: ymax, xticks: false, yticks: o.yticks,
      ylabel: o.ylabel, xlabel: o.xlabel, title: o.title, yfmt: o.yfmt, grid: o.grid, ylabelOffset: o.ylabelOffset });
    var band = ax.w / Math.max(1, n), inner = band * (1 - v_num(o.gap, 0.28)), bw = inner / ns;
    var base = ax.sy(Math.max(ax.ymin, Math.min(ax.ymax, 0))), parts = [ax.svg], d = o.digits === undefined ? 2 : o.digits;
    var showVals = o.valueLabels !== false && n * ns <= 24, hl = Array.isArray(o.highlight) ? o.highlight : ((o.highlight === undefined || o.highlight === null) ? [] : [o.highlight]);
    for (i = 0; i < n; i++) {
      var x0 = ax.x + band * i + (band - inner) / 2;
      for (k = 0; k < ns; k++) {
        var vv = ((S[k] && S[k].values) || [])[i], bx = x0 + bw * k, cx = bx + bw / 2;
        if (vv === undefined || vv === null) continue;
        if (!isFinite(vv)) { parts.push(v_text(cx, base - 6, String(vv), { anchor: 'middle', size: 11, fill: C.red })); continue; }
        vv = +vv;
        var col = (Array.isArray(o.colors) && o.colors[i]) || (S[k] && S[k].color) || (ns > 1 ? C.series[k % C.series.length] : C.blue);
        var topY = ax.sy(Math.max(ax.ymin, Math.min(ax.ymax, vv))), isHl = hl.indexOf(i) >= 0;
        parts.push(v_rect(bx + 1, Math.min(topY, base), Math.max(1, bw - 2), Math.abs(base - topY), { fill: col, rx: 2, opacity: (hl.length && !isHl) ? 0.45 : 1, stroke: isHl ? C.ink : 'none', 'stroke-width': isHl ? 2 : 0 }));
        if (showVals) parts.push(v_text(cx, vv >= 0 ? topY - 5 : topY + 13, v_fmt(vv, d), { anchor: 'middle', size: 11 }));
      }
      if (labels[i] !== undefined) parts.push(v_text(ax.x + band * (i + 0.5), ax.y + ax.h + 16, labels[i], { anchor: 'middle', size: 11.5 }));
    }
    if (ns > 1) {
      var items = [];
      for (k = 0; k < ns; k++) if (S[k] && S[k].label) items.push({ label: S[k].label, color: S[k].color || C.series[k % C.series.length] });
      if (items.length) parts.push(v_legend(ax.x + ax.w - 120, ax.y + 12, items));
    }
    return parts.join('');
  }
  function v_heatmap(o) {
    o = v_isObj(o) ? o : {};
    var M = Array.isArray(o.matrix) ? o.matrix : [], R = M.length, K = 0, i, j, v;
    var x = v_num(o.x, 60), y = v_num(o.y, 40), w = v_num(o.w, 240), h = v_num(o.h, 160), flat = [];
    for (i = 0; i < R; i++) { K = Math.max(K, (M[i] || []).length); for (j = 0; j < (M[i] || []).length; j++) if (v_ok(M[i][j])) flat.push(+M[i][j]); }
    if (!R || !K) return v_text(x, y + 14, '(empty matrix)', { fill: C.muted });
    var lo = v_num(o.min, flat.length ? Math.min.apply(null, flat) : 0), hi = v_num(o.max, flat.length ? Math.max.apply(null, flat) : 1);
    var cw = w / K, ch = h / R, d = o.digits === undefined ? 2 : o.digits, parts = [], rl = o.rowLabels || [], cl = o.colLabels || [];
    var fs = Math.max(9, Math.min(13, ch * 0.42, cw / 3.4)), hlist = Array.isArray(o.highlight) ? o.highlight : [];
    if (o.title) parts.push(v_text(x, y - (cl.length ? 26 : 10), o.title, { size: 13.5, weight: 600 }));
    for (i = 0; i < R; i++) {
      for (j = 0; j < K; j++) {
        v = (M[i] || [])[j];
        var fill = !v_ok(v) ? '#fee2e2' : (o.diverging ? v_div(+v, Math.max(Math.abs(lo), Math.abs(hi))) : v_heat(+v, lo, hi));
        parts.push(v_rect(x + j * cw, y + i * ch, cw, ch, { fill: fill, stroke: '#ffffff', 'stroke-width': 1.5 }));
        if (o.showValues !== false && cw >= 24 && ch >= 15) parts.push(v_text(x + (j + 0.5) * cw, y + (i + 0.5) * ch, typeof v === 'number' ? v_fmt(v, d) : String(v), { anchor: 'middle', baseline: 'central', size: fs, fill: v_ink(fill) }));
      }
      if (rl[i] !== undefined) parts.push(v_text(x - 8, y + (i + 0.5) * ch, rl[i], { anchor: 'end', baseline: 'central', size: 12 }));
    }
    for (j = 0; j < K; j++) if (cl[j] !== undefined) parts.push(v_text(x + (j + 0.5) * cw, y - 8, cl[j], { anchor: 'middle', size: 12 }));
    for (i = 0; i < hlist.length; i++) if (Array.isArray(hlist[i])) parts.push(v_rect(x + hlist[i][1] * cw + 1, y + hlist[i][0] * ch + 1, cw - 2, ch - 2, { fill: 'none', stroke: C.ink, 'stroke-width': 2.5 }));
    return parts.join('');
  }
  return {
    c: C, esc: v_esc, fmt: v_fmt, scale: v_scale, linspace: v_linspace, range: v_range, ticks: v_ticks,
    mix: v_mix, heat: v_heat, div: v_div, ink: v_ink, svg: v_svg, g: v_g, translate: v_translate, rect: v_rect,
    circle: v_circle, line: v_line, arrow: v_arrow, path: v_path, polyline: v_polyline, polygon: v_polygon,
    text: v_text, box: v_box, node: v_node, legend: v_legend, axes: v_axes, lineChart: v_lineChart,
    barChart: v_barChart, heatmap: v_heatmap, setPalette: v_setPalette
  };
})();

var P2P = (function () {
  'use strict';
  var HAS = Object.prototype.hasOwnProperty;
  function p2p_num(v, d) { var n = typeof v === 'number' ? v : parseFloat(v); return isFinite(n) ? n : d; }
  function p2p_dim(spec, q, fallback) {
    var n = typeof spec === 'string' ? q[spec] : spec;
    return Math.max(1, Math.min(16, Math.round(p2p_num(n, fallback))));
  }
  function p2p_fill(c) {
    if (typeof c.fill === 'number' && isFinite(c.fill)) return c.fill;
    var lo = p2p_num(c.min, 0), hi = p2p_num(c.max, 0);
    return (lo <= 0 && hi >= 0) ? 0 : lo;
  }
  function p2p_vec(a, n, fill, dflt) {
    var out = [], i, v;
    for (i = 0; i < n; i++) {
      v = (Array.isArray(a) && i < a.length) ? p2p_num(a[i], NaN) : NaN;
      if (!isFinite(v)) v = (Array.isArray(dflt) && i < dflt.length && isFinite(dflt[i])) ? +dflt[i] : fill;
      out.push(v);
    }
    return out;
  }
  function p2p_normalize(C, p) {
    p = p || {};
    var q = {}, i, k, c, v, opts, hit;
    for (i = 0; i < C.length; i++) {
      c = C[i];
      if (c.type === 'vector' || c.type === 'matrix') continue;
      v = HAS.call(p, c.id) ? p[c.id] : c.value;
      if (c.type === 'slider' || c.type === 'number') q[c.id] = p2p_num(v, p2p_num(c.value, 0));
      else if (c.type === 'toggle') q[c.id] = (v === true || v === 'true' || v === 1);
      else if (c.type === 'select') {
        opts = c.options || []; hit = null;
        for (k = 0; k < opts.length; k++) if (String(opts[k].value) === String(v)) hit = opts[k].value;
        q[c.id] = hit !== null ? hit : c.value;
      } else q[c.id] = v;
    }
    for (i = 0; i < C.length; i++) {
      c = C[i];
      v = HAS.call(p, c.id) ? p[c.id] : c.value;
      if (c.type === 'vector') {
        var dv = Array.isArray(c.value) ? c.value : [];
        q[c.id] = p2p_vec(v, p2p_dim(c.length, q, dv.length || 1), p2p_fill(c), dv);
      } else if (c.type === 'matrix') {
        var dm = Array.isArray(c.value) ? c.value : [], R = p2p_dim(c.rows, q, dm.length || 1);
        var K = p2p_dim(c.cols, q, (dm[0] || []).length || 1), rows = [], r;
        for (r = 0; r < R; r++) rows.push(p2p_vec(Array.isArray(v) ? v[r] : null, K, p2p_fill(c), dm[r]));
        q[c.id] = rows;
      }
    }
    return q;
  }
  function p2p_defaults(C) { return p2p_normalize(C, {}); }
  function p2p_merge(C, base, over) {
    var p = {}, k, i, c;
    for (k in base) if (HAS.call(base, k)) p[k] = base[k];
    if (over) for (k in over) if (HAS.call(over, k)) p[k] = over[k];
    /* A preset/test that gives a whole vector or matrix but not its size slider means "use this size":
       set the slider from the array instead of padding/truncating the array to the old size. */
    var bySize = function (sizeId, n) {
      if (typeof sizeId === 'string' && over && !HAS.call(over, sizeId) && n > 0) p[sizeId] = n;
    };
    for (i = 0; over && i < C.length; i++) {
      c = C[i];
      if (!HAS.call(over, c.id) || !Array.isArray(over[c.id])) continue;
      if (c.type === 'vector') bySize(c.length, over[c.id].length);
      else if (c.type === 'matrix') {
        bySize(c.rows, over[c.id].length);
        if (Array.isArray(over[c.id][0])) bySize(c.cols, over[c.id][0].length);
      }
    }
    return p2p_normalize(C, JSON.parse(JSON.stringify(p)));
  }
  return { normalize: p2p_normalize, defaults: p2p_defaults, merge: p2p_merge };
})();
