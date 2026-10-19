//! Frozen golden outputs for a curated renderer corpus.
//!
//! Regenerate after an intentional renderer change:
//!   cargo run --example golden -- --update

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

#[test]
fn golden_corpus_matches() {
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let text = fs::read_to_string(root.join("tests/golden/cases.jsonl")).expect("cases.jsonl");
    let expected_dir = root.join("tests/golden/expected");
    let mut checked = 0;
    let mut failures = Vec::new();
    for (line_no, line) in text.lines().enumerate() {
        if line.trim().is_empty() {
            continue;
        }
        let case: Case = serde_json::from_str(line)
            .unwrap_or_else(|err| panic!("cases.jsonl:{}: {err}", line_no + 1));
        let html = render_markdown(&case.input, &case.rel);
        let path = expected_dir.join(format!("{}.html", case.id));
        let expected = fs::read_to_string(&path).unwrap_or_else(|err| {
            panic!(
                "missing golden {}: {err}; run cargo run --example golden -- --update",
                path.display()
            )
        });
        if expected != html {
            failures.push(format!(
                "{} ({}):\n  expected: {:?}\n  actual:   {:?}",
                case.id, case.note, expected, html
            ));
        }
        checked += 1;
    }
    assert!(
        failures.is_empty(),
        "{} of {checked} golden cases differ:\n{}",
        failures.len(),
        failures.join("\n")
    );
}
