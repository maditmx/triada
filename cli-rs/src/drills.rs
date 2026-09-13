//! The exercise runners — port of drills.py.

use crate::curriculum::Curriculum;
use crate::input::{self, ctrl};
use crate::keyboard::key_hint;
use crate::markdown::{render_markdown, rows_to_lines};
use crate::progress::Progress;
use crate::ui::{self, Canvas, Term};
use crate::vim::{parse_keys, Vim};
use crossterm::event::{KeyCode, KeyModifiers};
use ratatui::layout::{Alignment, Constraint, Layout, Rect};
use ratatui::style::{Modifier, Style};
use ratatui::text::{Line, Span};
use ratatui::widgets::{Block, BorderType, List, ListItem, Paragraph, Scrollbar, ScrollbarOrientation, ScrollbarState, Wrap};
use serde_json::{json, Value};
use std::io;
use std::process::Command;
use std::time::{Duration, Instant};

pub enum Outcome {
    Back,
    Next,
}

/// Render a lesson's markdown "teach" blurb, capped at `max_lines` (with a
/// "press t" trailer beyond that), as ready-to-render lines plus their height.
fn teach_lines(text: &str, width: usize, max_lines: usize) -> (Vec<Line<'static>>, u16) {
    if text.is_empty() {
        return (Vec::new(), 0);
    }
    let rows = render_markdown(text, width);
    let shown = rows.len().min(max_lines);
    let mut lines = rows_to_lines(&rows[..shown]);
    let mut h = shown as u16;
    if rows.len() > max_lines {
        lines.push(Line::styled("… press t for the full explanation", ui::dim()));
        h += 1;
    }
    (lines, h)
}

pub fn pager(term: &mut Term, title: &str, text: &str) -> io::Result<()> {
    let mut top: usize = 0;
    loop {
        let (h, w) = ui::size(term)?;
        let area = Rect::new(0, 0, w as u16, h as u16);
        let block = ui::chrome(title, ui::DIM);
        let inner = block.inner(area);
        let (body, foot) = ui::body_footer(inner);
        let split = Layout::horizontal([Constraint::Min(0), Constraint::Length(1)]).split(body);
        let text_area = split[0];
        let sb_area = split[1];
        let width = (text_area.width as usize).saturating_sub(1).max(1);
        let rows = render_markdown(text, width);
        let lines = rows_to_lines(&rows);
        let body_h = text_area.height as usize;
        let max_top = rows.len().saturating_sub(body_h);
        top = top.min(max_top);
        let para = Paragraph::new(lines).scroll((top as u16, 0));
        let mut sstate = ScrollbarState::new(rows.len().max(1)).position(top);

        term.draw(|f| {
            f.render_widget(block, area);
            ui::footer(f, foot, "j/k scroll · space page · q back");
            f.render_widget(para, text_area);
            f.render_stateful_widget(Scrollbar::new(ScrollbarOrientation::VerticalRight), sb_area, &mut sstate);
        })?;

        let k = input::read_key()?;
        match k.code {
            KeyCode::Char('q') | KeyCode::Esc | KeyCode::Left => return Ok(()),
            KeyCode::Char('j') | KeyCode::Down => top = (top + 1).min(max_top),
            KeyCode::Char('k') | KeyCode::Up => top = top.saturating_sub(1),
            KeyCode::Char(' ') | KeyCode::PageDown => top = (top + body_h).min(max_top),
            KeyCode::PageUp => top = top.saturating_sub(body_h),
            KeyCode::Char('g') => top = 0,
            KeyCode::Char('G') => top = max_top,
            _ => {}
        }
    }
}

fn get_str(v: &Value, k: &str) -> String {
    v.get(k).and_then(|x| x.as_str()).unwrap_or("").to_string()
}
fn get_f64(v: &Value, k: &str, default: f64) -> f64 {
    v.get(k).and_then(|x| x.as_f64()).unwrap_or(default)
}
fn get_u64(v: &Value, k: &str, default: u64) -> u64 {
    v.get(k).and_then(|x| x.as_u64()).unwrap_or(default)
}

// ============================================================== TYPING
pub fn run_typing(
    term: &mut Term,
    lesson: &Value,
    level: Option<&Value>,
    prog: &mut Progress,
    cur: &Curriculum,
    track: &str,
) -> io::Result<Outcome> {
    let content = get_str(lesson, "content");
    let chars: Vec<char> = content.chars().collect();
    let mut typed: Vec<char> = Vec::new();
    let mut started: Option<Instant> = None;
    let mut first_wrong: std::collections::HashSet<usize> = std::collections::HashSet::new();
    let mut err_keys: std::collections::HashMap<char, u32> = std::collections::HashMap::new();

    let pass = lesson.get("pass").or_else(|| level.and_then(|l| l.get("pass")));
    let pass_wpm = pass.map(|p| get_u64(p, "wpm", 25)).unwrap_or(25);
    let pass_acc = pass.map(|p| get_f64(p, "acc", 0.95)).unwrap_or(0.95);

    let mut result: Option<(String, bool)> = None;

    let metrics = |typed: &[char], started: &Option<Instant>, first_wrong: &std::collections::HashSet<usize>| -> (usize, f64, u64) {
        let correct = typed.iter().enumerate().filter(|&(i, &c)| i < chars.len() && c == chars[i]).count();
        let acc = if typed.is_empty() { 1.0 } else { (typed.len() - first_wrong.len()) as f64 / typed.len() as f64 };
        let mins = started.map(|s| s.elapsed().as_secs_f64() / 60.0).unwrap_or(0.0);
        let wpm = if mins > 0.002 { ((correct as f64 / 5.0) / mins) as u64 } else { 0 };
        (correct, acc.max(0.0), wpm)
    };

    loop {
        let (h, w) = ui::size(term)?;
        let area = Rect::new(0, 0, w as u16, h as u16);
        let block = ui::chrome(&format!("TRÍADA › {}", get_str(lesson, "title")), ui::track_color(track));
        let inner = block.inner(area);
        let (body, foot) = ui::body_footer(inner);
        let chunks = Layout::vertical([Constraint::Length(1), Constraint::Min(0)]).split(body);
        let header_area = chunks[0];
        let canvas_area = chunks[1];

        let (_c, acc, wpm) = metrics(&typed, &started, &first_wrong);
        let passing = wpm >= pass_wpm && acc >= pass_acc;
        let stats_text = format!(" {:3} wpm  {:5.1}%  target {}/{}% ", wpm, acc * 100.0, pass_wpm, (pass_acc * 100.0) as u64);
        let stats_style = if passing { ui::chip(ui::OK) } else { ui::dim() };
        let header = Paragraph::new(Line::styled(stats_text, stats_style)).alignment(Alignment::Right);

        let width = 92.min((canvas_area.width as usize).saturating_sub(2)).max(1);
        let mut canvas = Canvas::new(canvas_area.height as usize, canvas_area.width as usize);
        let x0 = 1usize;
        let mut y = 0usize;
        let teach = get_str(lesson, "teach");
        if !teach.is_empty() {
            let (lines, th) = teach_lines(&teach, width, 3);
            for (i, l) in lines.iter().enumerate() {
                canvas.put_segments(y + i, x0, &l.spans.iter().map(|s| (s.content.to_string(), s.style)).collect::<Vec<_>>(), width);
            }
            y += th as usize + 1;
        }

        let (mut row, mut col) = (y, x0);
        for (i, &ch) in chars.iter().enumerate() {
            if ch == '\n' {
                let style = if i == typed.len() { ui::chip(ui::ACCENT) } else { ui::dim() };
                canvas.put(row, col, "⏎", style);
                row += 1;
                col = x0;
                continue;
            }
            if col >= x0 + width && ch == ' ' {
                row += 1;
                col = x0;
                continue;
            }
            if col >= x0 + width + 6 {
                row += 1;
                col = x0;
            }
            let mut style = if i < typed.len() {
                if typed[i] == ch {
                    Default::default()
                } else {
                    ui::chip(ui::BAD)
                }
            } else {
                ui::dim()
            };
            if i == typed.len() {
                style = ui::chip(ui::ACCENT);
            }
            canvas.put(row, col, &ch.to_string(), style);
            col += 1;
        }
        if typed.len() > chars.len() {
            let extra: String = typed[chars.len()..].iter().collect();
            canvas.put(row, col, &extra, ui::chip(ui::BAD));
        }

        row += 2;
        if typed.len() < chars.len() {
            let nxt = chars[typed.len()];
            let nlabel = if nxt == ' ' { "␣".to_string() } else if nxt == '\n' { "↵".to_string() } else { nxt.to_string() };
            canvas.put(row, x0, &format!("next  {}   {}", nlabel, key_hint(nxt)), ui::accent());
        }
        row += 2;

        if let Some((msg, ok)) = &result {
            canvas.put(row, x0, msg, if *ok { ui::ok() } else { ui::bad() });
            row += 1;
            if !err_keys.is_empty() {
                let mut worst: Vec<(&char, &u32)> = err_keys.iter().collect();
                worst.sort_by(|a, b| b.1.cmp(a.1));
                worst.truncate(10);
                let txt = worst
                    .iter()
                    .map(|(k, n)| {
                        let label = if **k == ' ' { "␣".to_string() } else if **k == '\n' { "↵".to_string() } else { k.to_string() };
                        format!("{}×{}", label, n)
                    })
                    .collect::<Vec<_>>()
                    .join("  ");
                canvas.put(row, x0, &format!("missed: {}", txt), ui::dim());
            }
        }

        term.draw(|f| {
            f.render_widget(block, area);
            ui::footer(f, foot, "type it · ^R restart · ^N next · Esc back");
            f.render_widget(header, header_area);
            canvas.render(f, canvas_area);
        })?;

        let k = input::read_key()?;
        if ctrl(&k, 'r') {
            typed.clear();
            started = None;
            first_wrong.clear();
            err_keys.clear();
            result = None;
            continue;
        }
        if ctrl(&k, 'n') {
            return Ok(Outcome::Next);
        }
        if matches!(k.code, KeyCode::Esc) {
            return Ok(Outcome::Back);
        }
        if matches!(k.code, KeyCode::Backspace) {
            typed.pop();
            continue;
        }
        let mut ch = match k.code {
            KeyCode::Enter => '\n',
            KeyCode::Tab => continue,
            KeyCode::Char(c) if !k.modifiers.contains(KeyModifiers::CONTROL) => c,
            _ => continue,
        };
        if ch == '\n' && typed.len() < chars.len() && chars[typed.len()] != '\n' {
            continue;
        }
        if (ch as u32) < 32 && ch != '\n' {
            continue;
        }
        let _ = &mut ch;

        let i = typed.len();
        if started.is_none() {
            started = Some(Instant::now());
        }
        if i < chars.len() && ch != chars[i] {
            if !first_wrong.contains(&i) {
                first_wrong.insert(i);
                *err_keys.entry(chars[i]).or_insert(0) += 1;
                prog.bump_key(chars[i]);
            }
        }
        typed.push(ch);

        if typed == chars {
            let (_c, acc, wpm) = metrics(&typed, &started, &first_wrong);
            let passed = wpm >= pass_wpm && acc >= pass_acc;
            let lesson_id = get_str(lesson, "id");
            if passed {
                prog.mark_done(track, &lesson_id, Some(json!({"wpm": wpm, "acc": (acc * 100.0).round() / 100.0})), cur);
                result = Some((format!("✓ {} wpm at {:.0}% — passed. ^N for the next lesson.", wpm, acc * 100.0), true));
            } else {
                prog.mark_tried(track, &lesson_id);
                result = Some((
                    format!(
                        "· {} wpm at {:.0}% — need {} wpm at {}%. ^R to retry, slower.",
                        wpm,
                        acc * 100.0,
                        pass_wpm,
                        (pass_acc * 100.0) as u64
                    ),
                    false,
                ));
            }
            prog.save();
        }
    }
}

// ================================================================= VIM
pub fn run_vim(
    term: &mut Term,
    lesson: &Value,
    prog: &mut Progress,
    cur: &Curriculum,
    track: &str,
    mut on_solved: Option<&mut dyn FnMut()>,
) -> io::Result<Outcome> {
    let start_lines: Vec<String> = lesson["start"]["lines"].as_array().unwrap().iter().map(|v| v.as_str().unwrap_or("").to_string()).collect();
    let start_cursor = (
        lesson["start"]["cursor"][0].as_u64().unwrap_or(0) as usize,
        lesson["start"]["cursor"][1].as_u64().unwrap_or(0) as usize,
    );
    let goal = &lesson["goal"];
    let goal_lines: Vec<String> = goal["lines"].as_array().unwrap().iter().map(|v| v.as_str().unwrap_or("").to_string()).collect();
    let par = get_u64(lesson, "par", 0);

    let mut v = Vim::new(start_lines.clone(), start_cursor);
    let mut solved = false;
    let mut revealed = false;
    let mut show_hint = false;

    let check = |v: &Vim| -> bool {
        if v.lines_as_strings() != goal_lines {
            return false;
        }
        if let Some(c) = goal.get("cursor").and_then(|c| c.as_array()) {
            if v.row != c[0].as_u64().unwrap_or(0) as usize || v.col != c[1].as_u64().unwrap_or(0) as usize {
                return false;
            }
        }
        if let Some(m) = goal.get("mode").and_then(|m| m.as_str()) {
            if v.mode.as_str() != m {
                return false;
            }
        }
        true
    };

    loop {
        let (h, w) = ui::size(term)?;
        let area = Rect::new(0, 0, w as u16, h as u16);
        let block = ui::chrome(&format!("TRÍADA › {}", get_str(lesson, "title")), ui::track_color(track));
        let inner = block.inner(area);
        let (body, foot) = ui::body_footer(inner);

        let teach = get_str(lesson, "teach");
        let teach_width = 96.min((body.width as usize).saturating_sub(2)).max(1);
        let (teach_para_lines, teach_h) = teach_lines(&teach, teach_width, 4);
        let teach_reserved = if teach_h > 0 { teach_h + 1 } else { 0 };

        let chunks = Layout::vertical([Constraint::Length(1), Constraint::Length(teach_reserved), Constraint::Min(6), Constraint::Length(6)]).split(body);
        let header_area = chunks[0];
        let teach_area = chunks[1];
        let panels_area = chunks[2];
        let status_area = chunks[3];

        let header = Paragraph::new(Line::styled(format!("keys {:3} · par {:3}", v.typed, par), ui::dim())).alignment(Alignment::Right);
        let teach_para = Paragraph::new(teach_para_lines);

        let panels = Layout::horizontal([Constraint::Percentage(50), Constraint::Percentage(50)]).split(panels_area);
        let left_block = Block::bordered()
            .border_type(BorderType::Rounded)
            .border_style(Style::default().fg(ui::track_color(track)))
            .title(Span::styled(" Your buffer ", ui::head_bold()));
        let right_block = Block::bordered().border_type(BorderType::Rounded).border_style(ui::dim()).title(Span::styled(" Target ", ui::dim()));
        let left_inner = left_block.inner(panels[0]);
        let right_inner = right_block.inner(panels[1]);

        let mut left = Canvas::new(left_inner.height as usize, left_inner.width as usize);
        let vr = if v.visual_start.is_some() { Some(v.visual_range()) } else { None };
        let vlines = v.lines_as_strings();
        for (r, line) in vlines.iter().enumerate() {
            if r >= left.h {
                break;
            }
            let num = if r == v.row { (r + 1).to_string() } else { (r as i64 - v.row as i64).abs().to_string() };
            let numstyle = if r == v.row { ui::accent_bold() } else { ui::dim() };
            left.put(r, 0, &format!("{:>3}", num), numstyle);
            let mut x = 4usize;
            let lchars: Vec<char> = line.chars().collect();
            let cbody: Vec<char> = if lchars.is_empty() { vec![' '] } else { lchars.clone() };
            for (c, ch) in cbody.iter().enumerate() {
                let mut style = Style::default();
                if let Some((s, e)) = vr {
                    let inside = if v.mode == crate::vim::Mode::VLine {
                        s.0 <= r && r <= e.0
                    } else if v.mode == crate::vim::Mode::VBlock {
                        let (r1, r2, c1, c2) = v.vblock_cols();
                        r1 <= r && r <= r2 && c1 <= c && c <= c2
                    } else {
                        let idx = v.to_index(r, c);
                        v.to_index(s.0, s.1) <= idx && idx <= v.to_index(e.0, e.1)
                    };
                    if inside {
                        style = ui::chip(ui::NVIM);
                    }
                }
                if r == v.row && c == v.col {
                    style = ui::chip(ui::ACCENT);
                }
                left.put(r, x, &ch.to_string(), style);
                x += 1;
            }
            if r == v.row && v.col >= lchars.len() {
                left.put(r, 4 + lchars.len(), " ", ui::chip(ui::ACCENT));
            }
        }

        let mut right = Canvas::new(right_inner.height as usize, right_inner.width as usize);
        for (r, line) in goal_lines.iter().enumerate() {
            if r >= right.h {
                break;
            }
            let same = r < vlines.len() && &vlines[r] == line;
            let shown: String = if line.is_empty() { " ".to_string() } else { line.chars().take(right.w).collect() };
            right.put(r, 0, &shown, if same { ui::dim() } else { ui::ok() });
        }
        if get_str(lesson, "kind") == "move" {
            if let Some(c) = goal.get("cursor").and_then(|c| c.as_array()) {
                right.put(
                    goal_lines.len() + 1,
                    0,
                    &format!("cursor → line {}, col {}", c[0].as_u64().unwrap_or(0) + 1, c[1].as_u64().unwrap_or(0) + 1),
                    ui::ok(),
                );
            }
        }

        let mut status = Canvas::new(status_area.height as usize, status_area.width as usize);
        let mode_label = match v.mode {
            crate::vim::Mode::VLine => "V-LINE".to_string(),
            crate::vim::Mode::VBlock => "V-BLOCK".to_string(),
            m => m.as_str().to_uppercase(),
        };
        status.put(0, 0, &format!(" {} ", mode_label), ui::chip(ui::NVIM));
        let sx = mode_label.chars().count() + 3;
        if v.mode == crate::vim::Mode::Cmdline {
            status.put(0, sx, &format!("{}{}█", v.cmdtype, v.cmdline), ui::accent());
        } else if !v.pending.is_empty() {
            let s: String = v.pending.iter().collect();
            status.put(0, sx, &s, ui::accent_bold());
        }
        if let Some(r) = v.recording_reg {
            status.put(0, sx + 12, &format!("recording @{}", r), ui::accent());
        }
        let mut sy = 1;
        if !v.message.is_empty() {
            status.put(sy, 0, &v.message, ui::dim());
            sy += 1;
        }
        if show_hint {
            let hint = get_str(lesson, "hint");
            if !hint.is_empty() {
                for (i, segs) in render_markdown(&hint, status.w.saturating_sub(2)).iter().take(3).enumerate() {
                    status.put_segments(sy + i, 0, segs, status.w);
                }
                sy += 3;
            }
        }
        if solved {
            let over = v.typed as i64 - par as i64;
            let mut msg = format!("✓ solved in {} keys", v.typed);
            let suffix = if over > 0 { format!(" — par is {}", par) } else { " — at or under par".to_string() };
            msg += &suffix;
            if revealed {
                msg += "   (shown, so it was not recorded)";
            }
            status.put(sy, 0, &msg, ui::ok().add_modifier(Modifier::BOLD));
        }

        term.draw(|f| {
            f.render_widget(block, area);
            ui::footer(f, foot, "keys go to Vim · F1 hint · F2 show me · F5 reset · F10 or ZZ back · ^N next");
            f.render_widget(header, header_area);
            if teach_h > 0 {
                f.render_widget(teach_para, teach_area);
            }
            f.render_widget(left_block, panels[0]);
            f.render_widget(right_block, panels[1]);
            left.render(f, left_inner);
            right.render(f, right_inner);
            status.render(f, status_area);
        })?;

        let k = input::read_key()?;
        match k.code {
            KeyCode::F(10) => return Ok(Outcome::Back),
            KeyCode::F(5) => {
                v = Vim::new(start_lines.clone(), start_cursor);
                solved = false;
                revealed = false;
                continue;
            }
            KeyCode::F(1) => {
                show_hint = !show_hint;
                continue;
            }
            KeyCode::F(2) => {
                v = Vim::new(start_lines.clone(), start_cursor);
                solved = false;
                revealed = true;
                for key in parse_keys(&get_str(lesson, "solution")) {
                    v.key(key);
                    let _ = input::poll_key(Duration::from_millis(160))?;
                }
                if check(&v) {
                    solved = true;
                }
                continue;
            }
            _ => {}
        }
        if ctrl(&k, 'n') {
            return Ok(Outcome::Next);
        }
        let kc = match input::to_char(&k) {
            Some(c) => c,
            None => continue,
        };
        v.message.clear();
        v.key(kc);

        if v.quit {
            return Ok(Outcome::Back);
        }
        if !solved && check(&v) {
            solved = true;
            if !revealed {
                if let Some(cb) = on_solved.as_mut() {
                    cb();
                } else {
                    prog.mark_done(track, &get_str(lesson, "id"), Some(json!({"keys": v.typed})), cur);
                }
            }
        }
    }
}

// ============================================================== PYTHON
pub fn run_quiz(
    term: &mut Term,
    lesson: &Value,
    prog: &mut Progress,
    cur: &Curriculum,
    track: &str,
    mut on_answered: Option<&mut dyn FnMut(bool)>,
) -> io::Result<Outcome> {
    let options: Vec<String> = lesson["options"].as_array().unwrap().iter().map(|v| v.as_str().unwrap_or("").to_string()).collect();
    let answer = get_u64(lesson, "answer", 0) as usize;
    let mut picked: Option<usize> = None;

    loop {
        let (h, w) = ui::size(term)?;
        let area = Rect::new(0, 0, w as u16, h as u16);
        let block = ui::chrome(&format!("TRÍADA › {}", get_str(lesson, "title")), ui::track_color(track));
        let inner = block.inner(area);
        let (body, foot) = ui::body_footer(inner);
        let width = 92.min((body.width as usize).saturating_sub(2)).max(1);

        let teach = get_str(lesson, "teach");
        let (teach_para_lines, teach_h) = teach_lines(&teach, width, 4);
        let teach_reserved = if teach_h > 0 { teach_h + 1 } else { 0 };

        let question_rows = render_markdown(&get_str(lesson, "question"), width);
        let question_h = question_rows.len() as u16;
        let question_lines = rows_to_lines(&question_rows);

        let opt_width = width.saturating_sub(6);
        let mut option_items: Vec<ListItem> = Vec::new();
        let mut options_h: u16 = 0;
        for (i, opt) in options.iter().enumerate() {
            let attr = if let Some(p) = picked {
                if i == answer {
                    ui::ok().add_modifier(Modifier::BOLD)
                } else if i == p {
                    ui::bad()
                } else {
                    ui::dim()
                }
            } else {
                Style::default()
            };
            let num_style = if picked.is_none() { ui::accent() } else { attr };
            let rows = render_markdown(opt, opt_width);
            let body_lines = rows_to_lines(&rows);
            let mut lines: Vec<Line> = Vec::new();
            for (j, l) in body_lines.into_iter().enumerate() {
                let mut spans = if j == 0 {
                    vec![Span::styled(format!("{:<4}", format!("{}.", i + 1)), num_style)]
                } else {
                    vec![Span::raw("    ")]
                };
                spans.extend(l.spans);
                lines.push(Line::from(spans));
            }
            options_h += lines.len().max(1) as u16;
            option_items.push(ListItem::new(lines));
        }

        let mut feedback_lines: Vec<Line> = Vec::new();
        if let Some(p) = picked {
            let right = p == answer;
            feedback_lines.push(Line::styled(if right { "Correct." } else { "Not quite." }, (if right { ui::ok() } else { ui::bad() }).add_modifier(Modifier::BOLD)));
            feedback_lines.extend(rows_to_lines(&render_markdown(&get_str(lesson, "why"), width)));
        }

        let chunks = Layout::vertical([
            Constraint::Length(teach_reserved),
            Constraint::Length(question_h),
            Constraint::Length(1),
            Constraint::Length(options_h),
            Constraint::Length(1),
            Constraint::Min(0),
        ])
        .split(body);

        term.draw(|f| {
            f.render_widget(block, area);
            ui::footer(f, foot, if picked.is_none() { "1-4 answer · ^N next · Esc back" } else { "^N next · Esc back" });
            if teach_h > 0 {
                f.render_widget(Paragraph::new(teach_para_lines), chunks[0]);
            }
            f.render_widget(Paragraph::new(question_lines), chunks[1]);
            f.render_widget(List::new(option_items), chunks[3]);
            f.render_widget(Paragraph::new(feedback_lines), chunks[5]);
        })?;

        let k = input::read_key()?;
        if matches!(k.code, KeyCode::Esc | KeyCode::F(10)) {
            return Ok(Outcome::Back);
        }
        if ctrl(&k, 'n') {
            return Ok(Outcome::Next);
        }
        if picked.is_none() {
            if let KeyCode::Char(c) = k.code {
                if ('1'..='4').contains(&c) {
                    let n = c as usize - '1' as usize;
                    if n < options.len() {
                        picked = Some(n);
                        let ok = n == answer;
                        if let Some(cb) = on_answered.as_mut() {
                            cb(ok);
                        } else if ok {
                            prog.mark_done(track, &get_str(lesson, "id"), None, cur);
                        } else {
                            prog.mark_tried(track, &get_str(lesson, "id"));
                        }
                    }
                }
            }
        }
    }
}

pub fn run_output(term: &mut Term, lesson: &Value, prog: &mut Progress, cur: &Curriculum) -> io::Result<Outcome> {
    let mut answer: Vec<String> = vec![String::new()];
    let mut row = 0usize;
    let mut checked: Option<bool> = None;

    loop {
        let (h, w) = ui::size(term)?;
        let area = Rect::new(0, 0, w as u16, h as u16);
        let block = ui::chrome(&format!("TRÍADA › {}", get_str(lesson, "title")), ui::PYTHON);
        let inner = block.inner(area);
        let (body, foot) = ui::body_footer(inner);
        let width = 92.min((body.width as usize).saturating_sub(2)).max(1);

        let teach = get_str(lesson, "teach");
        let (teach_para_lines, teach_h) = teach_lines(&teach, width, 3);
        let teach_reserved = if teach_h > 0 { teach_h + 1 } else { 0 };

        let code_str = get_str(lesson, "code");
        let code_lines: Vec<&str> = code_str.split('\n').collect();
        let code_h = code_lines.len() as u16 + 2;
        let answer_h = (answer.len() as u16 + 2).max(3);

        let mut feedback: Vec<Line> = Vec::new();
        if let Some(ok) = checked {
            feedback.push(Line::styled(
                if ok { "✓ Exactly right." } else { "· Not the actual output." },
                (if ok { ui::ok() } else { ui::bad() }).add_modifier(Modifier::BOLD),
            ));
            if !ok {
                feedback.push(Line::styled("actual:", ui::dim()));
                for line in get_str(lesson, "answer").split('\n') {
                    feedback.push(Line::styled(line.to_string(), ui::ok()));
                }
            }
            feedback.extend(rows_to_lines(&render_markdown(&get_str(lesson, "why"), width)));
        }

        let chunks = Layout::vertical([
            Constraint::Length(teach_reserved),
            Constraint::Length(code_h),
            Constraint::Length(answer_h),
            Constraint::Min(0),
        ])
        .split(body);

        let code_block = Block::bordered().border_type(BorderType::Rounded).border_style(ui::dim()).title(Span::styled(" What does this print? ", ui::bold()));
        let code_inner = code_block.inner(chunks[1]);
        let code_para = Paragraph::new(code_lines.iter().map(|l| Line::styled(l.to_string(), ui::code())).collect::<Vec<_>>());

        let answer_block =
            Block::bordered().border_type(BorderType::Rounded).border_style(ui::accent()).title(Span::styled(" Your answer ", ui::accent_bold()));
        let answer_inner = answer_block.inner(chunks[2]);
        let answer_para = Paragraph::new(answer.iter().map(|l| Line::raw(l.clone())).collect::<Vec<_>>());

        term.draw(|f| {
            f.render_widget(block, area);
            ui::footer(f, foot, "type the output · ^D check · ^R clear · ^N next · Esc back");
            if teach_h > 0 {
                f.render_widget(Paragraph::new(teach_para_lines), chunks[0]);
            }
            f.render_widget(code_block, chunks[1]);
            f.render_widget(code_para, code_inner);
            f.render_widget(answer_block, chunks[2]);
            f.render_widget(answer_para, answer_inner);
            f.render_widget(Paragraph::new(feedback), chunks[3]);
        })?;

        let k = input::read_key()?;
        if matches!(k.code, KeyCode::Esc | KeyCode::F(10)) {
            return Ok(Outcome::Back);
        }
        if ctrl(&k, 'n') {
            return Ok(Outcome::Next);
        }
        if ctrl(&k, 'r') {
            answer = vec![String::new()];
            row = 0;
            checked = None;
            continue;
        }
        if ctrl(&k, 'd') {
            let got = answer.join("\n").trim_end_matches('\n').to_string();
            let want = get_str(lesson, "answer").trim_end_matches('\n').to_string();
            let ok = got == want;
            checked = Some(ok);
            let id = get_str(lesson, "id");
            if ok {
                prog.mark_done("python", &id, None, cur);
            } else {
                prog.mark_tried("python", &id);
            }
            continue;
        }
        if matches!(k.code, KeyCode::Backspace) {
            if !answer[row].is_empty() {
                answer[row].pop();
            } else if row > 0 {
                answer.remove(row);
                row -= 1;
            }
            continue;
        }
        if matches!(k.code, KeyCode::Enter) {
            answer.insert(row + 1, String::new());
            row += 1;
            continue;
        }
        if let KeyCode::Char(c) = k.code {
            if !k.modifiers.contains(KeyModifiers::CONTROL) && (c as u32) >= 32 {
                answer[row].push(c);
            }
        }
    }
}

fn editor_command() -> String {
    if let Ok(ed) = std::env::var("VISUAL").or_else(|_| std::env::var("EDITOR")) {
        if !ed.is_empty() {
            return ed;
        }
    }
    for cand in ["nvim", "vim", "vi", "nano"] {
        if which(cand) {
            return cand.to_string();
        }
    }
    "vi".to_string()
}

fn which(cmd: &str) -> bool {
    Command::new("which").arg(cmd).output().map(|o| o.status.success()).unwrap_or(false)
}

pub fn run_code(term: &mut Term, lesson: &Value, prog: &mut Progress, cur: &Curriculum) -> io::Result<Outcome> {
    let id = get_str(lesson, "id");
    let dir = std::env::temp_dir().join(format!("triada-{}", std::process::id()));
    std::fs::create_dir_all(&dir)?;
    let path = dir.join(format!("{}.py", id));
    std::fs::write(&path, get_str(lesson, "starter"))?;
    let mut output: Option<(bool, String)> = None;

    let run_tests = |path: &std::path::Path| -> (bool, String) {
        let src = std::fs::read_to_string(path).unwrap_or_default();
        let runner = path.with_file_name("_run.py");
        let content = format!("{}\n\n{}\nprint('__TRIADA_OK__')\n", src, get_str(lesson, "tests"));
        if std::fs::write(&runner, content).is_err() {
            return (false, "could not write test runner".to_string());
        }
        let out = Command::new("python3").arg(&runner).output();
        match out {
            Ok(o) => {
                let stdout = String::from_utf8_lossy(&o.stdout).to_string();
                let stderr = String::from_utf8_lossy(&o.stderr).to_string();
                if stdout.contains("__TRIADA_OK__") {
                    let extra = stdout.replace("__TRIADA_OK__\n", "").trim().to_string();
                    (true, if extra.is_empty() { "all tests passed".to_string() } else { format!("all tests passed\n\nstdout:\n{}", extra) })
                } else {
                    let err = if !stderr.trim().is_empty() { stderr.trim().to_string() } else if !stdout.trim().is_empty() { stdout.trim().to_string() } else { "no output".to_string() };
                    let tail: String = err.chars().rev().take(1600).collect::<Vec<_>>().into_iter().rev().collect();
                    (false, tail)
                }
            }
            Err(e) => (false, format!("failed to run python3: {}", e)),
        }
    };

    loop {
        let (h, w) = ui::size(term)?;
        let area = Rect::new(0, 0, w as u16, h as u16);
        let block = ui::chrome(&format!("TRÍADA › {}", get_str(lesson, "title")), ui::PYTHON);
        let inner = block.inner(area);
        let (body, foot) = ui::body_footer(inner);
        let width = 92.min((body.width as usize).saturating_sub(2)).max(1);

        let teach = get_str(lesson, "teach");
        let (teach_para_lines, teach_h) = teach_lines(&teach, width, 4);
        let teach_reserved = if teach_h > 0 { teach_h + 1 } else { 0 };

        let prompt_rows = render_markdown(&get_str(lesson, "prompt"), width);
        let prompt_h = (prompt_rows.len() as u16 + 2).min(h as u16 / 2);
        let prompt_lines = rows_to_lines(&prompt_rows);

        let cur_src = std::fs::read_to_string(&path).unwrap_or_default();
        let src_lines: Vec<&str> = cur_src.split('\n').collect();
        let remaining = (body.height as usize).saturating_sub(teach_reserved as usize + prompt_h as usize + 5);
        let file_h = (src_lines.len().min(remaining.max(4)) as u16 + 2).max(4);

        let chunks = Layout::vertical([
            Constraint::Length(teach_reserved),
            Constraint::Length(prompt_h),
            Constraint::Length(file_h),
            Constraint::Min(3),
        ])
        .split(body);

        let prompt_block = Block::bordered().border_type(BorderType::Rounded).border_style(ui::dim()).title(Span::styled(" Prompt ", ui::bold()));
        let prompt_inner = prompt_block.inner(chunks[1]);

        let file_border = ui::PYTHON;
        let file_block = Block::bordered()
            .border_type(BorderType::Rounded)
            .border_style(Style::default().fg(file_border))
            .title(Span::styled(format!(" {} ", path.display()), Style::default().fg(file_border)));
        let file_inner = file_block.inner(chunks[2]);
        let file_para = Paragraph::new(src_lines.iter().take(file_inner.height as usize).map(|l| Line::styled(l.to_string(), ui::code())).collect::<Vec<_>>());

        let (result_color, result_lines): (ratatui::style::Color, Vec<Line>) = match &output {
            Some((ok, text)) => {
                let color = if *ok { ui::OK } else { ui::BAD };
                let style = if *ok { ui::ok() } else { ui::bad() };
                let mut lines = vec![Line::styled(if *ok { "✓ passed" } else { "✗ failed" }, style.add_modifier(Modifier::BOLD))];
                lines.extend(text.split('\n').map(|l| Line::styled(l.to_string(), style)));
                (color, lines)
            }
            None => (ui::DIM, vec![Line::styled("no result yet — press r to run the tests", ui::dim())]),
        };
        let result_block = Block::bordered().border_type(BorderType::Rounded).border_style(Style::default().fg(result_color)).title(Span::styled(" Result ", ui::bold()));
        let result_inner = result_block.inner(chunks[3]);
        let result_para = Paragraph::new(result_lines).wrap(Wrap { trim: false });

        let ed = editor_command();

        term.draw(|f| {
            f.render_widget(block, area);
            ui::footer(f, foot, &format!("e edit in {} · r run tests · s solution · x reset · t tests · ^N next · Esc back", ed));
            if teach_h > 0 {
                f.render_widget(Paragraph::new(teach_para_lines), chunks[0]);
            }
            f.render_widget(prompt_block, chunks[1]);
            f.render_widget(Paragraph::new(prompt_lines).wrap(Wrap { trim: false }), prompt_inner);
            f.render_widget(file_block, chunks[2]);
            f.render_widget(file_para, file_inner);
            f.render_widget(result_block, chunks[3]);
            f.render_widget(result_para, result_inner);
        })?;

        let k = input::read_key()?;
        if matches!(k.code, KeyCode::Esc | KeyCode::F(10)) {
            return Ok(Outcome::Back);
        }
        if ctrl(&k, 'n') {
            return Ok(Outcome::Next);
        }
        match k.code {
            KeyCode::Char('e') => {
                crossterm::terminal::disable_raw_mode()?;
                crossterm::execute!(std::io::stdout(), crossterm::terminal::LeaveAlternateScreen)?;
                let parts: Vec<&str> = ed.split_whitespace().collect();
                if let Some((prog_cmd, args)) = parts.split_first() {
                    let _ = Command::new(prog_cmd).args(args).arg(&path).status();
                }
                crossterm::execute!(std::io::stdout(), crossterm::terminal::EnterAlternateScreen)?;
                crossterm::terminal::enable_raw_mode()?;
                term.clear()?;
                continue;
            }
            KeyCode::Char('r') => {
                let res = run_tests(&path);
                if res.0 {
                    prog.mark_done("python", &id, None, cur);
                } else {
                    prog.mark_tried("python", &id);
                }
                output = Some(res);
                continue;
            }
            KeyCode::Char('s') => {
                std::fs::write(&path, get_str(lesson, "solution"))?;
                output = Some((false, "solution written to the file — read it, then reset with 'x' and do it yourself".to_string()));
                continue;
            }
            KeyCode::Char('x') => {
                std::fs::write(&path, get_str(lesson, "starter"))?;
                output = None;
                continue;
            }
            KeyCode::Char('t') => {
                let tests = get_str(lesson, "tests");
                if !tests.is_empty() {
                    pager(term, "Tests this must pass", &format!("```\n{}\n```", tests))?;
                }
                continue;
            }
            _ => {}
        }
    }
}
