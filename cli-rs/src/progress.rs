//! Progress persistence — port of data.py's blank_progress()/Progress.
//! JSON-shape-compatible with the Python CLI and the web app.

use crate::curriculum::{Curriculum, TRACKS};
use serde_json::{json, Value};
use std::path::PathBuf;

pub fn home_dir() -> PathBuf {
    let p = std::env::var("TRIADA_HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|_| {
            let home = std::env::var("HOME").unwrap_or_else(|_| ".".to_string());
            PathBuf::from(home).join(".triada")
        });
    let _ = std::fs::create_dir_all(&p);
    p
}

pub fn progress_path() -> PathBuf {
    home_dir().join("progress.json")
}

pub fn blank_progress() -> Value {
    json!({
        "version": 1,
        "typing": {"lessons": {}, "level": 1},
        "nvim": {"lessons": {}, "level": 1},
        "python": {"lessons": {}, "level": 1},
        "combos": {},
        "keyStats": {},
        "totals": {"seconds": 0, "sessions": 0}
    })
}

pub struct Stats {
    pub done: usize,
    pub total: usize,
    pub pct: f64,
    pub level: usize,
    pub levels: usize,
}

pub struct Progress {
    pub data: Value,
}

impl Progress {
    pub fn new(cur: &Curriculum) -> Self {
        let mut p = Progress { data: blank_progress() };
        p.load();
        p.recompute(cur);
        p
    }

    pub fn load(&mut self) {
        let path = progress_path();
        let raw_str = match std::fs::read_to_string(&path) {
            Ok(s) => s,
            Err(_) => return,
        };
        let raw: Value = match serde_json::from_str(&raw_str) {
            Ok(v) => v,
            Err(_) => return,
        };
        let mut base = blank_progress();
        for t in TRACKS {
            let lessons = raw.get(t).and_then(|v| v.get("lessons")).cloned().unwrap_or_else(|| json!({}));
            let level = raw.get(t).and_then(|v| v.get("level")).cloned().unwrap_or_else(|| json!(1));
            base[t]["lessons"] = lessons;
            base[t]["level"] = level;
        }
        base["combos"] = raw.get("combos").cloned().unwrap_or_else(|| json!({}));
        base["keyStats"] = raw.get("keyStats").cloned().unwrap_or_else(|| json!({}));
        if let Some(totals) = raw.get("totals") {
            base["totals"] = totals.clone();
        }
        self.data = base;
    }

    pub fn save(&self) {
        if let Ok(s) = serde_json::to_string_pretty(&self.data) {
            let _ = std::fs::write(progress_path(), s);
        }
    }

    pub fn done(&self, track: &str, lesson_id: &str) -> bool {
        self.data[track]["lessons"]
            .get(lesson_id)
            .and_then(|r| r.get("done"))
            .and_then(|v| v.as_bool())
            .unwrap_or(false)
    }

    pub fn record(&self, track: &str, lesson_id: &str) -> Value {
        self.data[track]["lessons"].get(lesson_id).cloned().unwrap_or_else(|| json!({}))
    }

    pub fn level_complete(&self, track: &str, level: &Value) -> bool {
        level["lessons"]
            .as_array()
            .map(|a| a.iter().all(|ls| self.done(track, ls["id"].as_str().unwrap_or(""))))
            .unwrap_or(true)
    }

    pub fn unlocked(&self, track: &str) -> usize {
        self.data[track]["level"].as_u64().unwrap_or(1) as usize
    }

    pub fn stats(&self, track: &str, cur: &Curriculum) -> Stats {
        let levels = cur.levels(track);
        let total: usize = levels.iter().map(|lv| lv["lessons"].as_array().map(|a| a.len()).unwrap_or(0)).sum();
        let done: usize = levels
            .iter()
            .flat_map(|lv| lv["lessons"].as_array().cloned().unwrap_or_default())
            .filter(|ls| self.done(track, ls["id"].as_str().unwrap_or("")))
            .count();
        Stats {
            done,
            total,
            pct: if total > 0 { done as f64 / total as f64 } else { 0.0 },
            level: self.unlocked(track).min(levels.len().max(1)),
            levels: levels.len(),
        }
    }

    pub fn mark_done(&mut self, track: &str, lesson_id: &str, score: Option<Value>, cur: &Curriculum) {
        {
            let lessons = self.data[track]["lessons"].as_object_mut().unwrap();
            let rec = lessons
                .entry(lesson_id.to_string())
                .or_insert_with(|| json!({"done": false, "tries": 0}));
            rec["done"] = json!(true);
            let tries = rec["tries"].as_i64().unwrap_or(0);
            rec["tries"] = json!(tries + 1);
            if let Some(score) = score {
                if rec.get("best").map(|b| !b.is_object()).unwrap_or(true) {
                    rec["best"] = json!({});
                }
                if let Some(scoreobj) = score.as_object() {
                    let best = rec["best"].as_object_mut().unwrap();
                    for (k, v) in scoreobj {
                        let vnum = v.as_f64().unwrap_or(0.0);
                        let better = match best.get(k).and_then(|b| b.as_f64()) {
                            None => true,
                            Some(bnum) => {
                                if k == "keys" {
                                    vnum < bnum
                                } else {
                                    vnum > bnum
                                }
                            }
                        };
                        if better {
                            best.insert(k.clone(), v.clone());
                        }
                    }
                }
                rec["last"] = score;
            }
        }
        self.recompute(cur);
        self.save();
    }

    pub fn mark_tried(&mut self, track: &str, lesson_id: &str) {
        let lessons = self.data[track]["lessons"].as_object_mut().unwrap();
        let rec = lessons
            .entry(lesson_id.to_string())
            .or_insert_with(|| json!({"done": false, "tries": 0}));
        let tries = rec["tries"].as_i64().unwrap_or(0);
        rec["tries"] = json!(tries + 1);
        self.save();
    }

    pub fn bump_key(&mut self, ch: char) {
        let key = ch.to_string();
        let obj = self.data["keyStats"].as_object_mut().unwrap();
        let n = obj.get(&key).and_then(|v| v.as_i64()).unwrap_or(0);
        obj.insert(key, json!(n + 1));
    }

    pub fn recompute(&mut self, cur: &Curriculum) {
        for t in TRACKS {
            let levels = cur.levels(t);
            let mut unlocked = 1usize;
            for (i, lv) in levels.iter().enumerate() {
                if self.level_complete(t, lv) {
                    unlocked = (i + 2).min(levels.len());
                } else {
                    break;
                }
            }
            let cur_level = self.data[t]["level"].as_u64().unwrap_or(1) as usize;
            self.data[t]["level"] = json!(cur_level.max(unlocked));
        }
    }
}
