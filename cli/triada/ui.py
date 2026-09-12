"""Curses helpers: colour pairs, a tiny markdown renderer, and a pager."""
from __future__ import annotations

import curses
import re
import textwrap

# colour pair ids
CP_DIM = 1
CP_ACCENT = 2
CP_OK = 3
CP_BAD = 4
CP_TYPING = 5
CP_NVIM = 6
CP_PYTHON = 7
CP_CODE = 8
CP_INV = 9
CP_SEL = 10
CP_HEAD = 11


def init_colors():
    curses.start_color()
    try:
        curses.use_default_colors()
        bg = -1
    except curses.error:
        bg = curses.COLOR_BLACK
    pairs = {
        CP_DIM: curses.COLOR_WHITE,
        CP_ACCENT: curses.COLOR_RED,
        CP_OK: curses.COLOR_GREEN,
        CP_BAD: curses.COLOR_RED,
        CP_TYPING: curses.COLOR_CYAN,
        CP_NVIM: curses.COLOR_BLUE,
        CP_PYTHON: curses.COLOR_YELLOW,
        CP_CODE: curses.COLOR_MAGENTA,
        CP_HEAD: curses.COLOR_CYAN,
    }
    if curses.COLORS >= 256:
        pairs.update({
            CP_DIM: 244, CP_ACCENT: 173, CP_OK: 71, CP_BAD: 167,
            CP_TYPING: 72, CP_NVIM: 74, CP_PYTHON: 179, CP_CODE: 139, CP_HEAD: 109,
        })
    for pid, fg in pairs.items():
        try:
            curses.init_pair(pid, fg, bg)
        except curses.error:
            pass
    try:
        curses.init_pair(CP_INV, curses.COLOR_BLACK, pairs[CP_ACCENT])
        curses.init_pair(CP_SEL, curses.COLOR_BLACK, pairs[CP_NVIM])
    except curses.error:
        pass


def C(pid, attr=0):
    return curses.color_pair(pid) | attr


TRACK_COLOR = {"typing": CP_TYPING, "nvim": CP_NVIM, "python": CP_PYTHON}


def safe_addstr(win, y, x, text, attr=0):
    h, w = win.getmaxyx()
    if y < 0 or y >= h or x >= w:
        return
    text = text.replace("\t", "    ")
    avail = w - x - 1
    if avail <= 0:
        return
    try:
        win.addstr(y, x, text[:avail], attr)
    except curses.error:
        pass


# ---------------------------------------------------------------- markdown
Segment = tuple  # (text, attr)


def render_markdown(src: str, width: int) -> list[list[Segment]]:
    """Return a list of lines; each line is a list of (text, attr) segments."""
    lines: list[list[Segment]] = []
    src_lines = str(src or "").split("\n")
    i = 0

    def inline(s: str) -> list[Segment]:
        out: list[Segment] = []
        for part in re.split(r"(`[^`]+`|\*\*[^*]+\*\*)", s):
            if not part:
                continue
            if part.startswith("`") and part.endswith("`") and len(part) > 1:
                out.append((part[1:-1], C(CP_CODE)))
            elif part.startswith("**") and part.endswith("**"):
                out.append((part[2:-2], curses.A_BOLD))
            else:
                out.append((part, 0))
        return out

    def wrap_segments(segs: list[Segment], indent: str = "") -> list[list[Segment]]:
        """Greedy wrap preserving segment attributes."""
        out: list[list[Segment]] = []
        cur: list[Segment] = []
        col = len(indent)
        if indent:
            cur.append((indent, 0))
        for text, attr in segs:
            for word in re.split(r"(\s+)", text):
                if not word:
                    continue
                if word.isspace():
                    if cur and col < width:
                        cur.append((" ", attr))
                        col += 1
                    continue
                if col + len(word) > width and col > len(indent):
                    out.append(cur)
                    cur = [(indent, 0)] if indent else []
                    col = len(indent)
                cur.append((word, attr))
                col += len(word)
        if cur:
            out.append(cur)
        return out or [[]]

    while i < len(src_lines):
        ln = src_lines[i]
        if ln.startswith("```"):
            i += 1
            while i < len(src_lines) and not src_lines[i].startswith("```"):
                lines.append([("  ", 0), (src_lines[i][: width - 2], C(CP_CODE))])
                i += 1
            i += 1
            lines.append([])
            continue
        if ln.startswith("|") and i + 1 < len(src_lines) and re.match(r"^\|[\s:|-]+\|?\s*$", src_lines[i + 1]):
            def cells(row):
                return [c.strip() for c in row.strip().strip("|").split("|")]
            head = cells(ln)
            i += 2
            body = []
            while i < len(src_lines) and src_lines[i].startswith("|"):
                body.append(cells(src_lines[i]))
                i += 1
            ncol = max(len(head), max((len(r) for r in body), default=0))
            widths = []
            for c in range(ncol):
                cw = max([len(strip_md(head[c])) if c < len(head) else 0] +
                         [len(strip_md(r[c])) if c < len(r) else 0 for r in body])
                widths.append(min(cw, max(8, width // max(1, ncol))))
            def row_segs(cs, attr):
                segs = []
                for c in range(ncol):
                    raw = strip_md(cs[c]) if c < len(cs) else ""
                    segs.append((raw[: widths[c]].ljust(widths[c] + 2), attr))
                return segs
            lines.append(row_segs(head, C(CP_DIM, curses.A_BOLD)))
            for r in body:
                lines.append(row_segs(r, 0))
            lines.append([])
            continue
        if re.match(r"^#{1,4} ", ln):
            lines.append([(re.sub(r"^#+ ", "", ln), C(CP_HEAD, curses.A_BOLD))])
            lines.append([])
            i += 1
            continue
        if re.match(r"^\s*[-*] ", ln):
            body = re.sub(r"^\s*[-*] ", "", ln)
            i += 1
            while i < len(src_lines) and re.match(r"^\s{2,}\S", src_lines[i]) and not re.match(r"^\s*[-*] ", src_lines[i]):
                body += " " + src_lines[i].strip()
                i += 1
            segs = [("  • ", C(CP_ACCENT))] + inline(body)
            lines.extend(wrap_segments(segs, ""))
            continue
        if re.match(r"^\s*\d+\. ", ln):
            num = re.match(r"^\s*(\d+)\. ", ln).group(1)
            body = re.sub(r"^\s*\d+\. ", "", ln)
            i += 1
            while i < len(src_lines) and re.match(r"^\s{2,}\S", src_lines[i]) and not re.match(r"^\s*\d+\. ", src_lines[i]):
                body += " " + src_lines[i].strip()
                i += 1
            segs = [(f"  {num}. ", C(CP_ACCENT))] + inline(body)
            lines.extend(wrap_segments(segs, ""))
            continue
        if not ln.strip():
            lines.append([])
            i += 1
            continue
        para = []
        while i < len(src_lines) and src_lines[i].strip() and not re.match(r"^(```|\||#{1,4} |\s*[-*] |\s*\d+\. )", src_lines[i]):
            para.append(src_lines[i])
            i += 1
        lines.extend(wrap_segments(inline(" ".join(para))))
        lines.append([])
    while lines and not lines[-1]:
        lines.pop()
    return lines


def strip_md(s: str) -> str:
    return re.sub(r"[`*]", "", s)


def draw_segments(win, y, x, segs, maxw):
    col = x
    for text, attr in segs:
        if col - x >= maxw:
            break
        safe_addstr(win, y, col, text[: maxw - (col - x)], attr)
        col += len(text)


def wrap(text, width):
    out = []
    for para in str(text).split("\n"):
        out.extend(textwrap.wrap(para, width) or [""])
    return out
