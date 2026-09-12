"""The three exercise runners, in curses."""
from __future__ import annotations

import curses
import os
import subprocess
import sys
import tempfile
import time

from .ui import (CP_ACCENT, CP_BAD, CP_CODE, CP_DIM, CP_HEAD, CP_INV, CP_NVIM,
                 CP_OK, CP_SEL, C, draw_segments, render_markdown, safe_addstr)
from .vimengine import Vim, parse_keys

BACKSPACES = (curses.KEY_BACKSPACE, 127, 8, "\x7f", "\b")


def is_esc(k):
    """get_wch() gives Escape as the string '\x1b'; getch() gives 27."""
    return k == 27 or k == "\x1b"


def teach_block(win, y, text, width, max_lines):
    """Draw teaching text, return the number of lines used."""
    lines = render_markdown(text, width)
    shown = lines[:max_lines]
    for i, segs in enumerate(shown):
        draw_segments(win, y + i, 2, segs, width)
    if len(lines) > max_lines:
        safe_addstr(win, y + max_lines, 2, "… press t for the full explanation", C(CP_DIM))
        return max_lines + 1
    return len(shown)


def pager(stdscr, title, text):
    """Full-screen scrollable view of a markdown block."""
    top = 0
    while True:
        stdscr.erase()
        h, w = stdscr.getmaxyx()
        width = min(96, w - 6)
        lines = render_markdown(text, width)
        safe_addstr(stdscr, 0, 2, title, C(CP_HEAD, curses.A_BOLD))
        body_h = h - 3
        for i in range(body_h):
            if top + i >= len(lines):
                break
            draw_segments(stdscr, 2 + i, 2, lines[top + i], width)
        pos = f"{min(top + body_h, len(lines))}/{len(lines)}"
        safe_addstr(stdscr, h - 1, 2, f"j/k scroll · space page · q back    {pos}", C(CP_DIM))
        stdscr.refresh()
        k = stdscr.getch()
        if k in (ord("q"), 27, curses.KEY_LEFT):
            return
        if k in (ord("j"), curses.KEY_DOWN):
            top = min(max(0, len(lines) - body_h), top + 1)
        elif k in (ord("k"), curses.KEY_UP):
            top = max(0, top - 1)
        elif k in (ord(" "), curses.KEY_NPAGE):
            top = min(max(0, len(lines) - body_h), top + body_h)
        elif k in (curses.KEY_PPAGE,):
            top = max(0, top - body_h)
        elif k in (ord("g"),):
            top = 0
        elif k in (ord("G"),):
            top = max(0, len(lines) - body_h)


# ============================================================== TYPING
def run_typing(stdscr, lesson, level, progress, track="typing"):
    target = lesson["content"]
    chars = list(target)
    typed: list[str] = []
    started = None
    first_wrong: set[int] = set()
    err_keys: dict[str, int] = {}
    passcrit = lesson.get("pass") or (level or {}).get("pass") or {"wpm": 25, "acc": 0.95}
    result = None

    stdscr.nodelay(False)
    curses.curs_set(0)

    def metrics():
        correct = sum(1 for i, c in enumerate(typed) if i < len(chars) and c == chars[i])
        acc = (len(typed) - len(first_wrong)) / len(typed) if typed else 1.0
        mins = (time.time() - started) / 60 if started else 0
        wpm = int((correct / 5) / mins) if mins > 0.002 else 0
        return correct, max(0.0, acc), wpm

    while True:
        stdscr.erase()
        h, w = stdscr.getmaxyx()
        width = min(92, w - 6)
        correct, acc, wpm = metrics()

        safe_addstr(stdscr, 0, 2, lesson["title"], C(CP_HEAD, curses.A_BOLD))
        safe_addstr(stdscr, 0, w - 34,
                    f"{wpm:3d} wpm  {acc * 100:5.1f}%  target {passcrit['wpm']}/{int(passcrit['acc'] * 100)}%",
                    C(CP_OK if (wpm >= passcrit["wpm"] and acc >= passcrit["acc"]) else CP_DIM))

        y = 2
        if lesson.get("teach"):
            y += teach_block(stdscr, y, lesson["teach"], width, 3) + 1

        # lay the target text out, wrapping on spaces
        row, col = y, 2
        for i, ch in enumerate(chars):
            if ch == "\n":
                if i == len(typed):
                    safe_addstr(stdscr, row, col, "⏎", C(CP_INV))
                else:
                    safe_addstr(stdscr, row, col, "⏎", C(CP_DIM))
                row += 1
                col = 2
                continue
            if col >= width and ch == " ":
                row += 1
                col = 2
                continue
            if col >= width + 6:
                row += 1
                col = 2
            if i < len(typed):
                attr = 0 if typed[i] == ch else C(CP_BAD, curses.A_REVERSE)
            else:
                attr = C(CP_DIM)
            if i == len(typed):
                attr = C(CP_INV)
            safe_addstr(stdscr, row, col, ch, attr)
            col += 1
        if len(typed) > len(chars):
            safe_addstr(stdscr, row, col, "".join(typed[len(chars):]), C(CP_BAD, curses.A_REVERSE))

        row += 2
        nxt = chars[len(typed)] if len(typed) < len(chars) else None
        if nxt is not None:
            from .keyboard import key_hint
            label = "␣" if nxt == " " else "↵" if nxt == "\n" else nxt
            safe_addstr(stdscr, row, 2, f"next  {label}   {key_hint(nxt)}", C(CP_ACCENT))
        row += 2

        if result:
            safe_addstr(stdscr, row, 2, result[0], C(CP_OK if result[1] else CP_BAD, curses.A_BOLD))
            row += 1
            if err_keys:
                worst = sorted(err_keys, key=lambda k: -err_keys[k])[:10]
                txt = "  ".join(
                    ("␣" if k == " " else "↵" if k == "\n" else k) + f"×{err_keys[k]}" for k in worst
                )
                safe_addstr(stdscr, row, 2, "missed: " + txt, C(CP_DIM))
                row += 1

        safe_addstr(stdscr, h - 1, 2,
                    "type it · ^R restart · ^N next · Esc back", C(CP_DIM))
        stdscr.refresh()

        try:
            k = stdscr.get_wch()
        except curses.error:
            continue
        except KeyboardInterrupt:
            return "back"

        if k == "\x12":  # ^R
            typed, started, first_wrong, err_keys, result = [], None, set(), {}, None
            continue
        if k == "\x0e":  # ^N
            return "next"
        if k == 27:
            return "back"
        if isinstance(k, str) and k == "\x1b":
            return "back"
        if k in BACKSPACES or k == curses.KEY_BACKSPACE:
            if typed:
                typed.pop()
            continue
        if isinstance(k, int):
            if k == curses.KEY_RESIZE:
                continue
            continue
        if k in ("\n", "\r"):
            k = "\n"
            if len(typed) < len(chars) and chars[len(typed)] != "\n":
                continue
        if k == "\t":
            continue
        if len(k) != 1 or (ord(k) < 32 and k != "\n"):
            continue

        i = len(typed)
        if started is None:
            started = time.time()
        if i < len(chars) and k != chars[i]:
            if i not in first_wrong:
                first_wrong.add(i)
                err_keys[chars[i]] = err_keys.get(chars[i], 0) + 1
                progress.bump_key(chars[i])
        typed.append(k)

        if "".join(typed) == target:
            correct, acc, wpm = metrics()
            passed = wpm >= passcrit["wpm"] and acc >= passcrit["acc"]
            if passed:
                progress.mark_done(track, lesson["id"], {"wpm": wpm, "acc": round(acc, 2)})
                result = (f"✓ {wpm} wpm at {acc * 100:.0f}% — passed. ^N for the next lesson.", True)
            else:
                progress.mark_tried(track, lesson["id"])
                result = (f"· {wpm} wpm at {acc * 100:.0f}% — need "
                          f"{passcrit['wpm']} wpm at {int(passcrit['acc'] * 100)}%. ^R to retry, slower.", False)
            progress.save()


# ================================================================= VIM
def run_vim(stdscr, lesson, progress, track="nvim", on_solved=None):
    v = Vim(list(lesson["start"]["lines"]), tuple(lesson["start"]["cursor"]))
    solved = False
    revealed = False
    show_hint = False
    goal = lesson["goal"]
    curses.curs_set(0)

    def check():
        if v.lines != goal["lines"]:
            return False
        if "cursor" in goal and [v.row, v.col] != goal["cursor"]:
            return False
        if goal.get("mode") and v.mode != goal["mode"]:
            return False
        return True

    def draw():
        stdscr.erase()
        h, w = stdscr.getmaxyx()
        half = max(28, (w - 8) // 2)
        safe_addstr(stdscr, 0, 2, lesson["title"], C(CP_HEAD, curses.A_BOLD))
        safe_addstr(stdscr, 0, w - 24, f"keys {v.typed:3d} · par {lesson['par']:3d}", C(CP_DIM))

        y = 2
        if lesson.get("teach"):
            y += teach_block(stdscr, y, lesson["teach"], min(96, w - 6), 4) + 1

        safe_addstr(stdscr, y, 2, "YOUR BUFFER", C(CP_DIM, curses.A_BOLD))
        safe_addstr(stdscr, y, 4 + half, "TARGET", C(CP_DIM, curses.A_BOLD))
        y += 1

        vr = v.visual_range() if v.visual_start else None
        for r, line in enumerate(v.lines):
            if y + r >= h - 4:
                break
            num = str(r + 1) if r == v.row else str(abs(r - v.row))
            safe_addstr(stdscr, y + r, 2, num.rjust(3),
                        C(CP_ACCENT, curses.A_BOLD) if r == v.row else C(CP_DIM))
            x = 6
            body = line if line else " "
            for c, ch in enumerate(body):
                if x - 6 >= half - 2:
                    break
                attr = 0
                if vr:
                    if v.mode == "vline":
                        inside = vr[0][0] <= r <= vr[1][0]
                    elif v.mode == "vblock":
                        r1, r2, c1, c2 = v._vblock_cols()
                        inside = r1 <= r <= r2 and c1 <= c <= c2
                    else:
                        idx = v.to_index(r, c)
                        inside = v.to_index(*vr[0]) <= idx <= v.to_index(*vr[1])
                    if inside:
                        attr = C(CP_SEL)
                if r == v.row and c == v.col:
                    attr = C(CP_INV)
                safe_addstr(stdscr, y + r, x, ch, attr)
                x += 1
            if r == v.row and v.col >= len(line):
                safe_addstr(stdscr, y + r, 6 + len(line), " ", C(CP_INV))

        for r, line in enumerate(goal["lines"]):
            if y + r >= h - 4:
                break
            same = r < len(v.lines) and v.lines[r] == line
            safe_addstr(stdscr, y + r, 4 + half, (line or " ")[: half - 2],
                        C(CP_DIM) if same else C(CP_OK))
        if lesson["kind"] == "move" and goal.get("cursor"):
            safe_addstr(stdscr, y + len(goal["lines"]) + 1, 4 + half,
                        f"cursor → line {goal['cursor'][0] + 1}, col {goal['cursor'][1] + 1}", C(CP_OK))

        sy = y + max(len(v.lines), len(goal["lines"])) + 1
        mode = {"vline": "V-LINE", "vblock": "V-BLOCK"}.get(v.mode, v.mode.upper())
        safe_addstr(stdscr, sy, 2, f" {mode} ", C(CP_NVIM, curses.A_REVERSE))
        x = 3 + len(mode) + 2
        if v.mode == "cmdline":
            safe_addstr(stdscr, sy, x, v.cmdtype + v.cmdline + "█", C(CP_ACCENT))
        elif v.pending:
            safe_addstr(stdscr, sy, x, "".join(v.pending), C(CP_ACCENT, curses.A_BOLD))
        if v.recording_reg:
            safe_addstr(stdscr, sy, x + 12, f"recording @{v.recording_reg}", C(CP_ACCENT))
        if v.message:
            safe_addstr(stdscr, sy + 1, 2, v.message[: w - 4], C(CP_DIM))

        if show_hint and lesson.get("hint"):
            for i, segs in enumerate(render_markdown(lesson["hint"], min(90, w - 6))[:3]):
                draw_segments(stdscr, sy + 2 + i, 2, segs, w - 4)

        if solved:
            over = v.typed - lesson["par"]
            msg = f"✓ solved in {v.typed} keys" + (
                f" — par is {lesson['par']}" if over > 0 else " — at or under par")
            safe_addstr(stdscr, h - 3, 2, msg + ("   (shown, so it was not recorded)" if revealed else ""),
                        C(CP_OK, curses.A_BOLD))

        safe_addstr(stdscr, h - 1, 2,
                    "keys go to Vim · F1 hint · F2 show me · F5 reset · F10 or ZZ back · ^N next",
                    C(CP_DIM))
        stdscr.refresh()

    def reset():
        nonlocal v, solved, revealed
        v = Vim(list(lesson["start"]["lines"]), tuple(lesson["start"]["cursor"]))
        solved = False
        revealed = False

    while True:
        draw()
        try:
            k = stdscr.get_wch()
        except curses.error:
            continue
        except KeyboardInterrupt:
            return "back"

        if k == curses.KEY_F10:
            return "back"
        if k == curses.KEY_F5:
            reset()
            continue
        if k == curses.KEY_F1:
            show_hint = not show_hint
            continue
        if k == curses.KEY_F2:
            reset()
            revealed = True
            for key in parse_keys(lesson["solution"]):
                v.key(key)
                draw()
                time.sleep(0.16)
            if check():
                solved = True
            continue
        if k == "\x0e":  # ^N
            return "next"
        if k == curses.KEY_RESIZE:
            continue

        if isinstance(k, int):
            mapped = {curses.KEY_BACKSPACE: "\x08", curses.KEY_ENTER: "\r",
                      curses.KEY_LEFT: "h", curses.KEY_RIGHT: "l",
                      curses.KEY_UP: "k", curses.KEY_DOWN: "j"}.get(k)
            if mapped is None:
                continue
            k = mapped
        if k == "\n":
            k = "\r"

        v.message = ""
        try:
            v.key(k)
        except Exception as exc:  # noqa: BLE001
            v.message = f"engine: {exc}"

        if v.quit:
            return "back"
        if not solved and check():
            solved = True
            if not revealed:
                if on_solved:
                    on_solved()
                else:
                    progress.mark_done(track, lesson["id"], {"keys": v.typed})


# ============================================================== PYTHON
def run_quiz(stdscr, lesson, progress, track="python", on_answered=None):
    picked = None
    curses.curs_set(0)
    while True:
        stdscr.erase()
        h, w = stdscr.getmaxyx()
        width = min(92, w - 6)
        safe_addstr(stdscr, 0, 2, lesson["title"], C(CP_HEAD, curses.A_BOLD))
        y = 2
        if lesson.get("teach"):
            y += teach_block(stdscr, y, lesson["teach"], width, 4) + 1
        for segs in render_markdown(lesson["question"], width):
            draw_segments(stdscr, y, 2, segs, width)
            y += 1
        y += 1
        for i, opt in enumerate(lesson["options"]):
            attr = 0
            if picked is not None:
                if i == lesson["answer"]:
                    attr = C(CP_OK, curses.A_BOLD)
                elif i == picked:
                    attr = C(CP_BAD)
                else:
                    attr = C(CP_DIM)
            safe_addstr(stdscr, y, 2, f"{i + 1}.", C(CP_ACCENT) if picked is None else attr)
            for j, segs in enumerate(render_markdown(opt, width - 6)):
                draw_segments(stdscr, y + j, 6, segs, width - 6)
                if picked is not None:
                    for dy in range(j + 1):
                        pass
            y += max(1, len(render_markdown(opt, width - 6)))
        y += 1
        if picked is not None:
            right = picked == lesson["answer"]
            safe_addstr(stdscr, y, 2, "Correct." if right else "Not quite.",
                        C(CP_OK if right else CP_BAD, curses.A_BOLD))
            y += 1
            for segs in render_markdown(lesson["why"], width):
                draw_segments(stdscr, y, 2, segs, width)
                y += 1
        safe_addstr(stdscr, h - 1, 2,
                    "1-4 answer · ^N next · Esc back" if picked is None else "^N next · Esc back",
                    C(CP_DIM))
        stdscr.refresh()
        k = stdscr.getch()
        if k in (27, curses.KEY_F10):
            return "back"
        if k == 14:
            return "next"
        if picked is None and ord("1") <= k <= ord("4"):
            n = k - ord("1")
            if n < len(lesson["options"]):
                picked = n
                if on_answered:
                    on_answered(n == lesson["answer"])
                elif n == lesson["answer"]:
                    progress.mark_done(track, lesson["id"])
                else:
                    progress.mark_tried(track, lesson["id"])


def run_output(stdscr, lesson, progress):
    answer: list[str] = [""]
    row = 0
    checked = None
    curses.curs_set(1)
    while True:
        stdscr.erase()
        h, w = stdscr.getmaxyx()
        width = min(92, w - 6)
        safe_addstr(stdscr, 0, 2, lesson["title"], C(CP_HEAD, curses.A_BOLD))
        y = 2
        if lesson.get("teach"):
            y += teach_block(stdscr, y, lesson["teach"], width, 3) + 1
        safe_addstr(stdscr, y, 2, "WHAT DOES THIS PRINT?", C(CP_DIM, curses.A_BOLD))
        y += 1
        for line in lesson["code"].split("\n"):
            safe_addstr(stdscr, y, 4, line[: width], C(CP_CODE))
            y += 1
        y += 1
        safe_addstr(stdscr, y, 2, "your answer:", C(CP_DIM))
        y += 1
        ay = y
        for i, line in enumerate(answer):
            safe_addstr(stdscr, y, 4, "│ " + line, 0)
            y += 1
        y += 1
        if checked is not None:
            ok = checked
            safe_addstr(stdscr, y, 2, "✓ Exactly right." if ok else "· Not the actual output.",
                        C(CP_OK if ok else CP_BAD, curses.A_BOLD))
            y += 1
            if not ok:
                safe_addstr(stdscr, y, 2, "actual:", C(CP_DIM))
                y += 1
                for line in lesson["answer"].split("\n"):
                    safe_addstr(stdscr, y, 4, line[: width], C(CP_OK))
                    y += 1
            y += 1
            for segs in render_markdown(lesson["why"], width):
                draw_segments(stdscr, y, 2, segs, width)
                y += 1
        safe_addstr(stdscr, h - 1, 2, "type the output · ^D check · ^R clear · ^N next · Esc back", C(CP_DIM))
        try:
            stdscr.move(ay + row, 6 + len(answer[row]))
        except curses.error:
            pass
        stdscr.refresh()
        try:
            k = stdscr.get_wch()
        except curses.error:
            continue
        if is_esc(k) or k == curses.KEY_F10:
            curses.curs_set(0)
            return "back"
        if k == "\x0e":
            curses.curs_set(0)
            return "next"
        if k == "\x12":
            answer, row, checked = [""], 0, None
            continue
        if k == "\x04":  # ^D
            got = "\n".join(answer).rstrip("\n")
            want = lesson["answer"].rstrip("\n")
            checked = got == want
            if checked:
                progress.mark_done("python", lesson["id"])
            else:
                progress.mark_tried("python", lesson["id"])
            continue
        if k in BACKSPACES or k == curses.KEY_BACKSPACE:
            if answer[row]:
                answer[row] = answer[row][:-1]
            elif row > 0:
                answer.pop(row)
                row -= 1
            continue
        if k in ("\n", "\r"):
            answer.insert(row + 1, "")
            row += 1
            continue
        if isinstance(k, int) or len(k) != 1 or ord(k) < 32:
            continue
        answer[row] += k


def editor_command():
    ed = os.environ.get("VISUAL") or os.environ.get("EDITOR")
    if ed:
        return ed
    for cand in ("nvim", "vim", "vi", "nano"):
        if subprocess.run(["which", cand], capture_output=True).returncode == 0:
            return cand
    return "vi"


def run_code(stdscr, lesson, progress):
    """Edit in $EDITOR (ideally Neovim), then run against the real tests."""
    path = os.path.join(tempfile.mkdtemp(prefix="triada-"), lesson["id"] + ".py")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(lesson["starter"])
    output = None
    curses.curs_set(0)

    def run_tests():
        src = open(path, encoding="utf-8").read()
        runner = os.path.join(os.path.dirname(path), "_run.py")
        with open(runner, "w", encoding="utf-8") as fh:
            fh.write(src + "\n\n" + lesson["tests"] + "\nprint('__TRIADA_OK__')\n")
        try:
            p = subprocess.run([sys.executable, runner], capture_output=True, text=True, timeout=30)
        except subprocess.TimeoutExpired:
            return False, "timed out after 30s — is there an infinite loop?"
        if "__TRIADA_OK__" in p.stdout:
            extra = p.stdout.replace("__TRIADA_OK__\n", "").strip()
            return True, ("all tests passed" + ("\n\nstdout:\n" + extra if extra else ""))
        err = p.stderr.strip() or p.stdout.strip() or "no output"
        return False, err[-1600:]

    while True:
        stdscr.erase()
        h, w = stdscr.getmaxyx()
        width = min(92, w - 6)
        safe_addstr(stdscr, 0, 2, lesson["title"], C(CP_HEAD, curses.A_BOLD))
        y = 2
        if lesson.get("teach"):
            y += teach_block(stdscr, y, lesson["teach"], width, 4) + 1
        for segs in render_markdown(lesson["prompt"], width):
            draw_segments(stdscr, y, 2, segs, width)
            y += 1
        y += 1
        safe_addstr(stdscr, y, 2, "file: " + path, C(CP_DIM))
        y += 2
        try:
            cur = open(path, encoding="utf-8").read().split("\n")
        except OSError:
            cur = []
        for line in cur[: max(4, h - y - 8)]:
            safe_addstr(stdscr, y, 4, line[: width], C(CP_CODE))
            y += 1
        y += 1
        if output:
            ok, text = output
            safe_addstr(stdscr, y, 2, "✓ " if ok else "✗ ", C(CP_OK if ok else CP_BAD, curses.A_BOLD))
            for line in text.split("\n")[: h - y - 3]:
                safe_addstr(stdscr, y, 6, line[: width], C(CP_OK if ok else CP_BAD))
                y += 1
        safe_addstr(stdscr, h - 1, 2,
                    f"e edit in {editor_command()} · r run tests · s solution · ^N next · Esc back",
                    C(CP_DIM))
        stdscr.refresh()
        k = stdscr.getch()
        if k in (27, curses.KEY_F10):
            return "back"
        if k == 14:
            return "next"
        if k == ord("e"):
            curses.endwin()
            subprocess.call(editor_command().split() + [path])
            stdscr.clear()
            curses.doupdate()
            continue
        if k == ord("r"):
            output = run_tests()
            if output[0]:
                progress.mark_done("python", lesson["id"])
            else:
                progress.mark_tried("python", lesson["id"])
            continue
        if k == ord("s"):
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(lesson["solution"])
            output = (False, "solution written to the file — read it, then reset with 'x' and do it yourself")
            continue
        if k == ord("x"):
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(lesson["starter"])
            output = None
            continue
        if k == ord("t") and lesson.get("tests"):
            pager(stdscr, "Tests this must pass", "```\n" + lesson["tests"] + "\n```")
