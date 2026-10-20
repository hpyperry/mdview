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
  --bg: light-dark(#f6f8fa, #0d1117);
  --surface: light-dark(#ffffff, #161b22);
  --surface-2: light-dark(#f6f8fa, #21262d);
  --fg: light-dark(#1f2328, #e6edf3);
  --muted: light-dark(#59636e, #9198a1);
  --border: light-dark(#d1d9e0, #30363d);
  --accent: light-dark(#0969da, #4493f8);
  --accent-soft: light-dark(#ddf4ff, #121d2f);
  --mark: light-dark(#fff8c5, #4a3200);
  --code-bg: light-dark(#f6f8fa, #0d1117);
  --shadow: light-dark(0 1px 0 rgba(31,35,40,.04), 0 1px 0 rgba(1,4,9,.4));
  --panel: var(--surface-2);
  --vscode-editor-foreground: var(--fg);
  --vscode-editor-background: var(--surface);
  --vscode-textCodeBlock-background: var(--code-bg);
  --vscode-widget-border: var(--border);
  --vscode-editor-font-family: "SF Mono", Monaco, Menlo, Consolas, monospace;
  --vscode-toolbar-hoverBackground: rgba(90, 93, 94, .2);
  --vscode-toolbar-activeBackground: rgba(99, 102, 103, .28);
  --vscode-textLink-foreground: var(--accent);
  --vscode-testing-iconPassed: #73c991;
  --vscode-editorError-foreground: #f48771;
  --vscode-inputValidation-errorBackground: rgba(244, 135, 113, .1);
  --vscode-contrastBorder: transparent;
  --nav-width: 240px;
  --toc-width: 220px;
}
html[data-theme="light"] { color-scheme: light; }
html[data-theme="dark"] { color-scheme: dark; }

html, body { margin: 0; padding: 0; }
body {
  background: var(--bg);
  color: var(--fg);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans", Helvetica, Arial, sans-serif;
  font-size: 15px;
  line-height: 1.55;
}
* { box-sizing: border-box; }
a { color: var(--accent); }
button, input { font: inherit; }
.icon { width: 16px; height: 16px; fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; flex: 0 0 auto; }
.sr-only {
  position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px;
  overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; border: 0;
}

/* top bar */
.topbar {
  display: flex; align-items: center; gap: 12px; min-height: 58px;
  padding: 0 18px; background: var(--surface); border-bottom: 1px solid var(--border);
  position: sticky; top: 0; z-index: 30;
}
.icon-btn {
  display: inline-flex; align-items: center; justify-content: center;
  width: 32px; height: 32px; border: 1px solid transparent; border-radius: 6px;
  background: transparent; color: var(--muted); cursor: pointer; flex: 0 0 auto;
}
.icon-btn:hover { background: var(--surface-2); color: var(--fg); border-color: var(--border); }
.icon-btn:focus-visible, a:focus-visible, button:focus-visible, input:focus-visible {
  outline: 2px solid var(--accent); outline-offset: 2px;
}
.brand {
  display: inline-flex; align-items: center; gap: 8px; border: 0; background: transparent;
  color: var(--fg); font-weight: 700; font-size: 15px; cursor: pointer; padding: 0; text-decoration: none;
}
.brand-mark {
  display: inline-grid; place-items: center; width: 24px; height: 24px; border-radius: 6px;
  background: var(--accent); color: #fff; font-size: 14px; font-weight: 800;
}
.root-name {
  color: var(--muted); font-size: 13px; text-decoration: none; border-left: 1px solid var(--border);
  padding-left: 12px; white-space: nowrap;
}
.root-name:hover { color: var(--accent); }
.crumbs {
  display: flex; align-items: center; gap: 5px; color: var(--muted); font-size: 13px;
  min-width: 0; white-space: nowrap; overflow: hidden;
}
.crumbs a { color: var(--muted); text-decoration: none; }
.crumbs a:hover { color: var(--accent); text-decoration: underline; }
.crumbs .current { color: var(--fg); font-weight: 500; overflow: hidden; text-overflow: ellipsis; }
.crumbs .icon { width: 13px; height: 13px; opacity: .7; }
.searchbox {
  margin-left: auto; display: flex; align-items: center; gap: 6px;
  min-width: 220px; max-width: 440px; flex: 1 1 300px;
  border: 1px solid var(--border); border-radius: 8px; background: var(--surface-2);
  padding: 4px 5px 4px 10px;
}
.searchbox:focus-within { border-color: var(--accent); background: var(--surface); box-shadow: 0 0 0 3px var(--accent-soft); }
.searchbox .icon { width: 15px; height: 15px; color: var(--muted); }
.searchbox input { border: 0; outline: 0; background: transparent; color: var(--fg); min-width: 0; flex: 1; font-size: 13px; padding: 4px 0; }
.searchbox input::placeholder { color: var(--muted); }
.searchbox kbd {
  border: 1px solid var(--border); border-bottom-width: 2px; border-radius: 4px;
  background: var(--surface); color: var(--muted); font-size: 11px; padding: 0 5px; line-height: 18px;
}
.searchbox button {
  border: 1px solid var(--border); border-radius: 6px; background: var(--surface);
  color: var(--fg); font-size: 12px; padding: 4px 10px; cursor: pointer;
}
.searchbox button:hover { border-color: var(--accent); color: var(--accent); }
html.no-js .sidebar-toggle, html.no-js .theme-toggle, html.no-js .toc-toggle { display: none; }
.toc-toggle[hidden] { display: none; }
html.no-js .toc-col, html.no-js .toc-inline { display: none !important; }
html.no-js .shell.has-toc { grid-template-columns: var(--nav-width) minmax(0,1fr) !important; }
html.no-js[data-sidebar="collapsed"] .shell.has-toc { grid-template-columns: 0 minmax(0,1fr) !important; }
.theme-icon { display: none; }
.theme-system { display: inline-flex; }
html[data-theme-mode="light"] .theme-system,
html[data-theme-mode="dark"] .theme-system { display: none; }
html[data-theme-mode="light"] .theme-light { display: inline-flex; }
html[data-theme-mode="dark"] .theme-dark { display: inline-flex; }

/* shell */
.shell { display: grid; grid-template-columns: var(--nav-width) minmax(0, 1fr); position: relative; }
.sidebar {
  background: var(--surface); border-right: 1px solid var(--border);
  padding: 18px 12px 22px;
  position: sticky; top: 58px; height: calc(100vh - 58px);
  align-self: start; min-height: 0; max-height: none; overflow: auto;
}
html[data-sidebar="collapsed"] .shell { grid-template-columns: 0 minmax(0, 1fr); }
html[data-sidebar="collapsed"] .sidebar { padding: 0; border: 0; overflow: hidden; }
.side-head {
  display: flex; align-items: center; justify-content: space-between; gap: 8px;
  padding: 0 8px 10px; color: var(--muted); font-size: 11px;
  text-transform: uppercase; letter-spacing: .06em;
}
.side-current { color: var(--fg); font-weight: 600; text-transform: none; letter-spacing: 0; overflow: hidden; text-overflow: ellipsis; }
.side-label { padding: 12px 8px 5px; color: var(--muted); font-size: 11px; font-weight: 600; letter-spacing: .04em; }
.side-link, .side-parent {
  display: flex; align-items: center; gap: 8px; padding: 6px 8px; border-radius: 6px;
  color: var(--fg); text-decoration: none; font-size: 13px; line-height: 1.4;
}
.side-link .icon, .side-parent .icon { color: var(--muted); width: 15px; height: 15px; }
.side-link:hover, .side-parent:hover { background: var(--surface-2); color: var(--accent); }
.side-link:hover .icon, .side-parent:hover .icon { color: var(--accent); }
.side-link.active { background: var(--accent-soft); color: var(--accent); font-weight: 600; }
.side-link.active .icon { color: var(--accent); }
.side-parent { margin: 0 0 6px; color: var(--muted); font-size: 12px; }
.side-empty { padding: 10px 8px; color: var(--muted); font-size: 12px; line-height: 1.5; }
.side-foot { margin: 22px 8px 0; padding-top: 12px; border-top: 1px solid var(--border); color: var(--muted); font-size: 11px; line-height: 1.6; }
.scrim { position: fixed; inset: 0; z-index: 35; background: rgba(0,0,0,.45); }
.scrim[hidden] { display: none; }
.main { min-width: 0; padding: 26px 34px 60px; }
.content-card {
  max-width: 1040px; margin: 0 auto; background: var(--surface);
  border: 1px solid var(--border); border-radius: 10px; box-shadow: var(--shadow);
}

/* directory */
.dir-head, .search-head { padding: 26px 30px 18px; border-bottom: 1px solid var(--border); }
.dir-head h1, .search-head h1 { margin: 0; font-size: 24px; line-height: 1.25; letter-spacing: -.01em; }
.dir-head p, .search-head p { margin: 6px 0 0; color: var(--muted); font-size: 13px; }
.dir-section { padding: 6px 18px 18px; }
.dir-section h2 { margin: 16px 12px 6px; font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: .06em; }
.dir-row { display: flex; align-items: center; gap: 12px; padding: 9px 12px; border-radius: 6px; border: 1px solid transparent; }
.dir-row:hover { background: var(--surface-2); border-color: var(--border); }
.file-icon { width: 30px; height: 30px; display: grid; place-items: center; border-radius: 7px; background: var(--surface-2); color: var(--muted); flex: 0 0 auto; }
.file-icon.folder { color: var(--accent); background: var(--accent-soft); }
.file-icon .icon { width: 16px; height: 16px; }
.dir-row .nm { flex: 1; min-width: 0; color: var(--fg); text-decoration: none; font-size: 13px; font-weight: 500; overflow-wrap: anywhere; }
.dir-row .nm:hover { color: var(--accent); text-decoration: underline; }
.dir-row .meta { color: var(--muted); font-size: 12px; white-space: nowrap; }
.dir-row .dl { display: inline-flex; align-items: center; gap: 4px; color: var(--muted); font-size: 12px; text-decoration: none; opacity: 0; transition: opacity .12s ease; }
.dir-row:hover .dl, .dir-row:focus-within .dl { opacity: 1; color: var(--accent); }
.dir-row .dl .icon { width: 14px; height: 14px; }

/* markdown */
.article-toolbar { display: flex; align-items: center; gap: 16px; padding: 16px 30px; border-bottom: 1px solid var(--border); }
.doc-meta { color: var(--muted); font-size: 12px; }
.page-actions { display: flex; align-items: center; gap: 8px; margin-left: auto; }
.action {
  display: inline-flex; align-items: center; gap: 5px; padding: 5px 9px;
  border: 1px solid var(--border); border-radius: 6px; background: var(--surface-2);
  color: var(--fg); font-size: 12px; text-decoration: none; cursor: pointer;
}
.action:hover { border-color: var(--accent); color: var(--accent); }
.action.primary { background: var(--accent); border-color: var(--accent); color: #fff; }
.action.primary:hover { filter: brightness(1.06); color: #fff; }
.action .icon { width: 14px; height: 14px; }
.markdown-body { max-width: 780px; margin: 0 auto; padding: 30px 30px 58px; font-size: 16px; line-height: 1.7; }
.markdown-body h1 { font-size: 2em; line-height: 1.25; margin: 0 0 18px; letter-spacing: -.015em; border-bottom: 0; padding-bottom: 0; }
.markdown-body h2 { font-size: 1.45em; line-height: 1.35; margin: 34px 0 10px; padding-bottom: 6px; border-bottom: 1px solid var(--border); }
.markdown-body h3 { font-size: 1.18em; margin: 24px 0 8px; }
.markdown-body p, .markdown-body ul, .markdown-body ol, .markdown-body blockquote { margin-bottom: 16px; }
.markdown-body li { margin: 4px 0; }
.markdown-body blockquote { margin: 16px 0; padding: 2px 16px; border-left: 3px solid var(--accent); background: var(--accent-soft); color: var(--fg); border-radius: 0 6px 6px 0; }
.markdown-body img { max-width: 100%; height: auto; border-radius: 6px; }
.markdown-body table { display: table; width: 100%; margin: 12px 0 18px; }
.markdown-body th, .markdown-body td { padding: 7px 10px; }
.markdown-body :not(pre) > code { background: var(--surface-2); border: 1px solid var(--border); border-radius: 5px; padding: .1em .32em; }

/* toc */
.toc-inline { max-width: 780px; margin: 22px auto 0; padding: 0 30px; }
.toc-inline[hidden] { display: none; }
.toc { border: 1px solid var(--border); border-radius: 8px; background: var(--surface-2); padding: 10px 14px; }
.toc summary { cursor: pointer; color: var(--fg); font-size: 13px; font-weight: 600; }
.toc-list { display: flex; flex-direction: column; gap: 1px; margin-top: 8px; }
.toc-list a {
  display: block; color: var(--muted); text-decoration: none; font-size: 12px;
  line-height: 1.45; padding: 4px 8px; border-left: 2px solid transparent; border-radius: 0 4px 4px 0;
}
.toc-list a.toc-h3 { padding-left: 20px; font-size: 11.5px; }
.toc-list a:hover { color: var(--accent); background: var(--surface); }
.toc-list a.active { color: var(--accent); background: var(--accent-soft); border-left-color: var(--accent); font-weight: 600; }
.toc-col {
  display: none; background: var(--surface); border-left: 1px solid var(--border);
  padding: 18px 14px 24px; overflow: auto;
}
.toc-col[hidden] { display: none; }
.toc-head { font-size: 11px; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: .06em; margin: 0 8px 10px; }
.toc-toggle { display: none; }
.toc-toggle[hidden] { display: none; }
.markdown-body h2, .markdown-body h3 { scroll-margin-top: 74px; }
.source .gutter a[id], .source-chunk .gutter a[id] { scroll-margin-top: 74px; }
@media (min-width: 1360px) {
  .shell.has-toc { grid-template-columns: var(--nav-width) minmax(0,1fr) var(--toc-width); }
  html[data-sidebar="collapsed"] .shell.has-toc { grid-template-columns: 0 minmax(0,1fr) var(--toc-width); }
  html[data-toc="hidden"] .shell.has-toc { grid-template-columns: var(--nav-width) minmax(0,1fr); }
  html[data-toc="hidden"][data-sidebar="collapsed"] .shell.has-toc { grid-template-columns: 0 minmax(0,1fr); }
  .shell.has-toc.no-toc { grid-template-columns: var(--nav-width) minmax(0,1fr); }
  html[data-sidebar="collapsed"] .shell.has-toc.no-toc { grid-template-columns: 0 minmax(0,1fr); }
  .shell.has-toc .toc-col {
    display: block; position: sticky; top: 58px; height: calc(100vh - 58px);
    align-self: start; min-height: 0; max-height: none;
  }
  html[data-toc="hidden"] .shell.has-toc .toc-col { display: none; }
  .shell.has-toc .toc-inline { display: none; }
  .toc-toggle { display: inline-flex; }
}

/* code blocks */
.code-block { margin: 16px 0 20px; border: 1px solid var(--border); border-radius: 8px; overflow: hidden; background: var(--code-bg); }
.code-bar { display: flex; align-items: center; justify-content: space-between; padding: 5px 8px 5px 12px; background: var(--surface-2); border-bottom: 1px solid var(--border); color: var(--muted); font-size: 12px; }
.code-bar .lang { display: inline-flex; align-items: center; gap: 6px; }
.code-bar .lang .icon { width: 14px; height: 14px; }
.copy-btn { display: inline-flex; align-items: center; gap: 5px; border: 1px solid transparent; border-radius: 5px; background: transparent; color: var(--muted); font-size: 12px; padding: 3px 7px; cursor: pointer; }
.copy-btn:hover { background: var(--surface); border-color: var(--border); color: var(--fg); }
.copy-btn .icon { width: 14px; height: 14px; }
.code-block pre, .markdown-body .code-block pre { margin: 0; padding: 14px 16px; overflow-x: auto; background: var(--code-bg); border: 0; border-radius: 0; font-size: 13px; line-height: 1.62; }
.code-block code { background: none; border: 0; padding: 0; }

/* source */
.page-head { display: flex; align-items: flex-start; gap: 20px; padding: 22px 30px 18px; border-bottom: 1px solid var(--border); }
.page-head .grow { flex: 1; min-width: 0; }
.page-head h1 { margin: 0; font-size: 24px; line-height: 1.25; }
.page-head p { margin: 6px 0 0; color: var(--muted); font-size: 13px; overflow-wrap: anywhere; }
.source-wrap { overflow: auto; }
.source { display: grid; grid-template-columns: auto minmax(0,1fr); background: var(--code-bg); }
.source .gutter { margin: 0; padding: 14px 10px 14px 14px; text-align: right; color: var(--muted); border-right: 1px solid var(--border); user-select: none; font-size: 13px; line-height: 1.65; }
.source .gutter a { color: inherit; text-decoration: none; display: block; }
.source .gutter a:hover { color: var(--accent); }
.source .code { margin: 0; padding: 14px 16px; overflow-x: auto; background: transparent; border: 0; border-radius: 0; }
.source .code code { display: block; background: none; border: 0; padding: 0; color: var(--fg); font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace; font-size: 13px; line-height: 1.65; white-space: pre; }
.source-line:target, .source .gutter a:target { background: var(--mark); }
.source-chunked { overflow-x: auto; }
.source-chunk {
  position: relative; display: grid; grid-template-columns: max-content minmax(0, 1fr);
  width: max-content; min-width: 100%;
  background: var(--code-bg);
  content-visibility: auto;
  contain-intrinsic-width: none;
  contain-intrinsic-height: calc(var(--rows) * 21px + 28px);
}
.source-chunk .gutter {
  margin: 0; padding: 14px 10px 14px 14px; text-align: right;
  color: var(--muted); background: var(--code-bg);
  border-right: 1px solid var(--border); user-select: none;
  font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
  font-size: 13px; line-height: 21px; white-space: pre;
  position: relative; z-index: 1;
}
.source-chunk .gutter a { color: inherit; text-decoration: none; display: block; }
.source-chunk .gutter a:hover { color: var(--accent); }
.source-chunk .gutter a.target { background: var(--mark); color: var(--fg); }
.source-chunk .code {
  margin: 0; padding: 14px 16px; overflow: visible; background: transparent;
  border: 0; border-radius: 0; position: relative; z-index: 1;
}
.source-chunk .code code {
  display: block; background: none; border: 0; padding: 0; color: var(--fg);
  font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
  font-size: 13px; line-height: 21px; white-space: pre;
}
.source-target-line {
  position: absolute; left: 0; right: 0; height: 21px;
  background: var(--mark); pointer-events: none; z-index: 0;
}
.source-note {
  margin: 0; padding: 9px 16px; border-top: 1px solid var(--border);
  border-radius: 0 0 10px 10px;
  background: var(--surface-2); color: var(--muted); font-size: 12px;
}

/* search */
.page-body { padding: 22px 30px 46px; }
.search-note { color: var(--muted); font-size: 13px; }
.result-group { margin: 0 0 14px; border: 1px solid var(--border); border-radius: 8px; overflow: hidden; }
.result-head { display: flex; align-items: center; gap: 10px; padding: 10px 14px; background: var(--surface-2); border-bottom: 1px solid var(--border); }
.result-head .path { flex: 1; min-width: 0; font-size: 13px; font-weight: 600; display: flex; align-items: center; gap: 7px; overflow-wrap: anywhere; }
.result-head .path .icon { color: var(--muted); }
.badge { border: 1px solid var(--border); border-radius: 999px; padding: 1px 8px; font-size: 11px; color: var(--muted); background: var(--surface); white-space: nowrap; }
.badge-doc { color: var(--accent); border-color: var(--accent); background: var(--accent-soft); }
.hit { padding: 10px 14px; border-top: 1px solid var(--border); }
.hit:first-of-type { border-top: 0; }
.hit-top { display: flex; flex-wrap: wrap; align-items: baseline; gap: 12px; color: var(--muted); font-size: 12px; }
.hit-top a { color: var(--accent); text-decoration: none; }
.hit-top a:hover { text-decoration: underline; }
.hit-snippet { margin: 5px 0 0; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12.5px; line-height: 1.6; color: var(--fg); white-space: pre-wrap; overflow-wrap: anywhere; }
.hit-snippet mark { background: var(--mark); color: var(--fg); border-radius: 2px; padding: 0 1px; }

/* trust, empty, errors */
.trust-panel { max-width: 560px; margin: 0 auto; padding: 56px 30px 64px; text-align: center; }
.trust-icon { width: 54px; height: 54px; margin: 0 auto 14px; display: grid; place-items: center; border-radius: 50%; background: var(--accent-soft); color: var(--accent); }
.trust-icon .icon { width: 26px; height: 26px; }
.trust-panel h1 { margin: 0 0 8px; font-size: 24px; }
.trust-panel p { color: var(--muted); }
.trust-path { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12.5px; }
.trust-actions { display: flex; justify-content: center; gap: 10px; margin-top: 18px; }
.empty-state { padding: 48px 20px; text-align: center; color: var(--muted); font-size: 14px; }
.empty-state h1 { color: var(--fg); margin: 0 0 8px; font-size: 24px; }
.empty-state .icon { width: 30px; height: 30px; margin-bottom: 8px; opacity: .6; }
.empty-state .action { margin-top: 10px; }

/* image zoom and back to top (unchanged behaviour) */
.zoomable { cursor: zoom-in; }
.zoomdlg { border: 0; padding: 0; background: transparent; color: #fff; max-width: none; max-height: none; outline: none; }
.zoomdlg::backdrop { background: rgba(0, 0, 0, .72); }
.zoomdlg img { display: block; max-width: 92vw; max-height: 86vh; object-fit: contain; border-radius: 6px; }
.zoom-caption { margin: 10px 0 0; text-align: center; font-size: 13px; color: #fff; }
.zoom-close { position: fixed; top: 18px; right: 22px; width: 34px; height: 34px; border: 1px solid rgba(255,255,255,.35); border-radius: 8px; background: rgba(0,0,0,.35); color: #fff; cursor: pointer; display: flex; align-items: center; justify-content: center; }
.zoom-close:focus-visible { outline: 2px solid #fff; outline-offset: 2px; }
.totop { position: fixed; right: 22px; bottom: 22px; width: 38px; height: 38px; border: 1px solid var(--border); border-radius: 50%; background: var(--surface); color: var(--fg); cursor: pointer; font-size: 18px; line-height: 1; box-shadow: 0 2px 8px rgba(0,0,0,.12); }
.totop:hover { border-color: var(--accent); color: var(--accent); }

@media (max-width: 900px) {
  .root-name, .crumbs { display: none; }
  .topbar { flex-wrap: wrap; padding: 8px 12px; gap: 8px; }
  .searchbox { order: 9; flex: 1 0 100%; max-width: none; margin-left: 0; }
  .shell { grid-template-columns: 1fr; }
  .sidebar {
    position: fixed; left: 0; top: 0; bottom: 0; z-index: 40; width: 280px;
    transform: translateX(-100%); transition: transform .16s ease; box-shadow: 8px 0 24px rgba(0,0,0,.18);
    height: 100vh; min-height: 100vh; max-height: none;
  }
  html[data-sidebar-open="1"] .sidebar { transform: none; }
  html[data-sidebar="collapsed"] .sidebar { padding: 18px 12px 22px; overflow: auto; }
  .main { padding: 14px 12px 40px; }
  .markdown-body { padding: 22px 18px 40px; }
  .toc-inline { padding: 0 18px; }
  .article-toolbar, .page-head, .dir-head, .search-head, .page-body { padding-left: 18px; padding-right: 18px; }
  .dir-row .dl { opacity: 1; }
  .action span { display: none; }
  .action { padding: 6px 8px; }
}
@media (prefers-reduced-motion: reduce) {
  * { transition: none !important; scroll-behavior: auto !important; }
}
@media print {
  .topbar, .sidebar, .article-toolbar, .zoomdlg, .totop, .code-bar { display: none !important; }
  .shell { display: block; }
  .main { padding: 0; }
  .content-card { border: 0; box-shadow: none; }
  .source-chunk { content-visibility: visible; }
}
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
