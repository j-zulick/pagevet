(function () {
  'use strict';
  var SCHEMA_VERSION = 1;
  var PAGE_SIZE = 100;
  var SEV = ['none', 'low', 'medium', 'high'];
  var DATA = null, RECORDS = [], BY_ID = {};
  var state = { ds: 'field', view: 'data', filters: {}, q: '', detail: '', limit: PAGE_SIZE, ca: '', cb: '', pair: 0 };

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined && text !== null) e.textContent = String(text);
    return e;
  }
  function byId(id) { return document.getElementById(id); }
  function pct(k, n) { return n ? (100 * k / n).toFixed(1) + '%' : '–'; }

  function fail(message) {
    document.body.replaceChildren();
    var box = el('div', 'error');
    box.setAttribute('role', 'alert');
    box.id = 'error';
    box.append(el('h1', null, 'This explorer cannot show its data'), el('p', null, message),
      el('p', null, 'No partial results are shown. Regenerate the page with: pagevet-study explore docs/bench/*-field-* --out site/'));
    document.body.append(box);
    document.body.dataset.state = 'error';
  }

  function sha256hex(text) {
    return crypto.subtle.digest('SHA-256', new TextEncoder().encode(text)).then(function (buf) {
      return Array.prototype.map.call(new Uint8Array(buf), function (x) { return x.toString(16).padStart(2, '0'); }).join('');
    });
  }

  // --- the shared rules (same as pagevet.explore.matches / facet_counts / headline) -------------
  function matches(r, filters, q, skip) {
    for (var key in filters) {
      if (key === skip || !filters[key].length) continue;
      var have = r.f[key] || [], wanted = filters[key], ok = false;
      for (var i = 0; i < have.length; i++) if (wanted.indexOf(have[i]) >= 0) { ok = true; break; }
      if (!ok) return false;
    }
    if (q) {
      var hay = [r.url || '', r.domain || '', r.title || ''].join(' ').toLowerCase();
      if (hay.indexOf(q.toLowerCase()) < 0) return false;
    }
    return true;
  }
  function facetCounts(ds, filters, q) {
    var out = {}, pool = RECORDS.filter(function (r) { return r.ds === ds; });
    facetsOf(ds).forEach(function (f) {
      var counts = {};
      pool.forEach(function (r) {
        if (!matches(r, filters, q, f.key)) return;
        var seen = {};
        (r.f[f.key] || []).forEach(function (v) { if (!seen[v]) { seen[v] = 1; counts[v] = (counts[v] || 0) + 1; } });
      });
      out[f.key] = counts;
    });
    return out;
  }
  function wilson(k, n) {
    if (!n) return [0, 0];
    var z = 1.96, p = k / n, d = 1 + z * z / n;
    var c = (p + z * z / (2 * n)) / d, h = z * Math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d;
    return [Math.max(0, c - h), Math.min(1, c + h)];
  }
  function headline(ds, rows) {
    if (ds === 'bench') {
      var caught = rows.filter(function (r) { return r.f.result[0] === 'caught'; }).length;
      return { cases: rows.length, caught: caught, missed: rows.length - caught };
    }
    var read = rows.filter(function (r) { return r.f.read.length === 1 && r.f.read[0] === 'read'; });
    var flagged = read.filter(function (r) { return !(r.f.severity.length === 1 && r.f.severity[0] === 'none'); });
    var out = { pages: rows.length, read: read.length, not_read: rows.length - read.length, flagged: flagged.length, flagged_ci: wilson(flagged.length, read.length) };
    if (ds === 'pages') out.medium_or_high = read.filter(function (r) { return r.f.severity[0] === 'medium' || r.f.severity[0] === 'high'; }).length;
    if (ds === 'field') out.refusing = read.filter(function (r) { return !(r.f.refused.length === 1 && r.f.refused[0] === '0'); }).length;
    return out;
  }

  function facetsOf(ds) { return DATA.datasets.filter(function (d) { return d.key === ds; })[0].facets; }
  function filtered() {
    return RECORDS.filter(function (r) { return r.ds === state.ds && matches(r, state.filters, state.q, null); });
  }

  // --- URL state -----------------------------------------------------------------------------
  function readHash() {
    var p = new URLSearchParams(location.hash.replace(/^#/, ''));
    var ds = p.get('ds');
    state.ds = DATA.datasets.some(function (d) { return d.key === ds; }) ? ds : 'field';
    state.view = ['data', 'compare', 'about'].indexOf(p.get('view')) >= 0 ? p.get('view') : 'data';
    state.q = p.get('q') || '';
    state.detail = p.get('id') || '';
    state.ca = p.get('ca') || ''; state.cb = p.get('cb') || ''; state.pair = parseInt(p.get('pair') || '0', 10) || 0;
    state.filters = {};
    facetsOf(state.ds).forEach(function (f) { var v = p.getAll('f.' + f.key); if (v.length) state.filters[f.key] = v; });
  }
  function writeHash() {
    var p = new URLSearchParams();
    p.set('ds', state.ds);
    if (state.view !== 'data') p.set('view', state.view);
    Object.keys(state.filters).sort().forEach(function (k) { state.filters[k].forEach(function (v) { p.append('f.' + k, v); }); });
    if (state.q) p.set('q', state.q);
    if (state.detail) p.set('id', state.detail);
    if (state.view === 'compare') { if (state.ca) p.set('ca', state.ca); if (state.cb) p.set('cb', state.cb); p.set('pair', String(state.pair)); }
    var h = '#' + p.toString();
    if (location.hash !== h) history.replaceState(null, '', h);
  }

  // --- rendering -------------------------------------------------------------------------------
  function stat(id, value, label, raw) {
    var s = el('div', 'stat'); s.id = id;
    if (raw !== undefined) s.dataset.value = String(raw);
    s.append(el('b', null, value), el('span', null, label));
    return s;
  }
  function renderHeadline(rows) {
    var h = headline(state.ds, rows), box = byId('headline');
    box.replaceChildren();
    if (state.ds === 'bench') {
      box.append(stat('h-cases', h.cases, 'cases in view', h.cases), stat('h-caught', h.caught + ' (' + pct(h.caught, h.cases) + ')', 'caught', h.caught),
        stat('h-missed', h.missed, 'missed: shown, not hidden', h.missed));
      var b = DATA.bipia;
      if (b && b.cases) box.append(stat('h-bipia', b.caught + ' of ' + b.cases, 'BIPIA injected cases caught (PageVet ' + b.version + '); ' + b.false_alarms + ' of ' + b.clean + ' clean flagged'));
      return;
    }
    var ci = h.flagged_ci;
    box.append(
      stat('h-pages', h.pages, 'pages in view', h.pages),
      stat('h-read', h.read, 'read; ' + h.not_read + ' not read (counted separately, never as clean)', h.read),
      stat('h-flagged', h.flagged + ' of ' + h.read, 'with text aimed at AI, any severity (95% CI ' + (100 * ci[0]).toFixed(1) + '–' + (100 * ci[1]).toFixed(1) + '%)', h.flagged));
    if (state.ds === 'field') box.append(stat('h-refusing', h.refusing + ' of ' + h.read + ' (' + pct(h.refusing, h.read) + ')', 'refuse at least one of three AI crawlers: a site\'s choice', h.refusing));
    if (state.ds === 'pages') box.append(stat('h-medhigh', h.medium_or_high, 'flagged at medium or high', h.medium_or_high));
  }

  function renderFacets() {
    var counts = facetCounts(state.ds, state.filters, state.q), box = byId('facets');
    box.replaceChildren();
    facetsOf(state.ds).forEach(function (f) {
      var c = counts[f.key] || {}, selected = state.filters[f.key] || [];
      var values = Object.keys(c);
      selected.forEach(function (v) { if (values.indexOf(v) < 0) values.push(v); });
      if (!values.length) return;
      values.sort(function (a, b) { return (c[b] || 0) - (c[a] || 0) || (a < b ? -1 : a > b ? 1 : 0); });
      var fs = el('fieldset'); fs.dataset.facet = f.key;
      fs.append(el('legend', null, f.label));
      values.forEach(function (v) {
        var lab = el('label'); lab.dataset.facet = f.key; lab.dataset.value = v;
        var box2 = el('input'); box2.type = 'checkbox'; box2.checked = selected.indexOf(v) >= 0;
        box2.addEventListener('change', function () {
          var cur = (state.filters[f.key] || []).filter(function (x) { return x !== v; });
          if (box2.checked) cur.push(v);
          if (cur.length) state.filters[f.key] = cur; else delete state.filters[f.key];
          state.limit = PAGE_SIZE; update();
        });
        var span = el('span', 'v'); span.append(box2, document.createTextNode(' ' + v));
        var n = c[v] || 0, cnt = el('span', 'count' + (n ? '' : ' zero'), n); cnt.dataset.count = String(n);
        lab.append(span, cnt); fs.append(lab);
      });
      box.append(fs);
    });
  }

  var COLUMNS = {
    field: [['url', 'Page'], ['study', 'Study'], ['read', 'Read'], ['severity', 'Text aimed at AI'], ['refused', 'AI crawlers not served'], ['differs', 'Different text']],
    pages: [['url', 'Page'], ['set', 'Set'], ['language', 'Language'], ['read', 'Read'], ['severity', 'Highest severity']],
    bench: [['title', 'Case'], ['set', 'Set'], ['language', 'Language'], ['technique', 'Technique'], ['result', 'Result']]
  };
  function renderTable(rows) {
    var box = byId('results'), cols = COLUMNS[state.ds];
    box.replaceChildren();
    byId('count').textContent = rows.length + ' records';
    var t = el('table'), head = el('tr');
    cols.forEach(function (c) { head.append(el('th', null, c[1])); });
    head.append(el('th', null, ''));
    var thead = el('thead'); thead.append(head); t.append(thead);
    var tb = el('tbody');
    rows.slice(0, state.limit).forEach(function (r) {
      var tr = el('tr'); tr.dataset.id = r.id;
      cols.forEach(function (c) {
        var v = c[0] === 'url' ? r.url : c[0] === 'title' ? r.title : (r.f[c[0]] || []).join(', ');
        tr.append(el('td', c[0] === 'url' ? 'url' : null, v));
      });
      var td = el('td'), b = el('button', null, 'Details'); b.type = 'button';
      b.addEventListener('click', function () { state.detail = r.id; renderDrawer(); writeHash(); });
      td.append(b); tr.append(td); tb.append(tr);
    });
    t.append(tb); box.append(t);
    if (rows.length > state.limit) {
      var more = el('button', 'more', 'Show ' + Math.min(PAGE_SIZE, rows.length - state.limit) + ' more (counts above cover all ' + rows.length + ')');
      more.type = 'button';
      more.addEventListener('click', function () { state.limit += PAGE_SIZE; renderTable(rows); });
      box.append(more);
    }
  }

  function renderReproduce() {
    var lines = [];
    if (state.ds === 'field') {
      var studies = DATA.studies.filter(function (s) { return !state.filters.study || state.filters.study.indexOf(s.topic) >= 0; });
      studies.forEach(function (s) { lines.push('pagevet-study report docs/bench/' + s.folder + '      # ' + s.topic); });
      lines.push('pagevet-study compare docs/bench/*-field-* --out docs/bench/FIELD-STUDIES.md');
    } else if (state.ds === 'pages') {
      lines.push('uv run python docs/bench/pages_12_languages.py scan PAGES.jsonl.gz results.json   # twelve-language set (pages kept locally)');
      lines.push('uv run python docs/bench/clean_pages.py ...                                       # older sets: see each folder README');
    } else {
      lines.push('uv run python docs/bench/evasion_run.py docs/bench/2026-11-19-evasion results.json');
      lines.push('pagevet-bench cases.jsonl     # BIPIA: build cases.jsonl with docs/bench/bipia_build.py');
    }
    lines.push('pagevet-study explore docs/bench/*-field-* --out site/    # then open site/index.html' + location.hash);
    byId('reproduce-cmd').textContent = lines.join('\n');
  }

  function dl(pairs) {
    var d = el('dl');
    pairs.forEach(function (p) { if (p[1] === '' || p[1] === undefined) return; d.append(el('dt', null, p[0]), el('dd', null, p[1])); });
    return d;
  }
  function renderDrawer() {
    var box = byId('drawer'), r = BY_ID[state.detail];
    box.replaceChildren();
    if (!r) { box.hidden = true; return; }
    box.hidden = false;
    var close = el('button', null, 'Close'); close.type = 'button';
    close.addEventListener('click', function () { state.detail = ''; renderDrawer(); writeHash(); });
    box.append(close, el('h2', null, r.url || r.title));
    var pairs = [['Domain', r.domain], ['Response', r.d.status], ['How read', r.d.how]];
    facetsOf(r.ds).forEach(function (f) { pairs.push([f.label, (r.f[f.key] || []).join(', ')]); });
    pairs.push(['Hashes', r.d.hashes]);
    box.append(dl(pairs));
    if (r.d.findings.length) {
      box.append(el('h3', null, 'Findings'));
      r.d.findings.forEach(function (f) {
        box.append(dl([['Severity', f.severity], ['Where', f.where], ['Kinds', f.kinds.join(', ')], ['Quote', f.quote], ['Why this severity', f.reason]]));
      });
    } else if (r.f.read && r.f.read[0] !== 'read') {
      box.append(el('p', 'note', 'Not read, so not checked. This page is not counted as clean.'));
    }
    if (r.d.crawlers.length) {
      box.append(el('h3', null, 'AI crawlers'));
      r.d.crawlers.forEach(function (c) { box.append(dl([['', c.what], ['Evidence', c.quote]])); });
    }
    box.append(el('h3', null, 'Re-check this page'), el('pre', null, r.d.recheck));
  }

  function renderCompare() {
    var box = byId('compare');
    box.replaceChildren();
    box.append(el('h2', null, 'Two studies side by side'));
    var studies = DATA.studies;
    if (!state.ca && studies[0]) state.ca = studies[0].folder;
    if (!state.cb && studies[1]) state.cb = studies[1].folder;
    function picker(which) {
      var s = el('select'); s.setAttribute('aria-label', which === 'ca' ? 'First study' : 'Second study');
      studies.forEach(function (st) { var o = el('option', null, st.topic + ' (' + st.date + ')'); o.value = st.folder; o.selected = state[which] === st.folder; s.append(o); });
      s.addEventListener('change', function () { state[which] = s.value; renderCompare(); writeHash(); });
      return s;
    }
    box.append(picker('ca'), document.createTextNode(' vs '), picker('cb'));
    var A = studies.filter(function (s) { return s.folder === state.ca; })[0], B = studies.filter(function (s) { return s.folder === state.cb; })[0];
    if (A && B) {
      var rows = [['Scanned', A.scanned, B.scanned], ['Read', A.read, B.read],
        ['Not read', A.scanned - A.read, B.scanned - B.read],
        ['Pages with text aimed at AI (high/medium/low)', [A.found.high || 0, A.found.medium || 0, A.found.low || 0].join(' / '), [B.found.high || 0, B.found.medium || 0, B.found.low || 0].join(' / ')],
        ['Refuse ≥1 AI crawler', A.refused_any + ' (' + pct(A.refused_any, A.read) + ')', B.refused_any + ' (' + pct(B.refused_any, B.read) + ')'],
        ['Refuse all three', A.refused_all, B.refused_all], ['Served different text to an AI crawler', A.differs, B.differs]];
      ['GPTBot', 'ClaudeBot', 'PerplexityBot'].forEach(function (a) { rows.push([a + ' not served', A.refusals[a] || 0, B.refusals[a] || 0]); });
      box.append(table(['', A.topic, B.topic], rows, true));
    }
    box.append(el('h2', null, 'Two PageVet versions on identical bytes'));
    var pairs = DATA.version_pairs, sel = el('select'); sel.setAttribute('aria-label', 'Version pair');
    pairs.forEach(function (p, i) { var o = el('option', null, p.name); o.value = String(i); o.selected = i === state.pair; sel.append(o); });
    sel.addEventListener('change', function () { state.pair = parseInt(sel.value, 10); renderCompare(); writeHash(); });
    box.append(sel);
    var P = pairs[state.pair];
    if (P) {
      var diff = P.rows.filter(function (r) { return r[1] !== r[2]; });
      box.append(el('p', null, P.rows.length + ' pages; ' + (P.rows.length - diff.length) + ' rated the same by both versions; ' + diff.length + ' different (highlighted).'));
      box.append(table(['Page', P.left, P.right], diff.length ? diff : [['No differences', '', '']], false));
    }
  }
  function table(head, rows, markDiff) {
    var t = el('table'), hr = el('tr');
    head.forEach(function (h) { hr.append(el('th', null, h)); });
    var th = el('thead'); th.append(hr); t.append(th);
    var tb = el('tbody');
    rows.forEach(function (r) {
      var tr = el('tr', (!markDiff || String(r[1]) !== String(r[2])) && r[1] !== '' ? 'diff' : null);
      r.forEach(function (c, i) { tr.append(el('td', i === 0 ? 'url' : null, c)); });
      tb.append(tr);
    });
    t.append(tb);
    return t;
  }

  function renderTabs() {
    var nav = byId('tabs');
    nav.replaceChildren();
    var items = DATA.datasets.map(function (d) { return [d.key, d.label]; }).concat([['compare', 'Compare'], ['about', 'About this data']]);
    items.forEach(function (it) {
      var b = el('button', null, it[1]); b.type = 'button'; b.dataset.tab = it[0];
      var on = (state.view === 'data' && state.ds === it[0]) || state.view === it[0];
      b.setAttribute('aria-selected', on ? 'true' : 'false');
      b.addEventListener('click', function () {
        if (it[0] === 'compare' || it[0] === 'about') state.view = it[0];
        else { state.view = 'data'; if (state.ds !== it[0]) { state.ds = it[0]; state.filters = {}; state.q = ''; state.detail = ''; } }
        state.limit = PAGE_SIZE; byId('q').value = state.q; update();
      });
      nav.append(b);
    });
  }

  function renderFooter(digest) {
    var p = DATA.provenance;
    byId('footer').textContent = 'PageVet ' + p.pagevet + ' · commit ' + p.commit + ' · study runs ' + p.study_dates.join(', ') +
      ' · ' + p.records + ' records · schema ' + DATA.schema_version + ' · data sha256 ' + digest + ' (verified in this page)';
  }

  function update() {
    var dataView = state.view === 'data';
    byId('layout').hidden = !dataView; byId('headline').hidden = !dataView;
    byId('compare').hidden = state.view !== 'compare'; byId('about').hidden = state.view !== 'about';
    renderTabs();
    if (dataView) {
      var rows = filtered();
      renderHeadline(rows); renderFacets(); renderTable(rows); renderReproduce();
    } else if (state.view === 'compare') renderCompare();
    renderDrawer();
    writeHash();
    document.body.dataset.state = 'ready';
  }

  function start() {
    var node = byId('pv-data'), expected = (document.querySelector('meta[name="pv-data-sha256"]') || {}).content || '';
    if (!node) return fail('The data block is missing.');
    var text = node.textContent;
    if (!window.crypto || !crypto.subtle) return fail('This browser cannot verify the data (no Web Crypto), so nothing is shown.');
    sha256hex(text).then(function (digest) {
      if (digest !== expected) return fail('The embedded data does not match its SHA-256 (expected ' + expected + ', got ' + digest + '). The file was changed after it was generated.');
      try { DATA = JSON.parse(text); } catch (e) { return fail('The embedded data is not valid JSON.'); }
      if (DATA.schema_version !== SCHEMA_VERSION) return fail('Unknown schema_version ' + JSON.stringify(DATA.schema_version) + '; this page reads version ' + SCHEMA_VERSION + '.');
      RECORDS = DATA.records;
      RECORDS.forEach(function (r) { BY_ID[r.id] = r; });
      readHash();
      var q = byId('q');
      q.value = state.q;
      q.addEventListener('input', function () { state.q = q.value.trim(); state.limit = PAGE_SIZE; update(); });
      byId('clear').addEventListener('click', function () { state.filters = {}; state.q = ''; q.value = ''; update(); });
      document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && state.detail) { state.detail = ''; renderDrawer(); writeHash(); } });
      window.addEventListener('hashchange', function () { readHash(); byId('q').value = state.q; update(); });
      renderFooter(digest);
      update();
    }, function () { fail('The data could not be verified.'); });
  }
  start();
})();
