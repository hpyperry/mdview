//! Embedded CSS/JS assets.
//!
//! P3 embeds highlight.js and the browser-side helpers; VS Code markdown.css is
//! added on top of this base chrome.

pub const HIGHLIGHT_JS: &[u8] = include_bytes!("../assets/highlight.min.js");
pub const HIGHLIGHT_CSS: &str = include_str!("../assets/highlight.css");
pub const MARKDOWN_CSS: &str = include_str!("../assets/markdown.css");
pub const MDVIEW_JS: &str = include_str!("../assets/mdview.js");

/// FNV-1a over all cacheable assets. The query string on `/_assets/...` carries
/// this value and the responses are `immutable`, so a rebuilt bundle gets a new
/// URL without restarting config or clearing browser caches.
pub fn asset_version() -> &'static str {
    use std::sync::OnceLock;
    static VERSION: OnceLock<String> = OnceLock::new();
    VERSION.get_or_init(|| {
        let mut hash = 0xcbf2_9ce4_8422_2325u64;
        for bytes in [
            HIGHLIGHT_JS,
            HIGHLIGHT_CSS.as_bytes(),
            MARKDOWN_CSS.as_bytes(),
            MDVIEW_JS.as_bytes(),
        ] {
            for &byte in bytes {
                hash ^= u64::from(byte);
                hash = hash.wrapping_mul(0x0000_0100_0000_01b3);
            }
        }
        format!("{hash:016x}")
    })
}

pub const SERVER_CSS: &str = r#"
:root {
  color-scheme: light dark;
  --fg: #1f2328;
  --muted: #656d76;
  --bg: #ffffff;
  --panel: #f6f8fa;
  --border: #d0d7de;
  --accent: #0969da;
  --vscode-editor-foreground: var(--fg);
  --vscode-editor-background: var(--bg);
  --vscode-textCodeBlock-background: var(--panel);
  --vscode-widget-border: var(--border);
  --vscode-editor-font-family: "SF Mono", Monaco, Menlo, Consolas, monospace;
  --vscode-toolbar-hoverBackground: rgba(90, 93, 94, .31);
  --vscode-toolbar-activeBackground: rgba(99, 102, 103, .31);
  --vscode-testing-iconPassed: #73c991;
  --vscode-editorError-foreground: #f48771;
  --vscode-inputValidation-errorBackground: rgba(244, 135, 113, .1);
  --vscode-contrastBorder: transparent;
}
@media (prefers-color-scheme: dark) {
  :root {
    --fg: #e6edf3;
    --muted: #8b949e;
    --bg: #0d1117;
    --panel: #161b22;
    --border: #30363d;
    --accent: #4493f8;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0;
  padding: 0;
  background: var(--bg);
  color: var(--fg);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
  font-size: 15px;
  line-height: 1.55;
}
header {
  border-bottom: 1px solid var(--border);
  padding: 14px 24px;
  background: var(--panel);
}
header .crumb { color: var(--muted); }
header a { color: var(--accent); text-decoration: none; }
header a:hover { text-decoration: underline; }
main { padding: 24px; max-width: 1100px; }
main > h1 { font-size: 22px; margin: 0 0 16px; }
.note { color: var(--muted); }
ul.dirlist { list-style: none; padding: 0; margin: 0; border: 1px solid var(--border); border-radius: 8px; overflow: hidden; }
ul.dirlist li { display: flex; gap: 12px; align-items: baseline; padding: 9px 12px; border-top: 1px solid var(--border); }
ul.dirlist li:first-child { border-top: 0; }
ul.dirlist .nm { flex: 1; min-width: 0; overflow-wrap: anywhere; }
ul.dirlist .meta { color: var(--muted); font-variant-numeric: tabular-nums; white-space: nowrap; }
ul.dirlist .dl { color: var(--accent); white-space: nowrap; }
a { color: var(--accent); }
.source { display: grid; grid-template-columns: auto 1fr; border: 1px solid var(--border); border-radius: 8px; overflow: auto; background: var(--panel); }
.source .gutter { margin: 0; padding: 12px 10px 12px 14px; text-align: right; color: var(--muted); border-right: 1px solid var(--border); user-select: none; }
.source .gutter a { color: inherit; text-decoration: none; display: block; }
.source .gutter a:hover { color: var(--accent); }
.source .code { margin: 0; padding: 12px 16px; overflow-x: auto; }
.source .code code { font-family: "SF Mono", Monaco, Menlo, Consolas, monospace; font-size: 13px; line-height: 1.55; white-space: pre; }
.toolbar { display: flex; gap: 16px; align-items: center; margin: 0 0 14px; color: var(--muted); }
.search { display: flex; gap: 8px; margin: 0 0 18px; }
.search input { flex: 1; max-width: 420px; padding: 7px 10px; border: 1px solid var(--border); border-radius: 6px; background: var(--bg); color: var(--fg); }
.search button { padding: 7px 14px; border: 1px solid var(--border); border-radius: 6px; background: var(--panel); color: var(--fg); cursor: pointer; }
.search button:hover { border-color: var(--accent); }
.hits { margin: 0 0 22px; }
.hits h2 { font-size: 17px; margin: 0 0 8px; }
.hits ul { margin: 0; padding-left: 20px; }
.hits li { margin: 5px 0; }
.hits .line { color: var(--muted); font-variant-numeric: tabular-nums; }
.markdown-body { max-width: 900px; font-size: 14px; line-height: 22px; }
.source .gutter, .source .code { background: transparent; border: 0; }
.source .code code { display: block; color: var(--fg); }
pre { position: relative; }
.copy-btn {
  position: absolute; top: 6px; right: 8px; z-index: 1;
  padding: 3px 9px; border: 1px solid var(--border); border-radius: 6px;
  background: var(--panel); color: var(--muted); font: inherit; font-size: 12px;
  cursor: pointer; opacity: 0; transition: opacity .12s ease;
}
pre:hover .copy-btn, .copy-btn:focus-visible { opacity: 1; }
.zoomable { cursor: zoom-in; }
.zoomdlg {
  border: 0; padding: 0; background: transparent; color: #fff;
  max-width: none; max-height: none; outline: none;
}
.zoomdlg::backdrop { background: rgba(0, 0, 0, .72); }
.zoomdlg img { display: block; max-width: 92vw; max-height: 86vh; object-fit: contain; border-radius: 6px; }
.zoom-caption { margin: 10px 0 0; text-align: center; font-size: 13px; color: #fff; }
.zoom-close {
  position: fixed; top: 18px; right: 22px; width: 34px; height: 34px;
  border: 1px solid rgba(255,255,255,.35); border-radius: 8px;
  background: rgba(0,0,0,.35); color: #fff; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
}
.zoom-close:focus-visible { outline: 2px solid #fff; outline-offset: 2px; }
.totop {
  position: fixed; right: 22px; bottom: 22px; width: 38px; height: 38px;
  border: 1px solid var(--border); border-radius: 50%;
  background: var(--panel); color: var(--fg); cursor: pointer;
  font-size: 18px; line-height: 1; box-shadow: 0 2px 8px rgba(0,0,0,.12);
}
.totop:hover { border-color: var(--accent); color: var(--accent); }
footer { padding: 20px 24px; color: var(--muted); font-size: 12px; }
"#;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn asset_version_is_stable_hex() {
        let version = asset_version();
        assert_eq!(version.len(), 16);
        assert!(version.chars().all(|ch| ch.is_ascii_hexdigit()));
        assert_eq!(version, asset_version());
    }
}
