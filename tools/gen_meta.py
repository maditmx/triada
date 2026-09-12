#!/usr/bin/env python3
"""Generate curriculum/combos.json — challenges that use all three tracks at once.

Combos are optional. They never gate track progress; they unlock when you have
reached the level shown in `needs` on *each* track, and they are the only place
the three skills are exercised in a single task.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "curriculum", "combos.json")


def combo(cid, n, title, brief, needs, typing_text, vim, py):
    return {"id": cid, "n": n, "title": title, "brief": brief, "needs": needs,
            "typing": {"content": typing_text}, "vim": vim, "python": py}


C = [
    combo("c1", 1, "Fix the signature",
          "A missing colon, a missing return. Type it, edit it, explain it.",
          {"typing": 1, "nvim": 1, "python": 1},
          "def greet(name):\n    return f'hola {name}'",
          {"start": {"lines": ["def greet(name)", "    return 'hola ' + name"], "cursor": [0, 0]},
           "goal": {"lines": ["def greet(name):", "    return 'hola ' + name"]},
           "solution": "A:<Esc>", "par": 3,
           "hint": "`A` appends at the end of the line — you do not need to move first."},
          {"question": "Why is `f'hola {name}'` usually preferred over `'hola ' + name`?",
           "options": ["It is faster in every case",
                       "It works when `name` is not a string, and it keeps the shape of "
                       "the output visible in the source",
                       "Concatenation is deprecated",
                       "f-strings are evaluated lazily"],
           "answer": 1,
           "why": "`+` raises TypeError on a non-string, so you end up writing "
                  "`str(name)`. The f-string calls `str()` for you and, more "
                  "importantly, the template reads like the result."}),

    combo("c2", 2, "Comment out a block",
          "Visual block mode over real code.",
          {"typing": 3, "nvim": 9, "python": 2},
          "# debug = True\n# print(rows)\n# breakpoint()",
          {"start": {"lines": ["debug = True", "print(rows)", "breakpoint()"], "cursor": [0, 0]},
           "goal": {"lines": ["# debug = True", "# print(rows)", "# breakpoint()"]},
           "solution": "<C-v>jjI# <Esc>", "par": 7,
           "hint": "`Ctrl-v` `jj` `I# ` `Esc`."},
          {"question": "What does `breakpoint()` do in modern Python?",
           "options": ["Nothing unless you pass a debugger",
                       "Drops into the debugger named by PYTHONBREAKPOINT, defaulting to pdb",
                       "Raises SystemExit",
                       "It is a syntax error outside a function"],
           "answer": 1,
           "why": "Since 3.7 `breakpoint()` is a builtin that honours the "
                  "`PYTHONBREAKPOINT` environment variable — set it to `0` to disable "
                  "every breakpoint in a codebase without editing anything, or to "
                  "`ipdb.set_trace` to use a different debugger."}),

    combo("c3", 3, "Rename across a file",
          "The substitute command, with word boundaries.",
          {"typing": 7, "nvim": 10, "python": 3},
          ":%s/\\<amount\\>/total/g",
          {"start": {"lines": ["amount = 0", "for r in rows:", "    amount += r['amount_eur']",
                               "print(amount)"], "cursor": [0, 0]},
           "goal": {"lines": ["total = 0", "for r in rows:", "    total += r['amount_eur']",
                              "print(total)"]},
           "solution": ":%s/\\<amount\\>/total/g\r", "par": 24,
           "hint": "Without `\\<` and `\\>` you would also hit `amount_eur`."},
          {"question": "The dict key `'amount_eur'` was deliberately left alone. Why "
                       "would a regex rename be dangerous without the word boundaries?",
           "options": ["It would raise a syntax error",
                       "It would rewrite the dict key too, silently breaking a lookup "
                       "against data the code does not control",
                       "Regex cannot match inside strings",
                       "It would only rename the first match"],
           "answer": 1,
           "why": "A variable rename is a *semantic* change; a string literal is data. "
                  "This is exactly the case where an LSP rename (`<leader>rn`) beats "
                  "`:%s` — it knows which `amount` is a symbol."}),

    combo("c4", 4, "Loop to comprehension",
          "Delete four lines, write one.",
          {"typing": 9, "nvim": 6, "python": 5},
          "actives = [r['ref'] for r in rows if r['ok']]",
          {"start": {"lines": ["actives = []", "for r in rows:", "    if r['ok']:",
                               "        actives.append(r['ref'])"], "cursor": [1, 0]},
           "goal": {"lines": ["actives = []"]},
           "solution": "dG", "par": 2,
           "hint": "`dG` deletes from the current line to the end of the file."},
          {"question": "Which comprehension is equivalent to the loop you just deleted?",
           "options": ["[r['ref'] for r in rows]",
                       "[r['ref'] for r in rows if r['ok']]",
                       "[r for r in rows if r['ok']]",
                       "{r['ref'] for r in rows if r['ok']}"],
           "answer": 1,
           "why": "The expression comes first, then the `for`, then the filter — the "
                  "same order as the nested statements, read outside-in."}),

    combo("c5", 5, "Extract a constant",
          "Yank, navigate, put — then reason about scope.",
          {"typing": 9, "nvim": 7, "python": 5},
          "MAX_RETRIES = 3\n\ndef run(fn):\n    for _ in range(MAX_RETRIES):",
          {"start": {"lines": ["def run(fn):", "    for _ in range(3):", "        fn()"],
                     "cursor": [1, 0]},
           "goal": {"lines": ["MAX_RETRIES = 3", "", "def run(fn):",
                              "    for _ in range(MAX_RETRIES):", "        fn()"]},
           "solution": "f3cwMAX_RETRIES<Esc>ggOMAX_RETRIES = 3\r<Esc>", "par": 36,
           "hint": "`f3` `cw` to replace the literal, then `gg` `O` to open a line "
                   "above the first line and type the constant plus a blank line."},
          {"question": "Why is a module-level constant better than the literal `3` here?",
           "options": ["It is faster to look up",
                       "It names the intent, appears once, and can be changed or "
                       "overridden in one place",
                       "Python caches small integers",
                       "It avoids a global lookup"],
           "answer": 1,
           "why": "It is very slightly *slower* — a global lookup versus a constant. "
                  "That is irrelevant next to the readability and the single point of "
                  "change. Optimise for the reader until a profiler says otherwise."}),

    combo("c6", 6, "Add type annotations",
          "Symbol-dense typing, precise editing, modern syntax.",
          {"typing": 10, "nvim": 5, "python": 11},
          "def totals(rows: list[dict[str, float]]) -> dict[str, float]:",
          {"start": {"lines": ["def totals(rows):", "    return {}"], "cursor": [0, 0]},
           "goal": {"lines": ["def totals(rows: list[dict[str, float]]) -> dict[str, float]:",
                              "    return {}"]},
           "solution": "f)i: list[dict[str, float]]<Esc>f)a -> dict[str, float]<Esc>",
           "par": 0,
           "hint": "`f)` then `i` inserts the parameter type just before the paren. "
                   "Then `f)` again and `a` — appending *after* the paren but before "
                   "the colon. `A` would land after the colon."},
          {"question": "Which is the modern (3.10+) way to say 'an int or None'?",
           "options": ["Optional[int]", "int | None", "Union[int, NoneType]", "int?"],
           "answer": 1,
           "why": "`X | Y` is built into the language now — no `typing` import, and it "
                  "reads as a union. `Optional[int]` still works and means exactly the "
                  "same thing, but new code should prefer the operator."}),

    combo("c7", 7, "Record a macro over data",
          "The macro that turns a list into a dict.",
          {"typing": 11, "nvim": 11, "python": 3},
          "qwI'<Esc>A': 0,<Esc>jq3@w",
          {"start": {"lines": ["eur", "usd", "gbp"], "cursor": [0, 0]},
           "goal": {"lines": ["'eur': 0,", "'usd': 0,", "'gbp': 0,"]},
           "solution": "qwI'<Esc>A': 0,<Esc>jq2@w", "par": 20,
           "hint": "Record `I'` `Esc` `A': 0,` `Esc` `j` into register w — that already "
                   "does the first line — then `2@w`."},
          {"question": "You now have `{'eur': 0, 'usd': 0, 'gbp': 0}`. What is the "
                       "cleanest way to build the same thing in code from a list of keys?",
           "options": ["A for loop with d[k] = 0",
                       "dict.fromkeys(keys, 0)",
                       "{k: 0 for k in keys}",
                       "Either 2 or 3 — both are idiomatic one-liners"],
           "answer": 3,
           "why": "`dict.fromkeys(keys, 0)` is the most direct; the comprehension is "
                  "just as clear and generalises when the value depends on the key. "
                  "Careful with `fromkeys` and a *mutable* default — every key would "
                  "share the same object."}),

    combo("c8", 8, "The full loop",
          "Write it, fix it, and know why it was wrong.",
          {"typing": 12, "nvim": 12, "python": 12},
          "from decimal import Decimal, ROUND_HALF_UP\n\ntotal = Decimal('0.1') + Decimal('0.2')\nprint(total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))",
          {"start": {"lines": ["total = 0.1 + 0.2", "if total == 0.3:", "    print('exact')"],
                     "cursor": [0, 0]},
           "goal": {"lines": ["from decimal import Decimal",
                              "total = Decimal('0.1') + Decimal('0.2')",
                              "if total == Decimal('0.3'):", "    print('exact')"]},
           "solution": "Ofrom decimal import Decimal<Esc>j:s/0\\.1/Decimal('0.1')/\r"
                       ":s/0\\.2/Decimal('0.2')/\rj:s/0\\.3/Decimal('0.3')/\r",
           "par": 89,
           "hint": "`O` for the import, then one `:s` per literal. There is a shorter "
                   "way with `:%s` and a capture group — try to find it."},
          {"question": "Why does `0.1 + 0.2 == 0.3` evaluate to False?",
           "options": ["Python rounds badly",
                       "Binary floating point cannot represent 0.1, 0.2 or 0.3 exactly, "
                       "so the sum lands one ulp away from the literal 0.3",
                       "The comparison operator is imprecise",
                       "It is True in Python 3"],
           "answer": 1,
           "why": "This is IEEE 754, not a Python quirk — the same is true in C, Java "
                  "and JavaScript. For money use `Decimal` built from *strings*; for "
                  "measurements compare with `math.isclose`."}),
]

doc = {"title": "Combos", "subtitle": "one task, all three skills", "combos": C}

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(doc, fh, ensure_ascii=False, indent=1)
    fh.write("\n")

# derive par from the engine, exactly as gen_nvim does
import sys  # noqa: E402
sys.path.insert(0, os.path.join(HERE, "..", "cli"))
from triada.vimengine import Vim  # noqa: E402

for c in C:
    v = Vim(c["vim"]["start"]["lines"], tuple(c["vim"]["start"]["cursor"]))
    v.feed(c["vim"]["solution"])
    c["vim"]["par"] = v.typed
    ok = v.lines == c["vim"]["goal"]["lines"]
    if not ok:
        print(f"  !! {c['id']} solution does not reach the goal: {v.lines}")

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(doc, fh, ensure_ascii=False, indent=1)
    fh.write("\n")
print(f"combos.json: {len(C)} combos")
