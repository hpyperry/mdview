use std::fmt::Write as _;
use std::fs;
use std::io::{BufRead, BufReader, BufWriter, Write};
use std::panic::{catch_unwind, AssertUnwindSafe};
use std::path::Path;

use comrak::html::ChildRendering;
use comrak::nodes::{NodeValue, Sourcepos};
use comrak::{create_formatter, parse_document, Arena, Options};
use serde::Deserialize;

#[derive(Debug, Deserialize)]
struct Entry {
    id: String,
    input: String,
    #[serde(default)]
    name: String,
}

#[derive(Default)]
struct SourceMap {
    text: String,
    line_starts: Vec<usize>,
}

impl SourceMap {
    fn new(text: &str) -> Self {
        let mut line_starts = vec![0];
        for (i, b) in text.bytes().enumerate() {
            if b == b'\n' {
                line_starts.push(i + 1);
            }
        }
        Self {
            text: text.to_string(),
            line_starts,
        }
    }

    fn slice(&self, pos: Sourcepos) -> &str {
        if pos.start.line == 0 || pos.end.line == 0 {
            return "";
        }
        let start = self
            .line_starts
            .get(pos.start.line - 1)
            .copied()
            .unwrap_or(0)
            + pos.start.column.saturating_sub(1);
        // comrak's end.column is the 1-based byte index of the last byte of the
        // node, so it is exactly the exclusive end offset for a 0-based slice.
        let end = self.line_starts.get(pos.end.line - 1).copied().unwrap_or(0) + pos.end.column;
        if start > end || start > self.text.len() {
            return "";
        }
        let end = end.min(self.text.len());
        if !self.text.is_char_boundary(start) || !self.text.is_char_boundary(end) {
            return "";
        }
        &self.text[start..end]
    }
}

fn is_safe_link(url: &str) -> bool {
    let trimmed = url.trim();
    let lower = trimmed.to_lowercase();

    // Server deviation: VS Code's override allows vscode: / vscode-insiders:;
    // a standalone browser has no handler, so we reject them.
    if lower.starts_with("vscode:") || lower.starts_with("vscode-insiders:") {
        return false;
    }

    // markdown-it's default validateLink (lowercased).
    if lower.starts_with("javascript:")
        || lower.starts_with("vbscript:")
        || lower.starts_with("file:")
    {
        return false;
    }
    if lower.starts_with("data:") {
        if lower.starts_with("data:image/gif;")
            || lower.starts_with("data:image/png;")
            || lower.starts_with("data:image/jpeg;")
            || lower.starts_with("data:image/webp;")
        {
            return true;
        }
        // VS Code's override: any data:image/<type>;... (case-sensitive,
        // mirrors the extension's /^data:image\/.*?;/ test).
        if let Some(rest) = trimmed.strip_prefix("data:image/") {
            return rest.contains(';');
        }
        return false;
    }
    true
}

/// Split raw source `[label](dest)` / `![alt](dest)` / `[label][ref]` into
/// the prefix and the tail after the label's closing `]`. The label itself is
/// rendered from comrak's children, so inline markup in a rejected link/image
/// survives (markdown-it does the same).
fn split_label<'a>(raw: &'a str, is_image: bool) -> Option<(&'a str, &'a str)> {
    let prefix = if is_image { "![" } else { "[" };
    if !raw.starts_with(prefix) {
        return None;
    }
    let bytes = raw.as_bytes();
    let mut depth = 0usize;
    let mut in_code = false;
    let mut i = if is_image { 1 } else { 0 };
    while i < bytes.len() {
        match bytes[i] {
            b'\\' => {
                i += 2;
                continue;
            }
            b'`' => {
                in_code = !in_code;
            }
            b'[' if !in_code => depth += 1,
            b']' if !in_code => {
                depth = depth.saturating_sub(1);
                if depth == 0 {
                    return Some((prefix, &raw[i + 1..]));
                }
            }
            _ => {}
        }
        i += 1;
    }
    None
}

fn write_valid_link(
    context: &mut comrak::html::Context<SourceMap>,
    url: &str,
    title: &str,
    entering: bool,
) -> Result<ChildRendering, std::fmt::Error> {
    if entering {
        context.write_str("<a href=\"")?;
        context.escape_href(url)?;
        if !title.is_empty() {
            context.write_str("\" title=\"")?;
            context.escape(title)?;
        }
        context.write_str("\">")?;
    } else {
        context.write_str("</a>")?;
    }
    Ok(ChildRendering::HTML)
}

fn write_valid_image(
    context: &mut comrak::html::Context<SourceMap>,
    url: &str,
    title: &str,
    entering: bool,
) -> Result<ChildRendering, std::fmt::Error> {
    if entering {
        context.write_str("<img src=\"")?;
        context.escape_href(url)?;
        context.write_str("\" alt=\"")?;
        Ok(ChildRendering::Plain)
    } else {
        if !title.is_empty() {
            context.write_str("\" title=\"")?;
            context.escape(title)?;
        }
        context.write_str("\" />")?;
        Ok(ChildRendering::HTML)
    }
}

fn write_rejected_literal(
    context: &mut comrak::html::Context<SourceMap>,
    raw: &str,
    is_image: bool,
    entering: bool,
) -> Result<ChildRendering, std::fmt::Error> {
    if entering {
        if let Some((prefix, _tail)) = split_label(raw, is_image) {
            context.write_str(prefix)?;
            Ok(ChildRendering::HTML)
        } else {
            context.escape(raw)?;
            Ok(ChildRendering::Skip)
        }
    } else if let Some((_prefix, tail)) = split_label(raw, is_image) {
        context.write_str("]")?;
        // markdown-it keeps the raw remainder when a destination is rejected;
        // html:true means a `<script>` inside that remainder is still HTML.
        // The real server relies on Trust/CSP for this, not escaping.
        context.write_str(tail)?;
        Ok(ChildRendering::HTML)
    } else {
        Ok(ChildRendering::HTML)
    }
}

create_formatter!(ProbeFormatter<SourceMap>, {
    NodeValue::Link(ref nl) => |context, node, entering| {
        let raw = context.user.slice(node.data().sourcepos).to_string();
        if !is_safe_link(&nl.url) {
            return write_rejected_literal(context, &raw, false, entering);
        }
        return write_valid_link(context, &nl.url, &nl.title, entering)
    },
    NodeValue::Image(ref nl) => |context, node, entering| {
        let raw = context.user.slice(node.data().sourcepos).to_string();
        if !is_safe_link(&nl.url) {
            return write_rejected_literal(context, &raw, true, entering);
        }
        return write_valid_image(context, &nl.url, &nl.title, entering)
    },
    NodeValue::Strikethrough => |context, node, entering| {
        let _ = node;
        if entering {
            context.write_str("<s>")?;
        } else {
            context.write_str("</s>")?;
        }
    },
});

fn render_markdown(input: &str) -> String {
    let arena = Arena::new();
    let mut options = Options::default();
    options.extension.table = true;
    options.extension.strikethrough = true;
    options.extension.autolink = true;
    options.render.r#unsafe = true;
    options.render.sourcepos = false;

    let root = parse_document(&arena, input, &options);
    let mut output = String::new();
    let source = SourceMap::new(input);
    ProbeFormatter::format_document(root, &options, &mut output, source).unwrap();
    output
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let default_corpus = Path::new("corpus/corpus.jsonl");
    let input_path = args.get(1).map(Path::new).unwrap_or(default_corpus);
    let output_path = args
        .get(2)
        .map(Path::new)
        .unwrap_or(Path::new("results/comrak.jsonl"));

    let file = fs::File::open(input_path).expect("open corpus");
    let reader = BufReader::new(file);
    if let Some(parent) = output_path.parent() {
        fs::create_dir_all(parent).expect("create results dir");
    }
    let out = fs::File::create(output_path).expect("create output");
    let mut writer = BufWriter::new(out);

    let mut total = 0usize;
    let mut errors = 0usize;
    for line in reader.lines() {
        let line = line.expect("read line");
        if line.trim().is_empty() {
            continue;
        }
        let entry: Entry = serde_json::from_str(&line).expect("parse corpus entry");
        total += 1;
        let start = std::time::Instant::now();
        let result = catch_unwind(AssertUnwindSafe(|| render_markdown(&entry.input)));
        let elapsed_ms = start.elapsed().as_secs_f64() * 1000.0;
        let value = match result {
            Ok(html) => serde_json::json!({
                "id": entry.id,
                "html": html,
                "elapsed_ms": elapsed_ms,
            }),
            Err(_) => {
                errors += 1;
                serde_json::json!({
                    "id": entry.id,
                    "html": "",
                    "elapsed_ms": elapsed_ms,
                    "error": format!("panic while rendering {}", entry.name),
                })
            }
        };
        writeln!(writer, "{}", serde_json::to_string(&value).unwrap()).expect("write result");
    }
    writer.flush().expect("flush");
    println!(
        "[comrak] wrote {} entries to {} ({} panics)",
        total,
        output_path.display(),
        errors
    );
}
