/* Tríada — three interconnected tracks: touch typing, Neovim, Python.
 * No build step, no framework, works from file://. */
(function () {
  'use strict';

  var C = window.CURRICULUM;
  var TRACKS = ['typing', 'nvim', 'python'];
  var STORE_KEY = 'triada.progress.v1';

  /* =====================================================  utilities  */
  function h(tag, attrs, children) {
    var e = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (k) {
        var v = attrs[k];
        if (v === null || v === undefined || v === false) return;
        if (k === 'class') e.className = v;
        else if (k === 'html') e.innerHTML = v;
        else if (k === 'text') e.textContent = v;
        else if (k.slice(0, 2) === 'on') e.addEventListener(k.slice(2), v);
        else e.setAttribute(k, v === true ? '' : v);
      });
    }
    (children || []).forEach(function (c) {
      if (c === null || c === undefined || c === false) return;
      e.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
    });
    return e;
  }

  function esc(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  /* A small markdown renderer: enough for the teaching text we author. */
  function md(src) {
    var lines = String(src || '').split('\n');
    var out = [], i = 0;

    function inline(s) {
      s = esc(s);
      s = s.replace(/`([^`]+)`/g, function (_, c) { return '<code>' + c + '</code>'; });
      s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
      s = s.replace(/(^|[\s(])\*([^*\n]+)\*/g, '$1<em>$2</em>');
      return s;
    }

    while (i < lines.length) {
      var ln = lines[i];

      if (/^```/.test(ln)) {
        var buf = [];
        i += 1;
        while (i < lines.length && !/^```/.test(lines[i])) { buf.push(lines[i]); i += 1; }
        i += 1;
        out.push('<pre><code>' + esc(buf.join('\n')) + '</code></pre>');
        continue;
      }
      if (/^\|/.test(ln) && i + 1 < lines.length && /^\|[\s:|-]+\|?\s*$/.test(lines[i + 1])) {
        var cells = function (row) {
          return row.replace(/^\||\|$/g, '').split('|').map(function (c) { return c.trim(); });
        };
        var head = cells(ln);
        i += 2;
        var body = [];
        while (i < lines.length && /^\|/.test(lines[i])) { body.push(cells(lines[i])); i += 1; }
        out.push('<table><thead><tr>' + head.map(function (c) { return '<th>' + inline(c) + '</th>'; }).join('') +
          '</tr></thead><tbody>' + body.map(function (r) {
            return '<tr>' + r.map(function (c) { return '<td>' + inline(c) + '</td>'; }).join('') + '</tr>';
          }).join('') + '</tbody></table>');
        continue;
      }
      if (/^(\s*)[-*] /.test(ln)) {
        var items = [];
        while (i < lines.length && /^\s*[-*] /.test(lines[i])) {
          items.push(lines[i].replace(/^\s*[-*] /, ''));
          i += 1;
          while (i < lines.length && /^\s{2,}\S/.test(lines[i]) && !/^\s*[-*] /.test(lines[i])) {
            items[items.length - 1] += ' ' + lines[i].trim();
            i += 1;
          }
        }
        out.push('<ul>' + items.map(function (t) { return '<li>' + inline(t) + '</li>'; }).join('') + '</ul>');
        continue;
      }
      if (/^\s*\d+\. /.test(ln)) {
        var oitems = [];
        while (i < lines.length && /^\s*\d+\. /.test(lines[i])) {
          oitems.push(lines[i].replace(/^\s*\d+\. /, ''));
          i += 1;
          while (i < lines.length && /^\s{2,}\S/.test(lines[i]) && !/^\s*\d+\. /.test(lines[i])) {
            oitems[oitems.length - 1] += ' ' + lines[i].trim();
            i += 1;
          }
        }
        out.push('<ol>' + oitems.map(function (t) { return '<li>' + inline(t) + '</li>'; }).join('') + '</ol>');
        continue;
      }
      if (/^#{1,4} /.test(ln)) {
        var lvl = ln.match(/^#+/)[0].length;
        out.push('<h' + (lvl + 1) + '>' + inline(ln.replace(/^#+ /, '')) + '</h' + (lvl + 1) + '>');
        i += 1;
        continue;
      }
      if (!ln.trim()) { i += 1; continue; }
      var para = [];
      while (i < lines.length && lines[i].trim() && !/^(```|\||#{1,4} |\s*[-*] |\s*\d+\. )/.test(lines[i])) {
        para.push(lines[i]); i += 1;
      }
      out.push('<p>' + inline(para.join(' ')) + '</p>');
    }
    return out.join('\n');
  }

  /* ====================================================== progress  */
  function blankProgress() {
    return {
      version: 1,
      typing: { lessons: {}, level: 1 },
      nvim: { lessons: {}, level: 1 },
      python: { lessons: {}, level: 1 },
      combos: {},
      keyStats: {},
      totals: { seconds: 0, sessions: 0 }
    };
  }

  var progress = load();

  function load() {
    try {
      var raw = localStorage.getItem(STORE_KEY);
      if (!raw) return blankProgress();
      var p = JSON.parse(raw);
      var base = blankProgress();
      TRACKS.forEach(function (t) {
        base[t].lessons = (p[t] && p[t].lessons) || {};
        base[t].level = (p[t] && p[t].level) || 1;
      });
      base.combos = p.combos || {};
      base.keyStats = p.keyStats || {};
      base.totals = p.totals || base.totals;
      return base;
    } catch (e) { return blankProgress(); }
  }

  function save() {
    try { localStorage.setItem(STORE_KEY, JSON.stringify(progress)); }
    catch (e) { /* private mode, quota — progress simply is not persisted */ }
  }

  function lessonDone(track, id) { return !!(progress[track].lessons[id] && progress[track].lessons[id].done); }

  function markDone(track, id, score) {
    var rec = progress[track].lessons[id] || { done: false, tries: 0 };
    rec.done = true;
    rec.tries = (rec.tries || 0) + 1;
    if (score) {
      rec.best = rec.best || {};
      Object.keys(score).forEach(function (k) {
        var better = k === 'keys' ? (rec.best[k] === undefined || score[k] < rec.best[k])
          : (rec.best[k] === undefined || score[k] > rec.best[k]);
        if (better) rec.best[k] = score[k];
      });
      rec.last = score;
    }
    progress[track].lessons[id] = rec;
    recomputeLevel(track);
    save();
  }

  function markTried(track, id) {
    var rec = progress[track].lessons[id] || { done: false, tries: 0 };
    rec.tries = (rec.tries || 0) + 1;
    progress[track].lessons[id] = rec;
    save();
  }

  function levelComplete(track, lv) {
    return lv.lessons.every(function (ls) { return lessonDone(track, ls.id); });
  }

  function recomputeLevel(track) {
    var lvs = C[track].levels, unlocked = 1;
    for (var i = 0; i < lvs.length; i++) {
      if (levelComplete(track, lvs[i])) unlocked = Math.min(lvs.length, i + 2);
      else break;
    }
    progress[track].level = Math.max(progress[track].level || 1, unlocked);
  }
  TRACKS.forEach(recomputeLevel);

  function trackStats(track) {
    var lvs = C[track].levels;
    var total = 0, done = 0;
    lvs.forEach(function (lv) {
      lv.lessons.forEach(function (ls) { total += 1; if (lessonDone(track, ls.id)) done += 1; });
    });
    return { total: total, done: done, pct: total ? done / total : 0, level: progress[track].level, levels: lvs.length };
  }

  /* ============================================ ES QWERTY keyboard  */
  /* rows of [primary, shifted, altgr, fingerClass] */
  var KB = [
    [['º', 'ª', '\\', 'f4'], ['1', '!', '|', 'f4'], ['2', '"', '@', 'f3'], ['3', '·', '#', 'f2'],
     ['4', '$', '~', 'f1'], ['5', '%', '€', 'f1'], ['6', '&', '¬', 'f1'], ['7', '/', '', 'f1'],
     ['8', '(', '', 'f2'], ['9', ')', '', 'f3'], ['0', '=', '', 'f4'], ["'", '?', '', 'f4'],
     ['¡', '¿', '', 'f4']],
    [['q', 'Q', '', 'f4'], ['w', 'W', '', 'f3'], ['e', 'E', '', 'f2'], ['r', 'R', '', 'f1'],
     ['t', 'T', '', 'f1'], ['y', 'Y', '', 'f1'], ['u', 'U', '', 'f1'], ['i', 'I', '', 'f2'],
     ['o', 'O', '', 'f3'], ['p', 'P', '', 'f4'], ['`', '^', '[', 'f4'], ['+', '*', ']', 'f4']],
    [['a', 'A', '', 'f4'], ['s', 'S', '', 'f3'], ['d', 'D', '', 'f2'], ['f', 'F', '', 'f1'],
     ['g', 'G', '', 'f1'], ['h', 'H', '', 'f1'], ['j', 'J', '', 'f1'], ['k', 'K', '', 'f2'],
     ['l', 'L', '', 'f3'], ['ñ', 'Ñ', '', 'f4'], ['´', '¨', '{', 'f4'], ['ç', 'Ç', '}', 'f4']],
    [['<', '>', '', 'f4'], ['z', 'Z', '', 'f4'], ['x', 'X', '', 'f3'], ['c', 'C', '', 'f2'],
     ['v', 'V', '', 'f1'], ['b', 'B', '', 'f1'], ['n', 'N', '', 'f1'], ['m', 'M', '', 'f2'],
     [',', ';', '', 'f3'], ['.', ':', '', 'f4'], ['-', '_', '', 'f4']]
  ];

  var DEAD = { 'á': ['´', 'a'], 'é': ['´', 'e'], 'í': ['´', 'i'], 'ó': ['´', 'o'], 'ú': ['´', 'u'],
    'Á': ['´', 'A'], 'É': ['´', 'E'], 'Í': ['´', 'I'], 'Ó': ['´', 'O'], 'Ú': ['´', 'U'],
    'ü': ['¨', 'u'], 'Ü': ['¨', 'U'], 'à': ['`', 'a'], 'è': ['`', 'e'] };

  var KEYINDEX = (function () {
    var idx = {};
    KB.forEach(function (row, r) {
      row.forEach(function (k, c) {
        if (k[0]) idx[k[0]] = { r: r, c: c, mod: '' };
        if (k[1] && !idx[k[1]]) idx[k[1]] = { r: r, c: c, mod: 'Shift' };
        if (k[2] && !idx[k[2]]) idx[k[2]] = { r: r, c: c, mod: 'AltGr' };
      });
    });
    idx[' '] = { r: -1, c: -1, mod: '' };
    return idx;
  })();

  function keyHint(ch) {
    if (ch === ' ') return 'Space (thumb)';
    if (ch === '\n') return 'Enter (right pinky)';
    if (DEAD[ch]) {
      var d = DEAD[ch];
      var m = KEYINDEX[d[0]];
      return (m && m.mod === 'Shift' ? 'Shift + ' : '') + '´/¨ dead key, then ' + d[1];
    }
    var k = KEYINDEX[ch];
    if (!k) return '';
    var label = KB[k.r][k.c][0];
    return (k.mod ? k.mod + ' + ' : '') + (label === ' ' ? 'Space' : label);
  }

  function keyFor(ch) {
    if (DEAD[ch]) return KEYINDEX[DEAD[ch][0]];
    return KEYINDEX[ch];
  }

  /* ==================================================== app state  */
  var view = { name: 'home', track: 'typing', levelId: null, lessonId: null, comboId: null };
  var app = document.getElementById('app');
  var teardown = null;

  function go(v) {
    if (teardown) { teardown(); teardown = null; }
    Object.assign(view, v);
    render();
    app.focus({ preventScroll: true });
    window.scrollTo({ top: 0, behavior: 'auto' });
  }

  function render() {
    renderTabs();
    app.innerHTML = '';
    var fns = { home: viewHome, track: viewTrack, lesson: viewLesson, combos: viewCombos, combo: viewCombo, stats: viewStats };
    (fns[view.name] || viewHome)();
  }

  var TRACKMETA = {
    typing: { label: 'Typing', key: '1' },
    nvim: { label: 'Neovim', key: '2' },
    python: { label: 'Python', key: '3' }
  };

  function renderTabs() {
    var tabs = document.getElementById('tabs');
    tabs.innerHTML = '';
    TRACKS.forEach(function (t) {
      var s = trackStats(t);
      tabs.appendChild(h('button', {
        class: 'tab', 'aria-current': (view.name === 'track' && view.track === t) || (view.name === 'lesson' && view.track === t) ? 'page' : null,
        onclick: function () { go({ name: 'track', track: t }); }
      }, [
        h('span', { class: 'pip ' + t }),
        TRACKMETA[t].label,
        h('span', { class: 'kbd' }, ['L' + s.level])
      ]));
    });
    tabs.appendChild(h('button', {
      class: 'tab', 'aria-current': view.name === 'combos' || view.name === 'combo' ? 'page' : null,
      onclick: function () { go({ name: 'combos' }); }
    }, [h('span', { class: 'pip combos' }), 'Combos']));
    tabs.appendChild(h('button', {
      class: 'tab', 'aria-current': view.name === 'stats' ? 'page' : null,
      onclick: function () { go({ name: 'stats' }); }
    }, ['Stats']));
  }

  /* ======================================================== HOME  */
  function viewHome() {
    app.appendChild(h('h1', {}, ['Three skills, one keyboard.']));
    app.appendChild(h('p', { class: 'lede' }, [
      'Touch typing, Neovim and Python — taught side by side and practised on the same material, ' +
      'but progressed independently. Reach expert in one while you are still starting another.'
    ]));

    var grid = h('div', { class: 'grid' });
    TRACKS.forEach(function (t) {
      var s = trackStats(t);
      var lv = C[t].levels[Math.min(s.level, C[t].levels.length) - 1];
      grid.appendChild(h('button', { class: 'card', onclick: function () { go({ name: 'track', track: t }); } }, [
        h('div', { class: 'tagline', style: 'color:var(--' + t + ')' }, [C[t].title]),
        h('h3', {}, ['Level ' + s.level + ' · ' + lv.title]),
        h('p', {}, [lv.goal]),
        h('div', { class: 'bar ' + t }, [h('i', { style: 'width:' + Math.round(s.pct * 100) + '%' })]),
        h('div', { class: 'meta' }, [
          h('span', {}, [s.done + ' / ' + s.total + ' lessons']),
          h('span', {}, [s.level + ' / ' + s.levels + ' levels'])
        ])
      ]));
    });
    app.appendChild(grid);

    // next-up strip
    app.appendChild(h('h2', {}, ['Pick up where you left off']));
    var strip = h('div', { class: 'levels' });
    TRACKS.forEach(function (t) {
      var nx = nextLesson(t);
      if (!nx) return;
      strip.appendChild(h('button', { class: 'lesson-row', onclick: function () { go({ name: 'lesson', track: t, levelId: nx.lv.id, lessonId: nx.ls.id }); } }, [
        h('span', { class: 'pip ' + t, style: 'flex:0 0 auto' }),
        h('span', { class: 'kind' }, [TRACKMETA[t].label]),
        h('span', { class: 'name' }, ['L' + nx.lv.n + ' · ' + nx.ls.title]),
        h('span', { class: 'score' }, ['start →'])
      ]));
    });
    app.appendChild(strip);

    var avail = C.combos.combos.filter(comboUnlocked).length;
    app.appendChild(h('div', { class: 'linkbox' }, [
      h('b', {}, ['Combos. ']),
      avail + ' of ' + C.combos.combos.length + ' unlocked. ',
      'Each one is a single task that needs all three skills at once — the only place the tracks meet. ',
      h('a', { tabindex: '0', role: 'button', onclick: function () { go({ name: 'combos' }); } }, ['Open combos'])
    ]));

    app.appendChild(h('p', { class: 'muted', style: 'margin-top:26px' }, [
      'Everything is keyboard-navigable: ',
      h('kbd', {}, ['j']), ' ', h('kbd', {}, ['k']), ' to move, ',
      h('kbd', {}, ['Enter']), ' to open, ', h('kbd', {}, ['Esc']), ' to go back, ',
      h('kbd', {}, ['?']), ' for the full list.'
    ]));
  }

  function nextLesson(track) {
    var lvs = C[track].levels;
    for (var i = 0; i < Math.min(progress[track].level, lvs.length); i++) {
      for (var j = 0; j < lvs[i].lessons.length; j++) {
        if (!lessonDone(track, lvs[i].lessons[j].id)) return { lv: lvs[i], ls: lvs[i].lessons[j] };
      }
    }
    var last = lvs[Math.min(progress[track].level, lvs.length) - 1];
    return { lv: last, ls: last.lessons[0] };
  }

  /* ======================================================= TRACK  */
  var openLevels = {};

  function viewTrack() {
    var t = view.track, doc = C[t], s = trackStats(t);
    app.appendChild(h('h1', {}, [doc.title]));
    app.appendChild(h('p', { class: 'lede' }, [doc.subtitle]));
    app.appendChild(h('div', { class: 'bar ' + t, style: 'max-width:420px' }, [h('i', { style: 'width:' + Math.round(s.pct * 100) + '%' })]));
    app.appendChild(h('p', { class: 'muted' }, [
      s.done + ' of ' + s.total + ' lessons done · level ' + s.level + ' of ' + s.levels + ' unlocked'
    ]));

    var wrap = h('div', { class: 'levels' });
    doc.levels.forEach(function (lv) {
      var locked = lv.n > progress[t].level;
      var complete = levelComplete(t, lv);
      var doneN = lv.lessons.filter(function (ls) { return lessonDone(t, ls.id); }).length;
      var isOpen = openLevels[lv.id] || (!locked && !complete && doneN < lv.lessons.length && lv.n === progress[t].level);

      var body = h('div', { class: 'level-body', hidden: !isOpen });
      body.appendChild(h('div', { class: 'prose', html: md(lv.brief) }));
      lv.lessons.forEach(function (ls) {
        body.appendChild(h('button', {
          class: 'lesson-row', 'data-nav': '1',
          onclick: function () { go({ name: 'lesson', track: t, levelId: lv.id, lessonId: ls.id }); }
        }, [
          h('span', { class: 'tick' }, [lessonDone(t, ls.id) ? '✓' : '']),
          h('span', { class: 'kind' }, [kindLabel(t, ls)]),
          h('span', { class: 'name' }, [ls.title]),
          h('span', { class: 'score' }, [scoreLabel(t, ls)])
        ]));
      });
      (lv.links || []).forEach(function (lk) {
        body.appendChild(h('div', { class: 'linkbox' }, [
          h('b', {}, [TRACKMETA[lk.track].label + ' · ' + levelById(lk.track, lk.level).title + '. ']),
          lk.note + ' ',
          h('a', {
            tabindex: '0', role: 'button',
            onclick: function () { openLevels[lk.level] = true; go({ name: 'track', track: lk.track }); }
          }, ['Go there'])
        ]));
      });

      var head = h('button', {
        class: 'level-head', 'data-nav': '1', 'aria-expanded': isOpen ? 'true' : 'false',
        onclick: function () {
          if (locked) { flash('Finish level ' + (lv.n - 1) + ' first — every lesson in it.'); return; }
          var now = body.hasAttribute('hidden');
          openLevels[lv.id] = now;
          if (now) body.removeAttribute('hidden'); else body.setAttribute('hidden', '');
          head.setAttribute('aria-expanded', now ? 'true' : 'false');
        }
      }, [
        h('span', { class: 'level-num' }, [locked ? '🔒' : String(lv.n)]),
        h('span', { class: 'level-title' }, [h('b', {}, [lv.title]), h('span', {}, [lv.goal])]),
        h('span', { class: 'level-count' }, [doneN + '/' + lv.lessons.length])
      ]);

      wrap.appendChild(h('div', {
        class: 'level' + (locked ? ' locked' : '') + (complete ? ' done' : '') + (lv.n === progress[t].level && !complete ? ' current' : '')
      }, [head, body]));
    });
    app.appendChild(wrap);
    initNav();
  }

  function levelById(track, id) {
    return C[track].levels.filter(function (l) { return l.id === id; })[0];
  }

  function kindLabel(track, ls) {
    if (track === 'typing') return ls.kind;
    if (track === 'nvim') return ls.kind === 'quiz' ? 'quiz' : (ls.kind === 'move' ? 'move' : 'edit');
    return ls.kind;
  }

  function scoreLabel(track, ls) {
    var rec = progress[track].lessons[ls.id];
    if (!rec || !rec.best) return '';
    var b = rec.best;
    if (b.wpm !== undefined) return b.wpm + ' wpm · ' + Math.round(b.acc * 100) + '%';
    if (b.keys !== undefined) return b.keys + ' keys (par ' + ls.par + ')';
    return '';
  }

  /* ====================================================== LESSON  */
  function viewLesson() {
    var t = view.track;
    var lv = levelById(t, view.levelId);
    var idx = lv.lessons.findIndex(function (l) { return l.id === view.lessonId; });
    var ls = lv.lessons[idx];
    if (!ls) { go({ name: 'track', track: t }); return; }

    app.appendChild(h('div', { class: 'crumb' }, [
      h('button', { onclick: function () { go({ name: 'track', track: t }); } }, [C[t].title]),
      ' / Level ' + lv.n + ' · ' + lv.title
    ]));
    app.appendChild(h('div', { class: 'lesson-head' }, [
      h('h1', { style: 'margin-top:6px' }, [ls.title]),
      h('span', { class: 'muted' }, [(idx + 1) + ' of ' + lv.lessons.length])
    ]));

    if (ls.teach) app.appendChild(h('div', { class: 'prose', html: md(ls.teach) }));

    var host = h('div', {});
    app.appendChild(host);

    var nextBtn = h('button', {
      class: 'btn primary', onclick: function () { gotoNext(); }
    }, ['Next lesson ', h('span', { class: 'kbd' }, ['Ctrl ↵'])]);

    function gotoNext() {
      if (idx + 1 < lv.lessons.length) go({ name: 'lesson', track: t, levelId: lv.id, lessonId: lv.lessons[idx + 1].id });
      else {
        var lvs = C[t].levels, li = lvs.indexOf(lv);
        if (li + 1 < lvs.length && lv.n < progress[t].level) {
          go({ name: 'lesson', track: t, levelId: lvs[li + 1].id, lessonId: lvs[li + 1].lessons[0].id });
        } else { openLevels[lv.id] = true; go({ name: 'track', track: t }); }
      }
    }

    var onDone = function (score) { markDone(t, ls.id, score); renderTabs(); };

    if (t === 'typing') typingLesson(host, ls, onDone, nextBtn);
    else if (t === 'nvim') {
      if (ls.kind === 'quiz') quizLesson(host, ls, onDone, nextBtn);
      else vimLesson(host, ls, onDone, nextBtn);
    } else {
      if (ls.kind === 'quiz') quizLesson(host, ls, onDone, nextBtn);
      else if (ls.kind === 'output') outputLesson(host, ls, onDone, nextBtn);
      else codeLesson(host, ls, onDone, nextBtn);
    }

    window.__next = gotoNext;
  }

  /* ---------------------------------------------------- typing UI */
  function typingLesson(host, ls, onDone, nextBtn) {
    var target = ls.content;
    var chars = Array.from(target);
    var typed = '';
    var started = null, finished = false, timer = null;
    var firstWrong = {};   // index -> true, for accuracy over first attempts
    var errKeys = {};

    var stats = h('div', { class: 'stat-row' });
    var surface = h('div', { class: 'type-surface', tabindex: '0' });
    var input = h('textarea', {
      class: 'hidden-input', autocapitalize: 'off', autocorrect: 'off',
      autocomplete: 'off', spellcheck: 'false', 'aria-label': 'Typing input'
    });
    var kbmap = h('div', { class: 'kbmap' });
    var hint = h('div', { class: 'kbhint' });
    var banner = h('div', {});

    var pass = ls.pass || (levelById('typing', view.levelId) || {}).pass || { wpm: 25, acc: 0.95 };

    var panel = h('div', { class: 'panel' }, [stats, surface, hint, kbmap, banner]);
    surface.appendChild(input);
    host.appendChild(panel);

    var showKb = true;
    host.appendChild(h('div', { class: 'toolbar' }, [
      h('button', { class: 'btn', onclick: reset }, ['Restart ', h('span', { class: 'kbd' }, ['Alt R'])]),
      h('button', {
        class: 'btn', onclick: function (e) {
          showKb = !showKb;
          kbmap.hidden = !showKb;
          e.target.textContent = showKb ? 'Hide keyboard' : 'Show keyboard';
        }
      }, ['Hide keyboard']),
      nextBtn
    ]));

    function reset() {
      typed = ''; started = null; finished = false; firstWrong = {}; errKeys = {};
      banner.innerHTML = '';
      input.value = '';
      surface.classList.remove('done');
      draw();
      input.focus();
    }

    surface.addEventListener('mousedown', function (e) {
      if (e.target !== input) { e.preventDefault(); input.focus(); }
    });
    surface.addEventListener('focus', function () { input.focus(); });

    input.addEventListener('input', function () {
      if (finished) { input.value = typed; return; }
      var v = input.value;
      if (v.length > chars.length + 20) v = v.slice(0, chars.length + 20);
      if (started === null && v.length) {
        started = performance.now();
        timer = setInterval(draw, 250);
      }
      // record first-attempt errors for the characters newly reached
      var arr = Array.from(v);
      for (var i = Array.from(typed).length; i < arr.length; i++) {
        if (i < chars.length && arr[i] !== chars[i]) {
          firstWrong[i] = true;
          errKeys[chars[i]] = (errKeys[chars[i]] || 0) + 1;
          progress.keyStats[chars[i]] = (progress.keyStats[chars[i]] || 0) + 1;
        }
      }
      typed = v;
      draw();
      if (typed === target) finish();
    });

    input.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') { e.preventDefault(); input.blur(); surface.blur(); return; }
      if (e.key === 'Enter' && !e.ctrlKey && !e.metaKey) {
        // let the textarea insert \n only when the target expects one
        var i = Array.from(input.value).length;
        if (chars[i] !== '\n') e.preventDefault();
      }
      if (e.key === 'Tab') { /* allow focus escape */ }
    });

    function metrics() {
      var arr = Array.from(typed);
      var correct = 0;
      for (var i = 0; i < arr.length && i < chars.length; i++) if (arr[i] === chars[i]) correct += 1;
      var attempted = Math.max(arr.length, 1);
      var firstErrs = Object.keys(firstWrong).length;
      var acc = arr.length ? Math.max(0, (arr.length - firstErrs) / arr.length) : 1;
      var mins = started ? (performance.now() - started) / 60000 : 0;
      var wpm = mins > 0.002 ? Math.round((correct / 5) / mins) : 0;
      return { correct: correct, acc: acc, wpm: wpm, attempted: attempted };
    }

    function draw() {
      var arr = Array.from(typed);
      var m = metrics();

      stats.innerHTML = '';
      [['wpm', m.wpm, 'wpm', m.wpm >= pass.wpm],
       ['acc', Math.round(m.acc * 100) + '%', 'accuracy', m.acc >= pass.acc],
       ['prog', Math.round((arr.length / chars.length) * 100) + '%', 'progress', null],
       ['goal', pass.wpm + ' wpm · ' + Math.round(pass.acc * 100) + '%', 'to pass', null]
      ].forEach(function (s) {
        stats.appendChild(h('div', {
          class: 'stat' + (s[3] === true ? ' good' : s[3] === false && started ? ' bad' : '')
        }, [h('b', {}, [String(s[1])]), h('span', {}, [s[2]])]));
      });

      var frag = document.createDocumentFragment();
      chars.forEach(function (ch, i) {
        var cls = 'ch ';
        if (i < arr.length) cls += (arr[i] === ch ? 'ok' : 'err');
        else cls += 'pending';
        if (i === arr.length) cls += ' cur';
        if (ch === ' ' && cls.indexOf('err') !== -1) cls += ' space';
        if (ch === '\n') cls += ' nl';
        frag.appendChild(h('span', { class: cls }, [ch === '\n' ? '\n' : ch]));
      });
      if (arr.length > chars.length) {
        frag.appendChild(h('span', { class: 'ch err' }, [arr.slice(chars.length).join('')]));
      }
      // rebuild without destroying the input
      Array.prototype.slice.call(surface.childNodes).forEach(function (n) {
        if (n !== input) surface.removeChild(n);
      });
      surface.appendChild(frag);

      var nextCh = chars[arr.length];
      drawKeyboard(nextCh, errKeys);
      hint.innerHTML = nextCh === undefined ? 'Done.'
        : 'next: <b>' + esc(nextCh === '\n' ? '↵' : nextCh === ' ' ? '␣' : nextCh) + '</b> — ' + esc(keyHint(nextCh));
    }

    function drawKeyboard(nextCh, errs) {
      var k = nextCh === undefined ? null : keyFor(nextCh);
      kbmap.innerHTML = '';
      KB.forEach(function (row, r) {
        var el = h('div', { class: 'kbrow' });
        row.forEach(function (key, c) {
          var hot = (errs[key[0]] || 0) + (errs[key[1]] || 0) + (errs[key[2]] || 0);
          var isNext = k && k.r === r && k.c === c;
          el.appendChild(h('div', {
            class: 'key ' + key[3] + (isNext ? ' next' : hot > 1 ? ' hot' : '')
          }, [key[0], key[2] ? h('span', { class: 'sub' }, [key[2]]) : null]));
        });
        kbmap.appendChild(el);
      });
      var last = h('div', { class: 'kbrow' }, [
        h('div', { class: 'key w20' }, ['Alt']),
        h('div', { class: 'key wsp' + (nextCh === ' ' ? ' next' : '') }, ['space']),
        h('div', { class: 'key w20' + (k && k.mod === 'AltGr' ? ' next' : '') }, ['AltGr'])
      ]);
      kbmap.appendChild(last);
    }

    function finish() {
      finished = true;
      if (timer) clearInterval(timer);
      var m = metrics();
      surface.classList.add('done');
      var passed = m.wpm >= pass.wpm && m.acc >= pass.acc;
      banner.innerHTML = '';
      banner.appendChild(h('div', { class: 'banner ' + (passed ? 'ok' : 'bad') }, [
        passed
          ? '✓ ' + m.wpm + ' wpm at ' + Math.round(m.acc * 100) + '% — passed.'
          : '· ' + m.wpm + ' wpm at ' + Math.round(m.acc * 100) + '% — target is ' + pass.wpm +
            ' wpm at ' + Math.round(pass.acc * 100) + '%. Restart and go slower; accuracy first.'
      ]));
      var worst = Object.keys(errKeys).sort(function (a, b) { return errKeys[b] - errKeys[a]; }).slice(0, 8);
      if (worst.length) {
        banner.appendChild(h('div', { class: 'muted' }, ['Most-missed keys this run:']));
        banner.appendChild(h('div', { class: 'heat' }, worst.map(function (ch) {
          return h('span', { class: 'hk' }, [(ch === ' ' ? '␣' : ch === '\n' ? '↵' : ch) + ' ×' + errKeys[ch]]);
        })));
      }
      save();
      if (passed) onDone({ wpm: m.wpm, acc: Math.round(m.acc * 100) / 100 });
      else markTried('typing', ls.id);
    }

    draw();
    setTimeout(function () { input.focus(); }, 40);
    teardown = function () { if (timer) clearInterval(timer); };
    window.__reset = reset;
  }

  /* ------------------------------------------------------- vim UI */
  function domKeyToVim(e) {
    if (e.key === 'Escape') return '\x1b';
    if (e.key === 'Enter') return '\r';
    if (e.key === 'Backspace') return '\x08';
    if (e.key === 'Tab') return '\t';
    if (e.ctrlKey && e.key.length === 1) {
      var code = e.key.toUpperCase().charCodeAt(0);
      if (code >= 64 && code <= 95) return String.fromCharCode(code - 64);
      return null;
    }
    if (e.altKey || e.metaKey) return null;
    if (e.key.length === 1) return e.key;
    return null;
  }

  function renderBuffer(el, v, solved) {
    el.innerHTML = '';
    el.className = 'buffer' + (solved ? ' solved' : '');
    var vr = null;
    if (v.visualStart) vr = v.visualRange();
    v.lines.forEach(function (line, r) {
      var num = r === v.row ? String(r + 1) : String(Math.abs(r - v.row));
      var text = h('span', { class: 'btext' });
      var chars = line.length ? Array.from(line) : [''];
      if (!line.length) {
        text.appendChild(r === v.row && v.col === 0
          ? h('span', { class: 'cursor' + (v.mode === 'insert' ? ' insert' : '') }, [' '])
          : document.createTextNode(' '));
      } else {
        chars.forEach(function (ch, c) {
          var inSel = false;
          if (vr) {
            if (v.mode === 'vline') inSel = r >= vr[0][0] && r <= vr[1][0];
            else if (v.mode === 'vblock') {
              var b = v._vblockCols();
              inSel = r >= b[0] && r <= b[1] && c >= b[2] && c <= b[3];
            } else {
              var idx = v.toIndex(r, c);
              inSel = idx >= v.toIndex(vr[0][0], vr[0][1]) && idx <= v.toIndex(vr[1][0], vr[1][1]);
            }
          }
          var isCur = r === v.row && c === v.col;
          var cls = isCur ? 'cursor' + (v.mode === 'insert' ? ' insert' : '') : (inSel ? 'sel' : '');
          if (cls) text.appendChild(h('span', { class: cls }, [ch]));
          else text.appendChild(document.createTextNode(ch));
        });
        if (r === v.row && v.col >= line.length) {
          text.appendChild(h('span', { class: 'cursor' + (v.mode === 'insert' ? ' insert' : '') }, [' ']));
        }
      }
      el.appendChild(h('div', { class: 'bline' + (r === v.row ? ' at' : '') }, [
        h('span', { class: 'bnum' }, [num]), text
      ]));
    });
  }

  function vimLesson(host, ls, onDone, nextBtn, isCombo) {
    var v, solved = false, revealed = false;
    var bufEl = h('div', { class: 'buffer', tabindex: '0', role: 'application', 'aria-label': 'Vim buffer — press Tab to leave' });
    var status = h('div', { class: 'vim-status' });
    var goalEl = h('div', { class: 'goal-lines' });
    var banner = h('div', {});

    var goalPanel = h('div', { class: 'panel' }, [
      h('div', { class: 'tagline' }, [ls.kind === 'move' ? 'Target cursor position' : 'Target buffer']),
      goalEl
    ]);

    host.appendChild(h('div', { class: 'vim-wrap' }, [
      h('div', {}, [
        h('div', { class: 'panel', style: 'margin-top:0' }, [
          h('div', { class: 'tagline' }, ['Your buffer']), bufEl, status
        ])
      ]),
      h('div', {}, [goalPanel])
    ]));
    host.appendChild(banner);

    var hintBox = h('div', { class: 'hintbox', hidden: true, html: md(ls.hint || 'No hint for this one.') });
    host.appendChild(hintBox);

    var bar = h('div', { class: 'toolbar' }, [
      h('button', { class: 'btn', onclick: reset }, ['Reset ', h('span', { class: 'kbd' }, ['Alt R'])]),
      h('button', { class: 'btn', onclick: function () { hintBox.hidden = !hintBox.hidden; } }, ['Hint ', h('span', { class: 'kbd' }, ['Alt H'])]),
      h('button', { class: 'btn', onclick: replay }, ['Show me ', h('span', { class: 'kbd' }, ['Alt S'])]),
      nextBtn
    ]);
    host.appendChild(bar);
    host.appendChild(h('p', { class: 'muted', style: 'margin-top:10px' }, [
      'Click the buffer (or press ', h('kbd', {}, ['Enter']), ' on it) to start typing. ',
      'Every key goes to Vim — including ', h('kbd', {}, ['Esc']), '. Press ',
      h('kbd', {}, ['Tab']), ' in Normal mode to leave the buffer.'
    ]));

    function drawGoal() {
      goalEl.innerHTML = '';
      if (ls.kind === 'move') {
        ls.start.lines.forEach(function (line, r) {
          var row = h('div', {});
          Array.from(line.length ? line : ' ').forEach(function (ch, c) {
            var isT = ls.goal.cursor && r === ls.goal.cursor[0] && c === ls.goal.cursor[1];
            row.appendChild(isT ? h('span', { class: 'diff', style: 'outline:2px solid var(--ok)' }, [ch]) : document.createTextNode(ch));
          });
          goalEl.appendChild(row);
        });
      } else {
        ls.goal.lines.forEach(function (line, i) {
          var same = v && v.lines[i] === line;
          goalEl.appendChild(h('div', { class: same ? '' : 'diff' }, [line || ' ']));
        });
      }
    }

    function drawStatus() {
      status.innerHTML = '';
      var mode = v.mode === 'vline' ? 'V-LINE' : v.mode === 'vblock' ? 'V-BLOCK' : v.mode.toUpperCase();
      status.appendChild(h('span', { class: 'badge ' + v.mode }, [mode]));
      if (v.mode === 'cmdline') status.appendChild(h('span', {}, [v.cmdtype + v.cmdline + '█']));
      if (v.pending.length) status.appendChild(h('span', { class: 'pendkeys' }, [v.pending.join('')]));
      if (v.recordingReg) status.appendChild(h('span', { class: 'pendkeys' }, ['recording @' + v.recordingReg]));
      status.appendChild(h('span', { class: 'spacer', style: 'flex:1' }));
      status.appendChild(h('span', {}, ['keys ' + v.typed + ' · par ' + ls.par]));
      if (v.message) status.appendChild(h('span', {}, [v.message]));
    }

    function check() {
      var linesOk = v.lines.length === ls.goal.lines.length &&
        v.lines.every(function (l, i) { return l === ls.goal.lines[i]; });
      var curOk = !ls.goal.cursor || (v.row === ls.goal.cursor[0] && v.col === ls.goal.cursor[1]);
      var modeOk = !ls.goal.mode || v.mode === ls.goal.mode;
      return linesOk && curOk && modeOk;
    }

    function draw() {
      renderBuffer(bufEl, v, solved);
      drawStatus();
      drawGoal();
    }

    function reset() {
      v = new window.Vim(ls.start.lines.slice(), ls.start.cursor.slice());
      solved = false; revealed = false;
      banner.innerHTML = '';
      draw();
      bufEl.focus();
    }

    function succeed() {
      if (solved) return;
      solved = true;
      var over = v.typed - ls.par;
      banner.innerHTML = '';
      banner.appendChild(h('div', { class: 'banner ok' }, [
        '✓ Solved in ' + v.typed + ' keys' +
        (over <= 0 ? ' — at or under par (' + ls.par + '). ' : ' — par is ' + ls.par + '. ') +
        (revealed ? 'Reset and do it yourself to lock it in.' : '')
      ]));
      if (!isCombo && !revealed) onDone({ keys: v.typed });
      if (isCombo) host.dispatchEvent(new CustomEvent('combo-vim-done', { bubbles: true }));
      draw();
    }

    bufEl.addEventListener('keydown', function (e) {
      if (e.key === 'Tab' && v.mode === 'normal') return;      // let focus escape
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') return;
      if (e.key === 'F5' || (e.metaKey && !e.ctrlKey)) return;
      var k = domKeyToVim(e);
      if (k === null) return;
      e.preventDefault();
      v.message = '';
      try { v.key(k); } catch (err) { v.message = 'engine: ' + err.message; }
      draw();
      if (check()) succeed();
    });

    bufEl.addEventListener('click', function () { bufEl.focus(); });

    function replay() {
      revealed = true;
      reset();
      revealed = true;
      var keys = window.Vim.parseKeys(ls.solution);
      var i = 0;
      var iv = setInterval(function () {
        if (i >= keys.length) {
          clearInterval(iv);
          if (check()) succeed();
          return;
        }
        v.key(keys[i]); i += 1;
        draw();
      }, 220);
      teardown = function () { clearInterval(iv); };
    }

    reset();
    window.__reset = reset;
    window.__hint = function () { hintBox.hidden = !hintBox.hidden; };
    window.__show = replay;
    setTimeout(function () { bufEl.focus(); }, 40);
  }

  /* ------------------------------------------------------ quiz UI */
  function quizLesson(host, ls, onDone, nextBtn, isCombo) {
    var answered = false;
    var panel = h('div', { class: 'panel' });
    panel.appendChild(h('div', { class: 'prose', html: md(ls.question) }));
    var choices = h('div', { class: 'choices' });
    var why = h('div', {});

    ls.options.forEach(function (opt, i) {
      var b = h('button', {
        class: 'choice', 'data-nav': '1',
        onclick: function () { pick(i, b); }
      }, [h('span', { class: 'n' }, [String(i + 1)]), h('span', { html: md(opt).replace(/^<p>|<\/p>$/g, '') })]);
      choices.appendChild(b);
    });
    panel.appendChild(choices);
    panel.appendChild(why);
    host.appendChild(panel);
    host.appendChild(h('div', { class: 'toolbar' }, [nextBtn]));

    function pick(i, btn) {
      if (answered) return;
      answered = true;
      var right = i === ls.answer;
      btn.classList.add(right ? 'right' : 'wrong');
      Array.prototype.forEach.call(choices.children, function (c, j) {
        c.disabled = true;
        if (j === ls.answer) c.classList.add('right');
      });
      why.innerHTML = '';
      why.appendChild(h('div', { class: 'why' }, [
        h('b', {}, [right ? 'Correct. ' : 'Not quite. ']),
        h('span', { html: md(ls.why).replace(/^<p>|<\/p>$/g, '') })
      ]));
      if (isCombo) host.dispatchEvent(new CustomEvent('combo-quiz-done', { bubbles: true, detail: right }));
      else if (right) onDone({});
      else markTried(view.track, ls.id);
    }

    window.__pick = function (n) {
      var b = choices.children[n];
      if (b && !answered) pick(n, b);
    };
  }

  /* ---------------------------------------------------- output UI */
  function outputLesson(host, ls, onDone, nextBtn) {
    var panel = h('div', { class: 'panel' });
    panel.appendChild(h('div', { class: 'tagline' }, ['What does this print?']));
    panel.appendChild(h('pre', { class: 'prose', style: 'margin-top:8px' }, [h('code', { text: ls.code })]));
    var ta = h('textarea', {
      class: 'editor', style: 'min-height:110px', placeholder: 'Type the exact output, one line per printed line…',
      spellcheck: 'false', 'aria-label': 'Expected output'
    });
    panel.appendChild(h('div', { class: 'editor-wrap', style: 'margin-top:12px' }, [
      h('div', { class: 'editor-bar' }, ['your answer']), ta
    ]));
    var res = h('div', {});
    panel.appendChild(res);
    host.appendChild(panel);

    var checkBtn = h('button', { class: 'btn primary', onclick: check }, ['Check ', h('span', { class: 'kbd' }, ['Ctrl ↵'])]);
    var revealBtn = h('button', { class: 'btn', onclick: reveal }, ['Reveal ', h('span', { class: 'kbd' }, ['Alt S'])]);
    host.appendChild(h('div', { class: 'toolbar' }, [checkBtn, revealBtn, nextBtn]));

    function norm(s) { return s.replace(/\r/g, '').replace(/[ \t]+$/gm, '').replace(/\n+$/, ''); }

    function check() {
      var right = norm(ta.value) === norm(ls.answer);
      res.innerHTML = '';
      res.appendChild(h('div', { class: 'banner ' + (right ? 'ok' : 'bad') }, [right ? '✓ Exactly right.' : '· Not the actual output.']));
      if (!right) {
        res.appendChild(h('div', { class: 'output' }, ['actual:\n' + ls.answer]));
      }
      res.appendChild(h('div', { class: 'why' }, [h('span', { html: md(ls.why).replace(/^<p>|<\/p>$/g, '') })]));
      if (right) onDone({}); else markTried('python', ls.id);
    }

    function reveal() {
      ta.value = ls.answer;
      check();
    }

    window.__run = check;
    window.__show = reveal;
    setTimeout(function () { ta.focus(); }, 40);
  }

  /* ------------------------------------------------------ code UI */
  var pyodide = null, pyLoading = null;

  /* Pyodide is loaded lazily and from a CDN. Sources are tried in order, and
     `vendor/pyodide/` first so a fully offline copy can be dropped in (see
     README: "Running Python offline"). */
  var PYODIDE_SOURCES = [
    'vendor/pyodide/',
    'https://cdn.jsdelivr.net/npm/pyodide@0.26.4/',
    'https://cdn.jsdelivr.net/pyodide/v0.26.4/full/'
  ];

  function loadPyodide() {
    if (pyodide) return Promise.resolve(pyodide);
    if (pyLoading) return pyLoading;

    function attempt(i) {
      if (i >= PYODIDE_SOURCES.length) return Promise.reject(new Error('no Python runtime available'));
      var base = PYODIDE_SOURCES[i];
      return new Promise(function (resolve, reject) {
        var tag = document.createElement('script');
        tag.src = base + 'pyodide.js';
        tag.onload = function () {
          if (!window.loadPyodide) { reject(new Error('bad bundle')); return; }
          window.loadPyodide({ indexURL: base }).then(resolve, reject);
        };
        tag.onerror = function () { reject(new Error('unreachable: ' + base)); };
        document.head.appendChild(tag);
      }).catch(function () { return attempt(i + 1); });
    }

    pyLoading = attempt(0).then(function (py) { pyodide = py; return py; });
    return pyLoading;
  }

  function codeLesson(host, ls, onDone, nextBtn) {
    var panel = h('div', { class: 'panel' });
    panel.appendChild(h('div', { class: 'prose', html: md(ls.prompt) }));

    var ta = h('textarea', { class: 'editor', spellcheck: 'false', 'aria-label': 'Python editor' });
    ta.value = ls.starter;
    var vimToggle = h('input', { type: 'checkbox', id: 'vimmode' });
    var vimBadge = h('span', { class: 'badge normal', hidden: true }, ['NORMAL']);

    panel.appendChild(h('div', { class: 'editor-wrap', style: 'margin-top:12px' }, [
      h('div', { class: 'editor-bar' }, [
        'python',
        h('span', { style: 'flex:1' }),
        h('label', { for: 'vimmode' }, [vimToggle, 'Vim keys']),
        vimBadge
      ]),
      ta
    ]));

    panel.appendChild(h('details', { style: 'margin-top:12px' }, [
      h('summary', { class: 'muted', style: 'cursor:pointer' }, ['Show the tests this must pass']),
      h('pre', { class: 'prose' }, [h('code', { text: ls.tests })])
    ]));

    var out = h('div', {});
    panel.appendChild(out);
    host.appendChild(panel);

    if (ls.hint) host.appendChild(h('div', { class: 'hintbox', hidden: true, html: md(ls.hint) }));
    var hintBox = host.querySelector('.hintbox');
    if (ls.vimtip) host.appendChild(h('div', { class: 'vimtip', html: '⌨ ' + md(ls.vimtip).replace(/^<p>|<\/p>$/g, '') }));

    var runBtn = h('button', { class: 'btn primary', onclick: run }, ['Run tests ', h('span', { class: 'kbd' }, ['Ctrl ↵'])]);
    host.appendChild(h('div', { class: 'toolbar' }, [
      runBtn,
      ls.hint ? h('button', { class: 'btn', onclick: function () { hintBox.hidden = !hintBox.hidden; } }, ['Hint ', h('span', { class: 'kbd' }, ['Alt H'])]) : null,
      h('button', { class: 'btn', onclick: function () { ta.value = ls.solution; ta.focus(); } }, ['Show solution ', h('span', { class: 'kbd' }, ['Alt S'])]),
      h('button', { class: 'btn', onclick: function () { ta.value = ls.starter; ta.focus(); } }, ['Reset ', h('span', { class: 'kbd' }, ['Alt R'])]),
      nextBtn
    ]));

    /* Tab inserts four spaces; Vim mode routes keys through the same engine
       that powers the Neovim track. */
    var vim = null;
    vimToggle.addEventListener('change', function () {
      if (vimToggle.checked) {
        vim = new window.Vim(ta.value.split('\n'), [0, 0]);
        vimBadge.hidden = false;
        syncFromVim();
      } else { vim = null; vimBadge.hidden = true; }
      ta.focus();
    });

    function syncFromVim() {
      ta.value = vim.lines.join('\n');
      vimBadge.textContent = (vim.mode === 'vline' ? 'V-LINE' : vim.mode === 'vblock' ? 'V-BLOCK' : vim.mode.toUpperCase()) +
        (vim.pending.length ? '  ' + vim.pending.join('') : '') +
        (vim.mode === 'cmdline' ? '  ' + vim.cmdtype + vim.cmdline : '');
      vimBadge.className = 'badge ' + vim.mode;
      var pos = 0;
      for (var i = 0; i < vim.row; i++) pos += vim.lines[i].length + 1;
      pos += vim.col;
      ta.setSelectionRange(pos, pos + (vim.mode === 'insert' ? 0 : 1));
    }

    ta.addEventListener('keydown', function (e) {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); run(); return; }
      if (vim) {
        if (e.key === 'Tab' && vim.mode === 'normal') return;
        var k = domKeyToVim(e);
        if (k === null) return;
        e.preventDefault();
        vim.key(k);
        syncFromVim();
        return;
      }
      if (e.key === 'Tab') {
        e.preventDefault();
        var s = ta.selectionStart, en = ta.selectionEnd;
        ta.value = ta.value.slice(0, s) + '    ' + ta.value.slice(en);
        ta.selectionStart = ta.selectionEnd = s + 4;
      }
    });
    ta.addEventListener('click', function () { if (vim) syncFromVim(); });

    function show(cls, text) {
      out.innerHTML = '';
      out.appendChild(h('div', { class: 'output ' + cls, text: text }));
    }

    function run() {
      var source = vim ? vim.lines.join('\n') : ta.value;
      show('', 'starting the Python runtime…');
      loadPyodide().then(function (py) {
        var prog = 'import sys, io\n_buf = io.StringIO()\n_old = sys.stdout\nsys.stdout = _buf\ntry:\n' +
          indent(source) + '\n' + indent(ls.tests) + '\n' +
          '    _res = "PASS"\nexcept AssertionError as _e:\n    _res = "FAIL: " + (str(_e) or "an assertion failed")\n' +
          'except Exception as _e:\n    _res = type(_e).__name__ + ": " + str(_e)\n' +
          'finally:\n    sys.stdout = _old\n_out = _buf.getvalue()\n(_res, _out)';
        var r;
        try { r = py.runPython(prog); }
        catch (err) { show('bad', String(err.message || err).split('\n').slice(-6).join('\n')); return; }
        var res = r.get(0), stdout = r.get(1);
        r.destroy && r.destroy();
        if (res === 'PASS') {
          out.innerHTML = '';
          out.appendChild(h('div', { class: 'banner ok' }, ['✓ All tests passed.']));
          if (stdout) out.appendChild(h('div', { class: 'output' }, [stdout]));
          onDone({});
        } else {
          out.innerHTML = '';
          out.appendChild(h('div', { class: 'output bad', text: res + (stdout ? '\n\n--- stdout ---\n' + stdout : '') }));
          markTried('python', ls.id);
        }
      }, function () {
        out.innerHTML = '';
        out.appendChild(h('div', { class: 'banner info' }, [
          'The in-browser Python runtime is not reachable (offline, or the CDN is blocked). ' +
          'The CLI version runs on your own python3 and has no such problem:'
        ]));
        out.appendChild(h('div', { class: 'output' }, ['triada py ' + ls.id]));
        out.appendChild(h('div', { class: 'toolbar' }, [
          h('button', {
            class: 'btn',
            onclick: function () { onDone({}); flash('Marked as done.'); }
          }, ['I solved it — mark as done']),
          h('button', {
            class: 'btn',
            onclick: function () {
              var blob = source + '\n\n' + ls.tests + '\nprint("all tests passed")\n';
              navigator.clipboard && navigator.clipboard.writeText(blob);
              flash('Code + tests copied — paste into a python3 file.');
            }
          }, ['Copy code + tests'])
        ]));
      });
    }

    function indent(src) {
      return src.split('\n').map(function (l) { return '    ' + l; }).join('\n');
    }

    window.__run = run;
    window.__reset = function () { ta.value = ls.starter; };
    window.__hint = function () { if (hintBox) hintBox.hidden = !hintBox.hidden; };
    window.__show = function () { ta.value = ls.solution; };
    setTimeout(function () { ta.focus(); }, 40);
  }

  /* ====================================================== COMBOS  */
  function comboUnlocked(cb) {
    return TRACKS.every(function (t) { return progress[t].level >= cb.needs[t]; });
  }

  function viewCombos() {
    app.appendChild(h('h1', {}, ['Combos']));
    app.appendChild(h('p', { class: 'lede' }, [
      'One task, all three skills: type the snippet, make the edit in Vim, then answer for why. ' +
      'Combos are optional and never block a track — they unlock when every track has reached the level they need.'
    ]));
    var wrap = h('div', { class: 'levels' });
    C.combos.combos.forEach(function (cb) {
      var open = comboUnlocked(cb);
      var done = !!progress.combos[cb.id];
      wrap.appendChild(h('div', { class: 'level' + (open ? '' : ' locked') + (done ? ' done' : '') }, [
        h('button', {
          class: 'level-head', 'data-nav': '1',
          onclick: function () {
            if (!open) {
              flash('Needs typing L' + cb.needs.typing + ', Neovim L' + cb.needs.nvim + ', Python L' + cb.needs.python + '.');
              return;
            }
            go({ name: 'combo', comboId: cb.id });
          }
        }, [
          h('span', { class: 'level-num' }, [open ? (done ? '✓' : String(cb.n)) : '🔒']),
          h('span', { class: 'level-title' }, [h('b', {}, [cb.title]), h('span', {}, [cb.brief])]),
          h('span', { class: 'level-count' }, [
            'T' + cb.needs.typing + ' · V' + cb.needs.nvim + ' · P' + cb.needs.python
          ])
        ])
      ]));
    });
    app.appendChild(wrap);
    initNav();
  }

  function viewCombo() {
    var cb = C.combos.combos.filter(function (x) { return x.id === view.comboId; })[0];
    if (!cb) { go({ name: 'combos' }); return; }
    var stage = { typing: false, vim: false, quiz: false };

    app.appendChild(h('div', { class: 'crumb' }, [
      h('button', { onclick: function () { go({ name: 'combos' }); } }, ['Combos']), ' / ' + cb.title
    ]));
    app.appendChild(h('h1', { style: 'margin-top:6px' }, [cb.title]));
    app.appendChild(h('p', { class: 'lede' }, [cb.brief]));

    var progressLine = h('p', { class: 'muted' });
    app.appendChild(progressLine);

    function tick() {
      progressLine.textContent =
        (stage.typing ? '✓' : '·') + ' type   ' +
        (stage.vim ? '✓' : '·') + ' edit   ' +
        (stage.quiz ? '✓' : '·') + ' explain';
      if (stage.typing && stage.vim && stage.quiz && !progress.combos[cb.id]) {
        progress.combos[cb.id] = { done: true };
        save();
        app.appendChild(h('div', { class: 'banner ok' }, ['✓ Combo complete.']));
      }
    }

    app.appendChild(h('h2', {}, ['1 · Type it']));
    var tHost = h('div', {});
    app.appendChild(tHost);
    typingLesson(tHost, { id: cb.id + '-t', content: cb.typing.content,
      pass: { wpm: 20 + cb.n * 2, acc: 0.95 } },
      function () { stage.typing = true; tick(); },
      h('span', {}));

    app.appendChild(h('h2', {}, ['2 · Edit it']));
    var vHost = h('div', {});
    app.appendChild(vHost);
    vHost.addEventListener('combo-vim-done', function () { stage.vim = true; tick(); });
    vimLesson(vHost, {
      id: cb.id + '-v', kind: 'drill', start: cb.vim.start, goal: cb.vim.goal,
      solution: cb.vim.solution, par: cb.vim.par, hint: cb.vim.hint
    }, function () {}, h('span', {}), true);

    app.appendChild(h('h2', {}, ['3 · Explain it']));
    var qHost = h('div', {});
    app.appendChild(qHost);
    qHost.addEventListener('combo-quiz-done', function (e) { if (e.detail) { stage.quiz = true; tick(); } });
    quizLesson(qHost, {
      id: cb.id + '-q', question: cb.python.question, options: cb.python.options,
      answer: cb.python.answer, why: cb.python.why
    }, function () {}, h('span', {}), true);

    tick();
  }

  /* ======================================================= STATS  */
  function viewStats() {
    app.appendChild(h('h1', {}, ['Progress']));
    var grid = h('div', { class: 'grid' });
    TRACKS.forEach(function (t) {
      var s = trackStats(t);
      var best = { wpm: 0, keysOver: 0 };
      Object.keys(progress[t].lessons).forEach(function (id) {
        var b = progress[t].lessons[id].best || {};
        if (b.wpm) best.wpm = Math.max(best.wpm, b.wpm);
      });
      grid.appendChild(h('div', { class: 'card', style: 'cursor:default' }, [
        h('div', { class: 'tagline', style: 'color:var(--' + t + ')' }, [C[t].title]),
        h('h3', {}, [Math.round(s.pct * 100) + '%']),
        h('div', { class: 'bar ' + t }, [h('i', { style: 'width:' + Math.round(s.pct * 100) + '%' })]),
        h('div', { class: 'meta' }, [
          h('span', {}, [s.done + '/' + s.total + ' lessons']),
          h('span', {}, [t === 'typing' && best.wpm ? 'best ' + best.wpm + ' wpm' : 'level ' + s.level])
        ])
      ]));
    });
    app.appendChild(grid);

    var keys = Object.keys(progress.keyStats).sort(function (a, b) { return progress.keyStats[b] - progress.keyStats[a]; });
    app.appendChild(h('h2', {}, ['Keys you miss most']));
    if (!keys.length) app.appendChild(h('p', { class: 'muted' }, ['Nothing recorded yet — do a typing lesson.']));
    else {
      app.appendChild(h('div', { class: 'heat' }, keys.slice(0, 24).map(function (ch) {
        return h('span', { class: 'hk' }, [(ch === ' ' ? '␣' : ch === '\n' ? '↵' : ch) + ' ×' + progress.keyStats[ch]]);
      })));
      app.appendChild(h('p', { class: 'muted', style: 'margin-top:10px' }, [
        'Each of these has a home in the curriculum — check which typing level introduces it and redo that level.'
      ]));
    }

    app.appendChild(h('h2', {}, ['Your data']));
    app.appendChild(h('p', { class: 'muted' }, [
      'Progress lives in this browser only. Export it to move it to another machine, or to share it with the CLI ' +
      '(the CLI reads the same format from ~/.triada/progress.json).'
    ]));
    app.appendChild(h('div', { class: 'toolbar' }, [
      h('button', { class: 'btn', onclick: exportProgress }, ['Export JSON']),
      h('button', { class: 'btn', onclick: importProgress }, ['Import JSON']),
      h('button', { class: 'btn', onclick: resetProgress }, ['Reset everything'])
    ]));
  }

  function exportProgress() {
    var text = JSON.stringify(progress, null, 1);
    openDialog('Export progress', [
      h('p', { class: 'muted' }, ['Copy this, or save it as ~/.triada/progress.json to continue in the CLI.']),
      h('textarea', { class: 'editor', style: 'min-height:280px;border:1px solid var(--line);border-radius:10px', text: text, readonly: true })
    ]);
    var ta = document.querySelector('#dlg textarea');
    ta.focus(); ta.select();
  }

  function importProgress() {
    var ta = h('textarea', { class: 'editor', style: 'min-height:220px;border:1px solid var(--line);border-radius:10px', placeholder: 'Paste an exported progress JSON…' });
    openDialog('Import progress', [
      ta,
      h('div', { class: 'toolbar' }, [h('button', {
        class: 'btn primary', onclick: function () {
          try {
            var p = JSON.parse(ta.value);
            localStorage.setItem(STORE_KEY, JSON.stringify(p));
            progress = load();
            TRACKS.forEach(recomputeLevel);
            document.getElementById('dlg').close();
            go({ name: 'stats' });
            flash('Progress imported.');
          } catch (e) { flash('That is not valid JSON.'); }
        }
      }, ['Import'])])
    ]);
  }

  function resetProgress() {
    openDialog('Reset everything?', [
      h('p', {}, ['This clears every lesson, score and unlocked level in this browser. It cannot be undone.']),
      h('div', { class: 'toolbar' }, [
        h('button', {
          class: 'btn primary', onclick: function () {
            progress = blankProgress(); save();
            document.getElementById('dlg').close();
            go({ name: 'home' });
          }
        }, ['Yes, reset']),
        h('button', { class: 'btn', onclick: function () { document.getElementById('dlg').close(); } }, ['Cancel'])
      ])
    ]);
  }

  /* ======================================================= chrome  */
  function openDialog(title, nodes) {
    var body = document.getElementById('dlg-body');
    body.innerHTML = '';
    body.appendChild(h('h2', { style: 'margin-top:0' }, [title]));
    nodes.forEach(function (n) { body.appendChild(n); });
    document.getElementById('dlg').showModal();
  }

  function showHelp() {
    var rows = [
      ['1 2 3', 'switch to typing / Neovim / Python'],
      ['g h', 'home'], ['c', 'combos'], ['s', 'stats'],
      ['j k  ↓ ↑', 'move through a list'],
      ['Enter', 'open the selected item'],
      ['Esc / Backspace', 'go back one level'],
      ['Ctrl Enter', 'run / check / next lesson'],
      ['Alt R', 'restart the exercise'],
      ['Alt H', 'toggle the hint'],
      ['Alt S', 'show the solution'],
      ['1–4 (in a quiz)', 'pick an answer'],
      ['Tab', 'leave the Vim buffer / move focus'],
      ['?', 'this list']
    ];
    openDialog('Keyboard', [
      h('p', { class: 'muted' }, ['Everything here also works with the mouse. Inside a Vim buffer every key goes to Vim — press Tab in Normal mode to get out.']),
      h('div', { class: 'help-grid' }, rows.map(function (r) {
        return h('div', { class: 'help-row' }, [h('kbd', {}, [r[0]]), h('span', {}, [r[1]])]);
      }))
    ]);
  }

  var flashEl = null;
  function flash(msg) {
    if (flashEl) flashEl.remove();
    flashEl = h('div', {
      class: 'banner info',
      style: 'position:fixed;left:50%;transform:translateX(-50%);bottom:20px;z-index:50;box-shadow:0 6px 24px rgba(0,0,0,.18);background:var(--bg-elev);border:1px solid var(--line-2)'
    }, [msg]);
    document.body.appendChild(flashEl);
    setTimeout(function () { if (flashEl) { flashEl.remove(); flashEl = null; } }, 3200);
  }

  /* list navigation with j/k and roving focus */
  function initNav() {
    var items = Array.prototype.slice.call(app.querySelectorAll('[data-nav]'));
    items.forEach(function (el, i) { el.tabIndex = 0; el.dataset.navIndex = i; });
  }

  function navMove(delta) {
    var items = Array.prototype.slice.call(app.querySelectorAll('[data-nav]'));
    if (!items.length) return false;
    var cur = items.indexOf(document.activeElement);
    var next = cur === -1 ? (delta > 0 ? 0 : items.length - 1) : Math.max(0, Math.min(items.length - 1, cur + delta));
    items[next].focus();
    return true;
  }

  function isTyping(e) {
    var t = e.target;
    return t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable ||
      (t.classList && t.classList.contains('buffer')));
  }

  document.addEventListener('keydown', function (e) {
    var dlg = document.getElementById('dlg');
    if (dlg.open) { if (e.key === 'Escape') dlg.close(); return; }

    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      if (view.name === 'lesson' && window.__run) { e.preventDefault(); window.__run(); return; }
      if (window.__next) { e.preventDefault(); window.__next(); return; }
    }
    if (e.altKey && !e.ctrlKey) {
      var k = e.key.toLowerCase();
      if (k === 'r' && window.__reset) { e.preventDefault(); window.__reset(); return; }
      if (k === 'h' && window.__hint) { e.preventDefault(); window.__hint(); return; }
      if (k === 's' && window.__show) { e.preventDefault(); window.__show(); return; }
    }
    if (isTyping(e)) return;
    if (e.ctrlKey || e.metaKey || e.altKey) return;

    if (e.key === '?') { e.preventDefault(); showHelp(); return; }
    if (e.key === 'Escape' || e.key === 'Backspace') {
      e.preventDefault();
      if (view.name === 'lesson') go({ name: 'track', track: view.track });
      else if (view.name === 'combo') go({ name: 'combos' });
      else if (view.name !== 'home') go({ name: 'home' });
      return;
    }
    if (e.key === '1' || e.key === '2' || e.key === '3') {
      if (view.name === 'lesson' && window.__pick) { e.preventDefault(); window.__pick(parseInt(e.key, 10) - 1); return; }
      if (view.name === 'combo' && window.__pick) { e.preventDefault(); window.__pick(parseInt(e.key, 10) - 1); return; }
      e.preventDefault(); go({ name: 'track', track: TRACKS[parseInt(e.key, 10) - 1] }); return;
    }
    if (e.key === '4' && window.__pick) { e.preventDefault(); window.__pick(3); return; }
    if (e.key === 'c') { e.preventDefault(); go({ name: 'combos' }); return; }
    if (e.key === 's') { e.preventDefault(); go({ name: 'stats' }); return; }
    if (e.key === 'h' && lastKey === 'g') { e.preventDefault(); go({ name: 'home' }); lastKey = ''; return; }
    if (e.key === 'j' || e.key === 'ArrowDown') { if (navMove(1)) e.preventDefault(); return; }
    if (e.key === 'k' || e.key === 'ArrowUp') { if (navMove(-1)) e.preventDefault(); return; }
    lastKey = e.key;
  });
  var lastKey = '';

  document.getElementById('brand').onclick = function () { go({ name: 'home' }); };
  document.getElementById('btn-help').onclick = showHelp;
  document.getElementById('btn-data').onclick = function () { go({ name: 'stats' }); };
  document.getElementById('btn-theme').onclick = function () {
    var cur = document.documentElement.getAttribute('data-theme');
    var next = cur === 'dark' ? 'light' : cur === 'light' ? '' : 'dark';
    if (next) document.documentElement.setAttribute('data-theme', next);
    else document.documentElement.removeAttribute('data-theme');
    try { localStorage.setItem('triada.theme', next); } catch (e) { /* ignore */ }
  };
  try {
    var th = localStorage.getItem('triada.theme');
    if (th) document.documentElement.setAttribute('data-theme', th);
  } catch (e) { /* ignore */ }

  render();
})();
