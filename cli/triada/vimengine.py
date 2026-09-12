"""A compact but faithful Vim emulator.

Supports the subset of Vim needed to teach Vim properly:

  modes      normal, insert, visual (char/line/block), replace, cmdline
  motions    h j k l w W b B e E ge 0 ^ $ gg G { } f F t T ; , % H M L + - _
  operators  d c y > < gu gU g~  (with counts, doubling, and text objects)
  objects    iw aw iW aW i" a" i' a' i( a( i[ a[ i{ a{ i< a< ip ap  (b/B aliases)
  commands   x X s S D C Y p P o O a A i I J gJ r R ~ u <C-r> . v V <C-v>
             m ` ' q @ / ? n N : (a useful slice of ex)
  registers  " 0 a-z A-Z (append) _ (black hole)

Keys are fed as a string using Vim's own notation for specials:
``<Esc> <CR> <BS> <Tab> <Space> <C-r> <C-v> <lt>``.

The engine is deliberately dependency-free and mirrors ``web/vimengine.js``
key for key; ``tests/vim_cases.json`` is run against both.
"""

from __future__ import annotations

import re

WORD_RE = re.compile(r"[0-9A-Za-z_\u00c0-\u024f]")

SPECIALS = {
    "<esc>": "\x1b",
    "<cr>": "\r",
    "<enter>": "\r",
    "<bs>": "\x08",
    "<tab>": "\t",
    "<space>": " ",
    "<lt>": "<",
    "<gt>": ">",
    "<del>": "\x7f",
}


def parse_keys(s: str) -> list[str]:
    """'ciw<Esc>' -> ['c','i','w','\\x1b']"""
    out: list[str] = []
    i = 0
    while i < len(s):
        if s[i] == "<":
            j = s.find(">", i)
            if j != -1:
                tok = s[i : j + 1]
                low = tok.lower()
                if low in SPECIALS:
                    out.append(SPECIALS[low])
                    i = j + 1
                    continue
                m = re.fullmatch(r"<c-([a-z\[])>", low)
                if m:
                    ch = m.group(1)
                    out.append(chr(ord(ch.upper()) - 64) if ch != "[" else "\x1b")
                    i = j + 1
                    continue
        out.append(s[i])
        i += 1
    return out


def char_class(c: str, big: bool = False) -> int:
    if c in " \t":
        return 0
    if c == "\n":
        return 0
    if big:
        return 1
    return 1 if WORD_RE.match(c) else 2


class VimError(Exception):
    pass


class Vim:
    """A single-buffer Vim."""

    def __init__(self, lines=None, cursor=(0, 0)):
        self.lines: list[str] = list(lines) if lines else [""]
        self.row, self.col = cursor
        self.mode = "normal"  # normal insert visual vline vblock replace cmdline
        self.pending: list[str] = []
        self.registers: dict[str, tuple[str, str]] = {}
        self.marks: dict[str, tuple[int, int]] = {}
        self.undo_stack: list[tuple] = []
        self.redo_stack: list[tuple] = []
        self.message = ""
        self.cmdline = ""
        self.cmdtype = ""
        self.last_search: tuple[str, str] | None = None
        self.last_ft: tuple[str, str] | None = None
        self.last_insert = ""
        self.last_change: list[str] | None = None
        self._recording_change: list[str] | None = None
        self.recording_reg: str | None = None
        self.recorded: list[str] = []
        self.last_macro: str | None = None
        self.visual_start: tuple[int, int] | None = None
        self.desired_col = 0
        self.keylog: list[str] = []
        self.typed = 0
        self.written = False
        self.quit = False
        self.pending_str = ""
        self._depth = 0
        self.failed = False
        self._block_insert = None
        self._insert_anchor = None
        self.last_visual = None
        self._op_pending = None

    # ------------------------------------------------------------ helpers
    @property
    def line(self) -> str:
        return self.lines[self.row] if 0 <= self.row < len(self.lines) else ""

    def text(self) -> str:
        return "\n".join(self.lines)

    def snapshot(self):
        return (list(self.lines), self.row, self.col)

    def push_undo(self):
        snap = self.snapshot()
        if self.undo_stack and self.undo_stack[-1][0] == snap[0]:
            return
        self.undo_stack.append(snap)
        self.redo_stack.clear()

    def undo(self):
        if not self.undo_stack:
            self.message = "Already at oldest change"
            return
        cur = self.snapshot()
        lines, r, c = self.undo_stack.pop()
        self.redo_stack.append(cur)
        self.lines, self.row, self.col = list(lines), r, c
        self.clamp()

    def redo(self):
        if not self.redo_stack:
            self.message = "Already at newest change"
            return
        cur = self.snapshot()
        lines, r, c = self.redo_stack.pop()
        self.undo_stack.append(cur)
        self.lines, self.row, self.col = list(lines), r, c
        self.clamp()

    def clamp(self):
        if not self.lines:
            self.lines = [""]
        self.row = max(0, min(self.row, len(self.lines) - 1))
        maxc = len(self.line) - (0 if self.mode in ("insert", "visual", "vline", "vblock") else 1)
        self.col = max(0, min(self.col, max(0, maxc)))

    # flat-index conversions (word motions are far easier on a flat string)
    def to_index(self, row: int, col: int) -> int:
        return sum(len(l) + 1 for l in self.lines[:row]) + col

    def from_index(self, idx: int) -> tuple[int, int]:
        idx = max(0, min(idx, len(self.text())))
        r = 0
        while r < len(self.lines) and idx > len(self.lines[r]):
            idx -= len(self.lines[r]) + 1
            r += 1
        return (min(r, len(self.lines) - 1), max(0, idx))

    # ------------------------------------------------------------ feeding
    def feed(self, keys):
        if isinstance(keys, str):
            keys = parse_keys(keys)
        for k in keys:
            self.key(k)
        return self

    def key(self, k: str):
        self.keylog.append(k)
        if self._depth == 0:
            self.typed += 1
        if self.recording_reg is not None and not (k == "q" and self.mode == "normal" and not self.pending):
            self.recorded.append(k)
        if self._recording_change is not None:
            self._recording_change.append(k)

        if self.mode == "insert":
            self._insert_key(k)
        elif self.mode == "replace":
            self._replace_key(k)
        elif self.mode == "cmdline":
            self._cmdline_key(k)
        else:
            self._normal_key(k)
        return self

    # ------------------------------------------------------------- insert
    def _insert_key(self, k: str):
        if k == "\x1b":
            self.mode = "normal"
            self._finish_block_insert()
            self.col = max(0, self.col - 1)
            self._end_change()
            self.clamp()
            return
        line = self.line
        if k == "\x08":  # backspace
            if self.col > 0:
                self.lines[self.row] = line[: self.col - 1] + line[self.col :]
                self.col -= 1
            elif self.row > 0:
                prev = self.lines[self.row - 1]
                self.col = len(prev)
                self.lines[self.row - 1] = prev + line
                del self.lines[self.row]
                self.row -= 1
            return
        if k == "\r":
            self.lines[self.row] = line[: self.col]
            indent = re.match(r"[ \t]*", line).group(0) if line.strip() else ""
            self.lines.insert(self.row + 1, indent + line[self.col :])
            self.row += 1
            self.col = len(indent)
            return
        if k == "\t":
            self.lines[self.row] = line[: self.col] + "    " + line[self.col :]
            self.col += 4
            return
        if k < " " and k not in ("\t",):
            return
        self.lines[self.row] = line[: self.col] + k + line[self.col :]
        self.col += len(k)

    def _finish_block_insert(self):
        """<C-v>I / <C-v>A / <C-v>c: replay the typed text on every block row."""
        if not self._block_insert:
            return
        r1, r2, col, pad = self._block_insert
        self._block_insert = None
        if self.row != r1:
            return
        typed = self.lines[r1][col : self.col]
        if not typed:
            return
        for r in range(r1 + 1, r2 + 1):
            if r >= len(self.lines):
                break
            line = self.lines[r]
            if len(line) < col:
                if not pad:
                    continue
                line = line.ljust(col)
            self.lines[r] = line[:col] + typed + line[col:]

    def _replace_key(self, k: str):
        if k == "\x1b":
            self.mode = "normal"
            self.col = max(0, self.col - 1)
            self._end_change()
            return
        if k == "\r":
            self.row += 1
            self.col = 0
            if self.row >= len(self.lines):
                self.lines.append("")
            return
        line = self.line
        self.lines[self.row] = line[: self.col] + k + line[self.col + 1 :]
        self.col += 1

    # ------------------------------------------------------------ cmdline
    def _cmdline_key(self, k: str):
        if k == "\x1b":
            self.mode = "normal"
            self.cmdline = ""
            return
        if k == "\x08":
            if self.cmdline:
                self.cmdline = self.cmdline[:-1]
            else:
                self.mode = "normal"
            return
        if k == "\r":
            cmd, self.cmdline = self.cmdline, ""
            self.mode = "normal"
            if self.cmdtype == ":":
                self._ex(cmd)
            elif self._op_pending:
                op, reg, r0, c0 = self._op_pending
                self._op_pending = None
                if cmd:
                    self.last_search = (cmd, self.cmdtype)
                target = self._search(cmd, self.cmdtype, from_pos=self.to_index(r0, c0))
                if target is None:
                    self.failed = True
                    self.message = f"E486: Pattern not found: {cmd}"
                    return
                start, end = (r0, c0), target
                if self.to_index(*start) > self.to_index(*end):
                    start, end = end, start
                self._apply_operator(op, start, end, "excl", reg)
            else:
                self._do_search(cmd, self.cmdtype)
            return
        self.cmdline += k

    # ---------------------------------------------------------- change rec
    def _begin_change(self, keys):
        self._recording_change = list(keys)

    def _end_change(self):
        if self._recording_change is not None:
            self.last_change = self._recording_change
            self._recording_change = None

    # ------------------------------------------------------------- normal
    def _normal_key(self, k: str):
        if k == "\x1b":
            self.pending = []
            if self.mode in ("visual", "vline", "vblock"):
                self.mode = "normal"
                self.visual_start = None
                self.clamp()
            return
        self.pending.append(k)
        seq = "".join(self.pending)
        try:
            status = self._exec_normal(seq)
        except VimError:
            status = "invalid"
        if status in ("done", "invalid"):
            self.pending = []
        self.pending_str = "".join(self.pending)

    # ---- parsing -------------------------------------------------------
    def _exec_normal(self, seq: str) -> str:
        i = 0
        reg = None
        count1 = ""
        # ["x] and counts may interleave
        while True:
            while i < len(seq) and seq[i].isdigit() and not (seq[i] == "0" and not count1):
                count1 += seq[i]
                i += 1
            if i < len(seq) and seq[i] == '"':
                if i + 1 >= len(seq):
                    return "incomplete"
                reg = seq[i + 1]
                i += 2
                continue
            break
        if i >= len(seq):
            return "incomplete"
        n1 = int(count1) if count1 else None
        rest = seq[i:]
        return self._command(rest, n1, reg)

    OPERATORS = {"d", "c", "y", ">", "<", "=", "gu", "gU", "g~", "g?"}

    def _command(self, s: str, count, reg) -> str:
        vis = self.mode in ("visual", "vline", "vblock")
        c = s[0]

        # ---- operators
        op = None
        if c in "dcy><=":
            op = c
            oprest = s[1:]
        elif c == "g" and len(s) >= 2 and s[1] in "uU~?":
            op = "g" + s[1]
            oprest = s[2:]
        elif c == "g" and len(s) == 1:
            return "incomplete"

        if op is not None:
            if vis:
                return self._apply_operator_visual(op, reg)
            return self._operator_pending(op, oprest, count, reg)

        # ---- simple / non-operator commands
        return self._simple(s, count, reg, vis)

    # ---- operator pending ---------------------------------------------
    def _operator_pending(self, op: str, rest: str, count1, reg) -> str:
        if rest == "":
            return "incomplete"
        i = 0
        count2 = ""
        while i < len(rest) and rest[i].isdigit() and not (rest[i] == "0" and not count2):
            count2 += rest[i]
            i += 1
        if i >= len(rest):
            return "incomplete"
        motion = rest[i:]
        n = (count1 or 1) * (int(count2) if count2 else 1)

        if motion[0] in "/?":
            self._op_pending = (op, reg, self.row, self.col)
            self.mode = "cmdline"
            self.cmdtype = motion[0]
            self.cmdline = motion[1:]
            return "done"

        # doubled operator => linewise on n lines
        doubled = motion == op[-1] or (len(op) == 2 and motion == op)
        if op in (">", "<", "=") and motion == op:
            doubled = True
        if doubled:
            r2 = min(len(self.lines) - 1, self.row + n - 1)
            return self._apply_operator(op, (self.row, 0), (r2, 0), "line", reg)

        # text objects
        if motion[0] in "ia":
            if len(motion) == 1:
                return "incomplete"
            rng = self.text_object(motion[0], motion[1], n)
            if rng is None:
                return "done"
            start, end, kind = rng
            return self._apply_operator(op, start, end, kind, reg)

        res = self.motion(motion, n, for_operator=True)
        if res == "incomplete":
            return "incomplete"
        if res is None:
            return "done"
        target, kind = res
        start, end = (self.row, self.col), target
        if self.to_index(*start) > self.to_index(*end):
            start, end = end, start
        return self._apply_operator(op, start, end, kind, reg)

    # ---- applying operators -------------------------------------------
    def _yank_text(self, start, end, kind) -> str:
        if kind == "line":
            return "\n".join(self.lines[start[0] : end[0] + 1]) + "\n"
        a, b = self.to_index(*start), self.to_index(*end)
        if kind == "incl":
            b += 1
        return self.text()[a:b]

    def set_register(self, reg, text, kind):
        if reg == "_":
            return
        if reg and reg.isupper():
            key = reg.lower()
            old = self.registers.get(key, ("", kind))
            self.registers[key] = (old[0] + text, kind)
        elif reg:
            self.registers[reg] = (text, kind)
        else:
            self.registers['"'] = (text, kind)
            self.registers["0"] = (text, kind)

    def get_register(self, reg):
        return self.registers.get(reg or '"', ("", "char"))

    def _delete_range(self, start, end, kind):
        if kind == "line":
            del self.lines[start[0] : end[0] + 1]
            if not self.lines:
                self.lines = [""]
            self.row = min(start[0], len(self.lines) - 1)
            self.col = self._first_nonblank(self.row)
        else:
            a, b = self.to_index(*start), self.to_index(*end)
            if kind == "incl":
                b += 1
            t = self.text()
            self.lines = (t[:a] + t[b:]).split("\n")
            self.row, self.col = self.from_index(a)

    def _apply_operator(self, op, start, end, kind, reg):
        if op == "y":
            txt = self._yank_text(start, end, kind)
            self.set_register(reg, txt, "line" if kind == "line" else "char")
            if reg not in ("_",):
                self.registers['"'] = (txt, "line" if kind == "line" else "char")
            self.row, self.col = (start if kind != "line" else (start[0], self.col))
            if kind == "line":
                self.row = start[0]
            self.clamp()
            return "done"

        self.push_undo()

        if op in (">", "<"):
            for r in range(start[0], end[0] + 1):
                if op == ">":
                    self.lines[r] = "    " + self.lines[r] if self.lines[r] else self.lines[r]
                else:
                    self.lines[r] = re.sub(r"^ {1,4}", "", self.lines[r])
            self.row = start[0]
            self.col = self._first_nonblank(self.row)
            self._register_dot()
            return "done"

        if op == "=":
            self.row = start[0]
            self.clamp()
            return "done"

        if op in ("gu", "gU", "g~"):
            txt = self._yank_text(start, end, kind)
            fn = {"gu": str.lower, "gU": str.upper, "g~": str.swapcase}[op]
            new = fn(txt)
            if kind == "line":
                repl = new.rstrip("\n").split("\n")
                self.lines[start[0] : end[0] + 1] = repl
                self.row, self.col = start[0], self._first_nonblank(start[0])
            else:
                a, b = self.to_index(*start), self.to_index(*end)
                if kind == "incl":
                    b += 1
                t = self.text()
                self.lines = (t[:a] + new + t[b:]).split("\n")
                self.row, self.col = start
            self.clamp()
            self._register_dot()
            return "done"

        txt = self._yank_text(start, end, kind)
        self.set_register(reg, txt, "line" if kind == "line" else "char")

        if op == "d":
            self._delete_range(start, end, kind)
            self.clamp()
            self._register_dot()
            return "done"

        # op == 'c'
        if kind == "line":
            indent = re.match(r"[ \t]*", self.lines[start[0]]).group(0)
            del self.lines[start[0] : end[0] + 1]
            self.lines.insert(start[0], indent)
            self.row, self.col = start[0], len(indent)
        else:
            self._delete_range(start, end, kind)
        self.mode = "insert"
        self._begin_change(list(self.pending))
        return "done"

    def _register_dot(self):
        self.last_change = list(self.pending)

    # ---- visual --------------------------------------------------------
    def visual_range(self):
        s, e = self.visual_start, (self.row, self.col)
        if self.to_index(*s) > self.to_index(*e):
            s, e = e, s
        return s, e

    def _save_visual(self):
        if self.visual_start is not None:
            s, e = self.visual_range()
            self.last_visual = (self.mode, s, e)

    def _apply_operator_visual(self, op, reg):
        self._save_visual()
        s, e = self.visual_range()
        kind = "line" if self.mode == "vline" else "incl"
        if self.mode == "vblock":
            return self._vblock_op(op, reg)
        mode_was = self.mode
        self.mode = "normal"
        self.visual_start = None
        if op == "c" and kind == "line":
            self.push_undo()
            indent = re.match(r"[ \t]*", self.lines[s[0]]).group(0)
            txt = self._yank_text(s, e, "line")
            self.set_register(reg, txt, "line")
            del self.lines[s[0] : e[0] + 1]
            self.lines.insert(s[0], indent)
            self.row, self.col = s[0], len(indent)
            self.mode = "insert"
            self._begin_change([])
            return "done"
        res = self._apply_operator(op, s, e, kind, reg)
        if mode_was and self.mode not in ("insert",):
            self.clamp()
        return res

    def _vblock_cols(self):
        s, e = self.visual_start, (self.row, self.col)
        r1, r2 = sorted((s[0], e[0]))
        c1, c2 = sorted((s[1], e[1]))
        return r1, r2, c1, c2

    def _vblock_op(self, op, reg):
        r1, r2, c1, c2 = self._vblock_cols()
        self.mode = "normal"
        self.visual_start = None
        chunks = [self.lines[r][c1 : c2 + 1] for r in range(r1, r2 + 1)]
        self.set_register(reg, "\n".join(chunks), "block")
        if op == "y":
            self.row, self.col = r1, c1
            self.clamp()
            return "done"
        self.push_undo()
        for r in range(r1, r2 + 1):
            self.lines[r] = self.lines[r][:c1] + self.lines[r][c2 + 1 :]
        self.row, self.col = r1, c1
        if op == "c":
            self.mode = "insert"
            self._block_insert = (r1, r2, c1)
            self._begin_change([])
        self.clamp()
        return "done"

    # ---- text objects --------------------------------------------------
    PAIRS = {
        "(": ("(", ")"),
        ")": ("(", ")"),
        "b": ("(", ")"),
        "[": ("[", "]"),
        "]": ("[", "]"),
        "{": ("{", "}"),
        "}": ("{", "}"),
        "B": ("{", "}"),
        "<": ("<", ">"),
        ">": ("<", ">"),
    }
    QUOTES = {'"', "'", "`"}

    def text_object(self, ia: str, obj: str, n: int = 1):
        inner = ia == "i"
        if obj in ("w", "W"):
            return self._obj_word(inner, obj == "W", n)
        if obj in self.PAIRS:
            return self._obj_pair(inner, *self.PAIRS[obj])
        if obj in self.QUOTES:
            return self._obj_quote(inner, obj)
        if obj == "p":
            return self._obj_para(inner)
        return None

    def _obj_word(self, inner, big, n):
        t = self.text()
        i = self.to_index(self.row, self.col)
        if i >= len(t):
            return None
        cls = char_class(t[i], big)
        a = i
        while a > 0 and t[a - 1] != "\n" and char_class(t[a - 1], big) == cls:
            a -= 1
        b = i
        while b + 1 < len(t) and t[b + 1] != "\n" and char_class(t[b + 1], big) == cls:
            b += 1
        for _ in range(n - 1):
            j = b + 1
            if j < len(t) and t[j] != "\n":
                cls2 = char_class(t[j], big)
                while b + 1 < len(t) and t[b + 1] != "\n" and char_class(t[b + 1], big) == cls2:
                    b += 1
        if not inner:
            # aw: include trailing whitespace, else leading
            e = b
            grew = False
            while e + 1 < len(t) and t[e + 1] in " \t":
                e += 1
                grew = True
            if grew:
                b = e
            else:
                while a > 0 and t[a - 1] in " \t":
                    a -= 1
        return (self.from_index(a), self.from_index(b), "incl")

    def _obj_pair(self, inner, o, c):
        t = self.text()
        i = self.to_index(self.row, self.col)
        # find enclosing open
        depth = 0
        a = -1
        j = i
        if j < len(t) and t[j] == o:
            a = j
        else:
            while j >= 0:
                if t[j] == c and j != i:
                    depth += 1
                elif t[j] == o:
                    if depth == 0:
                        a = j
                        break
                    depth -= 1
                j -= 1
        if a < 0:
            return None
        depth = 0
        b = -1
        j = a + 1
        while j < len(t):
            if t[j] == o:
                depth += 1
            elif t[j] == c:
                if depth == 0:
                    b = j
                    break
                depth -= 1
            j += 1
        if b < 0:
            return None
        if inner:
            if a + 1 > b - 1:
                return (self.from_index(a + 1), self.from_index(a), "excl-empty")
            # Vim special case: when the open brace ends its line and the close
            # brace starts its own, the inner object becomes linewise.
            head = t[a + 1 :]
            nl = head.find("\n")
            tail_start = t.rfind("\n", 0, b)
            if nl != -1 and not head[:nl].strip() and tail_start != -1 and not t[tail_start + 1 : b].strip():
                r1 = self.from_index(a + 1 + nl + 1)[0]
                r2 = self.from_index(tail_start)[0]
                if r1 <= r2:
                    return ((r1, 0), (r2, 0), "line")
            return (self.from_index(a + 1), self.from_index(b - 1), "incl")
        return (self.from_index(a), self.from_index(b), "incl")

    def _obj_quote(self, inner, q):
        line = self.line
        positions = [m.start() for m in re.finditer(re.escape(q), line)]
        positions = [p for p in positions if p == 0 or line[p - 1] != "\\"]
        if len(positions) < 2:
            return None
        for k in range(0, len(positions) - 1, 2):
            a, b = positions[k], positions[k + 1]
            if self.col <= b:
                if inner:
                    if a + 1 > b - 1:
                        return ((self.row, a + 1), (self.row, a), "excl-empty")
                    return ((self.row, a + 1), (self.row, b - 1), "incl")
                return ((self.row, a), (self.row, b), "incl")
        return None

    def _obj_para(self, inner):
        r = self.row
        blank = lambda i: not self.lines[i].strip()
        cur_blank = blank(r)
        a = r
        while a > 0 and blank(a - 1) == cur_blank:
            a -= 1
        b = r
        while b + 1 < len(self.lines) and blank(b + 1) == cur_blank:
            b += 1
        if not inner:
            e = b
            while e + 1 < len(self.lines) and blank(e + 1) != cur_blank:
                e += 1
            if e != b:
                b = e
        return ((a, 0), (b, 0), "line")

    # ---- motions -------------------------------------------------------
    def _first_nonblank(self, r):
        line = self.lines[r]
        m = re.match(r"[ \t]*", line)
        return min(m.end(), max(0, len(line) - 1)) if line else 0

    def motion(self, m: str, n: int = 1, for_operator=False):
        """Return ((row,col), kind) | None | 'incomplete'.

        kind: 'excl' | 'incl' | 'line'
        """
        c = m[0]
        t = self.text()
        idx = self.to_index(self.row, self.col)

        if c == "h":
            return ((self.row, max(0, self.col - n)), "excl")
        if c == "l":
            lim = len(self.line) if for_operator else max(0, len(self.line) - 1)
            return ((self.row, min(lim, self.col + n)), "excl")
        if c == " ":
            return ((self.row, min(len(self.line), self.col + n)), "excl")
        if c in "jk":
            r = self.row + (n if c == "j" else -n)
            if r < 0 or r > len(self.lines) - 1:
                self.failed = True
                return None
            r = max(0, min(r, len(self.lines) - 1))
            col = min(max(self.desired_col, self.col), max(0, len(self.lines[r]) - 1))
            return ((r, col), "line")
        if c == "+" or c == "\r":
            r = min(len(self.lines) - 1, self.row + n)
            return ((r, self._first_nonblank(r)), "line")
        if c == "-":
            r = max(0, self.row - n)
            return ((r, self._first_nonblank(r)), "line")
        if c == "_":
            r = min(len(self.lines) - 1, self.row + n - 1)
            return ((r, self._first_nonblank(r)), "line")
        if c == "0":
            return ((self.row, 0), "excl")
        if c == "^":
            return ((self.row, self._first_nonblank(self.row)), "excl")
        if c == "$":
            r = min(len(self.lines) - 1, self.row + n - 1)
            return ((r, max(0, len(self.lines[r]) - (0 if for_operator else 1))), "incl")
        if c == "G":
            r = (n - 1) if m == "G" and n != 1 else (len(self.lines) - 1 if n == 1 else n - 1)
            r = max(0, min(r, len(self.lines) - 1))
            return ((r, self._first_nonblank(r)), "line")
        if c == "H":
            return ((0, self._first_nonblank(0)), "line")
        if c == "L":
            r = len(self.lines) - 1
            return ((r, self._first_nonblank(r)), "line")
        if c == "M":
            r = len(self.lines) // 2
            return ((r, self._first_nonblank(r)), "line")
        if c == "|":
            return ((self.row, max(0, min(n - 1, len(self.line) - 1))), "excl")
        if c in "wW":
            big = c == "W"
            i = idx
            for _ in range(n):
                i = self._next_word_start(t, i, big)
            if for_operator and n >= 1:
                # dw at end of word must not eat the newline
                r0, _c0 = self.row, self.col
                r1, _c1 = self.from_index(i)
                if r1 > r0 and t[max(0, i - 1)] == "\n":
                    k = i
                    while k > 0 and t[k - 1] in " \t\n":
                        k -= 1
                    if k > idx:
                        i = k
            return (self.from_index(i), "excl")
        if c in "bB":
            i = idx
            for _ in range(n):
                i = self._prev_word_start(t, i, c == "B")
            return (self.from_index(i), "excl")
        if c in "eE":
            i = idx
            for _ in range(n):
                i = self._next_word_end(t, i, c == "E")
            return (self.from_index(i), "incl")
        if m == "ge" or m == "gE":
            i = idx
            for _ in range(n):
                i = self._prev_word_end(t, i, m == "gE")
            return (self.from_index(i), "incl")
        if c in "fFtT":
            if len(m) < 2:
                return "incomplete"
            target = m[1]
            self.last_ft = (c, target)
            return self._do_ft(c, target, n, for_operator)
        if c in ";,":
            if not self.last_ft:
                return None
            k, target = self.last_ft
            if c == ",":
                k = {"f": "F", "F": "f", "t": "T", "T": "t"}[k]
            return self._do_ft(k, target, n, for_operator, repeat=True)
        if c == "{":
            return (self._para_move(-1, n), "excl")
        if c == "}":
            return (self._para_move(1, n), "excl")
        if c == "%":
            return self._match_pair()
        if c == "`":
            if len(m) < 2:
                return "incomplete"
            p = self.marks.get(m[1])
            return (p, "excl") if p else None
        if c == "'":
            if len(m) < 2:
                return "incomplete"
            p = self.marks.get(m[1])
            return ((p[0], self._first_nonblank(p[0])), "line") if p else None
        if c == "n" or c == "N":
            if not self.last_search:
                self.failed = True
                return None
            pat, direction = self.last_search
            d = direction if c == "n" else ("?" if direction == "/" else "/")
            p = self._search(pat, d)
            if not p:
                self.failed = True
            return (p, "excl") if p else None
        if c in "*#":
            word = self._word_under_cursor()
            if not word:
                self.failed = True
                return None
            self.last_search = (r"\<" + re.escape(word) + r"\>", "/" if c == "*" else "?")
            p = self._search(*self.last_search)
            if not p:
                self.failed = True
            return (p, "excl") if p else None
        if c == "g":
            if m == "g":
                return "incomplete"
            if m == "gg":
                r = max(0, min(n - 1, len(self.lines) - 1))
                return ((r, self._first_nonblank(r)), "line")
            if m in ("g_",):
                line = self.line
                return ((self.row, max(0, len(line.rstrip()) - 1)), "incl")
            return None
        return None

    def _word_under_cursor(self):
        line = self.line
        i = self.col
        while i < len(line) and not WORD_RE.match(line[i]):
            i += 1
        if i >= len(line):
            return ""
        a = i
        while a > 0 and WORD_RE.match(line[a - 1]):
            a -= 1
        b = i
        while b + 1 < len(line) and WORD_RE.match(line[b + 1]):
            b += 1
        return line[a : b + 1]

    def _do_ft(self, kind, target, n, for_operator, repeat=False):
        line = self.line
        col = self.col
        if kind in "ft":
            pos = col
            for _ in range(n):
                start = pos + 1
                if kind == "t" and repeat and n == 1:
                    start = pos + 2
                found = line.find(target, start)
                if found == -1:
                    self.failed = True
                    return None
                pos = found
            if kind == "t":
                pos -= 1
            return ((self.row, pos), "incl")
        else:
            pos = col
            for _ in range(n):
                start = pos - 1
                if kind == "T" and repeat and n == 1:
                    start = pos - 2
                found = line.rfind(target, 0, max(0, start + 1))
                if found == -1:
                    self.failed = True
                    return None
                pos = found
            if kind == "T":
                pos += 1
            return ((self.row, pos), "excl")

    def _para_move(self, direction, n):
        r = self.row
        for _ in range(n):
            r += direction
            while 0 < r < len(self.lines) - 1 and self.lines[r].strip():
                r += direction
            r = max(0, min(r, len(self.lines) - 1))
        return (r, 0)

    def _match_pair(self):
        line = self.line
        opens, closes = "([{", ")]}"
        i = self.col
        while i < len(line) and line[i] not in opens + closes:
            i += 1
        if i >= len(line):
            return None
        ch = line[i]
        t = self.text()
        idx = self.to_index(self.row, i)
        if ch in opens:
            o, c, step = ch, closes[opens.index(ch)], 1
        else:
            c, o, step = ch, opens[closes.index(ch)], -1
        depth = 0
        j = idx
        while 0 <= j < len(t):
            if t[j] == (o if step == 1 else c):
                depth += 1
            elif t[j] == (c if step == 1 else o):
                depth -= 1
                if depth == 0:
                    return (self.from_index(j), "incl")
            j += step
        return None

    # word helpers on the flat text
    @staticmethod
    def _next_word_start(t, i, big):
        n = len(t)
        if i >= n:
            return n
        cls = char_class(t[i], big)
        if cls != 0:
            while i < n and char_class(t[i], big) == cls and t[i] != "\n":
                i += 1
        while i < n and char_class(t[i], big) == 0:
            if t[i] == "\n" and i + 1 < n and t[i + 1] == "\n":
                return i + 1
            i += 1
        return min(i, n)

    @staticmethod
    def _prev_word_start(t, i, big):
        i -= 1
        while i > 0 and char_class(t[i], big) == 0:
            i -= 1
        if i <= 0:
            return 0
        cls = char_class(t[i], big)
        while i > 0 and char_class(t[i - 1], big) == cls:
            i -= 1
        return max(0, i)

    @staticmethod
    def _next_word_end(t, i, big):
        n = len(t)
        i += 1
        while i < n and char_class(t[i], big) == 0:
            i += 1
        if i >= n:
            return n - 1
        cls = char_class(t[i], big)
        while i + 1 < n and char_class(t[i + 1], big) == cls:
            i += 1
        return i

    @staticmethod
    def _prev_word_end(t, i, big):
        i -= 1
        while i > 0 and char_class(t[i], big) == 0:
            i -= 1
        return max(0, i)

    # ---- search ---------------------------------------------------------
    def _search(self, pat, direction, from_pos=None):
        t = self.text()
        try:
            rx = re.compile(self._vim_re(pat))
        except re.error:
            return None
        start = self.to_index(self.row, self.col) if from_pos is None else from_pos
        hits = [m.start() for m in rx.finditer(t)]
        if not hits:
            return None
        if direction == "/":
            nxt = [h for h in hits if h > start]
            return self.from_index(nxt[0] if nxt else hits[0])
        prv = [h for h in hits if h < start]
        return self.from_index(prv[-1] if prv else hits[-1])

    @staticmethod
    def _vim_re(pat):
        # a small translation of Vim regex atoms we actually teach
        out = pat.replace(r"\<", r"\b").replace(r"\>", r"\b")
        out = re.sub(r"\\\((.*?)\\\)", r"(\1)", out)
        out = out.replace(r"\+", "+").replace(r"\?", "?").replace(r"\|", "|")
        out = out.replace(r"\{", "{").replace(r"\}", "}")
        return out

    def _do_search(self, pat, direction):
        if pat:
            self.last_search = (pat, direction)
        elif self.last_search:
            pat, direction = self.last_search[0], direction
        p = self._search(pat, direction)
        if p:
            self.row, self.col = p
            self.clamp()
        else:
            self.message = f"E486: Pattern not found: {pat}"

    # ---- ex commands -----------------------------------------------------
    def _ex(self, cmd: str):
        cmd = cmd.strip()
        if not cmd:
            return
        # range
        rng = None
        m = re.match(r"^(%|\d+,\d+|\.,\$|'<,'>|\.,\.\+\d+|\d+)(.*)$", cmd)
        body = cmd
        if m:
            rng, body = m.group(1), m.group(2)
        body = body.strip()

        def resolve(r):
            if r is None:
                return (self.row, self.row)
            if r == "%":
                return (0, len(self.lines) - 1)
            if r == "'<,'>":
                s, e = self.visual_range() if self.visual_start else ((self.row, 0), (self.row, 0))
                return (s[0], e[0])
            if r == ".,$":
                return (self.row, len(self.lines) - 1)
            if "," in r:
                a, b = r.split(",")
                if b.startswith(".+"):
                    return (self.row, min(len(self.lines) - 1, self.row + int(b[2:])))
                return (int(a) - 1, int(b) - 1)
            return (int(r) - 1, int(r) - 1)

        # :s substitute
        ms = re.match(r"^s([^A-Za-z0-9 ])(.*)$", body)
        if ms:
            sep = ms.group(1)
            parts = re.split(r"(?<!\\)" + re.escape(sep), ms.group(2))
            pat = parts[0] if parts else ""
            rep = parts[1] if len(parts) > 1 else ""
            flags = parts[2] if len(parts) > 2 else ""
            a, b = resolve(rng)
            self.push_undo()
            count = 0
            try:
                rx = re.compile(self._vim_re(pat))
            except re.error:
                self.message = "E486: invalid pattern"
                return
            pyrep = re.sub(r"\\(\d)", r"\\\1", rep).replace("&", r"\g<0>") if "&" in rep else re.sub(r"\\(\d)", r"\\\1", rep)
            for r in range(a, min(b + 1, len(self.lines))):
                new, k = rx.subn(pyrep, self.lines[r], count=0 if "g" in flags else 1)
                if k:
                    self.lines[r] = new
                    count += k
                    self.row = r
            self.message = f"{count} substitution(s)" if count else (
                "" if "e" in flags else f"E486: Pattern not found: {pat}"
            )
            self.clamp()
            return

        # :g/pat/cmd
        mg = re.match(r"^(g|v|global|vglobal)(!?)/(.*)$", body)
        if mg:
            invert = mg.group(1) in ("v", "vglobal") or mg.group(2) == "!"
            rest = mg.group(3)
            parts = re.split(r"(?<!\\)/", rest, maxsplit=1)
            pat = parts[0]
            sub = parts[1] if len(parts) > 1 else "p"
            a, b = resolve(rng if rng else "%")
            try:
                rx = re.compile(self._vim_re(pat))
            except re.error:
                return
            self.push_undo()
            targets = [
                r for r in range(a, min(b + 1, len(self.lines)))
                if bool(rx.search(self.lines[r])) != invert
            ]
            if sub.strip() in ("d", "delete"):
                for r in reversed(targets):
                    del self.lines[r]
                if not self.lines:
                    self.lines = [""]
            elif sub.startswith("normal ") or sub.startswith("norm "):
                keys = sub.split(" ", 1)[1]
                for r in reversed(targets):
                    self.row, self.col = r, 0
                    self._run_normal(keys)
            elif sub.startswith("s"):
                for r in targets:
                    self.row = r
                    self._ex(f"{r+1}{sub}")
            self.clamp()
            return

        # :normal
        mn = re.match(r"^(normal|norm)!?\s+(.*)$", body)
        if mn:
            keys = mn.group(2)
            a, b = resolve(rng) if rng else (self.row, self.row)
            self.push_undo()
            for r in range(a, min(b + 1, len(self.lines))):
                self.row, self.col = r, 0
                self._run_normal(keys)
            self.clamp()
            return

        # :d :y :m :t/:co :sort :j
        if re.fullmatch(r"d(elete)?", body):
            a, b = resolve(rng)
            self.push_undo()
            self.set_register(None, "\n".join(self.lines[a : b + 1]) + "\n", "line")
            del self.lines[a : b + 1]
            if not self.lines:
                self.lines = [""]
            self.row = min(a, len(self.lines) - 1)
            self.clamp()
            return
        mm = re.fullmatch(r"(m|move|t|co|copy)\s*(\S+)", body)
        if mm:
            a, b = resolve(rng)
            dest = mm.group(2)
            d = len(self.lines) - 1 if dest == "$" else (-1 if dest == "0" else int(dest) - 1)
            block = self.lines[a : b + 1]
            self.push_undo()
            if mm.group(1) in ("m", "move"):
                del self.lines[a : b + 1]
                if d > b:
                    d -= b - a + 1
                self.lines[d + 1 : d + 1] = block
                self.row = d + len(block)
            else:
                self.lines[d + 1 : d + 1] = block
                self.row = d + len(block)
            self.clamp()
            return
        if re.fullmatch(r"sort(\s+u)?", body):
            a, b = resolve(rng if rng else "%")
            self.push_undo()
            block = sorted(self.lines[a : b + 1])
            if body.strip().endswith("u"):
                seen, uniq = set(), []
                for x in block:
                    if x not in seen:
                        seen.add(x)
                        uniq.append(x)
                block = uniq
            self.lines[a : b + 1] = block
            self.clamp()
            return
        if re.fullmatch(r"(w|write|wq|x|q|q!|wa|xa)", body):
            if body[0] in "wx":
                self.written = True
                self.message = '"buffer" written'
            if body in ("q", "q!", "wq", "x", "xa"):
                self.quit = True
            return
        if re.fullmatch(r"noh(l|lsearch)?", body):
            return
        if re.fullmatch(r"set\s+.*", body):
            self.message = body
            return
        if re.fullmatch(r"\d+", cmd):
            r = max(0, min(int(cmd) - 1, len(self.lines) - 1))
            self.row, self.col = r, self._first_nonblank(r)
            return
        self.message = f"E492: Not an editor command: {body}"

    def _run_normal(self, keys):
        """Execute keys as if typed in normal mode (used by :normal, macros)."""
        if self._depth > 20:
            return
        self._depth += 1
        try:
            saved = self.pending
            self.pending = []
            for k in parse_keys(keys):
                self.key(k)
                if self.failed:
                    break
            if self.mode == "insert":
                self.key("\x1b")
            self.pending = saved
        finally:
            self._depth -= 1

    # ---- simple commands -------------------------------------------------
    def _simple(self, s: str, count, reg, vis) -> str:
        n = count or 1
        c = s[0]

        # counts already stripped; handle multi-char prefixes first
        if c == "g":
            if len(s) == 1:
                return "incomplete"
            two = s[:2]
            if two == "gg":
                r = max(0, min((count - 1) if count else 0, len(self.lines) - 1))
                self.row, self.col = r, self._first_nonblank(r)
                if vis:
                    return "done"
                self.clamp()
                return "done"
            if two == "gJ":
                return self._join(n, spaces=False)
            if two == "gv":
                if self.last_visual:
                    mode, s, e = self.last_visual
                    self.mode = mode
                    self.visual_start = s
                    self.row, self.col = e
                    self.clamp()
                return "done"
            if two in ("gu", "gU", "g~"):
                return "incomplete"
            return "invalid"

        if c == "Z":
            if len(s) == 1:
                return "incomplete"
            if s[:2] in ("ZZ", "ZQ"):
                self.written = s[:2] == "ZZ"
                self.quit = True
                return "done"
            return "invalid"

        if c == "m":
            if len(s) == 1:
                return "incomplete"
            self.marks[s[1]] = (self.row, self.col)
            return "done"

        if c == "r":
            if len(s) == 1:
                return "incomplete"
            ch = s[1]
            self.push_undo()
            if vis:
                sv, ev = self.visual_range()
                if self.mode == "vline":
                    for r in range(sv[0], ev[0] + 1):
                        self.lines[r] = ch * len(self.lines[r])
                else:
                    a, b = self.to_index(*sv), self.to_index(*ev) + 1
                    t = self.text()
                    mid = "".join(ch if x != "\n" else "\n" for x in t[a:b])
                    self.lines = (t[:a] + mid + t[b:]).split("\n")
                    self.row, self.col = sv
                self.mode = "normal"
                self.visual_start = None
                self.clamp()
                return "done"
            line = self.line
            if self.col + n > len(line):
                return "done"
            self.lines[self.row] = line[: self.col] + ch * n + line[self.col + n :]
            self.col += n - 1
            self._register_dot()
            return "done"

        if c == "q":
            if self.recording_reg is not None:
                self.registers[self.recording_reg] = ("".join(self.recorded), "macro")
                self.recording_reg = None
                self.recorded = []
                return "done"
            if len(s) == 1:
                return "incomplete"
            self.recording_reg = s[1]
            self.recorded = []
            return "done"

        if c == "@":
            if len(s) == 1:
                return "incomplete"
            r = s[1]
            if r == "@":
                r = self.last_macro
                if not r:
                    return "done"
            self.last_macro = r
            body = self.registers.get(r, ("", ""))[0]
            for _ in range(n):
                self.failed = False
                self._run_normal(body)
                if self.failed:
                    break
            self.failed = False
            return "done"

        if c == '"':
            return "incomplete"

        # visual-mode-only quick keys
        if vis:
            if c in "oO":
                self.visual_start, (self.row, self.col) = (self.row, self.col), self.visual_start
                return "done"
            if c in "ia" and len(s) >= 2:
                rng = self.text_object(c, s[1], n)
                if rng:
                    self.visual_start = rng[0]
                    self.row, self.col = rng[1]
                return "done"
            if c in "ia":
                return "incomplete"
            if c == "x":
                return self._apply_operator_visual("d", reg)
            if c == "s":
                return self._apply_operator_visual("c", reg)
            if c in "DXR":
                self.mode = "vline" if self.mode != "vline" else self.mode
                return self._apply_operator_visual("d", reg)
            if c == "C":
                self.mode = "vline"
                return self._apply_operator_visual("c", reg)
            if c == "Y":
                self.mode = "vline"
                return self._apply_operator_visual("y", reg)
            if c == "J":
                sv, ev = self.visual_range()
                self.mode = "normal"
                self.visual_start = None
                self.row = sv[0]
                return self._join(max(2, ev[0] - sv[0] + 1))
            if c == "u":
                return self._apply_operator_visual("gu", reg)
            if c == "U":
                return self._apply_operator_visual("gU", reg)
            if c == "~":
                return self._apply_operator_visual("g~", reg)
            if c == "p" or c == "P":
                sv, ev = self.visual_range()
                txt, kind = self.get_register(reg)
                self._apply_operator_visual("d", "_")
                self._paste(txt, kind, before=True)
                return "done"
            if c == "I" and self.mode == "vblock":
                r1, r2, c1, c2 = self._vblock_cols()
                self._save_visual()
                self.push_undo()
                self.mode = "insert"
                self.visual_start = None
                self.row, self.col = r1, c1
                self._block_insert = (r1, r2, c1, False)
                self._begin_change([])
                return "done"
            if c == "A" and self.mode == "vblock":
                r1, r2, c1, c2 = self._vblock_cols()
                self._save_visual()
                self.push_undo()
                self.mode = "insert"
                self.visual_start = None
                self.row, self.col = r1, min(len(self.lines[r1]), c2 + 1)
                self._block_insert = (r1, r2, c2 + 1, True)
                self._begin_change([])
                return "done"

        # mode switches
        if c == "i" and not vis:
            self.push_undo()
            self.mode = "insert"
            self._begin_change(list(self.pending))
            return "done"
        if c == "a" and not vis:
            self.push_undo()
            self.mode = "insert"
            self.col = min(len(self.line), self.col + 1)
            self._begin_change(list(self.pending))
            return "done"
        if c == "I":
            self.push_undo()
            self.mode = "insert"
            self.col = self._first_nonblank(self.row) if self.line.strip() else 0
            self._begin_change(list(self.pending))
            return "done"
        if c == "A":
            self.push_undo()
            self.mode = "insert"
            self.col = len(self.line)
            self._begin_change(list(self.pending))
            return "done"
        if c == "o" or c == "O":
            self.push_undo()
            indent = re.match(r"[ \t]*", self.line).group(0)
            at = self.row + 1 if c == "o" else self.row
            self.lines.insert(at, indent)
            self.row, self.col = at, len(indent)
            self.mode = "insert"
            self._begin_change(list(self.pending))
            return "done"
        if c == "R":
            self.push_undo()
            self.mode = "replace"
            self._begin_change(list(self.pending))
            return "done"
        if c == "v":
            self.mode = "visual"
            self.visual_start = (self.row, self.col)
            return "done"
        if c == "V":
            self.mode = "vline"
            self.visual_start = (self.row, self.col)
            return "done"
        if c == "\x16":  # <C-v>
            self.mode = "vblock"
            self.visual_start = (self.row, self.col)
            return "done"
        if c == ":":
            self.mode = "cmdline"
            self.cmdtype = ":"
            self.cmdline = "'<,'>" if vis else ""
            if vis:
                self.mode = "cmdline"
            return "done"
        if c in "/?":
            self.mode = "cmdline"
            self.cmdtype = c
            self.cmdline = ""
            return "done"

        # edits
        if c == "x":
            self.push_undo()
            line = self.line
            if not line:
                return "done"
            end = min(len(line), self.col + n)
            self.set_register(reg, line[self.col : end], "char")
            self.lines[self.row] = line[: self.col] + line[end:]
            self.clamp()
            self._register_dot()
            return "done"
        if c == "X":
            self.push_undo()
            line = self.line
            start = max(0, self.col - n)
            self.set_register(reg, line[start : self.col], "char")
            self.lines[self.row] = line[:start] + line[self.col :]
            self.col = start
            self._register_dot()
            return "done"
        if c == "s":
            self.push_undo()
            line = self.line
            end = min(len(line), self.col + n)
            self.set_register(reg, line[self.col : end], "char")
            self.lines[self.row] = line[: self.col] + line[end:]
            self.mode = "insert"
            self._begin_change(list(self.pending))
            return "done"
        if c == "S":
            return self._operator_pending("c", "c", count, reg)
        if c == "D":
            self.push_undo()
            line = self.line
            self.set_register(reg, line[self.col :], "char")
            self.lines[self.row] = line[: self.col]
            self.clamp()
            self._register_dot()
            return "done"
        if c == "C":
            self.push_undo()
            line = self.line
            self.set_register(reg, line[self.col :], "char")
            self.lines[self.row] = line[: self.col]
            self.mode = "insert"
            self._begin_change(list(self.pending))
            return "done"
        if c == "Y":
            return self._operator_pending("y", "y", count, reg)
        if c == "J":
            return self._join(max(2, n))
        if c == "~":
            self.push_undo()
            line = self.line
            end = min(len(line), self.col + n)
            self.lines[self.row] = line[: self.col] + line[self.col : end].swapcase() + line[end:]
            self.col = min(end, max(0, len(line) - 1))
            self._register_dot()
            return "done"
        if c == "p" or c == "P":
            self.push_undo()
            txt, kind = self.get_register(reg)
            if not txt:
                return "done"
            for _ in range(n):
                self._paste(txt, kind, before=(c == "P"))
            self._register_dot()
            return "done"
        if c == "\x01" or c == "\x18":  # <C-a> / <C-x>
            delta = n if c == "\x01" else -n
            line = self.line
            m = None
            for cand in re.finditer(r"-?\d+", line):
                if cand.end() > self.col:
                    m = cand
                    break
            if not m:
                self.failed = True
                return "done"
            self.push_undo()
            new = str(int(m.group(0)) + delta)
            self.lines[self.row] = line[: m.start()] + new + line[m.end() :]
            self.col = m.start() + len(new) - 1
            self._register_dot()
            return "done"
        if c == "u":
            self.undo()
            return "done"
        if c == "\x12":  # <C-r>
            self.redo()
            return "done"
        if c == ".":
            if self.last_change:
                keys = list(self.last_change)
                self.last_change = None
                self._run_normal("".join(keys))
                self.last_change = keys
            return "done"
        if c == "\x04" or c == "\x15" or c == "\x06" or c == "\x02":
            step = {"\x04": 10, "\x15": -10, "\x06": 20, "\x02": -20}[c]
            self.row = max(0, min(len(self.lines) - 1, self.row + step))
            self.clamp()
            return "done"

        # plain motions
        res = self.motion(s, n, for_operator=False)
        if res == "incomplete":
            return "incomplete"
        if res is None:
            return "done"
        (r, col), kind = res
        self.row, self.col = r, col
        if s[0] not in "jk":
            self.desired_col = self.col
        if s[0] == "$":
            self.desired_col = 10**6
        self.clamp()
        return "done"

    def _join(self, n, spaces=True):
        self.push_undo()
        for _ in range(max(1, n - 1)):
            if self.row + 1 >= len(self.lines):
                break
            cur = self.lines[self.row]
            nxt = self.lines.pop(self.row + 1)
            if spaces:
                joined = cur.rstrip() + (" " if cur.strip() and nxt.strip() else "") + nxt.lstrip()
                self.col = len(cur.rstrip())
            else:
                joined = cur + nxt
                self.col = len(cur)
            self.lines[self.row] = joined
        self.clamp()
        self._register_dot()
        return "done"

    def _paste(self, txt, kind, before=False):
        if kind == "line":
            body = txt[:-1].split("\n") if txt.endswith("\n") else txt.split("\n")
            at = self.row if before else self.row + 1
            self.lines[at:at] = body
            self.row = at
            self.col = self._first_nonblank(self.row)
        elif kind == "block":
            body = txt.split("\n")
            c = self.col + (0 if before else 1)
            for i, chunk in enumerate(body):
                r = self.row + i
                while r >= len(self.lines):
                    self.lines.append("")
                line = self.lines[r].ljust(c)
                self.lines[r] = line[:c] + chunk + line[c:]
        else:
            line = self.line
            at = self.col if before else min(len(line), self.col + 1)
            if "\n" in txt:
                head, *rest = txt.split("\n")
                tail = line[at:]
                self.lines[self.row] = line[:at] + head
                self.lines[self.row + 1 : self.row + 1] = rest
                self.row += len(rest)
                self.col = max(0, len(rest[-1]) if rest else 0)
                self.lines[self.row] += tail
            else:
                self.lines[self.row] = line[:at] + txt + line[at:]
                self.col = at + len(txt) - 1
        self.clamp()

    # ---- introspection ---------------------------------------------------
    def state(self):
        return {
            "lines": list(self.lines),
            "cursor": [self.row, self.col],
            "mode": self.mode,
            "pending": "".join(self.pending),
            "cmdline": (self.cmdtype + self.cmdline) if self.mode == "cmdline" else "",
            "message": self.message,
            "registers": {k: v[0] for k, v in self.registers.items()},
            "recording": self.recording_reg,
        }


def run(lines, cursor, keys):
    v = Vim(lines, tuple(cursor))
    v.feed(keys)
    return v
