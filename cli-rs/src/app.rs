//! The application: home, track, level and lesson navigation. Port of app.py.

use crate::curriculum::{self, Curriculum, TRACKS};
use crate::drills::{self, Outcome};
use crate::input;
use crate::progress::Progress;
use crate::ui::{self, Term};
use crossterm::event::KeyCode;
use ratatui::layout::{Alignment, Constraint, Layout, Rect};
use ratatui::style::{Modifier, Style};
use ratatui::text::{Line, Span};
use ratatui::widgets::{Block, BorderType, Clear, Gauge, LineGauge, List, ListItem, ListState, Paragraph, Wrap};
use serde_json::{json, Value};
use std::io;
use std::time::Duration;

fn label(track: &str) -> &'static str {
    match track {
        "typing" => "Touch Typing",
        "nvim" => "Neovim",
        "python" => "Python",
        _ => "?",
    }
}

pub struct App {
    pub cur: Curriculum,
    pub prog: Progress,
}

impl App {
    pub fn new() -> Result<Self, String> {
        let cur = curriculum::load_all()?;
        let prog = Progress::new(&cur);
        Ok(App { cur, prog })
    }

    pub fn run(&mut self, term: &mut Term, start: Option<&str>) -> io::Result<()> {
        if let Some(id) = start {
            self.open_lesson_by_id(term, id)?;
        }
        loop {
            if self.home(term)? {
                return Ok(());
            }
        }
    }

    fn toast(&self, term: &mut Term, msg: &str) -> io::Result<()> {
        term.draw(|f| {
            let area = f.area();
            let w = (msg.chars().count() as u16 + 4).min(area.width.saturating_sub(4)).max(12);
            let h = 3u16;
            let x = area.x + area.width.saturating_sub(w) / 2;
            let y = area.y + area.height.saturating_sub(h) / 2;
            let popup = Rect::new(x, y, w, h);
            f.render_widget(Clear, popup);
            let block = Block::bordered().border_type(BorderType::Rounded).border_style(ui::accent());
            let inner = block.inner(popup);
            f.render_widget(block, popup);
            f.render_widget(Paragraph::new(Line::styled(msg.to_string(), ui::accent())).alignment(Alignment::Center), inner);
        })?;
        std::thread::sleep(Duration::from_millis(1300));
        Ok(())
    }

    // ------------------------------------------------------------ home
    /// Returns true when the user asked to quit.
    fn home(&mut self, term: &mut Term) -> io::Result<bool> {
        let rows: Vec<(&str, Option<&str>)> = vec![
            ("track", Some("typing")),
            ("track", Some("nvim")),
            ("track", Some("python")),
            ("combos", None),
            ("stats", None),
        ];
        let mut sel = 0usize;
        loop {
            term.draw(|f| {
                let area = f.area();
                let block = ui::chrome("TRÍADA", ui::DIM);
                let inner = block.inner(area);
                f.render_widget(block, area);
                let (body, foot) = ui::body_footer(inner);
                ui::footer(f, foot, "j/k move · Enter open · 1/2/3 track · c combos · s stats · ? help · q quit");

                let chunks = Layout::vertical([
                    Constraint::Length(3),
                    Constraint::Length(5),
                    Constraint::Length(5),
                    Constraint::Length(5),
                    Constraint::Length(3),
                    Constraint::Length(3),
                    Constraint::Min(0),
                ])
                .split(body);

                let header = Paragraph::new(vec![
                    Line::from(vec![Span::styled("TRÍADA", ui::accent_bold()), Span::raw("   "), Span::styled("type · edit · program", ui::dim())]),
                    Line::styled("Three skills, one keyboard.", ui::bold()),
                    Line::styled("Progress in each track is independent — go expert in one while you start another.", ui::dim()),
                ]);
                f.render_widget(header, chunks[0]);

                for (i, t) in TRACKS.iter().enumerate() {
                    let on = sel == i;
                    let st = self.prog.stats(t, &self.cur);
                    let levels = self.cur.levels(t);
                    let lvidx = st.level.min(st.levels).max(1) - 1;
                    let lv = &levels[lvidx];
                    let color = ui::track_color(t);
                    let card = Block::bordered()
                        .border_type(if on { BorderType::Thick } else { BorderType::Rounded })
                        .border_style(Style::default().fg(if on { color } else { ui::DIM }))
                        .title(Span::styled(format!(" {} ", label(t)), Style::default().fg(color).add_modifier(Modifier::BOLD)));
                    let ci = card.inner(chunks[1 + i]);
                    f.render_widget(card, chunks[1 + i]);
                    let inner_rows = Layout::vertical([Constraint::Length(1), Constraint::Length(1), Constraint::Length(1)]).split(ci);
                    let gauge = LineGauge::default().ratio(st.pct).filled_style(Style::default().fg(color)).unfilled_style(ui::dim());
                    f.render_widget(gauge, inner_rows[0]);
                    f.render_widget(
                        Paragraph::new(Line::styled(format!("{:3}/{:<4} lessons · level {}/{}", st.done, st.total, st.level, st.levels), ui::dim())),
                        inner_rows[1],
                    );
                    f.render_widget(
                        Paragraph::new(Line::styled(format!("next: L{} · {}", lv["n"].as_u64().unwrap_or(0), lv["title"].as_str().unwrap_or("")), ui::dim())),
                        inner_rows[2],
                    );
                }

                let combos = self.cur.combos["combos"].as_array().cloned().unwrap_or_default();
                let n_open = combos.iter().filter(|c| self.combo_open(c)).count();
                let n_done = combos.iter().filter(|c| self.prog.data["combos"].get(c["id"].as_str().unwrap_or("")).is_some()).count();
                let on = sel == 3;
                let cb_block = Block::bordered()
                    .border_type(if on { BorderType::Thick } else { BorderType::Rounded })
                    .border_style(Style::default().fg(if on { ui::ACCENT } else { ui::DIM }))
                    .title(Span::styled(" Combos ", ui::accent_bold()));
                let cbi = cb_block.inner(chunks[4]);
                f.render_widget(cb_block, chunks[4]);
                f.render_widget(
                    Paragraph::new(Line::styled(
                        format!("{} done · {}/{} unlocked — one task, all three skills", n_done, n_open, combos.len()),
                        ui::dim(),
                    )),
                    cbi,
                );

                let on = sel == 4;
                let st_block = Block::bordered()
                    .border_type(if on { BorderType::Thick } else { BorderType::Rounded })
                    .border_style(Style::default().fg(if on { ui::HEAD } else { ui::DIM }))
                    .title(Span::styled(" Stats & data ", ui::head_bold()));
                let sti = st_block.inner(chunks[5]);
                f.render_widget(st_block, chunks[5]);
                f.render_widget(Paragraph::new(Line::styled("overall progress, best wpm and the keys you miss most", ui::dim())), sti);
            })?;

            let k = input::read_key()?;
            match k.code {
                KeyCode::Char('q') => return Ok(true),
                KeyCode::Char('j') | KeyCode::Down => sel = (sel + 1) % rows.len(),
                KeyCode::Char('k') | KeyCode::Up => sel = (sel + rows.len() - 1) % rows.len(),
                KeyCode::Char('?') => self.help(term)?,
                KeyCode::Char(c) if ('1'..='3').contains(&c) => {
                    self.view_track(term, TRACKS[c as usize - '1' as usize])?;
                }
                KeyCode::Char('c') => self.view_combos(term)?,
                KeyCode::Char('s') => self.view_stats(term)?,
                KeyCode::Enter | KeyCode::Right | KeyCode::Char('l') => {
                    let (kind, t) = rows[sel];
                    if kind == "track" {
                        self.view_track(term, t.unwrap())?;
                    } else if kind == "combos" {
                        self.view_combos(term)?;
                    } else {
                        self.view_stats(term)?;
                    }
                }
                _ => {}
            }
        }
    }

    // ------------------------------------------------------------ track
    fn view_track(&mut self, term: &mut Term, track: &str) -> io::Result<()> {
        let levels = self.cur.levels(track).to_vec();
        let mut sel = self.prog.unlocked(track).min(levels.len()).saturating_sub(1);
        let mut list_state = ListState::default();
        loop {
            list_state.select(Some(sel));
            let doc = self.cur.get(track);
            let title = doc["title"].as_str().unwrap_or("").to_string();
            let subtitle = doc["subtitle"].as_str().unwrap_or("").to_string();
            let st = self.prog.stats(track, &self.cur);
            term.draw(|f| {
                let area = f.area();
                let block = ui::chrome(&format!("TRÍADA › {}", title), ui::track_color(track));
                let inner = block.inner(area);
                f.render_widget(block, area);
                let (body, foot) = ui::body_footer(inner);
                ui::footer(f, foot, "j/k move · Enter open level · b brief · Esc back");

                let chunks = Layout::vertical([Constraint::Length(1), Constraint::Length(1), Constraint::Length(1), Constraint::Min(3)]).split(body);
                f.render_widget(Paragraph::new(Line::styled(subtitle.clone(), ui::dim())), chunks[0]);
                let gauge = Gauge::default()
                    .ratio(st.pct)
                    .gauge_style(Style::default().fg(ui::track_color(track)))
                    .label(format!("{}/{} lessons", st.done, st.total));
                f.render_widget(gauge, chunks[1]);

                let inner_w = chunks[3].width as usize;
                let items: Vec<ListItem> = levels
                    .iter()
                    .enumerate()
                    .map(|(i, lv)| {
                        let n = lv["n"].as_u64().unwrap_or(0);
                        let locked = n as usize > self.prog.unlocked(track);
                        let complete = self.prog.level_complete(track, lv);
                        let dn = lv["lessons"]
                            .as_array()
                            .map(|a| a.iter().filter(|ls| self.prog.done(track, ls["id"].as_str().unwrap_or(""))).count())
                            .unwrap_or(0);
                        let total = lv["lessons"].as_array().map(|a| a.len()).unwrap_or(0);
                        let glyph = if locked { "🔒" } else if complete { "✓" } else { " " };
                        let title_str = lv["title"].as_str().unwrap_or("");
                        let left_plain = format!("{} {:>2}  {}", glyph, n, title_str);
                        let right = format!("{}/{}", dn, total);
                        let pad = inner_w.saturating_sub(left_plain.chars().count() + right.chars().count()).max(1);
                        let style = if locked { ui::dim() } else if complete { ui::ok() } else { Style::default() };
                        let line1 = Line::from(vec![
                            Span::styled(format!("{} {:>2}  ", glyph, n), style),
                            Span::styled(title_str.to_string(), style),
                            Span::raw(" ".repeat(pad)),
                            Span::styled(right, ui::dim()),
                        ]);
                        let mut lines = vec![line1];
                        if i == sel && !locked {
                            let goal_str = lv["goal"].as_str().unwrap_or("");
                            lines.push(Line::styled(format!("      {}", goal_str), ui::dim()));
                        }
                        ListItem::new(lines)
                    })
                    .collect();
                let list = List::new(items).highlight_style(ui::chip(ui::track_color(track)));
                f.render_stateful_widget(list, chunks[3], &mut list_state);
            })?;

            let k = input::read_key()?;
            match k.code {
                KeyCode::Esc | KeyCode::Char('q') | KeyCode::Left => return Ok(()),
                KeyCode::Char('j') | KeyCode::Down => sel = (sel + 1) % levels.len(),
                KeyCode::Char('k') | KeyCode::Up => sel = (sel + levels.len() - 1) % levels.len(),
                KeyCode::Char('b') => {
                    let lv = &levels[sel];
                    drills::pager(
                        term,
                        &format!("Level {} · {}", lv["n"].as_u64().unwrap_or(0), lv["title"].as_str().unwrap_or("")),
                        lv["brief"].as_str().unwrap_or(""),
                    )?;
                }
                KeyCode::Enter | KeyCode::Right | KeyCode::Char('l') => {
                    let lv = &levels[sel];
                    let n = lv["n"].as_u64().unwrap_or(0) as usize;
                    if n > self.prog.unlocked(track) {
                        self.toast(term, &format!("Finish level {} first — every lesson in it.", n.saturating_sub(1)))?;
                    } else {
                        self.view_level(term, track, lv)?;
                    }
                }
                _ => {}
            }
        }
    }

    // ------------------------------------------------------------ level
    fn view_level(&mut self, term: &mut Term, track: &str, lv: &Value) -> io::Result<()> {
        let lessons = lv["lessons"].as_array().cloned().unwrap_or_default();
        let mut sel = 0usize;
        for (i, ls) in lessons.iter().enumerate() {
            if !self.prog.done(track, ls["id"].as_str().unwrap_or("")) {
                sel = i;
                break;
            }
        }
        let links = lv.get("links").and_then(|l| l.as_array()).cloned().unwrap_or_default();
        let links_h: u16 = if links.is_empty() { 0 } else { links.len() as u16 + 2 };
        let lv_n = lv["n"].as_u64().unwrap_or(0);
        let lv_title = lv["title"].as_str().unwrap_or("").to_string();
        let lv_goal = lv["goal"].as_str().unwrap_or("").to_string();
        let mut list_state = ListState::default();

        loop {
            list_state.select(Some(sel));
            term.draw(|f| {
                let area = f.area();
                let block = ui::chrome(&format!("TRÍADA › {} › Level {}", label(track), lv_n), ui::track_color(track));
                let inner = block.inner(area);
                f.render_widget(block, area);
                let (body, foot) = ui::body_footer(inner);
                ui::footer(f, foot, "j/k move · Enter start · b level brief · Esc back");

                let chunks = Layout::vertical([
                    Constraint::Length(1),
                    Constraint::Length(1),
                    Constraint::Length(1),
                    Constraint::Min(3),
                    Constraint::Length(links_h),
                ])
                .split(body);
                f.render_widget(Paragraph::new(Line::styled(lv_title.clone(), ui::bold())), chunks[0]);
                f.render_widget(Paragraph::new(Line::styled(lv_goal.clone(), ui::dim())), chunks[1]);

                let inner_w = chunks[3].width as usize;
                let items: Vec<ListItem> = lessons
                    .iter()
                    .enumerate()
                    .map(|(i, ls)| {
                        let id = ls["id"].as_str().unwrap_or("");
                        let done = self.prog.done(track, id);
                        let kind = ls["kind"].as_str().unwrap_or("");
                        let tag = match kind {
                            "text" => "TYPE",
                            "drill" => "DRILL",
                            "quiz" => "QUIZ",
                            "output" => "OUT",
                            "code" => "CODE",
                            _ => "?",
                        };
                        let title_str = ls["title"].as_str().unwrap_or("");
                        let glyph = if done { "✓" } else { " " };
                        let rec = self.prog.record(track, id);
                        let right = if let Some(best) = rec.get("best") {
                            if let Some(wpm) = best.get("wpm").and_then(|v| v.as_u64()) {
                                let acc = best.get("acc").and_then(|v| v.as_f64()).unwrap_or(0.0);
                                format!("{} wpm · {}%", wpm, (acc * 100.0) as u64)
                            } else if let Some(keys) = best.get("keys").and_then(|v| v.as_u64()) {
                                let par = ls.get("par").and_then(|v| v.as_u64()).map(|n| n.to_string()).unwrap_or_else(|| "-".to_string());
                                format!("{} keys (par {})", keys, par)
                            } else {
                                String::new()
                            }
                        } else {
                            String::new()
                        };
                        let left_plain = format!("{} {:<5}  {}", glyph, tag, title_str);
                        let pad = inner_w.saturating_sub(left_plain.chars().count() + right.chars().count()).max(1);
                        let title_style = if i == sel { Style::default().add_modifier(Modifier::BOLD) } else { Style::default() };
                        let line1 = Line::from(vec![
                            Span::styled(format!("{} ", glyph), if done { ui::ok() } else { Style::default() }),
                            Span::styled(format!("{:<5} ", tag), ui::chip(ui::track_color(track))),
                            Span::raw(" "),
                            Span::styled(title_str.to_string(), title_style),
                            Span::raw(" ".repeat(pad)),
                            Span::styled(right, ui::dim()),
                        ]);
                        ListItem::new(vec![line1])
                    })
                    .collect();
                let list = List::new(items).highlight_style(ui::chip(ui::track_color(track)));
                f.render_stateful_widget(list, chunks[3], &mut list_state);

                if !links.is_empty() {
                    let lb = Block::bordered().border_type(BorderType::Rounded).border_style(ui::accent()).title(Span::styled(" Cross-track ", ui::accent_bold()));
                    let li = lb.inner(chunks[4]);
                    f.render_widget(lb, chunks[4]);
                    let lines: Vec<Line> = links
                        .iter()
                        .map(|lk| {
                            let track2 = lk["track"].as_str().unwrap_or("");
                            Line::styled(format!("↔ {}: {}", label(track2), lk["note"].as_str().unwrap_or("")), ui::accent())
                        })
                        .collect();
                    f.render_widget(Paragraph::new(lines).wrap(Wrap { trim: false }), li);
                }
            })?;

            let k = input::read_key()?;
            match k.code {
                KeyCode::Esc | KeyCode::Char('q') | KeyCode::Left => return Ok(()),
                KeyCode::Char('j') | KeyCode::Down => sel = (sel + 1) % lessons.len(),
                KeyCode::Char('k') | KeyCode::Up => sel = (sel + lessons.len() - 1) % lessons.len(),
                KeyCode::Char('b') => {
                    drills::pager(term, &format!("Level {} · {}", lv_n, lv_title), lv["brief"].as_str().unwrap_or(""))?;
                }
                KeyCode::Enter | KeyCode::Right => loop {
                    let res = self.run_lesson(term, track, &lessons[sel])?;
                    if matches!(res, Outcome::Next) && sel + 1 < lessons.len() {
                        sel += 1;
                        continue;
                    }
                    break;
                },
                _ => {}
            }
        }
    }

    // ----------------------------------------------------------- lesson
    fn run_lesson(&mut self, term: &mut Term, track: &str, ls: &Value) -> io::Result<Outcome> {
        let kind = ls["kind"].as_str().unwrap_or("");
        if track == "typing" {
            return drills::run_typing(term, ls, None, &mut self.prog, &self.cur, "typing");
        }
        if track == "nvim" {
            if kind == "quiz" {
                return drills::run_quiz(term, ls, &mut self.prog, &self.cur, "nvim", None);
            }
            return drills::run_vim(term, ls, &mut self.prog, &self.cur, "nvim", None);
        }
        if kind == "quiz" {
            return drills::run_quiz(term, ls, &mut self.prog, &self.cur, "python", None);
        }
        if kind == "output" {
            return drills::run_output(term, ls, &mut self.prog, &self.cur);
        }
        drills::run_code(term, ls, &mut self.prog, &self.cur)
    }

    pub fn open_lesson_by_id(&mut self, term: &mut Term, lesson_id: &str) -> io::Result<()> {
        let found = curriculum::find_lesson(&self.cur, lesson_id).map(|(t, _lv, ls)| (t.to_string(), ls.clone()));
        if let Some((track, ls)) = found {
            self.run_lesson(term, &track, &ls)?;
        }
        Ok(())
    }

    // ----------------------------------------------------------- combos
    fn combo_open(&self, cb: &Value) -> bool {
        TRACKS.iter().all(|t| self.prog.unlocked(t) >= cb["needs"][t].as_u64().unwrap_or(0) as usize)
    }

    fn view_combos(&mut self, term: &mut Term) -> io::Result<()> {
        let combos = self.cur.combos["combos"].as_array().cloned().unwrap_or_default();
        let mut sel = 0usize;
        let mut list_state = ListState::default();
        loop {
            list_state.select(Some(sel));
            term.draw(|f| {
                let area = f.area();
                let block = ui::chrome("TRÍADA › Combos", ui::ACCENT);
                let inner = block.inner(area);
                f.render_widget(block, area);
                let (body, foot) = ui::body_footer(inner);
                ui::footer(f, foot, "j/k move · Enter start · Esc back");

                let chunks = Layout::vertical([Constraint::Length(1), Constraint::Length(1), Constraint::Min(3)]).split(body);
                f.render_widget(
                    Paragraph::new(Line::styled("Type it, edit it, explain it. Optional — they never block a track.", ui::dim())),
                    chunks[0],
                );
                let inner_w = chunks[2].width as usize;
                let items: Vec<ListItem> = combos
                    .iter()
                    .enumerate()
                    .map(|(i, cb)| {
                        let open = self.combo_open(cb);
                        let done = self.prog.data["combos"].get(cb["id"].as_str().unwrap_or("")).is_some();
                        let style = if !open { ui::dim() } else if done { ui::ok() } else { Style::default() };
                        let glyph = if done { "✓" } else if !open { "🔒" } else { " " };
                        let title_str = cb["title"].as_str().unwrap_or("");
                        let left_plain = format!("{} {} {}", glyph, cb["n"].as_u64().unwrap_or(0), title_str);
                        let right = format!(
                            "T{} V{} P{}",
                            cb["needs"]["typing"].as_u64().unwrap_or(0),
                            cb["needs"]["nvim"].as_u64().unwrap_or(0),
                            cb["needs"]["python"].as_u64().unwrap_or(0)
                        );
                        let pad = inner_w.saturating_sub(left_plain.chars().count() + right.chars().count()).max(1);
                        let line1 = Line::from(vec![
                            Span::styled(format!("{} {} ", glyph, cb["n"].as_u64().unwrap_or(0)), style),
                            Span::styled(title_str.to_string(), style),
                            Span::raw(" ".repeat(pad)),
                            Span::styled(right, ui::dim()),
                        ]);
                        let mut lines = vec![line1];
                        if i == sel {
                            let brief = cb["brief"].as_str().unwrap_or("");
                            lines.push(Line::styled(format!("    {}", brief), ui::dim()));
                        }
                        ListItem::new(lines)
                    })
                    .collect();
                let list = List::new(items).highlight_style(ui::chip(ui::ACCENT));
                f.render_stateful_widget(list, chunks[2], &mut list_state);
            })?;

            let k = input::read_key()?;
            match k.code {
                KeyCode::Esc | KeyCode::Char('q') | KeyCode::Left => return Ok(()),
                KeyCode::Char('j') | KeyCode::Down => sel = (sel + 1) % combos.len(),
                KeyCode::Char('k') | KeyCode::Up => sel = (sel + combos.len() - 1) % combos.len(),
                KeyCode::Enter | KeyCode::Right => {
                    let cb = &combos[sel];
                    if !self.combo_open(cb) {
                        self.toast(
                            term,
                            &format!(
                                "Needs typing L{}, Neovim L{}, Python L{}.",
                                cb["needs"]["typing"].as_u64().unwrap_or(0),
                                cb["needs"]["nvim"].as_u64().unwrap_or(0),
                                cb["needs"]["python"].as_u64().unwrap_or(0)
                            ),
                        )?;
                    } else {
                        self.run_combo(term, cb)?;
                    }
                }
                _ => {}
            }
        }
    }

    fn run_combo(&mut self, term: &mut Term, cb: &Value) -> io::Result<()> {
        let cb_id = cb["id"].as_str().unwrap_or("").to_string();
        let cb_title = cb["title"].as_str().unwrap_or("").to_string();
        let cb_n = cb["n"].as_u64().unwrap_or(0);

        let typ = json!({
            "id": format!("{}-t", cb_id),
            "title": format!("{} · 1/3 type it", cb_title),
            "kind": "text",
            "content": cb["typing"]["content"],
            "teach": "",
            "pass": {"wpm": 20 + cb_n * 2, "acc": 0.95},
        });
        let before = self.prog.data["typing"]["lessons"].clone();
        drills::run_typing(term, &typ, None, &mut self.prog, &self.cur, "typing")?;
        let typing_ok = self.prog.done("typing", typ["id"].as_str().unwrap());
        self.prog.data["typing"]["lessons"] = before; // combos do not count as typing lessons

        let mut vim = cb["vim"].clone();
        vim["id"] = json!(format!("{}-v", cb_id));
        vim["title"] = json!(format!("{} · 2/3 edit it", cb_title));
        vim["kind"] = json!("drill");
        vim["teach"] = json!("");
        let mut solved = false;
        drills::run_vim(term, &vim, &mut self.prog, &self.cur, "nvim", Some(&mut || solved = true))?;
        let vim_ok = solved;

        let mut q = cb["python"].clone();
        q["id"] = json!(format!("{}-q", cb_id));
        q["title"] = json!(format!("{} · 3/3 explain it", cb_title));
        q["teach"] = json!("");
        let mut quiz_ok = false;
        drills::run_quiz(term, &q, &mut self.prog, &self.cur, "python", Some(&mut |ok| quiz_ok = ok))?;

        if typing_ok && vim_ok && quiz_ok {
            self.prog.data["combos"].as_object_mut().unwrap().insert(cb_id.clone(), json!({"done": true}));
            self.prog.save();
            self.toast(term, "✓ Combo complete.")?;
        } else {
            let mut missing = Vec::new();
            if !typing_ok {
                missing.push("typing");
            }
            if !vim_ok {
                missing.push("vim");
            }
            if !quiz_ok {
                missing.push("quiz");
            }
            self.toast(term, &format!("Still to do: {}", missing.join(", ")))?;
        }
        Ok(())
    }

    // ------------------------------------------------------------ stats
    fn view_stats(&mut self, term: &mut Term) -> io::Result<()> {
        loop {
            let ks = self.prog.data["keyStats"].as_object().cloned().unwrap_or_default();
            let keys_h: u16 = 3;
            term.draw(|f| {
                let area = f.area();
                let block = ui::chrome("TRÍADA › Stats", ui::DIM);
                let inner = block.inner(area);
                f.render_widget(block, area);
                let (body, foot) = ui::body_footer(inner);
                ui::footer(f, foot, "Esc back");

                let chunks = Layout::vertical([
                    Constraint::Length(4),
                    Constraint::Length(4),
                    Constraint::Length(4),
                    Constraint::Length(keys_h),
                    Constraint::Length(2),
                    Constraint::Min(0),
                ])
                .split(body);

                for (i, t) in TRACKS.iter().enumerate() {
                    let st = self.prog.stats(t, &self.cur);
                    let mut best = 0u64;
                    if let Some(lessons) = self.prog.data[t]["lessons"].as_object() {
                        for rec in lessons.values() {
                            if let Some(wpm) = rec.get("best").and_then(|b| b.get("wpm")).and_then(|v| v.as_u64()) {
                                best = best.max(wpm);
                            }
                        }
                    }
                    let color = ui::track_color(t);
                    let card = Block::bordered()
                        .border_type(BorderType::Rounded)
                        .border_style(Style::default().fg(color))
                        .title(Span::styled(format!(" {} ", label(t)), Style::default().fg(color).add_modifier(Modifier::BOLD)));
                    let ci = card.inner(chunks[i]);
                    f.render_widget(card, chunks[i]);
                    let rows2 = Layout::vertical([Constraint::Length(1), Constraint::Length(1)]).split(ci);
                    let gauge = Gauge::default().ratio(st.pct).gauge_style(Style::default().fg(color));
                    f.render_widget(gauge, rows2[0]);
                    let mut line = format!("{:3}%   {}/{}   L{}", (st.pct * 100.0) as u64, st.done, st.total, st.level);
                    if best > 0 {
                        line += &format!("   best {} wpm", best);
                    }
                    f.render_widget(Paragraph::new(Line::styled(line, ui::dim())), rows2[1]);
                }

                let keys_block = Block::bordered().border_type(BorderType::Rounded).border_style(ui::dim()).title(Span::styled(" Keys you miss most ", ui::bold()));
                let ki = keys_block.inner(chunks[3]);
                f.render_widget(keys_block, chunks[3]);
                if ks.is_empty() {
                    f.render_widget(Paragraph::new(Line::styled("nothing recorded yet", ui::dim())), ki);
                } else {
                    let mut worst: Vec<(&String, &Value)> = ks.iter().collect();
                    worst.sort_by(|a, b| b.1.as_i64().unwrap_or(0).cmp(&a.1.as_i64().unwrap_or(0)));
                    worst.truncate(20);
                    let line = worst
                        .iter()
                        .map(|(k, n)| {
                            let label = if k.as_str() == " " { "␣".to_string() } else if k.as_str() == "\n" { "↵".to_string() } else { (*k).clone() };
                            format!("{}×{}", label, n.as_i64().unwrap_or(0))
                        })
                        .collect::<Vec<_>>()
                        .join("  ");
                    let line: String = line.chars().take(ki.width as usize).collect();
                    f.render_widget(Paragraph::new(Line::styled(line, ui::bad())), ki);
                }

                let footnote = Paragraph::new(vec![
                    Line::styled(format!("progress file: {}", crate::progress::progress_path().display()), ui::dim()),
                    Line::styled("the web app imports and exports exactly this file (Stats → Import JSON)", ui::dim()),
                ]);
                f.render_widget(footnote, chunks[4]);
            })?;
            let k = input::read_key()?;
            if matches!(k.code, KeyCode::Esc | KeyCode::Char('q') | KeyCode::Left) {
                return Ok(());
            }
        }
    }

    // ------------------------------------------------------------- misc
    fn help(&mut self, term: &mut Term) -> io::Result<()> {
        drills::pager(term, "Keyboard", HELP)
    }
}

const HELP: &str = "
## Everywhere

| Key | Does |
|---|---|
| `j` `k` or arrows | move |
| `Enter` | open |
| `Esc` or `q` | back |
| `1` `2` `3` | jump to a track |
| `c` | combos |
| `s` | stats |
| `?` | this list |

## Typing drills

| Key | Does |
|---|---|
| any key | types |
| `Backspace` | correct a mistake |
| `Ctrl-R` | restart the drill |
| `Ctrl-N` | next lesson |
| `Esc` | back |

Accuracy is measured on *first attempts*, so backspacing does not hide an error —
it just lets you finish. That is deliberate.

## Vim drills

Every key goes to the emulator, including `Esc`. To get out:

| Key | Does |
|---|---|
| `F10` or `ZZ` or `:q` | leave the drill |
| `F5` | reset the buffer |
| `F1` | toggle the hint |
| `F2` | replay the reference solution (does not count) |
| `Ctrl-N` | next lesson |

## Python exercises

| Key | Does |
|---|---|
| `e` | edit the file in `$EDITOR` (Neovim, ideally) |
| `r` | run the real tests with your own python3 |
| `s` | write the reference solution into the file |
| `x` | reset the file to the starter |
| `1`-`4` | answer a quiz |
| `Ctrl-D` | check a predicted output |

## Progress

Progress lives in `~/.triada/progress.json` and is the same format the web app
exports, so you can move a session between the two by copying one file.
";
