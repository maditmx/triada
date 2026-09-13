//! ES QWERTY (Spain) layout knowledge — port of cli/triada/keyboard.py.

use std::collections::HashMap;
use std::sync::OnceLock;

// (primary, shifted, altgr, finger)
type Key = (&'static str, &'static str, &'static str, u8);

pub const KB: &[&[Key]] = &[
    &[
        ("º", "ª", "\\", 4), ("1", "!", "|", 4), ("2", "\"", "@", 3), ("3", "·", "#", 2),
        ("4", "$", "~", 1), ("5", "%", "€", 1), ("6", "&", "¬", 1), ("7", "/", "", 1),
        ("8", "(", "", 2), ("9", ")", "", 3), ("0", "=", "", 4), ("'", "?", "", 4),
        ("¡", "¿", "", 4),
    ],
    &[
        ("q", "Q", "", 4), ("w", "W", "", 3), ("e", "E", "", 2), ("r", "R", "", 1),
        ("t", "T", "", 1), ("y", "Y", "", 1), ("u", "U", "", 1), ("i", "I", "", 2),
        ("o", "O", "", 3), ("p", "P", "", 4), ("`", "^", "[", 4), ("+", "*", "]", 4),
    ],
    &[
        ("a", "A", "", 4), ("s", "S", "", 3), ("d", "D", "", 2), ("f", "F", "", 1),
        ("g", "G", "", 1), ("h", "H", "", 1), ("j", "J", "", 1), ("k", "K", "", 2),
        ("l", "L", "", 3), ("ñ", "Ñ", "", 4), ("´", "¨", "{", 4), ("ç", "Ç", "}", 4),
    ],
    &[
        ("<", ">", "", 4), ("z", "Z", "", 4), ("x", "X", "", 3), ("c", "C", "", 2),
        ("v", "V", "", 1), ("b", "B", "", 1), ("n", "N", "", 1), ("m", "M", "", 2),
        (",", ";", "", 3), (".", ":", "", 4), ("-", "_", "", 4),
    ],
];

fn dead_keys() -> &'static HashMap<char, (char, char)> {
    static MAP: OnceLock<HashMap<char, (char, char)>> = OnceLock::new();
    MAP.get_or_init(|| {
        let mut m = HashMap::new();
        for (acc, dead, base) in [
            ('á', '´', 'a'), ('é', '´', 'e'), ('í', '´', 'i'), ('ó', '´', 'o'), ('ú', '´', 'u'),
            ('Á', '´', 'A'), ('É', '´', 'E'), ('Í', '´', 'I'), ('Ó', '´', 'O'), ('Ú', '´', 'U'),
            ('ü', '¨', 'u'), ('Ü', '¨', 'U'), ('à', '`', 'a'), ('è', '`', 'e'),
        ] {
            m.insert(acc, (dead, base));
        }
        m
    })
}

#[derive(Clone, Copy)]
struct Loc {
    row: usize,
    col: usize,
    modifier: &'static str, // "" | "Shift" | "AltGr"
}

fn index_map() -> &'static HashMap<char, Loc> {
    static MAP: OnceLock<HashMap<char, Loc>> = OnceLock::new();
    MAP.get_or_init(|| {
        let mut m = HashMap::new();
        for (r, row) in KB.iter().enumerate() {
            for (c, k) in row.iter().enumerate() {
                if !k.0.is_empty() {
                    if let Some(ch) = k.0.chars().next() {
                        m.entry(ch).or_insert(Loc { row: r, col: c, modifier: "" });
                    }
                }
                if !k.1.is_empty() {
                    if let Some(ch) = k.1.chars().next() {
                        m.entry(ch).or_insert(Loc { row: r, col: c, modifier: "Shift" });
                    }
                }
                if !k.2.is_empty() {
                    if let Some(ch) = k.2.chars().next() {
                        m.entry(ch).or_insert(Loc { row: r, col: c, modifier: "AltGr" });
                    }
                }
            }
        }
        m
    })
}

fn finger_name(f: u8) -> &'static str {
    match f {
        1 => "index",
        2 => "middle",
        3 => "ring",
        _ => "pinky",
    }
}

pub fn key_hint(ch: char) -> String {
    if ch == ' ' {
        return "space bar — thumb".to_string();
    }
    if ch == '\n' {
        return "Enter — right pinky".to_string();
    }
    if let Some(&(dead, base)) = dead_keys().get(&ch) {
        let modf = index_map().get(&dead).map(|l| l.modifier).unwrap_or("");
        let mod_prefix = if modf == "Shift" { "Shift + " } else { "" };
        return format!("dead key {}{}, then {}", mod_prefix, dead, base);
    }
    let loc = match index_map().get(&ch) {
        Some(l) => *l,
        None => return String::new(),
    };
    let key = KB[loc.row][loc.col];
    let hand = if loc.col < KB[loc.row].len() / 2 { "left" } else { "right" };
    let finger = finger_name(key.3);
    let prefix = if !loc.modifier.is_empty() { format!("{} + ", loc.modifier) } else { String::new() };
    format!("{}{}   ({} {})", prefix, key.0, hand, finger)
}
