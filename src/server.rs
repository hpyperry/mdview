use std::collections::HashMap;
use std::ffi::OsStr;
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant, SystemTime};

use axum::Router;
use axum::body::{Body, Bytes};
use axum::extract::{Query, State};
use axum::http::{Method, StatusCode, Uri, header};
use axum::response::Response;
use axum::routing::get;
use percent_encoding::{
    AsciiSet, CONTROLS, NON_ALPHANUMERIC, percent_decode_str, utf8_percent_encode,
};
use rand::RngCore;
use time::OffsetDateTime;
use tokio::io::AsyncReadExt;
use tokio_util::io::ReaderStream;
use walkdir::WalkDir;

use crate::assets::{HIGHLIGHT_CSS, HIGHLIGHT_JS, MARKDOWN_CSS, MDVIEW_JS, SERVER_CSS};
use crate::cli::Cli;
use crate::render::render_markdown;
use crate::trust::TrustState;

const IMAGE_EXT: &[&str] = &[
    "png", "jpg", "jpeg", "gif", "svg", "webp", "bmp", "ico", "avif",
];
const TEXT_EXT: &[&str] = &[
    "txt",
    "log",
    "csv",
    "tsv",
    "json",
    "xml",
    "html",
    "htm",
    "css",
    "scss",
    "sass",
    "less",
    "js",
    "mjs",
    "cjs",
    "jsx",
    "ts",
    "tsx",
    "vue",
    "svelte",
    "py",
    "sh",
    "bash",
    "zsh",
    "fish",
    "c",
    "cc",
    "cpp",
    "cxx",
    "h",
    "hpp",
    "cs",
    "java",
    "kt",
    "kts",
    "go",
    "rs",
    "rb",
    "php",
    "pl",
    "pm",
    "lua",
    "sql",
    "ini",
    "cfg",
    "conf",
    "properties",
    "env",
    "diff",
    "patch",
    "mk",
    "bat",
    "ps1",
    "rst",
    "tex",
    "yaml",
    "yml",
    "toml",
    "gradle",
    "lock",
    "proto",
    "graphql",
    "gql",
    "srt",
    "vtt",
    "mdx",
];
const TEXT_NAMES: &[&str] = &[
    "Makefile",
    "Dockerfile",
    "Containerfile",
    "README",
    "LICENSE",
    "NOTICE",
    "Cargo.lock",
    "Cargo.toml",
    "go.mod",
    "go.sum",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "requirements.txt",
    "Procfile",
    "Gemfile",
    "Rakefile",
    "Vagrantfile",
    ".gitignore",
    ".gitattributes",
    ".dockerignore",
    ".editorconfig",
    ".npmrc",
    ".nvmrc",
    ".env",
];
const SKIP_DIRS: &[&str] = &[
    ".git",
    ".svn",
    ".hg",
    ".idea",
    ".vscode",
    "node_modules",
    "__pycache__",
];
const PATH_SEGMENT_SET: &AsciiSet = &CONTROLS
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
    .add(b'\\');

#[derive(Clone)]
pub struct AppState {
    pub root: PathBuf,
    pub safe: bool,
    pub no_search: bool,
    pub max_preview: u64,
    pub trust: TrustState,
    tokens: Arc<Mutex<HashMap<String, TokenEntry>>>,
    cache: Arc<Mutex<HashMap<PathBuf, CacheEntry>>>,
}

#[derive(Debug, Clone)]
struct TokenEntry {
    path: String,
    expires: Instant,
}

#[derive(Debug, Clone)]
struct CacheEntry {
    mtime: SystemTime,
    size: u64,
    html: String,
}

impl AppState {
    pub fn new(
        root: PathBuf,
        safe: bool,
        no_search: bool,
        max_preview: u64,
        trust: TrustState,
    ) -> Self {
        Self {
            root,
            safe,
            no_search,
            max_preview,
            trust,
            tokens: Arc::new(Mutex::new(HashMap::new())),
            cache: Arc::new(Mutex::new(HashMap::new())),
        }
    }

    fn store_token(&self, rel: &str) -> String {
        let token = random_nonce();
        let now = Instant::now();
        let mut tokens = self.tokens.lock().unwrap();
        tokens.retain(|_, entry| entry.expires > now);
        tokens.insert(
            token.clone(),
            TokenEntry {
                path: rel.to_string(),
                expires: now + Duration::from_secs(60),
            },
        );
        token
    }

    fn consume_token(&self, token: &str, rel: &str) -> bool {
        let mut tokens = self.tokens.lock().unwrap();
        match tokens.remove(token) {
            Some(entry) => entry.path == rel && entry.expires > Instant::now(),
            None => false,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Kind {
    Markdown,
    Text,
    Binary,
}

#[derive(Debug, Clone)]
struct FileInfo {
    kind: Kind,
    mime: String,
}

pub fn app(state: AppState) -> Router {
    Router::new()
        .route("/search", get(search))
        .route("/_assets/highlight.js", get(asset_highlight_js))
        .route("/_assets/highlight.css", get(asset_highlight_css))
        .route("/_assets/markdown.css", get(asset_markdown_css))
        .route("/_assets/mdview.js", get(asset_mdview_js))
        .fallback(handle)
        .with_state(state)
}

async fn asset_highlight_js() -> Response {
    asset_response(HIGHLIGHT_JS, "text/javascript; charset=utf-8")
}

async fn asset_highlight_css() -> Response {
    asset_response(HIGHLIGHT_CSS.as_bytes(), "text/css; charset=utf-8")
}

async fn asset_markdown_css() -> Response {
    asset_response(MARKDOWN_CSS.as_bytes(), "text/css; charset=utf-8")
}

async fn asset_mdview_js() -> Response {
    asset_response(MDVIEW_JS.as_bytes(), "text/javascript; charset=utf-8")
}

fn asset_response(bytes: &'static [u8], content_type: &'static str) -> Response {
    Response::builder()
        .status(StatusCode::OK)
        .header(header::CONTENT_TYPE, content_type)
        .header(header::CONTENT_LENGTH, bytes.len().to_string())
        .header(header::CACHE_CONTROL, "public, max-age=31536000, immutable")
        .header("X-Content-Type-Options", "nosniff")
        .body(Body::from(Bytes::from_static(bytes)))
        .unwrap()
}

pub async fn run(
    cli: Cli,
    root: PathBuf,
    max_preview: u64,
    trust: TrustState,
) -> anyhow::Result<()> {
    let state = AppState::new(root, cli.safe, cli.no_search, max_preview, trust);
    let app = app(state.clone());

    let mut bound = None;
    let mut last_err = None;
    for offset in 0..=cli.port_tries {
        let Some(port) = cli.port.checked_add(offset) else {
            break;
        };
        let addr = format_addr(&cli.host, port);
        match tokio::net::TcpListener::bind(&addr).await {
            Ok(listener) => {
                bound = Some((listener, port));
                break;
            }
            Err(err) => last_err = Some(err),
        }
    }
    let (listener, port) = bound.ok_or_else(|| {
        anyhow::anyhow!(
            "无法绑定 {}:{}（尝试 {} 次）: {}",
            cli.host,
            cli.port,
            cli.port_tries as u32 + 1,
            last_err.map(|e| e.to_string()).unwrap_or_default()
        )
    })?;

    print_banner(&cli, &state.root, max_preview, state.trust, port);
    axum::serve(listener, app)
        .with_graceful_shutdown(shutdown_signal())
        .await?;
    Ok(())
}

fn format_addr(host: &str, port: u16) -> String {
    if host.contains(':') && !host.starts_with('[') {
        format!("[{host}]:{port}")
    } else {
        format!("{host}:{port}")
    }
}

fn print_banner(cli: &Cli, root: &Path, max_preview: u64, trust: TrustState, port: u16) {
    println!(
        "mdview {}  单文件离线 Markdown 预览",
        env!("CARGO_PKG_VERSION")
    );
    println!("  root:        {}", root.display());
    println!("  listen:      http://{}:{}", cli.host, port);
    println!("  max preview: {}", format_size(max_preview));
    println!("  safe:        {}", on_off(cli.safe));
    println!("  search:      {}", on_off(!cli.no_search));
    println!("  trust:       {}", trust.describe());
    println!("  security:    {}", security_label(trust.security_level));
    if cli.host == "0.0.0.0" || cli.host == "::" {
        eprintln!(
            "warning: listening on {} exposes the root to the network; use --host 127.0.0.1 or --safe when appropriate",
            cli.host
        );
    }
}

fn on_off(value: bool) -> &'static str {
    if value { "on" } else { "off" }
}

fn security_label(level: u8) -> &'static str {
    match level {
        0 => "0 Strict",
        1 => "1 Allow HTTP",
        2 => "2 Disable (not recommended)",
        3 => "3 Allow localhost HTTP",
        _ => "unknown",
    }
}

async fn shutdown_signal() {
    let ctrl_c = async {
        let _ = tokio::signal::ctrl_c().await;
    };
    #[cfg(unix)]
    let terminate = async {
        if let Ok(mut signal) =
            tokio::signal::unix::signal(tokio::signal::unix::SignalKind::terminate())
        {
            signal.recv().await;
        }
    };
    #[cfg(not(unix))]
    let terminate = std::future::pending::<()>();
    tokio::select! {
        _ = ctrl_c => {},
        _ = terminate => {},
    }
}

async fn handle(
    State(state): State<AppState>,
    method: Method,
    uri: Uri,
    Query(query): Query<HashMap<String, String>>,
) -> Response {
    if method != Method::GET && method != Method::HEAD {
        return error_page(&state, StatusCode::METHOD_NOT_ALLOWED, "方法不允许", false);
    }
    let is_head = method == Method::HEAD;

    let raw_path = uri.path();
    let decoded = match percent_decode_str(raw_path).decode_utf8() {
        Ok(value) => value,
        Err(_) => return error_page(&state, StatusCode::BAD_REQUEST, "URL 编码无效", is_head),
    };
    let rel = decoded.trim_start_matches('/');
    if rel.contains('\0') || rel.contains('\\') {
        return error_page(&state, StatusCode::BAD_REQUEST, "路径包含非法字符", is_head);
    }

    let target = match resolve_path(&state.root, rel).await {
        Ok(path) => path,
        Err(status) => {
            let message = if status == StatusCode::FORBIDDEN {
                "路径越界"
            } else {
                "文件不存在"
            };
            return error_page(&state, status, message, is_head);
        }
    };

    let metadata = match tokio::fs::metadata(&target).await {
        Ok(meta) => meta,
        Err(_) => return error_page(&state, StatusCode::NOT_FOUND, "文件不存在", is_head),
    };

    if metadata.is_dir() {
        if !raw_path.ends_with('/') {
            let location = match uri.query() {
                Some(q) => format!("{raw_path}/?{q}"),
                None => format!("{raw_path}/"),
            };
            return redirect(&location);
        }
        return list_dir(&state, &target, rel, is_head).await;
    }

    if !metadata.is_file() {
        return error_page(&state, StatusCode::NOT_FOUND, "不是普通文件", is_head);
    }

    if state.safe && !allowed_in_safe_mode(&target) {
        return error_page(&state, StatusCode::NOT_FOUND, "文件不存在", is_head);
    }

    let size = metadata.len();
    let force_download = query.get("download").map(|v| v == "1").unwrap_or(false)
        || (state.max_preview > 0 && size > state.max_preview);
    let info = classify(&target).await;
    if force_download {
        return serve_file(&state, &target, &info, size, true, is_head).await;
    }

    match info.kind {
        Kind::Markdown => {
            if query.get("raw").map(|value| value == "1").unwrap_or(false) {
                return source_page(&state, &target, rel, &info, is_head).await;
            }
            if state.trust.trusted {
                return render_page(&state, &target, rel, is_head).await;
            }
            if let Some(token) = query.get("open")
                && state.consume_token(token, rel)
            {
                return render_page(&state, &target, rel, is_head).await;
            }
            interstitial_page(&state, rel, is_head)
        }
        Kind::Text => source_page(&state, &target, rel, &info, is_head).await,
        Kind::Binary => serve_file(&state, &target, &info, size, false, is_head).await,
    }
}

async fn resolve_path(root: &Path, rel: &str) -> Result<PathBuf, StatusCode> {
    if rel.is_empty() {
        return Ok(root.to_path_buf());
    }
    let mut path = root.to_path_buf();
    let mut depth = 0usize;
    for segment in rel.split('/') {
        match segment {
            "" | "." => {}
            ".." => {
                if depth == 0 {
                    return Err(StatusCode::FORBIDDEN);
                }
                path.pop();
                depth -= 1;
            }
            _ => {
                path.push(segment);
                depth += 1;
            }
        }
    }
    let canonical = tokio::fs::canonicalize(&path)
        .await
        .map_err(|_| StatusCode::NOT_FOUND)?;
    if !canonical.starts_with(root) {
        return Err(StatusCode::FORBIDDEN);
    }
    Ok(canonical)
}

fn redirect(location: &str) -> Response {
    Response::builder()
        .status(StatusCode::MOVED_PERMANENTLY)
        .header(header::LOCATION, location)
        .header(header::CONTENT_LENGTH, "0")
        .header("X-Content-Type-Options", "nosniff")
        .body(Body::empty())
        .unwrap()
}

async fn list_dir(state: &AppState, path: &Path, rel: &str, is_head: bool) -> Response {
    // Directory requests arrive with a trailing slash; normalize it so hrefs
    // do not become `/sub//c.md` and the parent of `/sub/` is `/`, not `/sub/`.
    let rel = rel.trim_end_matches('/');
    let mut dir = match tokio::fs::read_dir(path).await {
        Ok(dir) => dir,
        Err(_) => return error_page(state, StatusCode::FORBIDDEN, "无法读取目录", is_head),
    };
    let mut entries = Vec::new();
    loop {
        let entry = match dir.next_entry().await {
            Ok(Some(entry)) => entry,
            Ok(None) | Err(_) => break,
        };
        let name = entry.file_name().to_string_lossy().to_string();
        if name == ".DS_Store" {
            continue;
        }
        let metadata = match entry.metadata().await {
            Ok(meta) => meta,
            Err(_) => continue,
        };
        let is_dir = metadata.is_dir();
        if is_dir && SKIP_DIRS.contains(&name.as_str()) {
            continue;
        }
        if !is_dir && state.safe && !allowed_in_safe_mode(&entry.path()) {
            continue;
        }
        entries.push((is_dir, name, metadata));
    }
    entries.sort_by(|a, b| {
        b.0.cmp(&a.0)
            .then_with(|| a.1.to_lowercase().cmp(&b.1.to_lowercase()))
    });

    let mut rows = String::new();
    for (is_dir, name, metadata) in &entries {
        let href = join_href(rel, name, *is_dir);
        let label = if *is_dir {
            format!("📁 {}", escape_html(name))
        } else {
            escape_html(name)
        };
        let meta = if *is_dir {
            "目录".to_string()
        } else {
            format!(
                "{} · {}",
                format_size(metadata.len()),
                format_mtime(metadata.modified().unwrap_or(SystemTime::UNIX_EPOCH))
            )
        };
        let dl = if *is_dir {
            String::new()
        } else {
            format!("<a class=\"dl\" href=\"{href}?download=1\">⬇ 下载</a>")
        };
        rows.push_str(&format!(
            "<li><span class=\"nm\"><a href=\"{href}\">{label}</a></span><span class=\"meta\">{meta}</span>{dl}</li>"
        ));
    }
    if rows.is_empty() {
        rows.push_str("<li class=\"note\">这个目录是空的。</li>");
    }

    let title = if rel.is_empty() {
        "目录索引".to_string()
    } else {
        format!("目录 /{rel}")
    };
    let parent_link = if rel.is_empty() {
        String::new()
    } else {
        let parent = parent_rel(rel);
        let href = if parent.is_empty() {
            "/".to_string()
        } else {
            format!("/{}/", encode_path(parent))
        };
        format!("<p class=\"toolbar\"><a class=\"parent\" href=\"{href}\">⬆ 上级目录</a></p>")
    };
    let search_box = if state.no_search {
        String::new()
    } else {
        search_form("")
    };
    let body = format!(
        "{}<h1>{title}</h1>{parent_link}{search_box}<ul class=\"dirlist\">{rows}</ul>",
        breadcrumb(rel, true)
    );
    html_page(state, StatusCode::OK, &title, &body, is_head)
}

async fn search(
    State(state): State<AppState>,
    method: Method,
    Query(query): Query<HashMap<String, String>>,
) -> Response {
    let is_head = method == Method::HEAD;
    if method != Method::GET && method != Method::HEAD {
        return error_page(&state, StatusCode::METHOD_NOT_ALLOWED, "方法不允许", false);
    }
    if state.no_search {
        return error_page(&state, StatusCode::NOT_FOUND, "搜索已关闭", is_head);
    }
    let q = query
        .get("q")
        .cloned()
        .unwrap_or_default()
        .trim()
        .to_string();
    let body = if q.is_empty() {
        format!(
            "<h1>全文搜索</h1>{}<p class=\"note\">只搜索 .md 文件；大小写不敏感。</p>",
            search_form("")
        )
    } else {
        let root = state.root.clone();
        let needle = q.clone();
        let max_preview = state.max_preview;
        let results =
            tokio::task::spawn_blocking(move || search_files(&root, &needle, max_preview))
                .await
                .unwrap_or_default();
        render_search(&q, results)
    };
    html_page(&state, StatusCode::OK, &format!("搜索 {q}"), &body, is_head)
}

#[derive(Default)]
struct SearchResults {
    names: Vec<String>,
    bodies: Vec<(String, usize, String)>,
    truncated: bool,
}

fn search_form(q: &str) -> String {
    format!(
        "<form class=\"search\" action=\"/search\" method=\"get\">\
         <input type=\"search\" name=\"q\" value=\"{}\" placeholder=\"搜索 .md 全文\">\
         <button type=\"submit\">搜索</button></form>",
        escape_html(q)
    )
}

fn render_search(q: &str, results: SearchResults) -> String {
    let mut out = format!("<h1>搜索 “{}”</h1>{}", escape_html(q), search_form(q));
    if results.names.is_empty() && results.bodies.is_empty() {
        out.push_str("<p class=\"note\">没有命中。</p>");
        return out;
    }
    if !results.names.is_empty() {
        out.push_str("<div class=\"hits\"><h2>文件名命中</h2><ul>");
        for name in results.names {
            out.push_str(&format!(
                "<li><a href=\"/{}\">{}</a></li>",
                encode_path(&name),
                escape_html(&name)
            ));
        }
        out.push_str("</ul></div>");
    }
    if !results.bodies.is_empty() {
        out.push_str("<div class=\"hits\"><h2>正文命中</h2><ul>");
        for (name, line, text) in results.bodies {
            out.push_str(&format!(
                "<li><a href=\"/{}?raw=1#L{}\">{}:{}</a> <span class=\"line\">{}</span></li>",
                encode_path(&name),
                line,
                escape_html(&name),
                line,
                escape_html(&text)
            ));
        }
        out.push_str("</ul></div>");
    }
    if results.truncated {
        out.push_str("<p class=\"note\">结果过多，已截断。</p>");
    }
    out
}

fn search_files(root: &Path, needle: &str, max_preview: u64) -> SearchResults {
    let needle = needle.to_lowercase();
    let mut results = SearchResults::default();
    let walker = WalkDir::new(root)
        .follow_links(false)
        .into_iter()
        .filter_entry(|entry| !skipped_search_entry(entry));
    for entry in walker.flatten() {
        if !entry.file_type().is_file() {
            continue;
        }
        let is_md = entry
            .path()
            .extension()
            .and_then(OsStr::to_str)
            .map(|ext| ext.eq_ignore_ascii_case("md"))
            .unwrap_or(false);
        if !is_md {
            continue;
        }
        if max_preview > 0
            && entry
                .metadata()
                .map(|meta| meta.len() > max_preview)
                .unwrap_or(false)
        {
            continue;
        }
        let rel = entry
            .path()
            .strip_prefix(root)
            .unwrap_or(entry.path())
            .to_string_lossy()
            .replace('\\', "/");
        if rel.to_lowercase().contains(&needle) && results.names.len() < 100 {
            results.names.push(rel.clone());
        }
        let bytes = match std::fs::read(entry.path()) {
            Ok(bytes) => bytes,
            Err(_) => continue,
        };
        let text = String::from_utf8_lossy(&bytes);
        for (index, line) in text.lines().enumerate() {
            if line.to_lowercase().contains(&needle) {
                let snippet: String = line.trim().chars().take(240).collect();
                results.bodies.push((rel.clone(), index + 1, snippet));
                if results.bodies.len() >= 100 {
                    results.truncated = true;
                    return results;
                }
            }
        }
    }
    results
}

fn skipped_search_entry(entry: &walkdir::DirEntry) -> bool {
    if !entry.file_type().is_dir() || entry.depth() == 0 {
        return false;
    }
    let name = entry.file_name().to_string_lossy();
    name.starts_with('.') || SKIP_DIRS.contains(&name.as_ref())
}

async fn source_page(
    state: &AppState,
    path: &Path,
    rel: &str,
    info: &FileInfo,
    is_head: bool,
) -> Response {
    let bytes = match tokio::fs::read(path).await {
        Ok(bytes) => bytes,
        Err(_) => return error_page(state, StatusCode::NOT_FOUND, "文件不存在", is_head),
    };
    let text = String::from_utf8_lossy(&bytes);
    let mut gutter = String::new();
    let mut code = String::new();
    for (index, line) in text.split('\n').enumerate() {
        let number = index + 1;
        gutter.push_str(&format!(
            "<a id=\"L{number}\" href=\"#L{number}\">{number}</a>"
        ));
        code.push_str(&escape_html(line));
        code.push('\n');
    }
    let name = path.file_name().and_then(OsStr::to_str).unwrap_or("文件");
    let note = if info.kind == Kind::Markdown {
        "<p class=\"note\">源码视图</p>"
    } else {
        ""
    };
    let render_link = if info.kind == Kind::Markdown {
        format!("<a href=\"/{}\">看渲染结果</a>", encode_path(rel))
    } else {
        String::new()
    };
    let download = format!("{}?download=1", join_href(parent_rel(rel), name, false));
    let code_class = highlight_language(path)
        .map(|lang| format!(" class=\"language-{lang}\""))
        .unwrap_or_default();
    let body = format!(
        "{}<h1>{}</h1>{}<div class=\"toolbar\">{}<a href=\"{}\">⬇ 下载</a><span>{}</span></div>\
         <div class=\"source\"><pre class=\"gutter\">{}</pre>\
         <pre class=\"code\"><code{}>{}</code></pre></div>",
        breadcrumb(rel, false),
        escape_html(name),
        note,
        render_link,
        download,
        escape_html(&source_type_label(info)),
        gutter,
        code_class,
        code
    );
    html_page(
        state,
        StatusCode::OK,
        &format!("源码 {name}"),
        &body,
        is_head,
    )
}

async fn render_page(state: &AppState, path: &Path, rel: &str, is_head: bool) -> Response {
    let metadata = match tokio::fs::metadata(path).await {
        Ok(meta) => meta,
        Err(_) => return error_page(state, StatusCode::NOT_FOUND, "文件不存在", is_head),
    };
    let mtime = metadata.modified().unwrap_or(SystemTime::UNIX_EPOCH);
    let size = metadata.len();
    let cached = {
        let cache = state.cache.lock().unwrap();
        cache
            .get(path)
            .filter(|entry| entry.mtime == mtime && entry.size == size)
            .map(|entry| entry.html.clone())
    };
    let rendered = if let Some(html) = cached {
        html
    } else {
        let bytes = match tokio::fs::read(path).await {
            Ok(bytes) => bytes,
            Err(_) => return error_page(state, StatusCode::NOT_FOUND, "文件不存在", is_head),
        };
        let text = String::from_utf8_lossy(&bytes);
        let html = render_markdown(&text, rel);
        let mut cache = state.cache.lock().unwrap();
        if cache.len() > 128 {
            cache.clear();
        }
        cache.insert(
            path.to_path_buf(),
            CacheEntry {
                mtime,
                size,
                html: html.clone(),
            },
        );
        html
    };

    let name = path
        .file_name()
        .and_then(OsStr::to_str)
        .unwrap_or("Markdown");
    let encoded = encode_path(rel);
    let body = format!(
        "{}<h1>{}</h1><div class=\"toolbar\"><a href=\"/{encoded}?raw=1\">源码</a>\
         <a href=\"/{encoded}?download=1\">下载</a></div>\
         <article class=\"markdown-body\">{rendered}</article>",
        breadcrumb(rel, false),
        escape_html(name)
    );
    html_page(state, StatusCode::OK, name, &body, is_head)
}

fn interstitial_page(state: &AppState, rel: &str, is_head: bool) -> Response {
    let token = state.store_token(rel);
    let encoded = encode_path(rel);
    let cancel = match rel.rfind('/') {
        Some(index) => format!("/{}/", encode_path(&rel[..index])),
        None => "/".to_string(),
    };
    let body = format!(
        "<h1>未信任目录</h1>\
         <p>此 Markdown 文件位于未信任目录中。仍要打开吗？</p>\
         <p><a href=\"{cancel}\">取消</a> <a href=\"/{encoded}?open={token}\">仍要打开</a></p>"
    );
    html_page(state, StatusCode::OK, "未信任目录", &body, is_head)
}

fn source_type_label(info: &FileInfo) -> String {
    match info.kind {
        Kind::Markdown => "Markdown 源码".to_string(),
        Kind::Text => info.mime.clone(),
        Kind::Binary => info.mime.clone(),
    }
}

fn highlight_language(path: &Path) -> Option<&'static str> {
    let name = path.file_name().and_then(OsStr::to_str).unwrap_or("");
    match name {
        "Dockerfile" | "Containerfile" => return Some("dockerfile"),
        "Makefile" => return Some("makefile"),
        _ => {}
    }
    let ext = path
        .extension()
        .and_then(OsStr::to_str)
        .unwrap_or("")
        .to_ascii_lowercase();
    Some(match ext.as_str() {
        "rs" => "rust",
        "py" => "python",
        "js" | "mjs" | "cjs" | "jsx" => "javascript",
        "ts" | "tsx" => "typescript",
        "go" => "go",
        "java" => "java",
        "kt" | "kts" => "kotlin",
        "c" | "h" => "c",
        "cc" | "cpp" | "cxx" | "hpp" | "hh" => "cpp",
        "cs" => "csharp",
        "rb" => "ruby",
        "php" => "php",
        "pl" | "pm" => "perl",
        "lua" => "lua",
        "sql" => "sql",
        "sh" | "bash" | "zsh" | "fish" => "bash",
        "yaml" | "yml" => "yaml",
        "toml" | "ini" | "cfg" | "conf" | "properties" => "ini",
        "json" => "json",
        "xml" | "html" | "htm" => "xml",
        "css" => "css",
        "scss" => "scss",
        "sass" => "sass",
        "less" => "less",
        "md" | "markdown" | "mdx" => "markdown",
        "diff" | "patch" => "diff",
        "swift" => "swift",
        "dart" => "dart",
        "scala" => "scala",
        "r" => "r",
        "tex" => "latex",
        "proto" => "protobuf",
        "graphql" | "gql" => "graphql",
        _ => return None,
    })
}

async fn serve_file(
    state: &AppState,
    path: &Path,
    info: &FileInfo,
    size: u64,
    attachment: bool,
    is_head: bool,
) -> Response {
    let file = match tokio::fs::File::open(path).await {
        Ok(file) => file,
        Err(_) => return error_page(state, StatusCode::NOT_FOUND, "文件不存在", is_head),
    };
    let name = path
        .file_name()
        .and_then(OsStr::to_str)
        .unwrap_or("download");
    let mut builder = Response::builder()
        .status(StatusCode::OK)
        .header(header::CONTENT_TYPE, content_type(info))
        .header(header::CONTENT_LENGTH, size.to_string())
        .header(header::CACHE_CONTROL, "no-store")
        .header("X-Content-Type-Options", "nosniff");
    if attachment {
        builder = builder.header(header::CONTENT_DISPOSITION, content_disposition(name));
    }
    let body = if is_head {
        Body::empty()
    } else {
        Body::from_stream(ReaderStream::new(file))
    };
    builder.body(body).unwrap()
}

fn html_page(
    state: &AppState,
    status: StatusCode,
    title: &str,
    body: &str,
    is_head: bool,
) -> Response {
    let nonce = random_nonce();
    let version = crate::assets::asset_version();
    let html = format!(
        "<!doctype html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\">\
         <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\
         <title>{}</title><link rel=\"stylesheet\" href=\"/_assets/markdown.css?v={version}\">\
         <link rel=\"stylesheet\" href=\"/_assets/highlight.css?v={version}\">\
         <style>{SERVER_CSS}</style>\
         <script nonce=\"{nonce}\" src=\"/_assets/highlight.js?v={version}\" defer></script>\
         <script nonce=\"{nonce}\" src=\"/_assets/mdview.js?v={version}\" defer></script>\
         </head><body class=\"vscode-light\" data-totop=\"1\">{}</body></html>",
        escape_html(title),
        body
    );
    let length = html.len();
    let mut builder = Response::builder()
        .status(status)
        .header(header::CONTENT_TYPE, "text/html; charset=utf-8")
        .header(header::CONTENT_LENGTH, length.to_string())
        .header(header::CACHE_CONTROL, "no-store")
        .header("X-Content-Type-Options", "nosniff");
    if let Some(csp) = csp_header(state.trust.security_level, &nonce) {
        builder = builder.header("Content-Security-Policy", csp);
    }
    let body = if is_head {
        Body::empty()
    } else {
        Body::from(html)
    };
    builder.body(body).unwrap()
}

fn error_page(state: &AppState, status: StatusCode, message: &str, is_head: bool) -> Response {
    let title = match status {
        StatusCode::FORBIDDEN => "403 禁止访问",
        StatusCode::BAD_REQUEST => "400 请求无效",
        StatusCode::METHOD_NOT_ALLOWED => "405 方法不允许",
        _ => "404 未找到",
    };
    let body = format!(
        "<h1>{title}</h1><p class=\"note\">{}</p><p><a href=\"/\">返回目录</a></p>",
        escape_html(message)
    );
    html_page(state, status, title, &body, is_head)
}

async fn classify(path: &Path) -> FileInfo {
    let ext = path
        .extension()
        .and_then(OsStr::to_str)
        .unwrap_or("")
        .to_ascii_lowercase();
    let name = path.file_name().and_then(OsStr::to_str).unwrap_or("");

    if ext == "md" {
        return FileInfo {
            kind: Kind::Markdown,
            mime: "text/markdown; charset=utf-8".to_string(),
        };
    }
    if IMAGE_EXT.contains(&ext.as_str()) {
        return FileInfo {
            kind: Kind::Binary,
            mime: image_mime(&ext).to_string(),
        };
    }
    if ext == "pdf" {
        return FileInfo {
            kind: Kind::Binary,
            mime: "application/pdf".to_string(),
        };
    }
    if is_text_ext(&ext) || is_text_name(name) {
        let mime = match ext.as_str() {
            "json" => "application/json",
            "xml" => "application/xml",
            _ => "text/plain",
        };
        return FileInfo {
            kind: Kind::Text,
            mime: format!("{mime}; charset=utf-8"),
        };
    }

    if sniff_text(path).await == Some(true) {
        return FileInfo {
            kind: Kind::Text,
            mime: "text/plain; charset=utf-8".to_string(),
        };
    }
    FileInfo {
        kind: Kind::Binary,
        mime: guess_binary_mime(&ext),
    }
}

async fn sniff_text(path: &Path) -> Option<bool> {
    let mut file = tokio::fs::File::open(path).await.ok()?;
    let mut buffer = [0u8; 512];
    let read = file.read(&mut buffer).await.ok()?;
    Some(!buffer[..read].contains(&0))
}

fn allowed_in_safe_mode(path: &Path) -> bool {
    let ext = path
        .extension()
        .and_then(OsStr::to_str)
        .unwrap_or("")
        .to_ascii_lowercase();
    ext == "md" || IMAGE_EXT.contains(&ext.as_str())
}

fn is_text_ext(ext: &str) -> bool {
    TEXT_EXT.contains(&ext)
}

fn is_text_name(name: &str) -> bool {
    TEXT_NAMES.contains(&name)
}

fn image_mime(ext: &str) -> &'static str {
    match ext {
        "png" => "image/png",
        "jpg" | "jpeg" => "image/jpeg",
        "gif" => "image/gif",
        "svg" => "image/svg+xml",
        "webp" => "image/webp",
        "bmp" => "image/bmp",
        "ico" => "image/x-icon",
        "avif" => "image/avif",
        _ => "application/octet-stream",
    }
}

fn guess_binary_mime(ext: &str) -> String {
    if ext.is_empty() {
        return "application/octet-stream".to_string();
    }
    mime_guess::from_ext(ext)
        .first_raw()
        .unwrap_or("application/octet-stream")
        .to_string()
}

fn content_type(info: &FileInfo) -> String {
    if info.mime.starts_with("text/") {
        if info.mime.contains("charset=") {
            info.mime.clone()
        } else {
            format!("{}; charset=utf-8", info.mime)
        }
    } else {
        info.mime.clone()
    }
}

fn content_disposition(name: &str) -> String {
    let fallback: String = name
        .chars()
        .map(|ch| {
            if ch.is_ascii_alphanumeric() || matches!(ch, '-' | '_' | '.' | ' ') {
                ch
            } else {
                '_'
            }
        })
        .collect();
    let fallback = fallback.trim();
    let fallback = if fallback.is_empty() {
        "download"
    } else {
        fallback
    };
    let encoded = utf8_percent_encode(name, NON_ALPHANUMERIC);
    format!("attachment; filename=\"{fallback}\"; filename*=UTF-8''{encoded}")
}

fn join_href(rel_dir: &str, name: &str, is_dir: bool) -> String {
    let encoded_name = encode_segment(name);
    let mut href = if rel_dir.is_empty() {
        format!("/{encoded_name}")
    } else {
        format!("/{}/{}", encode_path(rel_dir), encoded_name)
    };
    if is_dir {
        href.push('/');
    }
    href
}

fn parent_rel(rel: &str) -> &str {
    match rel.rfind('/') {
        Some(index) => &rel[..index],
        None => "",
    }
}

fn breadcrumb(rel: &str, is_dir: bool) -> String {
    let mut html = String::from("<header><span class=\"crumb\"><a href=\"/\">根目录</a>");
    let mut accumulated = String::new();
    let parts: Vec<&str> = rel.split('/').filter(|part| !part.is_empty()).collect();
    for (index, part) in parts.iter().enumerate() {
        accumulated.push('/');
        accumulated.push_str(part);
        let is_last = index + 1 == parts.len();
        if is_last && !is_dir {
            html.push_str(" / ");
            html.push_str(&escape_html(part));
        } else {
            html.push_str(" / <a href=\"");
            html.push_str(&encode_path(&accumulated));
            html.push_str("/\">");
            html.push_str(&escape_html(part));
            html.push_str("</a>");
        }
    }
    html.push_str("</span></header>");
    html
}

fn encode_segment(value: &str) -> String {
    utf8_percent_encode(value, PATH_SEGMENT_SET).to_string()
}

fn encode_path(value: &str) -> String {
    value
        .split('/')
        .map(encode_segment)
        .collect::<Vec<_>>()
        .join("/")
}

fn escape_html(value: &str) -> String {
    let mut out = String::with_capacity(value.len());
    for ch in value.chars() {
        match ch {
            '&' => out.push_str("&amp;"),
            '<' => out.push_str("&lt;"),
            '>' => out.push_str("&gt;"),
            '"' => out.push_str("&quot;"),
            '\'' => out.push_str("&#39;"),
            _ => out.push(ch),
        }
    }
    out
}

fn csp_header(level: u8, nonce: &str) -> Option<String> {
    if level == 2 {
        return None;
    }
    let (img_extra, style_extra, font_extra) = match level {
        3 => (
            " http://localhost:* http://127.0.0.1:*",
            " http://localhost:* http://127.0.0.1:*",
            " http://localhost:* http://127.0.0.1:*",
        ),
        1 => (" http:", " http:", " http:"),
        _ => ("", "", ""),
    };
    Some(format!(
        "default-src 'none'; img-src 'self' https: data:{img_extra}; \
         media-src 'self' https: data:{img_extra}; script-src 'nonce-{nonce}'; \
         style-src 'self' 'unsafe-inline' https: data:{style_extra}; \
         font-src 'self' https: data:{font_extra}; frame-src 'none'; \
         form-action 'none'; base-uri 'none'; object-src 'none'"
    ))
}

fn random_nonce() -> String {
    let mut bytes = [0u8; 16];
    rand::rng().fill_bytes(&mut bytes);
    let mut out = String::with_capacity(32);
    for byte in bytes {
        out.push_str(&format!("{byte:02x}"));
    }
    out
}

fn format_mtime(time: SystemTime) -> String {
    let datetime = OffsetDateTime::from(time);
    format!(
        "{:04}-{:02}-{:02} {:02}:{:02}",
        datetime.year(),
        datetime.month() as u8,
        datetime.day(),
        datetime.hour(),
        datetime.minute()
    )
}

fn format_size(bytes: u64) -> String {
    if bytes == 0 {
        return "0 B".to_string();
    }
    const KIB: u64 = 1024;
    const MIB: u64 = KIB * 1024;
    const GIB: u64 = MIB * 1024;
    if bytes.is_multiple_of(GIB) {
        format!("{} GiB", bytes / GIB)
    } else if bytes.is_multiple_of(MIB) {
        format!("{} MiB", bytes / MIB)
    } else if bytes.is_multiple_of(KIB) {
        format!("{} KiB", bytes / KIB)
    } else {
        format!("{bytes} B")
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use axum::body::to_bytes;
    use axum::http::{HeaderMap, Request};
    use tower::ServiceExt;

    fn fixture() -> tempfile::TempDir {
        let dir = tempfile::tempdir().unwrap();
        let root = dir.path();
        std::fs::write(root.join("a.md"), "# hi\n\nsecond\n").unwrap();
        std::fs::write(root.join("b.txt"), "hello\nworld\n").unwrap();
        std::fs::write(root.join("a b.txt"), "space name\n").unwrap();
        std::fs::write(root.join("img.png"), b"\x89PNG\r\n\x1a\n").unwrap();
        std::fs::write(root.join("bin.dat"), b"abc\0def").unwrap();
        std::fs::write(root.join("code.rs"), "fn main() {}\n").unwrap();
        std::fs::create_dir(root.join("sub")).unwrap();
        std::fs::write(root.join("sub").join("c.md"), "# c\n").unwrap();
        dir
    }

    fn state(root: &Path, safe: bool, max_preview: u64, level: u8) -> AppState {
        AppState::new(
            std::fs::canonicalize(root).unwrap(),
            safe,
            false,
            max_preview,
            TrustState::new(true, level),
        )
    }

    async fn call(app: Router, method: Method, uri: &str) -> (StatusCode, HeaderMap, Vec<u8>) {
        let request = Request::builder()
            .method(method)
            .uri(uri)
            .body(Body::empty())
            .unwrap();
        let response = app.oneshot(request).await.unwrap();
        let status = response.status();
        let headers = response.headers().clone();
        let body = to_bytes(response.into_body(), 10_000_000)
            .await
            .unwrap()
            .to_vec();
        (status, headers, body)
    }

    #[tokio::test]
    async fn directory_listing_and_redirect() {
        let dir = fixture();
        let app = app(state(dir.path(), false, 0, 0));
        let (status, _, body) = call(app.clone(), Method::GET, "/").await;
        assert_eq!(status, StatusCode::OK);
        let html = String::from_utf8(body).unwrap();
        assert!(html.contains("a.md"));
        assert!(html.contains("sub/"));
        assert!(!html.contains("上级目录"));

        let (_, _, body) = call(app.clone(), Method::GET, "/sub/").await;
        let html = String::from_utf8(body).unwrap();
        assert!(html.contains("上级目录"), "{html}");
        assert!(html.contains("class=\"parent\" href=\"/\""), "{html}");
        assert!(html.contains("href=\"/sub/c.md\""), "{html}");
        assert!(!html.contains("//c.md"), "{html}");

        let (status, headers, _) = call(app, Method::GET, "/sub").await;
        assert_eq!(status, StatusCode::MOVED_PERMANENTLY);
        assert_eq!(headers.get(header::LOCATION).unwrap(), "/sub/");
    }

    #[tokio::test]
    async fn source_and_download() {
        let dir = fixture();
        let app = app(state(dir.path(), false, 0, 0));
        let (status, _, body) = call(app.clone(), Method::GET, "/b.txt").await;
        assert_eq!(status, StatusCode::OK);
        let html = String::from_utf8(body).unwrap();
        assert!(html.contains("id=\"L1\""));
        assert!(html.contains("hello"));
        assert!(html.contains("?download=1"));

        let (status, _, body) = call(app.clone(), Method::GET, "/a.md?raw=1").await;
        assert_eq!(status, StatusCode::OK);
        let html = String::from_utf8(body).unwrap();
        assert!(html.contains("看渲染结果"), "{html}");
        assert!(html.contains("href=\"/a.md\""), "{html}");
        assert!(html.contains("id=\"L1\""), "{html}");

        let (status, headers, body) = call(app.clone(), Method::GET, "/b.txt?download=1").await;
        assert_eq!(status, StatusCode::OK);
        assert!(
            headers
                .get(header::CONTENT_DISPOSITION)
                .unwrap()
                .to_str()
                .unwrap()
                .contains("attachment")
        );
        assert_eq!(body, b"hello\nworld\n");

        let (status, headers, _) = call(app, Method::GET, "/a%20b.txt").await;
        assert_eq!(status, StatusCode::OK);
        assert!(
            headers
                .get(header::CONTENT_TYPE)
                .unwrap()
                .to_str()
                .unwrap()
                .starts_with("text/html")
        );
    }

    #[tokio::test]
    async fn markdown_renders_when_trusted() {
        let dir = fixture();
        let app = app(state(dir.path(), false, 0, 0));
        let (status, _, body) = call(app.clone(), Method::GET, "/a.md").await;
        assert_eq!(status, StatusCode::OK);
        let html = String::from_utf8(body).unwrap();
        assert!(html.contains("<h1>hi</h1>"));
        assert!(html.contains("class=\"markdown-body\""));
        assert!(!html.contains("源码视图"));

        let (status, _, body) = call(app, Method::GET, "/a.md?raw=1").await;
        assert_eq!(status, StatusCode::OK);
        let html = String::from_utf8(body).unwrap();
        assert!(html.contains("源码视图"));
        assert!(html.contains("id=\"L1\""));
    }

    #[tokio::test]
    async fn untrusted_markdown_needs_one_time_token() {
        let dir = fixture();
        let app = app(AppState::new(
            std::fs::canonicalize(dir.path()).unwrap(),
            false,
            false,
            0,
            TrustState::new(false, 0),
        ));
        let (status, _, body) = call(app.clone(), Method::GET, "/a.md").await;
        assert_eq!(status, StatusCode::OK);
        let html = String::from_utf8(body).unwrap();
        assert!(html.contains("仍要打开"));
        let start = html.find("?open=").unwrap() + "?open=".len();
        let end = html[start..].find('"').unwrap() + start;
        let token = &html[start..end];

        let uri = format!("/a.md?open={token}");
        let (status, _, body) = call(app.clone(), Method::GET, &uri).await;
        assert_eq!(status, StatusCode::OK);
        let html = String::from_utf8(body).unwrap();
        assert!(html.contains("<h1>hi</h1>"));

        let (_, _, body) = call(app.clone(), Method::GET, &uri).await;
        let html = String::from_utf8(body).unwrap();
        assert!(html.contains("仍要打开"));

        let (status, _, body) = call(app, Method::GET, "/a.md?raw=1").await;
        assert_eq!(status, StatusCode::OK);
        let html = String::from_utf8(body).unwrap();
        assert!(html.contains("源码视图"));
    }

    #[tokio::test]
    async fn binary_type_and_head() {
        let dir = fixture();
        let app = app(state(dir.path(), false, 0, 0));
        let (status, headers, _) = call(app.clone(), Method::GET, "/bin.dat").await;
        assert_eq!(status, StatusCode::OK);
        assert_eq!(
            headers.get(header::CONTENT_TYPE).unwrap(),
            "application/octet-stream"
        );

        let (status, headers, body) = call(app, Method::HEAD, "/b.txt").await;
        assert_eq!(status, StatusCode::OK);
        assert!(headers.contains_key(header::CONTENT_LENGTH));
        assert!(body.is_empty());
    }

    #[tokio::test]
    async fn traversal_is_forbidden() {
        let dir = fixture();
        let app = app(state(dir.path(), false, 0, 0));
        let (status, _, _) = call(app, Method::GET, "/..%2F..%2Fetc%2Fpasswd").await;
        assert!(status == StatusCode::FORBIDDEN || status == StatusCode::NOT_FOUND);
    }

    #[tokio::test]
    async fn resolve_path_normalizes_and_stays_inside_root() {
        let dir = fixture();
        let root = std::fs::canonicalize(dir.path()).unwrap();
        assert_eq!(
            resolve_path(&root, "sub/../a.md").await.unwrap(),
            root.join("a.md")
        );
        assert_eq!(
            resolve_path(&root, "sub/./c.md").await.unwrap(),
            root.join("sub/c.md")
        );
        assert!(resolve_path(&root, "../etc/passwd").await.is_err());
    }

    #[tokio::test]
    async fn windows_style_paths_and_encoded_nul_are_rejected() {
        let dir = fixture();
        let app = app(state(dir.path(), false, 0, 0));

        let (status, _, _) = call(app.clone(), Method::GET, "/sub%5Cc.md").await;
        assert_eq!(status, StatusCode::BAD_REQUEST);

        let (status, _, _) = call(app.clone(), Method::GET, "/C:/Windows/win.ini").await;
        assert!(
            status == StatusCode::FORBIDDEN || status == StatusCode::NOT_FOUND,
            "{status}"
        );

        let (status, _, _) = call(app.clone(), Method::GET, "/a.md%00.png").await;
        assert_eq!(status, StatusCode::BAD_REQUEST);

        // Traversal encoded twice is not decoded twice by the router; it is just
        // a missing literal filename.
        let (status, _, _) = call(app, Method::GET, "/%252e%252e/%252e%252e/etc/passwd").await;
        assert_eq!(status, StatusCode::NOT_FOUND);
    }

    #[tokio::test]
    async fn unicode_filenames_are_addressable() {
        let dir = fixture();
        std::fs::write(dir.path().join("中文 文件.txt"), "中文内容\n").unwrap();
        let app = app(state(dir.path(), false, 0, 0));
        let (status, headers, body) = call(
            app,
            Method::GET,
            "/%E4%B8%AD%E6%96%87%20%E6%96%87%E4%BB%B6.txt",
        )
        .await;
        assert_eq!(status, StatusCode::OK);
        assert!(
            headers
                .get(header::CONTENT_TYPE)
                .unwrap()
                .to_str()
                .unwrap()
                .starts_with("text/html")
        );
        let html = String::from_utf8(body).unwrap();
        assert!(html.contains("中文内容"), "{html}");
    }

    #[tokio::test]
    async fn safe_mode_filters_files() {
        let dir = fixture();
        let app = app(state(dir.path(), true, 0, 0));
        let (status, _, _) = call(app.clone(), Method::GET, "/b.txt").await;
        assert_eq!(status, StatusCode::NOT_FOUND);

        let (status, _, _) = call(app.clone(), Method::GET, "/a.md").await;
        assert_eq!(status, StatusCode::OK);

        let (status, _, _) = call(app, Method::GET, "/img.png").await;
        assert_eq!(status, StatusCode::OK);
    }

    #[tokio::test]
    async fn max_preview_forces_download() {
        let dir = fixture();
        let app = app(state(dir.path(), false, 5, 0));
        let (status, headers, body) = call(app, Method::GET, "/b.txt").await;
        assert_eq!(status, StatusCode::OK);
        assert!(
            headers
                .get(header::CONTENT_DISPOSITION)
                .unwrap()
                .to_str()
                .unwrap()
                .contains("attachment")
        );
        assert_eq!(body, b"hello\nworld\n");
    }

    #[test]
    fn content_disposition_is_ascii_fallback_plus_rfc5987() {
        let value = content_disposition("report.pdf");
        assert!(
            value.starts_with("attachment; filename=\"report.pdf\""),
            "{value}"
        );
        assert!(value.contains("filename*=UTF-8''report%2Epdf"), "{value}");

        let value = content_disposition("报告 2024.txt");
        assert!(value.contains("filename=\"__ 2024.txt\""), "{value}");
        assert!(
            value.contains("filename*=UTF-8''%E6%8A%A5%E5%91%8A%202024%2Etxt"),
            "{value}"
        );
    }

    #[test]
    fn content_disposition_sanitizes_header_metacharacters() {
        // A filename is attacker-controlled on disk; CR/LF and quotes must not
        // escape into the header syntax.
        let value = content_disposition("a\"b\r\nc\\d;e.txt");
        assert!(!value.contains('\r'), "{value}");
        assert!(!value.contains('\n'), "{value}");
        assert_eq!(value.matches('"').count(), 2, "{value}");
        assert!(value.contains("filename=\"a_b__c_d_e.txt\""), "{value}");
        assert!(value.contains("%0D%0A"), "{value}");
    }

    #[test]
    fn content_disposition_never_has_an_empty_fallback() {
        for name in ["", "   "] {
            let value = content_disposition(name);
            assert!(value.contains("filename=\"download\""), "{name:?}: {value}");
        }
        for name in ["😀", "\"\""] {
            let value = content_disposition(name);
            let fallback = value
                .split("filename=\"")
                .nth(1)
                .and_then(|rest| rest.split('"').next())
                .unwrap();
            assert!(!fallback.trim().is_empty(), "{name:?}: {value}");
        }
    }

    #[tokio::test]
    async fn download_headers_are_hardened() {
        let dir = fixture();
        std::fs::write(dir.path().join("报告 2024.txt"), "hi\n").unwrap();
        let app = app(state(dir.path(), false, 0, 0));
        let (status, headers, _) = call(
            app,
            Method::GET,
            "/%E6%8A%A5%E5%91%8A%202024.txt?download=1",
        )
        .await;
        assert_eq!(status, StatusCode::OK);
        let disposition = headers
            .get(header::CONTENT_DISPOSITION)
            .unwrap()
            .to_str()
            .unwrap();
        assert!(disposition.contains("attachment"), "{disposition}");
        assert!(disposition.contains("filename*=UTF-8''"), "{disposition}");
        assert_eq!(headers.get("X-Content-Type-Options").unwrap(), "nosniff");
        assert_eq!(headers.get(header::CACHE_CONTROL).unwrap(), "no-store");
    }

    #[cfg(unix)]
    #[tokio::test]
    async fn symlink_escape_is_forbidden() {
        use std::os::unix::fs::symlink;
        let dir = fixture();
        let outside = tempfile::tempdir().unwrap();
        std::fs::write(outside.path().join("secret.txt"), "secret").unwrap();
        symlink(
            outside.path().join("secret.txt"),
            dir.path().join("escape.txt"),
        )
        .unwrap();
        symlink(outside.path(), dir.path().join("escape-dir")).unwrap();

        let app = app(state(dir.path(), false, 0, 0));
        let (status, _, body) = call(app.clone(), Method::GET, "/escape.txt").await;
        assert_eq!(status, StatusCode::FORBIDDEN);
        assert!(!String::from_utf8_lossy(&body).contains("secret"));

        let (status, _, _) = call(app, Method::GET, "/escape-dir/secret.txt").await;
        assert_eq!(status, StatusCode::FORBIDDEN);
    }

    #[cfg(unix)]
    #[tokio::test]
    async fn symlink_inside_root_is_allowed() {
        use std::os::unix::fs::symlink;
        let dir = fixture();
        symlink(dir.path().join("a.md"), dir.path().join("alias.md")).unwrap();
        let app = app(state(dir.path(), false, 0, 0));
        let (status, _, body) = call(app, Method::GET, "/alias.md").await;
        assert_eq!(status, StatusCode::OK);
        let html = String::from_utf8(body).unwrap();
        assert!(html.contains("<h1>hi</h1>"), "{html}");
    }

    #[tokio::test]
    async fn csp_levels() {
        let dir = fixture();
        let strict = app(state(dir.path(), false, 0, 0));
        let (_, headers, _) = call(strict.clone(), Method::GET, "/").await;
        let csp = headers
            .get("Content-Security-Policy")
            .unwrap()
            .to_str()
            .unwrap();
        assert!(csp.contains("script-src 'nonce-"));
        assert!(!csp.contains("'self' 'nonce"));

        let (_, headers, _) = call(strict, Method::GET, "/").await;
        let csp2 = headers
            .get("Content-Security-Policy")
            .unwrap()
            .to_str()
            .unwrap();
        assert_ne!(nonce_of(csp), nonce_of(csp2));

        let allow_http = app(state(dir.path(), false, 0, 1));
        let (_, headers, _) = call(allow_http, Method::GET, "/").await;
        let csp = headers
            .get("Content-Security-Policy")
            .unwrap()
            .to_str()
            .unwrap();
        assert!(csp.contains("http:"));

        let allow_local = app(state(dir.path(), false, 0, 3));
        let (_, headers, _) = call(allow_local, Method::GET, "/").await;
        let csp = headers
            .get("Content-Security-Policy")
            .unwrap()
            .to_str()
            .unwrap();
        assert!(csp.contains("http://localhost:*"));

        let disabled = app(state(dir.path(), false, 0, 2));
        let (_, headers, _) = call(disabled, Method::GET, "/").await;
        assert!(!headers.contains_key("Content-Security-Policy"));
    }

    fn nonce_of(csp: &str) -> &str {
        csp.split("script-src 'nonce-")
            .nth(1)
            .and_then(|rest| rest.split('\'').next())
            .unwrap()
    }

    #[tokio::test]
    async fn search_finds_markdown_only() {
        let dir = fixture();
        let app = app(state(dir.path(), false, 0, 0));
        let (status, _, body) = call(app.clone(), Method::GET, "/search?q=second").await;
        assert_eq!(status, StatusCode::OK);
        let html = String::from_utf8(body).unwrap();
        assert!(html.contains("a.md"));
        assert!(html.contains("#L3"));

        let (_, _, body) = call(app.clone(), Method::GET, "/search?q=hello").await;
        let html = String::from_utf8(body).unwrap();
        assert!(html.contains("没有命中"));

        let (status, _, _) = call(app, Method::GET, "/search").await;
        assert_eq!(status, StatusCode::OK);
    }

    #[tokio::test]
    async fn no_search_disables_route_and_box() {
        let dir = fixture();
        let app = app(AppState::new(
            std::fs::canonicalize(dir.path()).unwrap(),
            false,
            true,
            0,
            TrustState::new(true, 0),
        ));
        let (status, _, _) = call(app.clone(), Method::GET, "/search?q=second").await;
        assert_eq!(status, StatusCode::NOT_FOUND);
        let (_, _, body) = call(app, Method::GET, "/").await;
        let html = String::from_utf8(body).unwrap();
        assert!(!html.contains("class=\"search\""));
    }

    #[tokio::test]
    async fn render_cache_invalidates_on_mtime_and_size() {
        let dir = fixture();
        let app = app(state(dir.path(), false, 0, 0));
        let (_, _, body) = call(app.clone(), Method::GET, "/a.md").await;
        let html = String::from_utf8(body).unwrap();
        assert!(html.contains("<h1>hi</h1>"));

        std::thread::sleep(Duration::from_millis(20));
        std::fs::write(dir.path().join("a.md"), "# changed\n").unwrap();

        let (_, _, body) = call(app, Method::GET, "/a.md").await;
        let html = String::from_utf8(body).unwrap();
        assert!(html.contains("<h1>changed</h1>"));
        assert!(!html.contains("<h1>hi</h1>"));
    }

    #[tokio::test]
    async fn assets_and_source_highlight_class() {
        let dir = fixture();
        let app = app(state(dir.path(), false, 0, 0));
        let (status, headers, body) = call(app.clone(), Method::GET, "/_assets/highlight.js").await;
        assert_eq!(status, StatusCode::OK);
        assert!(
            headers
                .get(header::CONTENT_TYPE)
                .unwrap()
                .to_str()
                .unwrap()
                .starts_with("text/javascript")
        );
        assert!(body.len() > 1000);

        let (status, _, _) = call(app.clone(), Method::GET, "/_assets/highlight.css").await;
        assert_eq!(status, StatusCode::OK);
        let (status, _, _) = call(app.clone(), Method::GET, "/_assets/markdown.css").await;
        assert_eq!(status, StatusCode::OK);
        let (status, _, _) = call(app.clone(), Method::GET, "/_assets/mdview.js").await;
        assert_eq!(status, StatusCode::OK);

        let (_, _, body) = call(app.clone(), Method::GET, "/a.md").await;
        let html = String::from_utf8(body).unwrap();
        assert!(html.contains("/_assets/markdown.css"));
        assert!(html.contains("/_assets/highlight.js"));
        assert!(html.contains("/_assets/mdview.js"));
        assert!(html.contains(&format!("?v={}", crate::assets::asset_version())));
        assert!(html.contains("nonce="));

        let (_, _, body) = call(app, Method::GET, "/code.rs").await;
        let html = String::from_utf8(body).unwrap();
        assert!(html.contains("class=\"language-rust\""));
    }
}
