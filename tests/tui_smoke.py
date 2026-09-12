#!/usr/bin/env python3
"""Drive the curses TUI in a pty and assert the screens render.

Not a full UI test — it checks that every view paints without raising, which is
what actually breaks in curses code.
"""
import os
import pty
import select
import subprocess
import sys
import tempfile
import time

try:
    import pyte
except ImportError:  # pragma: no cover
    print("tests/tui_smoke.py needs `pyte` (pip install pyte) — skipping the TUI test.")
    raise SystemExit(0)

import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRIADA_HOME = os.path.join(tempfile.gettempdir(), "triada-tui-test")
shutil.rmtree(TRIADA_HOME, ignore_errors=True)   # the test assumes zero progress
ENV = dict(os.environ,
           TERM="xterm-256color", LINES="40", COLUMNS="120", LC_ALL="C.UTF-8",
           TRIADA_HOME=TRIADA_HOME,
           PYTHONPATH=os.path.join(ROOT, "cli"))


class Tui:
    def __init__(self):
        self.master, slave = pty.openpty()
        try:
            import fcntl, struct, termios
            fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 40, 120, 0, 0))
        except Exception:
            pass
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "triada"],
            stdin=slave, stdout=slave, stderr=slave, env=ENV, cwd=ROOT, close_fds=True)
        os.close(slave)
        self.screen = pyte.Screen(120, 40)
        self.stream = pyte.ByteStream(self.screen)

    def read(self, wait=0.7):
        """Feed everything the app emitted into a real terminal emulator, then
        return the rendered screen — curses only sends diffs, so nothing else
        gives an accurate picture."""
        end = time.time() + wait
        while time.time() < end:
            r, _, _ = select.select([self.master], [], [], 0.12)
            if r:
                try:
                    self.stream.feed(os.read(self.master, 65536))
                except OSError:
                    break
        return "\n".join(self.screen.display)

    def send(self, s, wait=0.7):
        os.write(self.master, s.encode())
        return self.read(wait)

    def dump(self):
        return "\n".join(line.rstrip() for line in self.screen.display)

    def close(self):
        try:
            self.proc.terminate()
            self.proc.wait(timeout=3)
        except Exception:
            self.proc.kill()
        os.close(self.master)


def main():
    fails = []

    def want(label, screen, *needles):
        missing = [n for n in needles if n not in screen]
        if missing:
            fails.append(f"{label}: missing {missing}")
            print(f"  ✗ {label}: missing {missing}")
        else:
            print(f"  ✓ {label}")

    t = Tui()

    def home(label=""):
        """Escape until the home screen is showing."""
        for _ in range(5):
            screen = t.read(0.25)
            if "TRÍADA" in screen and "Touch Typing" in screen:
                return screen
            screen = t.send("\x1b", 0.5)
        fails.append(f"{label}: could not get back to home")
        print(f"  ✗ {label}: could not get back to home")
        return screen

    try:
        want("home", t.read(1.5), "TRÍADA", "Touch Typing", "Neovim", "Python", "Combos")

        want("typing track", t.send("1"), "ES QWERTY", "Home Row Anchors")
        want("typing level", t.send("\r"), "Index fingers", "Level 1")
        want("typing drill", t.send("\r", 1.0), "next", "wpm")
        want("typing input", t.send("fff jjj", 1.0), "wpm")
        home("after typing")

        want("nvim track", t.send("2"), "Neovim", "Modes & Survival")
        t.send("\r")
        want("vim drill", t.send("jjj\r", 1.0), "YOUR BUFFER", "TARGET", "NORMAL", "par")
        want("vim solve", t.send("imundo\x1b", 1.2), "hola mundo", "solved")
        t.send("ZZ", 0.5)          # ZZ leaves a drill — Esc belongs to Vim
        home("after vim")

        want("python track", t.send("3"), "Python", "Values, Names")
        t.send("\r")
        want("python output", t.send("\r", 1.0), "WHAT DOES THIS PRINT", "type(3)")
        want("python answer", t.send("int\rfloat\rstr\rTrue\rFalse\x04", 1.2), "Exactly right")
        home("after python")

        want("combos", t.send("c"), "Combos", "Fix the signature")
        home("after combos")
        want("stats", t.send("s"), "Progress", "Keys you miss most")
        home("after stats")
        want("help", t.send("?", 1.0), "Typing drills", "Vim drills")
        t.send("q")
        home("after help")
        t.send("q")
    finally:
        t.close()

    print()
    if fails:
        print(f"{len(fails)} TUI checks failed")
        return 1
    print("TUI smoke: all screens render")
    return 0


if __name__ == "__main__":
    sys.exit(main())
