//! Tiny markdown renderer — port of render_markdown() in ui.py, producing
//! rows of (text, style) segments instead of curses attr pairs.

use crate::ui;
use ratatui::style::Style;
use ratatui::text::{Line, Span};
use regex::Regex;

pub type Seg = (String, Style);
pub type Row = Vec<Seg>;

pub fn strip_md(s: &str) -> String {
    s.chars().filter(|&c| c != '`' && c != '*').collect()
}

fn inline(s: &str) -> Row {
    let re = Regex::new(r"(`[^`]+`|\*\*[^*]+\*\*)").unwrap();
    let mut out = Row::new();
    let mut last = 0;
    for m in re.find_iter(s) {
        if m.start() > last {
            out.push((s[last..m.start()].to_string(), Style::default()));
        }
        let part = m.as_str();
        if part.starts_with('`') {
            out.push((part[1..part.len() - 1].to_string(), ui::code()));
        } else {
            out.push((part[2..part.len() - 2].to_string(), ui::bold()));
        }
        last = m.end();
    }
    if last < s.len() {
        out.push((s[last..].to_string(), Style::default()));
    }
    out
}

fn wrap_segments(segs: &[Seg], indent: &str, width: usize) -> Vec<Row> {
    let ws_re = Regex::new(r"\s+").unwrap();
    let mut out: Vec<Row> = Vec::new();
    let mut cur: Row = Vec::new();
    let indent_len = indent.chars().count();
    let mut col = indent_len;
    if !indent.is_empty() {
        cur.push((indent.to_string(), Style::default()));
    }
    for (text, attr) in segs {
        let mut last = 0;
        let mut words: Vec<(String, bool)> = Vec::new();
        for m in ws_re.find_iter(text) {
            if m.start() > last {
                words.push((text[last..m.start()].to_string(), false));
            }
            words.push((m.as_str().to_string(), true));
            last = m.end();
        }
        if last < text.len() {
            words.push((text[last..].to_string(), false));
        }
        for (word, is_space) in words {
            if word.is_empty() {
                continue;
            }
            if is_space {
                if !cur.is_empty() && col < width {
                    cur.push((" ".to_string(), *attr));
                    col += 1;
                }
                continue;
            }
            let wlen = word.chars().count();
            if col + wlen > width && col > indent_len {
                out.push(std::mem::take(&mut cur));
                cur = if !indent.is_empty() { vec![(indent.to_string(), Style::default())] } else { Vec::new() };
                col = indent_len;
            }
            cur.push((word, *attr));
            col += wlen;
        }
    }
    if !cur.is_empty() {
        out.push(cur);
    }
    if out.is_empty() {
        out.push(Vec::new());
    }
    out
}

fn cells(row: &str) -> Vec<String> {
    row.trim().trim_matches('|').split('|').map(|c| c.trim().to_string()).collect()
}

pub fn render_markdown(src: &str, width: usize) -> Vec<Row> {
    let width = width.max(1);
    let mut lines: Vec<Row> = Vec::new();
    let src_lines: Vec<&str> = src.split('\n').collect();
    let mut i = 0usize;
    let heading_re = Regex::new(r"^#{1,4} ").unwrap();
    let table_sep_re = Regex::new(r"^\|[\s:|-]+\|?\s*$").unwrap();
    let bullet_re = Regex::new(r"^\s*[-*] ").unwrap();
    let bullet_cont_re = Regex::new(r"^\s{2,}\S").unwrap();
    let numbered_re = Regex::new(r"^\s*\d+\. ").unwrap();
    let numbered_num_re = Regex::new(r"^\s*(\d+)\. ").unwrap();
    let para_stop_re = Regex::new(r"^(```|\||#{1,4} |\s*[-*] |\s*\d+\. )").unwrap();

    while i < src_lines.len() {
        let ln = src_lines[i];
        if ln.starts_with("```") {
            i += 1;
            while i < src_lines.len() && !src_lines[i].starts_with("```") {
                let text: String = src_lines[i].chars().take(width.saturating_sub(2)).collect();
                lines.push(vec![("  ".to_string(), Style::default()), (text, ui::code())]);
                i += 1;
            }
            i += 1;
            lines.push(Vec::new());
            continue;
        }
        if ln.starts_with('|') && i + 1 < src_lines.len() && table_sep_re.is_match(src_lines[i + 1]) {
            let head = cells(ln);
            i += 2;
            let mut body: Vec<Vec<String>> = Vec::new();
            while i < src_lines.len() && src_lines[i].starts_with('|') {
                body.push(cells(src_lines[i]));
                i += 1;
            }
            let ncol = head.len().max(body.iter().map(|r| r.len()).max().unwrap_or(0));
            let mut widths = Vec::new();
            for c in 0..ncol {
                let hw = if c < head.len() { strip_md(&head[c]).chars().count() } else { 0 };
                let bw = body.iter().map(|r| if c < r.len() { strip_md(&r[c]).chars().count() } else { 0 }).max().unwrap_or(0);
                let cw = hw.max(bw);
                widths.push(cw.min((width / ncol.max(1)).max(8)));
            }
            let row_segs = |cs: &[String], style: Style, widths: &[usize]| -> Row {
                (0..ncol)
                    .map(|c| {
                        let raw = if c < cs.len() { strip_md(&cs[c]) } else { String::new() };
                        let truncated: String = raw.chars().take(widths[c]).collect();
                        let padded = format!("{:<width$}", truncated, width = widths[c] + 2);
                        (padded, style)
                    })
                    .collect()
            };
            lines.push(row_segs(&head, ui::dim().add_modifier(ratatui::style::Modifier::BOLD), &widths));
            for r in &body {
                lines.push(row_segs(r, Style::default(), &widths));
            }
            lines.push(Vec::new());
            continue;
        }
        if heading_re.is_match(ln) {
            let text = Regex::new(r"^#+ ").unwrap().replace(ln, "").to_string();
            lines.push(vec![(text, ui::head_bold())]);
            lines.push(Vec::new());
            i += 1;
            continue;
        }
        if bullet_re.is_match(ln) {
            let mut body = bullet_re.replace(ln, "").to_string();
            i += 1;
            while i < src_lines.len() && bullet_cont_re.is_match(src_lines[i]) && !bullet_re.is_match(src_lines[i]) {
                body.push(' ');
                body.push_str(src_lines[i].trim());
                i += 1;
            }
            let mut segs = vec![("  • ".to_string(), ui::accent())];
            segs.extend(inline(&body));
            lines.extend(wrap_segments(&segs, "", width));
            continue;
        }
        if numbered_re.is_match(ln) {
            let num = numbered_num_re.captures(ln).map(|c| c[1].to_string()).unwrap_or_default();
            let mut body = numbered_num_re.replace(ln, "").to_string();
            i += 1;
            while i < src_lines.len() && bullet_cont_re.is_match(src_lines[i]) && !numbered_re.is_match(src_lines[i]) {
                body.push(' ');
                body.push_str(src_lines[i].trim());
                i += 1;
            }
            let mut segs = vec![(format!("  {}. ", num), ui::accent())];
            segs.extend(inline(&body));
            lines.extend(wrap_segments(&segs, "", width));
            continue;
        }
        if ln.trim().is_empty() {
            lines.push(Vec::new());
            i += 1;
            continue;
        }
        let mut para: Vec<&str> = Vec::new();
        while i < src_lines.len() && !src_lines[i].trim().is_empty() && !para_stop_re.is_match(src_lines[i]) {
            para.push(src_lines[i]);
            i += 1;
        }
        let joined = para.join(" ");
        lines.extend(wrap_segments(&inline(&joined), "", width));
        lines.push(Vec::new());
    }
    while lines.last().map(|l| l.is_empty()).unwrap_or(false) {
        lines.pop();
    }
    lines
}

pub fn row_to_line(row: &Row) -> Line<'static> {
    Line::from(row.iter().map(|(t, s)| Span::styled(t.clone(), *s)).collect::<Vec<_>>())
}

pub fn rows_to_lines(rows: &[Row]) -> Vec<Line<'static>> {
    rows.iter().map(row_to_line).collect()
}
