"""triada — terminal trainer for touch typing, Neovim and Python.

Usage:
  triada                 open the trainer
  triada <lesson-id>     jump straight to one lesson (e.g. triada v06l3)
  triada py <lesson-id>  run one Python exercise without curses
  triada stats           print progress and exit
  triada doctor          check the environment
"""
from __future__ import annotations

import curses
import locale
import os
import subprocess
import sys
import tempfile

from .app import App
from .data import TRACKS, Progress, find_lesson, load_all, progress_path


def cmd_stats():
    p = Progress()
    print("Tríada — progress\n")
    for t in TRACKS:
        st = p.stats(t)
        filled = int(round(st["pct"] * 24))
        print(f"  {t:<8} {'█' * filled}{'·' * (24 - filled)}  "
              f"{int(st['pct'] * 100):3d}%   {st['done']:3d}/{st['total']:<4d} lessons   "
              f"level {st['level']}/{st['levels']}")
    combos = load_all()["combos"]["combos"]
    done = sum(1 for c in combos if p.data["combos"].get(c["id"]))
    print(f"\n  combos   {done}/{len(combos)} complete")
    ks = p.data["keyStats"]
    if ks:
        worst = sorted(ks, key=lambda k: -ks[k])[:12]
        print("\n  most-missed keys: " + "  ".join(
            ("space" if c == " " else "enter" if c == "\n" else c) + f"×{ks[c]}" for c in worst))
    print(f"\n  file: {progress_path()}")


def cmd_py(lesson_id):
    """Run one Python exercise head-less: edit in $EDITOR, run the real tests."""
    found = find_lesson(lesson_id)
    if not found or found[0] != "python":
        print(f"No Python exercise with id {lesson_id!r}.")
        return 1
    _, _, ls = found
    if ls["kind"] != "code":
        print(f"{lesson_id} is a {ls['kind']} exercise — open it with `triada {lesson_id}`.")
        return 1

    print(f"\n{ls['title']}\n")
    print(ls["prompt"] + "\n")
    d = tempfile.mkdtemp(prefix="triada-")
    path = os.path.join(d, lesson_id + ".py")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(ls["starter"])
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR") or "nvim"
    print(f"editing {path} with {editor} — save and quit when you are done\n")
    subprocess.call(editor.split() + [path])

    runner = os.path.join(d, "_run.py")
    with open(runner, "w", encoding="utf-8") as fh:
        fh.write(open(path, encoding="utf-8").read() + "\n\n" + ls["tests"] +
                 "\nprint('__TRIADA_OK__')\n")
    r = subprocess.run([sys.executable, runner], capture_output=True, text=True)
    if "__TRIADA_OK__" in r.stdout:
        print("✓ all tests passed")
        extra = r.stdout.replace("__TRIADA_OK__\n", "").strip()
        if extra:
            print("\nstdout:\n" + extra)
        p = Progress()
        p.mark_done("python", lesson_id)
        return 0
    print("✗ tests failed\n")
    print((r.stderr or r.stdout).strip())
    Progress().mark_tried("python", lesson_id)
    return 1


def cmd_doctor():
    ok = True
    print("Tríada — environment check\n")
    print(f"  python      {sys.version.split()[0]}")
    try:
        import curses  # noqa: F401
        print("  curses      available")
    except ImportError:
        print("  curses      MISSING — the TUI cannot run")
        ok = False
    ed = os.environ.get("VISUAL") or os.environ.get("EDITOR")
    if ed:
        print(f"  $EDITOR     {ed}")
    else:
        found = [c for c in ("nvim", "vim", "vi")
                 if subprocess.run(["which", c], capture_output=True).returncode == 0]
        print(f"  $EDITOR     unset — will use {found[0] if found else 'vi'}"
              + (f" (found: {', '.join(found)})" if found else ""))
    try:
        from .data import curriculum_dir
        d = curriculum_dir()
        cur = load_all()
        n = sum(len(lv["lessons"]) for t in TRACKS for lv in cur[t]["levels"])
        print(f"  curriculum  {d}  ({n} lessons, {len(cur['combos']['combos'])} combos)")
    except SystemExit as e:
        print(f"  curriculum  {e}")
        ok = False
    print(f"  progress    {progress_path()}"
          + ("" if progress_path().exists() else "  (will be created)"))
    term = os.environ.get("TERM", "")
    print(f"  TERM        {term or 'unset'}"
          + ("" if "256" in term or "color" in term else "  — a 256-colour TERM looks much better"))
    print("\n" + ("all good" if ok else "problems above"))
    return 0 if ok else 1


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    locale.setlocale(locale.LC_ALL, "")

    if argv and argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    if argv and argv[0] == "stats":
        cmd_stats()
        return 0
    if argv and argv[0] == "doctor":
        return cmd_doctor()
    if argv and argv[0] == "py":
        if len(argv) < 2:
            print("usage: triada py <lesson-id>")
            return 1
        return cmd_py(argv[1])

    start = argv[0] if argv else None
    if start and not find_lesson(start):
        print(f"No lesson with id {start!r}. Try `triada` and browse, or `triada stats`.")
        return 1

    os.environ.setdefault("ESCDELAY", "25")
    curses.wrapper(lambda scr: App(scr, start=start).run())
    return 0


if __name__ == "__main__":
    sys.exit(main())
