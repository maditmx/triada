#!/usr/bin/env python3
"""Generate curriculum/typing.json — 12 levels, ES QWERTY (Spain).

Drill text is generated deterministically from a seed so the file is
reproducible: re-running this script produces byte-identical output.
"""
import json
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "curriculum", "typing.json")

# ---------------------------------------------------------------- helpers


def rng(seed):
    return random.Random(f"triada::{seed}")


def bigrams(keys, seed, groups=14, per_group=4, glen=3):
    """Rhythm drill: groups of short random clusters built from `keys`."""
    r = rng(seed)
    out = []
    for _ in range(groups):
        chunk = "".join(
            "".join(r.choice(keys) for _ in range(glen)) for _ in range(1)
        )
        out.append(chunk)
        for _ in range(per_group - 1):
            out.append("".join(r.choice(keys) for _ in range(glen)))
    return " ".join(out)


def ladder(pairs, seed, reps=6):
    """Alternating-finger ladder: 'fj jf ff jj' style."""
    r = rng(seed)
    out = []
    for a, b in pairs:
        block = [a * 3, b * 3, a + b, b + a, a + b + a, b + a + b]
        r.shuffle(block)
        out.extend(block[:reps])
    return " ".join(out)


def wordline(words, seed, n=40):
    r = rng(seed)
    return " ".join(r.choice(words) for _ in range(n))


# ---------------------------------------------------------------- content

L = []


def level(n, lid, title, goal, brief, wpm, acc, lessons, links=None):
    L.append(
        {
            "id": lid,
            "n": n,
            "title": title,
            "goal": goal,
            "brief": brief,
            "pass": {"wpm": wpm, "acc": acc},
            "lessons": lessons,
            "links": links or [],
        }
    )


def lesson(lid, title, kind, content, teach="", focus=None):
    return {
        "id": lid,
        "title": title,
        "kind": kind,  # keys | words | text | code
        "teach": teach,
        "focus": focus or [],
        "content": content,
    }


# ---- Level 1: home row anchors -----------------------------------------
level(
    1,
    "t01",
    "Home Row Anchors",
    "Find F and J without looking. Never look down again.",
    """Put your left index on **F** and your right index on **J**. Both keys have a
raised bump — that bump is the only thing your hands are allowed to search for,
ever. The other six fingers fall into place beside them:

```
left   a  s  d  f        j  k  l  ñ   right
       4  3  2  1        1  2  3  4     (1 = index)
```

Thumbs rest on the space bar. Wrists floating, not resting on the desk. If you
lose your place, lift both hands, drop them back on the bumps, and continue.

**Rule for the whole track: do not look at the keyboard.** Slow and correct beats
fast and peeking. Speed is a side effect of accuracy, never the other way round.""",
    12,
    0.92,
    [
        lesson(
            "t01l1",
            "Index fingers: f and j",
            "keys",
            ladder([("f", "j")], "t01l1", 12) + " " + bigrams("fj", "t01l1b", 10, 3, 4),
            "Only two keys. Feel the bumps. Eyes on the screen.",
            ["f", "j"],
        ),
        lesson(
            "t01l2",
            "Middle fingers: d and k",
            "keys",
            ladder([("d", "k"), ("f", "j")], "t01l2", 8)
            + " "
            + bigrams("dkfj", "t01l2b", 12, 3, 4),
            "Your index fingers stay anchored while the middle fingers move.",
            ["d", "k"],
        ),
        lesson(
            "t01l3",
            "Ring fingers: s and l",
            "keys",
            ladder([("s", "l"), ("d", "k")], "t01l3", 8)
            + " "
            + bigrams("sldkfj", "t01l3b", 12, 3, 4),
            "The ring finger is the weakest. Give it clean, deliberate strokes.",
            ["s", "l"],
        ),
        lesson(
            "t01l4",
            "Little fingers: a and ñ",
            "keys",
            ladder([("a", "ñ"), ("s", "l")], "t01l4", 8)
            + " "
            + bigrams("añsl", "t01l4b", 12, 3, 4),
            "**ñ** sits where a US keyboard has the semicolon — right of L, right pinky.",
            ["a", "ñ"],
        ),
        lesson(
            "t01l5",
            "Stretch keys: g and h",
            "keys",
            ladder([("g", "h")], "t01l5", 10)
            + " "
            + bigrams("ghfj", "t01l5b", 12, 3, 4),
            "The index fingers stretch inward for G and H, then snap back to F and J.",
            ["g", "h"],
        ),
        lesson(
            "t01l6",
            "All eight fingers",
            "keys",
            bigrams("asdfghjklñ", "t01l6", 20, 4, 3),
            "Every home-row key, random order. This is your baseline.",
            list("asdfghjklñ"),
        ),
    ],
)

# ---- Level 2: home row words -------------------------------------------
HOME_WORDS = [
    "sal",
    "gas",
    "das",
    "haz",
    "ala",
    "asa",
    "faja",
    "hala",
    "gala",
    "jalá",
    "sala",
    "falla",
    "halla",
    "dalas",
    "flash",
    "lags",
    "sagas",
    "fáng",
    "hall",
    "dad",
    "gada",
    "js",
    "ash",
    "kal",
    "lag",
    "slash",
]
HOME_WORDS = [w for w in HOME_WORDS if all(c in "asdfghjklñ" for c in w)]

level(
    2,
    "t02",
    "Home Row Words & Rhythm",
    "Type real syllables from the home row at an even tempo.",
    """Letters are not the unit of typing — *rhythm* is. Aim for a metronome-steady
stream where every keystroke takes the same time, including the space bar.

Two habits that decide your ceiling:

1. **Return to home.** After every stroke the finger comes back to its resting key.
2. **Space with the thumb of the hand that did *not* type the last letter** — it
   costs nothing now and buys you 10 wpm later.

Errors: this trainer does not let you race past a mistake. Fix it and move on.""",
    18,
    0.94,
    [
        lesson(
            "t02l1",
            "Three-letter syllables",
            "words",
            wordline([w for w in HOME_WORDS if len(w) == 3], "t02l1", 44),
            focus=list("asdfghjkl"),
        ),
        lesson(
            "t02l2",
            "Longer clusters",
            "words",
            wordline([w for w in HOME_WORDS if len(w) >= 4], "t02l2", 36),
        ),
        lesson(
            "t02l3",
            "Hand alternation",
            "keys",
            bigrams("asdfghjklñ", "t02l3", 22, 4, 4),
            "Alternating hands is the fastest pattern there is. Notice how much easier "
            "`fj` feels than `fd`.",
        ),
        lesson(
            "t02l4",
            "Same-hand rolls",
            "keys",
            " ".join(
                [
                    "asdf",
                    "fdsa",
                    "jklñ",
                    "ñlkj",
                    "sdfg",
                    "gfds",
                    "hjkl",
                    "lkjh",
                    "asdf",
                    "jklñ",
                    "fdsa",
                    "ñlkj",
                    "adfs",
                    "jlñk",
                    "sfda",
                    "kjñl",
                ]
                * 3
            ),
            "Rolls (adjacent fingers, one direction) are the second-fastest pattern. "
            "Train them explicitly.",
        ),
        lesson(
            "t02l5",
            "Sustained mixed drill",
            "words",
            wordline(HOME_WORDS, "t02l5", 60),
            "Longer run. Watch your accuracy number, not the clock.",
        ),
    ],
    links=[
        {
            "track": "nvim",
            "level": "v01",
            "note": "hjkl — Vim's movement keys — are four home-row keys you just drilled.",
        }
    ],
)

# ---- Level 3: top row ---------------------------------------------------
level(
    3,
    "t03",
    "Top Row",
    "Reach up and come straight back down.",
    """The top row is `q w e r t  y u i o p`. Each finger owns the key diagonally
above its home key:

```
q  w  e  r  t     y  u  i  o  p
4  3  2  1  1     1  1  2  3  4
```

`t` and `y` are the index-finger stretches, exactly like `g` and `h` were.

The mistake everyone makes: the hand *travels* up and stays there. It shouldn't.
Only the finger moves; the palm stays put over the home row.""",
    22,
    0.94,
    [
        lesson("t03l1", "e and i", "keys", ladder([("e", "i")], "t03l1", 10) + " " + bigrams("eidk", "t03l1b", 12, 3, 4), focus=["e", "i"]),
        lesson("t03l2", "r and u", "keys", ladder([("r", "u")], "t03l2", 10) + " " + bigrams("rufj", "t03l2b", 12, 3, 4), focus=["r", "u"]),
        lesson("t03l3", "t and y", "keys", ladder([("t", "y")], "t03l3", 10) + " " + bigrams("tyru", "t03l3b", 12, 3, 4), focus=["t", "y"]),
        lesson("t03l4", "w and o", "keys", ladder([("w", "o")], "t03l4", 10) + " " + bigrams("wosl", "t03l4b", 12, 3, 4), focus=["w", "o"]),
        lesson("t03l5", "q and p", "keys", ladder([("q", "p")], "t03l5", 10) + " " + bigrams("qpañ", "t03l5b", 12, 3, 4), focus=["q", "p"]),
        lesson(
            "t03l6",
            "Top + home words",
            "words",
            wordline(
                [
                    "que",
                    "para",
                    "puerta",
                    "trigo",
                    "sopa",
                    "reto",
                    "aire",
                    "poder",
                    "julio",
                    "queso",
                    "flor",
                    "grupo",
                    "pared",
                    "salir",
                    "raro",
                    "lider",
                    "prisa",
                    "logro",
                    "traje",
                    "torre",
                ],
                "t03l6",
                48,
            ),
        ),
        lesson(
            "t03l7",
            "Top row sprint",
            "keys",
            bigrams("qwertyuiop", "t03l7", 20, 4, 4),
        ),
    ],
)

# ---- Level 4: bottom row ------------------------------------------------
level(
    4,
    "t04",
    "Bottom Row",
    "The hardest row. Curl down without collapsing the hand.",
    """`z x c v b  n m , . -` sits below home. It is the slowest row for almost
everyone because the fingers curl *under*, which is a weaker motion than
reaching up.

```
z  x  c  v  b     n  m  ,  .  -
4  3  2  1  1     1  2  3  4  4
```

`b` is a left-index stretch; `n` belongs to the right index. If you type `b`
with the right hand (very common bad habit) you will hit a wall around 55 wpm.

`,` `.` and `-` are here too, and they matter more than the letters: they are
everywhere in both prose and code.""",
    26,
    0.95,
    [
        lesson("t04l1", "v and n", "keys", ladder([("v", "n")], "t04l1", 10) + " " + bigrams("vnfj", "t04l1b", 12, 3, 4), focus=["v", "n"]),
        lesson("t04l2", "c and m", "keys", ladder([("c", "m")], "t04l2", 10) + " " + bigrams("cmdk", "t04l2b", 12, 3, 4), focus=["c", "m"]),
        lesson("t04l3", "x and comma", "keys", ladder([("x", ",")], "t04l3", 10) + " " + bigrams("x,sl", "t04l3b", 12, 3, 4), focus=["x", ","]),
        lesson("t04l4", "z and period", "keys", ladder([("z", ".")], "t04l4", 10) + " " + bigrams("z.añ", "t04l4b", 12, 3, 4), focus=["z", "."]),
        lesson("t04l5", "b and hyphen", "keys", ladder([("b", "-")], "t04l5", 10) + " " + bigrams("bn-.", "t04l5b", 12, 3, 4), focus=["b", "-"]),
        lesson(
            "t04l6",
            "Bottom row words",
            "words",
            wordline(
                [
                    "vez",
                    "cama",
                    "buzo",
                    "menta",
                    "nave",
                    "zumo",
                    "cine",
                    "banco",
                    "mezcla",
                    "cambio",
                    "vencer",
                    "número",
                    "nombre",
                    "cubrir",
                    "excavar",
                    "vínculo",
                ],
                "t04l6",
                44,
            ),
        ),
        lesson(
            "t04l7",
            "All three rows",
            "keys",
            bigrams("asdfghjklñqwertyuiopzxcvbnm", "t04l7", 24, 4, 4),
        ),
    ],
)

# ---- Level 5: full alphabet + Spanish accents ---------------------------
level(
    5,
    "t05",
    "Full Alphabet & Accents",
    "Real Spanish prose, including the dead-key accents.",
    """Now the whole letter set, plus the two things a Spanish layout adds:

- **`´` (dead acute)** — the key right of `Ñ`. Press it, *nothing appears*, then
  press a vowel: `´` + `a` → `á`. That is what "dead key" means.
- **`¨` (dead diaeresis)** — `Shift` + `´`, then `u` → `ü` (pingüino, vergüenza).
- **`ñ`** — right pinky, already in your fingers from Level 1.

Dead keys cost two strokes but only one "beat" of rhythm; don't let them
break your tempo. Typing `á` should feel like typing one letter.""",
    30,
    0.95,
    [
        lesson(
            "t05l1",
            "Acute accents",
            "words",
            wordline(
                ["así", "café", "está", "más", "avión", "según", "también", "rápido",
                 "número", "público", "está", "acción", "razón", "difícil", "fácil",
                 "último", "próximo", "análisis", "código", "función"],
                "t05l1",
                40,
            ),
            focus=["´"],
        ),
        lesson(
            "t05l2",
            "Diaeresis and ñ",
            "words",
            wordline(
                ["pingüino", "vergüenza", "bilingüe", "ambigüedad", "año", "niño",
                 "señal", "mañana", "pequeño", "diseño", "español", "cañón", "sueño",
                 "extraño", "compañero"],
                "t05l2",
                36,
            ),
            focus=["¨", "ñ"],
        ),
        lesson(
            "t05l3",
            "Common Spanish words",
            "words",
            wordline(
                ["de", "la", "que", "el", "en", "y", "a", "los", "se", "del", "las",
                 "un", "por", "con", "no", "una", "su", "para", "es", "al", "lo",
                 "como", "más", "pero", "sus", "le", "ha", "me", "si", "sin", "sobre",
                 "este", "ya", "entre", "cuando", "todo", "esta", "ser", "son", "dos"],
                "t05l3",
                60,
            ),
        ),
        lesson(
            "t05l4",
            "Prose: on practice",
            "text",
            "La práctica deliberada no consiste en repetir lo que ya sabes hacer, "
            "sino en trabajar justo por encima de tu nivel actual, con atención plena "
            "y con información inmediata sobre cada error. Es incómoda por diseño: "
            "si la sesión se siente fácil, casi con seguridad estás repasando en "
            "lugar de aprender.",
        ),
        lesson(
            "t05l5",
            "Prose: on tools",
            "text",
            "Una herramienta que dominas desaparece. Dejas de pensar en el teclado y "
            "empiezas a pensar en el texto; dejas de pensar en los comandos y "
            "empiezas a pensar en el cambio que quieres hacer. Ese es el único "
            "objetivo razonable de todo este esfuerzo.",
        ),
        lesson(
            "t05l6",
            "English prose",
            "text",
            "The keyboard is the highest-bandwidth channel you have into a computer, "
            "and almost nobody bothers to widen it. Thirty hours of deliberate "
            "practice buys you a skill you will use every working day for the rest "
            "of your career, which is a return on investment that very few things "
            "can match.",
        ),
    ],
    links=[
        {
            "track": "python",
            "level": "p01",
            "note": "Python identifiers are ASCII by convention — good accents practice is prose, not code.",
        }
    ],
)

# ---- Level 6: shift & punctuation ---------------------------------------
level(
    6,
    "t06",
    "Shift, Capitals & Punctuation",
    "Use the opposite-hand Shift. Always.",
    """**The rule: the Shift you press is on the hand that is *not* typing the letter.**
Capital `A` → right pinky holds Shift, left pinky presses A. Capital `L` → left
Shift. Typing `A` with the left Shift twists the wrist and is the single most
common intermediate-level habit worth breaking.

Spanish punctuation you need:

| Character | Keystroke |
|---|---|
| `;` | `Shift` + `,` |
| `:` | `Shift` + `.` |
| `_` | `Shift` + `-` |
| `?` | `Shift` + `'` (the key right of `0`) |
| `¿` | `Shift` + `¡` (the key right of `'`) |
| `!` | `Shift` + `1` &nbsp;&nbsp; `¡` → its own key |
| `"` | `Shift` + `2` |""",
    32,
    0.95,
    [
        lesson(
            "t06l1",
            "Opposite-hand Shift",
            "words",
            wordline(
                ["Ana", "Luis", "Madrid", "Java", "Kant", "Sol", "Feliz", "Gato",
                 "Hola", "Jazz", "Lima", "Ñu", "Quito", "Roma", "Tokio", "Uva",
                 "Verde", "Wifi", "Xilo", "Yoga", "Zeta", "Perú", "Ávila", "Óscar"],
                "t06l1",
                40,
            ),
        ),
        lesson(
            "t06l2",
            "CamelCase and SCREAMING_CASE",
            "code",
            "getUserName setTimeout MAX_RETRIES HttpClient parseJSON DEFAULT_PORT "
            "readFile isValid TOTAL_COUNT DataFrame toString MIN_VALUE "
            "userId apiKey BASE_URL onClick handleError CACHE_TTL "
            "buildIndex nextToken IS_ENABLED loadConfig",
            "Notice how much Shift work code demands compared to prose.",
        ),
        lesson(
            "t06l3",
            "Spanish punctuation",
            "text",
            "¿Vienes mañana? ¡Claro que sí! Dijo: «ya está listo»; luego se fue. "
            "¿Cuántos? Tres, quizá cuatro. ¡No lo sabía! ¿De verdad? Sí: seguro. "
            "Uno, dos, tres; después, el resto. ¿Y tú? ¡Ánimo!",
            focus=["¿", "¡", ";", ":", "?", "!"],
        ),
        lesson(
            "t06l4",
            "Mixed prose with punctuation",
            "text",
            "Cuando escribes sin mirar, la atención se libera: ya no vigilas los "
            "dedos, sino las ideas. Y esa es la diferencia real entre teclear y "
            "escribir; entre operar una máquina y pensar con ella. ¿Vale la pena? "
            "Sin duda: es la inversión de tiempo más rentable que conozco.",
        ),
        lesson(
            "t06l5",
            "Underscores and identifiers",
            "code",
            "user_id max_retries http_client parse_json default_port read_file "
            "is_valid total_count data_frame to_string min_value api_key base_url "
            "on_click handle_error cache_ttl build_index next_token load_config "
            "__init__ __name__ __main__ _private snake_case",
            "`_` is `Shift`+`-`, right pinky. In Python you will type it constantly.",
            focus=["_"],
        ),
    ],
    links=[
        {
            "track": "python",
            "level": "p01",
            "note": "snake_case for variables, PascalCase for classes, SCREAMING_CASE for constants — you just drilled all three.",
        }
    ],
)

# ---- Level 7: numbers ---------------------------------------------------
level(
    7,
    "t07",
    "Number Row",
    "Numbers without leaving home position.",
    """The number row is a long reach, and it is where touch typing usually breaks
down. Standard finger assignment:

```
1  2  3  4  5     6  7  8  9  0  '  ¡
4  3  2  1  1     1  1  2  3  4  4  4
```

Left index covers `4` and `5`; right index covers `6` and `7`. The right pinky
gets `0`, `'` and `¡` — it is doing a lot of work, which is why it needs its own
drill.

With `Shift` the same row gives you `! " · $ % & / ( ) = ? ¿`. Note where the
parentheses live: **`(` is `Shift`+`8`, `)` is `Shift`+`9`** — a reach every
programmer on a Spanish layout makes thousands of times a day.""",
    30,
    0.95,
    [
        lesson("t07l1", "Index numbers: 4 5 6 7", "keys", bigrams("4567", "t07l1", 16, 4, 3), focus=list("4567")),
        lesson("t07l2", "Middle and ring: 3 8 2 9", "keys", bigrams("3829", "t07l2", 16, 4, 3), focus=list("3829")),
        lesson("t07l3", "Pinky: 1 0 ' ¡", "keys", bigrams("10'¡", "t07l3", 16, 4, 3), focus=["1", "0", "'", "¡"]),
        lesson(
            "t07l4",
            "Realistic numbers",
            "code",
            "2026 3.14159 1024 0.001 42 100000 0755 8080 127.0.0.1 "
            "1_000_000 0xFF 3e8 2.71828 65535 1440 0b1011 9.81 "
            "192.168.1.1 2026-09-12 v1.2.3 10**9 1e-6",
        ),
        lesson(
            "t07l5",
            "Parentheses and shifted digits",
            "code",
            "(1) (2, 3) f(x) g(a, b) 50% $100 &&  ¿? !=  ((()))  "
            "(a) (b) (c) sum(xs) len(s) max(a, b) round(x, 2) "
            "print() range(10) zip(a, b) dict()",
            "`(` = Shift+8, `)` = Shift+9. Drill them until the pair is one motion.",
            focus=["(", ")"],
        ),
        lesson(
            "t07l6",
            "Numbers in prose",
            "text",
            "En 2026 el equipo procesó 14.320 operaciones, un 27% más que en 2025, "
            "con un tiempo medio de 3,4 días y un margen de error del 0,8%. "
            "El pico se registró el 12 de septiembre: 1.204 en una sola jornada.",
        ),
    ],
)

# ---- Level 8: AltGr essentials ------------------------------------------
level(
    8,
    "t08",
    "AltGr: the Programmer's Row",
    "@ # ~ € | ¬ \\ — the characters a Spanish layout hides.",
    """This is the level that separates "I can type Spanish" from "I can type code
on a Spanish keyboard". **AltGr** is the right Alt key. Hold it with your right
thumb and strike the number row with the correct finger — do not press AltGr
with a finger and then hunt with the same hand.

| Char | Keystroke | Finger |
|---|---|---|
| `\\` | `AltGr` + `º` | left pinky |
| `\\|` | `AltGr` + `1` | left pinky |
| `@` | `AltGr` + `2` | left ring |
| `#` | `AltGr` + `3` | left middle |
| `~` | `AltGr` + `4` | left index |
| `€` | `AltGr` + `5` | left index |
| `¬` | `AltGr` + `6` | right index |

`~` is a **dead key** on some macOS Spanish layouts: press `AltGr`+`4` then
`Space` to get a bare `~`. Try it once now and note which behaviour your machine
has — it matters for shell paths and Python's `~` in `pathlib`.""",
    26,
    0.94,
    [
        lesson("t08l1", "at and hash", "keys", " ".join(["@@@", "###", "@#@", "#@#", "@#", "#@"] * 8), focus=["@", "#"]),
        lesson("t08l2", "pipe and backslash", "keys", " ".join(["|||", "\\\\\\", "|\\|", "\\|\\", "|\\", "\\|"] * 8), focus=["|", "\\"]),
        lesson("t08l3", "tilde and euro", "keys", " ".join(["~~~", "€€€", "~€~", "€~€", "~€", "€~"] * 8), focus=["~", "€"]),
        lesson(
            "t08l4",
            "Emails, decorators, paths",
            "code",
            "marco@example.com  @property  @staticmethod  @dataclass  "
            "~/proyectosweb  ~/.config/nvim  C:\\Users\\marco  "
            "# TODO  # noqa  #!/usr/bin/env python3  "
            "a | b  x |= y  cat f | grep x  Optional[int] | None",
            "Python decorators, shell pipes, home paths and comments — all AltGr.",
        ),
        lesson(
            "t08l5",
            "Shell one-liners",
            "code",
            "ls -la | grep .py\n"
            "cat ~/.zshrc | tail -20\n"
            "find . -name '*.json' | wc -l\n"
            "python3 -m http.server 8080\n"
            "grep -rn 'TODO' ~/proyectosweb | head\n"
            "echo $HOME && cd ~/ && pwd",
        ),
    ],
    links=[
        {"track": "python", "level": "p07", "note": "@decorator syntax needs AltGr+2 — you will type it a lot in Level 7 of Python."},
        {"track": "nvim", "level": "v09", "note": "Vim's :! shell escapes and | command chaining use these same keys."},
    ],
)

# ---- Level 9: brackets and braces ---------------------------------------
level(
    9,
    "t09",
    "Brackets & Braces",
    "[ ] { } < > — the four hardest characters on a Spanish layout.",
    """On a US keyboard these are single keys. On ES QWERTY they are AltGr combos,
and they are *everywhere* in code. This level exists because this is the single
biggest speed tax a Spanish-layout programmer pays.

| Char | Keystroke | Note |
|---|---|---|
| `[` | `AltGr` + `` ` `` | the key right of `P` |
| `]` | `AltGr` + `+` | right of `` ` `` |
| `{` | `AltGr` + `´` | the key right of `Ñ` |
| `}` | `AltGr` + `ç` | right of `´` |
| `<` | plain key, left of `Z` | left pinky |
| `>` | `Shift` + `<` | |

All four AltGr brackets are on the **right pinky column**. Hold AltGr with the
right thumb, strike with the right pinky, release. One motion, not three.

Learn the *pairs* as units: `[]` `{}` `()` `<>`. Your editor auto-closes them,
but your fingers still need to know the shape.""",
    24,
    0.94,
    [
        lesson("t09l1", "square brackets", "keys", " ".join(["[[[", "]]]", "[]", "[][]", "[ ]", "[]["] * 9), focus=["[", "]"]),
        lesson("t09l2", "curly braces", "keys", " ".join(["{{{", "}}}", "{}", "{}{}", "{ }", "}{}"] * 9), focus=["{", "}"]),
        lesson("t09l3", "angle brackets", "keys", " ".join(["<<<", ">>>", "<>", "<><>", "-> ", "=>", "<="] * 8), focus=["<", ">"]),
        lesson(
            "t09l4",
            "All four pairs",
            "keys",
            " ".join(["()", "[]", "{}", "<>", "([{", "}])", "([{}])", "<[{}]>"] * 8),
        ),
        lesson(
            "t09l5",
            "Python literals",
            "code",
            "xs = [1, 2, 3]\n"
            "d = {'a': 1, 'b': 2}\n"
            "s = {1, 2, 3}\n"
            "t = (1,)\n"
            "m = [[0] * 3 for _ in range(3)]\n"
            "cfg = {'host': 'localhost', 'port': 8080, 'tags': ['a', 'b']}\n"
            "def f(xs: list[int]) -> dict[str, int]: ...",
        ),
        lesson(
            "t09l6",
            "Comprehensions",
            "code",
            "[x**2 for x in range(10)]\n"
            "[x for x in xs if x > 0]\n"
            "{k: v for k, v in pairs}\n"
            "{c for c in word}\n"
            "[(i, x) for i, x in enumerate(xs)]\n"
            "[y for row in grid for y in row]",
        ),
    ],
    links=[
        {"track": "python", "level": "p03", "note": "Every collection literal in Python lives behind these AltGr combos."},
        {"track": "nvim", "level": "v06", "note": "Vim text objects i[ a{ i( operate on exactly these pairs."},
    ],
)

# ---- Level 10: code symbols in context ----------------------------------
level(
    10,
    "t10",
    "Code Symbols in Context",
    "Operators, comparisons and the punctuation of real programs.",
    """Individual symbols are easy; *sequences* are what slow you down. `!=`, `->`,
`:=`, `**`, `//`, `==`, `>=` are two-keystroke units and should be trained as
units, the same way you trained `fj`.

Watch for the ones that switch hands mid-symbol — `->` is right-pinky `Shift` +
left-bottom `-` then `Shift` + `<`. Those are the expensive ones.""",
    28,
    0.95,
    [
        lesson(
            "t10l1",
            "Comparison operators",
            "code",
            " ".join(["==", "!=", "<=", ">=", "<", ">", "is", "is not", "in", "not in"] * 6),
        ),
        lesson(
            "t10l2",
            "Arithmetic and assignment",
            "code",
            " ".join(["+", "-", "*", "/", "//", "%", "**", "+=", "-=", "*=", "/=", "//=", "**=", ":="] * 4),
        ),
        lesson(
            "t10l3",
            "Type annotations",
            "code",
            "def parse(raw: str) -> dict[str, int]:\n"
            "def load(path: Path, *, strict: bool = False) -> list[Row]:\n"
            "x: int | None = None\n"
            "Handler = Callable[[Event], Awaitable[None]]\n"
            "items: dict[str, list[tuple[int, str]]] = {}",
        ),
        lesson(
            "t10l4",
            "A whole function",
            "code",
            "def summarize(rows: list[dict[str, float]]) -> dict[str, float]:\n"
            "    total = sum(r['amount'] for r in rows)\n"
            "    n = len(rows)\n"
            "    return {\n"
            "        'total': total,\n"
            "        'mean': total / n if n else 0.0,\n"
            "        'max': max((r['amount'] for r in rows), default=0.0),\n"
            "    }",
            "Indentation counts. Four spaces, typed as four spaces.",
        ),
        lesson(
            "t10l5",
            "Vim command lines",
            "code",
            ":%s/old/new/g\n"
            ":g/TODO/d\n"
            ":e ~/.config/nvim/init.lua\n"
            ":vsplit | wincmd l\n"
            ":set number relativenumber\n"
            ":'<,'>normal A;\n"
            ":bufdo %s/foo/bar/ge | update",
            "Ex commands are their own typing dialect. Get fluent with `:%s/.../.../g`.",
        ),
    ],
    links=[
        {"track": "nvim", "level": "v10", "note": "Level 10 of the Vim track is exactly these ex commands, executed."},
        {"track": "python", "level": "p08", "note": "Type annotations get their own Python level."},
    ],
)

# ---- Level 11: interconnected speed -------------------------------------
level(
    11,
    "t11",
    "Combined Speed: Code + Commands",
    "Full-speed runs on the material of the other two tracks.",
    """No new keys. This level is pure transfer: everything you type here is a real
Python snippet or a real Neovim sequence. If a passage feels slow, that is a
signal about which *concept* is still unfamiliar, not just which key.

Target: 40+ wpm on prose-like code, 96% accuracy. Code wpm is always lower than
prose wpm — a 60 wpm prose typist typically manages 35–40 on code, and that is
normal.""",
    38,
    0.96,
    [
        lesson(
            "t11l1",
            "Dataclasses",
            "code",
            "from dataclasses import dataclass, field\n\n"
            "@dataclass(frozen=True, slots=True)\n"
            "class Trade:\n"
            "    ref: str\n"
            "    amount: float\n"
            "    currency: str = 'EUR'\n"
            "    tags: list[str] = field(default_factory=list)\n\n"
            "    def notional(self, fx: float = 1.0) -> float:\n"
            "        return self.amount * fx",
        ),
        lesson(
            "t11l2",
            "Comprehensions and generators",
            "code",
            "squares = [n * n for n in range(20) if n % 3]\n"
            "index = {row['id']: row for row in rows}\n"
            "total = sum(t.amount for t in trades if t.currency == 'EUR')\n"
            "pairs = list(zip(keys, values, strict=True))\n"
            "flat = [x for chunk in chunks for x in chunk]",
        ),
        lesson(
            "t11l3",
            "Neovim normal-mode sequences",
            "code",
            "ciw  daw  yi(  ca{  di\"  vi]  gUiw  guu  >ip  =ap  "
            "0d$  dG  ggVG  ct,  yyp  ddp  xp  J  gJ  "
            "2dd  3yy  d2w  c3l  100G  \"ayy  \"ap  qa...q  @a  10@a",
            "Type them as text now; execute them for real in the Vim track.",
        ),
        lesson(
            "t11l4",
            "Error handling",
            "code",
            "try:\n"
            "    payload = json.loads(raw)\n"
            "except json.JSONDecodeError as exc:\n"
            "    logger.warning('bad payload: %s', exc)\n"
            "    raise ValueError(f'cannot parse {path!r}') from exc\n"
            "else:\n"
            "    return payload\n"
            "finally:\n"
            "    handle.close()",
        ),
        lesson(
            "t11l5",
            "Async",
            "code",
            "async def fetch_all(urls: list[str]) -> list[bytes]:\n"
            "    async with httpx.AsyncClient(timeout=10.0) as client:\n"
            "        tasks = [client.get(u) for u in urls]\n"
            "        responses = await asyncio.gather(*tasks, return_exceptions=True)\n"
            "    return [r.content for r in responses if not isinstance(r, Exception)]",
        ),
        lesson(
            "t11l6",
            "Lua config for Neovim",
            "code",
            "vim.opt.number = true\n"
            "vim.opt.relativenumber = true\n"
            "vim.g.mapleader = ' '\n"
            "vim.keymap.set('n', '<leader>w', '<cmd>write<cr>', { desc = 'Save' })\n"
            "vim.keymap.set('n', '<leader>ff', require('telescope.builtin').find_files)\n"
            "vim.api.nvim_create_autocmd('TextYankPost', {\n"
            "  callback = function() vim.highlight.on_yank() end,\n"
            "})",
        ),
    ],
    links=[
        {"track": "nvim", "level": "v12", "note": "Configuring Neovim in Lua is the Vim track's final level."},
        {"track": "python", "level": "p09", "note": "async/await is Python Level 9."},
    ],
)

# ---- Level 12: expert ---------------------------------------------------
level(
    12,
    "t12",
    "Expert: Sustained Accuracy",
    "Long runs, mixed material, no warm-up. 50+ wpm at 97%.",
    """Expert typing is not about peak speed on a short burst; it is about the
*absence of collapse* over a long passage. The metric that matters is
consistency: your slowest 10 seconds should be within 20% of your fastest.

Three habits at this level:

1. **Read ahead.** Your eyes should be 4–8 characters in front of your fingers.
2. **Chunk.** Common words (`return`, `self`, `import`, `function`) are single
   motor programs, not letter sequences.
3. **Never backspace-storm.** One error, one correction. If you are correcting
   in bursts you are typing above your control speed — slow down 10%.""",
    50,
    0.97,
    [
        lesson(
            "t12l1",
            "Mixed prose sprint",
            "text",
            "There is a particular kind of fluency that only arrives after the "
            "mechanics disappear. You stop noticing the keyboard, then you stop "
            "noticing the editor, and eventually the only thing left in your "
            "attention is the problem itself. Getting there is unglamorous: it is "
            "the same drills, done attentively, for longer than feels reasonable. "
            "But the payoff compounds every single day you sit down to work, and "
            "it never depreciates.",
        ),
        lesson(
            "t12l2",
            "Long code passage",
            "code",
            "import asyncio\n"
            "from collections import defaultdict\n"
            "from dataclasses import dataclass\n"
            "from typing import Iterable, Iterator\n\n\n"
            "@dataclass(slots=True)\n"
            "class Node:\n"
            "    key: str\n"
            "    children: list['Node']\n\n"
            "    def walk(self) -> Iterator['Node']:\n"
            "        yield self\n"
            "        for child in self.children:\n"
            "            yield from child.walk()\n\n\n"
            "def group_by_depth(root: Node) -> dict[int, list[str]]:\n"
            "    out: dict[int, list[str]] = defaultdict(list)\n"
            "    stack: list[tuple[Node, int]] = [(root, 0)]\n"
            "    while stack:\n"
            "        node, depth = stack.pop()\n"
            "        out[depth].append(node.key)\n"
            "        stack.extend((c, depth + 1) for c in node.children)\n"
            "    return dict(out)",
        ),
        lesson(
            "t12l3",
            "Spanish technical prose",
            "text",
            "El cuello de botella de casi cualquier flujo de trabajo técnico no está "
            "en la máquina, sino en la interfaz entre la persona y la máquina. "
            "Optimizar el código antes de optimizar esa interfaz es, en la mayoría "
            "de los casos, resolver el problema equivocado: ganas milisegundos de "
            "ejecución y pierdes horas de edición. La proporción correcta es la "
            "inversa, y casi nadie la aplica.",
        ),
        lesson(
            "t12l4",
            "Symbol-dense sprint",
            "code",
            "cfg = {'db': {'host': '127.0.0.1', 'port': 5432}, 'retries': 3}\n"
            "url = f\"postgres://{u}:{p}@{h}:{port}/{db}?sslmode=require\"\n"
            "pat = re.compile(r'^\\s*(\\w+)\\s*=\\s*\"([^\"]*)\"\\s*$')\n"
            "out = [(k, v) for k, v in cfg.items() if not k.startswith('_')]\n"
            "fn: Callable[[int, str], tuple[bool, str | None]] = handler\n"
            "assert xs[-1] == ys[0] != zs[1:3][0], f'{xs!r} vs {ys!r}'",
        ),
        lesson(
            "t12l5",
            "Everything at once",
            "code",
            "-- Neovim: format on save for Python only\n"
            "vim.api.nvim_create_autocmd('BufWritePre', {\n"
            "  pattern = '*.py',\n"
            "  callback = function(args)\n"
            "    vim.lsp.buf.format({ bufnr = args.buf, timeout_ms = 2000 })\n"
            "  end,\n"
            "})\n"
            "\n"
            "# then in the shell:\n"
            "python3 -m pytest -q --maxfail=1 && git commit -am 'fmt' && git push\n"
            "\n"
            ":%s/\\<print(/logger.debug(/g | update | source ~/.config/nvim/init.lua",
        ),
    ],
)

# ---------------------------------------------------------------- write

doc = {
    "track": "typing",
    "title": "Touch Typing",
    "subtitle": "ES QWERTY (Spain) · from home row to code at speed",
    "icon": "keyboard",
    "layout": "es",
    "levels": L,
}

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(doc, fh, ensure_ascii=False, indent=1)
    fh.write("\n")

n_lessons = sum(len(lv["lessons"]) for lv in L)
print(f"typing.json: {len(L)} levels, {n_lessons} lessons")
