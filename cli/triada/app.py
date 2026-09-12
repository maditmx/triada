"""The curses application: home, track, level and lesson navigation."""
from __future__ import annotations

import curses

from . import drills
from .data import TRACKS, Progress, load_all
from .ui import (CP_ACCENT, CP_BAD, CP_DIM, CP_HEAD, CP_INV, CP_OK, TRACK_COLOR,
                 C, draw_segments, init_colors, render_markdown, safe_addstr)

LABEL = {"typing": "Touch Typing", "nvim": "Neovim", "python": "Python"}


def bar(pct, width=22):
    filled = int(round(pct * width))
    return "█" * filled + "·" * (width - filled)


class App:
    def __init__(self, stdscr, start=None):
        self.s = stdscr
        self.cur = load_all()
        self.p = Progress()
        self.track = "typing"
        self.sel = 0
        self.level_sel = 0
        self.start = start

    # ------------------------------------------------------------- run
    def run(self):
        curses.curs_set(0)
        self.s.keypad(True)
        try:
            curses.set_escdelay(25)
        except AttributeError:
            pass
        init_colors()

        if self.start:
            self.open_lesson_by_id(self.start)

        while True:
            if self.home() == "quit":
                return

    # ------------------------------------------------------------ home
    def home(self):
        rows = []
        for t in TRACKS:
            rows.append(("track", t))
        rows.append(("combos", None))
        rows.append(("stats", None))
        sel = 0
        while True:
            self.s.erase()
            h, w = self.s.getmaxyx()
            safe_addstr(self.s, 0, 2, "TRÍADA", C(CP_ACCENT, curses.A_BOLD))
            safe_addstr(self.s, 0, 11, "type · edit · program", C(CP_DIM))
            safe_addstr(self.s, 2, 2, "Three skills, one keyboard.", curses.A_BOLD)
            safe_addstr(self.s, 3, 2,
                        "Progress in each track is independent — go expert in one while you start another.",
                        C(CP_DIM))
            y = 5
            for i, (kind, t) in enumerate(rows):
                on = i == sel
                mark = "▸ " if on else "  "
                if kind == "track":
                    st = self.p.stats(t)
                    lv = self.cur[t]["levels"][min(st["level"], st["levels"]) - 1]
                    safe_addstr(self.s, y, 2, mark + LABEL[t].ljust(14),
                                C(TRACK_COLOR[t], curses.A_BOLD if on else 0))
                    safe_addstr(self.s, y, 18, bar(st["pct"]), C(TRACK_COLOR[t]))
                    safe_addstr(self.s, y, 42,
                                f"{st['done']:3d}/{st['total']:<4d} lessons   level {st['level']}/{st['levels']}",
                                C(CP_DIM))
                    safe_addstr(self.s, y + 1, 20, f"next: L{lv['n']} · {lv['title']}", C(CP_DIM))
                    y += 3
                elif kind == "combos":
                    n = sum(1 for c in self.cur["combos"]["combos"] if self.combo_open(c))
                    done = sum(1 for c in self.cur["combos"]["combos"] if self.p.data["combos"].get(c["id"]))
                    safe_addstr(self.s, y, 2, mark + "Combos".ljust(14), C(CP_ACCENT, curses.A_BOLD if on else 0))
                    safe_addstr(self.s, y, 18,
                                f"{done} done · {n}/{len(self.cur['combos']['combos'])} unlocked "
                                "— one task, all three skills", C(CP_DIM))
                    y += 2
                else:
                    safe_addstr(self.s, y, 2, mark + "Stats & data".ljust(14),
                                curses.A_BOLD if on else 0)
                    y += 2
            safe_addstr(self.s, h - 1, 2,
                        "j/k move · Enter open · 1/2/3 track · ? help · q quit", C(CP_DIM))
            self.s.refresh()

            k = self.s.getch()
            if k in (ord("q"),):
                return "quit"
            if k in (ord("j"), curses.KEY_DOWN):
                sel = (sel + 1) % len(rows)
            elif k in (ord("k"), curses.KEY_UP):
                sel = (sel - 1) % len(rows)
            elif k == ord("?"):
                self.help()
            elif k in (ord("1"), ord("2"), ord("3")):
                self.view_track(TRACKS[k - ord("1")])
            elif k == ord("c"):
                self.view_combos()
            elif k == ord("s"):
                self.view_stats()
            elif k in (curses.KEY_ENTER, 10, 13, curses.KEY_RIGHT, ord("l")):
                kind, t = rows[sel]
                if kind == "track":
                    self.view_track(t)
                elif kind == "combos":
                    self.view_combos()
                else:
                    self.view_stats()

    # ------------------------------------------------------------ track
    def view_track(self, track):
        self.track = track
        doc = self.cur[track]
        sel = min(self.p.unlocked(track), len(doc["levels"])) - 1
        while True:
            self.s.erase()
            h, w = self.s.getmaxyx()
            st = self.p.stats(track)
            safe_addstr(self.s, 0, 2, doc["title"], C(TRACK_COLOR[track], curses.A_BOLD))
            safe_addstr(self.s, 0, 2 + len(doc["title"]) + 3, doc["subtitle"], C(CP_DIM))
            safe_addstr(self.s, 1, 2, bar(st["pct"], 30) + f"  {st['done']}/{st['total']}", C(CP_DIM))
            y = 3
            for i, lv in enumerate(doc["levels"]):
                if y >= h - 4:
                    break
                locked = lv["n"] > self.p.unlocked(track)
                complete = self.p.level_complete(track, lv)
                dn = sum(1 for ls in lv["lessons"] if self.p.done(track, ls["id"]))
                on = i == sel
                glyph = "🔒" if locked else ("✓" if complete else " ")
                attr = C(CP_DIM) if locked else (C(CP_OK) if complete else 0)
                if on:
                    attr |= curses.A_BOLD
                safe_addstr(self.s, y, 2, ("▸" if on else " ") + f" {lv['n']:2d} {glyph} ", attr)
                safe_addstr(self.s, y, 12, lv["title"][: w - 34], attr)
                safe_addstr(self.s, y, w - 20, f"{dn}/{len(lv['lessons'])}", C(CP_DIM))
                if on and not locked:
                    safe_addstr(self.s, y + 1, 14, lv["goal"][: w - 20], C(CP_DIM))
                    y += 1
                y += 1
            safe_addstr(self.s, h - 1, 2,
                        "j/k move · Enter open level · b brief · Esc back", C(CP_DIM))
            self.s.refresh()

            k = self.s.getch()
            if k in (27, ord("q"), curses.KEY_LEFT):
                return
            if k in (ord("j"), curses.KEY_DOWN):
                sel = (sel + 1) % len(doc["levels"])
            elif k in (ord("k"), curses.KEY_UP):
                sel = (sel - 1) % len(doc["levels"])
            elif k == ord("b"):
                drills.pager(self.s, f"Level {doc['levels'][sel]['n']} · {doc['levels'][sel]['title']}",
                             doc["levels"][sel]["brief"])
            elif k in (curses.KEY_ENTER, 10, 13, curses.KEY_RIGHT, ord("l")):
                lv = doc["levels"][sel]
                if lv["n"] > self.p.unlocked(track):
                    self.toast(f"Finish level {lv['n'] - 1} first — every lesson in it.")
                else:
                    self.view_level(track, lv)

    # ------------------------------------------------------------ level
    def view_level(self, track, lv):
        sel = 0
        for i, ls in enumerate(lv["lessons"]):
            if not self.p.done(track, ls["id"]):
                sel = i
                break
        while True:
            self.s.erase()
            h, w = self.s.getmaxyx()
            safe_addstr(self.s, 0, 2, f"{LABEL[track]} · Level {lv['n']}",
                        C(TRACK_COLOR[track], curses.A_BOLD))
            safe_addstr(self.s, 1, 2, lv["title"], curses.A_BOLD)
            safe_addstr(self.s, 2, 2, lv["goal"], C(CP_DIM))
            y = 4
            for i, ls in enumerate(lv["lessons"]):
                if y >= h - 6:
                    break
                on = i == sel
                done = self.p.done(track, ls["id"])
                safe_addstr(self.s, y, 2, ("▸" if on else " ") + (" ✓ " if done else "   "),
                            C(CP_OK) if done else 0)
                safe_addstr(self.s, y, 7, ls["kind"].ljust(7), C(CP_DIM))
                safe_addstr(self.s, y, 15, ls["title"][: w - 40],
                            curses.A_BOLD if on else 0)
                rec = self.p.record(track, ls["id"]).get("best") or {}
                if "wpm" in rec:
                    safe_addstr(self.s, y, w - 24, f"{rec['wpm']} wpm · {int(rec['acc'] * 100)}%", C(CP_DIM))
                elif "keys" in rec:
                    safe_addstr(self.s, y, w - 24, f"{rec['keys']} keys (par {ls.get('par', '-')})", C(CP_DIM))
                y += 1
            y += 1
            for lk in lv.get("links", []):
                safe_addstr(self.s, y, 2, "↔ " + LABEL[lk["track"]] + ": " + lk["note"][: w - 10],
                            C(CP_ACCENT))
                y += 1
            safe_addstr(self.s, h - 1, 2,
                        "j/k move · Enter start · b level brief · Esc back", C(CP_DIM))
            self.s.refresh()

            k = self.s.getch()
            if k in (27, ord("q"), curses.KEY_LEFT):
                return
            if k in (ord("j"), curses.KEY_DOWN):
                sel = (sel + 1) % len(lv["lessons"])
            elif k in (ord("k"), curses.KEY_UP):
                sel = (sel - 1) % len(lv["lessons"])
            elif k == ord("b"):
                drills.pager(self.s, f"Level {lv['n']} · {lv['title']}", lv["brief"])
            elif k in (curses.KEY_ENTER, 10, 13, curses.KEY_RIGHT):
                while True:
                    res = self.run_lesson(track, lv, lv["lessons"][sel])
                    if res == "next" and sel + 1 < len(lv["lessons"]):
                        sel += 1
                        continue
                    break

    # ----------------------------------------------------------- lesson
    def run_lesson(self, track, lv, ls):
        kind = ls["kind"]
        if track == "typing":
            return drills.run_typing(self.s, ls, lv, self.p)
        if track == "nvim":
            if kind == "quiz":
                return drills.run_quiz(self.s, ls, self.p, "nvim")
            return drills.run_vim(self.s, ls, self.p, "nvim")
        if kind == "quiz":
            return drills.run_quiz(self.s, ls, self.p, "python")
        if kind == "output":
            return drills.run_output(self.s, ls, self.p)
        return drills.run_code(self.s, ls, self.p)

    def open_lesson_by_id(self, lesson_id):
        from .data import find_lesson
        found = find_lesson(lesson_id)
        if not found:
            return
        track, lv, ls = found
        self.run_lesson(track, lv, ls)

    # ----------------------------------------------------------- combos
    def combo_open(self, cb):
        return all(self.p.unlocked(t) >= cb["needs"][t] for t in TRACKS)

    def view_combos(self):
        combos = self.cur["combos"]["combos"]
        sel = 0
        while True:
            self.s.erase()
            h, w = self.s.getmaxyx()
            safe_addstr(self.s, 0, 2, "Combos", C(CP_ACCENT, curses.A_BOLD))
            safe_addstr(self.s, 1, 2,
                        "Type it, edit it, explain it. Optional — they never block a track.", C(CP_DIM))
            y = 3
            for i, cb in enumerate(combos):
                op = self.combo_open(cb)
                done = bool(self.p.data["combos"].get(cb["id"]))
                on = i == sel
                attr = (C(CP_DIM) if not op else (C(CP_OK) if done else 0)) | (curses.A_BOLD if on else 0)
                safe_addstr(self.s, y, 2, ("▸" if on else " ") + f" {cb['n']} " + ("✓" if done else ("🔒" if not op else " ")), attr)
                safe_addstr(self.s, y, 10, cb["title"][: w - 40], attr)
                safe_addstr(self.s, y, w - 26,
                            f"T{cb['needs']['typing']} V{cb['needs']['nvim']} P{cb['needs']['python']}",
                            C(CP_DIM))
                if on:
                    safe_addstr(self.s, y + 1, 12, cb["brief"][: w - 16], C(CP_DIM))
                    y += 1
                y += 1
            safe_addstr(self.s, h - 1, 2, "j/k move · Enter start · Esc back", C(CP_DIM))
            self.s.refresh()
            k = self.s.getch()
            if k in (27, ord("q"), curses.KEY_LEFT):
                return
            if k in (ord("j"), curses.KEY_DOWN):
                sel = (sel + 1) % len(combos)
            elif k in (ord("k"), curses.KEY_UP):
                sel = (sel - 1) % len(combos)
            elif k in (curses.KEY_ENTER, 10, 13, curses.KEY_RIGHT):
                cb = combos[sel]
                if not self.combo_open(cb):
                    self.toast(f"Needs typing L{cb['needs']['typing']}, "
                               f"Neovim L{cb['needs']['nvim']}, Python L{cb['needs']['python']}.")
                else:
                    self.run_combo(cb)

    def run_combo(self, cb):
        state = {"typing": False, "vim": False, "quiz": False}

        typ = {"id": cb["id"] + "-t", "title": cb["title"] + " · 1/3 type it",
               "kind": "text", "content": cb["typing"]["content"], "teach": "",
               "pass": {"wpm": 20 + cb["n"] * 2, "acc": 0.95}}
        before = dict(self.p.data["typing"]["lessons"])
        drills.run_typing(self.s, typ, None, self.p, track="typing")
        state["typing"] = self.p.done("typing", typ["id"])
        self.p.data["typing"]["lessons"] = before  # combos do not count as typing lessons

        vim = dict(cb["vim"])
        vim.update({"id": cb["id"] + "-v", "title": cb["title"] + " · 2/3 edit it",
                    "kind": "drill", "teach": ""})
        solved = {"v": False}
        drills.run_vim(self.s, vim, self.p, track="nvim", on_solved=lambda: solved.__setitem__("v", True))
        state["vim"] = solved["v"]

        q = dict(cb["python"])
        q.update({"id": cb["id"] + "-q", "title": cb["title"] + " · 3/3 explain it", "teach": ""})
        answered = {"ok": False}
        drills.run_quiz(self.s, q, self.p, track="python",
                        on_answered=lambda ok: answered.__setitem__("ok", ok))
        state["quiz"] = answered["ok"]

        if all(state.values()):
            self.p.data["combos"][cb["id"]] = {"done": True}
            self.p.save()
            self.toast("✓ Combo complete.")
        else:
            missing = [k for k, v in state.items() if not v]
            self.toast("Still to do: " + ", ".join(missing))

    # ------------------------------------------------------------ stats
    def view_stats(self):
        while True:
            self.s.erase()
            h, w = self.s.getmaxyx()
            safe_addstr(self.s, 0, 2, "Progress", curses.A_BOLD)
            y = 2
            for t in TRACKS:
                st = self.p.stats(t)
                best = 0
                for rec in self.p.data[t]["lessons"].values():
                    best = max(best, (rec.get("best") or {}).get("wpm", 0))
                safe_addstr(self.s, y, 2, LABEL[t].ljust(14), C(TRACK_COLOR[t], curses.A_BOLD))
                safe_addstr(self.s, y, 18, bar(st["pct"], 26), C(TRACK_COLOR[t]))
                safe_addstr(self.s, y, 46,
                            f"{int(st['pct'] * 100):3d}%   {st['done']}/{st['total']}   L{st['level']}"
                            + (f"   best {best} wpm" if best else ""), C(CP_DIM))
                y += 2

            ks = self.p.data["keyStats"]
            y += 1
            safe_addstr(self.s, y, 2, "Keys you miss most", curses.A_BOLD)
            y += 1
            if not ks:
                safe_addstr(self.s, y, 2, "nothing recorded yet", C(CP_DIM))
                y += 1
            else:
                worst = sorted(ks, key=lambda k: -ks[k])[:20]
                line = "  ".join(("␣" if c == " " else "↵" if c == "\n" else c) + f"×{ks[c]}" for c in worst)
                safe_addstr(self.s, y, 2, line[: w - 4], C(CP_BAD))
                y += 1
            y += 2
            from .data import progress_path
            safe_addstr(self.s, y, 2, "progress file: " + str(progress_path()), C(CP_DIM))
            y += 1
            safe_addstr(self.s, y, 2,
                        "the web app imports and exports exactly this file (Stats → Import JSON)", C(CP_DIM))
            safe_addstr(self.s, h - 1, 2, "Esc back", C(CP_DIM))
            self.s.refresh()
            k = self.s.getch()
            if k in (27, ord("q"), curses.KEY_LEFT):
                return

    # ------------------------------------------------------------- misc
    def help(self):
        drills.pager(self.s, "Keyboard", HELP)

    def toast(self, msg):
        h, w = self.s.getmaxyx()
        safe_addstr(self.s, h - 2, 2, " " + msg + " ", C(CP_ACCENT, curses.A_REVERSE))
        self.s.refresh()
        curses.napms(1300)


HELP = """
## Everywhere

| Key | Does |
|---|---|
| `j` `k` or arrows | move |
| `Enter` | open |
| `Esc` or `q` | back |
| `1` `2` `3` | jump to a track |
| `c` | combos |
| `s` | stats |
| `?` | this list |

## Typing drills

| Key | Does |
|---|---|
| any key | types |
| `Backspace` | correct a mistake |
| `Ctrl-R` | restart the drill |
| `Ctrl-N` | next lesson |
| `Esc` | back |

Accuracy is measured on *first attempts*, so backspacing does not hide an error —
it just lets you finish. That is deliberate.

## Vim drills

Every key goes to the emulator, including `Esc`. To get out:

| Key | Does |
|---|---|
| `F10` or `ZZ` or `:q` | leave the drill |
| `F5` | reset the buffer |
| `F1` | toggle the hint |
| `F2` | replay the reference solution (does not count) |
| `Ctrl-N` | next lesson |

## Python exercises

| Key | Does |
|---|---|
| `e` | edit the file in `$EDITOR` (Neovim, ideally) |
| `r` | run the real tests with your own python3 |
| `s` | write the reference solution into the file |
| `x` | reset the file to the starter |
| `1`–`4` | answer a quiz |
| `Ctrl-D` | check a predicted output |

## Progress

Progress lives in `~/.triada/progress.json` and is the same format the web app
exports, so you can move a session between the two by copying one file.
"""
