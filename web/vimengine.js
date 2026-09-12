/* Vim emulator — JavaScript port of cli/triada/vimengine.py.
 * Both are exercised by tests/vim_cases.json so they cannot drift.
 * Exposes a global `Vim` (no modules, so the page works from file://). */
(function (root) {
  'use strict';

  var WORD_RE = /[0-9A-Za-z_À-ɏ]/;

  var SPECIALS = {
    '<esc>': '\x1b', '<cr>': '\r', '<enter>': '\r', '<bs>': '\x08',
    '<tab>': '\t', '<space>': ' ', '<lt>': '<', '<gt>': '>', '<del>': '\x7f'
  };

  function parseKeys(s) {
    var out = [], i = 0;
    while (i < s.length) {
      if (s[i] === '<') {
        var j = s.indexOf('>', i);
        if (j !== -1) {
          var tok = s.slice(i, j + 1).toLowerCase();
          if (SPECIALS[tok] !== undefined) { out.push(SPECIALS[tok]); i = j + 1; continue; }
          var m = /^<c-([a-z[])>$/.exec(tok);
          if (m) {
            var ch = m[1];
            out.push(ch === '[' ? '\x1b' : String.fromCharCode(ch.toUpperCase().charCodeAt(0) - 64));
            i = j + 1; continue;
          }
        }
      }
      out.push(s[i]); i += 1;
    }
    return out;
  }

  function charClass(c, big) {
    if (c === ' ' || c === '\t' || c === '\n') return 0;
    if (big) return 1;
    return WORD_RE.test(c) ? 1 : 2;
  }

  function isDigit(c) { return c >= '0' && c <= '9'; }
  function escapeRe(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }
  function leadingWs(s) { var m = /^[ \t]*/.exec(s); return m[0]; }

  function Vim(lines, cursor) {
    this.lines = (lines && lines.length) ? lines.slice() : [''];
    this.row = cursor ? cursor[0] : 0;
    this.col = cursor ? cursor[1] : 0;
    this.mode = 'normal';
    this.pending = [];
    this.registers = {};
    this.marks = {};
    this.undoStack = [];
    this.redoStack = [];
    this.message = '';
    this.cmdline = '';
    this.cmdtype = '';
    this.lastSearch = null;
    this.lastFt = null;
    this.lastChange = null;
    this._recordingChange = null;
    this.recordingReg = null;
    this.recorded = [];
    this.lastMacro = null;
    this.visualStart = null;
    this.desiredCol = 0;
    this.keylog = [];
    this.typed = 0;
    this.written = false;
    this.quit = false;
    this._depth = 0;
    this.failed = false;
    this._blockInsert = null;
    this.lastVisual = null;
    this._opPending = null;
  }

  var P = Vim.prototype;

  P.line = function () { return (this.row >= 0 && this.row < this.lines.length) ? this.lines[this.row] : ''; };
  P.text = function () { return this.lines.join('\n'); };
  P.snapshot = function () { return [this.lines.slice(), this.row, this.col]; };

  P.pushUndo = function () {
    var snap = this.snapshot();
    if (this.undoStack.length) {
      var prev = this.undoStack[this.undoStack.length - 1][0];
      if (prev.length === snap[0].length && prev.every(function (l, i) { return l === snap[0][i]; })) return;
    }
    this.undoStack.push(snap);
    this.redoStack = [];
  };

  P.undo = function () {
    if (!this.undoStack.length) { this.message = 'Already at oldest change'; return; }
    var cur = this.snapshot(), s = this.undoStack.pop();
    this.redoStack.push(cur);
    this.lines = s[0].slice(); this.row = s[1]; this.col = s[2];
    this.clamp();
  };

  P.redo = function () {
    if (!this.redoStack.length) { this.message = 'Already at newest change'; return; }
    var cur = this.snapshot(), s = this.redoStack.pop();
    this.undoStack.push(cur);
    this.lines = s[0].slice(); this.row = s[1]; this.col = s[2];
    this.clamp();
  };

  P.clamp = function () {
    if (!this.lines.length) this.lines = [''];
    this.row = Math.max(0, Math.min(this.row, this.lines.length - 1));
    var visual = this.mode === 'insert' || this.mode === 'visual' || this.mode === 'vline' || this.mode === 'vblock';
    var maxc = this.line().length - (visual ? 0 : 1);
    this.col = Math.max(0, Math.min(this.col, Math.max(0, maxc)));
  };

  P.toIndex = function (row, col) {
    var n = 0;
    for (var i = 0; i < row && i < this.lines.length; i++) n += this.lines[i].length + 1;
    return n + col;
  };

  P.fromIndex = function (idx) {
    idx = Math.max(0, Math.min(idx, this.text().length));
    var r = 0;
    while (r < this.lines.length && idx > this.lines[r].length) { idx -= this.lines[r].length + 1; r += 1; }
    return [Math.min(r, this.lines.length - 1), Math.max(0, idx)];
  };

  P.feed = function (keys) {
    var ks = (typeof keys === 'string') ? parseKeys(keys) : keys;
    for (var i = 0; i < ks.length; i++) this.key(ks[i]);
    return this;
  };

  P.key = function (k) {
    this.keylog.push(k);
    if (this._depth === 0) this.typed += 1;
    if (this.recordingReg !== null && !(k === 'q' && this.mode === 'normal' && !this.pending.length)) this.recorded.push(k);
    if (this._recordingChange !== null) this._recordingChange.push(k);

    if (this.mode === 'insert') this._insertKey(k);
    else if (this.mode === 'replace') this._replaceKey(k);
    else if (this.mode === 'cmdline') this._cmdlineKey(k);
    else this._normalKey(k);
    return this;
  };

  /* ---------------------------------------------------------- insert */
  P._insertKey = function (k) {
    if (k === '\x1b') {
      this.mode = 'normal';
      this._finishBlockInsert();
      this.col = Math.max(0, this.col - 1);
      this._endChange();
      this.clamp();
      return;
    }
    var line = this.line();
    if (k === '\x08') {
      if (this.col > 0) {
        this.lines[this.row] = line.slice(0, this.col - 1) + line.slice(this.col);
        this.col -= 1;
      } else if (this.row > 0) {
        var prev = this.lines[this.row - 1];
        this.col = prev.length;
        this.lines[this.row - 1] = prev + line;
        this.lines.splice(this.row, 1);
        this.row -= 1;
      }
      return;
    }
    if (k === '\r') {
      this.lines[this.row] = line.slice(0, this.col);
      var indent = line.trim() ? leadingWs(line) : '';
      this.lines.splice(this.row + 1, 0, indent + line.slice(this.col));
      this.row += 1; this.col = indent.length;
      return;
    }
    if (k === '\t') {
      this.lines[this.row] = line.slice(0, this.col) + '    ' + line.slice(this.col);
      this.col += 4; return;
    }
    if (k < ' ') return;
    this.lines[this.row] = line.slice(0, this.col) + k + line.slice(this.col);
    this.col += k.length;
  };

  P._finishBlockInsert = function () {
    if (!this._blockInsert) return;
    var r1 = this._blockInsert[0], r2 = this._blockInsert[1], col = this._blockInsert[2], pad = this._blockInsert[3];
    this._blockInsert = null;
    if (this.row !== r1) return;
    var typed = this.lines[r1].slice(col, this.col);
    if (!typed) return;
    for (var r = r1 + 1; r <= r2 && r < this.lines.length; r++) {
      var line = this.lines[r];
      if (line.length < col) {
        if (!pad) continue;
        while (line.length < col) line += ' ';
      }
      this.lines[r] = line.slice(0, col) + typed + line.slice(col);
    }
  };

  P._replaceKey = function (k) {
    if (k === '\x1b') { this.mode = 'normal'; this.col = Math.max(0, this.col - 1); this._endChange(); return; }
    if (k === '\r') { this.row += 1; this.col = 0; if (this.row >= this.lines.length) this.lines.push(''); return; }
    var line = this.line();
    this.lines[this.row] = line.slice(0, this.col) + k + line.slice(this.col + 1);
    this.col += 1;
  };

  /* --------------------------------------------------------- cmdline */
  P._cmdlineKey = function (k) {
    if (k === '\x1b') { this.mode = 'normal'; this.cmdline = ''; this._opPending = null; return; }
    if (k === '\x08') {
      if (this.cmdline) this.cmdline = this.cmdline.slice(0, -1);
      else this.mode = 'normal';
      return;
    }
    if (k === '\r') {
      var cmd = this.cmdline; this.cmdline = ''; this.mode = 'normal';
      if (this.cmdtype === ':') { this._ex(cmd); return; }
      if (this._opPending) {
        var op = this._opPending[0], reg = this._opPending[1], r0 = this._opPending[2], c0 = this._opPending[3];
        this._opPending = null;
        if (cmd) this.lastSearch = [cmd, this.cmdtype];
        var target = this._search(cmd, this.cmdtype, this.toIndex(r0, c0));
        if (!target) { this.failed = true; this.message = 'E486: Pattern not found: ' + cmd; return; }
        var start = [r0, c0], end = target;
        if (this.toIndex(start[0], start[1]) > this.toIndex(end[0], end[1])) { var t = start; start = end; end = t; }
        this._applyOperator(op, start, end, 'excl', reg);
        return;
      }
      this._doSearch(cmd, this.cmdtype);
      return;
    }
    this.cmdline += k;
  };

  P._beginChange = function (keys) { this._recordingChange = keys.slice(); };
  P._endChange = function () {
    if (this._recordingChange !== null) { this.lastChange = this._recordingChange; this._recordingChange = null; }
  };

  /* ---------------------------------------------------------- normal */
  P._normalKey = function (k) {
    if (k === '\x1b') {
      this.pending = [];
      if (this.mode === 'visual' || this.mode === 'vline' || this.mode === 'vblock') {
        this._saveVisual();
        this.mode = 'normal'; this.visualStart = null; this.clamp();
      }
      return;
    }
    this.pending.push(k);
    var status;
    try { status = this._execNormal(this.pending.join('')); }
    catch (e) { status = 'invalid'; }
    if (status === 'done' || status === 'invalid') this.pending = [];
  };

  P._execNormal = function (seq) {
    var i = 0, reg = null, count1 = '';
    for (;;) {
      while (i < seq.length && isDigit(seq[i]) && !(seq[i] === '0' && !count1)) { count1 += seq[i]; i += 1; }
      if (i < seq.length && seq[i] === '"') {
        if (i + 1 >= seq.length) return 'incomplete';
        reg = seq[i + 1]; i += 2; continue;
      }
      break;
    }
    if (i >= seq.length) return 'incomplete';
    var n1 = count1 ? parseInt(count1, 10) : null;
    return this._command(seq.slice(i), n1, reg);
  };

  P._command = function (s, count, reg) {
    var vis = this.mode === 'visual' || this.mode === 'vline' || this.mode === 'vblock';
    var c = s[0], op = null, oprest = '';
    if ('dcy><='.indexOf(c) !== -1) { op = c; oprest = s.slice(1); }
    else if (c === 'g' && s.length >= 2 && 'uU~?'.indexOf(s[1]) !== -1) { op = 'g' + s[1]; oprest = s.slice(2); }
    else if (c === 'g' && s.length === 1) return 'incomplete';

    if (op !== null) {
      if (vis) return this._applyOperatorVisual(op, reg);
      return this._operatorPending(op, oprest, count, reg);
    }
    return this._simple(s, count, reg, vis);
  };

  P._operatorPending = function (op, rest, count1, reg) {
    if (rest === '') return 'incomplete';
    var i = 0, count2 = '';
    while (i < rest.length && isDigit(rest[i]) && !(rest[i] === '0' && !count2)) { count2 += rest[i]; i += 1; }
    if (i >= rest.length) return 'incomplete';
    var motion = rest.slice(i);
    var n = (count1 || 1) * (count2 ? parseInt(count2, 10) : 1);

    if (motion[0] === '/' || motion[0] === '?') {
      this._opPending = [op, reg, this.row, this.col];
      this.mode = 'cmdline';
      this.cmdtype = motion[0];
      this.cmdline = motion.slice(1);
      return 'done';
    }

    var doubled = motion === op[op.length - 1] || (op.length === 2 && motion === op);
    if ('><='.indexOf(op) !== -1 && motion === op) doubled = true;
    if (doubled) {
      var r2 = Math.min(this.lines.length - 1, this.row + n - 1);
      return this._applyOperator(op, [this.row, 0], [r2, 0], 'line', reg);
    }

    if (motion[0] === 'i' || motion[0] === 'a') {
      if (motion.length === 1) return 'incomplete';
      var rng = this.textObject(motion[0], motion[1], n);
      if (!rng) return 'done';
      return this._applyOperator(op, rng[0], rng[1], rng[2], reg);
    }

    var res = this.motion(motion, n, true);
    if (res === 'incomplete') return 'incomplete';
    if (!res) return 'done';
    var target = res[0], kind = res[1];
    var start = [this.row, this.col], end = target;
    if (this.toIndex(start[0], start[1]) > this.toIndex(end[0], end[1])) { var t = start; start = end; end = t; }
    return this._applyOperator(op, start, end, kind, reg);
  };

  /* ------------------------------------------------------- operators */
  P._yankText = function (start, end, kind) {
    if (kind === 'line') return this.lines.slice(start[0], end[0] + 1).join('\n') + '\n';
    var a = this.toIndex(start[0], start[1]), b = this.toIndex(end[0], end[1]);
    if (kind === 'incl') b += 1;
    return this.text().slice(a, b);
  };

  P.setRegister = function (reg, text, kind) {
    if (reg === '_') return;
    if (reg && reg !== reg.toLowerCase()) {
      var key = reg.toLowerCase();
      var old = this.registers[key] || ['', kind];
      this.registers[key] = [old[0] + text, kind];
    } else if (reg) {
      this.registers[reg] = [text, kind];
    } else {
      this.registers['"'] = [text, kind];
      this.registers['0'] = [text, kind];
    }
  };

  P.getRegister = function (reg) { return this.registers[reg || '"'] || ['', 'char']; };

  P.firstNonBlank = function (r) {
    var line = this.lines[r];
    if (!line) return 0;
    return Math.min(leadingWs(line).length, Math.max(0, line.length - 1));
  };

  P._deleteRange = function (start, end, kind) {
    if (kind === 'line') {
      this.lines.splice(start[0], end[0] - start[0] + 1);
      if (!this.lines.length) this.lines = [''];
      this.row = Math.min(start[0], this.lines.length - 1);
      this.col = this.firstNonBlank(this.row);
    } else {
      var a = this.toIndex(start[0], start[1]), b = this.toIndex(end[0], end[1]);
      if (kind === 'incl') b += 1;
      var t = this.text();
      this.lines = (t.slice(0, a) + t.slice(b)).split('\n');
      var p = this.fromIndex(a);
      this.row = p[0]; this.col = p[1];
    }
  };

  P._applyOperator = function (op, start, end, kind, reg) {
    var txt, i, r;
    if (op === 'y') {
      txt = this._yankText(start, end, kind);
      this.setRegister(reg, txt, kind === 'line' ? 'line' : 'char');
      if (reg !== '_') this.registers['"'] = [txt, kind === 'line' ? 'line' : 'char'];
      if (kind === 'line') this.row = start[0];
      else { this.row = start[0]; this.col = start[1]; }
      this.clamp();
      return 'done';
    }

    this.pushUndo();

    if (op === '>' || op === '<') {
      for (r = start[0]; r <= end[0]; r++) {
        if (op === '>') { if (this.lines[r]) this.lines[r] = '    ' + this.lines[r]; }
        else this.lines[r] = this.lines[r].replace(/^ {1,4}/, '');
      }
      this.row = start[0]; this.col = this.firstNonBlank(this.row);
      this._registerDot();
      return 'done';
    }

    if (op === '=') { this.row = start[0]; this.clamp(); return 'done'; }

    if (op === 'gu' || op === 'gU' || op === 'g~') {
      txt = this._yankText(start, end, kind);
      var fn = op === 'gu' ? function (s) { return s.toLowerCase(); }
        : op === 'gU' ? function (s) { return s.toUpperCase(); }
          : function (s) {
            return s.replace(/[a-zA-ZÀ-ɏ]/g, function (ch) {
              return ch === ch.toLowerCase() ? ch.toUpperCase() : ch.toLowerCase();
            });
          };
      var neu = fn(txt);
      if (kind === 'line') {
        var repl = neu.replace(/\n$/, '').split('\n');
        this.lines.splice.apply(this.lines, [start[0], end[0] - start[0] + 1].concat(repl));
        this.row = start[0]; this.col = this.firstNonBlank(start[0]);
      } else {
        var a = this.toIndex(start[0], start[1]), b = this.toIndex(end[0], end[1]);
        if (kind === 'incl') b += 1;
        var t = this.text();
        this.lines = (t.slice(0, a) + neu + t.slice(b)).split('\n');
        this.row = start[0]; this.col = start[1];
      }
      this.clamp();
      this._registerDot();
      return 'done';
    }

    txt = this._yankText(start, end, kind);
    this.setRegister(reg, txt, kind === 'line' ? 'line' : 'char');

    if (op === 'd') {
      this._deleteRange(start, end, kind);
      this.clamp();
      this._registerDot();
      return 'done';
    }

    // c
    if (kind === 'line') {
      var indent = leadingWs(this.lines[start[0]]);
      this.lines.splice(start[0], end[0] - start[0] + 1);
      this.lines.splice(start[0], 0, indent);
      this.row = start[0]; this.col = indent.length;
    } else {
      this._deleteRange(start, end, kind);
    }
    this.mode = 'insert';
    this._beginChange(this.pending);
    return 'done';
  };

  P._registerDot = function () { this.lastChange = this.pending.slice(); };

  /* ---------------------------------------------------------- visual */
  P.visualRange = function () {
    var s = this.visualStart, e = [this.row, this.col];
    if (this.toIndex(s[0], s[1]) > this.toIndex(e[0], e[1])) return [e, s];
    return [s, e];
  };

  P._saveVisual = function () {
    if (this.visualStart !== null) {
      var vr = this.visualRange();
      this.lastVisual = [this.mode, vr[0], vr[1]];
    }
  };

  P._applyOperatorVisual = function (op, reg) {
    this._saveVisual();
    if (this.mode === 'vblock') return this._vblockOp(op, reg);
    var vr = this.visualRange(), s = vr[0], e = vr[1];
    var kind = this.mode === 'vline' ? 'line' : 'incl';
    this.mode = 'normal';
    this.visualStart = null;
    if (op === 'c' && kind === 'line') {
      this.pushUndo();
      var indent = leadingWs(this.lines[s[0]]);
      this.setRegister(reg, this._yankText(s, e, 'line'), 'line');
      this.lines.splice(s[0], e[0] - s[0] + 1);
      this.lines.splice(s[0], 0, indent);
      this.row = s[0]; this.col = indent.length;
      this.mode = 'insert';
      this._beginChange([]);
      return 'done';
    }
    var res = this._applyOperator(op, s, e, kind, reg);
    if (this.mode !== 'insert') this.clamp();
    return res;
  };

  P._vblockCols = function () {
    var s = this.visualStart, e = [this.row, this.col];
    var r1 = Math.min(s[0], e[0]), r2 = Math.max(s[0], e[0]);
    var c1 = Math.min(s[1], e[1]), c2 = Math.max(s[1], e[1]);
    return [r1, r2, c1, c2];
  };

  P._vblockOp = function (op, reg) {
    var b = this._vblockCols(), r1 = b[0], r2 = b[1], c1 = b[2], c2 = b[3], r;
    this.mode = 'normal'; this.visualStart = null;
    var chunks = [];
    for (r = r1; r <= r2; r++) chunks.push(this.lines[r].slice(c1, c2 + 1));
    this.setRegister(reg, chunks.join('\n'), 'block');
    if (op === 'y') { this.row = r1; this.col = c1; this.clamp(); return 'done'; }
    this.pushUndo();
    for (r = r1; r <= r2; r++) this.lines[r] = this.lines[r].slice(0, c1) + this.lines[r].slice(c2 + 1);
    this.row = r1; this.col = c1;
    if (op === 'c') { this.mode = 'insert'; this._blockInsert = [r1, r2, c1, false]; this._beginChange([]); }
    this.clamp();
    return 'done';
  };

  /* ----------------------------------------------------- text objects */
  var PAIRS = {
    '(': ['(', ')'], ')': ['(', ')'], b: ['(', ')'],
    '[': ['[', ']'], ']': ['[', ']'],
    '{': ['{', '}'], '}': ['{', '}'], B: ['{', '}'],
    '<': ['<', '>'], '>': ['<', '>']
  };
  var QUOTES = { '"': 1, "'": 1, '`': 1 };

  P.textObject = function (ia, obj, n) {
    var inner = ia === 'i';
    if (obj === 'w' || obj === 'W') return this._objWord(inner, obj === 'W', n || 1);
    if (PAIRS[obj]) return this._objPair(inner, PAIRS[obj][0], PAIRS[obj][1]);
    if (QUOTES[obj]) return this._objQuote(inner, obj);
    if (obj === 'p') return this._objPara(inner);
    return null;
  };

  P._objWord = function (inner, big, n) {
    var t = this.text(), i = this.toIndex(this.row, this.col);
    if (i >= t.length) return null;
    var cls = charClass(t[i], big), a = i, b = i, k;
    while (a > 0 && t[a - 1] !== '\n' && charClass(t[a - 1], big) === cls) a -= 1;
    while (b + 1 < t.length && t[b + 1] !== '\n' && charClass(t[b + 1], big) === cls) b += 1;
    for (k = 1; k < n; k++) {
      var j = b + 1;
      if (j < t.length && t[j] !== '\n') {
        var cls2 = charClass(t[j], big);
        while (b + 1 < t.length && t[b + 1] !== '\n' && charClass(t[b + 1], big) === cls2) b += 1;
      }
    }
    if (!inner) {
      var e = b, grew = false;
      while (e + 1 < t.length && (t[e + 1] === ' ' || t[e + 1] === '\t')) { e += 1; grew = true; }
      if (grew) b = e;
      else while (a > 0 && (t[a - 1] === ' ' || t[a - 1] === '\t')) a -= 1;
    }
    return [this.fromIndex(a), this.fromIndex(b), 'incl'];
  };

  P._objPair = function (inner, o, c) {
    var t = this.text(), i = this.toIndex(this.row, this.col);
    var depth = 0, a = -1, b = -1, j;
    if (i < t.length && t[i] === o) a = i;
    else {
      j = i;
      while (j >= 0) {
        if (t[j] === c && j !== i) depth += 1;
        else if (t[j] === o) { if (depth === 0) { a = j; break; } depth -= 1; }
        j -= 1;
      }
    }
    if (a < 0) return null;
    depth = 0;
    for (j = a + 1; j < t.length; j++) {
      if (t[j] === o) depth += 1;
      else if (t[j] === c) { if (depth === 0) { b = j; break; } depth -= 1; }
    }
    if (b < 0) return null;
    if (inner) {
      if (a + 1 > b - 1) return [this.fromIndex(a + 1), this.fromIndex(a), 'excl-empty'];
      var head = t.slice(a + 1);
      var nl = head.indexOf('\n');
      var tailStart = t.lastIndexOf('\n', b - 1);
      if (nl !== -1 && !head.slice(0, nl).trim() && tailStart !== -1 && tailStart > a &&
          !t.slice(tailStart + 1, b).trim()) {
        var r1 = this.fromIndex(a + 1 + nl + 1)[0], r2 = this.fromIndex(tailStart)[0];
        if (r1 <= r2) return [[r1, 0], [r2, 0], 'line'];
      }
      return [this.fromIndex(a + 1), this.fromIndex(b - 1), 'incl'];
    }
    return [this.fromIndex(a), this.fromIndex(b), 'incl'];
  };

  P._objQuote = function (inner, q) {
    var line = this.line(), positions = [], i;
    for (i = 0; i < line.length; i++) if (line[i] === q && (i === 0 || line[i - 1] !== '\\')) positions.push(i);
    if (positions.length < 2) return null;
    for (var k = 0; k + 1 < positions.length; k += 2) {
      var a = positions[k], b = positions[k + 1];
      if (this.col <= b) {
        if (inner) {
          if (a + 1 > b - 1) return [[this.row, a + 1], [this.row, a], 'excl-empty'];
          return [[this.row, a + 1], [this.row, b - 1], 'incl'];
        }
        return [[this.row, a], [this.row, b], 'incl'];
      }
    }
    return null;
  };

  P._objPara = function (inner) {
    var self = this;
    var blank = function (i) { return !self.lines[i].trim(); };
    var cur = blank(this.row), a = this.row, b = this.row;
    while (a > 0 && blank(a - 1) === cur) a -= 1;
    while (b + 1 < this.lines.length && blank(b + 1) === cur) b += 1;
    if (!inner) {
      var e = b;
      while (e + 1 < this.lines.length && blank(e + 1) !== cur) e += 1;
      if (e !== b) b = e;
    }
    return [[a, 0], [b, 0], 'line'];
  };

  /* ---------------------------------------------------------- motions */
  P.motion = function (m, n, forOperator) {
    n = n || 1;
    var c = m[0], t = this.text(), idx = this.toIndex(this.row, this.col), i, r, p;

    if (c === 'h') return [[this.row, Math.max(0, this.col - n)], 'excl'];
    if (c === 'l') {
      var lim = forOperator ? this.line().length : Math.max(0, this.line().length - 1);
      return [[this.row, Math.min(lim, this.col + n)], 'excl'];
    }
    if (c === ' ') return [[this.row, Math.min(this.line().length, this.col + n)], 'excl'];
    if (c === 'j' || c === 'k') {
      r = this.row + (c === 'j' ? n : -n);
      if (r < 0 || r > this.lines.length - 1) { this.failed = true; return null; }
      var col = Math.min(Math.max(this.desiredCol, this.col), Math.max(0, this.lines[r].length - 1));
      return [[r, col], 'line'];
    }
    if (c === '+' || c === '\r') { r = Math.min(this.lines.length - 1, this.row + n); return [[r, this.firstNonBlank(r)], 'line']; }
    if (c === '-') { r = Math.max(0, this.row - n); return [[r, this.firstNonBlank(r)], 'line']; }
    if (c === '_') { r = Math.min(this.lines.length - 1, this.row + n - 1); return [[r, this.firstNonBlank(r)], 'line']; }
    if (c === '0') return [[this.row, 0], 'excl'];
    if (c === '^') return [[this.row, this.firstNonBlank(this.row)], 'excl'];
    if (c === '$') {
      r = Math.min(this.lines.length - 1, this.row + n - 1);
      return [[r, Math.max(0, this.lines[r].length - (forOperator ? 0 : 1))], 'incl'];
    }
    if (c === 'G') {
      r = (m === 'G' && n !== 1) ? n - 1 : (n === 1 ? this.lines.length - 1 : n - 1);
      r = Math.max(0, Math.min(r, this.lines.length - 1));
      return [[r, this.firstNonBlank(r)], 'line'];
    }
    if (c === 'H') return [[0, this.firstNonBlank(0)], 'line'];
    if (c === 'L') { r = this.lines.length - 1; return [[r, this.firstNonBlank(r)], 'line']; }
    if (c === 'M') { r = Math.floor(this.lines.length / 2); return [[r, this.firstNonBlank(r)], 'line']; }
    if (c === '|') return [[this.row, Math.max(0, Math.min(n - 1, this.line().length - 1))], 'excl'];
    if (c === 'w' || c === 'W') {
      var big = c === 'W';
      i = idx;
      for (var q = 0; q < n; q++) i = nextWordStart(t, i, big);
      if (forOperator) {
        var r1 = this.fromIndex(i)[0];
        if (r1 > this.row && t[Math.max(0, i - 1)] === '\n') {
          var k2 = i;
          while (k2 > 0 && ' \t\n'.indexOf(t[k2 - 1]) !== -1) k2 -= 1;
          if (k2 > idx) i = k2;
        }
      }
      return [this.fromIndex(i), 'excl'];
    }
    if (c === 'b' || c === 'B') {
      i = idx;
      for (var q2 = 0; q2 < n; q2++) i = prevWordStart(t, i, c === 'B');
      return [this.fromIndex(i), 'excl'];
    }
    if (c === 'e' || c === 'E') {
      i = idx;
      for (var q3 = 0; q3 < n; q3++) i = nextWordEnd(t, i, c === 'E');
      return [this.fromIndex(i), 'incl'];
    }
    if (m === 'ge' || m === 'gE') {
      i = idx;
      for (var q4 = 0; q4 < n; q4++) i = prevWordEnd(t, i);
      return [this.fromIndex(i), 'incl'];
    }
    if ('fFtT'.indexOf(c) !== -1) {
      if (m.length < 2) return 'incomplete';
      this.lastFt = [c, m[1]];
      return this._doFt(c, m[1], n, forOperator, false);
    }
    if (c === ';' || c === ',') {
      if (!this.lastFt) return null;
      var k = this.lastFt[0], target = this.lastFt[1];
      if (c === ',') k = { f: 'F', F: 'f', t: 'T', T: 't' }[k];
      return this._doFt(k, target, n, forOperator, true);
    }
    if (c === '{') return [this._paraMove(-1, n), 'excl'];
    if (c === '}') return [this._paraMove(1, n), 'excl'];
    if (c === '%') return this._matchPair();
    if (c === '`') { if (m.length < 2) return 'incomplete'; p = this.marks[m[1]]; return p ? [p, 'excl'] : null; }
    if (c === "'") { if (m.length < 2) return 'incomplete'; p = this.marks[m[1]]; return p ? [[p[0], this.firstNonBlank(p[0])], 'line'] : null; }
    if (c === 'n' || c === 'N') {
      if (!this.lastSearch) { this.failed = true; return null; }
      var pat = this.lastSearch[0], dir = this.lastSearch[1];
      var d = c === 'n' ? dir : (dir === '/' ? '?' : '/');
      p = this._search(pat, d);
      if (!p) this.failed = true;
      return p ? [p, 'excl'] : null;
    }
    if (c === '*' || c === '#') {
      var word = this._wordUnderCursor();
      if (!word) { this.failed = true; return null; }
      this.lastSearch = ['\\<' + escapeRe(word) + '\\>', c === '*' ? '/' : '?'];
      p = this._search(this.lastSearch[0], this.lastSearch[1]);
      if (!p) this.failed = true;
      return p ? [p, 'excl'] : null;
    }
    if (c === 'g') {
      if (m === 'g') return 'incomplete';
      if (m === 'gg') { r = Math.max(0, Math.min(n - 1, this.lines.length - 1)); return [[r, this.firstNonBlank(r)], 'line']; }
      if (m === 'g_') return [[this.row, Math.max(0, this.line().replace(/\s+$/, '').length - 1)], 'incl'];
      return null;
    }
    return null;
  };

  P._wordUnderCursor = function () {
    var line = this.line(), i = this.col;
    while (i < line.length && !WORD_RE.test(line[i])) i += 1;
    if (i >= line.length) return '';
    var a = i, b = i;
    while (a > 0 && WORD_RE.test(line[a - 1])) a -= 1;
    while (b + 1 < line.length && WORD_RE.test(line[b + 1])) b += 1;
    return line.slice(a, b + 1);
  };

  P._doFt = function (kind, target, n, forOperator, repeat) {
    var line = this.line(), pos = this.col, found, i;
    if (kind === 'f' || kind === 't') {
      for (i = 0; i < n; i++) {
        var start = pos + 1;
        if (kind === 't' && repeat && n === 1) start = pos + 2;
        found = line.indexOf(target, start);
        if (found === -1) { this.failed = true; return null; }
        pos = found;
      }
      if (kind === 't') pos -= 1;
      return [[this.row, pos], 'incl'];
    }
    for (i = 0; i < n; i++) {
      var st = pos - 1;
      if (kind === 'T' && repeat && n === 1) st = pos - 2;
      found = line.lastIndexOf(target, Math.max(0, st));
      if (found === -1 || found > st) { this.failed = true; return null; }
      pos = found;
    }
    if (kind === 'T') pos += 1;
    return [[this.row, pos], 'excl'];
  };

  P._paraMove = function (direction, n) {
    var r = this.row;
    for (var i = 0; i < n; i++) {
      r += direction;
      while (r > 0 && r < this.lines.length - 1 && this.lines[r].trim()) r += direction;
      r = Math.max(0, Math.min(r, this.lines.length - 1));
    }
    return [r, 0];
  };

  P._matchPair = function () {
    var line = this.line(), opens = '([{', closes = ')]}', i = this.col;
    while (i < line.length && opens.indexOf(line[i]) === -1 && closes.indexOf(line[i]) === -1) i += 1;
    if (i >= line.length) return null;
    var ch = line[i], t = this.text(), idx = this.toIndex(this.row, i), o, c, step;
    if (opens.indexOf(ch) !== -1) { o = ch; c = closes[opens.indexOf(ch)]; step = 1; }
    else { c = ch; o = opens[closes.indexOf(ch)]; step = -1; }
    var depth = 0, j = idx;
    while (j >= 0 && j < t.length) {
      if (t[j] === (step === 1 ? o : c)) depth += 1;
      else if (t[j] === (step === 1 ? c : o)) { depth -= 1; if (depth === 0) return [this.fromIndex(j), 'incl']; }
      j += step;
    }
    return null;
  };

  function nextWordStart(t, i, big) {
    var n = t.length;
    if (i >= n) return n;
    var cls = charClass(t[i], big);
    if (cls !== 0) while (i < n && charClass(t[i], big) === cls && t[i] !== '\n') i += 1;
    while (i < n && charClass(t[i], big) === 0) {
      if (t[i] === '\n' && i + 1 < n && t[i + 1] === '\n') return i + 1;
      i += 1;
    }
    return Math.min(i, n);
  }

  function prevWordStart(t, i, big) {
    i -= 1;
    while (i > 0 && charClass(t[i], big) === 0) i -= 1;
    if (i <= 0) return 0;
    var cls = charClass(t[i], big);
    while (i > 0 && charClass(t[i - 1], big) === cls) i -= 1;
    return Math.max(0, i);
  }

  function nextWordEnd(t, i, big) {
    var n = t.length;
    i += 1;
    while (i < n && charClass(t[i], big) === 0) i += 1;
    if (i >= n) return n - 1;
    var cls = charClass(t[i], big);
    while (i + 1 < n && charClass(t[i + 1], big) === cls) i += 1;
    return i;
  }

  function prevWordEnd(t, i) {
    i -= 1;
    while (i > 0 && charClass(t[i], false) === 0) i -= 1;
    return Math.max(0, i);
  }

  /* ----------------------------------------------------------- search */
  function vimRe(pat) {
    var out = pat.replace(/\\</g, '\\b').replace(/\\>/g, '\\b');
    out = out.replace(/\\\((.*?)\\\)/g, '($1)');
    out = out.replace(/\\\+/g, '+').replace(/\\\?/g, '?').replace(/\\\|/g, '|');
    out = out.replace(/\\\{/g, '{').replace(/\\\}/g, '}');
    return out;
  }

  P._search = function (pat, direction, fromPos) {
    var t = this.text(), rx;
    try { rx = new RegExp(vimRe(pat), 'g'); } catch (e) { return null; }
    var start = (fromPos === undefined || fromPos === null) ? this.toIndex(this.row, this.col) : fromPos;
    var hits = [], m;
    while ((m = rx.exec(t)) !== null) { hits.push(m.index); if (m.index === rx.lastIndex) rx.lastIndex += 1; }
    if (!hits.length) return null;
    var i;
    if (direction === '/') {
      for (i = 0; i < hits.length; i++) if (hits[i] > start) return this.fromIndex(hits[i]);
      return this.fromIndex(hits[0]);
    }
    for (i = hits.length - 1; i >= 0; i--) if (hits[i] < start) return this.fromIndex(hits[i]);
    return this.fromIndex(hits[hits.length - 1]);
  };

  P._doSearch = function (pat, direction) {
    if (pat) this.lastSearch = [pat, direction];
    else if (this.lastSearch) pat = this.lastSearch[0];
    var p = this._search(pat, direction);
    if (p) { this.row = p[0]; this.col = p[1]; this.clamp(); }
    else { this.failed = true; this.message = 'E486: Pattern not found: ' + pat; }
  };

  /* ------------------------------------------------------- ex commands */
  P._ex = function (cmd) {
    cmd = cmd.trim();
    if (!cmd) return;
    var self = this;
    var rng = null, body = cmd;
    var m = /^(%|\d+,\d+|\.,\$|'<,'>|\.,\.\+\d+|\d+)(.*)$/.exec(cmd);
    if (m) { rng = m[1]; body = m[2]; }
    body = body.trim();

    function resolve(r) {
      if (r === null || r === undefined) return [self.row, self.row];
      if (r === '%') return [0, self.lines.length - 1];
      if (r === "'<,'>") {
        if (self.lastVisual) return [self.lastVisual[1][0], self.lastVisual[2][0]];
        return [self.row, self.row];
      }
      if (r === '.,$') return [self.row, self.lines.length - 1];
      if (r.indexOf(',') !== -1) {
        var parts = r.split(',');
        if (parts[1].slice(0, 2) === '.+') return [self.row, Math.min(self.lines.length - 1, self.row + parseInt(parts[1].slice(2), 10))];
        return [parseInt(parts[0], 10) - 1, parseInt(parts[1], 10) - 1];
      }
      return [parseInt(r, 10) - 1, parseInt(r, 10) - 1];
    }

    var ms = /^s([^A-Za-z0-9 ])(.*)$/.exec(body);
    if (ms) {
      var sep = ms[1];
      var parts = splitUnescaped(ms[2], sep);
      var pat = parts[0] || '', rep = parts.length > 1 ? parts[1] : '', flags = parts.length > 2 ? parts[2] : '';
      var rr = resolve(rng);
      this.pushUndo();
      var rx;
      try { rx = new RegExp(vimRe(pat), flags.indexOf('g') !== -1 ? 'g' : ''); }
      catch (e) { this.message = 'E486: invalid pattern'; return; }
      var jsRep = rep.replace(/\\(\d)/g, '$$$1').replace(/&/g, '$&');
      var count = 0;
      for (var r = rr[0]; r <= rr[1] && r < this.lines.length; r++) {
        var before = this.lines[r];
        var after = before.replace(rx, jsRep);
        if (after !== before) { this.lines[r] = after; count += 1; this.row = r; }
      }
      this.message = count ? count + ' substitution(s)' : (flags.indexOf('e') !== -1 ? '' : 'E486: Pattern not found: ' + pat);
      this.clamp();
      return;
    }

    var mg = /^(g|v|global|vglobal)(!?)\/(.*)$/.exec(body);
    if (mg) {
      var invert = (mg[1] === 'v' || mg[1] === 'vglobal') || mg[2] === '!';
      var rest = mg[3];
      var idx = indexOfUnescaped(rest, '/');
      var gpat = idx === -1 ? rest : rest.slice(0, idx);
      var sub = idx === -1 ? 'p' : rest.slice(idx + 1);
      var gr = resolve(rng || '%');
      var grx;
      try { grx = new RegExp(vimRe(gpat)); } catch (e) { return; }
      this.pushUndo();
      var targets = [];
      for (var gi = gr[0]; gi <= gr[1] && gi < this.lines.length; gi++) {
        if (grx.test(this.lines[gi]) !== invert) targets.push(gi);
      }
      var st = sub.trim();
      if (st === 'd' || st === 'delete') {
        for (var ti = targets.length - 1; ti >= 0; ti--) this.lines.splice(targets[ti], 1);
        if (!this.lines.length) this.lines = [''];
      } else if (st.indexOf('normal ') === 0 || st.indexOf('norm ') === 0) {
        var keys = st.slice(st.indexOf(' ') + 1);
        for (var ni = targets.length - 1; ni >= 0; ni--) { this.row = targets[ni]; this.col = 0; this._runNormal(keys); }
      } else if (st[0] === 's') {
        for (var si = 0; si < targets.length; si++) { this.row = targets[si]; this._ex((targets[si] + 1) + st); }
      }
      this.clamp();
      return;
    }

    var mn = /^(normal|norm)!?\s+(.*)$/.exec(body);
    if (mn) {
      var nkeys = mn[2];
      var nr = rng ? resolve(rng) : [this.row, this.row];
      this.pushUndo();
      for (var nri = nr[0]; nri <= nr[1] && nri < this.lines.length; nri++) {
        this.row = nri; this.col = 0;
        this._runNormal(nkeys);
      }
      this.clamp();
      return;
    }

    if (/^d(elete)?$/.test(body)) {
      var dr = resolve(rng);
      this.pushUndo();
      this.setRegister(null, this.lines.slice(dr[0], dr[1] + 1).join('\n') + '\n', 'line');
      this.lines.splice(dr[0], dr[1] - dr[0] + 1);
      if (!this.lines.length) this.lines = [''];
      this.row = Math.min(dr[0], this.lines.length - 1);
      this.clamp();
      return;
    }

    var mm = /^(m|move|t|co|copy)\s*(\S+)$/.exec(body);
    if (mm) {
      var mr = resolve(rng), dest = mm[2];
      var d = dest === '$' ? this.lines.length - 1 : (dest === '0' ? -1 : parseInt(dest, 10) - 1);
      var block = this.lines.slice(mr[0], mr[1] + 1);
      this.pushUndo();
      if (mm[1] === 'm' || mm[1] === 'move') {
        this.lines.splice(mr[0], mr[1] - mr[0] + 1);
        if (d > mr[1]) d -= (mr[1] - mr[0] + 1);
        this.lines.splice.apply(this.lines, [d + 1, 0].concat(block));
      } else {
        this.lines.splice.apply(this.lines, [d + 1, 0].concat(block));
      }
      this.row = d + block.length;
      this.clamp();
      return;
    }

    if (/^sort(\s+u)?$/.test(body)) {
      var sr = resolve(rng || '%');
      this.pushUndo();
      var blk = this.lines.slice(sr[0], sr[1] + 1).sort();
      if (/u$/.test(body.trim())) {
        var seen = {}, uniq = [];
        for (var ui = 0; ui < blk.length; ui++) if (!seen[blk[ui]]) { seen[blk[ui]] = 1; uniq.push(blk[ui]); }
        blk = uniq;
      }
      this.lines.splice.apply(this.lines, [sr[0], sr[1] - sr[0] + 1].concat(blk));
      this.clamp();
      return;
    }

    if (/^(w|write|wq|x|q|q!|wa|xa)$/.test(body)) {
      if (body[0] === 'w' || body[0] === 'x') { this.written = true; this.message = '"buffer" written'; }
      if (['q', 'q!', 'wq', 'x', 'xa'].indexOf(body) !== -1) this.quit = true;
      return;
    }
    if (/^noh(l|lsearch)?$/.test(body)) return;
    if (/^set\s+/.test(body)) { this.message = body; return; }
    if (/^\d+$/.test(cmd)) {
      var ln = Math.max(0, Math.min(parseInt(cmd, 10) - 1, this.lines.length - 1));
      this.row = ln; this.col = this.firstNonBlank(ln);
      return;
    }
    this.message = 'E492: Not an editor command: ' + body;
  };

  function splitUnescaped(s, sep) {
    var out = [], cur = '', i;
    for (i = 0; i < s.length; i++) {
      if (s[i] === '\\' && s[i + 1] === sep) { cur += sep; i += 1; continue; }
      if (s[i] === sep) { out.push(cur); cur = ''; continue; }
      cur += s[i];
    }
    out.push(cur);
    return out;
  }

  function indexOfUnescaped(s, ch) {
    for (var i = 0; i < s.length; i++) {
      if (s[i] === '\\') { i += 1; continue; }
      if (s[i] === ch) return i;
    }
    return -1;
  }

  P._runNormal = function (keys) {
    if (this._depth > 20) return;
    this._depth += 1;
    try {
      var saved = this.pending;
      this.pending = [];
      var ks = parseKeys(keys);
      for (var i = 0; i < ks.length; i++) {
        this.key(ks[i]);
        if (this.failed) break;
      }
      if (this.mode === 'insert') this.key('\x1b');
      this.pending = saved;
    } finally { this._depth -= 1; }
  };

  /* -------------------------------------------------- simple commands */
  P._simple = function (s, count, reg, vis) {
    var n = count || 1, c = s[0], i, r, line, end, txt, kind, vr, sv, ev, b;

    if (c === 'g') {
      if (s.length === 1) return 'incomplete';
      var two = s.slice(0, 2);
      if (two === 'gg') {
        r = Math.max(0, Math.min(count ? count - 1 : 0, this.lines.length - 1));
        this.row = r; this.col = this.firstNonBlank(r);
        if (!vis) this.clamp();
        return 'done';
      }
      if (two === 'gJ') return this._join(n, false);
      if (two === 'gv') {
        if (this.lastVisual) {
          this.mode = this.lastVisual[0];
          this.visualStart = this.lastVisual[1];
          this.row = this.lastVisual[2][0]; this.col = this.lastVisual[2][1];
          this.clamp();
        }
        return 'done';
      }
      if (two === 'gu' || two === 'gU' || two === 'g~') return 'incomplete';
      return 'invalid';
    }

    if (c === 'Z') {
      if (s.length === 1) return 'incomplete';
      if (s.slice(0, 2) === 'ZZ' || s.slice(0, 2) === 'ZQ') {
        this.written = s.slice(0, 2) === 'ZZ'; this.quit = true; return 'done';
      }
      return 'invalid';
    }

    if (c === 'm') {
      if (s.length === 1) return 'incomplete';
      this.marks[s[1]] = [this.row, this.col];
      return 'done';
    }

    if (c === 'r') {
      if (s.length === 1) return 'incomplete';
      var ch = s[1];
      this.pushUndo();
      if (vis) {
        vr = this.visualRange(); sv = vr[0]; ev = vr[1];
        if (this.mode === 'vline') {
          for (r = sv[0]; r <= ev[0]; r++) this.lines[r] = ch.repeat(this.lines[r].length);
        } else {
          var a = this.toIndex(sv[0], sv[1]), bb = this.toIndex(ev[0], ev[1]) + 1, t = this.text();
          var mid = t.slice(a, bb).replace(/[^\n]/g, ch);
          this.lines = (t.slice(0, a) + mid + t.slice(bb)).split('\n');
          this.row = sv[0]; this.col = sv[1];
        }
        this.mode = 'normal'; this.visualStart = null; this.clamp();
        return 'done';
      }
      line = this.line();
      if (this.col + n > line.length) return 'done';
      this.lines[this.row] = line.slice(0, this.col) + ch.repeat(n) + line.slice(this.col + n);
      this.col += n - 1;
      this._registerDot();
      return 'done';
    }

    if (c === 'q') {
      if (this.recordingReg !== null) {
        this.registers[this.recordingReg] = [this.recorded.join(''), 'macro'];
        this.recordingReg = null; this.recorded = [];
        return 'done';
      }
      if (s.length === 1) return 'incomplete';
      this.recordingReg = s[1]; this.recorded = [];
      return 'done';
    }

    if (c === '@') {
      if (s.length === 1) return 'incomplete';
      var rg = s[1];
      if (rg === '@') { rg = this.lastMacro; if (!rg) return 'done'; }
      this.lastMacro = rg;
      var bodyKeys = (this.registers[rg] || ['', ''])[0];
      for (i = 0; i < n; i++) {
        this.failed = false;
        this._runNormal(bodyKeys);
        if (this.failed) break;
      }
      this.failed = false;
      return 'done';
    }

    if (c === '"') return 'incomplete';

    if (vis) {
      if (c === 'o' || c === 'O') {
        var tmp = this.visualStart;
        this.visualStart = [this.row, this.col];
        this.row = tmp[0]; this.col = tmp[1];
        return 'done';
      }
      if ((c === 'i' || c === 'a') && s.length >= 2) {
        var rng = this.textObject(c, s[1], n);
        if (rng) { this.visualStart = rng[0]; this.row = rng[1][0]; this.col = rng[1][1]; }
        return 'done';
      }
      if (c === 'i' || c === 'a') return 'incomplete';
      if (c === 'x') return this._applyOperatorVisual('d', reg);
      if (c === 's') return this._applyOperatorVisual('c', reg);
      if (c === 'D' || c === 'X' || c === 'R') { this.mode = 'vline'; return this._applyOperatorVisual('d', reg); }
      if (c === 'C') { this.mode = 'vline'; return this._applyOperatorVisual('c', reg); }
      if (c === 'Y') { this.mode = 'vline'; return this._applyOperatorVisual('y', reg); }
      if (c === 'J') {
        vr = this.visualRange();
        this._saveVisual();
        this.mode = 'normal'; this.visualStart = null;
        this.row = vr[0][0];
        return this._join(Math.max(2, vr[1][0] - vr[0][0] + 1), true);
      }
      if (c === 'u') return this._applyOperatorVisual('gu', reg);
      if (c === 'U') return this._applyOperatorVisual('gU', reg);
      if (c === '~') return this._applyOperatorVisual('g~', reg);
      if (c === 'p' || c === 'P') {
        var pr = this.getRegister(reg);
        this._applyOperatorVisual('d', '_');
        this._paste(pr[0], pr[1], true);
        return 'done';
      }
      if (c === 'I' && this.mode === 'vblock') {
        b = this._vblockCols();
        this._saveVisual(); this.pushUndo();
        this.mode = 'insert'; this.visualStart = null;
        this.row = b[0]; this.col = b[2];
        this._blockInsert = [b[0], b[1], b[2], false];
        this._beginChange([]);
        return 'done';
      }
      if (c === 'A' && this.mode === 'vblock') {
        b = this._vblockCols();
        this._saveVisual(); this.pushUndo();
        this.mode = 'insert'; this.visualStart = null;
        this.row = b[0]; this.col = Math.min(this.lines[b[0]].length, b[3] + 1);
        this._blockInsert = [b[0], b[1], b[3] + 1, true];
        this._beginChange([]);
        return 'done';
      }
    }

    if (c === 'i' && !vis) { this.pushUndo(); this.mode = 'insert'; this._beginChange(this.pending); return 'done'; }
    if (c === 'a' && !vis) {
      this.pushUndo(); this.mode = 'insert';
      this.col = Math.min(this.line().length, this.col + 1);
      this._beginChange(this.pending); return 'done';
    }
    if (c === 'I') {
      this.pushUndo(); this.mode = 'insert';
      this.col = this.line().trim() ? this.firstNonBlank(this.row) : 0;
      this._beginChange(this.pending); return 'done';
    }
    if (c === 'A') {
      this.pushUndo(); this.mode = 'insert';
      this.col = this.line().length;
      this._beginChange(this.pending); return 'done';
    }
    if (c === 'o' || c === 'O') {
      this.pushUndo();
      var ind = leadingWs(this.line());
      var at = c === 'o' ? this.row + 1 : this.row;
      this.lines.splice(at, 0, ind);
      this.row = at; this.col = ind.length;
      this.mode = 'insert';
      this._beginChange(this.pending);
      return 'done';
    }
    if (c === 'R') { this.pushUndo(); this.mode = 'replace'; this._beginChange(this.pending); return 'done'; }
    if (c === 'v') { this.mode = 'visual'; this.visualStart = [this.row, this.col]; return 'done'; }
    if (c === 'V') { this.mode = 'vline'; this.visualStart = [this.row, this.col]; return 'done'; }
    if (c === '\x16') { this.mode = 'vblock'; this.visualStart = [this.row, this.col]; return 'done'; }
    if (c === ':') {
      if (vis) this._saveVisual();
      this.mode = 'cmdline'; this.cmdtype = ':';
      this.cmdline = vis ? "'<,'>" : '';
      this.visualStart = null;
      return 'done';
    }
    if (c === '/' || c === '?') { this.mode = 'cmdline'; this.cmdtype = c; this.cmdline = ''; return 'done'; }

    if (c === 'x') {
      this.pushUndo();
      line = this.line();
      if (!line) return 'done';
      end = Math.min(line.length, this.col + n);
      this.setRegister(reg, line.slice(this.col, end), 'char');
      this.lines[this.row] = line.slice(0, this.col) + line.slice(end);
      this.clamp(); this._registerDot();
      return 'done';
    }
    if (c === 'X') {
      this.pushUndo();
      line = this.line();
      var st2 = Math.max(0, this.col - n);
      this.setRegister(reg, line.slice(st2, this.col), 'char');
      this.lines[this.row] = line.slice(0, st2) + line.slice(this.col);
      this.col = st2; this._registerDot();
      return 'done';
    }
    if (c === 's') {
      this.pushUndo();
      line = this.line();
      end = Math.min(line.length, this.col + n);
      this.setRegister(reg, line.slice(this.col, end), 'char');
      this.lines[this.row] = line.slice(0, this.col) + line.slice(end);
      this.mode = 'insert'; this._beginChange(this.pending);
      return 'done';
    }
    if (c === 'S') return this._operatorPending('c', 'c', count, reg);
    if (c === 'D') {
      this.pushUndo();
      line = this.line();
      this.setRegister(reg, line.slice(this.col), 'char');
      this.lines[this.row] = line.slice(0, this.col);
      this.clamp(); this._registerDot();
      return 'done';
    }
    if (c === 'C') {
      this.pushUndo();
      line = this.line();
      this.setRegister(reg, line.slice(this.col), 'char');
      this.lines[this.row] = line.slice(0, this.col);
      this.mode = 'insert'; this._beginChange(this.pending);
      return 'done';
    }
    if (c === 'Y') return this._operatorPending('y', 'y', count, reg);
    if (c === 'J') return this._join(Math.max(2, n), true);
    if (c === '~') {
      this.pushUndo();
      line = this.line();
      end = Math.min(line.length, this.col + n);
      var swapped = line.slice(this.col, end).replace(/[a-zA-ZÀ-ɏ]/g, function (x) {
        return x === x.toLowerCase() ? x.toUpperCase() : x.toLowerCase();
      });
      this.lines[this.row] = line.slice(0, this.col) + swapped + line.slice(end);
      this.col = Math.min(end, Math.max(0, line.length - 1));
      this._registerDot();
      return 'done';
    }
    if (c === 'p' || c === 'P') {
      this.pushUndo();
      var pr2 = this.getRegister(reg);
      if (!pr2[0]) return 'done';
      for (i = 0; i < n; i++) this._paste(pr2[0], pr2[1], c === 'P');
      this._registerDot();
      return 'done';
    }
    if (c === '\x01' || c === '\x18') {
      var delta = c === '\x01' ? n : -n;
      line = this.line();
      var rx2 = /-?\d+/g, mm2, hit = null;
      while ((mm2 = rx2.exec(line)) !== null) { if (mm2.index + mm2[0].length > this.col) { hit = mm2; break; } }
      if (!hit) { this.failed = true; return 'done'; }
      this.pushUndo();
      var neu2 = String(parseInt(hit[0], 10) + delta);
      this.lines[this.row] = line.slice(0, hit.index) + neu2 + line.slice(hit.index + hit[0].length);
      this.col = hit.index + neu2.length - 1;
      this._registerDot();
      return 'done';
    }
    if (c === 'u') { this.undo(); return 'done'; }
    if (c === '\x12') { this.redo(); return 'done'; }
    if (c === '.') {
      if (this.lastChange) {
        var keys = this.lastChange.slice();
        this.lastChange = null;
        this._runNormal(keys.join(''));
        this.lastChange = keys;
      }
      return 'done';
    }
    if (c === '\x04' || c === '\x15' || c === '\x06' || c === '\x02') {
      var step = { '\x04': 10, '\x15': -10, '\x06': 20, '\x02': -20 }[c];
      this.row = Math.max(0, Math.min(this.lines.length - 1, this.row + step));
      this.clamp();
      return 'done';
    }

    var res = this.motion(s, n, false);
    if (res === 'incomplete') return 'incomplete';
    if (!res) return 'done';
    this.row = res[0][0]; this.col = res[0][1];
    if (s[0] !== 'j' && s[0] !== 'k') this.desiredCol = this.col;
    if (s[0] === '$') this.desiredCol = 1000000;
    this.clamp();
    return 'done';
  };

  P._join = function (n, spaces) {
    this.pushUndo();
    for (var i = 0; i < Math.max(1, n - 1); i++) {
      if (this.row + 1 >= this.lines.length) break;
      var cur = this.lines[this.row];
      var nxt = this.lines.splice(this.row + 1, 1)[0];
      var joined;
      if (spaces) {
        var trimmed = cur.replace(/\s+$/, '');
        joined = trimmed + ((trimmed.trim() && nxt.trim()) ? ' ' : '') + nxt.replace(/^\s+/, '');
        this.col = trimmed.length;
      } else {
        joined = cur + nxt;
        this.col = cur.length;
      }
      this.lines[this.row] = joined;
    }
    this.clamp();
    this._registerDot();
    return 'done';
  };

  P._paste = function (txt, kind, before) {
    var line, at, i;
    if (kind === 'line') {
      var body = txt.slice(-1) === '\n' ? txt.slice(0, -1).split('\n') : txt.split('\n');
      at = before ? this.row : this.row + 1;
      this.lines.splice.apply(this.lines, [at, 0].concat(body));
      this.row = at;
      this.col = this.firstNonBlank(this.row);
    } else if (kind === 'block') {
      var chunks = txt.split('\n');
      var c = this.col + (before ? 0 : 1);
      for (i = 0; i < chunks.length; i++) {
        var r = this.row + i;
        while (r >= this.lines.length) this.lines.push('');
        line = this.lines[r];
        while (line.length < c) line += ' ';
        this.lines[r] = line.slice(0, c) + chunks[i] + line.slice(c);
      }
    } else {
      line = this.line();
      at = before ? this.col : Math.min(line.length, this.col + 1);
      if (txt.indexOf('\n') !== -1) {
        var parts = txt.split('\n');
        var head = parts[0], rest = parts.slice(1);
        var tail = line.slice(at);
        this.lines[this.row] = line.slice(0, at) + head;
        this.lines.splice.apply(this.lines, [this.row + 1, 0].concat(rest));
        this.row += rest.length;
        this.col = rest.length ? Math.max(0, rest[rest.length - 1].length) : 0;
        this.lines[this.row] += tail;
      } else {
        this.lines[this.row] = line.slice(0, at) + txt + line.slice(at);
        this.col = at + txt.length - 1;
      }
    }
    this.clamp();
  };

  P.state = function () {
    return {
      lines: this.lines.slice(),
      cursor: [this.row, this.col],
      mode: this.mode,
      pending: this.pending.join(''),
      cmdline: this.mode === 'cmdline' ? this.cmdtype + this.cmdline : '',
      message: this.message,
      recording: this.recordingReg
    };
  };

  Vim.parseKeys = parseKeys;
  root.Vim = Vim;
  if (typeof module !== 'undefined' && module.exports) module.exports = Vim;
})(typeof window !== 'undefined' ? window : globalThis);
