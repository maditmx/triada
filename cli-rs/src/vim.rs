//! A compact but faithful Vim emulator — a port of cli/triada/vimengine.py.
//! Mirrors web/vimengine.js key for key; tests/vim_cases.json is run against it.

use regex::Regex;
use std::collections::HashMap;

fn is_word_char(c: char) -> bool {
    c.is_ascii_alphanumeric() || c == '_' || ((c as u32) >= 0xC0 && (c as u32) <= 0x24F)
}

fn char_class(c: char, big: bool) -> u8 {
    if c == ' ' || c == '\t' || c == '\n' {
        return 0;
    }
    if big {
        return 1;
    }
    if is_word_char(c) {
        1
    } else {
        2
    }
}

pub fn parse_keys(s: &str) -> Vec<char> {
    let chars: Vec<char> = s.chars().collect();
    let mut out = Vec::new();
    let mut i = 0;
    while i < chars.len() {
        if chars[i] == '<' {
            if let Some(rel) = chars[i..].iter().position(|&c| c == '>') {
                let j = i + rel;
                let tok: String = chars[i..=j].iter().collect();
                let low = tok.to_lowercase();
                let special = match low.as_str() {
                    "<esc>" => Some('\x1b'),
                    "<cr>" | "<enter>" => Some('\r'),
                    "<bs>" => Some('\x08'),
                    "<tab>" => Some('\t'),
                    "<space>" => Some(' '),
                    "<lt>" => Some('<'),
                    "<gt>" => Some('>'),
                    "<del>" => Some('\x7f'),
                    _ => None,
                };
                if let Some(ch) = special {
                    out.push(ch);
                    i = j + 1;
                    continue;
                }
                let lowc: Vec<char> = low.chars().collect();
                if lowc.len() == 5 && lowc[0] == '<' && lowc[1] == 'c' && lowc[2] == '-' && lowc[4] == '>' {
                    let ch = lowc[3];
                    if ch.is_ascii_lowercase() || ch == '[' {
                        let mapped = if ch == '[' {
                            '\x1b'
                        } else {
                            ((ch.to_ascii_uppercase() as u8).wrapping_sub(64)) as char
                        };
                        out.push(mapped);
                        i = j + 1;
                        continue;
                    }
                }
            }
        }
        out.push(chars[i]);
        i += 1;
    }
    out
}

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Mode {
    Normal,
    Insert,
    Visual,
    VLine,
    VBlock,
    Replace,
    Cmdline,
}

impl Mode {
    pub fn as_str(&self) -> &'static str {
        match self {
            Mode::Normal => "normal",
            Mode::Insert => "insert",
            Mode::Visual => "visual",
            Mode::VLine => "vline",
            Mode::VBlock => "vblock",
            Mode::Replace => "replace",
            Mode::Cmdline => "cmdline",
        }
    }
}

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
enum Kind {
    Excl,
    Incl,
    Line,
    ExclEmpty,
}

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum RegKind {
    Char,
    Line,
    Block,
    Macro,
}

enum Status {
    Done,
    Incomplete,
    Invalid,
}

enum MotionResult {
    Move((usize, usize), Kind),
    None,
    Incomplete,
}

pub type Pos = (usize, usize);

pub struct Vim {
    pub lines: Vec<Vec<char>>,
    pub row: usize,
    pub col: usize,
    pub mode: Mode,
    pub pending: Vec<char>,
    pub registers: HashMap<char, (String, RegKind)>,
    pub marks: HashMap<char, Pos>,
    undo_stack: Vec<(Vec<Vec<char>>, usize, usize)>,
    redo_stack: Vec<(Vec<Vec<char>>, usize, usize)>,
    pub message: String,
    pub cmdline: String,
    pub cmdtype: char,
    last_search: Option<(String, char)>,
    last_ft: Option<(char, char)>,
    last_change: Option<Vec<char>>,
    recording_change: Option<Vec<char>>,
    pub recording_reg: Option<char>,
    recorded: Vec<char>,
    last_macro: Option<char>,
    pub visual_start: Option<Pos>,
    desired_col: usize,
    pub typed: u32,
    pub written: bool,
    pub quit: bool,
    pub pending_str: String,
    depth: u32,
    pub failed: bool,
    block_insert: Option<(usize, usize, usize, bool)>,
    last_visual: Option<(Mode, Pos, Pos)>,
    op_pending: Option<(String, Option<char>, usize, usize)>,
}

const BIG_COL: usize = usize::MAX / 4;

impl Vim {
    pub fn new(lines: Vec<String>, cursor: (usize, usize)) -> Self {
        let lines = if lines.is_empty() {
            vec![Vec::new()]
        } else {
            lines.into_iter().map(|l| l.chars().collect()).collect()
        };
        Vim {
            lines,
            row: cursor.0,
            col: cursor.1,
            mode: Mode::Normal,
            pending: Vec::new(),
            registers: HashMap::new(),
            marks: HashMap::new(),
            undo_stack: Vec::new(),
            redo_stack: Vec::new(),
            message: String::new(),
            cmdline: String::new(),
            cmdtype: '\0',
            last_search: None,
            last_ft: None,
            last_change: None,
            recording_change: None,
            recording_reg: None,
            recorded: Vec::new(),
            last_macro: None,
            visual_start: None,
            desired_col: 0,
            typed: 0,
            written: false,
            quit: false,
            pending_str: String::new(),
            depth: 0,
            failed: false,
            block_insert: None,
            last_visual: None,
            op_pending: None,
        }
    }

    pub fn lines_as_strings(&self) -> Vec<String> {
        self.lines.iter().map(|l| l.iter().collect()).collect()
    }

    pub fn line(&self) -> Vec<char> {
        if self.row < self.lines.len() {
            self.lines[self.row].clone()
        } else {
            Vec::new()
        }
    }

    fn flat(&self) -> Vec<char> {
        let mut out = Vec::new();
        for (i, l) in self.lines.iter().enumerate() {
            if i > 0 {
                out.push('\n');
            }
            out.extend(l.iter().copied());
        }
        out
    }

    fn snapshot(&self) -> (Vec<Vec<char>>, usize, usize) {
        (self.lines.clone(), self.row, self.col)
    }

    fn push_undo(&mut self) {
        let snap = self.snapshot();
        if let Some(last) = self.undo_stack.last() {
            if last.0 == snap.0 {
                return;
            }
        }
        self.undo_stack.push(snap);
        self.redo_stack.clear();
    }

    fn undo(&mut self) {
        if self.undo_stack.is_empty() {
            self.message = "Already at oldest change".into();
            return;
        }
        let cur = self.snapshot();
        let (lines, r, c) = self.undo_stack.pop().unwrap();
        self.redo_stack.push(cur);
        self.lines = lines;
        self.row = r;
        self.col = c;
        self.clamp();
    }

    fn redo(&mut self) {
        if self.redo_stack.is_empty() {
            self.message = "Already at newest change".into();
            return;
        }
        let cur = self.snapshot();
        let (lines, r, c) = self.redo_stack.pop().unwrap();
        self.undo_stack.push(cur);
        self.lines = lines;
        self.row = r;
        self.col = c;
        self.clamp();
    }

    fn clamp(&mut self) {
        if self.lines.is_empty() {
            self.lines.push(Vec::new());
        }
        if self.row >= self.lines.len() {
            self.row = self.lines.len() - 1;
        }
        let extend = matches!(self.mode, Mode::Insert | Mode::Visual | Mode::VLine | Mode::VBlock);
        let linelen = self.lines[self.row].len();
        let maxc: i64 = linelen as i64 - if extend { 0 } else { 1 };
        let maxc = maxc.max(0) as usize;
        if self.col > maxc {
            self.col = maxc;
        }
    }

    pub fn to_index(&self, row: usize, col: usize) -> usize {
        let mut idx = 0;
        for l in &self.lines[..row.min(self.lines.len())] {
            idx += l.len() + 1;
        }
        idx + col
    }

    fn flat_len(&self) -> usize {
        if self.lines.is_empty() {
            return 0;
        }
        self.lines.iter().map(|l| l.len()).sum::<usize>() + self.lines.len() - 1
    }

    fn from_index(&self, idx: usize) -> Pos {
        let mut idx = idx.min(self.flat_len());
        let mut r = 0;
        while r < self.lines.len() && idx > self.lines[r].len() {
            idx -= self.lines[r].len() + 1;
            r += 1;
        }
        (r.min(self.lines.len().saturating_sub(1)), idx)
    }

    // ---------------------------------------------------------- feeding
    pub fn feed(&mut self, keys: &str) -> &mut Self {
        let ks = parse_keys(keys);
        for k in ks {
            self.key(k);
        }
        self
    }

    pub fn key(&mut self, k: char) {
        if self.depth == 0 {
            self.typed += 1;
        }
        if self.recording_reg.is_some() && !(k == 'q' && self.mode == Mode::Normal && self.pending.is_empty()) {
            self.recorded.push(k);
        }
        if let Some(rec) = self.recording_change.as_mut() {
            rec.push(k);
        }
        match self.mode {
            Mode::Insert => self.insert_key(k),
            Mode::Replace => self.replace_key(k),
            Mode::Cmdline => self.cmdline_key(k),
            _ => self.normal_key(k),
        }
    }

    // ------------------------------------------------------------- insert
    fn insert_key(&mut self, k: char) {
        if k == '\x1b' {
            self.mode = Mode::Normal;
            self.finish_block_insert();
            self.col = self.col.saturating_sub(1);
            self.end_change();
            self.clamp();
            return;
        }
        if k == '\x08' {
            if self.col > 0 {
                self.lines[self.row].remove(self.col - 1);
                self.col -= 1;
            } else if self.row > 0 {
                let cur = self.lines.remove(self.row);
                self.row -= 1;
                self.col = self.lines[self.row].len();
                self.lines[self.row].extend(cur);
            }
            return;
        }
        if k == '\r' {
            let line = self.lines[self.row].clone();
            let has_content = line.iter().any(|c| !c.is_whitespace());
            let indent: Vec<char> = if has_content {
                line.iter().take_while(|&&c| c == ' ' || c == '\t').copied().collect()
            } else {
                Vec::new()
            };
            let head: Vec<char> = line[..self.col.min(line.len())].to_vec();
            let tail: Vec<char> = line[self.col.min(line.len())..].to_vec();
            self.lines[self.row] = head;
            let mut newline = indent.clone();
            newline.extend(tail);
            self.lines.insert(self.row + 1, newline);
            self.row += 1;
            self.col = indent.len();
            return;
        }
        if k == '\t' {
            for _ in 0..4 {
                self.lines[self.row].insert(self.col, ' ');
                self.col += 1;
            }
            return;
        }
        if (k as u32) < 0x20 {
            return;
        }
        let at = self.col.min(self.lines[self.row].len());
        self.lines[self.row].insert(at, k);
        self.col += 1;
    }

    fn finish_block_insert(&mut self) {
        let (r1, r2, col, pad) = match self.block_insert.take() {
            Some(v) => v,
            None => return,
        };
        if self.row != r1 {
            return;
        }
        if col > self.lines[r1].len() || self.col < col {
            return;
        }
        let typed: Vec<char> = self.lines[r1][col..self.col].to_vec();
        if typed.is_empty() {
            return;
        }
        for r in (r1 + 1)..=r2 {
            if r >= self.lines.len() {
                break;
            }
            let linelen = self.lines[r].len();
            if linelen < col {
                if !pad {
                    continue;
                }
                let padding = col - linelen;
                self.lines[r].extend(std::iter::repeat(' ').take(padding));
            }
            let insert_at = col.min(self.lines[r].len());
            for (i, &c) in typed.iter().enumerate() {
                self.lines[r].insert(insert_at + i, c);
            }
        }
    }

    fn replace_key(&mut self, k: char) {
        if k == '\x1b' {
            self.mode = Mode::Normal;
            self.col = self.col.saturating_sub(1);
            self.end_change();
            return;
        }
        if k == '\r' {
            self.row += 1;
            self.col = 0;
            if self.row >= self.lines.len() {
                self.lines.push(Vec::new());
            }
            return;
        }
        let line = &mut self.lines[self.row];
        if self.col < line.len() {
            line[self.col] = k;
        } else {
            line.push(k);
        }
        self.col += 1;
    }

    fn cmdline_key(&mut self, k: char) {
        if k == '\x1b' {
            self.mode = Mode::Normal;
            self.cmdline.clear();
            return;
        }
        if k == '\x08' {
            if !self.cmdline.is_empty() {
                self.cmdline.pop();
            } else {
                self.mode = Mode::Normal;
            }
            return;
        }
        if k == '\r' {
            let cmd = std::mem::take(&mut self.cmdline);
            self.mode = Mode::Normal;
            if self.cmdtype == ':' {
                self.ex(&cmd);
            } else if let Some((op, reg, r0, c0)) = self.op_pending.take() {
                if !cmd.is_empty() {
                    self.last_search = Some((cmd.clone(), self.cmdtype));
                }
                let from = self.to_index(r0, c0);
                match self.search(&cmd, self.cmdtype, Some(from)) {
                    None => {
                        self.failed = true;
                        self.message = format!("E486: Pattern not found: {}", cmd);
                    }
                    Some(target) => {
                        let mut start = (r0, c0);
                        let mut end = target;
                        if self.to_index(start.0, start.1) > self.to_index(end.0, end.1) {
                            std::mem::swap(&mut start, &mut end);
                        }
                        self.apply_operator(&op, start, end, Kind::Excl, reg);
                    }
                }
            } else {
                self.do_search(&cmd, self.cmdtype);
            }
            return;
        }
        self.cmdline.push(k);
    }

    fn begin_change(&mut self, keys: Vec<char>) {
        self.recording_change = Some(keys);
    }

    fn end_change(&mut self) {
        if let Some(rc) = self.recording_change.take() {
            self.last_change = Some(rc);
        }
    }

    // ------------------------------------------------------------- normal
    fn normal_key(&mut self, k: char) {
        if k == '\x1b' {
            self.pending.clear();
            if matches!(self.mode, Mode::Visual | Mode::VLine | Mode::VBlock) {
                self.mode = Mode::Normal;
                self.visual_start = None;
                self.clamp();
            }
            return;
        }
        self.pending.push(k);
        let seq = self.pending.clone();
        let status = self.exec_normal(&seq);
        if matches!(status, Status::Done | Status::Invalid) {
            self.pending.clear();
        }
        self.pending_str = self.pending.iter().collect();
    }

    fn exec_normal(&mut self, seq: &[char]) -> Status {
        let mut i = 0;
        let mut reg: Option<char> = None;
        let mut count1 = String::new();
        loop {
            while i < seq.len() && seq[i].is_ascii_digit() && !(seq[i] == '0' && count1.is_empty()) {
                count1.push(seq[i]);
                i += 1;
            }
            if i < seq.len() && seq[i] == '"' {
                if i + 1 >= seq.len() {
                    return Status::Incomplete;
                }
                reg = Some(seq[i + 1]);
                i += 2;
                continue;
            }
            break;
        }
        if i >= seq.len() {
            return Status::Incomplete;
        }
        let n1 = if count1.is_empty() { None } else { count1.parse::<usize>().ok() };
        let rest = &seq[i..];
        self.command(rest, n1, reg)
    }

    fn command(&mut self, s: &[char], count: Option<usize>, reg: Option<char>) -> Status {
        let vis = matches!(self.mode, Mode::Visual | Mode::VLine | Mode::VBlock);
        let c = s[0];
        let mut op: Option<String> = None;
        let mut oprest: &[char] = &[];
        if "dcy><=".contains(c) {
            op = Some(c.to_string());
            oprest = &s[1..];
        } else if c == 'g' && s.len() >= 2 && "uU~?".contains(s[1]) {
            op = Some(format!("g{}", s[1]));
            oprest = &s[2..];
        } else if c == 'g' && s.len() == 1 {
            return Status::Incomplete;
        }

        if let Some(op) = op {
            if vis {
                return self.apply_operator_visual(&op, reg);
            }
            return self.operator_pending(&op, oprest, count, reg);
        }
        self.simple(s, count, reg, vis)
    }

    fn operator_pending(&mut self, op: &str, rest: &[char], count1: Option<usize>, reg: Option<char>) -> Status {
        if rest.is_empty() {
            return Status::Incomplete;
        }
        let mut i = 0;
        let mut count2 = String::new();
        while i < rest.len() && rest[i].is_ascii_digit() && !(rest[i] == '0' && count2.is_empty()) {
            count2.push(rest[i]);
            i += 1;
        }
        if i >= rest.len() {
            return Status::Incomplete;
        }
        let motion = &rest[i..];
        let n = count1.unwrap_or(1) * count2.parse::<usize>().unwrap_or(1);

        if motion[0] == '/' || motion[0] == '?' {
            self.op_pending = Some((op.to_string(), reg, self.row, self.col));
            self.mode = Mode::Cmdline;
            self.cmdtype = motion[0];
            self.cmdline = motion[1..].iter().collect();
            return Status::Done;
        }

        let op_last = op.chars().last().unwrap();
        let mut doubled = (motion.len() == 1 && motion[0] == op_last)
            || (op.chars().count() == 2 && motion.iter().collect::<String>() == op);
        if (op == ">" || op == "<" || op == "=") && motion.len() == 1 && motion[0] == op.chars().next().unwrap() {
            doubled = true;
        }
        if doubled {
            let r2 = (self.row + n - 1).min(self.lines.len() - 1);
            return self.apply_operator(op, (self.row, 0), (r2, 0), Kind::Line, reg);
        }

        if motion[0] == 'i' || motion[0] == 'a' {
            if motion.len() == 1 {
                return Status::Incomplete;
            }
            let rng = self.text_object(motion[0], motion[1], n);
            let (start, end, kind) = match rng {
                None => return Status::Done,
                Some(v) => v,
            };
            return self.apply_operator(op, start, end, kind, reg);
        }

        let res = self.motion(motion, n, true);
        match res {
            MotionResult::Incomplete => Status::Incomplete,
            MotionResult::None => Status::Done,
            MotionResult::Move(target, kind) => {
                let mut start = (self.row, self.col);
                let mut end = target;
                if self.to_index(start.0, start.1) > self.to_index(end.0, end.1) {
                    std::mem::swap(&mut start, &mut end);
                }
                self.apply_operator(op, start, end, kind, reg)
            }
        }
    }

    // ---- applying operators -------------------------------------------
    fn yank_text(&self, start: Pos, end: Pos, kind: Kind) -> String {
        if kind == Kind::Line {
            let mut s = String::new();
            for r in start.0..=end.0 {
                s.push_str(&self.lines[r].iter().collect::<String>());
                s.push('\n');
            }
            return s;
        }
        let flat = self.flat();
        let a = self.to_index(start.0, start.1);
        let mut b = self.to_index(end.0, end.1);
        if kind == Kind::Incl {
            b += 1;
        }
        let b = b.min(flat.len());
        let a = a.min(b);
        flat[a..b].iter().collect()
    }

    fn set_register(&mut self, reg: Option<char>, text: String, kind: RegKind) {
        if reg == Some('_') {
            return;
        }
        if let Some(r) = reg {
            if r.is_ascii_uppercase() {
                let key = r.to_ascii_lowercase();
                let mut newtext = self.registers.get(&key).map(|v| v.0.clone()).unwrap_or_default();
                newtext.push_str(&text);
                self.registers.insert(key, (newtext, kind));
            } else {
                self.registers.insert(r, (text, kind));
            }
        } else {
            self.registers.insert('"', (text.clone(), kind));
            self.registers.insert('0', (text, kind));
        }
    }

    fn get_register(&self, reg: Option<char>) -> (String, RegKind) {
        let key = reg.unwrap_or('"');
        self.registers.get(&key).cloned().unwrap_or((String::new(), RegKind::Char))
    }

    fn delete_range(&mut self, start: Pos, end: Pos, kind: Kind) {
        if kind == Kind::Line {
            self.lines.drain(start.0..=end.0);
            if self.lines.is_empty() {
                self.lines.push(Vec::new());
            }
            self.row = start.0.min(self.lines.len() - 1);
            self.col = self.first_nonblank(self.row);
        } else {
            let flat = self.flat();
            let a = self.to_index(start.0, start.1);
            let mut b = self.to_index(end.0, end.1);
            if kind == Kind::Incl {
                b += 1;
            }
            let b = b.min(flat.len());
            let a = a.min(b);
            let mut newflat: Vec<char> = flat[..a].to_vec();
            newflat.extend(flat[b..].iter().copied());
            self.set_lines_from_flat(&newflat);
            let pos = self.from_index(a);
            self.row = pos.0;
            self.col = pos.1;
        }
    }

    fn set_lines_from_flat(&mut self, flat: &[char]) {
        let s: String = flat.iter().collect();
        self.lines = s.split('\n').map(|p| p.chars().collect()).collect();
    }

    fn apply_operator(&mut self, op: &str, start: Pos, end: Pos, kind: Kind, reg: Option<char>) -> Status {
        if op == "y" {
            let txt = self.yank_text(start, end, kind);
            let rk = if kind == Kind::Line { RegKind::Line } else { RegKind::Char };
            self.set_register(reg, txt.clone(), rk);
            if reg != Some('_') {
                self.registers.insert('"', (txt, rk));
            }
            if kind == Kind::Line {
                self.row = start.0;
            } else {
                self.row = start.0;
                self.col = start.1;
            }
            self.clamp();
            return Status::Done;
        }

        self.push_undo();

        if op == ">" || op == "<" {
            for r in start.0..=end.0 {
                if op == ">" {
                    if !self.lines[r].is_empty() {
                        let mut newline = vec![' ', ' ', ' ', ' '];
                        newline.extend(self.lines[r].iter().copied());
                        self.lines[r] = newline;
                    }
                } else {
                    let mut n = 0;
                    while n < 4 && n < self.lines[r].len() && self.lines[r][n] == ' ' {
                        n += 1;
                    }
                    self.lines[r].drain(0..n);
                }
            }
            self.row = start.0;
            self.col = self.first_nonblank(self.row);
            self.register_dot();
            return Status::Done;
        }

        if op == "=" {
            self.row = start.0;
            self.clamp();
            return Status::Done;
        }

        if op == "gu" || op == "gU" || op == "g~" {
            let txt = self.yank_text(start, end, kind);
            let new: String = match op {
                "gu" => txt.to_lowercase(),
                "gU" => txt.to_uppercase(),
                _ => txt.chars().map(swapcase_char).collect(),
            };
            if kind == Kind::Line {
                let repl: Vec<Vec<char>> = new
                    .strip_suffix('\n')
                    .unwrap_or(&new)
                    .split('\n')
                    .map(|p| p.chars().collect())
                    .collect();
                self.lines.splice(start.0..=end.0, repl);
                self.row = start.0;
                self.col = self.first_nonblank(start.0);
            } else {
                let flat = self.flat();
                let a = self.to_index(start.0, start.1);
                let mut b = self.to_index(end.0, end.1);
                if kind == Kind::Incl {
                    b += 1;
                }
                let b = b.min(flat.len());
                let a = a.min(b);
                let mut newflat: Vec<char> = flat[..a].to_vec();
                newflat.extend(new.chars());
                newflat.extend(flat[b..].iter().copied());
                self.set_lines_from_flat(&newflat);
                self.row = start.0;
                self.col = start.1;
            }
            self.clamp();
            self.register_dot();
            return Status::Done;
        }

        let txt = self.yank_text(start, end, kind);
        let rk = if kind == Kind::Line { RegKind::Line } else { RegKind::Char };
        self.set_register(reg, txt, rk);

        if op == "d" {
            self.delete_range(start, end, kind);
            self.clamp();
            self.register_dot();
            return Status::Done;
        }

        // op == "c"
        if kind == Kind::Line {
            let indent: Vec<char> = self.lines[start.0]
                .iter()
                .take_while(|&&c| c == ' ' || c == '\t')
                .copied()
                .collect();
            self.lines.drain(start.0..=end.0);
            self.lines.insert(start.0, indent.clone());
            self.row = start.0;
            self.col = indent.len();
        } else {
            self.delete_range(start, end, kind);
        }
        self.mode = Mode::Insert;
        let pend = self.pending.clone();
        self.begin_change(pend);
        Status::Done
    }

    fn register_dot(&mut self) {
        self.last_change = Some(self.pending.clone());
    }

    // ---- visual --------------------------------------------------------
    pub fn visual_range(&self) -> (Pos, Pos) {
        let s = self.visual_start.unwrap_or((self.row, self.col));
        let e = (self.row, self.col);
        if self.to_index(s.0, s.1) > self.to_index(e.0, e.1) {
            (e, s)
        } else {
            (s, e)
        }
    }

    fn save_visual(&mut self) {
        if self.visual_start.is_some() {
            let (s, e) = self.visual_range();
            self.last_visual = Some((self.mode, s, e));
        }
    }

    fn apply_operator_visual(&mut self, op: &str, reg: Option<char>) -> Status {
        self.save_visual();
        let (s, e) = self.visual_range();
        let kind = if self.mode == Mode::VLine { Kind::Line } else { Kind::Incl };
        if self.mode == Mode::VBlock {
            return self.vblock_op(op, reg);
        }
        let mode_was = self.mode;
        self.mode = Mode::Normal;
        self.visual_start = None;
        if op == "c" && kind == Kind::Line {
            self.push_undo();
            let indent: Vec<char> = self.lines[s.0]
                .iter()
                .take_while(|&&c| c == ' ' || c == '\t')
                .copied()
                .collect();
            let txt = self.yank_text(s, e, Kind::Line);
            self.set_register(reg, txt, RegKind::Line);
            self.lines.drain(s.0..=e.0);
            self.lines.insert(s.0, indent.clone());
            self.row = s.0;
            self.col = indent.len();
            self.mode = Mode::Insert;
            self.begin_change(Vec::new());
            return Status::Done;
        }
        let res = self.apply_operator(op, s, e, kind, reg);
        let _ = mode_was;
        if self.mode != Mode::Insert {
            self.clamp();
        }
        res
    }

    pub fn vblock_cols(&self) -> (usize, usize, usize, usize) {
        let s = self.visual_start.unwrap_or((self.row, self.col));
        let e = (self.row, self.col);
        let (r1, r2) = if s.0 <= e.0 { (s.0, e.0) } else { (e.0, s.0) };
        let (c1, c2) = if s.1 <= e.1 { (s.1, e.1) } else { (e.1, s.1) };
        (r1, r2, c1, c2)
    }

    fn vblock_op(&mut self, op: &str, reg: Option<char>) -> Status {
        let (r1, r2, c1, c2) = self.vblock_cols();
        self.mode = Mode::Normal;
        self.visual_start = None;
        let chunks: Vec<String> = (r1..=r2)
            .map(|r| {
                let line = &self.lines[r];
                let end = (c2 + 1).min(line.len());
                let start = c1.min(line.len());
                line[start..end.max(start)].iter().collect()
            })
            .collect();
        self.set_register(reg, chunks.join("\n"), RegKind::Block);
        if op == "y" {
            self.row = r1;
            self.col = c1;
            self.clamp();
            return Status::Done;
        }
        self.push_undo();
        for r in r1..=r2 {
            let line = &mut self.lines[r];
            let end = (c2 + 1).min(line.len());
            let start = c1.min(line.len());
            if start < end {
                line.drain(start..end);
            }
        }
        self.row = r1;
        self.col = c1;
        if op == "c" {
            self.mode = Mode::Insert;
            self.block_insert = Some((r1, r2, c1, false));
            self.begin_change(Vec::new());
        }
        self.clamp();
        Status::Done
    }

    // ---- text objects --------------------------------------------------
    fn pair_for(obj: char) -> Option<(char, char)> {
        match obj {
            '(' | ')' | 'b' => Some(('(', ')')),
            '[' | ']' => Some(('[', ']')),
            '{' | '}' | 'B' => Some(('{', '}')),
            '<' | '>' => Some(('<', '>')),
            _ => None,
        }
    }

    fn text_object(&mut self, ia: char, obj: char, n: usize) -> Option<(Pos, Pos, Kind)> {
        let inner = ia == 'i';
        if obj == 'w' || obj == 'W' {
            return self.obj_word(inner, obj == 'W', n);
        }
        if let Some((o, c)) = Self::pair_for(obj) {
            return self.obj_pair(inner, o, c);
        }
        if obj == '"' || obj == '\'' || obj == '`' {
            return self.obj_quote(inner, obj);
        }
        if obj == 'p' {
            return Some(self.obj_para(inner));
        }
        None
    }

    fn obj_word(&self, inner: bool, big: bool, n: usize) -> Option<(Pos, Pos, Kind)> {
        let t = self.flat();
        let i = self.to_index(self.row, self.col);
        if i >= t.len() {
            return None;
        }
        let cls = char_class(t[i], big);
        let mut a = i;
        while a > 0 && t[a - 1] != '\n' && char_class(t[a - 1], big) == cls {
            a -= 1;
        }
        let mut b = i;
        while b + 1 < t.len() && t[b + 1] != '\n' && char_class(t[b + 1], big) == cls {
            b += 1;
        }
        for _ in 0..n.saturating_sub(1) {
            let j = b + 1;
            if j < t.len() && t[j] != '\n' {
                let cls2 = char_class(t[j], big);
                while b + 1 < t.len() && t[b + 1] != '\n' && char_class(t[b + 1], big) == cls2 {
                    b += 1;
                }
            }
        }
        if !inner {
            let mut e = b;
            let mut grew = false;
            while e + 1 < t.len() && (t[e + 1] == ' ' || t[e + 1] == '\t') {
                e += 1;
                grew = true;
            }
            if grew {
                b = e;
            } else {
                while a > 0 && (t[a - 1] == ' ' || t[a - 1] == '\t') {
                    a -= 1;
                }
            }
        }
        Some((self.from_index(a), self.from_index(b), Kind::Incl))
    }

    fn obj_pair(&self, inner: bool, o: char, c: char) -> Option<(Pos, Pos, Kind)> {
        let t = self.flat();
        let i = self.to_index(self.row, self.col);
        let mut depth = 0i64;
        let mut a: i64 = -1;
        if i < t.len() && t[i] == o {
            a = i as i64;
        } else {
            let mut j: i64 = i as i64;
            while j >= 0 {
                let ch = t[j as usize];
                if ch == c && j as usize != i {
                    depth += 1;
                } else if ch == o {
                    if depth == 0 {
                        a = j;
                        break;
                    }
                    depth -= 1;
                }
                j -= 1;
            }
        }
        if a < 0 {
            return None;
        }
        let a = a as usize;
        let mut depth = 0i64;
        let mut b: i64 = -1;
        let mut j = a + 1;
        while j < t.len() {
            if t[j] == o {
                depth += 1;
            } else if t[j] == c {
                if depth == 0 {
                    b = j as i64;
                    break;
                }
                depth -= 1;
            }
            j += 1;
        }
        if b < 0 {
            return None;
        }
        let b = b as usize;
        if inner {
            if a + 1 > b.wrapping_sub(1) || b == 0 {
                return Some((self.from_index(a + 1), self.from_index(a), Kind::ExclEmpty));
            }
            // Vim special case: open brace ends its line, close brace starts its own -> linewise
            let head = &t[a + 1..];
            let nl = head.iter().position(|&c| c == '\n');
            let tail_start = t[..b].iter().rposition(|&c| c == '\n');
            if let (Some(nl), Some(tail_start)) = (nl, tail_start) {
                let head_before_nl: String = head[..nl].iter().collect();
                let mid: String = t[tail_start + 1..b].iter().collect();
                if head_before_nl.trim().is_empty() && mid.trim().is_empty() {
                    let r1 = self.from_index(a + 1 + nl + 1).0;
                    let r2 = self.from_index(tail_start).0;
                    if r1 <= r2 {
                        return Some(((r1, 0), (r2, 0), Kind::Line));
                    }
                }
            }
            return Some((self.from_index(a + 1), self.from_index(b - 1), Kind::Incl));
        }
        Some((self.from_index(a), self.from_index(b), Kind::Incl))
    }

    fn obj_quote(&self, inner: bool, q: char) -> Option<(Pos, Pos, Kind)> {
        let line = self.line();
        let positions: Vec<usize> = line
            .iter()
            .enumerate()
            .filter(|&(i, &c)| c == q && (i == 0 || line[i - 1] != '\\'))
            .map(|(i, _)| i)
            .collect();
        if positions.len() < 2 {
            return None;
        }
        let mut k = 0;
        while k + 1 < positions.len() {
            let a = positions[k];
            let b = positions[k + 1];
            if self.col <= b {
                if inner {
                    if a + 1 > b.wrapping_sub(1) || b == 0 {
                        return Some(((self.row, a + 1), (self.row, a), Kind::ExclEmpty));
                    }
                    return Some(((self.row, a + 1), (self.row, b - 1), Kind::Incl));
                }
                return Some(((self.row, a), (self.row, b), Kind::Incl));
            }
            k += 2;
        }
        None
    }

    fn obj_para(&self, inner: bool) -> (Pos, Pos, Kind) {
        let r = self.row;
        let blank = |i: usize| self.lines[i].iter().all(|c| c.is_whitespace());
        let cur_blank = blank(r);
        let mut a = r;
        while a > 0 && blank(a - 1) == cur_blank {
            a -= 1;
        }
        let mut b = r;
        while b + 1 < self.lines.len() && blank(b + 1) == cur_blank {
            b += 1;
        }
        if !inner {
            let mut e = b;
            while e + 1 < self.lines.len() && blank(e + 1) != cur_blank {
                e += 1;
            }
            if e != b {
                b = e;
            }
        }
        ((a, 0), (b, 0), Kind::Line)
    }

    // ---- motions -------------------------------------------------------
    fn first_nonblank(&self, r: usize) -> usize {
        let line = &self.lines[r];
        if line.is_empty() {
            return 0;
        }
        let mut m = 0;
        while m < line.len() && (line[m] == ' ' || line[m] == '\t') {
            m += 1;
        }
        m.min(line.len() - 1)
    }

    fn motion(&mut self, m: &[char], n: usize, for_operator: bool) -> MotionResult {
        let c = m[0];
        let idx = self.to_index(self.row, self.col);

        match c {
            'h' => return MotionResult::Move((self.row, self.col.saturating_sub(n)), Kind::Excl),
            'l' => {
                let lim = if for_operator {
                    self.line().len()
                } else {
                    self.line().len().saturating_sub(1)
                };
                return MotionResult::Move((self.row, (self.col + n).min(lim)), Kind::Excl);
            }
            ' ' => {
                return MotionResult::Move((self.row, (self.col + n).min(self.line().len())), Kind::Excl);
            }
            'j' | 'k' => {
                let r = if c == 'j' {
                    self.row as i64 + n as i64
                } else {
                    self.row as i64 - n as i64
                };
                if r < 0 || r > (self.lines.len() as i64 - 1) {
                    self.failed = true;
                    return MotionResult::None;
                }
                let r = r.clamp(0, self.lines.len() as i64 - 1) as usize;
                let col = self.desired_col.max(self.col).min(self.lines[r].len().saturating_sub(1));
                return MotionResult::Move((r, col), Kind::Line);
            }
            '+' | '\r' => {
                let r = (self.row + n).min(self.lines.len() - 1);
                return MotionResult::Move((r, self.first_nonblank(r)), Kind::Line);
            }
            '-' => {
                let r = self.row.saturating_sub(n);
                return MotionResult::Move((r, self.first_nonblank(r)), Kind::Line);
            }
            '_' => {
                let r = (self.row + n - 1).min(self.lines.len() - 1);
                return MotionResult::Move((r, self.first_nonblank(r)), Kind::Line);
            }
            '0' => return MotionResult::Move((self.row, 0), Kind::Excl),
            '^' => return MotionResult::Move((self.row, self.first_nonblank(self.row)), Kind::Excl),
            '$' => {
                let r = (self.row + n - 1).min(self.lines.len() - 1);
                let l = self.lines[r].len();
                let c = if for_operator { l } else { l.saturating_sub(1) };
                return MotionResult::Move((r, c.max(0)), Kind::Incl);
            }
            'G' => {
                let is_bare_g = m.len() == 1;
                let r: i64 = if is_bare_g && n != 1 {
                    n as i64 - 1
                } else if n == 1 {
                    self.lines.len() as i64 - 1
                } else {
                    n as i64 - 1
                };
                let r = r.clamp(0, self.lines.len() as i64 - 1) as usize;
                return MotionResult::Move((r, self.first_nonblank(r)), Kind::Line);
            }
            'H' => return MotionResult::Move((0, self.first_nonblank(0)), Kind::Line),
            'L' => {
                let r = self.lines.len() - 1;
                return MotionResult::Move((r, self.first_nonblank(r)), Kind::Line);
            }
            'M' => {
                let r = self.lines.len() / 2;
                return MotionResult::Move((r, self.first_nonblank(r)), Kind::Line);
            }
            '|' => {
                let col = (n.saturating_sub(1)).min(self.line().len().saturating_sub(1));
                return MotionResult::Move((self.row, col), Kind::Excl);
            }
            'w' | 'W' => {
                let big = c == 'W';
                let t = self.flat();
                let mut i = idx;
                for _ in 0..n {
                    i = next_word_start(&t, i, big);
                }
                if for_operator && n >= 1 {
                    let (r0, _c0) = (self.row, self.col);
                    let (r1, _c1) = self.from_index(i);
                    if r1 > r0 && i > 0 && t[i - 1] == '\n' {
                        let mut k = i;
                        while k > 0 && (t[k - 1] == ' ' || t[k - 1] == '\t' || t[k - 1] == '\n') {
                            k -= 1;
                        }
                        if k > idx {
                            i = k;
                        }
                    }
                }
                return MotionResult::Move(self.from_index(i), Kind::Excl);
            }
            'b' | 'B' => {
                let t = self.flat();
                let mut i = idx;
                for _ in 0..n {
                    i = prev_word_start(&t, i, c == 'B');
                }
                return MotionResult::Move(self.from_index(i), Kind::Excl);
            }
            'e' | 'E' => {
                let t = self.flat();
                let mut i = idx;
                for _ in 0..n {
                    i = next_word_end(&t, i, c == 'E');
                }
                return MotionResult::Move(self.from_index(i), Kind::Incl);
            }
            'f' | 'F' | 't' | 'T' => {
                if m.len() < 2 {
                    return MotionResult::Incomplete;
                }
                let target = m[1];
                self.last_ft = Some((c, target));
                return self.do_ft(c, target, n, for_operator, false);
            }
            ';' | ',' => {
                let (mut k, target) = match self.last_ft {
                    None => return MotionResult::None,
                    Some(v) => v,
                };
                if c == ',' {
                    k = match k {
                        'f' => 'F',
                        'F' => 'f',
                        't' => 'T',
                        _ => 't',
                    };
                }
                return self.do_ft(k, target, n, for_operator, true);
            }
            '{' => return MotionResult::Move(self.para_move(-1, n), Kind::Excl),
            '}' => return MotionResult::Move(self.para_move(1, n), Kind::Excl),
            '%' => {
                return match self.match_pair() {
                    Some((p, k)) => MotionResult::Move(p, k),
                    None => MotionResult::None,
                };
            }
            '`' => {
                if m.len() < 2 {
                    return MotionResult::Incomplete;
                }
                return match self.marks.get(&m[1]) {
                    Some(&p) => MotionResult::Move(p, Kind::Excl),
                    None => MotionResult::None,
                };
            }
            '\'' => {
                if m.len() < 2 {
                    return MotionResult::Incomplete;
                }
                return match self.marks.get(&m[1]) {
                    Some(&p) => MotionResult::Move((p.0, self.first_nonblank(p.0)), Kind::Line),
                    None => MotionResult::None,
                };
            }
            'n' | 'N' => {
                let (pat, direction) = match &self.last_search {
                    None => {
                        self.failed = true;
                        return MotionResult::None;
                    }
                    Some(v) => v.clone(),
                };
                let d = if c == 'n' {
                    direction
                } else if direction == '/' {
                    '?'
                } else {
                    '/'
                };
                let p = self.search(&pat, d, None);
                if p.is_none() {
                    self.failed = true;
                }
                return match p {
                    Some(p) => MotionResult::Move(p, Kind::Excl),
                    None => MotionResult::None,
                };
            }
            '*' | '#' => {
                let word = self.word_under_cursor();
                if word.is_empty() {
                    self.failed = true;
                    return MotionResult::None;
                }
                let pat = format!("\\<{}\\>", regex::escape(&word));
                let dir = if c == '*' { '/' } else { '?' };
                self.last_search = Some((pat.clone(), dir));
                let p = self.search(&pat, dir, None);
                if p.is_none() {
                    self.failed = true;
                }
                return match p {
                    Some(p) => MotionResult::Move(p, Kind::Excl),
                    None => MotionResult::None,
                };
            }
            'g' => {
                let ms: String = m.iter().collect();
                if ms == "g" {
                    return MotionResult::Incomplete;
                }
                if ms == "gg" {
                    let r = (n.saturating_sub(1)).min(self.lines.len() - 1);
                    return MotionResult::Move((r, self.first_nonblank(r)), Kind::Line);
                }
                if ms == "g_" {
                    let line = self.line();
                    let trimmed_len = line.iter().rposition(|c| !c.is_whitespace()).map(|p| p + 1).unwrap_or(0);
                    let c = trimmed_len.saturating_sub(1);
                    return MotionResult::Move((self.row, c), Kind::Incl);
                }
                return MotionResult::None;
            }
            _ => return MotionResult::None,
        }
    }

    fn word_under_cursor(&self) -> String {
        let line = self.line();
        let mut i = self.col;
        while i < line.len() && !is_word_char(line[i]) {
            i += 1;
        }
        if i >= line.len() {
            return String::new();
        }
        let mut a = i;
        while a > 0 && is_word_char(line[a - 1]) {
            a -= 1;
        }
        let mut b = i;
        while b + 1 < line.len() && is_word_char(line[b + 1]) {
            b += 1;
        }
        line[a..=b].iter().collect()
    }

    fn do_ft(&mut self, kind: char, target: char, n: usize, _for_operator: bool, repeat: bool) -> MotionResult {
        let line = self.line();
        let col = self.col;
        if kind == 'f' || kind == 't' {
            let mut pos = col as i64;
            for i in 0..n {
                let mut start = pos + 1;
                if kind == 't' && repeat && n == 1 && i == 0 {
                    start = pos + 2;
                }
                let found = find_char_from(&line, target, start.max(0) as usize);
                match found {
                    None => {
                        self.failed = true;
                        return MotionResult::None;
                    }
                    Some(p) => pos = p as i64,
                }
            }
            if kind == 't' {
                pos -= 1;
            }
            MotionResult::Move((self.row, pos.max(0) as usize), Kind::Incl)
        } else {
            let mut pos = col as i64;
            for i in 0..n {
                let mut start = pos - 1;
                if kind == 'T' && repeat && n == 1 && i == 0 {
                    start = pos - 2;
                }
                let found = rfind_char_before(&line, target, (start + 1).max(0) as usize);
                match found {
                    None => {
                        self.failed = true;
                        return MotionResult::None;
                    }
                    Some(p) => pos = p as i64,
                }
            }
            if kind == 'T' {
                pos += 1;
            }
            MotionResult::Move((self.row, pos.max(0) as usize), Kind::Excl)
        }
    }

    fn para_move(&self, direction: i64, n: usize) -> Pos {
        let mut r: i64 = self.row as i64;
        for _ in 0..n {
            r += direction;
            while r > 0 && r < self.lines.len() as i64 - 1 && !self.lines[r as usize].iter().all(|c| c.is_whitespace()) {
                r += direction;
            }
            r = r.clamp(0, self.lines.len() as i64 - 1);
        }
        (r as usize, 0)
    }

    fn match_pair(&self) -> Option<(Pos, Kind)> {
        let line = self.line();
        let opens = "([{";
        let closes = ")]}";
        let mut i = self.col;
        while i < line.len() && !opens.contains(line[i]) && !closes.contains(line[i]) {
            i += 1;
        }
        if i >= line.len() {
            return None;
        }
        let ch = line[i];
        let t = self.flat();
        let idx = self.to_index(self.row, i);
        let (o, c, step): (char, char, i64) = if opens.contains(ch) {
            let pos = opens.find(ch).unwrap();
            (ch, closes.chars().nth(pos).unwrap(), 1)
        } else {
            let pos = closes.find(ch).unwrap();
            (opens.chars().nth(pos).unwrap(), ch, -1)
        };
        let mut depth = 0i64;
        let mut j: i64 = idx as i64;
        while j >= 0 && (j as usize) < t.len() {
            let cur = t[j as usize];
            if cur == (if step == 1 { o } else { c }) {
                depth += 1;
            } else if cur == (if step == 1 { c } else { o }) {
                depth -= 1;
                if depth == 0 {
                    return Some((self.from_index(j as usize), Kind::Incl));
                }
            }
            j += step;
        }
        None
    }

    // ---- search ---------------------------------------------------------
    fn search(&self, pat: &str, direction: char, from_pos: Option<usize>) -> Option<Pos> {
        let flat = self.flat();
        let s: String = flat.iter().collect();
        let re = Regex::new(&vim_re(pat)).ok()?;
        let start = from_pos.unwrap_or_else(|| self.to_index(self.row, self.col));
        let hits: Vec<usize> = re.find_iter(&s).map(|m| s[..m.start()].chars().count()).collect();
        if hits.is_empty() {
            return None;
        }
        if direction == '/' {
            match hits.iter().find(|&&h| h > start) {
                Some(&h) => Some(self.from_index(h)),
                None => Some(self.from_index(hits[0])),
            }
        } else {
            match hits.iter().rev().find(|&&h| h < start) {
                Some(&h) => Some(self.from_index(h)),
                None => Some(self.from_index(*hits.last().unwrap())),
            }
        }
    }

    fn do_search(&mut self, pat: &str, direction: char) {
        let (pat, direction) = if !pat.is_empty() {
            self.last_search = Some((pat.to_string(), direction));
            (pat.to_string(), direction)
        } else if let Some((p, _)) = self.last_search.clone() {
            (p, direction)
        } else {
            (pat.to_string(), direction)
        };
        match self.search(&pat, direction, None) {
            Some(p) => {
                self.row = p.0;
                self.col = p.1;
                self.clamp();
            }
            None => {
                self.message = format!("E486: Pattern not found: {}", pat);
            }
        }
    }

    // ---- ex commands -----------------------------------------------------
    fn resolve_range(&self, r: Option<&str>) -> (usize, usize) {
        match r {
            None => (self.row, self.row),
            Some("%") => (0, self.lines.len() - 1),
            Some("'<,'>") => {
                if self.visual_start.is_some() {
                    let (s, e) = self.visual_range();
                    (s.0, e.0)
                } else {
                    (self.row, self.row)
                }
            }
            Some(".,$") => (self.row, self.lines.len() - 1),
            Some(r) if r.contains(',') => {
                let mut parts = r.splitn(2, ',');
                let a = parts.next().unwrap();
                let b = parts.next().unwrap();
                if let Some(rest) = b.strip_prefix(".+") {
                    let n: usize = rest.parse().unwrap_or(0);
                    (self.row, (self.row + n).min(self.lines.len() - 1))
                } else {
                    let a: usize = a.parse().unwrap_or(1);
                    let b: usize = b.parse().unwrap_or(1);
                    (a.saturating_sub(1), b.saturating_sub(1))
                }
            }
            Some(r) => {
                let n: usize = r.parse().unwrap_or(1);
                (n.saturating_sub(1), n.saturating_sub(1))
            }
        }
    }

    fn ex(&mut self, cmd: &str) {
        let cmd = cmd.trim();
        if cmd.is_empty() {
            return;
        }
        let range_re = Regex::new(r"^(%|\d+,\d+|\.,\$|'<,'>|\.,\.\+\d+|\d+)(.*)$").unwrap();
        let (rng, body): (Option<String>, String) = match range_re.captures(cmd) {
            Some(caps) => (Some(caps[1].to_string()), caps[2].to_string()),
            None => (None, cmd.to_string()),
        };
        let body = body.trim().to_string();

        // :s substitute
        let s_re = Regex::new(r"^s([^A-Za-z0-9 ])(.*)$").unwrap();
        if let Some(caps) = s_re.captures(&body) {
            let sep = caps[1].chars().next().unwrap();
            let rest = &caps[2];
            let parts = split_unescaped(rest, sep);
            let pat = parts.get(0).cloned().unwrap_or_default();
            let rep = parts.get(1).cloned().unwrap_or_default();
            let flags = parts.get(2).cloned().unwrap_or_default();
            let (a, b) = self.resolve_range(rng.as_deref());
            self.push_undo();
            let mut count = 0usize;
            let rx = match Regex::new(&vim_re(&pat)) {
                Ok(r) => r,
                Err(_) => {
                    self.message = "E486: invalid pattern".into();
                    return;
                }
            };
            let replacement = vim_replacement(&rep);
            let global = flags.contains('g');
            for r in a..=(b.min(self.lines.len().saturating_sub(1))) {
                let line: String = self.lines[r].iter().collect();
                let n_matches = if global { rx.find_iter(&line).count() } else { usize::from(rx.is_match(&line)) };
                if n_matches > 0 {
                    let limit = if global { 0 } else { 1 };
                    let new = rx.replacen(&line, limit, replacement.as_str()).into_owned();
                    self.lines[r] = new.chars().collect();
                    count += n_matches;
                    self.row = r;
                }
            }
            self.message = if count > 0 {
                format!("{} substitution(s)", count)
            } else if flags.contains('e') {
                String::new()
            } else {
                format!("E486: Pattern not found: {}", pat)
            };
            self.clamp();
            return;
        }

        // :g/pat/cmd
        let g_re = Regex::new(r"^(g|v|global|vglobal)(!?)/(.*)$").unwrap();
        if let Some(caps) = g_re.captures(&body) {
            let invert = caps[1] == *"v" || caps[1] == *"vglobal" || &caps[2] == "!";
            let rest = &caps[3];
            let (pat, sub) = match split_unescaped_once(rest, '/') {
                (p, Some(s)) => (p, s),
                (p, None) => (p, "p".to_string()),
            };
            let (a, b) = self.resolve_range(Some(rng.as_deref().unwrap_or("%")));
            let rx = match Regex::new(&vim_re(&pat)) {
                Ok(r) => r,
                Err(_) => return,
            };
            self.push_undo();
            let targets: Vec<usize> = (a..=(b.min(self.lines.len().saturating_sub(1))))
                .filter(|&r| {
                    let line: String = self.lines[r].iter().collect();
                    rx.is_match(&line) != invert
                })
                .collect();
            let subtrim = sub.trim();
            if subtrim == "d" || subtrim == "delete" {
                for &r in targets.iter().rev() {
                    self.lines.remove(r);
                }
                if self.lines.is_empty() {
                    self.lines.push(Vec::new());
                }
            } else if sub.starts_with("normal ") || sub.starts_with("norm ") {
                let keys: String = sub.splitn(2, ' ').nth(1).unwrap_or("").to_string();
                for &r in targets.iter().rev() {
                    self.row = r;
                    self.col = 0;
                    self.run_normal(&keys);
                }
            } else if sub.starts_with('s') {
                for &r in &targets {
                    self.row = r;
                    let excmd = format!("{}{}", r + 1, sub);
                    self.ex(&excmd);
                }
            }
            self.clamp();
            return;
        }

        // :normal
        let n_re = Regex::new(r"^(normal|norm)!?\s+(.*)$").unwrap();
        if let Some(caps) = n_re.captures(&body) {
            let keys = caps[2].to_string();
            let (a, b) = if rng.is_some() { self.resolve_range(rng.as_deref()) } else { (self.row, self.row) };
            self.push_undo();
            for r in a..=(b.min(self.lines.len().saturating_sub(1))) {
                self.row = r;
                self.col = 0;
                self.run_normal(&keys);
            }
            self.clamp();
            return;
        }

        // :d :y :m/:t/:co :sort
        if body == "d" || body == "delete" {
            let (a, b) = self.resolve_range(rng.as_deref());
            self.push_undo();
            let mut text: String = self.lines[a..=b.min(self.lines.len() - 1)]
                .iter()
                .map(|l| l.iter().collect::<String>())
                .collect::<Vec<_>>()
                .join("\n");
            text.push('\n');
            self.set_register(None, text, RegKind::Line);
            self.lines.drain(a..=b.min(self.lines.len() - 1));
            if self.lines.is_empty() {
                self.lines.push(Vec::new());
            }
            self.row = a.min(self.lines.len() - 1);
            self.clamp();
            return;
        }
        let mt_re = Regex::new(r"^(m|move|t|co|copy)\s*(\S+)$").unwrap();
        if let Some(caps) = mt_re.captures(&body) {
            let (a, b) = self.resolve_range(rng.as_deref());
            let b = b.min(self.lines.len() - 1);
            let dest = &caps[2];
            let mut d: i64 = if dest == "$" {
                self.lines.len() as i64 - 1
            } else if dest == "0" {
                -1
            } else {
                dest.parse::<i64>().unwrap_or(1) - 1
            };
            let block: Vec<Vec<char>> = self.lines[a..=b].to_vec();
            self.push_undo();
            if &caps[1] == "m" || &caps[1] == "move" {
                self.lines.drain(a..=b);
                if d > b as i64 {
                    d -= (b - a + 1) as i64;
                }
            }
            let insert_at = ((d + 1).max(0) as usize).min(self.lines.len());
            let n = block.len();
            for (i, l) in block.into_iter().enumerate() {
                self.lines.insert(insert_at + i, l);
            }
            self.row = insert_at + n.saturating_sub(1);
            self.clamp();
            return;
        }
        if body == "sort" || body == "sort u" {
            let (a, b) = self.resolve_range(Some(rng.as_deref().unwrap_or("%")));
            self.push_undo();
            let mut block: Vec<Vec<char>> = self.lines[a..=b.min(self.lines.len() - 1)].to_vec();
            block.sort();
            if body.trim().ends_with('u') {
                let mut seen = std::collections::HashSet::new();
                block.retain(|l| seen.insert(l.clone()));
            }
            self.lines.splice(a..=b.min(self.lines.len() - 1), block);
            self.clamp();
            return;
        }
        if matches!(body.as_str(), "w" | "write" | "wq" | "x" | "q" | "q!" | "wa" | "xa") {
            if body.starts_with('w') || body.starts_with('x') {
                self.written = true;
                self.message = "\"buffer\" written".into();
            }
            if matches!(body.as_str(), "q" | "q!" | "wq" | "x" | "xa") {
                self.quit = true;
            }
            return;
        }
        if body == "noh" || body == "nohl" || body == "nohlsearch" {
            return;
        }
        if body.starts_with("set ") {
            self.message = body;
            return;
        }
        if let Ok(n) = cmd.parse::<i64>() {
            let r = (n - 1).clamp(0, self.lines.len() as i64 - 1) as usize;
            self.row = r;
            self.col = self.first_nonblank(r);
            return;
        }
        self.message = format!("E492: Not an editor command: {}", body);
    }

    fn run_normal(&mut self, keys: &str) {
        if self.depth > 20 {
            return;
        }
        self.depth += 1;
        let saved = std::mem::take(&mut self.pending);
        for k in parse_keys(keys) {
            self.key(k);
            if self.failed {
                break;
            }
        }
        if self.mode == Mode::Insert {
            self.key('\x1b');
        }
        self.pending = saved;
        self.depth -= 1;
    }

    // ---- simple commands -------------------------------------------------
    fn simple(&mut self, s: &[char], count: Option<usize>, reg: Option<char>, vis: bool) -> Status {
        let n = count.unwrap_or(1);
        let c = s[0];

        if c == 'g' {
            if s.len() == 1 {
                return Status::Incomplete;
            }
            let two = &s[..2];
            if two == ['g', 'g'] {
                let r = count.map(|c| c.saturating_sub(1)).unwrap_or(0).min(self.lines.len() - 1);
                self.row = r;
                self.col = self.first_nonblank(r);
                self.clamp();
                return Status::Done;
            }
            if two == ['g', 'J'] {
                return self.join(n, false);
            }
            if two == ['g', 'v'] {
                if let Some((mode, s0, e)) = self.last_visual {
                    self.mode = mode;
                    self.visual_start = Some(s0);
                    self.row = e.0;
                    self.col = e.1;
                    self.clamp();
                }
                return Status::Done;
            }
            if two == ['g', 'u'] || two == ['g', 'U'] || two == ['g', '~'] {
                return Status::Incomplete;
            }
            return Status::Invalid;
        }

        if c == 'Z' {
            if s.len() == 1 {
                return Status::Incomplete;
            }
            if s[..2] == ['Z', 'Z'] || s[..2] == ['Z', 'Q'] {
                self.written = s[..2] == ['Z', 'Z'];
                self.quit = true;
                return Status::Done;
            }
            return Status::Invalid;
        }

        if c == 'm' {
            if s.len() == 1 {
                return Status::Incomplete;
            }
            self.marks.insert(s[1], (self.row, self.col));
            return Status::Done;
        }

        if c == 'r' {
            if s.len() == 1 {
                return Status::Incomplete;
            }
            let ch = s[1];
            self.push_undo();
            if vis {
                let (sv, ev) = self.visual_range();
                if self.mode == Mode::VLine {
                    for r in sv.0..=ev.0 {
                        let len = self.lines[r].len();
                        self.lines[r] = vec![ch; len];
                    }
                } else {
                    let flat = self.flat();
                    let a = self.to_index(sv.0, sv.1);
                    let b = (self.to_index(ev.0, ev.1) + 1).min(flat.len());
                    let mid: Vec<char> = flat[a..b].iter().map(|&x| if x != '\n' { ch } else { '\n' }).collect();
                    let mut newflat: Vec<char> = flat[..a].to_vec();
                    newflat.extend(mid);
                    newflat.extend(flat[b..].iter().copied());
                    self.set_lines_from_flat(&newflat);
                    self.row = sv.0;
                    self.col = sv.1;
                }
                self.mode = Mode::Normal;
                self.visual_start = None;
                self.clamp();
                return Status::Done;
            }
            let line = self.line();
            if self.col + n > line.len() {
                return Status::Done;
            }
            for i in 0..n {
                self.lines[self.row][self.col + i] = ch;
            }
            self.col += n - 1;
            self.register_dot();
            return Status::Done;
        }

        if c == 'q' {
            if let Some(r) = self.recording_reg {
                let text: String = self.recorded.iter().collect();
                self.registers.insert(r, (text, RegKind::Macro));
                self.recording_reg = None;
                self.recorded.clear();
                return Status::Done;
            }
            if s.len() == 1 {
                return Status::Incomplete;
            }
            self.recording_reg = Some(s[1]);
            self.recorded.clear();
            return Status::Done;
        }

        if c == '@' {
            if s.len() == 1 {
                return Status::Incomplete;
            }
            let mut r = s[1];
            if r == '@' {
                match self.last_macro {
                    Some(m) => r = m,
                    None => return Status::Done,
                }
            }
            self.last_macro = Some(r);
            let body = self.registers.get(&r).map(|v| v.0.clone()).unwrap_or_default();
            for _ in 0..n {
                self.failed = false;
                self.run_normal(&body);
                if self.failed {
                    break;
                }
            }
            self.failed = false;
            return Status::Done;
        }

        if c == '"' {
            return Status::Incomplete;
        }

        if vis {
            if c == 'o' || c == 'O' {
                let vs = self.visual_start.unwrap_or((self.row, self.col));
                self.visual_start = Some((self.row, self.col));
                self.row = vs.0;
                self.col = vs.1;
                return Status::Done;
            }
            if (c == 'i' || c == 'a') && s.len() >= 2 {
                if let Some((start, end, _)) = self.text_object(c, s[1], n) {
                    self.visual_start = Some(start);
                    self.row = end.0;
                    self.col = end.1;
                }
                return Status::Done;
            }
            if c == 'i' || c == 'a' {
                return Status::Incomplete;
            }
            if c == 'x' {
                return self.apply_operator_visual("d", reg);
            }
            if c == 's' {
                return self.apply_operator_visual("c", reg);
            }
            if c == 'D' || c == 'X' || c == 'R' {
                if self.mode != Mode::VLine {
                    self.mode = Mode::VLine;
                }
                return self.apply_operator_visual("d", reg);
            }
            if c == 'C' {
                self.mode = Mode::VLine;
                return self.apply_operator_visual("c", reg);
            }
            if c == 'Y' {
                self.mode = Mode::VLine;
                return self.apply_operator_visual("y", reg);
            }
            if c == 'J' {
                let (sv, ev) = self.visual_range();
                self.mode = Mode::Normal;
                self.visual_start = None;
                self.row = sv.0;
                return self.join((ev.0 - sv.0 + 1).max(2), true);
            }
            if c == 'u' {
                return self.apply_operator_visual("gu", reg);
            }
            if c == 'U' {
                return self.apply_operator_visual("gU", reg);
            }
            if c == '~' {
                return self.apply_operator_visual("g~", reg);
            }
            if c == 'p' || c == 'P' {
                let (txt, kind) = self.get_register(reg);
                self.apply_operator_visual("d", Some('_'));
                self.paste(&txt, kind, true);
                return Status::Done;
            }
            if c == 'I' && self.mode == Mode::VBlock {
                let (r1, r2, c1, _c2) = self.vblock_cols();
                self.save_visual();
                self.push_undo();
                self.mode = Mode::Insert;
                self.visual_start = None;
                self.row = r1;
                self.col = c1;
                self.block_insert = Some((r1, r2, c1, false));
                self.begin_change(Vec::new());
                return Status::Done;
            }
            if c == 'A' && self.mode == Mode::VBlock {
                let (r1, r2, _c1, c2) = self.vblock_cols();
                self.save_visual();
                self.push_undo();
                self.mode = Mode::Insert;
                self.visual_start = None;
                self.row = r1;
                self.col = (c2 + 1).min(self.lines[r1].len());
                self.block_insert = Some((r1, r2, c2 + 1, true));
                self.begin_change(Vec::new());
                return Status::Done;
            }
        }

        if c == 'i' && !vis {
            self.push_undo();
            self.mode = Mode::Insert;
            let pend = self.pending.clone();
            self.begin_change(pend);
            return Status::Done;
        }
        if c == 'a' && !vis {
            self.push_undo();
            self.mode = Mode::Insert;
            self.col = (self.col + 1).min(self.line().len());
            let pend = self.pending.clone();
            self.begin_change(pend);
            return Status::Done;
        }
        if c == 'I' {
            self.push_undo();
            self.mode = Mode::Insert;
            let line = self.line();
            self.col = if line.iter().any(|c| !c.is_whitespace()) {
                self.first_nonblank(self.row)
            } else {
                0
            };
            let pend = self.pending.clone();
            self.begin_change(pend);
            return Status::Done;
        }
        if c == 'A' {
            self.push_undo();
            self.mode = Mode::Insert;
            self.col = self.line().len();
            let pend = self.pending.clone();
            self.begin_change(pend);
            return Status::Done;
        }
        if c == 'o' || c == 'O' {
            self.push_undo();
            let indent: Vec<char> = self.line().iter().take_while(|&&c| c == ' ' || c == '\t').copied().collect();
            let at = if c == 'o' { self.row + 1 } else { self.row };
            self.lines.insert(at, indent.clone());
            self.row = at;
            self.col = indent.len();
            self.mode = Mode::Insert;
            let pend = self.pending.clone();
            self.begin_change(pend);
            return Status::Done;
        }
        if c == 'R' {
            self.push_undo();
            self.mode = Mode::Replace;
            let pend = self.pending.clone();
            self.begin_change(pend);
            return Status::Done;
        }
        if c == 'v' {
            self.mode = Mode::Visual;
            self.visual_start = Some((self.row, self.col));
            return Status::Done;
        }
        if c == 'V' {
            self.mode = Mode::VLine;
            self.visual_start = Some((self.row, self.col));
            return Status::Done;
        }
        if c == '\x16' {
            self.mode = Mode::VBlock;
            self.visual_start = Some((self.row, self.col));
            return Status::Done;
        }
        if c == ':' {
            self.mode = Mode::Cmdline;
            self.cmdtype = ':';
            self.cmdline = if vis { "'<,'>".to_string() } else { String::new() };
            return Status::Done;
        }
        if c == '/' || c == '?' {
            self.mode = Mode::Cmdline;
            self.cmdtype = c;
            self.cmdline = String::new();
            return Status::Done;
        }

        if c == 'x' {
            self.push_undo();
            let line = self.line();
            if line.is_empty() {
                return Status::Done;
            }
            let end = (self.col + n).min(line.len());
            let removed: String = line[self.col..end].iter().collect();
            self.set_register(reg, removed, RegKind::Char);
            self.lines[self.row].drain(self.col..end);
            self.clamp();
            self.register_dot();
            return Status::Done;
        }
        if c == 'X' {
            self.push_undo();
            let start = self.col.saturating_sub(n);
            let removed: String = self.line()[start..self.col].iter().collect();
            self.set_register(reg, removed, RegKind::Char);
            self.lines[self.row].drain(start..self.col);
            self.col = start;
            self.register_dot();
            return Status::Done;
        }
        if c == 's' {
            self.push_undo();
            let line = self.line();
            let end = (self.col + n).min(line.len());
            let removed: String = line[self.col..end].iter().collect();
            self.set_register(reg, removed, RegKind::Char);
            self.lines[self.row].drain(self.col..end);
            self.mode = Mode::Insert;
            let pend = self.pending.clone();
            self.begin_change(pend);
            return Status::Done;
        }
        if c == 'S' {
            return self.operator_pending("c", &['c'], count, reg);
        }
        if c == 'D' {
            self.push_undo();
            let line = self.line();
            let removed: String = line[self.col..].iter().collect();
            self.set_register(reg, removed, RegKind::Char);
            self.lines[self.row].truncate(self.col);
            self.clamp();
            self.register_dot();
            return Status::Done;
        }
        if c == 'C' {
            self.push_undo();
            let line = self.line();
            let removed: String = line[self.col..].iter().collect();
            self.set_register(reg, removed, RegKind::Char);
            self.lines[self.row].truncate(self.col);
            self.mode = Mode::Insert;
            let pend = self.pending.clone();
            self.begin_change(pend);
            return Status::Done;
        }
        if c == 'Y' {
            return self.operator_pending("y", &['y'], count, reg);
        }
        if c == 'J' {
            return self.join(n.max(2), true);
        }
        if c == '~' {
            self.push_undo();
            let line = self.line();
            let end = (self.col + n).min(line.len());
            let mut newline = line.clone();
            for i in self.col..end {
                newline[i] = swapcase_char(line[i]);
            }
            self.lines[self.row] = newline;
            self.col = end.min(line.len().saturating_sub(1));
            self.register_dot();
            return Status::Done;
        }
        if c == 'p' || c == 'P' {
            self.push_undo();
            let (txt, kind) = self.get_register(reg);
            if txt.is_empty() {
                return Status::Done;
            }
            for _ in 0..n {
                self.paste(&txt, kind, c == 'P');
            }
            self.register_dot();
            return Status::Done;
        }
        if c == '\x01' || c == '\x18' {
            let delta: i64 = if c == '\x01' { n as i64 } else { -(n as i64) };
            let line = self.line();
            let s: String = line.iter().collect();
            let num_re = Regex::new(r"-?\d+").unwrap();
            let m = num_re.find_iter(&s).find(|m| {
                let end_char = s[..m.end()].chars().count();
                end_char > self.col
            });
            let m = match m {
                Some(m) => m,
                None => {
                    self.failed = true;
                    return Status::Done;
                }
            };
            self.push_undo();
            let start_char = s[..m.start()].chars().count();
            let end_char = s[..m.end()].chars().count();
            let val: i64 = m.as_str().parse().unwrap_or(0);
            let new = (val + delta).to_string();
            let mut newline: Vec<char> = line[..start_char].to_vec();
            newline.extend(new.chars());
            newline.extend(line[end_char..].iter().copied());
            self.col = start_char + new.chars().count() - 1;
            self.lines[self.row] = newline;
            self.register_dot();
            return Status::Done;
        }
        if c == 'u' {
            self.undo();
            return Status::Done;
        }
        if c == '\x12' {
            self.redo();
            return Status::Done;
        }
        if c == '.' {
            if let Some(keys) = self.last_change.clone() {
                self.last_change = None;
                let s: String = keys.iter().collect();
                self.run_normal(&s);
                self.last_change = Some(keys);
            }
            return Status::Done;
        }
        if c == '\x04' || c == '\x15' || c == '\x06' || c == '\x02' {
            let step: i64 = match c {
                '\x04' => 10,
                '\x15' => -10,
                '\x06' => 20,
                _ => -20,
            };
            let r = (self.row as i64 + step).clamp(0, self.lines.len() as i64 - 1);
            self.row = r as usize;
            self.clamp();
            return Status::Done;
        }

        let res = self.motion(s, n, false);
        match res {
            MotionResult::Incomplete => Status::Incomplete,
            MotionResult::None => Status::Done,
            MotionResult::Move((r, col), _kind) => {
                self.row = r;
                self.col = col;
                if s[0] != 'j' && s[0] != 'k' {
                    self.desired_col = self.col;
                }
                if s[0] == '$' {
                    self.desired_col = BIG_COL;
                }
                self.clamp();
                Status::Done
            }
        }
    }

    fn join(&mut self, n: usize, spaces: bool) -> Status {
        self.push_undo();
        let iterations = n.saturating_sub(1).max(1);
        for _ in 0..iterations {
            if self.row + 1 >= self.lines.len() {
                break;
            }
            let cur = self.lines[self.row].clone();
            let nxt = self.lines.remove(self.row + 1);
            if spaces {
                let cur_trim_end = rstrip(&cur);
                let nxt_trim_start = lstrip(&nxt);
                let need_space = !all_ws(&cur) && !all_ws(&nxt);
                let mut joined = cur_trim_end.clone();
                if need_space {
                    joined.push(' ');
                }
                joined.extend(nxt_trim_start);
                self.col = cur_trim_end.len();
                self.lines[self.row] = joined;
            } else {
                let mut joined = cur.clone();
                joined.extend(nxt);
                self.col = cur.len();
                self.lines[self.row] = joined;
            }
        }
        self.clamp();
        self.register_dot();
        Status::Done
    }

    fn paste(&mut self, txt: &str, kind: RegKind, before: bool) {
        match kind {
            RegKind::Line => {
                let body: Vec<Vec<char>> = if let Some(stripped) = txt.strip_suffix('\n') {
                    stripped.split('\n').map(|p| p.chars().collect()).collect()
                } else {
                    txt.split('\n').map(|p| p.chars().collect()).collect()
                };
                let at = if before { self.row } else { self.row + 1 };
                let n = body.len();
                for (i, l) in body.into_iter().enumerate() {
                    self.lines.insert(at + i, l);
                }
                self.row = at;
                let _ = n;
                self.col = self.first_nonblank(self.row);
            }
            RegKind::Block => {
                let body: Vec<&str> = txt.split('\n').collect();
                let c = self.col + if before { 0 } else { 1 };
                for (i, chunk) in body.iter().enumerate() {
                    let r = self.row + i;
                    while r >= self.lines.len() {
                        self.lines.push(Vec::new());
                    }
                    if self.lines[r].len() < c {
                        let pad = c - self.lines[r].len();
                        self.lines[r].extend(std::iter::repeat(' ').take(pad));
                    }
                    let insert_at = c.min(self.lines[r].len());
                    for (j, ch) in chunk.chars().enumerate() {
                        self.lines[r].insert(insert_at + j, ch);
                    }
                }
            }
            RegKind::Char | RegKind::Macro => {
                let line = self.line();
                let at = if before { self.col } else { (self.col + 1).min(line.len()) };
                if txt.contains('\n') {
                    let mut parts = txt.split('\n');
                    let head: Vec<char> = parts.next().unwrap().chars().collect();
                    let rest: Vec<Vec<char>> = parts.map(|p| p.chars().collect()).collect();
                    let tail: Vec<char> = line[at..].to_vec();
                    let mut newfirst = line[..at].to_vec();
                    newfirst.extend(head);
                    self.lines[self.row] = newfirst;
                    let nrest = rest.len();
                    for (i, l) in rest.into_iter().enumerate() {
                        self.lines.insert(self.row + 1 + i, l);
                    }
                    self.row += nrest;
                    self.col = if nrest > 0 { self.lines[self.row].len() } else { 0 };
                    self.lines[self.row].extend(tail);
                } else {
                    let txtchars: Vec<char> = txt.chars().collect();
                    let mut newline = line[..at].to_vec();
                    newline.extend(txtchars.iter().copied());
                    newline.extend(line[at..].iter().copied());
                    self.lines[self.row] = newline;
                    self.col = at + txtchars.len() - 1;
                }
            }
        }
        self.clamp();
    }
}

fn swapcase_char(c: char) -> char {
    if c.is_uppercase() {
        c.to_lowercase().next().unwrap_or(c)
    } else if c.is_lowercase() {
        c.to_uppercase().next().unwrap_or(c)
    } else {
        c
    }
}

fn all_ws(v: &[char]) -> bool {
    v.iter().all(|c| c.is_whitespace())
}

fn rstrip(v: &[char]) -> Vec<char> {
    let mut end = v.len();
    while end > 0 && v[end - 1].is_whitespace() {
        end -= 1;
    }
    v[..end].to_vec()
}

fn lstrip(v: &[char]) -> Vec<char> {
    let mut start = 0;
    while start < v.len() && v[start].is_whitespace() {
        start += 1;
    }
    v[start..].to_vec()
}

fn find_char_from(line: &[char], target: char, start: usize) -> Option<usize> {
    (start..line.len()).find(|&i| line[i] == target)
}

fn rfind_char_before(line: &[char], target: char, before: usize) -> Option<usize> {
    let limit = before.min(line.len());
    (0..limit).rev().find(|&i| line[i] == target)
}

fn next_word_start(t: &[char], i: usize, big: bool) -> usize {
    let n = t.len();
    if i >= n {
        return n;
    }
    let cls = char_class(t[i], big);
    let mut i = i;
    if cls != 0 {
        while i < n && char_class(t[i], big) == cls && t[i] != '\n' {
            i += 1;
        }
    }
    while i < n && char_class(t[i], big) == 0 {
        if t[i] == '\n' && i + 1 < n && t[i + 1] == '\n' {
            return i + 1;
        }
        i += 1;
    }
    i.min(n)
}

fn prev_word_start(t: &[char], i0: usize, big: bool) -> usize {
    let mut i: i64 = i0 as i64 - 1;
    while i > 0 && char_class(t[i as usize], big) == 0 {
        i -= 1;
    }
    if i <= 0 {
        return 0;
    }
    let cls = char_class(t[i as usize], big);
    while i > 0 && char_class(t[(i - 1) as usize], big) == cls {
        i -= 1;
    }
    i.max(0) as usize
}

fn next_word_end(t: &[char], i: usize, big: bool) -> usize {
    let n = t.len();
    if n == 0 {
        return 0;
    }
    let mut i = i + 1;
    while i < n && char_class(t[i], big) == 0 {
        i += 1;
    }
    if i >= n {
        return n - 1;
    }
    let cls = char_class(t[i], big);
    while i + 1 < n && char_class(t[i + 1], big) == cls {
        i += 1;
    }
    i
}

fn vim_re(pat: &str) -> String {
    let mut out = pat.replace("\\<", "\\b").replace("\\>", "\\b");
    let re_paren = Regex::new(r"\\\((.*?)\\\)").unwrap();
    out = re_paren.replace_all(&out, "($1)").to_string();
    out = out.replace("\\+", "+").replace("\\?", "?").replace("\\|", "|");
    out = out.replace("\\{", "{").replace("\\}", "}");
    out
}

fn vim_replacement(rep: &str) -> String {
    let mut out = String::new();
    let chars: Vec<char> = rep.chars().collect();
    let mut i = 0;
    while i < chars.len() {
        let c = chars[i];
        if c == '$' {
            out.push_str("$$");
            i += 1;
        } else if c == '\\' && i + 1 < chars.len() && chars[i + 1].is_ascii_digit() {
            out.push_str("${");
            out.push(chars[i + 1]);
            out.push('}');
            i += 2;
        } else if c == '&' {
            out.push_str("${0}");
            i += 1;
        } else {
            out.push(c);
            i += 1;
        }
    }
    out
}

fn split_unescaped(s: &str, sep: char) -> Vec<String> {
    let mut parts = Vec::new();
    let mut cur = String::new();
    let mut escaped = false;
    for c in s.chars() {
        if escaped {
            cur.push(c);
            escaped = false;
        } else if c == '\\' {
            cur.push(c);
            escaped = true;
        } else if c == sep {
            parts.push(std::mem::take(&mut cur));
        } else {
            cur.push(c);
        }
    }
    parts.push(cur);
    parts
}

fn split_unescaped_once(s: &str, sep: char) -> (String, Option<String>) {
    let chars: Vec<char> = s.chars().collect();
    let mut escaped = false;
    for (i, &c) in chars.iter().enumerate() {
        if escaped {
            escaped = false;
            continue;
        }
        if c == '\\' {
            escaped = true;
            continue;
        }
        if c == sep {
            let first: String = chars[..i].iter().collect();
            let rest: String = chars[i + 1..].iter().collect();
            return (first, Some(rest));
        }
    }
    (s.to_string(), None)
}
