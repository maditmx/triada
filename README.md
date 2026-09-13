# Tríada

An interconnected trainer for the three things that decide how fast you can turn
a thought into working code: **touch typing**, **Neovim**, and **Python**.

Two front-ends over one curriculum:

- **`web/`** — a single-page app. Open `web/index.html` in a browser. No build,
  no server, no dependencies.
- **`cli/`** — a curses TUI. Run `./triada`. Same lessons, same progress file,
  and Python exercises run on your own `python3` and open in your own Neovim.

Keyboard layout: **ES QWERTY (Spain)**. Interface and explanations in English.

---

## Quick start

```bash
./triada                    # the terminal trainer
open web/index.html         # the web app  (or: make web)
```

`./triada doctor` checks your environment. `./triada stats` prints progress.

---

## How it is organised

Three tracks, twelve levels each, **249 lessons**, from the home row to
`asyncio`.

| Track | Levels | Goes from | To |
|---|---|---|---|
| Touch Typing | 12 | finding `F` and `J` by feel | 50 wpm at 97% on symbol-dense code |
| Neovim | 12 | what a mode is | macros, `:g/…/normal`, Lua config, LSP |
| Python | 12 | names and f-strings | decorators, async, `Decimal`, profiling |
| Combos | 8 | — | one task that needs all three at once |

### Progression is independent

A level unlocks when **every lesson in the previous level of that same track**
is done. Nothing else gates it. You can be at Neovim level 11 and Python level 2,
or the reverse. This is deliberate: the three skills grow at very different
speeds, and coupling them would hold back whichever one you happen to be good at.

### …but the content is interconnected

- Typing drills are made of real Python and real Vim command lines. Level 9
  exists because `[ ] { }` are AltGr combos on a Spanish keyboard and that is
  the single biggest speed tax a Spanish-layout programmer pays.
- Vim exercises edit Python buffers — extracting a constant, commenting a block,
  renaming a symbol.
- Python lessons carry a `⌨` tip naming the Vim motion that makes that edit cheap.
- Every level shows explicit **cross-links** to the level in another track that
  it depends on or feeds.
- **Combos** are optional challenges that chain all three: type the snippet →
  make the edit in the Vim emulator → answer why it matters. They unlock on
  minimum levels in all three tracks, and completing one changes nothing about
  track progress.

---

## The Vim emulator

The Neovim track is not multiple-choice. It runs a real Vim emulator, twice:

- `cli/triada/vimengine.py` — Python, for the TUI
- `web/vimengine.js` — JavaScript, for the browser

Both implement modes (normal / insert / visual char-line-block / replace /
command-line), the full operator + motion + count grammar, text objects,
registers including named and black-hole, marks, macros, search, the dot repeat,
undo/redo, and a useful slice of ex (`:s`, `:g`, `:normal`, `:m`, `:sort`,
ranges). Motions that fail abort a macro, the way real Vim does — which is what
makes `50@a` on a 4-line file the right thing to type.

Every exercise carries the keystrokes that solve it, and `make test` replays each
one through **both** engines and asserts it reaches the goal. The `par` shown
next to your key count is not a guess: it is exactly what the reference solution
types. The curriculum cannot drift from the emulator, and the two emulators
cannot drift from each other.

---

## Running Python for real

**In the terminal** — the natural way. Press `e` on a code exercise: it opens the
file in `$EDITOR` (Neovim, if you have it), you edit and quit, then `r` runs the
real test suite with your own `python3`. Practising the Vim track and the Python
track in the same keystroke is the point.

**In the browser** — Pyodide is fetched from a CDN the first time you press *Run
tests* (about 10 MB, cached afterwards). If it cannot load, the exercise falls
back to showing you the CLI command for that exact lesson.

**Fully offline browser Python** — download a Pyodide release and unpack it into
`web/vendor/pyodide/` so that `web/vendor/pyodide/pyodide.js` exists. The app
tries that path first.

The web editor also has a **Vim keys** toggle: the same emulator, driving the
Python editor. Turn it on once you have finished Vim level 6.

---

## Progress

One JSON file, identical in both front-ends:

- CLI: `~/.triada/progress.json` (override with `TRIADA_HOME`)
- Web: browser `localStorage`, with **Stats → Export / Import JSON**

To move a session between them, copy the file. Export from the web, save it as
`~/.triada/progress.json`, and the terminal picks up exactly where you were.

It records, per lesson: done, attempts, best wpm and accuracy, best keystroke
count — plus a global tally of which characters you mistype, which is what the
key heat-map and the "keys you miss most" list are built from.

---

## Keyboard

Everything works with the mouse in the web app, and everything works with the
keyboard in both.

| Key | Everywhere |
|---|---|
| `j` `k` / arrows | move |
| `Enter` | open |
| `Esc` | back |
| `1` `2` `3` | jump to a track |
| `c` / `s` / `?` | combos / stats / help |

Inside a **Vim drill every key goes to the emulator, including `Esc`.** To get
out: `F10`, or `ZZ`, or `:q` in the TUI; `Tab` in Normal mode in the browser.

Typing drills: `Ctrl-R` restart, `Ctrl-N` next. Python code exercises in the TUI:
`e` edit, `r` run, `s` solution, `x` reset.

---

## Layout

```
curriculum/     the whole course as JSON — the single source of truth
  typing.json   12 levels · 69 lessons
  nvim.json     12 levels · 103 lessons   (each with solution keystrokes)
  python.json   12 levels · 77 lessons    (each with runnable tests)
  combos.json   8 cross-track challenges

web/            open index.html — no build step
  index.html  styles.css  app.js
  vimengine.js      the emulator, JS port
  curriculum.js     generated bundle (file:// cannot fetch JSON)

cli/triada/     the terminal app
  __main__.py   entry point and subcommands
  app.py        navigation
  drills.py     the four exercise runners
  vimengine.py  the emulator, reference implementation
  keyboard.py   ES QWERTY layout knowledge
  data.py       curriculum loading, progress persistence

cli-rs/         a Rust/ratatui port of the terminal app — same curriculum and
                progress file, kept alongside cli/ rather than replacing it

tools/          curriculum generators + the validator
tests/          engine tests, JS/Python parity, TUI render test
```

Edit the curriculum by editing `tools/gen_*.py`, then `make build`. Editing the
generated JSON directly works too, but a regeneration will overwrite it.

```bash
make build   # regenerate curriculum + web bundle
make test    # 60 engine cases, 249 lessons validated, JS parity, TUI render, Rust engine oracle
make cli-rs  # run the Rust/ratatui port
```

---

## Design notes

**Accuracy is measured on first attempts.** Backspacing lets you finish a drill;
it does not repair the score. Speed follows accuracy, never the other way round,
and a trainer that lets you buy speed with errors teaches the wrong habit.

**Par instead of a timer** in the Vim track. Vim's value is keystroke economy,
not raw speed — being shown that a job took you 14 keys when 4 was possible is
the feedback that changes behaviour.

**Every Python exercise is validated by running it.** The `make test` suite
executes every reference solution against its own tests, and every
predict-the-output snippet is actually run and compared. Nothing in the
curriculum is asserted without being checked.
