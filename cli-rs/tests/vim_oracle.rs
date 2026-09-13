//! Runs tests/vim_cases.json (repo-root) through the Rust engine — the same
//! oracle tests/parity.js runs against the JS port. See that file for the
//! reference check logic.

use serde_json::Value;
use std::fs;
use std::path::Path;
use triada::vim::Vim;

#[test]
fn vim_cases_oracle() {
    let path = Path::new(env!("CARGO_MANIFEST_DIR")).join("../tests/vim_cases.json");
    let raw = fs::read_to_string(&path).unwrap_or_else(|e| panic!("cannot read {}: {}", path.display(), e));
    let cases: Vec<Value> = serde_json::from_str(&raw).expect("invalid json");

    let mut fails = 0usize;
    let n = cases.len();

    for (i, c) in cases.iter().enumerate() {
        let lines: Vec<String> = c["lines"].as_array().unwrap().iter().map(|v| v.as_str().unwrap().to_string()).collect();
        let cursor = (c["cursor"][0].as_u64().unwrap() as usize, c["cursor"][1].as_u64().unwrap() as usize);
        let keys = c["keys"].as_str().unwrap();
        let want_lines: Vec<String> = c["lines_out"].as_array().unwrap().iter().map(|v| v.as_str().unwrap().to_string()).collect();
        let want_cursor = if c["cursor_out"].is_null() {
            None
        } else {
            Some((c["cursor_out"][0].as_u64().unwrap() as usize, c["cursor_out"][1].as_u64().unwrap() as usize))
        };

        let mut v = Vim::new(lines, cursor);
        v.feed(keys);
        let got_lines = v.lines_as_strings();
        if got_lines != want_lines {
            eprintln!("FAIL case{} keys={:?}\n   got  {:?}\n   want {:?}", i, keys, got_lines, want_lines);
            fails += 1;
            continue;
        }
        if let Some(want_cursor) = want_cursor {
            if (v.row, v.col) != want_cursor {
                eprintln!("FAIL case{} keys={:?} cursor {:?} != {:?}", i, keys, (v.row, v.col), want_cursor);
                fails += 1;
            }
        }
    }

    eprintln!("\n{}/{} passed in the Rust engine", n - fails, n);
    assert_eq!(fails, 0, "{} of {} vim oracle cases failed", fails, n);
}
