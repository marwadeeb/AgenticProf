/* Paper-to-Playground offline checker harness (generic; nothing paper-specific).
 * Evaluated inside QuickJS by p2p/jscheck.py after vlib.js and the wrapped generated code.
 * Helper names start with __h so their stack frames can be told apart from generated code. */
var __hSeen = {};

function __hClone(x) { return JSON.parse(JSON.stringify(x)); }

function __hText(x, depth, key) {
  var t = typeof x, a, k, i;
  depth = depth || 0;
  if (depth > 8) return '';
  if (x === undefined) return (key === undefined || key === 'value' || key === 'label') ? 'undefined' : '';
  if (x === null) return '';
  if (t === 'number' || t === 'string' || t === 'boolean') return String(x);
  if (Array.isArray(x)) { a = []; for (i = 0; i < x.length; i++) a.push(__hText(x[i], depth + 1)); return a.join(' | '); }
  if (t === 'object') {
    a = [];
    for (k in x) { if (Object.prototype.hasOwnProperty.call(x, k)) a.push(k + '=' + __hText(x[k], depth + 1, k)); }
    return '{' + a.join(', ') + '}';
  }
  return '';
}

/* NaN is always a bug. "undefined" is only a bug when it is a leaked JS value (after = or :, a whole SVG
   text node, or glued to a number); prose such as "the ratio is undefined when ε = 0" is correct teaching. */
var __hLEAK = /\bNaN\b|[=:]\s*undefined\b|>\s*undefined\s*<|="undefined"|[\d)\]]\s*undefined\b|\bundefined\s*[\d(]/;

function __hBad(text, svg) {
  var out = [];
  if (/\bNaN\b/.test(text)) out.push('NaN');
  if (/[=:]\s*undefined\b|>\s*undefined\s*<|="undefined"|[\d)\]]\s*undefined\b|\bundefined\s*[\d(]/.test(text)) out.push('undefined');
  if (text.indexOf('[object Object]') >= 0) out.push('[object Object]');
  if (/\bInfinity\b/.test(svg)) out.push('Infinity inside the SVG');
  return out;
}

/* Diagnostics for repair prompts: the model can only fix a bug it can see, so failures carry values. */
function __hBadPaths(x, path, out, depth) {
  var k, i;
  depth = depth || 0;
  if (out.length >= 4 || depth > 6) return out;
  if (typeof x === 'number' && !isFinite(x)) out.push(path + ' = ' + x);
  else if (x === undefined) out.push(path + ' = undefined');
  else if (Array.isArray(x)) { for (i = 0; i < x.length; i++) __hBadPaths(x[i], path + '[' + i + ']', out, depth + 1); }
  else if (x && typeof x === 'object') { for (k in x) if (Object.prototype.hasOwnProperty.call(x, k)) __hBadPaths(x[k], path + '.' + k, out, depth + 1); }
  return out;
}

/* Compact view of a result object: scalars first (they are what tests compare), large arrays by shape. */
function __hBrief(r, n) {
  var num = function (v) { return typeof v === 'number' ? (isFinite(v) ? String(+v.toPrecision(5)) : String(v)) : v === undefined ? 'undefined' : JSON.stringify(v); };
  var arr = function (a, depth) {
    if (!Array.isArray(a)) return a !== null && typeof a === 'object' ? '{...}' : num(a);
    if (depth > 0 || a.length > 6 || (a.length && typeof a[0] === 'object')) {
      var shape = [a.length], x = a[0];
      while (Array.isArray(x)) { shape.push(x.length); x = x[0]; }
      if (shape.length === 1 && typeof a[0] !== 'object') return '[' + a.slice(0, 4).map(num).join(',') + ',... (' + a.length + ')]';
      return '[' + shape.join('x') + ' array]';
    }
    return '[' + a.map(num).join(',') + ']';
  };
  n = n || 360;
  if (r === null || typeof r !== 'object' || Array.isArray(r)) return arr(r, 0).slice(0, n);
  var keys = Object.keys(r), scal = [], rest = [];
  keys.forEach(function (k) { (r[k] === null || typeof r[k] !== 'object' ? scal : rest).push(k); });
  var s = scal.concat(rest).map(function (k) { return k + '=' + arr(r[k], 0); }).join(', ');
  return s.length > n ? s.slice(0, n) + '...' : s;
}

function __hBadReadout(ro) {
  var out = [], i, it, t;
  if (!Array.isArray(ro)) return out;
  for (i = 0; i < ro.length && out.length < 3; i++) {
    it = ro[i];
    t = __hText(it);
    var m = __hLEAK.exec(t);
    if (m) out.push('readout item "' + (it && it.label !== undefined ? it.label : (it && it.table && it.table.title) || i) + '" shows ...' +
      t.slice(Math.max(0, m.index - 60), m.index + 20) + '...');
  }
  return out;
}

function __hErr(e) {
  var s, lines, keep = [], i, L;
  if (e === null || e === undefined) return String(e);
  s = (e.name ? e.name + ': ' : '') + (e.message !== undefined ? String(e.message) : String(e));
  if (e.stack) {
    lines = String(e.stack).split('\n');
    for (i = 0; i < lines.length && keep.length < 4; i++) {
      L = lines[i].replace(/^\s+|\s+$/g, '');
      if (!L || L.indexOf('__h') >= 0 || L.indexOf('<eval>') >= 0) continue;
      keep.push(L);
    }
    if (keep.length) s += ' [' + keep.join(' ; ') + ']';
  }
  return s;
}

function __hRender(p) {
  var r = MODEL.compute(__hClone(p));
  if (r === undefined || r === null) throw new Error('compute(p) returned ' + r);
  var svg = MODEL.view(__hClone(p), r);
  if (typeof svg !== 'string') throw new Error('view(p, r) must return an SVG string, got ' + typeof svg);
  var ro = MODEL.readout ? MODEL.readout(__hClone(p), r) : [];
  var ins = MODEL.insight ? MODEL.insight(__hClone(p), r) : '';
  return { r: r, svg: svg, roRaw: ro, ro: __hText(ro), ins: (ins === undefined || ins === null) ? '' : String(ins) };
}

function __hNote(rep, sev, detail, label) {
  var key = sev + ':' + detail.slice(0, 160);
  if (__hSeen[key]) return;
  __hSeen[key] = 1;
  var list = sev === 'error' ? rep.errors : rep.warnings;
  if (list.length < 10) list.push(detail + ' (first seen with ' + label + ')');
  else rep.suppressed++;
}

function __hTry(label, p, rep, sev) {
  var o;
  rep.cases++;
  try { o = __hRender(p); } catch (e) { __hNote(rep, sev, 'Exception: ' + __hErr(e), label); return null; }
  var bad = __hBad(o.svg + ' ' + o.ro + ' ' + o.ins, o.svg);
  if (bad.length) {
    var where = __hBadPaths(o.r, 'r', []);
    if (!where.length) where = __hBadReadout(o.roRaw);
    if (!where.length) {
      var hit = function (name, text) {
        var m = __hLEAK.exec(text);
        if (m) where.push(name + ' contains ...' + text.slice(Math.max(0, m.index - 60), m.index + 20) + '...');
      };
      hit('insight(p, r)', o.ins);
      hit('view(p, r) SVG text', o.svg.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' '));
      if (!where.length) hit('view(p, r) SVG markup', o.svg);
    }
    __hNote(rep, sev, 'Displayed output contains ' + bad.join(', ') + (where.length ? ': ' + where.join('; ') : '') +
      '; fix the computation or formatting that produces it', label);
  }
  var inv = __hInv(o.r, p);
  if (inv) __hNote(rep, sev, 'INVARIANT failed: ' + inv + '; compute gave ' + __hBrief(o.r, 240), label);
  return o;
}

function __hInv(r, p) {
  var I = (MODEL && Array.isArray(MODEL.invariants)) ? MODEL.invariants : [], i, ok, nm;
  for (i = 0; i < I.length; i++) {
    nm = (I[i] && I[i].name) ? String(I[i].name) : '#' + (i + 1);
    try { ok = !!I[i].check(r, p); } catch (e) { return '"' + nm + '" threw ' + __hErr(e); }
    if (!ok) return '"' + nm + '" returned false';
  }
  return '';
}

function __hSnap(c, v) {
  var lo = +c.min, st = +c.step;
  if (isFinite(lo) && st > 0) v = lo + Math.round((v - lo) / st) * st;
  return parseFloat((+v).toPrecision(12));
}
function __hZero(c) { return (c.min <= 0 && c.max >= 0) ? 0 : c.min; }
function __hFill(a, v) { var o = [], i; for (i = 0; i < a.length; i++) o.push(v); return o; }
function __hFillM(m, v) { var o = [], i; for (i = 0; i < m.length; i++) o.push(__hFill(m[i], v)); return o; }

function __hVariants(c, cur) {
  var out = [], i, v, a, cand;
  if (c.type === 'slider' || c.type === 'number') {
    cand = [c.min, c.max, __hSnap(c, (c.min + c.max) / 2)];
    for (i = 0; i < cand.length; i++) { v = cand[i]; if (typeof v === 'number' && isFinite(v) && v !== cur) out.push({ v: v, sev: 'error', d: String(v) }); }
  } else if (c.type === 'toggle') {
    out.push({ v: !cur, sev: 'error', d: String(!cur) });
  } else if (c.type === 'select') {
    for (i = 0; i < (c.options || []).length && out.length < 5; i++) {
      v = c.options[i].value;
      if (String(v) !== String(cur)) out.push({ v: v, sev: 'error', d: JSON.stringify(v) });
    }
  } else if (c.type === 'vector' && Array.isArray(cur) && cur.length) {
    a = cur.slice(); a[0] = (a[0] !== c.max) ? c.max : c.min;
    out.push({ v: a, sev: 'error', d: 'first entry ' + a[0] });
    out.push({ v: __hFill(cur, __hZero(c)), sev: 'warn', d: 'all entries ' + __hZero(c) });
    out.push({ v: __hFill(cur, c.max), sev: 'warn', d: 'all entries ' + c.max });
  } else if (c.type === 'matrix' && Array.isArray(cur) && cur.length && Array.isArray(cur[0]) && cur[0].length) {
    a = __hClone(cur); a[0][0] = (a[0][0] !== c.max) ? c.max : c.min;
    out.push({ v: a, sev: 'error', d: 'entry [0][0] = ' + a[0][0] });
    out.push({ v: __hFillM(cur, __hZero(c)), sev: 'warn', d: 'all entries ' + __hZero(c) });
    out.push({ v: __hFillM(cur, c.max), sev: 'warn', d: 'all entries ' + c.max });
  }
  return out;
}

function __hRng(seed) {
  var s = seed >>> 0;
  return function __hRand() {
    s = (s + 0x6D2B79F5) >>> 0;
    var t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function __hRandScalar(c, rnd, cur) {
  var o;
  if (c.type === 'slider' || c.type === 'number') return __hSnap(c, c.min + rnd() * (c.max - c.min));
  if (c.type === 'toggle') return rnd() < 0.5;
  if (c.type === 'select') { o = c.options || []; return o.length ? o[Math.floor(rnd() * o.length) % o.length].value : cur; }
  return cur;
}

function __hRun(cfgJSON) {
  var cfg = JSON.parse(cfgJSON), C = cfg.controls || [], presets = cfg.presets || [], i, j, k;
  var rep = { engine: 'quickjs', errors: [], warnings: [], suppressed: 0, cases: 0, tests: [], active: [], inert: [], visualActive: false, fatal: false, svgDefault: '' };
  var M = (typeof MODEL !== 'undefined' && MODEL) ? MODEL : null;
  if (!M) { rep.errors.push('CODE ran but produced no MODEL object.'); rep.fatal = true; return JSON.stringify(rep); }
  if (typeof M.compute !== 'function') rep.errors.push('compute(p) is not defined as a top-level function.');
  if (typeof M.view !== 'function') rep.errors.push('view(p, r) is not defined as a top-level function.');
  if (rep.errors.length) { rep.fatal = true; return JSON.stringify(rep); }
  if (typeof M.readout !== 'function') rep.warnings.push('readout(p, r) is not defined, so no intermediate values are displayed.');
  if (typeof M.insight !== 'function') rep.warnings.push('insight(p, r) is not defined.');
  var base = P2P.defaults(C);
  rep.invariants = Array.isArray(M.invariants) ? M.invariants.length : 0;
  var d = __hTry('the default values', base, rep, 'error');
  if (!d) rep.fatal = true;
  else {
    rep.svgDefault = d.svg;
    if (d.svg.indexOf('<svg') < 0) { rep.errors.push('view(p, r) must return an SVG string (use V.svg(...)).'); rep.fatal = true; }
    if (!Array.isArray(d.roRaw)) rep.errors.push('readout(p, r) must return an array.');
  }
  var bases = [];
  if (d) bases.push({ name: 'defaults', p: base, o: d });
  for (i = 0; i < presets.length; i++) {
    var pp = P2P.merge(C, base, presets[i] || {});
    var po = __hTry('the preset of exploration ' + (i + 1), pp, rep, 'error');
    if (po) bases.push({ name: 'exploration ' + (i + 1) + ' preset', p: pp, o: po });
  }
  var T = Array.isArray(M.tests) ? M.tests : [];
  for (i = 0; i < T.length && i < 12; i++) {
    var t = T[i] || {}, res = { name: t.name ? String(t.name) : 'test ' + (i + 1), pass: false };
    try {
      if (typeof t.check !== 'function') throw new Error('TESTS[' + i + '].check must be a function (r, p) => boolean');
      var tparams = (t.params && typeof t.params === 'object') ? t.params : {};
      var unknown = Object.keys(tparams).filter(function (key) { return !C.some(function (cc) { return cc.id === key; }); });
      if (unknown.length) throw new Error('params use unknown control id(s) ' + unknown.join(', ') + ' (valid ids: ' + C.map(function (cc) { return cc.id; }).join(', ') + '), so they were ignored');
      var tp = P2P.merge(C, base, tparams);
      var resized = Object.keys(tparams).filter(function (key) {
        var a = tparams[key], b = tp[key];
        return Array.isArray(a) && Array.isArray(b) && (a.length !== b.length || (Array.isArray(a[0]) && Array.isArray(b[0]) && a[0].length !== b[0].length));
      });
      if (resized.length) throw new Error('params.' + resized[0] + ' has a different size from the control (it was padded/truncated to ' +
        (Array.isArray(tp[resized[0]][0]) ? tp[resized[0]].length + 'x' + tp[resized[0]][0].length : tp[resized[0]].length) +
        '); also set the size control in params, or give an array of the current size');
      var tr = M.compute(__hClone(tp));
      res.pass = !!t.check(tr, tp);
      if (!res.pass) res.detail = 'params ' + __hBrief(tparams, 120) + ', compute gave ' + __hBrief(tr);
    } catch (e) { res.error = __hErr(e); }
    rep.tests.push(res);
  }
  for (i = 0; i < C.length; i++) {
    var c = C[i], act = false, vis = false;
    for (j = 0; j < bases.length; j++) {
      var b = bases[j], vars = __hVariants(c, b.p[c.id]);
      for (k = 0; k < vars.length; k++) {
        var q = __hClone(b.p);
        q[c.id] = vars[k].v;
        q = P2P.normalize(C, q);
        var o = __hTry('control "' + c.id + '" = ' + vars[k].d + ' (from ' + b.name + ')', q, rep, vars[k].sev);
        if (!o) continue;
        if (o.svg !== b.o.svg) { act = true; vis = true; }
        else if (o.ro !== b.o.ro || o.ins !== b.o.ins) act = true;
      }
    }
    (act ? rep.active : rep.inert).push(c.id);
    if (vis) rep.visualActive = true;
  }
  var rnd = __hRng(20240611);
  for (i = 0; i < 6 && C.length; i++) {
    var s = {};
    for (j = 0; j < C.length; j++) s[C[j].id] = __hRandScalar(C[j], rnd, base[C[j].id]);
    s = P2P.normalize(C, s);
    for (j = 0; j < C.length; j++) {
      var cc = C[j], r2, c2;
      if (cc.type === 'vector') for (k = 0; k < s[cc.id].length; k++) s[cc.id][k] = __hSnap(cc, cc.min + rnd() * (cc.max - cc.min));
      else if (cc.type === 'matrix') for (r2 = 0; r2 < s[cc.id].length; r2++) for (c2 = 0; c2 < s[cc.id][r2].length; c2++) s[cc.id][r2][c2] = __hSnap(cc, cc.min + rnd() * (cc.max - cc.min));
    }
    __hTry('random state ' + JSON.stringify(s).slice(0, 140), s, rep, 'warn');
  }
  return JSON.stringify(rep);
}
