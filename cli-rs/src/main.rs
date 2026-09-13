//! triada — terminal trainer for touch typing, Neovim and Python (ratatui port).
//!
//! Usage:
//!   triada                 open the trainer
//!   triada <lesson-id>     jump straight to one lesson (e.g. triada v06l3)
//!   triada py <lesson-id>  run one Python exercise without the TUI
//!   triada stats           print progress and exit
//!   triada doctor          check the environment

use crossterm::event::{DisableMouseCapture, EnableMouseCapture};
use crossterm::execute;
use crossterm::terminal::{disable_raw_mode, enable_raw_mode, EnterAlternateScreen, LeaveAlternateScreen};
use ratatui::backend::CrosstermBackend;
use std::io::{self, Write};
use std::process::Command;
use triada::app::App;
use triada::curriculum::{self, find_lesson, TRACKS};
use triada::progress::{progress_path, Progress};

const USAGE: &str = "triada — terminal trainer for touch typing, Neovim and Python

Usage:
  triada                 open the trainer
  triada <lesson-id>     jump straight to one lesson (e.g. triada v06l3)
  triada py <lesson-id>  run one Python exercise without the TUI
  triada stats           print progress and exit
  triada doctor          check the environment
";

fn cmd_stats() -> i32 {
    let cur = match curriculum::load_all() {
        Ok(c) => c,
        Err(e) => {
            eprintln!("{}", e);
            return 1;
        }
    };
    let prog = Progress::new(&cur);
    println!("Tríada — progress\n");
    for t in TRACKS {
        let st = prog.stats(t, &cur);
        let filled = (st.pct * 24.0).round() as usize;
        println!(
            "  {:<8} {}{}  {:3}%   {:3}/{:<4} lessons   level {}/{}",
            t,
            "█".repeat(filled),
            "·".repeat(24 - filled),
            (st.pct * 100.0) as u64,
            st.done,
            st.total,
            st.level,
            st.levels
        );
    }
    let combos = cur.combos["combos"].as_array().cloned().unwrap_or_default();
    let done = combos.iter().filter(|c| prog.data["combos"].get(c["id"].as_str().unwrap_or("")).is_some()).count();
    println!("\n  combos   {}/{} complete", done, combos.len());
    if let Some(ks) = prog.data["keyStats"].as_object() {
        if !ks.is_empty() {
            let mut worst: Vec<(&String, &serde_json::Value)> = ks.iter().collect();
            worst.sort_by(|a, b| b.1.as_i64().unwrap_or(0).cmp(&a.1.as_i64().unwrap_or(0)));
            worst.truncate(12);
            let line = worst
                .iter()
                .map(|(k, n)| {
                    let label = if k.as_str() == " " { "space".to_string() } else if k.as_str() == "\n" { "enter".to_string() } else { (*k).clone() };
                    format!("{}×{}", label, n.as_i64().unwrap_or(0))
                })
                .collect::<Vec<_>>()
                .join("  ");
            println!("\n  most-missed keys: {}", line);
        }
    }
    println!("\n  file: {}", progress_path().display());
    0
}

fn which(cmd: &str) -> bool {
    Command::new("which").arg(cmd).output().map(|o| o.status.success()).unwrap_or(false)
}

fn cmd_doctor() -> i32 {
    let mut ok = true;
    println!("Tríada — environment check\n");
    println!("  binary      {}", env!("CARGO_PKG_VERSION"));

    match which("python3") {
        true => println!("  python3     available (needed to run code exercises)"),
        false => {
            println!("  python3     MISSING — code exercises cannot run their tests");
            ok = false;
        }
    }

    let editor = std::env::var("VISUAL").ok().or_else(|| std::env::var("EDITOR").ok());
    match editor {
        Some(e) => println!("  $EDITOR     {}", e),
        None => {
            let found: Vec<&str> = ["nvim", "vim", "vi"].into_iter().filter(|c| which(c)).collect();
            println!(
                "  $EDITOR     unset — will use {}{}",
                found.first().copied().unwrap_or("vi"),
                if found.is_empty() { String::new() } else { format!(" (found: {})", found.join(", ")) }
            );
        }
    }

    match curriculum::load_all() {
        Ok(cur) => {
            let n: usize = TRACKS.iter().map(|t| cur.levels(t).iter().map(|lv| lv["lessons"].as_array().map(|a| a.len()).unwrap_or(0)).sum::<usize>()).sum();
            let combos = cur.combos["combos"].as_array().map(|a| a.len()).unwrap_or(0);
            let dir = curriculum::curriculum_dir().unwrap_or_default();
            println!("  curriculum  {}  ({} lessons, {} combos)", dir.display(), n, combos);
        }
        Err(e) => {
            println!("  curriculum  {}", e);
            ok = false;
        }
    }

    let pp = progress_path();
    println!("  progress    {}{}", pp.display(), if pp.exists() { "" } else { "  (will be created)" });

    let term = std::env::var("TERM").unwrap_or_default();
    let good_term = term.contains("256") || term.contains("color");
    println!("  TERM        {}{}", if term.is_empty() { "unset" } else { &term }, if good_term { "" } else { "  — a 256-colour TERM looks much better" });

    println!("\n{}", if ok { "all good" } else { "problems above" });
    if ok {
        0
    } else {
        1
    }
}

fn cmd_py(lesson_id: &str) -> i32 {
    let cur = match curriculum::load_all() {
        Ok(c) => c,
        Err(e) => {
            eprintln!("{}", e);
            return 1;
        }
    };
    let found = find_lesson(&cur, lesson_id);
    let (track, ls) = match found {
        Some((t, _lv, ls)) if t == "python" => (t, ls.clone()),
        _ => {
            println!("No Python exercise with id {:?}.", lesson_id);
            return 1;
        }
    };
    let _ = track;
    if ls["kind"].as_str() != Some("code") {
        println!("{} is a {} exercise — open it with `triada {}`.", lesson_id, ls["kind"].as_str().unwrap_or(""), lesson_id);
        return 1;
    }

    println!("\n{}\n", ls["title"].as_str().unwrap_or(""));
    println!("{}\n", ls["prompt"].as_str().unwrap_or(""));
    let dir = std::env::temp_dir().join(format!("triada-py-{}", std::process::id()));
    let _ = std::fs::create_dir_all(&dir);
    let path = dir.join(format!("{}.py", lesson_id));
    if std::fs::write(&path, ls["starter"].as_str().unwrap_or("")).is_err() {
        println!("could not write starter file");
        return 1;
    }
    let editor = std::env::var("VISUAL").ok().or_else(|| std::env::var("EDITOR").ok()).unwrap_or_else(|| "nvim".to_string());
    println!("editing {} with {} — save and quit when you are done\n", path.display(), editor);
    let parts: Vec<&str> = editor.split_whitespace().collect();
    if let Some((prog_cmd, args)) = parts.split_first() {
        let _ = Command::new(prog_cmd).args(args).arg(&path).status();
    }

    let runner = dir.join("_run.py");
    let src = std::fs::read_to_string(&path).unwrap_or_default();
    let content = format!("{}\n\n{}\nprint('__TRIADA_OK__')\n", src, ls["tests"].as_str().unwrap_or(""));
    if std::fs::write(&runner, content).is_err() {
        println!("could not write test runner");
        return 1;
    }
    let out = Command::new("python3").arg(&runner).output();
    match out {
        Ok(o) => {
            let stdout = String::from_utf8_lossy(&o.stdout).to_string();
            if stdout.contains("__TRIADA_OK__") {
                println!("✓ all tests passed");
                let extra = stdout.replace("__TRIADA_OK__\n", "").trim().to_string();
                if !extra.is_empty() {
                    println!("\nstdout:\n{}", extra);
                }
                let mut prog = Progress::new(&cur);
                prog.mark_done("python", lesson_id, None, &cur);
                0
            } else {
                println!("✗ tests failed\n");
                let stderr = String::from_utf8_lossy(&o.stderr).to_string();
                println!("{}", if !stderr.trim().is_empty() { stderr.trim() } else { stdout.trim() });
                let mut prog = Progress::new(&cur);
                prog.mark_tried("python", lesson_id);
                1
            }
        }
        Err(e) => {
            println!("failed to run python3: {}", e);
            1
        }
    }
}

fn run_tui(start: Option<&str>) -> io::Result<i32> {
    if let Some(id) = start {
        let cur = match curriculum::load_all() {
            Ok(c) => c,
            Err(e) => {
                eprintln!("{}", e);
                return Ok(1);
            }
        };
        if find_lesson(&cur, id).is_none() {
            println!("No lesson with id {:?}. Try `triada` and browse, or `triada stats`.", id);
            return Ok(1);
        }
    }

    let mut app = match App::new() {
        Ok(a) => a,
        Err(e) => {
            eprintln!("{}", e);
            return Ok(1);
        }
    };

    enable_raw_mode()?;
    let mut stdout = io::stdout();
    execute!(stdout, EnterAlternateScreen, EnableMouseCapture)?;
    let backend = CrosstermBackend::new(stdout);
    let mut terminal = ratatui::Terminal::new(backend)?;
    terminal.hide_cursor()?;

    let result = app.run(&mut terminal, start);

    disable_raw_mode()?;
    execute!(terminal.backend_mut(), LeaveAlternateScreen, DisableMouseCapture)?;
    terminal.show_cursor()?;

    result?;
    Ok(0)
}

fn main() {
    let argv: Vec<String> = std::env::args().skip(1).collect();

    let code = if !argv.is_empty() && matches!(argv[0].as_str(), "-h" | "--help" | "help") {
        print!("{}", USAGE);
        0
    } else if !argv.is_empty() && argv[0] == "stats" {
        cmd_stats()
    } else if !argv.is_empty() && argv[0] == "doctor" {
        cmd_doctor()
    } else if !argv.is_empty() && argv[0] == "py" {
        if argv.len() < 2 {
            println!("usage: triada py <lesson-id>");
            1
        } else {
            cmd_py(&argv[1])
        }
    } else {
        let start = argv.first().map(|s| s.as_str());
        match run_tui(start) {
            Ok(c) => c,
            Err(e) => {
                let _ = disable_raw_mode();
                eprintln!("error: {}", e);
                1
            }
        }
    };
    let _ = io::stdout().flush();
    std::process::exit(code);
}
