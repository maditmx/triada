//! Small crossterm key-event helpers shared by app.rs and drills.rs.

use crossterm::event::{self, Event, KeyCode, KeyEvent, KeyEventKind, KeyModifiers};
use std::io;
use std::time::Duration;

/// Block until a real key press (skips release/repeat noise some terminals send).
pub fn read_key() -> io::Result<KeyEvent> {
    loop {
        match event::read()? {
            Event::Key(k) if k.kind == KeyEventKind::Press => return Ok(k),
            Event::Resize(_, _) => {
                return Ok(KeyEvent::new(KeyCode::Null, KeyModifiers::NONE));
            }
            _ => continue,
        }
    }
}

/// Non-blocking poll used by the vim drill's F2 replay animation.
pub fn poll_key(timeout: Duration) -> io::Result<Option<KeyEvent>> {
    if event::poll(timeout)? {
        if let Event::Key(k) = event::read()? {
            if k.kind == KeyEventKind::Press {
                return Ok(Some(k));
            }
        }
    }
    Ok(None)
}

pub fn is_up(k: &KeyEvent) -> bool {
    matches!(k.code, KeyCode::Up) || k.code == KeyCode::Char('k')
}
pub fn is_down(k: &KeyEvent) -> bool {
    matches!(k.code, KeyCode::Down) || k.code == KeyCode::Char('j')
}
pub fn is_left_back(k: &KeyEvent) -> bool {
    matches!(k.code, KeyCode::Left | KeyCode::Esc) || k.code == KeyCode::Char('q')
}
pub fn is_right_enter(k: &KeyEvent) -> bool {
    matches!(k.code, KeyCode::Right | KeyCode::Enter)
}
pub fn is_esc(k: &KeyEvent) -> bool {
    matches!(k.code, KeyCode::Esc)
}
pub fn ctrl(k: &KeyEvent, c: char) -> bool {
    k.modifiers.contains(KeyModifiers::CONTROL) && matches!(k.code, KeyCode::Char(x) if x.eq_ignore_ascii_case(&c))
}

/// Map a key event to a single vim/typing "key char", mirroring what
/// curses' get_wch() would hand the Python engine.
pub fn to_char(k: &KeyEvent) -> Option<char> {
    match k.code {
        KeyCode::Char(c) => {
            if k.modifiers.contains(KeyModifiers::CONTROL) {
                let up = c.to_ascii_uppercase();
                if up.is_ascii_alphabetic() {
                    Some((((up as u8).wrapping_sub(64)) as char).into())
                } else if c == '[' {
                    Some('\x1b')
                } else {
                    Some(c)
                }
            } else {
                Some(c)
            }
        }
        KeyCode::Enter => Some('\r'),
        KeyCode::Backspace => Some('\x08'),
        KeyCode::Tab => Some('\t'),
        KeyCode::Esc => Some('\x1b'),
        KeyCode::Left => Some('h'),
        KeyCode::Right => Some('l'),
        KeyCode::Up => Some('k'),
        KeyCode::Down => Some('j'),
        _ => None,
    }
}
