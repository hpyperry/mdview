//! Golden snapshot generator.
//!
//! The P0 differential oracle lives in `tools/spike/`; this tool freezes the
//! output of the production renderer for a curated corpus so regressions show
//! up as a reviewable diff.
//!
//!   cargo run --example golden -- --update
//!   cargo run --example golden            # verify only

use std::fs;
use std::path::PathBuf;

use mdview::render::render_markdown;
use serde::Deserialize;

#[derive(Deserialize)]
struct Case {
    id: String,
    input: String,
    rel: String,
    #[serde(default)]
    note: String,
}

fn main() {
    let update = std::env::args().any(|arg| arg == "--update");
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let cases_path = root.join("tests/golden/cases.jsonl");
    let expected_dir = root.join("tests/golden/expected");

    let text = fs::read_to_string(&cases_path).expect("read cases.jsonl");
    let mut checked = 0;
    let mut updated = 0;
    let mut failed = 0;
    for (line_no, line) in text.lines().enumerate() {
        if line.trim().is_empty() {
            continue;
        }
        let case: Case = serde_json::from_str(line)
            .unwrap_or_else(|err| panic!("cases.jsonl:{}: {err}", line_no + 1));
        let html = render_markdown(&case.input, &case.rel);
        let path = expected_dir.join(format!("{}.html", case.id));
        if update {
            fs::create_dir_all(&expected_dir).expect("create expected dir");
            fs::write(&path, &html).expect("write golden");
            updated += 1;
            continue;
        }
        let expected = fs::read_to_string(&path)
            .unwrap_or_else(|err| panic!("read {}: {err}", path.display()));
        if expected != html {
            failed += 1;
            eprintln!("MISMATCH {} ({})", case.id, case.note);
            eprintln!("  expected: {:?}", expected);
            eprintln!("  actual:   {:?}", html);
        }
        checked += 1;
    }

    if update {
        println!(
            "updated {updated} golden files under {}",
            expected_dir.display()
        );
    } else {
        println!("checked {checked} golden files, {failed} mismatch(es)");
        if failed > 0 {
            std::process::exit(1);
        }
    }
}
