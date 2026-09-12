"""ES QWERTY (Spain) layout knowledge, shared by the CLI drills.

Mirrors the KB table in web/app.js.
"""
from __future__ import annotations

# rows of (primary, shifted, altgr, finger)
KB = [
    [("º", "ª", "\\", 4), ("1", "!", "|", 4), ("2", '"', "@", 3), ("3", "·", "#", 2),
     ("4", "$", "~", 1), ("5", "%", "€", 1), ("6", "&", "¬", 1), ("7", "/", "", 1),
     ("8", "(", "", 2), ("9", ")", "", 3), ("0", "=", "", 4), ("'", "?", "", 4),
     ("¡", "¿", "", 4)],
    [("q", "Q", "", 4), ("w", "W", "", 3), ("e", "E", "", 2), ("r", "R", "", 1),
     ("t", "T", "", 1), ("y", "Y", "", 1), ("u", "U", "", 1), ("i", "I", "", 2),
     ("o", "O", "", 3), ("p", "P", "", 4), ("`", "^", "[", 4), ("+", "*", "]", 4)],
    [("a", "A", "", 4), ("s", "S", "", 3), ("d", "D", "", 2), ("f", "F", "", 1),
     ("g", "G", "", 1), ("h", "H", "", 1), ("j", "J", "", 1), ("k", "K", "", 2),
     ("l", "L", "", 3), ("ñ", "Ñ", "", 4), ("´", "¨", "{", 4), ("ç", "Ç", "}", 4)],
    [("<", ">", "", 4), ("z", "Z", "", 4), ("x", "X", "", 3), ("c", "C", "", 2),
     ("v", "V", "", 1), ("b", "B", "", 1), ("n", "N", "", 1), ("m", "M", "", 2),
     (",", ";", "", 3), (".", ":", "", 4), ("-", "_", "", 4)],
]

DEAD = {
    "á": ("´", "a"), "é": ("´", "e"), "í": ("´", "i"), "ó": ("´", "o"), "ú": ("´", "u"),
    "Á": ("´", "A"), "É": ("´", "E"), "Í": ("´", "I"), "Ó": ("´", "O"), "Ú": ("´", "U"),
    "ü": ("¨", "u"), "Ü": ("¨", "U"), "à": ("`", "a"), "è": ("`", "e"),
}

HANDS = {}
INDEX = {}
for _r, _row in enumerate(KB):
    for _c, _k in enumerate(_row):
        left = _c < len(_row) // 2
        if _k[0] and _k[0] not in INDEX:
            INDEX[_k[0]] = (_r, _c, "")
        if _k[1] and _k[1] not in INDEX:
            INDEX[_k[1]] = (_r, _c, "Shift")
        if _k[2] and _k[2] not in INDEX:
            INDEX[_k[2]] = (_r, _c, "AltGr")

FINGER_NAME = {1: "index", 2: "middle", 3: "ring", 4: "pinky"}


def key_hint(ch: str) -> str:
    if ch == " ":
        return "space bar — thumb"
    if ch == "\n":
        return "Enter — right pinky"
    if ch in DEAD:
        dead, base = DEAD[ch]
        mod = "Shift + " if INDEX.get(dead, ("", "", ""))[2] == "Shift" else ""
        return f"dead key {mod}{dead}, then {base}"
    pos = INDEX.get(ch)
    if not pos:
        return ""
    r, c, mod = pos
    key = KB[r][c]
    hand = "left" if c < len(KB[r]) // 2 else "right"
    finger = FINGER_NAME[key[3]]
    prefix = f"{mod} + " if mod else ""
    return f"{prefix}{key[0]}   ({hand} {finger})"
