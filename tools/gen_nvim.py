#!/usr/bin/env python3
"""Generate curriculum/nvim.json — 12 levels of executable Vim exercises.

Every exercise carries a `solution` key sequence. tools/validate.py runs each
one through the engine and asserts the goal is reached, so the curriculum
cannot drift from the emulator.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "curriculum", "nvim.json")

L = []


def level(n, lid, title, goal, brief, lessons, links=None):
    L.append({
        "id": lid, "n": n, "title": title, "goal": goal, "brief": brief,
        "lessons": lessons, "links": links or [],
    })


def drill(lid, title, teach, start, cursor, goal_lines, solution, par,
          hint="", goal_cursor=None, goal_mode="normal", note=""):
    d = {
        "id": lid, "title": title, "kind": "drill", "teach": teach,
        "start": {"lines": start, "cursor": list(cursor)},
        "goal": {"lines": goal_lines},
        "solution": solution, "par": par, "hint": hint, "note": note,
    }
    if goal_cursor is not None:
        d["goal"]["cursor"] = list(goal_cursor)
    if goal_mode:
        d["goal"]["mode"] = goal_mode
    return d


def move(lid, title, teach, start, cursor, goal_cursor, solution, par, hint="", note=""):
    """Cursor-only exercise: the buffer must be unchanged."""
    return {
        "id": lid, "title": title, "kind": "move", "teach": teach,
        "start": {"lines": start, "cursor": list(cursor)},
        "goal": {"lines": start, "cursor": list(goal_cursor), "mode": "normal"},
        "solution": solution, "par": par, "hint": hint, "note": note,
    }


def quiz(lid, title, teach, question, options, answer, why):
    return {
        "id": lid, "title": title, "kind": "quiz", "teach": teach,
        "question": question, "options": options, "answer": answer, "why": why,
    }


PY1 = ["def greet(name):", "    print('hola ' + name)", "", "greet('marco')"]

# ============================================================ L1
level(1, "v01", "Modes & Survival",
      "Know which mode you are in, and how to get back to Normal.",
      """Vim's one big idea: **your keyboard means different things in different
modes.** Most editors have one mode — every key inserts a character. Vim has
several, and *Normal* is home.

| Mode | You get there by | Keys mean |
|---|---|---|
| **Normal** | `Esc` (always) | commands |
| **Insert** | `i` `a` `o` `I` `A` `O` | literal text |
| **Visual** | `v` `V` `Ctrl-v` | select |
| **Command-line** | `:` `/` `?` | ex commands / search |

**The habit that matters most: return to Normal the moment you stop typing.**
Not when you need a command — immediately. Normal mode is the resting position,
the way the home row is the resting position for your fingers.

Movement in Normal mode is `h j k l`:

```
      k        h  ←  left
 h  <   >  l   j  ↓  down
      j        k  ↑  up
                l  →  right
```

Yes, arrow keys work. Use `hjkl` anyway — they are under your fingers, and
every operator in Vim composes with them.""",
      [
          move("v01l1", "Left and right",
               "Move the cursor onto the `w` of `world` using only `l`.",
               ["hello world"], (0, 0), (0, 6), "llllll", 6,
               "Six presses of `l`. Count the characters — `hello ` is six."),
          move("v01l2", "Down and up",
               "`j` goes down, `k` goes up. Get to the last line.",
               ["line one", "line two", "line three"], (0, 0), (2, 0), "jj", 2,
               "`j` twice."),
          move("v01l3", "Navigate a small function",
               "Put the cursor on the `p` of `print` (line 2, column 4).",
               PY1, (0, 0), (1, 4), "jllll", 5,
               "Down once, then right four times."),
          drill("v01l4", "Insert before the cursor",
                "`i` enters Insert mode **before** the cursor. Type the missing word, "
                "then press `Esc`. Never leave a lesson in Insert mode.",
                ["hola "], (0, 5), ["hola mundo"], "imundo<Esc>", 7,
                "`i` then `mundo` then `Esc`."),
          drill("v01l5", "Append after the cursor",
                "`a` enters Insert **after** the cursor. This is the difference that "
                "trips up every beginner: at the end of a line, `i` cannot reach the "
                "last position — `a` can.",
                ["def f()"], (0, 6), ["def f():"], "a:<Esc>", 3,
                "The cursor is on `)`. `a` puts you just past it."),
          drill("v01l6", "Escape from a mistake",
                "You are going to make a mess and then undo it. Type `xyz`, press "
                "`Esc`, then press `u` to undo. Vim's undo is per *insertion*, not "
                "per keystroke — the whole `xyz` disappears at once.",
                ["clean"], (0, 0), ["clean"], "ixyz<Esc>u", 6,
                "`i` `x` `y` `z` `Esc` `u`."),
          quiz("v01l7", "Which mode?",
               "A quick check before moving on.",
               "You just pressed `Esc`, then `d`, and nothing seems to have happened. "
               "What is Vim waiting for?",
               ["Nothing — `d` did nothing and was discarded",
                "A motion or text object to tell `d` what to delete",
                "A second `Esc` to confirm",
                "A file name"],
               1,
               "`d` is an *operator*. It is incomplete on its own and waits for a motion "
               "(`dw`, `d$`) or a doubled key (`dd`). This pending state is the heart of "
               "Vim's grammar — Level 3 is built on it. `Esc` cancels it."),
      ],
      links=[{"track": "typing", "level": "t02",
              "note": "hjkl are home-row keys — Typing Level 2 drills exactly this cluster."}])

# ============================================================ L2
level(2, "v02", "Efficient Motions",
      "Stop pressing l forty times.",
      """`hjkl` is for fine adjustment. Real navigation happens in words and lines.

**Within a line**

| Key | Moves to |
|---|---|
| `w` | start of next **word** (punctuation counts as a word) |
| `W` | start of next **WORD** (whitespace-delimited only) |
| `b` | back to start of word |
| `e` | end of current/next word |
| `0` | column 0 |
| `^` | first non-blank character |
| `$` | end of line |

`word` vs `WORD` matters constantly in code: in `self.items[0]`, `w` stops at
`.`, `items`, `[`, `0`, `]` — five stops. `W` treats the whole thing as one.

**Across the file**

| Key | Moves to |
|---|---|
| `gg` | first line |
| `G` | last line |
| `{n}G` | line n (also `:{n}`) |
| `{` `}` | previous / next blank line |

**Counts.** Almost every motion takes a count prefix: `3w` = three words forward,
`5j` = five lines down. `count + motion` is the first half of Vim's grammar.""",
      [
          move("v02l1", "Word by word",
               "Get to `three` with word motions, not `l`.",
               ["one two three four"], (0, 0), (0, 8), "ww", 2, "`w` twice."),
          move("v02l2", "Counted words",
               "Same idea, with a count. Land on `four`.",
               ["one two three four"], (0, 0), (0, 14), "3w", 2,
               "`3w` — one keystroke cheaper than `www`."),
          move("v02l3", "End of word",
               "`e` lands on the *last* character of a word. Get to the `e` of `three`.",
               ["one two three four"], (0, 0), (0, 12), "3e", 2, "`3e`."),
          move("v02l4", "Backwards",
               "From the end, walk back to `two`.",
               ["one two three four"], (0, 15), (0, 4), "3b", 2, "`3b`."),
          move("v02l5", "word vs WORD",
               "`self.items[0]` is five *words* but one **WORD**. `E` jumps to the end "
               "of the WORD; lowercase `e` would need five presses to get there.",
               ["self.items[0] = value"], (0, 0), (0, 12), "E", 1,
               "`E` — the WORD version of `e`."),
          move("v02l6", "Line ends",
               "`$` goes to the last character; `^` to the first non-blank. "
               "Get to the closing brace.",
               ["    return {'ok': True}"], (0, 4), (0, 22), "$", 1, "`$`."),
          move("v02l7", "First non-blank",
               "The cursor is at the end. `0` would put you in the indentation; "
               "`^` puts you on real content.",
               ["    return {'ok': True}"], (0, 22), (0, 4), "^", 1, "`^`."),
          move("v02l8", "Top and bottom",
               "Jump to the last line, then to line 3.",
               ["one", "two", "three", "four", "five"], (0, 0), (2, 0), "G3G", 3,
               "`G` then `3G`. `3G` alone would also do it — but practise both."),
          move("v02l9", "Paragraph hops",
               "`}` jumps to the next blank line. Get from the first function to the second.",
               ["def a():", "    pass", "", "def b():", "    pass"],
               (0, 0), (3, 0), "}j", 2, "`}` lands on the blank line; then `j`."),
      ],
      links=[{"track": "python", "level": "p02",
              "note": "The buffers you navigate here are the Python constructs of Level 2."}])

# ============================================================ L3
level(3, "v03", "The Grammar: Operator + Motion",
      "Learn one rule, get a hundred commands for free.",
      """This is the level that turns Vim from "a weird editor" into a language.

```
   [count]  operator  [count]  motion
      2        d                w        →  delete two words
               c                $        →  change to end of line
      3        y                y        →  yank three lines
```

**Operators**

| Op | Does |
|---|---|
| `d` | delete (into a register — it is a *cut*, not a discard) |
| `c` | change = delete, then enter Insert mode |
| `y` | yank (copy) |
| `>` `<` | indent / outdent |
| `gu` `gU` | lowercase / uppercase |

**Doubling an operator makes it act on whole lines**: `dd`, `cc`, `yy`, `>>`.

You already know a dozen motions from Level 2. Multiply: `dw` `d$` `d0` `dG`
`dgg` `d}` `cw` `c$` `ce` `yw` `y$` `yG` `>}` `gUw`… none of these had to be
memorised separately. That is the whole point.

**`c` deletes slightly differently from `d`.** `cw` behaves like `ce` — it
changes to the *end* of the word, not up to the next one, because deleting the
trailing space before typing a replacement is almost never what you want.""",
      [
          drill("v03l1", "Delete a word",
                "`dw` deletes from the cursor to the start of the next word.",
                ["remove this word please"], (0, 7), ["remove word please"], "dw", 2,
                "Cursor is on `t` of `this`."),
          drill("v03l2", "Delete to end of line",
                "`d$` — or its synonym `D`.",
                ["keep this # delete this trailing comment"], (0, 10),
                ["keep this "], "d$", 2, "`d$`, cursor already on `#`."),
          drill("v03l3", "Change a word",
                "`cw` deletes the word and drops you in Insert mode. Replace `foo` "
                "with `bar`, then `Esc`.",
                ["value = foo"], (0, 8), ["value = bar"], "cwbar<Esc>", 6, ""),
          drill("v03l4", "Delete a line",
                "`dd`. The line is gone and the register holds it.",
                ["keep", "delete me", "keep"], (1, 0), ["keep", "keep"], "dd", 2, ""),
          drill("v03l5", "Counted line delete",
                "`3dd` removes three lines. Delete the whole body of the function.",
                ["def f():", "    a = 1", "    b = 2", "    c = 3", "    return a"],
                (1, 4), ["def f():", "    return a"], "3dd", 3, "`3dd` from line 2."),
          drill("v03l6", "Delete to end of file",
                "`dG` deletes from the current line to the last line. Truncate the "
                "file after the docstring.",
                ['"""Module docstring."""', "", "import junk", "junk.run()"],
                (2, 0), ['"""Module docstring."""', ""], "dG", 2, ""),
          drill("v03l7", "Change to end of line",
                "`C` is `c$`. Replace the whole return expression.",
                ["    return old_value"], (0, 11), ["    return None"], "CNone<Esc>", 6,
                "Cursor sits on `o` of `old_value`."),
          drill("v03l8", "Indent a block",
                "`>` with a motion, or `>>` for one line. Indent both body lines by "
                "one level using a count.",
                ["def f():", "a = 1", "return a"], (1, 0),
                ["def f():", "    a = 1", "    return a"], "2>>", 3,
                "`2>>` — the count goes before the doubled operator."),
          drill("v03l9", "Uppercase a word",
                "`gU` + motion. Turn the constant name into SCREAMING_CASE.",
                ["max_retries = 3"], (0, 0), ["MAX_RETRIES = 3"], "gUe", 3,
                "`gUe` — uppercase to end of word. `e` because `_` is a word character."),
          quiz("v03l10", "Compose it yourself",
               "You have the grammar now. Use it.",
               "The cursor is at the start of a 40-line function. You want to delete "
               "the function and copy nothing. Which is the cheapest correct command?",
               ["40dd", '"_d}', "d}", "dG"],
               2,
               "`d}` deletes to the next blank line — no counting required, and it "
               "adapts if the function is 38 or 44 lines. `40dd` needs you to count; "
               "`dG` deletes the rest of the file. `\"_d}` also works and additionally "
               "avoids clobbering the register (Level 7)."),
      ],
      links=[{"track": "typing", "level": "t11",
              "note": "Typing Level 11 drills these exact sequences as text."}])

# ============================================================ L4
level(4, "v04", "Entering Insert Mode Well",
      "Six doors into Insert mode. Pick the right one.",
      """Beginners use `i` for everything and then navigate inside Insert mode with
arrow keys. That is the slow path. Choose the entry point that lands the cursor
where you want it:

| Key | Enters Insert… |
|---|---|
| `i` | before the cursor |
| `a` | after the cursor |
| `I` | at the first non-blank of the line |
| `A` | at the end of the line |
| `o` | on a new line **below** |
| `O` | on a new line **above** |
| `s` | deleting the character under the cursor |
| `S` / `cc` | deleting the whole line's content, keeping indent |

`A` and `o` are the two you will use most: appending to a line and opening a new
one are what writing code actually consists of.

**Inside Insert mode, do as little as possible.** No arrow keys, no mouse. Type
the text, press `Esc`, move in Normal mode. Every excursion inside Insert mode is
a change Vim cannot repeat with `.` (Level 8).""",
      [
          drill("v04l1", "Append at end of line",
                "`A` — the single most useful insert command. Add the missing colon.",
                ["def process(rows)"], (0, 4), ["def process(rows):"], "A:<Esc>", 3, ""),
          drill("v04l2", "Insert at first non-blank",
                "`I` ignores indentation. Comment out the line.",
                ["    result = compute()"], (0, 15), ["    # result = compute()"],
                "I# <Esc>", 4, "`I` then `# ` then `Esc`."),
          drill("v04l3", "Open a line below",
                "`o` from anywhere on the line.",
                ["import os"], (0, 3), ["import os", "import sys"],
                "oimport sys<Esc>", 12, ""),
          drill("v04l4", "Open a line above",
                "`O`. Add the shebang.",
                ["import sys"], (0, 0), ["#!/usr/bin/env python3", "import sys"],
                "O#!/usr/bin/env python3<Esc>", 24, ""),
          drill("v04l5", "Substitute one character",
                "`s` deletes the character under the cursor and inserts. "
                "Fix the operator.",
                ["if x = 1:"], (0, 5), ["if x == 1:"], "s==<Esc>", 4,
                "Cursor is on `=`. `s` then `==`."),
          drill("v04l6", "Replace the whole line",
                "`S` (or `cc`) clears the line but keeps its indentation.",
                ["def f():", "    return wrong_thing()"], (1, 8),
                ["def f():", "    return None"], "Sreturn None<Esc>", 14, ""),
          drill("v04l7", "o keeps indentation",
                "Notice that `o` inherits the current line's indent — you do not type "
                "the spaces. Add a second statement to the body.",
                ["def f():", "    a = 1"], (1, 0),
                ["def f():", "    a = 1", "    b = 2"], "ob = 2<Esc>", 7, ""),
          quiz("v04l8", "A vs i at end of line",
               "One of Vim's genuine gotchas.",
               "The cursor is on the final `)` of `foo()` and you want to type `:` "
               "after it. `i:` gives you `foo(:)`. Why?",
               ["`i` is broken at end of line",
                "`i` inserts *before* the cursor, and the cursor is on `)`, not past it",
                "You need to be in Replace mode",
                "`:` opens the command line"],
               1,
               "In Normal mode the cursor sits *on* a character, never between two. "
               "`i` inserts to its left. To get to the right of the last character you "
                "need `a` — or `A`, which goes to the end of the line regardless of "
                "where you are."),
      ])

# ============================================================ L5
level(5, "v05", "Find & Till: Surgical Line Motions",
      "f F t T ; , — the fastest way to a character.",
      """`f{char}` jumps **onto** the next occurrence of `{char}` on the current line.
`t{char}` stops **till** just before it. Capitals search backwards.

| Key | Meaning |
|---|---|
| `f,` | forward onto the next `,` |
| `F,` | backward onto the previous `,` |
| `t)` | forward, stopping before `)` |
| `T(` | backward, stopping after `(` |
| `;` | repeat the last f/F/t/T |
| `,` | repeat it in the opposite direction |

These compose with operators, which is where they earn their keep:

- `dt)` — delete up to the closing paren
- `ct,` — change up to the next comma
- `df;` — delete through the semicolon
- `yt=` — yank everything before the `=`

**`f` vs `t` in one sentence:** use `f` when you want the character gone or
included, `t` when you want to stop short of it. `dt)` keeps the `)`; `df)`
eats it.

The `;` repeat is what makes this fast: `f,` then `;;;` walks a comma-separated
list. And `dt)` then `;` will *not* work as you expect — `.` (Level 8) is the
tool for repeating a change.""",
      [
          move("v05l1", "Jump to a character",
               "Land on the `=`.",
               ["total = a + b + c"], (0, 0), (0, 6), "f=", 2, "`f=`."),
          move("v05l2", "Till, not onto",
               "`t(` stops one before. Land on the `s` of `process`, "
               "i.e. just before `(`.",
               ["result = process(rows)"], (0, 9), (0, 15), "t(", 2, "`t(`."),
          move("v05l3", "Repeat with ;",
               "Walk to the third comma.",
               ["f(a, b, c, d)"], (0, 0), (0, 9), "f,;;", 4, "`f,` then `;` twice."),
          move("v05l4", "Search backwards",
               "`F` goes left. From the end, land on the first `_`.",
               ["max_retry_count"], (0, 14), (0, 3), "F_F_", 4,
               "`F_` twice. (`,` would reverse direction, not repeat it.)"),
          drill("v05l5", "Delete to a character",
                "`dt)` — delete the arguments but keep the parentheses.",
                ["call(a, b, c)"], (0, 5), ["call()"], "dt)", 3, ""),
          drill("v05l6", "Change up to a comma",
                "`ct,` — replace the first argument.",
                ["fn(old, keep, keep)"], (0, 3), ["fn(new, keep, keep)"],
                "ct,new<Esc>", 6, ""),
          drill("v05l7", "Delete through a character",
                "`df ` (with a space) deletes the word *and* its trailing space.",
                ["drop this keep this"], (0, 0), ["this keep this"], "df ", 3, ""),
          drill("v05l8", "Yank up to a character",
                "`yt:` copies everything before the colon, `A` appends, `p` pastes it. "
                "`t` stops *before* the target, so the colon itself is not copied.",
                ["name: value"], (0, 0), ["name: value -> name"],
                "yt:A -> <Esc>p", 10,
                "`yt:` yanks `name`; `A -> ` appends; `Esc`; `p` puts."),
          quiz("v05l9", "f or t?",
                "Pick the right one.",
                "You are on the `l` of `logger.debug(payload)` and want to delete "
                "everything from there through the dot, leaving `debug(payload)`. Which?",
                ["dt.", "df.", "dw", "de"],
                1,
                "`df.` deletes *through* the `.` — inclusive. `dt.` would stop before it "
                "and leave `.debug(payload)`. `dw` stops at the `.` too (punctuation "
                "starts a new word)."),
      ],
      links=[{"track": "typing", "level": "t09",
              "note": "`dt)` and `ci{` need brackets — AltGr combos drilled in Typing Level 9."}])

# ============================================================ L6
level(6, "v06", "Text Objects",
      "Edit by structure, not by counting characters.",
      """Text objects are the second half of Vim's grammar, and the half that
actually changes how you work. Instead of *"delete four characters"* you say
*"delete the thing I am inside of"*.

The pattern is `{operator}{i|a}{object}`:

- `i` = **inner** — the contents
- `a` = **around** — the contents *plus* the delimiters or trailing space

| Object | Is |
|---|---|
| `w` `W` | word / WORD |
| `"` `'` `` ` `` | quoted string |
| `(` `)` `b` | parentheses |
| `[` `]` | square brackets |
| `{` `}` `B` | braces |
| `<` `>` | angle brackets |
| `p` | paragraph |

**The cursor does not need to be on the delimiter.** Anywhere inside works.
`ci"` from the middle of a string replaces the string. That property is what
makes text objects fast: no positioning step.

The four you will use every day: **`ciw` `ci"` `ci(` `di{`**. Learn those and
the rest follow.""",
      [
          drill("v06l1", "Inner word",
                "`ciw` from anywhere in the word. The cursor is mid-word — "
                "`cw` would only change the tail.",
                ["rename_this_variable = 1"], (0, 7), ["total = 1"],
                "ciwtotal<Esc>", 9, ""),
          drill("v06l2", "Around word",
                "`daw` also eats the trailing space.",
                ["remove extra word here"], (0, 7), ["remove word here"], "daw", 3, ""),
          drill("v06l3", "Inner quotes",
                "`ci\"` from the middle of the string.",
                ["path = \"/old/location\""], (0, 12), ["path = \"/new\""],
                "ci\"/new<Esc>", 8, ""),
          drill("v06l4", "Around quotes",
                "`da'` removes the string *and* its quotes.",
                ["value = 'text' + rest"], (0, 10), ["value =  + rest"], "da'", 3, ""),
          drill("v06l5", "Inner parentheses",
                "`ci(` replaces the argument list.",
                ["result = compute(a, b, c)"], (0, 19), ["result = compute(x)"],
                "ci(x<Esc>", 5, ""),
          drill("v06l6", "Inner brackets",
                "`di[` empties a list literal — cursor inside the brackets.",
                ["items = [1, 2, 3, 4]"], (0, 12), ["items = []"], "di[", 3, ""),
          drill("v06l7", "Inner braces across lines",
                "Text objects span lines. Empty the dict body.",
                ["cfg = {", "    'a': 1,", "    'b': 2,", "}"], (1, 4),
                ["cfg = {", "}"], "di{", 3,
                "`di{` from inside — the whole multi-line inner region goes."),
          drill("v06l8", "Around parentheses",
                "`da(` takes the parens too. Turn a call into a bare name.",
                ["x = func(a, b)"], (0, 10), ["x = func"], "da(", 3, ""),
          drill("v06l9", "Inner paragraph",
                "`dip` deletes the block of non-blank lines around the cursor.",
                ["keep", "", "gone", "gone", "", "keep"], (2, 0),
                ["keep", "", "", "keep"], "dip", 3, ""),
          drill("v06l10", "Yank a string, paste it",
                "Combine: yank the inner string, then replace the second one with it.",
                ["a = 'hola'", "b = 'xxxx'"], (0, 6),
                ["a = 'hola'", "b = 'hola'"], "yi'jvi'p", 8,
                "`yi'` yanks `hola`; `j` down; `vi'` selects the other string; `p` "
                "pastes over the selection. (`ci'` then `P` does *not* work — after "
                "`Esc` the cursor sits on the quote, not inside it.)"),
      ],
      links=[{"track": "typing", "level": "t09",
              "note": "Every bracket in these exercises is an AltGr combo on ES QWERTY."},
             {"track": "python", "level": "p03",
              "note": "Lists, dicts and strings — the objects you just learned to edit."}])

# ============================================================ L7
level(7, "v07", "Registers, Yank & Put",
      "Vim's clipboard is 26 clipboards.",
      """Every delete is a cut. `dd` puts the line in the **unnamed register** `\"`,
which is also where `x`, `c`, `s` and `y` write. That is why beginners lose
their yank: `yy` then `dd` then `p` pastes the *deleted* line.

**Putting**

| Key | Does |
|---|---|
| `p` | put after cursor (charwise) / below (linewise) |
| `P` | put before cursor / above |

Whether a put is charwise or linewise depends on how the text was captured, not
on how you paste it. `yy` then `p` always makes a new line; `yiw` then `p` always
inserts inline.

**Named registers** `a`–`z`: prefix any command with `"{reg}`.

```
"ayy    yank this line into register a
"ap     put register a
"Ayy    APPEND this line to register a   (capital = append)
"_dd    delete into the black hole — does not touch any register
```

**Read-only registers worth knowing:** `"0` always holds the last *yank* (never
a delete) — so `"0p` recovers the yank you thought you lost. `"%` is the file
name, `".` the last inserted text, `"+` the system clipboard.

The classic idioms: **`yyp`** duplicate a line, **`ddp`** swap two lines,
**`xp`** swap two characters.""",
      [
          drill("v07l1", "Duplicate a line",
                "`yyp` — yank the line, put it below.",
                ["config = {}", "other = 1"], (0, 0),
                ["config = {}", "config = {}", "other = 1"], "yyp", 3, ""),
          drill("v07l2", "Swap two lines",
                "`ddp` — delete the line, put it back after the next one.",
                ["second", "first"], (0, 0), ["first", "second"], "ddp", 3, ""),
          drill("v07l3", "Swap two characters",
                "`xp` — the classic typo fix.",
                ["teh cat"], (0, 1), ["the cat"], "xp", 2,
                "Cursor on `e`: `x` cuts it, `p` puts it after `h`."),
          drill("v07l4", "Move a line far away",
                "`dd` then navigate then `p`. Move the import to the top.",
                ["def f():", "    pass", "import os"], (2, 0),
                ["import os", "def f():", "    pass"], "ddggP", 5,
                "`dd`, `gg`, then `P` to put *above* line 1."),
          drill("v07l5", "Named register",
                "Yank the first line into register `a`, then put it at the bottom "
                "without disturbing anything you delete in between.",
                ["header", "body", "junk"], (0, 0),
                ["header", "body", "header"], "\"ayyjjdd\"ap", 11,
                "`\"ayy` then `jj` then `dd` (clobbers the unnamed register, not `a`) "
                "then `\"ap`."),
          drill("v07l6", "The black hole register",
                "`\"_dd` deletes without touching any register — your yank survives.",
                ["keep me", "delete me", "target"], (0, 0),
                ["keep me", "target", "keep me"], "yyj\"_ddjp", 9,
                "`yy` yanks line 1; `j` `\"_dd` deletes line 2 into the void; "
                "`j`? — you are now on `target`; `p` puts `keep me` below."),
          drill("v07l7", "Append to a register",
                "Capital register letters append. Collect both TODO lines into `a`.",
                ["TODO one", "noise", "TODO two"], (0, 0),
                ["TODO one", "noise", "TODO two", "TODO one", "TODO two"],
                "\"ayyjj\"Ayy\"ap", 13,
                "`\"ayy`, `jj`, `\"Ayy` (append), then `\"ap` puts both lines."),
          quiz("v07l8", "Where did my yank go?",
               "The single most common register mistake.",
               "You do `yy` on line 1, then `dd` on line 5, then `p`. What gets pasted, "
               "and how do you paste what you actually wanted?",
               ["Line 1; nothing to fix",
                "Line 5; use `\"0p` to get the yanked line back",
                "Line 5; the yank is gone forever",
                "Both lines"],
               1,
               "`dd` overwrote the unnamed register. But register `0` only ever holds "
               "the last *yank*, so `\"0p` still has line 1. The habit that avoids the "
               "problem entirely: delete with `\"_d` when you are about to paste."),
      ])

# ============================================================ L8
level(8, "v08", "Undo, Repeat & the Dot Formula",
      "The most valuable key in Vim is `.`",
      """`.` repeats the last **change** — not the last motion, not the last command.
A change is anything that modified the buffer: `x`, `dw`, `ciwfoo<Esc>`, `A;<Esc>`.

**The dot formula.** Structure edits so that:

> one keystroke moves to the next target, one keystroke (`.`) makes the change.

```
Goal: add a semicolon to the end of every line
  A;<Esc>      make the change on line 1
  j.           down, repeat
  j.  j.  j.   ...
```

```
Goal: rename every `old` in the file
  /old<CR>     search
  cwnew<Esc>   change the first one
  n.  n.  n.   next match, repeat
```

This beats a macro for anything under ~8 repetitions and costs nothing to set up.

**Undo**

| Key | Does |
|---|---|
| `u` | undo one change |
| `Ctrl-r` | redo |
| `U` | undo all changes on the last line touched |

Undo granularity is per *Insert session*, which is another reason to press `Esc`
often: `iabc<Esc>` then `idef<Esc>` gives you two undo steps; typing `abcdef` in
one session gives you one.""",
      [
          drill("v08l1", "Repeat a change",
                "Delete the first word, then repeat with `.`",
                ["junk junk keep"], (0, 0), ["keep"], "dw.", 3, ""),
          drill("v08l2", "The A; formula",
                "Add a semicolon to every line using `A;<Esc>` then `j.`",
                ["a = 1", "b = 2", "c = 3"], (0, 0),
                ["a = 1;", "b = 2;", "c = 3;"], "A;<Esc>j.j.", 9, ""),
          drill("v08l3", "Dot with a text object",
                "`ciwX<Esc>` then move and `.` — the whole change repeats, "
                "including the typed text.",
                ["aaa bbb ccc"], (0, 0), ["xxx bbb xxx"], "ciwxxx<Esc>2w.", 11,
                "`ciwxxx<Esc>` changes the first; `2w` to the third; `.` repeats."),
          drill("v08l4", "Dot with search",
                "`/bug<CR>` `ciwfix<Esc>` `n` `.`",
                ["bug here", "ok", "bug there"], (0, 0),
                ["fix here", "ok", "fix there"], "/bug\rciwfix<Esc>n.", 15, ""),
          drill("v08l5", "Undo and redo",
                "Delete all three lines one at a time, undo twice, redo once. "
                "You should end with one line left.",
                ["a", "b", "c"], (0, 0), ["c"], "dddddduu<C-r>", 11,
                "Three `dd` empties the buffer; two `u` bring back `b` and `c`; "
                "one `Ctrl-r` removes `b` again."),
          drill("v08l6", "Undo granularity",
                "Type `foo`, `Esc`, type `bar`, `Esc`, then a single `u`. "
                "Only `bar` should disappear.",
                [""], (0, 0), ["foo"], "ifoo<Esc>abar<Esc>u", 13, ""),
          quiz("v08l7", "What does . repeat?",
               "Be precise about this.",
               "You press `dw`, then `j`, then `.`. What happens?",
               ["Deletes a word, moves down, moves down again",
                "Deletes a word, moves down, deletes another word",
                "Deletes two words on the first line",
                "Nothing — `.` needs an operator"],
               1,
               "`.` repeats the last *change*, and `j` is a motion, not a change. So "
               "the pending change is still `dw`. This is exactly why the dot formula "
               "works: motions are free, they never disturb the repeat."),
      ],
      links=[{"track": "python", "level": "p05",
              "note": "Refactoring loops into comprehensions is dot-formula work."}])

# ============================================================ L9
level(9, "v09", "Visual Modes",
      "See the selection before you act on it.",
      """Visual mode inverts Vim's usual order: instead of `operator` then `motion`,
you select first and then apply.

| Key | Mode |
|---|---|
| `v` | characterwise |
| `V` | linewise |
| `Ctrl-v` | **blockwise** — rectangular |
| `gv` | reselect the last visual selection |
| `o` | jump to the other end of the selection |

In Visual mode, operators apply to the selection: `d` `c` `y` `>` `<` `u` `U`
`~` `J` `r`. Text objects work too: `vi(`, `vap`.

**When to use Visual mode:** when the extent of the edit is easier to *see* than
to *describe*. For anything you can name — a word, a string, a paragraph —
operator + text object is faster and, crucially, repeatable with `.`.

**Blockwise is the exception** — it does something no operator can:

```
Ctrl-v  jjj  I# <Esc>     comment out four lines
Ctrl-v  jjj  $A,<Esc>     append a comma to four lines
Ctrl-v  jjj  d            delete a column
```

`I` and `A` in blockwise mode insert on *every* line of the block once you press
`Esc`. That is the killer feature.""",
      [
          drill("v09l1", "Characterwise select and delete",
                "`v` then a motion, then `d`.",
                ["delete these keep"], (0, 0), ["keep"], "v2eld", 5,
                "`v2e` selects `delete these`; `l` extends over the space; `d`."),
          drill("v09l2", "Linewise select",
                "`V` then `j` then `d`.",
                ["a", "b", "c", "d"], (0, 0), ["c", "d"], "Vjd", 3, ""),
          drill("v09l3", "Uppercase a selection",
                "`viwU` — select the inner word, uppercase it.",
                ["make this loud"], (0, 5), ["make THIS loud"], "viwU", 4, ""),
          drill("v09l4", "Reselect with gv",
                "Not everything needs gv, but know it exists. Indent, then indent "
                "again by reselecting.",
                ["x", "y"], (0, 0), ["        x", "        y"], "Vj>gv>", 6,
                "`Vj>` indents; `gv` reselects; `>` again."),
          drill("v09l5", "Block comment",
                "`Ctrl-v` `jj` `I# ` `Esc` — comment three lines at once.",
                ["a = 1", "b = 2", "c = 3"], (0, 0),
                ["# a = 1", "# b = 2", "# c = 3"], "<C-v>jjI# <Esc>", 9, ""),
          drill("v09l6", "Block append",
                "`Ctrl-v` `jj` `$` `A,` `Esc` — add a trailing comma to each line.",
                ["'a'", "'b'", "'c'"], (0, 0), ["'a',", "'b',", "'c',"],
                "<C-v>jj$A,<Esc>", 9, ""),
          drill("v09l7", "Delete a column",
                "`Ctrl-v` `jj` `d` removes the leading `- ` bullet from each line.",
                ["- one", "- two", "- three"], (0, 0), ["one", "two", "three"],
                "<C-v>jjld", 6, "`<C-v>` `jj` `l` widens the block to two columns, `d`."),
          drill("v09l8", "Join a selection",
                "`VjjJ` joins the selected lines into one.",
                ["one", "two", "three"], (0, 0), ["one two three"], "VjjJ", 4, ""),
          quiz("v09l9", "Visual or operator?",
               "A judgement call worth getting right.",
               "You need to delete the contents of a string 40 times across a file. "
               "Which approach is better?",
               ["`vi\"d` each time — you can see what you are selecting",
                "`di\"` once, then `n.` — because `.` repeats it and Visual mode "
                "selections are not repeatable in the same way",
                "Select all with `ggVG` and retype",
                "Use the mouse"],
               1,
               "Operator + text object produces a repeatable change. A visual selection "
               "followed by `d` is repeatable with `.` only over the *same size* region, "
               "which is rarely what you want. Reach for Visual mode when the region is "
               "irregular; reach for text objects when it has a name."),
      ],
      links=[{"track": "typing", "level": "t08",
              "note": "`Ctrl-v` and `|` chaining live on the AltGr row."}])

# ============================================================ L10
level(10, "v10", "Ex Commands & Ranges",
      "`:` is a second, line-oriented language.",
      """Everything after `:` operates on **lines**, addressed by a range.

**Ranges**

| Range | Means |
|---|---|
| *(none)* | the current line |
| `%` | the whole file |
| `1,10` | lines 1 to 10 |
| `.,$` | current line to end |
| `'<,'>` | the last visual selection (Vim types this for you after `V`) |
| `.,+3` | current line and the next three |

**Substitute** — `:{range}s/{pattern}/{replacement}/{flags}`

```
:s/old/new/           first match on this line
:%s/old/new/g         every match in the file
:%s/old/new/gc        ...with confirmation
:%s/\\<log\\>/logger/g   whole word only
:'<,'>s/^/# /         prefix the selection with #
```

Flags: `g` all matches on the line, `c` confirm, `i` ignore case, `e` no error
if not found.

**Global** — `:{range}g/{pattern}/{command}` runs an ex command on every matching
line. This is the most powerful thing in Vim, and almost nobody learns it.

```
:g/TODO/d             delete every line containing TODO
:g!/def /d            delete every line NOT containing 'def '   (also :v/def /d)
:g/^$/d               squeeze out blank lines
:g/import/normal A  # checked      run normal-mode keys on matching lines
```

**`:normal`** runs Normal-mode keystrokes over a range — the bridge between the
two languages. `:%normal A;` appends a semicolon to every line in the file.

Other essentials: `:m` move lines, `:t` (or `:co`) copy lines, `:sort`,
`:{n}` jump to line n, `:w` write, `:q` quit, `:wq`/`:x` both.""",
      [
          drill("v10l1", "Substitute on one line",
                "`:s/old/new/`",
                ["path = old_dir + name"], (0, 0), ["path = new_dir + name"],
                ":s/old/new/\r", 12, ""),
          drill("v10l2", "Substitute everywhere",
                "`:%s/.../.../g` — every occurrence in the file.",
                ["foo bar foo", "baz foo"], (0, 0), ["qux bar qux", "baz qux"],
                ":%s/foo/qux/g\r", 14, ""),
          drill("v10l3", "Whole-word substitution",
                "`\\<` and `\\>` anchor word boundaries — without them `log` also "
                "matches inside `login`.",
                ["log(x)", "login(y)", "log(z)"], (0, 0),
                ["logger(x)", "login(y)", "logger(z)"],
                ":%s/\\<log\\>/logger/g\r", 21, ""),
          drill("v10l4", "Delete matching lines",
                "`:g/pattern/d`",
                ["keep 1", "# comment", "keep 2", "# another"], (0, 0),
                ["keep 1", "keep 2"], ":g/^#/d\r", 9, ""),
          drill("v10l5", "Keep only matching lines",
                "`:v/pattern/d` (inverse global) deletes everything that does *not* match.",
                ["def a():", "    pass", "def b():", "    pass"], (0, 0),
                ["def a():", "def b():"], ":v/def/d\r", 10, ""),
          drill("v10l6", "Squeeze blank lines",
                "`:g/^$/d` removes every empty line.",
                ["a", "", "b", "", "", "c"], (0, 0), ["a", "b", "c"],
                ":g/^$/d\r", 9, ""),
          drill("v10l7", "Range on a selection",
                "Select two lines with `Vj`, then `:` — Vim inserts `'<,'>` for you. "
                "Comment them.",
                ["a = 1", "b = 2", "c = 3"], (0, 0),
                ["# a = 1", "# b = 2", "c = 3"], "Vj:s/^/# /\r", 12, ""),
          drill("v10l8", "normal over a range",
                "`:%normal A;` runs `A;` on every line.",
                ["a = 1", "b = 2"], (0, 0), ["a = 1;", "b = 2;"],
                ":%normal A;\r", 12, ""),
          drill("v10l9", "Move a line",
                "`:m0` moves the current line to the top; `:m$` to the bottom.",
                ["body", "header"], (1, 0), ["header", "body"], ":m0\r", 5, ""),
          drill("v10l10", "Sort a block",
                "`:%sort` — and `:sort u` also removes duplicates.",
                ["pear", "apple", "pear", "fig"], (0, 0), ["apple", "fig", "pear"],
                ":%sort u\r", 10, ""),
          quiz("v10l11", "g plus normal",
               "The combination that replaces most macros.",
               "Which command appends `  # checked` to every line containing `import`?",
               [":%s/import/  # checked/g",
                ":g/import/normal A  # checked",
                ":normal A  # checked",
                ":g/import/A  # checked"],
               1,
               "`:g/pat/normal {keys}` runs Normal-mode keystrokes on each matching "
               "line — the full power of Normal mode applied selectively. Option 1 "
               "would *replace* the word `import`; option 4 is not valid ex syntax."),
      ],
      links=[{"track": "typing", "level": "t10",
              "note": "Typing Level 10 drills these exact ex command lines."}])

# ============================================================ L11
level(11, "v11", "Marks, Search & Macros",
      "Record once, replay a hundred times.",
      """**Marks** — `m{a-z}` sets a mark, `` `{a-z} `` jumps to it (exact position),
`'{a-z}` jumps to its line. Automatic marks worth knowing: `` `` `` is where you
were before the last jump (press it twice to bounce), `` `. `` is the last edit,
`` `^ `` is where you last left Insert mode.

**Search** — `/pattern` forward, `?pattern` backward, `n`/`N` next/previous,
`*` searches for the word under the cursor. Search is also a motion: `d/END<CR>`
deletes up to the next `END`.

**Macros** — a macro is just a register holding keystrokes.

```
qa          start recording into register a
...         do the edit, ending in a repeatable position
q           stop recording
@a          replay
10@a        replay ten times
@@          replay the last macro again
```

**Three rules for macros that don't break:**

1. **Start from a predictable position** — begin with `0` or `^`.
2. **End positioned for the next iteration** — usually with `j`.
3. **Use relative motions**, never absolute line numbers.

A macro that fails partway through simply stops (Vim aborts a count-repeated
macro on the first error), which is a feature: `100@a` on a 12-line file does
12 iterations and stops. So overshoot deliberately.

**Macro or dot?** If the repeated edit is a single change, use `.`. If it is a
*sequence* — move, edit, move, edit — record a macro.""",
      [
          drill("v11l1", "Set and jump to a mark",
                "Mark the first junk line with `ma`, jump to the end, delete back to "
                "the mark. `d'a` is linewise and includes both ends.",
                ["start", "junk", "junk", "junk"], (0, 0), ["start"],
                "jmaGd'a", 7,
                "`ma` marks; `G` last line; `d'a` deletes linewise back to mark `a` "
                "— note `'a` is linewise, `` `a `` would be charwise."),
          drill("v11l2", "Search as a motion",
                "`d/END<CR>` deletes from the cursor up to (not including) `END`.",
                ["keep DELETE THIS END rest"], (0, 5), ["keep END rest"],
                "d/END\r", 7, ""),
          drill("v11l3", "Star search",
                "`*` jumps to the next occurrence of the word under the cursor. "
                "Change the second `total`.",
                ["total = 1", "x = 2", "total = 3"], (0, 0),
                ["total = 1", "x = 2", "sum = 3"], "*ciwsum<Esc>", 9,
                "`*` searches for the word under the cursor and jumps to the next "
                "match — line 3."),
          drill("v11l4", "Record a simple macro",
                "Record `A;<Esc>j` into register `q`, then replay it twice.",
                ["a", "b", "c"], (0, 0), ["a;", "b;", "c;"],
                "qqA;<Esc>jq2@q", 12,
                "`qq` start, `A;<Esc>j` the edit, `q` stop — that already did line 1. "
                "Then `2@q` for the other two."),
          drill("v11l5", "A macro with structure",
                "Turn each line into a dict entry. Record: `I'` `Esc` `A': 0,` `Esc` `j`",
                ["alpha", "beta"], (0, 0), ["'alpha': 0,", "'beta': 0,"],
                "qwI'<Esc>A': 0,<Esc>jq@w", 22,
                "`qw` … `q` records and runs it once on line 1; `@w` does line 2."),
          drill("v11l6", "Overshoot deliberately",
                "Record `I- <Esc>j`, then replay it **50** times on a 4-line buffer. "
                "The macro aborts by itself when `j` fails on the last line, so "
                "over-counting is free — you never need to know how many lines there are.",
                ["x", "x", "x", "x"], (0, 0), ["- x", "- x", "- x", "- x"],
                "qaI- <Esc>jq50@a", 14,
                "`qa` `I- ` `Esc` `j` `q` records and already runs iteration 1; "
                "`50@a` does the rest and stops on the error."),
          drill("v11l7", "Recursive-style repeat",
                "Apply the same change down a file with `@@`.",
                ["a", "b", "c", "d"], (0, 0), ["-a", "-b", "-c", "-d"],
                "qzI-<Esc>jq@z@@@@", 13,
                "`qz…q` runs once, `@z` again, then `@@` twice. `@@` replays whichever "
                "macro you ran last, so you stop having to name the register."),
          quiz("v11l8", "Why did my macro break?",
               "The most common macro bug.",
               "You record a macro that starts by pressing `w` to get to the second "
                "word. It works on line 1 and mangles line 4. Most likely cause?",
               ["Register overflow",
                "Line 4 has different structure, so `w` lands somewhere else — the "
                "macro used a fragile motion instead of an anchored one",
                "You need to re-record after every line",
                "Macros only work on 3 lines"],
               1,
               "Macros are literal keystroke replays with no awareness of content. "
               "Anchor them: start with `0` or `^`, and prefer `f{char}` or `/pattern` "
               "over counting words, so the motion adapts to each line."),
      ])

# ============================================================ L12
level(12, "v12", "Neovim in Practice",
      "Config, LSP, buffers and windows. Making it yours.",
      """You now know Vim. This level is about **Neovim** specifically — the parts
that are not in vi.

**Buffers, windows, tabs** — three different things, and confusing them is the
usual source of pain.

- A **buffer** is a file loaded in memory. `:ls` lists them, `:b {name}` switches,
  `:bd` closes.
- A **window** is a viewport onto a buffer. `:split` / `:vsplit`,
  `Ctrl-w h/j/k/l` to move between them, `Ctrl-w q` to close.
- A **tab** is a layout of windows. Most people who want tabs actually want
  buffers.

**Configuration is Lua.** `~/.config/nvim/init.lua`:

```lua
vim.opt.number = true            -- :set number
vim.opt.relativenumber = true    -- motions become countable at a glance
vim.opt.expandtab = true
vim.opt.shiftwidth = 4
vim.g.mapleader = ' '            -- set BEFORE loading plugins

vim.keymap.set('n', '<leader>w', '<cmd>write<cr>', { desc = 'Save' })
vim.keymap.set('n', '<esc>', '<cmd>nohlsearch<cr>')
vim.keymap.set('v', '<', '<gv')  -- keep the selection after indenting
```

`relativenumber` deserves a special mention: it turns "delete the next six
lines" from counting into reading. It is the single highest-value option in the
list.

**LSP** — Neovim speaks the Language Server Protocol natively. With a Python
server (`pyright` or `ruff` + `basedpyright`) attached you get, in Normal mode:

| Key | Does |
|---|---|
| `gd` | go to definition |
| `gr` | list references |
| `K` | hover documentation |
| `<leader>rn` | rename symbol across the project |
| `<leader>ca` | code action (quick fix) |
| `[d` `]d` | previous / next diagnostic |

`<leader>rn` is worth the whole setup on its own: a semantic rename beats
`:%s/old/new/g` because it will not touch a string that happens to contain the
same characters.

**Plugin manager** — `lazy.nvim` is the current default. A minimal, real
`init.lua` is about 40 lines and gives you fuzzy finding (telescope), treesitter
highlighting, and LSP.

**How to keep improving:** `:help {topic}` is genuinely excellent — `:help
text-objects`, `:help :g`, `:help registers`. And `:checkhealth` when something
is broken.""",
      [
          drill("v12l1", "Edit your options",
                "Add `relativenumber` below `number` in a config file.",
                ["vim.opt.number = true", "vim.opt.expandtab = true"], (0, 0),
                ["vim.opt.number = true", "vim.opt.relativenumber = true",
                 "vim.opt.expandtab = true"],
                "yypfnciwrelativenumber<Esc>", 25,
                "`yyp` duplicates the line but leaves the cursor in column 0, so `ciw` "
                "there would change `vim`. Press `fn` first, to land on `number`."),
          drill("v12l2", "Add a keymap",
                "Append a leader mapping after the existing one.",
                ["vim.keymap.set('n', '<leader>w', '<cmd>write<cr>')"], (0, 0),
                ["vim.keymap.set('n', '<leader>w', '<cmd>write<cr>')",
                 "vim.keymap.set('n', '<leader>q', '<cmd>quit<cr>')"],
                "yypf>lrq:s/write/quit/\r", 23,
                "`yyp` duplicates; `f>` lands on the `>` of `<leader>`, `l` steps onto "
                "the `w`, `rq` replaces it; then `:s/write/quit/` for the command."),
          drill("v12l3", "Fix a Lua table",
                "Turn the single-line table into the idiomatic multi-line form by "
                "replacing the contents.",
                ["local opts = { noremap = true, silent = true }"], (0, 15),
                ["local opts = { silent = true }"],
                "ci{ silent = true <Esc>", 22, ""),
          drill("v12l4", "Comment out a plugin",
                "Block-comment three lines of a lazy.nvim spec with `Ctrl-v`.",
                ["{ 'nvim-telescope/telescope.nvim',",
                 "  dependencies = { 'nvim-lua/plenary.nvim' },",
                 "  config = true },"], (0, 0),
                ["-- { 'nvim-telescope/telescope.nvim',",
                 "--   dependencies = { 'nvim-lua/plenary.nvim' },",
                 "--   config = true },"],
                "<C-v>jjI-- <Esc>", 10, ""),
          drill("v12l5", "Refactor with :normal",
                "Convert every `vim.opt.X = true` line to `vim.opt.X = false` "
                "with one ex command.",
                ["vim.opt.number = true", "vim.opt.wrap = true",
                 "vim.opt.list = true"], (0, 0),
                ["vim.opt.number = false", "vim.opt.wrap = false",
                 "vim.opt.list = false"],
                ":%s/true/false/g\r", 17, ""),
          quiz("v12l6", "Buffers vs windows",
               "Get the mental model right.",
               "You have three files open and want to see two of them side by side. "
               "What do you actually need?",
               ["Three tabs", "Two windows showing two of the three buffers",
                "Three windows", "Two buffers — the third must be closed"],
               1,
               "Buffers are the files; windows are the viewports. Three buffers can "
               "coexist with any number of windows, including one. `:vsplit` then "
               "`:b {other}` gives you the side-by-side view without closing anything."),
          quiz("v12l7", "Rename correctly",
               "The last habit to build.",
               "You need to rename the function `load` to `load_config` across a "
               "Python project. Which is safest?",
               [":%s/load/load_config/g",
                ":%s/\\<load\\>/load_config/g on every file",
                "LSP `<leader>rn` on the symbol",
                "Manual search and replace with confirmation"],
               2,
               "An LSP rename understands scope: it will not rename a *different* "
               "`load` in another class, nor a `load` inside a string or comment. "
               "The regex options either over-match (option 1 hits `download`) or "
               "cannot distinguish two unrelated symbols with the same name."),
      ],
      links=[{"track": "typing", "level": "t11",
              "note": "Typing Level 11 drills Lua config syntax."},
             {"track": "python", "level": "p12",
              "note": "Tooling and packaging — the Python side of the same workflow."}])

doc = {
    "track": "nvim",
    "title": "Neovim",
    "subtitle": "modes, motions, operators and the editing grammar",
    "icon": "terminal",
    "levels": L,
}

# `par` is derived, never hand-written: it is exactly the number of keys the
# reference solution types (replayed macro/dot keys do not count).
import sys  # noqa: E402
sys.path.insert(0, os.path.join(HERE, "..", "cli"))
from triada.vimengine import Vim  # noqa: E402

for lv in L:
    for ls in lv["lessons"]:
        if ls["kind"] == "quiz":
            continue
        v = Vim(ls["start"]["lines"], tuple(ls["start"]["cursor"]))
        v.feed(ls["solution"])
        ls["par"] = v.typed

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(doc, fh, ensure_ascii=False, indent=1)
    fh.write("\n")
print(f"nvim.json: {len(L)} levels, {sum(len(l['lessons']) for l in L)} lessons")
