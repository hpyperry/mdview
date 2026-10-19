//! Markdown rendering: comrak core + the VS Code/comrak conformance layer.
//!
//! Per ADR 0005/0007:
//! - core semantics follow VS Code/markdown-it;
//! - linkify, reference definitions, front matter, URL normalization and image
//!   alt use comrak behavior;
//! - protocol validation and root-relative URL rewriting stay custom.

use std::fmt::Write as _;

use percent_encoding::{AsciiSet, CONTROLS, percent_decode_str, utf8_percent_encode};

use comrak::html::ChildRendering;
use comrak::nodes::{NodeValue, TableAlignment};
use comrak::{Arena, Options, create_formatter, parse_document};

const URL_SEGMENT_SET: &AsciiSet = &CONTROLS
    .add(b' ')
    .add(b'"')
    .add(b'#')
    .add(b'<')
    .add(b'>')
    .add(b'?')
    .add(b'`')
    .add(b'{')
    .add(b'}')
    .add(b'%')
    .add(b'/')
    .add(b'\\')
    .add(b':');

#[derive(Debug, Default)]
struct RenderCtx {
    doc_rel: String,
}

impl RenderCtx {
    fn new(doc_rel: &str) -> Self {
        Self {
            doc_rel: doc_rel.to_string(),
        }
    }
}

/// Render a Markdown document to an HTML fragment.
///
/// `doc_rel` is the document path relative to the server root, decoded and
/// without a leading slash (for example `guide/install.md`).
pub fn render_markdown(input: &str, doc_rel: &str) -> String {
    let arena = Arena::new();
    let mut options = Options::default();
    options.extension.table = true;
    options.extension.strikethrough = true;
    options.extension.autolink = true;
    options.extension.front_matter_delimiter = Some("---".to_string());
    options.render.r#unsafe = true;
    options.render.sourcepos = false;

    let root = parse_document(&arena, input, &options);
    let mut output = String::new();
    let ctx = RenderCtx::new(doc_rel);
    MvFormatter::format_document(root, &options, &mut output, ctx).expect("format markdown");
    output
}

create_formatter!(MvFormatter<RenderCtx>, {
    NodeValue::Link(ref nl) => |context, node, entering| {
        let _ = node;
        if !is_safe_link(&nl.url) {
            // Rejected targets render as their label content, never as a link.
            return Ok(ChildRendering::HTML);
        }
        let url = rewrite_target(&nl.url, &context.user.doc_rel);
        if entering {
            context.write_str("<a href=\"")?;
            context.escape_href(&url)?;
            if !nl.title.is_empty() {
                context.write_str("\" title=\"")?;
                context.escape(&nl.title)?;
            }
            context.write_str("\">")?;
        } else {
            context.write_str("</a>")?;
        }
    },
    NodeValue::Image(ref nl) => |context, node, entering| {
        if !is_safe_link(&nl.url) {
            // Rejected images render as their alt text, not as an image.
            return if entering {
                Ok(ChildRendering::Plain)
            } else {
                Ok(ChildRendering::HTML)
            };
        }
        let url = rewrite_target(&nl.url, &context.user.doc_rel);
        let wrapped = node
            .parent()
            .map(|parent| !matches!(&parent.data().value, NodeValue::Link(_)))
            .unwrap_or(true);
        if entering {
            if wrapped {
                context.write_str("<a class=\"zoom\" href=\"")?;
                context.escape_href(&url)?;
                context.write_str("\">")?;
            }
            context.write_str("<img src=\"")?;
            context.escape_href(&url)?;
            context.write_str("\" alt=\"")?;
            return Ok(ChildRendering::Plain);
        }
        if !nl.title.is_empty() {
            context.write_str("\" title=\"")?;
            context.escape(&nl.title)?;
        }
        context.write_str("\" />")?;
        if wrapped {
            context.write_str("</a>")?;
        }
    },
    NodeValue::Strikethrough => |context, node, entering| {
        let _ = node;
        if entering {
            context.write_str("<s>")?;
        } else {
            context.write_str("</s>")?;
        }
    },
    NodeValue::TableCell => |context, node, entering| {
        let Some(row) = node.parent() else {
            return Ok(ChildRendering::HTML);
        };
        let NodeValue::TableRow(in_header) = row.data().value else {
            return Ok(ChildRendering::HTML);
        };
        let Some(table) = row.parent() else {
            return Ok(ChildRendering::HTML);
        };
        let table_data = table.data();
        let alignments = match &table_data.value {
            NodeValue::Table(table) => &table.alignments,
            _ => return Ok(ChildRendering::HTML),
        };
        let mut index = 0usize;
        let mut sibling = row.first_child();
        while let Some(cell) = sibling {
            if cell.same_node(node) {
                break;
            }
            index += 1;
            sibling = cell.next_sibling();
        }
        if entering {
            context.cr()?;
            context.write_str(if in_header { "<th" } else { "<td" })?;
            if let Some(alignment) = alignments.get(index) {
                match alignment {
                    TableAlignment::Left => context.write_str(" style=\"text-align:left\"")?,
                    TableAlignment::Right => context.write_str(" style=\"text-align:right\"")?,
                    TableAlignment::Center => context.write_str(" style=\"text-align:center\"")?,
                    TableAlignment::None => {}
                }
            }
            context.write_str(">")?;
        } else {
            context.write_str(if in_header { "</th>" } else { "</td>" })?;
        }
    },
});

/// Mirrors VS Code 1.142's preview policy, except that `vscode:` links are
/// rejected on this standalone server.
fn is_safe_link(url: &str) -> bool {
    let trimmed = url.trim();
    let lower = trimmed.to_lowercase();
    if lower.starts_with("vscode:") || lower.starts_with("vscode-insiders:") {
        return false;
    }
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
        if let Some(rest) = trimmed.strip_prefix("data:image/") {
            return rest.contains(';');
        }
        return false;
    }
    true
}

fn rewrite_target(target: &str, doc_rel: &str) -> String {
    let target = target.trim();
    if target.is_empty()
        || target.starts_with('#')
        || has_scheme(target)
        || target.starts_with("//")
    {
        return target.to_string();
    }
    let (path, suffix) = split_suffix(target);
    let Some(decoded) = decode_twice(path) else {
        return target.to_string();
    };

    let mut segments: Vec<String> = if decoded.starts_with('/') {
        Vec::new()
    } else {
        parent_segments(doc_rel)
    };
    let root_relative = decoded.starts_with('/');
    let mut depth = segments.len();

    for segment in decoded.split('/') {
        match segment {
            "" | "." => {}
            ".." => {
                if depth == 0 {
                    return target.to_string();
                }
                segments.pop();
                depth -= 1;
            }
            _ => {
                segments.push(segment.to_string());
                depth += 1;
            }
        }
    }

    let encoded = segments
        .iter()
        .map(|segment| utf8_percent_encode(segment, URL_SEGMENT_SET).to_string())
        .collect::<Vec<_>>()
        .join("/");
    if root_relative || !encoded.is_empty() {
        format!("/{encoded}{suffix}")
    } else {
        format!("/{suffix}")
    }
}

fn split_suffix(target: &str) -> (&str, &str) {
    match target.find(['?', '#']) {
        Some(index) => (&target[..index], &target[index..]),
        None => (target, ""),
    }
}

fn decode_twice(value: &str) -> Option<String> {
    let once = percent_decode_str(value).decode_utf8().ok()?.to_string();
    let twice = percent_decode_str(&once).decode_utf8().ok()?.to_string();
    Some(twice)
}

fn parent_segments(doc_rel: &str) -> Vec<String> {
    let mut segments: Vec<String> = doc_rel
        .split('/')
        .filter(|part| !part.is_empty())
        .map(|part| part.to_string())
        .collect();
    segments.pop();
    segments
}

fn has_scheme(value: &str) -> bool {
    let mut chars = value.chars();
    let Some(first) = chars.next() else {
        return false;
    };
    if !first.is_ascii_alphabetic() {
        return false;
    }
    for ch in chars {
        if ch == ':' {
            return true;
        }
        if !(ch.is_ascii_alphanumeric() || matches!(ch, '+' | '-' | '.')) {
            return false;
        }
    }
    false
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn renders_core_markdown() {
        let html = render_markdown("# 标题\n\n**粗** 与 ~~删~~\n", "docs/a.md");
        assert!(html.contains("<h1>标题</h1>"));
        assert!(html.contains("<strong>粗</strong>"));
        assert!(html.contains("<s>删</s>"));
        assert!(!html.contains("<del>"));
    }

    #[test]
    fn table_alignment_uses_style() {
        let html = render_markdown("| a | b |\n|:--|--:|\n| 1 | 2 |\n", "docs/a.md");
        assert!(html.contains("style=\"text-align:left\""));
        assert!(html.contains("style=\"text-align:right\""));
        assert!(!html.contains("align=\"left\""));
    }

    #[test]
    fn protocol_policy() {
        let html = render_markdown("[x](javascript:alert(1))", "docs/a.md");
        assert!(!html.contains("href="));
        assert!(html.contains("x"));

        let html = render_markdown("![x](data:image/svg+xml;base64,AAAA)", "docs/a.md");
        assert!(html.contains("src=\"data:image/svg+xml;base64,AAAA\""));

        let html = render_markdown("[x](vscode:command:foo)", "docs/a.md");
        assert!(!html.contains("href="));

        let html = render_markdown("![x](data:image/png,AAAA)", "docs/a.md");
        assert!(!html.contains("<img"));
    }

    #[test]
    fn rewrites_relative_urls() {
        let html = render_markdown("![x](img/a.png)", "docs/a.md");
        assert!(html.contains("src=\"/docs/img/a.png\""));
        let html = render_markdown("![x](../img/a.png)", "docs/sub/a.md");
        assert!(html.contains("src=\"/docs/img/a.png\""));
        let html = render_markdown("[x](/abs/a.md)", "docs/a.md");
        assert!(html.contains("href=\"/abs/a.md\""));
        let html = render_markdown("[x](https://e.com/a)", "docs/a.md");
        assert!(html.contains("href=\"https://e.com/a\""));
        let html = render_markdown("[x](#锚)", "docs/a.md");
        assert!(html.contains("href=\"#%"));
    }

    #[test]
    fn double_decode_and_colon_are_safe() {
        let html = render_markdown("![x](a%2520b.png)", "docs/a.md");
        assert!(html.contains("src=\"/docs/a%20b.png\""));
        let html = render_markdown("[x](%6aavascript:alert(1))", "docs/a.md");
        assert!(!html.contains("href=\"javascript:"));
        assert!(html.contains("javascript%3A"));
    }

    #[test]
    fn front_matter_is_consumed_and_raw_html_passes() {
        let html = render_markdown("---\ntitle: x\n---\n\n# Hi", "docs/a.md");
        assert!(!html.contains("title: x"));
        assert!(html.contains("<h1>Hi</h1>"));
        let html = render_markdown("<div>raw</div>", "docs/a.md");
        assert!(html.contains("<div>raw</div>"));
    }

    #[test]
    fn image_zoom_wrapper_respects_links() {
        let html = render_markdown("![x](p.png)", "docs/a.md");
        assert!(html.contains("<a class=\"zoom\" href=\"/docs/p.png\">"));
        assert!(html.contains("<img src=\"/docs/p.png\""));

        let html = render_markdown("[![i](p.png)](u.md)", "docs/a.md");
        assert!(!html.contains("class=\"zoom\""));
    }

    #[test]
    fn no_task_checkboxes_or_heading_ids() {
        let html = render_markdown("- [x] done\n\n# Title", "docs/a.md");
        assert!(!html.contains("<input"));
        assert!(html.contains("[x] done"));
        assert!(!html.contains("<h1 id="));
    }

    #[test]
    fn golden_outputs_are_frozen() {
        let cases = [
            ("# Hi\n", "<h1>Hi</h1>\n"),
            ("**粗**\n", "<p><strong>粗</strong></p>\n"),
            ("~~删~~\n", "<p><s>删</s></p>\n"),
            ("- [x] done\n", "<ul>\n<li>[x] done</li>\n</ul>\n"),
            (
                "![x](p.png)\n",
                "<p><a class=\"zoom\" href=\"/docs/p.png\"><img src=\"/docs/p.png\" alt=\"x\" /></a></p>\n",
            ),
            ("[x](javascript:alert(1))\n", "<p>x</p>\n"),
            (
                "[x](data:image/png;base64,AAAA)\n",
                "<p><a href=\"data:image/png;base64,AAAA\">x</a></p>\n",
            ),
            ("[x](vscode:command:foo)\n", "<p>x</p>\n"),
            (
                "[x](img/a.png)\n",
                "<p><a href=\"/docs/img/a.png\">x</a></p>\n",
            ),
            ("---\ntitle: x\n---\n\n# Hi\n", "<h1>Hi</h1>\n"),
            ("<div>raw</div>\n", "<div>raw</div>\n"),
            ("文字\n---\n", "<h2>文字</h2>\n"),
            ("中文*强调*中文\n", "<p>中文<em>强调</em>中文</p>\n"),
            ("2*3*4\n", "<p>2<em>3</em>4</p>\n"),
        ];
        for (input, expected) in cases {
            assert_eq!(render_markdown(input, "docs/a.md"), expected, "{input:?}");
        }
    }

    #[test]
    fn large_input_stays_usable() {
        let input = "word **bold** [x](u.md)\n\n".repeat(40_000);
        let start = std::time::Instant::now();
        let html = render_markdown(&input, "docs/a.md");
        assert!(!html.is_empty());
        assert!(start.elapsed() < std::time::Duration::from_secs(5));
    }
}
