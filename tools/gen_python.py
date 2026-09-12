#!/usr/bin/env python3
"""Generate curriculum/python.json — 12 levels, basics to expert.

Exercise kinds
  quiz    multiple choice
  output  predict what the snippet prints (validated by actually running it)
  code    write code that passes the tests (validated against the reference solution)
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "curriculum", "python.json")

L = []


def level(n, lid, title, goal, brief, lessons, links=None):
    L.append({"id": lid, "n": n, "title": title, "goal": goal, "brief": brief,
              "lessons": lessons, "links": links or []})


def quiz(lid, title, teach, question, options, answer, why):
    return {"id": lid, "title": title, "kind": "quiz", "teach": teach,
            "question": question, "options": options, "answer": answer, "why": why}


def out(lid, title, teach, code, answer, why, hint=""):
    return {"id": lid, "title": title, "kind": "output", "teach": teach,
            "code": code, "answer": answer, "why": why, "hint": hint}


def code(lid, title, teach, prompt, starter, tests, solution, hint="", vimtip=""):
    return {"id": lid, "title": title, "kind": "code", "teach": teach,
            "prompt": prompt, "starter": starter, "tests": tests,
            "solution": solution, "hint": hint, "vimtip": vimtip}


# ============================================================ L1
level(1, "p01", "Values, Names & Output",
      "Variables, the core types, and f-strings.",
      """Python has no variable declarations. A name is *bound* to an object by
assignment, and the same name can later be bound to something else entirely.

```python
amount = 1500          # int
rate = 0.0325          # float
ref = "LC-2026-0417"   # str
issued = True          # bool
maturity = None        # NoneType — "no value", not zero and not empty
```

`type(x)` tells you what something is; `isinstance(x, int)` asks whether it *is
one* (and respects subclasses, which is why it is preferred).

**f-strings** are the only string formatting you need:

```python
f"{ref}: {amount:,.2f} EUR at {rate:.2%}"
# 'LC-2026-0417: 1,500.00 EUR at 3.25%'
```

The format spec after `:` is a small language of its own:
`,` thousands separator, `.2f` two decimals, `.2%` percent, `>10` right-align in
10 columns, `<10` left-align, `^10` centre. And `f"{x!r}"` gives you `repr(x)`,
which is what you want in log messages and error text.

**Naming.** `snake_case` for variables and functions, `PascalCase` for classes,
`SCREAMING_CASE` for constants. Python will not enforce it; every reader will.""",
      [
          out("p01l1", "Types and truthiness",
              "Run through these in your head before you check.",
              "print(type(3).__name__)\nprint(type(3.0).__name__)\nprint(type('3').__name__)\nprint(3 == 3.0)\nprint(3 is 3.0)",
              "int\nfloat\nstr\nTrue\nFalse",
              "`==` compares *values* — 3 and 3.0 are numerically equal. `is` compares "
              "*identity*: they are two different objects. Use `is` only for `None`, "
              "`True` and `False`."),
          out("p01l2", "f-string format specs",
              "The mini-language after the colon.",
              "amount = 1234567.891\nprint(f'{amount:,.2f}')\nprint(f'{0.0325:.2%}')\nprint(f'{42:>8}|')\nprint(f'{\"ref\":<8}|')",
              "1,234,567.89\n3.25%\n      42|\nref     |",
              "`,` inserts thousands separators, `.2f` fixes two decimals, `.2%` "
              "multiplies by 100 and appends `%`, `>8` and `<8` pad to eight columns."),
          quiz("p01l3", "None is not zero",
               "A distinction that causes real bugs.",
               "Which of these is `True`?",
               ["None == 0", "None == False", "None is None", "None == ''"],
               2,
               "`None` is a unique singleton that equals nothing but itself. All three "
               "other comparisons are `False`. But note that `bool(None)` *is* `False` — "
               "`None` is falsy without being equal to `False`."),
          code("p01l4", "Format a reference line",
               "Put the pieces together.",
               "Write a function `line(ref, amount, rate)` that returns a string like "
               "`LC-2026-0417 | 1,500.00 EUR | 3.25%` — amount with thousands separators "
               "and two decimals, rate as a percentage with two decimals.",
               "def line(ref, amount, rate):\n    ...\n",
               "assert line('LC-2026-0417', 1500, 0.0325) == 'LC-2026-0417 | 1,500.00 EUR | 3.25%'\n"
               "assert line('X', 1234567.5, 0.1) == 'X | 1,234,567.50 EUR | 10.00%'",
               "def line(ref, amount, rate):\n"
               "    return f'{ref} | {amount:,.2f} EUR | {rate:.2%}'\n",
               "One f-string, three format specs.",
               "`ci(` from inside the parens replaces the whole argument list."),
          code("p01l5", "Swap without a temporary",
               "Python's tuple assignment.",
               "Write `swap(a, b)` returning the two values in the opposite order. "
               "Do it in one line, without a temporary variable.",
               "def swap(a, b):\n    ...\n",
               "assert swap(1, 2) == (2, 1)\nassert swap('a', 'b') == ('b', 'a')",
               "def swap(a, b):\n    return b, a\n",
               "A bare comma builds a tuple: `return b, a`.",
               "`A` then `Esc` — appending to the end of a line is the most common edit."),
          quiz("p01l6", "Integer division",
               "Two division operators, two results.",
               "What is `7 / 2` and `7 // 2`?",
               ["3.5 and 3.5", "3.5 and 3", "3 and 3.5", "3 and 3"],
               1,
               "`/` is always true division and always returns a float, even for "
               "`4 / 2` (which gives `2.0`). `//` is floor division: it rounds *down*, "
               "so `-7 // 2` is `-4`, not `-3`."),
      ],
      links=[{"track": "typing", "level": "t06",
              "note": "snake_case and underscores — Typing Level 6."}])

# ============================================================ L2
level(2, "p02", "Control Flow",
      "if, for, while — and the loop constructs Python actually wants you to use.",
      """```python
if amount > limit:
    action = 'escalate'
elif amount > 0:
    action = 'auto'
else:
    action = 'reject'
```

Indentation *is* the block. Four spaces, always. There is no `switch` — a chain
of `elif`, a dict lookup, or (3.10+) `match`.

**Looping.** Python's `for` is a *for-each*. Iterating an index and then
indexing back into the list is the mark of someone writing another language in
Python:

```python
for i in range(len(rows)):     # don't
    print(rows[i])

for row in rows:               # do
    print(row)

for i, row in enumerate(rows, start=1):   # when you genuinely need the index
    print(i, row)

for name, amount in zip(names, amounts):  # parallel sequences
    ...
```

**`else` on a loop** runs when the loop finished *without* `break` — useful for
search loops, and unknown to most Python programmers.

**Truthiness.** Empty containers, `0`, `''` and `None` are falsy; everything
else is truthy. So `if items:` rather than `if len(items) > 0:`.""",
      [
          out("p02l1", "enumerate and zip",
              "The two functions that eliminate index arithmetic.",
              "refs = ['A', 'B', 'C']\namounts = [100, 200, 300]\n"
              "for i, (r, a) in enumerate(zip(refs, amounts), start=1):\n"
              "    print(f'{i}. {r}={a}')",
              "1. A=100\n2. B=200\n3. C=300",
              "`zip` pairs the sequences, `enumerate(..., start=1)` numbers them, and "
              "the tuple unpacking `i, (r, a)` takes both apart in the `for` header."),
          out("p02l2", "range boundaries",
              "Half-open intervals, everywhere in Python.",
              "print(list(range(5)))\nprint(list(range(2, 5)))\nprint(list(range(0, 10, 3)))\nprint(list(range(5, 0, -1)))",
              "[0, 1, 2, 3, 4]\n[2, 3, 4]\n[0, 3, 6, 9]\n[5, 4, 3, 2, 1]",
              "`range(a, b)` includes `a` and excludes `b`. This half-open convention "
              "means `range(a, b)` has exactly `b - a` elements and `range(0, n)` plus "
              "`range(n, m)` tile perfectly."),
          out("p02l3", "for/else",
              "The loop `else` nobody knows.",
              "for x in [1, 3, 5]:\n    if x % 2 == 0:\n        print('found even')\n        break\nelse:\n    print('no even numbers')",
              "no even numbers",
              "`else` on a loop means *no break happened*. Read it as `nobreak`. It "
              "saves you the `found = False` flag variable in search loops."),
          code("p02l4", "Classify amounts",
               "A plain conditional chain.",
               "Write `classify(amount)` returning `'reject'` for anything <= 0, "
               "`'auto'` for up to and including 10000, and `'escalate'` above that.",
               "def classify(amount):\n    ...\n",
               "assert classify(-5) == 'reject'\nassert classify(0) == 'reject'\n"
               "assert classify(1) == 'auto'\nassert classify(10000) == 'auto'\n"
               "assert classify(10001) == 'escalate'",
               "def classify(amount):\n"
               "    if amount <= 0:\n        return 'reject'\n"
               "    if amount <= 10000:\n        return 'auto'\n"
               "    return 'escalate'\n",
               "Early `return` beats nested `else`.",
               "`>>` indents a line; `3>>` indents three."),
          code("p02l5", "First match, or None",
               "for/else in practice.",
               "Write `first_over(rows, limit)` that returns the first dict in `rows` "
               "whose `'amount'` exceeds `limit`, or `None` if there is none.",
               "def first_over(rows, limit):\n    ...\n",
               "rows = [{'amount': 5}, {'amount': 50}, {'amount': 500}]\n"
               "assert first_over(rows, 10) == {'amount': 50}\n"
               "assert first_over(rows, 1000) is None\n"
               "assert first_over([], 0) is None",
               "def first_over(rows, limit):\n"
               "    for row in rows:\n"
               "        if row['amount'] > limit:\n            return row\n"
               "    return None\n",
               "A bare `return` at the end already gives `None`, but being explicit "
               "is clearer.",
               "`ci[` changes what is inside the square brackets."),
          quiz("p02l6", "The mutable default trap",
               "The most famous Python gotcha. You will hit it eventually.",
               "```python\ndef add(item, bucket=[]):\n    bucket.append(item)\n    return bucket\n\nprint(add(1))\nprint(add(2))\n```\nWhat is printed?",
               ["[1] then [2]", "[1] then [1, 2]", "[1] then []", "TypeError"],
               1,
               "Default arguments are evaluated **once**, when the function is defined — "
               "so both calls share the same list. The fix is always the same: "
               "`def add(item, bucket=None):` and `if bucket is None: bucket = []`."),
      ],
      links=[{"track": "nvim", "level": "v03",
              "note": "`>>` and `2>>` re-indent blocks — the Vim skill this level needs most."}])

# ============================================================ L3
level(3, "p03", "Collections",
      "list, tuple, dict, set — and knowing which one.",
      """| Type | Ordered | Mutable | Lookup | Use for |
|---|---|---|---|---|
| `list` | yes | yes | O(n) | a sequence you will change |
| `tuple` | yes | **no** | O(n) | a fixed record; a dict key |
| `dict` | yes¹ | yes | **O(1)** | lookup by key |
| `set` | no | yes | **O(1)** | membership, deduplication |

¹ insertion-ordered since 3.7, and that is now a language guarantee.

**The single biggest performance mistake in Python** is `if x in big_list` inside
a loop — O(n) each time. `set(big_list)` first, then `in` is O(1). On 10,000
items that is a 1000× difference.

**Slicing** — `seq[start:stop:step]`, all optional, `stop` exclusive:

```python
xs[1:4]    xs[:3]    xs[3:]    xs[-1]    xs[-2:]    xs[::2]    xs[::-1]
```

`xs[:]` copies a list — a *shallow* copy: the list is new, the objects inside
are shared.

**Dict essentials**

```python
d.get('k')            # None instead of KeyError
d.get('k', 0)         # ...with a default
d.setdefault('k', []) # get, inserting the default if missing
d | other             # merge (3.9+)
for k, v in d.items()
```

`collections.Counter` and `collections.defaultdict` remove most of the
boilerplate around counting and grouping — reach for them before writing an
`if key not in d` line.""",
      [
          out("p03l1", "Slicing",
              "Negative indices count from the end.",
              "xs = [0, 1, 2, 3, 4, 5]\nprint(xs[1:4])\nprint(xs[:2])\nprint(xs[-2:])\nprint(xs[::2])\nprint(xs[::-1])",
              "[1, 2, 3]\n[0, 1]\n[4, 5]\n[0, 2, 4]\n[5, 4, 3, 2, 1, 0]",
              "`[::-1]` reverses. `[::2]` takes every second element. A slice always "
              "returns a *new* list of the same type."),
          out("p03l2", "Aliasing vs copying",
              "The bug that eats an afternoon.",
              "a = [1, 2, 3]\nb = a\nc = a[:]\nb.append(4)\nprint(a)\nprint(c)",
              "[1, 2, 3, 4]\n[1, 2, 3]",
              "`b = a` binds a second name to the *same* list. `c = a[:]` makes a copy. "
              "For nested structures even `[:]` is not enough — use `copy.deepcopy`."),
          out("p03l3", "Counter and defaultdict",
              "Two imports that delete a lot of code.",
              "from collections import Counter, defaultdict\n"
              "words = ['eur', 'usd', 'eur', 'gbp', 'eur']\n"
              "print(Counter(words).most_common(2))\n"
              "g = defaultdict(list)\n"
              "for i, w in enumerate(words):\n    g[w].append(i)\n"
              "print(dict(g))",
              "[('eur', 3), ('usd', 1)]\n{'eur': [0, 2, 4], 'usd': [1], 'gbp': [3]}",
              "`Counter` counts; `defaultdict(list)` creates the empty list on first "
              "access so you never write `if key not in d`."),
          code("p03l4", "Deduplicate, keep order",
               "`set` loses order; you often need both.",
               "Write `dedupe(items)` returning a list with duplicates removed, "
               "preserving first-seen order.",
               "def dedupe(items):\n    ...\n",
               "assert dedupe([3, 1, 3, 2, 1]) == [3, 1, 2]\n"
               "assert dedupe([]) == []\nassert dedupe(['a', 'a']) == ['a']",
               "def dedupe(items):\n"
               "    seen = set()\n    out = []\n"
               "    for x in items:\n"
               "        if x not in seen:\n"
               "            seen.add(x)\n            out.append(x)\n"
               "    return out\n",
               "A `set` for the O(1) membership test, a `list` for the order. "
               "(`list(dict.fromkeys(items))` is the one-line version.)",
               "`di{` empties a dict literal from anywhere inside it."),
          code("p03l5", "Group by key",
               "The most common data-shaping task there is.",
               "Write `group_by_currency(rows)` turning a list of dicts with `'ccy'` "
               "and `'amount'` keys into `{ccy: [amount, ...]}`, preserving order.",
               "def group_by_currency(rows):\n    ...\n",
               "rows = [{'ccy': 'EUR', 'amount': 1}, {'ccy': 'USD', 'amount': 2},\n"
               "        {'ccy': 'EUR', 'amount': 3}]\n"
               "assert group_by_currency(rows) == {'EUR': [1, 3], 'USD': [2]}\n"
               "assert group_by_currency([]) == {}",
               "from collections import defaultdict\n\n\n"
               "def group_by_currency(rows):\n"
               "    out = defaultdict(list)\n"
               "    for row in rows:\n"
               "        out[row['ccy']].append(row['amount'])\n"
               "    return dict(out)\n",
               "`defaultdict(list)`, then `dict()` at the end so the result compares "
               "equal to a plain dict.",
               ""),
          code("p03l6", "Invert a mapping",
               "Dict comprehensions.",
               "Write `invert(d)` returning a dict with keys and values swapped.",
               "def invert(d):\n    ...\n",
               "assert invert({'a': 1, 'b': 2}) == {1: 'a', 2: 'b'}\nassert invert({}) == {}",
               "def invert(d):\n    return {v: k for k, v in d.items()}\n",
               "`{v: k for k, v in d.items()}`.",
               "Every brace here is `AltGr` + `´` / `ç` on your keyboard."),
          quiz("p03l7", "Which container?",
               "Choosing correctly is most of the performance work.",
               "You must check 100,000 times whether a reference is in a collection of "
               "50,000 references. Which container?",
               ["list — simplest", "tuple — immutable so faster", "set — O(1) membership",
                "dict with None values"],
               2,
               "`in` on a list or tuple is a linear scan; on a set it is a hash lookup. "
               "Here that is roughly 2.5 billion comparisons versus 100,000 lookups. "
               "A dict with dummy values would also be O(1) but wastes memory and says "
               "the wrong thing to the reader."),
      ],
      links=[{"track": "typing", "level": "t09",
              "note": "[ ] and { } are AltGr combos — Typing Level 9 drills them."},
             {"track": "nvim", "level": "v06",
              "note": "`ci[`, `di{`, `ci(` edit exactly these literals."}])

# ============================================================ L4
level(4, "p04", "Strings",
      "Immutable, unicode, and full of useful methods.",
      """Strings are **immutable**: every "modification" makes a new string. That is
why building a string in a loop with `s += x` is O(n²) and `''.join(parts)` is
O(n). On a few hundred items you will not notice; on a few hundred thousand you
will.

The methods worth memorising:

```python
s.strip() .lstrip() .rstrip()      # whitespace or given chars
s.split(',')  s.rsplit(',', 1)     # to list
','.join(parts)                    # from list
s.replace(old, new, count?)
s.startswith(p)  s.endswith(p)     # both accept a tuple of options
s.upper() .lower() .title() .casefold()
s.zfill(6)  s.ljust(10)  s.rjust(10)
s.removeprefix(p)  s.removesuffix(p)      # 3.9+, safer than slicing
```

**Raw strings** `r'...'` disable backslash escapes — always use them for regexes
and Windows paths.

**Encoding.** `str` is text; `bytes` is bytes. `s.encode('utf-8')` and
`b.decode('utf-8')` cross the boundary, and files opened in text mode do it for
you. Never guess: specify `encoding='utf-8'` explicitly when you open a file.

Spanish text makes the difference concrete: `'ñ'` is one `str` character but two
UTF-8 bytes, and `len()` on the two types gives different answers.""",
      [
          out("p04l1", "str vs bytes",
              "Accented characters make the distinction visible.",
              "s = 'año'\nb = s.encode('utf-8')\nprint(len(s))\nprint(len(b))\nprint(b)\nprint(b.decode('utf-8') == s)",
              "3\n4\nb'a\\xc3\\xb1o'\nTrue",
              "`ñ` is one character but two bytes in UTF-8. `len()` on a `str` counts "
              "characters; on `bytes` it counts bytes. This is why you decode as early "
              "as possible and encode as late as possible."),
          out("p04l2", "split and join",
              "The two halves of every text pipeline.",
              "line = ' LC-1 , 1500 , EUR '\nparts = [p.strip() for p in line.split(',')]\nprint(parts)\nprint('|'.join(parts))\nprint(line.split())",
              "['LC-1', '1500', 'EUR']\nLC-1|1500|EUR\n['LC-1', ',', '1500', ',', 'EUR']",
              "`split(',')` splits on the literal comma and keeps the whitespace; the "
              "comprehension strips it. Bare `split()` with no argument splits on runs "
              "of any whitespace and drops empties — a different and often more useful "
              "behaviour."),
          out("p04l3", "removeprefix beats slicing",
              "Safer because it is a no-op when the prefix is absent.",
              "for ref in ['LC-001', 'SBLC-002', '003']:\n    print(ref.removeprefix('LC-'))",
              "001\nSBLC-002\n003",
              "`ref[3:]` would mangle the other two. `removeprefix` only strips when "
              "the prefix is actually there."),
          code("p04l4", "Normalise a reference",
               "String cleaning, the everyday task.",
               "Write `normalise(ref)` that strips surrounding whitespace, uppercases, "
               "and replaces any run of spaces or underscores with a single hyphen.",
               "def normalise(ref):\n    ...\n",
               "assert normalise('  lc 2026 _ 417 ') == 'LC-2026-417'\n"
               "assert normalise('already-ok') == 'ALREADY-OK'\n"
               "assert normalise('a__b') == 'A-B'",
               "import re\n\n\n"
               "def normalise(ref):\n"
               "    return re.sub(r'[ _]+', '-', ref.strip()).upper()\n",
               "`re.sub(r'[ _]+', '-', s)` collapses runs. Order matters: strip first.",
               "`ci\"` from inside a string literal replaces its contents."),
          code("p04l5", "Build efficiently",
               "join, not +=.",
               "Write `to_csv_line(values)` producing a comma-separated line where each "
               "value is converted with `str()` and any value containing a comma is "
               "wrapped in double quotes.",
               "def to_csv_line(values):\n    ...\n",
               "assert to_csv_line([1, 'a', 2.5]) == '1,a,2.5'\n"
               "assert to_csv_line(['x,y', 'z']) == '\"x,y\",z'\n"
               "assert to_csv_line([]) == ''",
               "def to_csv_line(values):\n"
               "    out = []\n"
               "    for v in values:\n"
               "        s = str(v)\n"
               "        out.append(f'\"{s}\"' if ',' in s else s)\n"
               "    return ','.join(out)\n",
               "Build a list, then `join` it once.",
               ""),
          quiz("p04l6", "Why is += slow?",
               "Understand the cost, not just the rule.",
               "Why is `s += part` inside a loop over 100,000 parts much slower than "
               "`''.join(parts)`?",
               ["`+=` is a syntax error on strings",
                "Strings are immutable, so each `+=` allocates and copies a whole new "
                "string — the total work is quadratic",
                "`join` uses C and `+=` uses Python",
                "It isn't slower"],
               1,
               "Each `+=` builds a new string containing everything so far, so the "
               "total copying is 1 + 2 + 3 + … + n characters. `join` measures the "
               "total length once, allocates once, and copies each part once. "
               "(CPython has an optimisation that sometimes hides this, but never "
               "rely on it.)"),
      ])

# ============================================================ L5
level(5, "p05", "Functions & Comprehensions",
      "Arguments, scope, and expressing loops as expressions.",
      """```python
def transfer(amount, ccy='EUR', *extras, strict=False, **options):
    ...
```

| Part | Means |
|---|---|
| `amount` | positional-or-keyword, required |
| `ccy='EUR'` | positional-or-keyword with a default |
| `*extras` | any further positional arguments, as a tuple |
| `strict=False` | **keyword-only** — everything after `*` must be named |
| `**options` | any further keyword arguments, as a dict |

A bare `*` in the signature (`def f(a, *, b)`) makes everything after it
keyword-only without collecting extras. Use it for boolean flags: `f(x, True)`
tells the reader nothing, `f(x, strict=True)` tells them everything.

**Comprehensions** turn a build-a-list loop into an expression:

```python
[expr for x in xs if cond]           # list
{k: v for k, v in pairs}             # dict
{expr for x in xs}                   # set
(expr for x in xs)                   # generator — lazy, no list built
```

Use one when the loop's only job is to build a collection. When the body does
several things, or nests three deep, write the loop — a comprehension nobody
can read is not a win.

**Scope** is LEGB: Local, Enclosing, Global, Built-in. Assigning to a name
anywhere in a function makes it local *for the whole function*, which is why
reading it before that line raises `UnboundLocalError`.""",
      [
          out("p05l1", "Argument kinds",
              "Read the signature carefully.",
              "def f(a, b=2, *rest, key=None, **opts):\n"
              "    print(a, b, rest, key, opts)\n\n"
              "f(1)\nf(1, 3, 4, 5, key='k', extra=True)",
              "1 2 () None {}\n1 3 (4, 5) k {'extra': True}",
              "`rest` collects extra positionals as a tuple; `opts` collects extra "
              "keywords as a dict; `key` is keyword-only because it comes after `*rest`."),
          out("p05l2", "Comprehension forms",
              "Same loop, four containers.",
              "xs = [1, 2, 2, 3]\nprint([x * 2 for x in xs])\nprint({x for x in xs})\n"
              "print({x: x ** 2 for x in xs})\nprint(sum(x for x in xs if x > 1))",
              "[2, 4, 4, 6]\n{1, 2, 3}\n{1: 1, 2: 4, 3: 9}\n7",
              "The last one is a *generator expression* — it never builds a list, which "
              "matters when the sequence is large. Inside a single-argument call you "
              "can drop the extra parentheses."),
          out("p05l3", "LEGB and UnboundLocalError",
              "Why this fails is worth understanding.",
              "count = 0\n\n"
              "def bump():\n    global count\n    count += 1\n    return count\n\n"
              "print(bump())\nprint(bump())\nprint(count)",
              "1\n2\n2",
              "Without `global`, `count += 1` would make `count` local for the whole "
              "function and raise `UnboundLocalError` on the read. `global` is usually "
              "a smell — returning a new value is almost always better — but you need "
              "to recognise the rule."),
          code("p05l4", "Keyword-only flag",
               "Design a signature that reads well at the call site.",
               "Write `fmt(amount, *, currency='EUR', symbol=False)` returning "
               "`'1,500.00 EUR'` by default, or `'1,500.00 €'` when `symbol=True` "
               "and the currency is EUR (use `'$'` for USD, otherwise fall back to "
               "the code).",
               "def fmt(amount, *, currency='EUR', symbol=False):\n    ...\n",
               "assert fmt(1500) == '1,500.00 EUR'\n"
               "assert fmt(1500, symbol=True) == '1,500.00 €'\n"
               "assert fmt(1500, currency='USD', symbol=True) == '1,500.00 $'\n"
               "assert fmt(1500, currency='GBP', symbol=True) == '1,500.00 GBP'\n"
               "try:\n    fmt(1500, 'USD')\n    raise AssertionError('should be keyword-only')\n"
               "except TypeError:\n    pass",
               "SYMBOLS = {'EUR': '€', 'USD': '$'}\n\n\n"
               "def fmt(amount, *, currency='EUR', symbol=False):\n"
               "    tag = SYMBOLS.get(currency, currency) if symbol else currency\n"
               "    return f'{amount:,.2f} {tag}'\n",
               "`dict.get(key, default)` is the fallback.",
               ""),
          code("p05l5", "Rewrite a loop as a comprehension",
               "The refactor you will do a thousand times.",
               "Write `active_refs(rows)` returning a list of the `'ref'` values of "
               "every row whose `'status'` is `'active'`, uppercased.",
               "def active_refs(rows):\n    ...\n",
               "rows = [{'ref': 'a', 'status': 'active'}, {'ref': 'b', 'status': 'closed'},\n"
               "        {'ref': 'c', 'status': 'active'}]\n"
               "assert active_refs(rows) == ['A', 'C']\nassert active_refs([]) == []",
               "def active_refs(rows):\n"
               "    return [r['ref'].upper() for r in rows if r['status'] == 'active']\n",
               "One comprehension with a filter.",
               "Vim's dot formula shines here: change one loop, then `n.` for the rest."),
          code("p05l6", "Flatten one level",
               "Nested comprehension order trips everyone up.",
               "Write `flatten(chunks)` turning a list of lists into a single flat list.",
               "def flatten(chunks):\n    ...\n",
               "assert flatten([[1, 2], [3], []]) == [1, 2, 3]\nassert flatten([]) == []",
               "def flatten(chunks):\n    return [x for chunk in chunks for x in chunk]\n",
               "The `for` clauses read left to right, in the same order as the nested "
               "loops they replace: outer first.",
               ""),
          quiz("p05l7", "When not to comprehend",
               "Taste, not syntax.",
               "Which is the best reason to write an explicit `for` loop instead of a "
               "comprehension?",
               ["Comprehensions are slower",
                "The body does more than build one collection — it logs, mutates state, "
                "or has several branches",
                "Comprehensions can't use `if`",
                "The list is longer than 100 items"],
               1,
               "Comprehensions are usually *faster*, and length is irrelevant. The real "
               "line is intent: a comprehension says 'this loop exists solely to build "
               "this collection'. Anything else — side effects, early exit, several "
               "steps — belongs in a loop where a reader can follow it."),
      ],
      links=[{"track": "nvim", "level": "v08",
              "note": "The dot formula turns a repetitive refactor into `n.` `n.` `n.`"}])

# ============================================================ L6
level(6, "p06", "Files, Paths & Structured Data",
      "pathlib, context managers, JSON and CSV.",
      """**Always use `pathlib`.** String path manipulation is a source of bugs that
`Path` simply does not have:

```python
from pathlib import Path

base = Path.home() / 'proyectosweb'
for p in base.rglob('*.json'):
    print(p.name, p.stem, p.suffix, p.parent)

p.exists()  p.is_file()  p.read_text(encoding='utf-8')  p.write_text(s)
p.with_suffix('.bak')    p.mkdir(parents=True, exist_ok=True)
```

The `/` operator joins paths correctly on every OS.

**Context managers.** `with` guarantees cleanup even when an exception is
raised. Never open a file without it:

```python
with open(path, encoding='utf-8') as fh:
    data = json.load(fh)
```

`encoding='utf-8'` is not optional in practice — the default is
platform-dependent, and the day it differs is the day your `ñ` breaks.

**JSON** — `load`/`dump` for files, `loads`/`dumps` for strings.
`json.dumps(obj, indent=2, ensure_ascii=False)` gives readable, accented output.

**CSV** — use `csv.DictReader` / `csv.DictWriter`, and always open with
`newline=''`. Splitting on commas by hand breaks on the first quoted field, and
real data always has one.""",
      [
          out("p06l1", "Path parts",
              "Every piece of a path, without string surgery.",
              "from pathlib import Path\np = Path('/home/marco/data/trades.csv')\n"
              "print(p.name)\nprint(p.stem)\nprint(p.suffix)\nprint(p.parent)\nprint(p.with_suffix('.json').name)",
              "trades.csv\ntrades\n.csv\n/home/marco/data\ntrades.json",
              "`name` is the last component, `stem` is it without the extension, and "
              "`with_suffix` returns a *new* Path — Paths are immutable."),
          out("p06l2", "JSON round trip",
              "Note what happens to the accents and to the tuple.",
              "import json\nobj = {'ref': 'LC-1', 'tags': ('a', 'b'), 'note': 'año'}\n"
              "s = json.dumps(obj, ensure_ascii=False)\nprint(s)\nprint(json.loads(s)['tags'])",
              '{"ref": "LC-1", "tags": ["a", "b"], "note": "año"}\n[\'a\', \'b\']',
              "JSON has no tuple type, so a tuple serialises as an array and comes back "
              "as a *list*. `ensure_ascii=False` keeps `ñ` readable instead of "
              "escaping it to `\\u00f1`."),
          out("p06l3", "with guarantees cleanup",
              "The point of a context manager.",
              "class Res:\n"
              "    def __enter__(self):\n        print('open')\n        return self\n"
              "    def __exit__(self, *exc):\n        print('close')\n        return False\n\n"
              "try:\n    with Res():\n        raise ValueError('boom')\n"
              "except ValueError as e:\n    print('caught', e)",
              "open\nclose\ncaught boom",
              "`__exit__` runs even though the body raised. Returning `False` lets the "
              "exception propagate; returning `True` would swallow it — which you almost "
              "never want."),
          code("p06l4", "Read a JSON config safely",
               "Missing file, bad JSON, missing key — all handled.",
               "Write `load_port(path, default=8080)` that reads a JSON file and returns "
               "its `'port'` value as an int, falling back to `default` if the file is "
               "missing, is not valid JSON, or has no `'port'` key.",
               "import json\nfrom pathlib import Path\n\n\ndef load_port(path, default=8080):\n    ...\n",
               "import tempfile, os, json\n"
               "d = tempfile.mkdtemp()\n"
               "good = os.path.join(d, 'g.json'); open(good, 'w').write('{\"port\": 9000}')\n"
               "bad = os.path.join(d, 'b.json'); open(bad, 'w').write('not json')\n"
               "nokey = os.path.join(d, 'n.json'); open(nokey, 'w').write('{}')\n"
               "assert load_port(good) == 9000\nassert load_port(bad) == 8080\n"
               "assert load_port(nokey) == 8080\nassert load_port(os.path.join(d, 'missing.json'), 1) == 1",
               "import json\nfrom pathlib import Path\n\n\n"
               "def load_port(path, default=8080):\n"
               "    try:\n"
               "        data = json.loads(Path(path).read_text(encoding='utf-8'))\n"
               "    except (OSError, json.JSONDecodeError):\n"
               "        return default\n"
               "    return int(data.get('port', default))\n",
               "Catch `OSError` for the file and `json.JSONDecodeError` for the parse; "
               "use `dict.get` for the key.",
               ""),
          code("p06l5", "Parse CSV text",
               "Use the csv module, not split.",
               "Write `total_by_ccy(text)` taking CSV text with a header row "
               "`ref,ccy,amount` and returning `{ccy: total}` with float totals.",
               "import csv, io\n\n\ndef total_by_ccy(text):\n    ...\n",
               "t = 'ref,ccy,amount\\nA,EUR,100.5\\nB,USD,50\\nC,EUR,10'\n"
               "assert total_by_ccy(t) == {'EUR': 110.5, 'USD': 50.0}\n"
               "assert total_by_ccy('ref,ccy,amount') == {}\n"
               "q = 'ref,ccy,amount\\n\"X,Y\",EUR,5'\nassert total_by_ccy(q) == {'EUR': 5.0}",
               "import csv\nimport io\nfrom collections import defaultdict\n\n\n"
               "def total_by_ccy(text):\n"
               "    out = defaultdict(float)\n"
               "    for row in csv.DictReader(io.StringIO(text)):\n"
               "        out[row['ccy']] += float(row['amount'])\n"
               "    return dict(out)\n",
               "`csv.DictReader(io.StringIO(text))` reads CSV from a string and handles "
               "the quoted field in the last test.",
               ""),
          quiz("p06l6", "Why newline=''?",
               "A detail the docs insist on.",
               "Why does the csv module tell you to open files with `newline=''`?",
               ["To strip trailing newlines from fields",
                "So the csv module handles line endings itself — a quoted field may "
                "legitimately contain a newline, and universal-newline translation "
                "would corrupt it",
                "For speed", "It is only needed on Windows and can be ignored"],
               1,
               "The csv reader and writer do their own line-ending handling precisely "
               "because embedded newlines inside quoted fields are legal. Letting "
               "Python translate line endings underneath them breaks those rows — and "
               "on Windows the writer additionally produces blank lines between rows."),
      ],
      links=[{"track": "typing", "level": "t08",
              "note": "`~/` paths and `@` need the AltGr row."}])

# ============================================================ L7
level(7, "p07", "Errors & Exceptions",
      "Fail loudly, fail specifically, clean up reliably.",
      """```python
try:
    payload = json.loads(raw)
except json.JSONDecodeError as exc:
    raise ValueError(f'bad payload in {path!r}') from exc
else:
    process(payload)        # runs only if no exception
finally:
    handle.close()          # runs always
```

**Rules that matter**

1. **Catch the narrowest exception you can.** A bare `except:` also catches
   `KeyboardInterrupt` and `SystemExit`; `except Exception:` is the widest you
   should ever write, and only at a top-level boundary.
2. **Never swallow silently.** `except Exception: pass` is how a system fails in
   a way nobody can debug. Log it, or re-raise.
3. **Chain with `from exc`.** It preserves the original traceback and shows
   *both* causes — the low-level and the meaningful one.
4. **Keep the `try` block small.** Wrap the one line that can fail, not the
   forty lines around it, or you will catch an error you did not mean to.

**EAFP over LBYL.** Python prefers "easier to ask forgiveness than permission":
try the operation and handle the failure, rather than checking preconditions
first. `d[k]` in a `try` beats `if k in d` when the key is usually present — and
it has no race condition, which matters for files.

**Custom exceptions** are one line and worth it: `class ValidationError(ValueError): pass`
lets callers catch exactly your failure mode.""",
      [
          out("p07l1", "else and finally",
              "Trace the order.",
              "def run(x):\n"
              "    try:\n        r = 10 // x\n"
              "    except ZeroDivisionError:\n        print('zero')\n        return -1\n"
              "    else:\n        print('ok')\n        return r\n"
              "    finally:\n        print('cleanup')\n\n"
              "print(run(2))\nprint(run(0))",
              "ok\ncleanup\n5\nzero\ncleanup\n-1",
              "`finally` runs even after `return` — the return value is computed, then "
              "`finally` executes, then the function actually returns."),
          out("p07l2", "Exception chaining",
              "What `from` gives you.",
              "try:\n"
              "    try:\n        int('abc')\n"
              "    except ValueError as exc:\n"
              "        raise RuntimeError('parse failed') from exc\n"
              "except RuntimeError as e:\n"
              "    print(e)\n    print(type(e.__cause__).__name__)",
              "parse failed\nValueError",
              "`from exc` sets `__cause__`, so the traceback shows both the low-level "
              "cause and your meaningful message. Without it Python still shows the "
              "original as 'During handling of the above exception…', which reads as "
              "an accident rather than a deliberate translation."),
          out("p07l3", "EAFP",
              "Ask forgiveness.",
              "d = {'a': 1}\n"
              "for k in ['a', 'b']:\n"
              "    try:\n        print(d[k])\n"
              "    except KeyError:\n        print(f'missing {k}')",
              "1\nmissing b",
              "For a dict, `d.get(k)` is simpler still. The EAFP pattern earns its keep "
              "where checking first is racy — files that may be deleted between the "
              "check and the open, for instance."),
          code("p07l4", "A custom exception",
               "Give callers something precise to catch.",
               "Define `ValidationError(ValueError)` and write `parse_amount(raw)` that "
               "returns a float, raising `ValidationError` with the message "
               "`'bad amount: <raw>'` when the input is not a number or is negative.",
               "class ValidationError(ValueError):\n    pass\n\n\ndef parse_amount(raw):\n    ...\n",
               "assert parse_amount('12.5') == 12.5\nassert parse_amount('0') == 0.0\n"
               "for bad in ['abc', '-1', '']:\n"
               "    try:\n        parse_amount(bad)\n"
               "        raise AssertionError(f'should have raised for {bad!r}')\n"
               "    except ValidationError as e:\n        assert str(e) == f'bad amount: {bad}'\n"
               "assert issubclass(ValidationError, ValueError)",
               "class ValidationError(ValueError):\n    pass\n\n\n"
               "def parse_amount(raw):\n"
               "    try:\n        value = float(raw)\n"
               "    except ValueError as exc:\n"
               "        raise ValidationError(f'bad amount: {raw}') from exc\n"
               "    if value < 0:\n"
               "        raise ValidationError(f'bad amount: {raw}')\n"
               "    return value\n",
               "Subclassing `ValueError` means existing `except ValueError` handlers "
               "still work.",
               ""),
          code("p07l5", "Retry with cleanup",
               "try/except/finally in a loop.",
               "Write `retry(fn, attempts=3)` that calls `fn()` and returns its result, "
               "retrying on any `Exception` up to `attempts` times, and re-raising the "
               "last exception if they all fail.",
               "def retry(fn, attempts=3):\n    ...\n",
               "calls = []\n"
               "def flaky():\n    calls.append(1)\n    if len(calls) < 3:\n        raise OSError('nope')\n    return 'ok'\n"
               "assert retry(flaky) == 'ok'\nassert len(calls) == 3\n"
               "def always():\n    raise KeyError('k')\n"
               "try:\n    retry(always, attempts=2)\n    raise AssertionError('should raise')\n"
               "except KeyError:\n    pass",
               "def retry(fn, attempts=3):\n"
               "    last = None\n"
               "    for _ in range(attempts):\n"
               "        try:\n            return fn()\n"
               "        except Exception as exc:\n            last = exc\n"
               "    raise last\n",
               "Keep the last exception in a variable and `raise` it after the loop.",
               ""),
          quiz("p07l6", "The worst line in the codebase",
               "You will meet it.",
               "What is actually wrong with `except Exception: pass`?",
               ["It is slow",
                "It hides every failure, so the program continues in an unknown state "
                "and the bug surfaces somewhere unrelated",
                "It only catches some exceptions",
                "Nothing, if the code afterwards works"],
               1,
               "The cost is not the exception you meant to ignore — it is the typo, "
               "the missing key and the network failure you did not. If you truly must "
               "continue, catch the specific class and log it: "
               "`except OSError as exc: logger.warning('...', exc_info=exc)`."),
      ])

# ============================================================ L8
level(8, "p08", "Classes & Data Modelling",
      "When to reach for a class, and how to write a good one.",
      """Most Python code needs fewer classes than people write. A class earns its
place when **state and the behaviour over that state belong together**. If a
class has one method and a constructor, it wanted to be a function.

```python
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Trade:
    ref: str
    amount: float
    currency: str = 'EUR'
    tags: list[str] = field(default_factory=list)

    def notional(self, fx: float = 1.0) -> float:
        return self.amount * fx
```

`@dataclass` writes `__init__`, `__repr__` and `__eq__` for you.
`frozen=True` makes instances immutable *and* hashable; `slots=True` cuts memory
and blocks accidental attribute typos. `field(default_factory=list)` is how you
give a mutable default without hitting the shared-default trap from Level 2.

**Dunder methods** hook into the language: `__len__` for `len()`, `__iter__` for
`for`, `__eq__` for `==`, `__repr__` for the debugger (make it unambiguous —
ideally something you could paste back into Python).

**`@property`** turns a method into a computed attribute, letting you add
validation later without changing every caller.

**Inheritance vs composition.** Inherit only for genuine *is-a* relationships
where the subclass can stand in for the parent everywhere. Otherwise hold the
other object as an attribute — it is easier to test and easier to change.""",
      [
          out("p08l1", "What a dataclass generates",
              "Three methods for one decorator.",
              "from dataclasses import dataclass\n\n"
              "@dataclass\nclass P:\n    x: int\n    y: int = 0\n\n"
              "a = P(1)\nb = P(1, 0)\nprint(a)\nprint(a == b)\nprint(a is b)",
              "P(x=1, y=0)\nTrue\nFalse",
              "You got `__init__`, a readable `__repr__` and a field-by-field `__eq__` "
              "for free. Equality is by value; identity is still per object."),
          out("p08l2", "property and validation",
              "A computed attribute.",
              "class Account:\n"
              "    def __init__(self, cents):\n        self._cents = cents\n\n"
              "    @property\n    def euros(self):\n        return self._cents / 100\n\n"
              "    @euros.setter\n    def euros(self, value):\n"
              "        self._cents = round(value * 100)\n\n"
              "a = Account(1550)\nprint(a.euros)\na.euros = 20.0\nprint(a._cents)",
              "15.5\n2000",
              "`euros` looks like an attribute at the call site but runs code. That is "
              "the point: you can start with a plain attribute and add a property later "
              "without touching a single caller."),
          out("p08l3", "Dunder methods",
              "Making your object behave like a builtin.",
              "class Bag:\n"
              "    def __init__(self, items):\n        self.items = list(items)\n"
              "    def __len__(self):\n        return len(self.items)\n"
              "    def __iter__(self):\n        return iter(self.items)\n"
              "    def __repr__(self):\n        return f'Bag({self.items!r})'\n\n"
              "b = Bag([1, 2, 3])\nprint(len(b))\nprint(sum(b))\nprint(b)\nprint(bool(Bag([])))",
              "3\n6\nBag([1, 2, 3])\nFalse",
              "`__len__` gives you `len()` *and* truthiness — an empty Bag is falsy "
              "without writing `__bool__`. `__iter__` gives you `for`, `sum`, `list`, "
              "unpacking and comprehensions, all at once."),
          code("p08l4", "A frozen dataclass",
               "Immutable records with a method.",
               "Define a frozen dataclass `Trade` with fields `ref: str`, "
               "`amount: float`, `currency: str = 'EUR'`, and a method "
               "`converted(fx)` returning a **new** Trade with the amount multiplied "
               "by `fx` and the currency set to `'USD'`.",
               "from dataclasses import dataclass, replace\n\n\n@dataclass(frozen=True)\nclass Trade:\n    ...\n",
               "t = Trade('A', 100.0)\nassert t.currency == 'EUR'\n"
               "u = t.converted(1.1)\nassert abs(u.amount - 110.0) < 1e-9\n"
               "assert u.currency == 'USD' and u.ref == 'A'\n"
               "assert t.amount == 100.0\n"
               "assert Trade('A', 100.0) == t\n"
               "try:\n    t.amount = 1\n    raise AssertionError('should be frozen')\n"
               "except Exception:\n    pass",
               "from dataclasses import dataclass, replace\n\n\n"
               "@dataclass(frozen=True)\nclass Trade:\n"
               "    ref: str\n    amount: float\n    currency: str = 'EUR'\n\n"
               "    def converted(self, fx):\n"
               "        return replace(self, amount=self.amount * fx, currency='USD')\n",
               "`dataclasses.replace(self, **changes)` is the clean way to make a "
               "modified copy of a frozen instance.",
               ""),
          code("p08l5", "Implement the protocol",
               "Dunder methods over a small collection.",
               "Write a class `Portfolio` taking a list of amounts. It must support "
               "`len()`, iteration, `in`, `+` with another Portfolio (returning a new "
               "one), and a `total` property.",
               "class Portfolio:\n    ...\n",
               "p = Portfolio([1, 2, 3])\nq = Portfolio([4])\n"
               "assert len(p) == 3\nassert list(p) == [1, 2, 3]\nassert 2 in p\n"
               "assert p.total == 6\nr = p + q\nassert list(r) == [1, 2, 3, 4]\n"
               "assert len(p) == 3\nassert Portfolio([]).total == 0",
               "class Portfolio:\n"
               "    def __init__(self, amounts):\n        self.amounts = list(amounts)\n\n"
               "    def __len__(self):\n        return len(self.amounts)\n\n"
               "    def __iter__(self):\n        return iter(self.amounts)\n\n"
               "    def __contains__(self, x):\n        return x in self.amounts\n\n"
               "    def __add__(self, other):\n"
               "        return Portfolio(self.amounts + list(other))\n\n"
               "    @property\n    def total(self):\n        return sum(self.amounts)\n",
               "`__contains__` is optional — `in` falls back to `__iter__` — but "
               "implementing it is faster and clearer.",
               ""),
          quiz("p08l6", "Class or function?",
               "The design question that comes up daily.",
               "You need something that converts a currency amount using a rate table "
               "loaded once at startup. Class or function?",
               ["A class — it has state (the rate table)",
                "A function taking the table as an argument, or a closure over it — "
                "there is one operation and no state that changes",
                "A class with only static methods",
                "A module-level global"],
               1,
               "One operation over fixed data is a function. A class here adds a "
               "constructor, an instance and a method call for no benefit. Reach for a "
               "class when there is state that *changes* over time, or several "
               "operations that share it. (Option 3 — a class of static methods — is a "
               "namespace pretending to be a class; use a module.)"),
      ],
      links=[{"track": "typing", "level": "t11",
              "note": "Typing Level 11 drills dataclass syntax at speed."}])

# ============================================================ L9
level(9, "p09", "Iterators & Generators",
      "Lazy sequences, and why they matter.",
      """A **generator** is a function with `yield` in it. Calling it runs no code —
it returns a generator object. Each `next()` runs until the next `yield` and
then *freezes*, keeping local state.

```python
def read_amounts(path):
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield float(line)
```

This processes a 10 GB file in constant memory. The list version would not
finish.

**`yield from`** delegates to another iterable, which makes recursive
generators trivial:

```python
def walk(node):
    yield node
    for child in node.children:
        yield from walk(child)
```

**itertools** is the standard library at its best:

| Function | Does |
|---|---|
| `chain(a, b)` | concatenate iterables |
| `islice(it, n)` | take the first n |
| `groupby(it, key)` | group **consecutive** equal keys (sort first!) |
| `takewhile` / `dropwhile` | stop / start on a predicate |
| `count`, `cycle`, `repeat` | infinite sequences |
| `pairwise(it)` | (3.10+) consecutive pairs |

**The trap:** a generator is consumed **once**. Iterating it a second time gives
you nothing, silently. If you need the values twice, materialise a list — and
`len()` does not work on a generator either.""",
      [
          out("p09l1", "Lazy evaluation",
              "Watch when the body actually runs.",
              "def gen():\n    print('start')\n    yield 1\n    print('middle')\n    yield 2\n    print('end')\n\n"
              "g = gen()\nprint('created')\nprint(next(g))\nprint(next(g))",
              "created\nstart\n1\nmiddle\n2",
              "Nothing ran until the first `next()`, and `'end'` never printed because "
              "we stopped before the function finished."),
          out("p09l2", "Generators are consumed once",
              "The bug that produces mysterious empty results.",
              "g = (x * 2 for x in range(3))\nprint(list(g))\nprint(list(g))\nprint(sum(x for x in []))",
              "[0, 2, 4]\n[]\n0",
              "The second `list(g)` is empty and raises no error. If a function takes an "
              "iterable and needs it twice, it must convert it to a list first — or "
              "document that it consumes the input."),
          out("p09l3", "itertools.groupby needs sorting",
              "The single most common groupby mistake.",
              "from itertools import groupby\n"
              "rows = [('a', 1), ('b', 2), ('a', 3)]\n"
              "print({k: [v for _, v in g] for k, g in groupby(rows, key=lambda r: r[0])})\n"
              "rows.sort(key=lambda r: r[0])\n"
              "print({k: [v for _, v in g] for k, g in groupby(rows, key=lambda r: r[0])})",
              "{'a': [3], 'b': [2]}\n{'a': [1, 3], 'b': [2]}",
              "`groupby` only groups *consecutive* equal keys — the first result "
              "silently lost the `('a', 1)` group when the second `'a'` overwrote it in "
              "the dict. Sort by the same key first, or use a `defaultdict`."),
          code("p09l4", "Write a generator",
               "Constant memory over a large input.",
               "Write `chunks(items, size)` yielding successive lists of at most `size` "
               "items. It must be a generator (not build the whole result).",
               "def chunks(items, size):\n    ...\n",
               "import types\nassert isinstance(chunks([1], 1), types.GeneratorType)\n"
               "assert list(chunks([1, 2, 3, 4, 5], 2)) == [[1, 2], [3, 4], [5]]\n"
               "assert list(chunks([], 3)) == []\n"
               "assert list(chunks([1, 2], 5)) == [[1, 2]]",
               "def chunks(items, size):\n"
               "    batch = []\n"
               "    for item in items:\n"
               "        batch.append(item)\n"
               "        if len(batch) == size:\n"
               "            yield batch\n            batch = []\n"
               "    if batch:\n        yield batch\n",
               "Accumulate into a list, yield it when full, and do not forget the "
               "partial batch at the end.",
               ""),
          code("p09l5", "yield from and recursion",
               "Flatten arbitrarily nested lists.",
               "Write `deep_flatten(x)` yielding every non-list item from an arbitrarily "
               "nested structure of lists.",
               "def deep_flatten(x):\n    ...\n",
               "assert list(deep_flatten([1, [2, [3, [4]]], 5])) == [1, 2, 3, 4, 5]\n"
               "assert list(deep_flatten([])) == []\n"
               "assert list(deep_flatten([[], [[]]])) == []",
               "def deep_flatten(x):\n"
               "    for item in x:\n"
               "        if isinstance(item, list):\n"
               "            yield from deep_flatten(item)\n"
               "        else:\n            yield item\n",
               "`yield from` on the recursive call; plain `yield` on the leaf.",
               ""),
          code("p09l6", "A running total",
               "State that survives between yields.",
               "Write `running_total(amounts)` yielding the cumulative sum after each "
               "item.",
               "def running_total(amounts):\n    ...\n",
               "assert list(running_total([1, 2, 3])) == [1, 3, 6]\n"
               "assert list(running_total([])) == []\n"
               "assert list(running_total([5])) == [5]",
               "def running_total(amounts):\n"
               "    total = 0\n"
               "    for a in amounts:\n"
               "        total += a\n        yield total\n",
               "The local `total` persists across yields — that is the whole trick. "
               "(`itertools.accumulate` does this for you.)",
               ""),
          quiz("p09l7", "When is a list better?",
               "Lazy is not always right.",
               "When should you return a list instead of a generator?",
               ["Always — generators are confusing",
                "When callers need `len()`, indexing, or to iterate more than once, or "
                "when the result is small and computed anyway",
                "When the data is large",
                "Never"],
               1,
               "Generators win on large or infinite sequences and on pipelines. They "
               "lose when the caller needs random access, a length, or a second pass — "
               "and for a ten-element result the laziness buys nothing while costing "
               "the caller flexibility."),
      ])

# ============================================================ L10
level(10, "p10", "Decorators & Functional Tools",
      "Functions that take and return functions.",
      """A decorator is just this:

```python
@timed
def work(): ...

# is exactly
work = timed(work)
```

The standard shape, which you should be able to write from memory:

```python
import functools


def timed(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        try:
            return fn(*args, **kwargs)
        finally:
            print(f'{fn.__name__}: {time.perf_counter() - start:.3f}s')
    return wrapper
```

**`functools.wraps` is not optional.** Without it the decorated function loses
its `__name__`, `__doc__` and signature, which breaks introspection, debuggers,
Sphinx and every framework that reads them.

**A decorator with arguments** needs one more layer — a function that returns
the decorator:

```python
def retry(times=3):
    def decorator(fn): ...
    return decorator
```

**From the standard library:** `functools.lru_cache` / `cache` memoises pure
functions (one line, occasionally a thousandfold speedup);
`functools.partial` pre-binds arguments; `functools.reduce` folds a sequence;
`operator.itemgetter` / `attrgetter` make fast, readable sort keys.

**Closures** are what make all of this work: the inner function keeps a live
reference to the enclosing scope's variables. To *rebind* one, you need
`nonlocal`.""",
      [
          out("p10l1", "Decoration is just assignment",
              "No magic, only syntax.",
              "def shout(fn):\n"
              "    def wrapper(*a, **k):\n        return fn(*a, **k).upper()\n"
              "    return wrapper\n\n"
              "@shout\ndef greet(name):\n    return f'hola {name}'\n\n"
              "print(greet('marco'))\nprint(greet.__name__)",
              "HOLA MARCO\nwrapper",
              "`greet` is now `wrapper` — note that `__name__` was lost. That is exactly "
              "what `functools.wraps` fixes."),
          out("p10l2", "Closures capture variables, not values",
              "The late-binding trap.",
              "fns = [lambda: i for i in range(3)]\nprint([f() for f in fns])\n"
              "fns = [lambda i=i: i for i in range(3)]\nprint([f() for f in fns])",
              "[2, 2, 2]\n[0, 1, 2]",
              "The first set of lambdas all close over the *same* `i`, read at call "
              "time — by then the loop has finished. The default-argument trick "
              "captures the value at definition time. (A factory function is the "
              "cleaner fix.)"),
          out("p10l3", "lru_cache",
              "One line, enormous difference.",
              "import functools\ncalls = []\n\n"
              "@functools.cache\ndef fib(n):\n    calls.append(n)\n"
              "    return n if n < 2 else fib(n - 1) + fib(n - 2)\n\n"
              "print(fib(20))\nprint(len(calls))",
              "6765\n21",
              "Without the cache this recursion makes 21,891 calls; with it, 21. Only "
              "ever apply it to pure functions with hashable arguments — a cached "
              "function that reads a file or a clock will lie to you."),
          code("p10l4", "Write a decorator",
               "The canonical shape, from memory.",
               "Write a decorator `counted` that records how many times the wrapped "
               "function was called in an attribute `calls`, preserves the function's "
               "`__name__`, and passes through arguments and return value unchanged.",
               "import functools\n\n\ndef counted(fn):\n    ...\n",
               "@counted\ndef add(a, b=0):\n    'docstring'\n    return a + b\n"
               "assert add(1, 2) == 3\nassert add(1, b=5) == 6\nassert add(1) == 1\n"
               "assert add.calls == 3\nassert add.__name__ == 'add'\n"
               "assert add.__doc__ == 'docstring'",
               "import functools\n\n\n"
               "def counted(fn):\n"
               "    @functools.wraps(fn)\n"
               "    def wrapper(*args, **kwargs):\n"
               "        wrapper.calls += 1\n"
               "        return fn(*args, **kwargs)\n"
               "    wrapper.calls = 0\n"
               "    return wrapper\n",
               "Attach the counter to `wrapper` itself, and set it before returning.",
               "`yyp` duplicates the `@functools.wraps` line when you write the next one."),
          code("p10l5", "A decorator with arguments",
               "Three levels deep.",
               "Write `repeat(times)` — a decorator factory whose decorated function "
               "runs `times` times and returns a list of the results.",
               "import functools\n\n\ndef repeat(times):\n    ...\n",
               "n = []\n@repeat(3)\ndef tick():\n    n.append(1)\n    return len(n)\n"
               "assert tick() == [1, 2, 3]\nassert tick.__name__ == 'tick'\n"
               "@repeat(1)\ndef echo(x):\n    return x\nassert echo('a') == ['a']",
               "import functools\n\n\n"
               "def repeat(times):\n"
               "    def decorator(fn):\n"
               "        @functools.wraps(fn)\n"
               "        def wrapper(*args, **kwargs):\n"
               "            return [fn(*args, **kwargs) for _ in range(times)]\n"
               "        return wrapper\n"
               "    return decorator\n",
               "Outer function takes the argument, middle takes the function, inner "
               "takes the call's arguments.",
               ""),
          code("p10l6", "Sort with itemgetter",
               "Readable, fast sort keys.",
               "Write `by_amount_desc(rows)` returning the rows sorted by `'amount'` "
               "descending, breaking ties by `'ref'` ascending.",
               "from operator import itemgetter\n\n\ndef by_amount_desc(rows):\n    ...\n",
               "rows = [{'ref': 'b', 'amount': 5}, {'ref': 'a', 'amount': 9},\n"
               "        {'ref': 'a', 'amount': 5}]\n"
               "assert [r['ref'] for r in by_amount_desc(rows)] == ['a', 'a', 'b']\n"
               "assert by_amount_desc(rows)[0]['amount'] == 9\nassert by_amount_desc([]) == []",
               "def by_amount_desc(rows):\n"
               "    return sorted(rows, key=lambda r: (-r['amount'], r['ref']))\n",
               "A tuple key sorts by each element in turn; negate the numeric one to "
               "reverse just that field. (`reverse=True` would reverse *both*.)",
               ""),
          quiz("p10l7", "Why functools.wraps?",
               "The one thing people leave out.",
               "What breaks if you omit `@functools.wraps(fn)` in a decorator?",
               ["The decorator returns None",
                "The wrapped function loses `__name__`, `__doc__` and its signature, "
                "breaking introspection, docs and any framework that reads them",
                "Arguments are not passed through",
                "Nothing, it is cosmetic"],
               1,
               "Behaviour is unaffected, which is exactly why the bug survives to "
               "production. Then a framework that dispatches on `__name__`, or a "
               "doc generator, or `inspect.signature` in a test, quietly does the "
               "wrong thing."),
      ])

# ============================================================ L11
level(11, "p11", "Types & Concurrency",
      "Annotations that catch bugs, and code that waits efficiently.",
      """**Type hints** are not checked at runtime — they are for readers and for
`mypy`/`pyright`. Modern syntax (3.10+):

```python
def parse(raw: str) -> dict[str, int]: ...
def find(xs: list[int], k: int) -> int | None: ...
Handler = Callable[[Event], Awaitable[None]]
```

`list[int]` not `List[int]`; `X | None` not `Optional[X]`. Annotate the
*boundaries* — function signatures, dataclass fields, module constants — and let
local variables be inferred. A codebase with typed signatures and an untyped
interior gets most of the benefit for a fraction of the effort.

**Concurrency: pick by the bottleneck.**

| Bottleneck | Tool | Why |
|---|---|---|
| Waiting on network/disk | `asyncio` or threads | the GIL is released while waiting |
| CPU-bound computation | `multiprocessing` / `ProcessPoolExecutor` | separate interpreters, real parallelism |

The GIL means threads never run Python bytecode in parallel — but it is released
during I/O, so threads *do* help there. (Free-threaded builds without the GIL are
appearing, but the rule above is still how to reason in 2026.)

```python
async def fetch_all(urls: list[str]) -> list[bytes]:
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(*(client.get(u) for u in urls))
    return [r.content for r in results]
```

**`asyncio.gather` is the whole point** — `await` in a loop is sequential and
buys you nothing. And an `async def` that never awaits anything is just a slower
function.""",
      [
          out("p11l1", "gather vs sequential await",
              "The difference between 0.1s and 0.5s.",
              "import asyncio, time\n\n"
              "async def work(n):\n    await asyncio.sleep(0.05)\n    return n\n\n"
              "async def main():\n"
              "    t = time.perf_counter()\n"
              "    seq = [await work(i) for i in range(4)]\n"
              "    t1 = time.perf_counter() - t\n"
              "    t = time.perf_counter()\n"
              "    par = await asyncio.gather(*(work(i) for i in range(4)))\n"
              "    t2 = time.perf_counter() - t\n"
              "    print(seq, par)\n"
              "    print(t1 > 0.15, t2 < 0.15)\n\n"
              "asyncio.run(main())",
              "[0, 1, 2, 3] [0, 1, 2, 3]\nTrue True",
              "Same results, four times the wall-clock for the sequential version. "
              "`await` in a loop is the most common asyncio mistake — it makes the code "
              "async without making it concurrent."),
          out("p11l2", "Annotations are not enforced",
              "They are documentation the tools can check.",
              "def add(a: int, b: int) -> int:\n    return a + b\n\n"
              "print(add('x', 'y'))\nprint(add.__annotations__['a'].__name__)",
              "xy\nint",
              "Python happily concatenated two strings. A type checker would have "
              "flagged it before the code ran — which is the entire value proposition: "
              "the error moves from runtime to your editor."),
          out("p11l3", "Threads help I/O, not CPU",
              "The GIL in one experiment.",
              "from concurrent.futures import ThreadPoolExecutor\nimport time\n\n"
              "def io_task(n):\n    time.sleep(0.05)\n    return n\n\n"
              "t = time.perf_counter()\n"
              "with ThreadPoolExecutor(max_workers=4) as ex:\n"
              "    out = list(ex.map(io_task, range(4)))\n"
              "print(out)\nprint(time.perf_counter() - t < 0.15)",
              "[0, 1, 2, 3]\nTrue",
              "Four 50 ms sleeps finished in well under 150 ms because the GIL is "
              "released while a thread waits. Replace `sleep` with a tight arithmetic "
              "loop and the same code shows no speed-up at all."),
          code("p11l4", "Annotate a signature",
               "Modern syntax, no typing imports needed.",
               "Write `totals(rows)` — annotated as taking `list[dict[str, float]]` and "
               "returning `dict[str, float]` — that sums the `'amount'` of each row by "
               "its `'ccy'`. Use `from __future__ import annotations` is not needed; "
               "use built-in generics directly.",
               "def totals(rows):\n    ...\n",
               "import typing\nhints = typing.get_type_hints(totals)\n"
               "assert hints['rows'] == list[dict[str, float]], hints\n"
               "assert hints['return'] == dict[str, float], hints\n"
               "assert totals([{'ccy': 'EUR', 'amount': 1.0},\n"
               "               {'ccy': 'EUR', 'amount': 2.0}]) == {'EUR': 3.0}\n"
               "assert totals([]) == {}",
               "def totals(rows: list[dict[str, float]]) -> dict[str, float]:\n"
               "    out: dict[str, float] = {}\n"
               "    for row in rows:\n"
               "        out[row['ccy']] = out.get(row['ccy'], 0.0) + row['amount']\n"
               "    return out\n",
               "`dict[str, float]`, lowercase, no import.",
               ""),
          code("p11l5", "Run coroutines concurrently",
               "gather, not a loop of awaits.",
               "Write `async def fetch_all(fns)` that runs every zero-argument coroutine "
               "function in `fns` concurrently and returns their results in order. "
               "Provide a synchronous `run_all(fns)` wrapper using `asyncio.run`.",
               "import asyncio\n\n\nasync def fetch_all(fns):\n    ...\n\n\ndef run_all(fns):\n    ...\n",
               "import asyncio, time\n"
               "async def mk(n):\n    await asyncio.sleep(0.05)\n    return n\n"
               "fns = [lambda n=n: mk(n) for n in range(4)]\n"
               "t = time.perf_counter()\nassert run_all(fns) == [0, 1, 2, 3]\n"
               "assert time.perf_counter() - t < 0.15, 'not concurrent'",
               "import asyncio\n\n\n"
               "async def fetch_all(fns):\n"
               "    return list(await asyncio.gather(*(fn() for fn in fns)))\n\n\n"
               "def run_all(fns):\n"
               "    return asyncio.run(fetch_all(fns))\n",
               "`asyncio.gather(*coros)` preserves order and runs them together.",
               ""),
          quiz("p11l6", "Which concurrency tool?",
               "Pick by the bottleneck, never by fashion.",
               "You need to resize 5,000 images as fast as possible on an 8-core "
               "machine. Which tool?",
               ["asyncio — it is the modern choice",
                "ProcessPoolExecutor — the work is CPU-bound, so you need separate "
                "interpreters to use all cores",
                "ThreadPoolExecutor — threads are lighter than processes",
                "A plain loop — Python cannot parallelise"],
               1,
               "Image resizing is pure computation, so the GIL serialises threads and "
               "asyncio gives you nothing at all (there is no waiting to overlap). "
               "Processes each get their own interpreter and genuinely use all eight "
               "cores. Caveat: arguments and results are pickled between processes, so "
               "the win shrinks if you pass very large objects around."),
      ],
      links=[{"track": "typing", "level": "t10",
              "note": "Type annotations are symbol-dense — Typing Level 10."}])

# ============================================================ L12
level(12, "p12", "Testing, Tooling & Performance",
      "The habits that separate scripts from software.",
      """**pytest.** Plain functions, plain `assert`, readable failures.

```python
import pytest


def test_classify_boundaries():
    assert classify(10000) == 'auto'
    assert classify(10001) == 'escalate'


@pytest.mark.parametrize('raw,expected', [('1', 1.0), ('2.5', 2.5)])
def test_parse(raw, expected):
    assert parse_amount(raw) == expected


def test_rejects_negative():
    with pytest.raises(ValidationError, match='bad amount'):
        parse_amount('-1')
```

Test **behaviour at the boundaries**, not every line. Three tests on the edge
cases of one function are worth more than thirty that walk the happy path.

**Tooling, 2026 edition.** `ruff` is linter and formatter in one and is fast
enough to run on every save; `pyright` or `mypy` for types; `uv` for
environments and dependency resolution; `pyproject.toml` as the single config
file for all of them.

**Performance, in order:**

1. **Measure.** `time.perf_counter()` for a rough number, `timeit` for a
   microbenchmark, `cProfile` + `snakeviz` for a real profile. Intuition about
   Python performance is wrong more often than it is right.
2. **Fix the algorithm.** `in` on a list → `in` on a set. A nested loop → a dict
   lookup. This is where the 100× lives.
3. **Then micro-optimise** — local variable lookups, comprehensions over
   `append` loops, `__slots__`.
4. **Then reach for C** — numpy, or the function in the standard library that is
   already written in C.

**The stdlib you should know exists:** `collections`, `itertools`, `functools`,
`pathlib`, `dataclasses`, `enum`, `datetime`, `decimal` (for money — never
floats), `statistics`, `re`, `json`, `csv`, `sqlite3`, `argparse`, `logging`,
`subprocess`, `textwrap`, `difflib`.""",
      [
          out("p12l1", "Floats are not money",
              "Why `decimal` exists.",
              "from decimal import Decimal\nprint(0.1 + 0.2)\nprint(0.1 + 0.2 == 0.3)\n"
              "print(Decimal('0.1') + Decimal('0.2') == Decimal('0.3'))\n"
              "print(round(2.675, 2))",
              "0.30000000000000004\nFalse\nTrue\n2.67",
              "Binary floating point cannot represent 0.1 exactly. For anything "
              "involving currency use `Decimal` constructed **from strings** — "
              "`Decimal(0.1)` inherits the float's error and defeats the purpose."),
          out("p12l2", "Measure, do not guess",
              "The set-versus-list difference, made concrete.",
              "import time\nbig = list(range(50000))\nbigset = set(big)\n"
              "t = time.perf_counter()\nsum(1 for i in range(2000) if i in big)\n"
              "slow = time.perf_counter() - t\n"
              "t = time.perf_counter()\nsum(1 for i in range(2000) if i in bigset)\n"
              "fast = time.perf_counter() - t\nprint(slow > fast * 5)",
              "True",
              "The list version scans up to 50,000 elements for every lookup; the set "
              "hashes once. This is the single highest-value optimisation in most "
              "Python code, and it is a one-word change."),
          out("p12l3", "Testing the boundary",
               "Where bugs actually live.",
               "def classify(a):\n"
               "    if a <= 0:\n        return 'reject'\n"
               "    if a <= 10000:\n        return 'auto'\n"
               "    return 'escalate'\n\n"
               "for a in [-1, 0, 1, 10000, 10001]:\n    print(a, classify(a))",
               "-1 reject\n0 reject\n1 auto\n10000 auto\n10001 escalate",
               "Five values, all at or adjacent to a boundary. Testing 500 random "
               "amounts in the middle of each range would find strictly less."),
          code("p12l4", "Money arithmetic",
               "Decimal, with correct rounding.",
               "Write `apply_fee(amount, pct)` taking string amounts, applying a "
               "percentage fee, and returning a `Decimal` rounded to two decimal "
               "places with banker-free half-up rounding.",
               "from decimal import Decimal, ROUND_HALF_UP\n\n\ndef apply_fee(amount, pct):\n    ...\n",
               "from decimal import Decimal\n"
               "assert apply_fee('100.00', '2.5') == Decimal('102.50')\n"
               "assert apply_fee('0.01', '50') == Decimal('0.02')\n"
               "assert apply_fee('1000', '0') == Decimal('1000.00')\n"
               "assert isinstance(apply_fee('1', '1'), Decimal)",
               "from decimal import Decimal, ROUND_HALF_UP\n\n\n"
               "def apply_fee(amount, pct):\n"
               "    total = Decimal(amount) * (1 + Decimal(pct) / 100)\n"
               "    return total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)\n",
               "`quantize` is how you round a Decimal to a fixed number of places. "
               "Decimal's default is ROUND_HALF_EVEN, which is not what finance wants.",
               ""),
          code("p12l5", "Optimise an algorithm",
               "Same output, different complexity.",
               "`common(a, b)` should return a sorted list of the values present in both "
               "lists. Make it work for lists of 100,000 items — an O(n·m) nested scan "
               "will time out.",
               "def common(a, b):\n    ...\n",
               "assert common([3, 1, 2], [2, 3, 4]) == [2, 3]\n"
               "assert common([], [1]) == []\nassert common([1, 1, 2], [1]) == [1]\n"
               "import time\nbig1 = list(range(100000)); big2 = list(range(50000, 150000))\n"
               "t = time.perf_counter()\nassert len(common(big1, big2)) == 50000\n"
               "assert time.perf_counter() - t < 1.0, 'too slow — use sets'",
               "def common(a, b):\n    return sorted(set(a) & set(b))\n",
               "Set intersection is O(n + m). The `&` operator is the intersection.",
               ""),
          code("p12l6", "Make it testable",
               "Separate the pure part from the I/O.",
               "Refactor: write `summarise(rows)` returning "
               "`{'count': n, 'total': t, 'mean': m}` for a list of amounts, with "
               "`mean` 0.0 for an empty input. No printing, no file access — pure, "
               "so it is trivially testable.",
               "def summarise(rows):\n    ...\n",
               "assert summarise([]) == {'count': 0, 'total': 0.0, 'mean': 0.0}\n"
               "assert summarise([1.0, 2.0, 3.0]) == {'count': 3, 'total': 6.0, 'mean': 2.0}\n"
               "r = summarise([1.0, 2.0])\nassert r['mean'] == 1.5",
               "def summarise(rows):\n"
               "    total = float(sum(rows))\n    n = len(rows)\n"
               "    return {'count': n, 'total': total, 'mean': total / n if n else 0.0}\n",
               "A conditional expression handles the empty case without a branch.",
               "Extracting a function is `V}d` then `P` where it belongs."),
          quiz("p12l7", "Where to optimise first",
               "The last habit.",
               "A report takes 40 seconds. Profiling shows 38 of them inside one "
               "function that looks up each of 20,000 records in a list of 30,000. "
               "What do you do?",
               ["Rewrite the whole report in C",
                "Build a dict or set index once, turning 20,000 linear scans into "
                "20,000 hash lookups",
                "Add multiprocessing",
                "Micro-optimise the loop body"],
               1,
               "600 million comparisons become 20,000 lookups — the 38 seconds "
               "collapse to milliseconds, for about two lines of change. Parallelism "
               "would give you at best an 8× speed-up on the *same* bad algorithm, and "
               "C or micro-optimisation the same. Always fix the complexity first."),
      ],
      links=[{"track": "nvim", "level": "v12",
              "note": "Running pytest from inside Neovim closes the loop."},
             {"track": "typing", "level": "t12",
              "note": "Expert typing: long, symbol-dense passages like these."}])

doc = {
    "track": "python",
    "title": "Python",
    "subtitle": "from names and loops to async, decorators and profiling",
    "icon": "python",
    "levels": L,
}

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(doc, fh, ensure_ascii=False, indent=1)
    fh.write("\n")
print(f"python.json: {len(L)} levels, {sum(len(l['lessons']) for l in L)} lessons")
