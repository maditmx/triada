//! Curriculum loading — port of the data.py load_all()/curriculum_dir()/find_lesson() slice.

use serde_json::Value;
use std::path::PathBuf;

pub const TRACKS: [&str; 3] = ["typing", "nvim", "python"];

pub struct Curriculum {
    pub typing: Value,
    pub nvim: Value,
    pub python: Value,
    pub combos: Value,
}

impl Curriculum {
    pub fn get(&self, track: &str) -> &Value {
        match track {
            "typing" => &self.typing,
            "nvim" => &self.nvim,
            "python" => &self.python,
            _ => &self.combos,
        }
    }

    pub fn levels(&self, track: &str) -> &[Value] {
        self.get(track)["levels"].as_array().map(|a| a.as_slice()).unwrap_or(&[])
    }
}

pub fn curriculum_dir() -> Result<PathBuf, String> {
    let mut candidates: Vec<PathBuf> = Vec::new();
    if let Ok(v) = std::env::var("TRIADA_CURRICULUM") {
        candidates.push(PathBuf::from(v));
    }
    candidates.push(PathBuf::from("../curriculum"));
    candidates.push(PathBuf::from("curriculum"));
    if let Ok(exe) = std::env::current_exe() {
        if let Some(dir) = exe.parent() {
            candidates.push(dir.join("curriculum"));
            candidates.push(dir.join("../curriculum"));
        }
    }
    for c in &candidates {
        if c.join("typing.json").is_file() {
            return Ok(c.clone());
        }
    }
    Err("Cannot find the curriculum/ directory. Set TRIADA_CURRICULUM to its path.".to_string())
}

pub fn load_all() -> Result<Curriculum, String> {
    let dir = curriculum_dir()?;
    let load = |name: &str| -> Result<Value, String> {
        let p = dir.join(format!("{}.json", name));
        let s = std::fs::read_to_string(&p).map_err(|e| format!("{}: {}", p.display(), e))?;
        serde_json::from_str(&s).map_err(|e| format!("{}: {}", p.display(), e))
    };
    Ok(Curriculum {
        typing: load("typing")?,
        nvim: load("nvim")?,
        python: load("python")?,
        combos: load("combos")?,
    })
}

/// Return (track, level, lesson) for a lesson id.
pub fn find_lesson<'a>(cur: &'a Curriculum, lesson_id: &str) -> Option<(&'static str, &'a Value, &'a Value)> {
    for t in TRACKS {
        for lv in cur.levels(t) {
            if let Some(lessons) = lv["lessons"].as_array() {
                for ls in lessons {
                    if ls["id"].as_str() == Some(lesson_id) {
                        return Some((t, lv, ls));
                    }
                }
            }
        }
    }
    None
}
