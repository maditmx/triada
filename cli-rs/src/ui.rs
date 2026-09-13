//! Colour palette and small shared UI helpers — port of the constants in ui.py.

use ratatui::backend::CrosstermBackend;
use ratatui::layout::{Constraint, Layout, Rect};
use ratatui::style::{Color, Modifier, Style};
use ratatui::text::{Line, Span};
use ratatui::widgets::{Block, BorderType, Paragraph};
use ratatui::Frame;
use std::io;

pub type Term = ratatui::Terminal<CrosstermBackend<std::io::Stdout>>;

/// A curses-like absolute-position character grid: put(y, x, text, style)
/// overwrites cells, mirroring ui.py's safe_addstr(). Rendered as a Paragraph
/// into an arbitrary sub-`Rect` of a `Frame` (typically a block's inner area).
pub struct Canvas {
    pub h: usize,
    pub w: usize,
    cells: Vec<(char, Style)>,
}

impl Canvas {
    pub fn new(h: usize, w: usize) -> Self {
        Canvas { h, w, cells: vec![(' ', Style::default()); h * w] }
    }

    fn idx(&self, y: usize, x: usize) -> usize {
        y * self.w + x
    }

    pub fn put(&mut self, y: usize, x: usize, text: &str, style: Style) {
        if y >= self.h || x >= self.w {
            return;
        }
        let mut xx = x;
        for ch in text.chars() {
            if xx >= self.w {
                break;
            }
            let idx = self.idx(y, xx);
            self.cells[idx] = (ch, style);
            xx += 1;
        }
    }

    /// port of draw_segments(): paint a run of (text, style) segments, clipped to maxw.
    pub fn put_segments(&mut self, y: usize, x: usize, segs: &[(String, Style)], maxw: usize) {
        let mut col = x;
        for (text, style) in segs {
            if col.saturating_sub(x) >= maxw {
                break;
            }
            let remaining = maxw - (col - x);
            let truncated: String = text.chars().take(remaining).collect();
            self.put(y, col, &truncated, *style);
            col += text.chars().count();
        }
    }

    pub fn to_lines(&self) -> Vec<Line<'static>> {
        let mut lines = Vec::with_capacity(self.h);
        for y in 0..self.h {
            let mut spans: Vec<Span<'static>> = Vec::new();
            let mut cur_text = String::new();
            let mut cur_style: Option<Style> = None;
            for x in 0..self.w {
                let (ch, style) = self.cells[self.idx(y, x)];
                match cur_style {
                    Some(s) if s == style => cur_text.push(ch),
                    _ => {
                        if !cur_text.is_empty() {
                            spans.push(Span::styled(std::mem::take(&mut cur_text), cur_style.unwrap()));
                        }
                        cur_style = Some(style);
                        cur_text.push(ch);
                    }
                }
            }
            if !cur_text.is_empty() {
                spans.push(Span::styled(cur_text, cur_style.unwrap()));
            }
            lines.push(Line::from(spans));
        }
        lines
    }

    /// Render this grid as a Paragraph into `area` of the current frame.
    pub fn render(&self, f: &mut Frame, area: Rect) {
        f.render_widget(Paragraph::new(self.to_lines()), area);
    }
}

pub fn size(term: &mut Term) -> io::Result<(usize, usize)> {
    let s = term.size()?;
    Ok((s.height as usize, s.width as usize))
}

pub const DIM: Color = Color::Indexed(244);
pub const ACCENT: Color = Color::Indexed(173);
pub const OK: Color = Color::Indexed(71);
pub const BAD: Color = Color::Indexed(167);
pub const TYPING: Color = Color::Indexed(72);
pub const NVIM: Color = Color::Indexed(74);
pub const PYTHON: Color = Color::Indexed(179);
pub const CODE: Color = Color::Indexed(139);
pub const HEAD: Color = Color::Indexed(109);

pub fn track_color(track: &str) -> Color {
    match track {
        "typing" => TYPING,
        "nvim" => NVIM,
        "python" => PYTHON,
        _ => DIM,
    }
}

pub fn dim() -> Style {
    Style::default().fg(DIM)
}
pub fn accent() -> Style {
    Style::default().fg(ACCENT)
}
pub fn accent_bold() -> Style {
    Style::default().fg(ACCENT).add_modifier(Modifier::BOLD)
}
pub fn ok() -> Style {
    Style::default().fg(OK)
}
pub fn bad() -> Style {
    Style::default().fg(BAD)
}
pub fn head_bold() -> Style {
    Style::default().fg(HEAD).add_modifier(Modifier::BOLD)
}
pub fn code() -> Style {
    Style::default().fg(CODE)
}
pub fn bold() -> Style {
    Style::default().add_modifier(Modifier::BOLD)
}

/// A highlighted "pill" style — used for selection highlights, mode badges,
/// the drill cursor cell and toast popups. Explicit bg/fg instead of
/// Modifier::REVERSED, which renders inconsistently across terminals.
pub fn chip(bg: Color) -> Style {
    Style::default().bg(bg).fg(Color::Black)
}

/// The outer chrome every screen shares: a rounded, breadcrumb-titled block.
pub fn chrome(title: &str, border_color: Color) -> Block<'static> {
    Block::bordered()
        .border_type(BorderType::Rounded)
        .border_style(Style::default().fg(border_color))
        .title(Span::styled(format!(" {} ", title), head_bold()))
}

/// Split a block's inner area into (body, footer) with a 1-row key-legend
/// strip pinned to the bottom.
pub fn body_footer(inner: Rect) -> (Rect, Rect) {
    let chunks = Layout::vertical([Constraint::Min(0), Constraint::Length(1)]).split(inner);
    (chunks[0], chunks[1])
}

pub fn footer(f: &mut Frame, area: Rect, text: &str) {
    f.render_widget(Paragraph::new(Line::styled(text.to_string(), dim())), area);
}
