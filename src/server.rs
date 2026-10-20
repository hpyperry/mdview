use std::collections::HashMap;
use std::ffi::OsStr;
use std::fmt::Write as _;
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant, SystemTime};

use axum::Json;
use axum::Router;
use axum::body::{Body, Bytes};
use axum::extract::{Query, State};
use axum::http::{Method, StatusCode, Uri, header};
use axum::response::{IntoResponse, Response};
use axum::routing::get;
use percent_encoding::{
    AsciiSet, CONTROLS, NON_ALPHANUMERIC, percent_decode_str, utf8_percent_encode,
};
use rand::RngCore;
use serde::Serialize;
use time::OffsetDateTime;
use tokio::io::AsyncReadExt;
use tokio_util::io::ReaderStream;
use walkdir::WalkDir;

use crate::assets::{APP_CSS, APP_JS, HIGHLIGHT_CSS, HIGHLIGHT_JS, MARKDOWN_CSS};
use crate::cli::Cli;
use crate::render::render_markdown_with_sourcepos;
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

/// Source pages above this size are still rendered in full, but split into
/// fixed-height chunks so `content-visibility: auto` can skip offscreen layout
/// and paint. Line anchors and syntax highlighting are added lazily per chunk.
const CHUNKED_SOURCE_THRESHOLD: u64 = 256 * 1024;
const SOURCE_CHUNK_LINES: usize = 500;

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
        .route("/_nav", get(nav))
        .route("/_assets/highlight.js", get(asset_highlight_js))
        .route("/_assets/highlight.css", get(asset_highlight_css))
        .route("/_assets/markdown.css", get(asset_markdown_css))
        .route("/_assets/app.css", get(asset_app_css))
        .route("/_assets/app.js", get(asset_app_js))
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

async fn asset_app_css() -> Response {
    asset_response(APP_CSS.as_bytes(), "text/css; charset=utf-8")
}

async fn asset_app_js() -> Response {
    asset_response(APP_JS, "text/javascript; charset=utf-8")
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
    println!(
        "  max preview: {}",
        if max_preview == 0 {
            "不限制".to_string()
        } else {
            format_size(max_preview)
        }
    );
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
        return error_page(
            &state,
            StatusCode::METHOD_NOT_ALLOWED,
            "这个操作暂时不支持",
            false,
        )
        .await;
    }
    let is_head = method == Method::HEAD;

    let raw_path = uri.path();
    let decoded = match percent_decode_str(raw_path).decode_utf8() {
        Ok(value) => value,
        Err(_) => {
            return error_page(&state, StatusCode::BAD_REQUEST, "地址格式不正确", is_head).await;
        }
    };
    let rel = decoded.trim_start_matches('/');
    if rel.contains('\0') || rel.contains('\\') {
        return error_page(&state, StatusCode::BAD_REQUEST, "地址格式不正确", is_head).await;
    }

    let target = match resolve_path(&state.root, rel).await {
        Ok(path) => path,
        Err(status) => {
            let message = if status == StatusCode::FORBIDDEN {
                "无法打开这个地址"
            } else {
                "这个文件不存在，或已被移动"
            };
            return error_page(&state, status, message, is_head).await;
        }
    };

    let metadata = match tokio::fs::metadata(&target).await {
        Ok(meta) => meta,
        Err(_) => {
            return error_page(
                &state,
                StatusCode::NOT_FOUND,
                "这个文件不存在，或已被移动",
                is_head,
            )
            .await;
        }
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
        return error_page(&state, StatusCode::NOT_FOUND, "这个文件无法预览", is_head).await;
    }

    if state.safe && !allowed_in_safe_mode(&target) {
        return error_page(
            &state,
            StatusCode::NOT_FOUND,
            "这个文件不存在，或已被移动",
            is_head,
        )
        .await;
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
                return source_page(
                    &state,
                    &target,
                    rel,
                    &info,
                    metadata.modified().unwrap_or(SystemTime::UNIX_EPOCH),
                    is_head,
                )
                .await;
            }
            if state.trust.trusted {
                return render_page(&state, &target, rel, is_head).await;
            }
            if let Some(token) = query.get("open")
                && state.consume_token(token, rel)
            {
                return render_page(&state, &target, rel, is_head).await;
            }
            interstitial_page(&state, rel, is_head).await
        }
        Kind::Text => {
            source_page(
                &state,
                &target,
                rel,
                &info,
                metadata.modified().unwrap_or(SystemTime::UNIX_EPOCH),
                is_head,
            )
            .await
        }
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
        Err(_) => {
            return error_page(
                state,
                StatusCode::FORBIDDEN,
                "目录加载失败，请稍后重试",
                is_head,
            )
            .await;
        }
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
        if is_dir && (name.starts_with('.') || SKIP_DIRS.contains(&name.as_str())) {
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

    let mut dir_rows = String::new();
    let mut file_rows = String::new();
    for (is_dir, name, metadata) in &entries {
        let href = join_href(rel, name, *is_dir);
        if *is_dir {
            dir_rows.push_str(&format!(
                "<div class=\"dir-row\"><span class=\"file-icon folder\">{icon}</span>\
                 <a class=\"nm\" href=\"{href}\">{name}</a>\
                 <span class=\"meta\">目录</span></div>",
                icon = icon("folder"),
                name = escape_html(name)
            ));
        } else {
            let meta = format!(
                "{} · {}",
                format_size(metadata.len()),
                format_mtime(metadata.modified().unwrap_or(SystemTime::UNIX_EPOCH))
            );
            file_rows.push_str(&format!(
                "<div class=\"dir-row\"><span class=\"file-icon\">{icon}</span>\
                 <a class=\"nm\" href=\"{href}\">{name}</a>\
                 <span class=\"meta\">{meta}</span>\
                 <a class=\"dl\" href=\"{href}?download=1\" title=\"下载 {name}\">\
                 {download}<span>下载</span></a></div>",
                icon = icon("file"),
                name = escape_html(name),
                download = icon("download")
            ));
        }
    }
    let mut list = String::new();
    list.push_str(&dir_rows);
    list.push_str(&file_rows);
    let sections = if list.is_empty() {
        "<div class=\"empty-state\">这个目录是空的。</div>".to_string()
    } else {
        format!("<div class=\"dir-list\">{list}</div>")
    };
    let dir_name = if rel.is_empty() {
        root_name(state)
    } else {
        rel.rsplit('/').next().unwrap_or(rel).to_string()
    };
    let crumbs = page_crumbs(state, rel, PageKind::Dir);
    let body = format!(
        "<div class=\"content-card\"><div class=\"dir-head\"><div class=\"head-inner\">\
         <nav class=\"crumbs\" aria-label=\"面包屑\">{crumbs}</nav>\
         <h1>{}</h1><p>{} 个项目</p></div></div>{}</div>",
        escape_html(&dir_name),
        entries.len(),
        sections
    );
    html_page(
        state,
        StatusCode::OK,
        Page {
            title: dir_name,
            rel: rel.to_string(),
            query: String::new(),
            kind: PageKind::Dir,
            body,
        },
        is_head,
    )
    .await
}

async fn search(
    State(state): State<AppState>,
    method: Method,
    Query(query): Query<HashMap<String, String>>,
) -> Response {
    let is_head = method == Method::HEAD;
    if method != Method::GET && method != Method::HEAD {
        return error_page(
            &state,
            StatusCode::METHOD_NOT_ALLOWED,
            "这个操作暂时不支持",
            false,
        )
        .await;
    }
    if state.no_search {
        return error_page(&state, StatusCode::NOT_FOUND, "搜索功能未开启", is_head).await;
    }
    let q = query
        .get("q")
        .cloned()
        .unwrap_or_default()
        .trim()
        .to_string();
    let results = if q.is_empty() {
        SearchResults::default()
    } else {
        let root = state.root.clone();
        let needle = q.clone();
        let max_preview = state.max_preview;
        tokio::task::spawn_blocking(move || search_files(&root, &needle, max_preview))
            .await
            .unwrap_or_default()
    };
    let crumbs = page_crumbs(&state, "", PageKind::Search);
    let body = render_search(&q, &results, &crumbs);
    html_page(
        &state,
        StatusCode::OK,
        Page {
            title: if q.is_empty() {
                "搜索".to_string()
            } else {
                format!("搜索 {q}")
            },
            rel: String::new(),
            query: q,
            kind: PageKind::Search,
            body,
        },
        is_head,
    )
    .await
}

#[derive(Serialize)]
struct NavPayload {
    root: String,
    tree: Vec<NavNode>,
}

#[derive(Serialize)]
struct NavNode {
    name: String,
    path: String,
    #[serde(rename = "type")]
    kind: &'static str,
    #[serde(skip_serializing_if = "Option::is_none")]
    href: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    file_kind: Option<&'static str>,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    children: Vec<NavNode>,
}

fn nav_file_kind(path: &Path) -> &'static str {
    let name = path.file_name().and_then(OsStr::to_str).unwrap_or("");
    let ext = path
        .extension()
        .and_then(OsStr::to_str)
        .unwrap_or("")
        .to_ascii_lowercase();
    if ext == "md" || ext == "markdown" || ext == "mdx" {
        "doc"
    } else if IMAGE_EXT.contains(&ext.as_str()) {
        "image"
    } else if ext == "pdf" {
        "pdf"
    } else if is_text_ext(&ext) || is_text_name(name) {
        "text"
    } else {
        "binary"
    }
}

fn nav_children(root: &Path, dir: &Path, safe: bool) -> std::io::Result<Vec<NavNode>> {
    let mut entries = Vec::new();
    for entry in std::fs::read_dir(dir)? {
        let entry = entry?;
        let name = entry.file_name().to_string_lossy().to_string();
        if name == ".DS_Store" {
            continue;
        }
        let file_type = entry.file_type()?;
        if file_type.is_dir() && (name.starts_with('.') || SKIP_DIRS.contains(&name.as_str())) {
            continue;
        }
        if file_type.is_dir() || file_type.is_file() {
            entries.push((file_type.is_dir(), name, entry.path()));
        }
    }
    entries.sort_by(|a, b| {
        b.0.cmp(&a.0)
            .then_with(|| a.1.to_lowercase().cmp(&b.1.to_lowercase()))
    });

    let mut nodes = Vec::new();
    for (is_dir, name, path) in entries {
        let rel = path
            .strip_prefix(root)
            .unwrap_or(&path)
            .to_string_lossy()
            .replace('\\', "/");
        if is_dir {
            let children = nav_children(root, &path, safe)?;
            nodes.push(NavNode {
                name,
                path: rel,
                kind: "dir",
                href: None,
                file_kind: None,
                children,
            });
        } else {
            if safe && !allowed_in_safe_mode(&path) {
                continue;
            }
            nodes.push(NavNode {
                name,
                href: Some(format!("/{}", encode_path(&rel))),
                path: rel,
                kind: "file",
                file_kind: Some(nav_file_kind(&path)),
                children: Vec::new(),
            });
        }
    }
    Ok(nodes)
}

fn nav_payload(root: &Path, safe: bool) -> std::io::Result<NavPayload> {
    let root_name = root
        .file_name()
        .and_then(OsStr::to_str)
        .filter(|name| !name.is_empty())
        .unwrap_or("docs")
        .to_string();
    Ok(NavPayload {
        root: root_name,
        tree: nav_children(root, root, safe)?,
    })
}

async fn nav(State(state): State<AppState>) -> Response {
    let root = state.root.clone();
    let safe = state.safe;
    match tokio::task::spawn_blocking(move || nav_payload(&root, safe)).await {
        Ok(Ok(payload)) => ([(header::CACHE_CONTROL, "no-store")], Json(payload)).into_response(),
        _ => (StatusCode::INTERNAL_SERVER_ERROR, "导航加载失败").into_response(),
    }
}

#[derive(Default)]
struct SearchResults {
    groups: Vec<SearchGroup>,
    files: usize,
    hits: usize,
    truncated: bool,
}

struct SearchGroup {
    path: String,
    kind: SearchKind,
    name_hit: bool,
    hits: Vec<SearchHit>,
}

struct SearchHit {
    line: usize,
    text: String,
}

#[derive(Clone, Copy, PartialEq, Eq)]
enum SearchKind {
    Doc,
    Text,
    File,
}

impl SearchKind {
    fn label(self) -> &'static str {
        match self {
            SearchKind::Doc => "文档",
            SearchKind::Text => "源码",
            SearchKind::File => "文件",
        }
    }

    fn icon(self) -> &'static str {
        match self {
            SearchKind::Doc => icon("file"),
            SearchKind::Text => icon("code"),
            SearchKind::File => icon("file"),
        }
    }

    fn rank(self) -> u8 {
        match self {
            SearchKind::Doc => 0,
            SearchKind::Text => 1,
            SearchKind::File => 2,
        }
    }
}

fn search_page_form(q: &str) -> String {
    format!(
        "<form class=\"search-page-form\" action=\"/search\" method=\"get\" role=\"search\">\
         <input type=\"search\" name=\"q\" value=\"{}\" placeholder=\"搜索文件名和内容\" \
         aria-label=\"搜索文件名和内容\" autocomplete=\"off\">\
         <button class=\"action primary\" type=\"submit\">{}<span>搜索</span></button></form>",
        escape_html(q),
        icon("search")
    )
}

fn render_search(q: &str, results: &SearchResults, crumbs: &str) -> String {
    if q.is_empty() {
        return format!(
            "<div class=\"content-card\"><div class=\"search-head\"><div class=\"head-inner search-head-inner\">\
             <div class=\"grow\"><nav class=\"crumbs\" aria-label=\"面包屑\">{crumbs}</nav>\
             <h1>搜索</h1><p>搜索文件名和内容，支持 Markdown 与文本文件。</p></div>{form}\
             </div></div><div class=\"page-body\"><div class=\"empty-state\">{}<div>在上方输入关键词开始搜索。</div></div></div></div>",
            icon("search"),
            crumbs = crumbs,
            form = search_page_form("")
        );
    }
    let mut body = format!(
        "<div class=\"content-card\"><div class=\"search-head\"><div class=\"head-inner search-head-inner\">\
         <div class=\"grow\"><nav class=\"crumbs\" aria-label=\"面包屑\">{crumbs}</nav>\
         <h1>搜索 “{}”</h1><p>{} 个文件 · {} 条结果</p></div>{form}\
         </div></div><div class=\"page-body\">",
        escape_html(q),
        results.files,
        results.hits,
        crumbs = crumbs,
        form = search_page_form(q)
    );
    if results.groups.is_empty() {
        body.push_str(&format!(
            "<div class=\"empty-state\">{}<div>没有找到相关内容。试试更短的关键词。</div></div>",
            icon("search")
        ));
    } else {
        for group in &results.groups {
            let count = group.hits.len() + usize::from(group.name_hit);
            body.push_str(&format!(
                "<section class=\"result-group\"><a class=\"result-head\" href=\"/{}\" aria-label=\"打开 {}\">\
                 <span class=\"path\">{}<span>{}</span></span>\
                 <span class=\"badge badge-{}\">{}</span>\
                 <span class=\"badge\">{} 条结果</span></a>",
                encode_path(&group.path),
                escape_html(&group.path),
                group.kind.icon(),
                escape_html(&group.path),
                match group.kind {
                    SearchKind::Doc => "doc",
                    SearchKind::Text => "text",
                    SearchKind::File => "file",
                },
                group.kind.label(),
                count
            ));
            for hit in &group.hits {
                let href = match group.kind {
                    SearchKind::Doc | SearchKind::Text => {
                        format!("/{}#L{}", encode_path(&group.path), hit.line)
                    }
                    SearchKind::File => format!("/{}", encode_path(&group.path)),
                };
                body.push_str(&format!(
                    "<a class=\"hit\" href=\"{href}\" aria-label=\"打开 {} 第 {} 行\">\
                     <div class=\"hit-top\"><span>第 {} 行</span></div>\
                     <p class=\"hit-snippet\">{}</p></a>",
                    escape_html(&group.path),
                    hit.line,
                    hit.line,
                    escape_html(&hit.text)
                ));
            }
            body.push_str("</section>");
        }
    }
    if results.truncated {
        body.push_str(
            "<p class=\"search-note\">结果较多，仅显示部分结果。请使用更具体的关键词。</p>",
        );
    }
    body.push_str("</div></div>");
    body
}

fn search_files(root: &Path, needle: &str, max_preview: u64) -> SearchResults {
    let needle = needle.to_lowercase();
    let mut groups: Vec<SearchGroup> = Vec::new();
    let mut total_hits = 0usize;
    let mut truncated = false;
    let walker = WalkDir::new(root)
        .follow_links(false)
        .into_iter()
        .filter_entry(|entry| !skipped_search_entry(entry));
    for entry in walker.flatten() {
        if !entry.file_type().is_file() {
            continue;
        }
        let rel = entry
            .path()
            .strip_prefix(root)
            .unwrap_or(entry.path())
            .to_string_lossy()
            .replace('\\', "/");
        let ext = entry
            .path()
            .extension()
            .and_then(OsStr::to_str)
            .unwrap_or("")
            .to_ascii_lowercase();
        let kind = if ext == "md" {
            SearchKind::Doc
        } else if is_search_text(entry.path()) {
            SearchKind::Text
        } else {
            SearchKind::File
        };
        let name_hit = rel.to_lowercase().contains(&needle);
        let mut hits = Vec::new();
        if kind != SearchKind::File
            && (max_preview == 0
                || entry
                    .metadata()
                    .map(|meta| meta.len() <= max_preview)
                    .unwrap_or(false))
        {
            let Ok(bytes) = std::fs::read(entry.path()) else {
                continue;
            };
            let text = String::from_utf8_lossy(&bytes);
            for (index, line) in text.lines().enumerate() {
                if line.to_lowercase().contains(&needle) {
                    let snippet: String = line.trim().chars().take(240).collect();
                    hits.push(SearchHit {
                        line: index + 1,
                        text: snippet,
                    });
                    total_hits += 1;
                    if hits.len() >= 5 || total_hits >= 200 {
                        truncated = true;
                        break;
                    }
                }
            }
        }
        if name_hit || !hits.is_empty() {
            if groups.len() >= 60 {
                truncated = true;
                break;
            }
            groups.push(SearchGroup {
                path: rel,
                kind,
                name_hit,
                hits,
            });
            if total_hits >= 200 {
                truncated = true;
                break;
            }
        }
    }
    groups.sort_by(|a, b| {
        a.kind
            .rank()
            .cmp(&b.kind.rank())
            .then_with(|| a.path.to_lowercase().cmp(&b.path.to_lowercase()))
    });
    let files = groups.len();
    let name_hits = groups.iter().filter(|group| group.name_hit).count();
    SearchResults {
        groups,
        files,
        hits: total_hits + name_hits,
        truncated,
    }
}

fn is_search_text(path: &Path) -> bool {
    let name = path.file_name().and_then(OsStr::to_str).unwrap_or("");
    let ext = path
        .extension()
        .and_then(OsStr::to_str)
        .unwrap_or("")
        .to_ascii_lowercase();
    ext == "md"
        || is_text_ext(&ext)
        || is_text_name(name)
        || (ext.is_empty() && sniff_text_sync(path).unwrap_or(false))
}

fn sniff_text_sync(path: &Path) -> Option<bool> {
    use std::io::Read;
    let mut file = std::fs::File::open(path).ok()?;
    let mut buffer = [0u8; 512];
    let read = file.read(&mut buffer).ok()?;
    Some(!buffer[..read].contains(&0))
}

fn skipped_search_entry(entry: &walkdir::DirEntry) -> bool {
    if !entry.file_type().is_dir() || entry.depth() == 0 {
        return false;
    }
    let name = entry.file_name().to_string_lossy();
    name.starts_with('.') || SKIP_DIRS.contains(&name.as_ref())
}

fn source_lines(text: &str, limit: usize) -> (String, String, usize) {
    let mut gutter = String::new();
    let mut code = String::new();
    let mut shown = 0usize;
    for (index, line) in text.split('\n').enumerate() {
        if index >= limit {
            break;
        }
        let number = index + 1;
        let _ = write!(
            gutter,
            "<a id=\"L{number}\" href=\"#L{number}\">{number}</a>"
        );
        escape_html_into(&mut code, line);
        code.push('\n');
        shown = number;
    }
    (gutter, code, shown)
}

/// Render the whole source as fixed-height chunks. The server never truncates:
/// offscreen chunks are skipped by the browser through `content-visibility`.
fn source_chunked(text: &str, chunk_lines: usize, code_class: &str) -> (String, usize) {
    let mut out = String::with_capacity(text.len() + text.len() / 8 + 4096);
    let mut lines = text.split('\n');
    let mut number = 0usize;
    loop {
        let start = number + 1;
        let mut gutter = String::with_capacity(chunk_lines * 8);
        let mut code = String::with_capacity(chunk_lines * 48);
        let mut rows = 0usize;
        while rows < chunk_lines {
            let Some(line) = lines.next() else {
                break;
            };
            number += 1;
            rows += 1;
            if rows > 1 {
                gutter.push('\n');
            }
            let _ = write!(gutter, "{number}");
            escape_html_into(&mut code, line);
            code.push('\n');
        }
        if rows == 0 {
            break;
        }
        let _ = write!(
            out,
            "<section class=\"source-chunk\" data-start=\"{start}\" data-rows=\"{rows}\" \
             style=\"--rows:{rows}\">\
             <pre class=\"gutter\">{gutter}</pre>\
             <pre class=\"code\"><code{code_class}>{code}</code></pre></section>"
        );
    }
    (out, number)
}

async fn source_page(
    state: &AppState,
    path: &Path,
    rel: &str,
    info: &FileInfo,
    mtime: SystemTime,
    is_head: bool,
) -> Response {
    let bytes = match tokio::fs::read(path).await {
        Ok(bytes) => bytes,
        Err(_) => {
            return error_page(
                state,
                StatusCode::NOT_FOUND,
                "这个文件不存在，或已被移动",
                is_head,
            )
            .await;
        }
    };
    let size = bytes.len();
    let text = String::from_utf8_lossy(&bytes);
    let chunked_mode = size as u64 > CHUNKED_SOURCE_THRESHOLD;
    let name = path.file_name().and_then(OsStr::to_str).unwrap_or("文件");
    let download = format!("{}?download=1", join_href(parent_rel(rel), name, false));
    let render_link = if info.kind == Kind::Markdown {
        format!(
            "<a class=\"action primary\" href=\"/{}\">{}<span>预览</span></a>",
            encode_path(rel),
            icon("book")
        )
    } else {
        String::new()
    };
    let code_class = highlight_language(path)
        .map(|lang| format!(" class=\"language-{lang}\""))
        .unwrap_or_default();
    let (source_markup, line_count) = if chunked_mode {
        let (chunks, total) = source_chunked(&text, SOURCE_CHUNK_LINES, &code_class);
        (
            format!(
                "<div class=\"source-wrap source-chunked\" data-source-lines=\"{total}\" \
                 data-chunk-lines=\"{chunk_lines}\">{chunks}</div>\
                 <p class=\"source-note\">文件较大（{size} · {total} 行），已加载完整内容。</p>",
                total = total,
                chunk_lines = SOURCE_CHUNK_LINES,
                chunks = chunks,
                size = format_size(size as u64)
            ),
            total,
        )
    } else {
        let (gutter, code, shown) = source_lines(&text, usize::MAX);
        (
            format!(
                "<div class=\"source-wrap\"><div class=\"source\">\
                 <pre class=\"gutter\">{gutter}</pre>\
                 <pre class=\"code\"><code{code_class}>{code}</code></pre></div></div>",
                gutter = gutter,
                code_class = code_class,
                code = code
            ),
            shown,
        )
    };
    let crumbs = page_crumbs(state, rel, PageKind::Source);
    let kind_label = source_language_label(path, info);
    let size_label = format_size(size as u64);
    let mtime_label = format_mtime(mtime);
    let body = format!(
        "<div class=\"content-card\"><div class=\"page-head\"><div class=\"head-inner page-head-inner\"><div class=\"grow\">\
         <nav class=\"crumbs\" aria-label=\"面包屑\">{crumbs}</nav>\
         <h1>{name}</h1>\
         <div class=\"source-tags\">\
         <span class=\"badge source-kind\">{kind_icon}<span>{kind}</span></span>\
         <span class=\"badge\">{size}</span>\
         <span class=\"badge\">{lines} 行</span>\
         <span class=\"badge\">更新于 {mtime}</span>\
         </div></div>\
         <div class=\"page-actions\">{render_link}\
         <a class=\"action\" href=\"{download}\" aria-label=\"下载\">{download_icon}<span>下载</span></a>\
         </div></div></div>{source_markup}</div>",
        crumbs = crumbs,
        name = escape_html(name),
        kind_icon = icon("code"),
        kind = escape_html(&kind_label),
        size = size_label,
        lines = line_count,
        mtime = mtime_label,
        download_icon = icon("download"),
        source_markup = source_markup
    );
    html_page(
        state,
        StatusCode::OK,
        Page {
            title: format!("{name} · 源码"),
            rel: rel.to_string(),
            query: String::new(),
            kind: PageKind::Source,
            body,
        },
        is_head,
    )
    .await
}

async fn render_page(state: &AppState, path: &Path, rel: &str, is_head: bool) -> Response {
    let metadata = match tokio::fs::metadata(path).await {
        Ok(meta) => meta,
        Err(_) => {
            return error_page(
                state,
                StatusCode::NOT_FOUND,
                "这个文件不存在，或已被移动",
                is_head,
            )
            .await;
        }
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
            Err(_) => {
                return error_page(
                    state,
                    StatusCode::NOT_FOUND,
                    "这个文件不存在，或已被移动",
                    is_head,
                )
                .await;
            }
        };
        let text = String::from_utf8_lossy(&bytes);
        let html = render_markdown_with_sourcepos(&text, rel);
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
    let meta = format!("Markdown · {} · {}", format_size(size), format_mtime(mtime));
    let crumbs = page_crumbs(state, rel, PageKind::Doc);
    let body = format!(
        "<article class=\"content-card doc-card\"><header class=\"doc-head\"><div class=\"head-inner\">\
         <nav class=\"crumbs\" aria-label=\"面包屑\">{crumbs}</nav>\
         <div class=\"article-toolbar\"><span class=\"doc-meta\">{meta}</span>\
         <div class=\"page-actions\"><a class=\"action\" href=\"/{encoded}?raw=1\">{code_icon}<span>源码</span></a>\
         <a class=\"action\" href=\"/{encoded}?download=1\">{download_icon}<span>下载</span></a></div></div>\
         </div></header>\
         <div class=\"toc-inline\" id=\"toc-slot\"><details class=\"toc\"><summary>本页目录</summary><nav class=\"toc-list\" aria-label=\"本页目录\"></nav></details></div>\
         <div class=\"doc-prose\"><h1 class=\"sr-only\">{name}</h1><article class=\"markdown-body\">{rendered}</article></div></article>",
        name = escape_html(name),
        meta = escape_html(&meta),
        crumbs = crumbs,
        code_icon = icon("code"),
        download_icon = icon("download")
    );
    html_page(
        state,
        StatusCode::OK,
        Page {
            title: name.to_string(),
            rel: rel.to_string(),
            query: String::new(),
            kind: PageKind::Doc,
            body,
        },
        is_head,
    )
    .await
}

async fn interstitial_page(state: &AppState, rel: &str, is_head: bool) -> Response {
    let token = state.store_token(rel);
    let encoded = encode_path(rel);
    let cancel = match rel.rfind('/') {
        Some(index) => format!("/{}/", encode_path(&rel[..index])),
        None => "/".to_string(),
    };
    let body = format!(
        "<div class=\"content-card\"><div class=\"trust-panel\"><div class=\"trust-icon\">{lock}</div>\
         <h1>此目录尚未受信任</h1><p>这个 Markdown 文件所在的目录尚未受信任。仍要打开吗？</p>\
         <p class=\"trust-path\">{rel}</p><div class=\"trust-actions\">\
         <a class=\"action\" href=\"{cancel}\">取消</a>\
         <a class=\"action primary\" href=\"/{encoded}?open={token}\">仍要打开</a></div></div></div>",
        lock = icon("lock"),
        rel = escape_html(rel)
    );
    html_page(
        state,
        StatusCode::OK,
        Page {
            title: "此目录尚未受信任".to_string(),
            rel: rel.to_string(),
            query: String::new(),
            kind: PageKind::Other,
            body,
        },
        is_head,
    )
    .await
}

fn source_language_label(path: &Path, info: &FileInfo) -> String {
    if info.kind == Kind::Markdown {
        return "Markdown".to_string();
    }
    let ext = path
        .extension()
        .and_then(OsStr::to_str)
        .unwrap_or("")
        .to_ascii_lowercase();
    let label = match ext.as_str() {
        "md" | "markdown" | "mdx" => "Markdown",
        "html" | "htm" => "HTML",
        "xml" => "XML",
        "toml" => "TOML",
        "ini" | "cfg" | "conf" | "properties" => "INI",
        "yaml" | "yml" => "YAML",
        "json" => "JSON",
        "rs" => "Rust",
        "py" => "Python",
        "js" | "mjs" | "cjs" | "jsx" => "JavaScript",
        "ts" | "tsx" => "TypeScript",
        "go" => "Go",
        "java" => "Java",
        "kt" | "kts" => "Kotlin",
        "c" | "h" => "C",
        "cc" | "cpp" | "cxx" | "hpp" | "hh" => "C++",
        "cs" => "C#",
        "rb" => "Ruby",
        "php" => "PHP",
        "pl" | "pm" => "Perl",
        "lua" => "Lua",
        "sql" => "SQL",
        "sh" | "bash" | "zsh" | "fish" => "Shell",
        "css" => "CSS",
        "scss" => "SCSS",
        "sass" => "Sass",
        "less" => "Less",
        "diff" | "patch" => "Diff",
        "swift" => "Swift",
        "dart" => "Dart",
        "scala" => "Scala",
        "r" => "R",
        "tex" => "LaTeX",
        "proto" => "Protobuf",
        "graphql" | "gql" => "GraphQL",
        _ => match path.file_name().and_then(OsStr::to_str).unwrap_or("") {
            "Dockerfile" | "Containerfile" => "Dockerfile",
            "Makefile" => "Makefile",
            _ => "文本",
        },
    };
    label.to_string()
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
        Err(_) => {
            return error_page(
                state,
                StatusCode::NOT_FOUND,
                "这个文件不存在，或已被移动",
                is_head,
            )
            .await;
        }
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

#[derive(Clone, Copy, PartialEq, Eq)]
enum PageKind {
    Dir,
    Doc,
    Source,
    Search,
    Other,
}

struct Page {
    title: String,
    rel: String,
    query: String,
    kind: PageKind,
    body: String,
}

fn icon(name: &str) -> &'static str {
    match name {
        "search" => {
            r#"<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>"#
        }
        "chevron" => {
            r#"<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="m9 18 6-6-6-6"/></svg>"#
        }
        "folder" => {
            r#"<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>"#
        }
        "file" => {
            r#"<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg>"#
        }
        "code" => {
            r#"<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="m8 9-3 3 3 3"/><path d="m16 9 3 3-3 3"/></svg>"#
        }
        "download" => {
            r#"<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v12"/><path d="m7 10 5 5 5-5"/><path d="M5 21h14"/></svg>"#
        }
        "copy" => {
            r#"<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>"#
        }
        "check" => {
            r#"<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M20 6 9 17l-5-5"/></svg>"#
        }
        "panel" => {
            r#"<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16"/></svg>"#
        }
        "sun" => {
            r#"<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>"#
        }
        "moon" => {
            r#"<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3 7 7 0 0 0 21 12.8z"/></svg>"#
        }
        "monitor" => {
            r#"<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4"/></svg>"#
        }
        "arrow-left" => {
            r#"<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M19 12H5"/><path d="m12 19-7-7 7-7"/></svg>"#
        }
        "book" => {
            r#"<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>"#
        }
        "lock" => {
            r#"<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="10" width="16" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/></svg>"#
        }
        "file-search" => {
            r#"<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h6"/><path d="M14 2v6h6"/><circle cx="17" cy="17" r="3"/><path d="m21 21-1.5-1.5"/></svg>"#
        }
        _ => "",
    }
}

fn root_name(state: &AppState) -> String {
    state
        .root
        .file_name()
        .and_then(OsStr::to_str)
        .filter(|name| !name.is_empty())
        .unwrap_or("docs")
        .to_string()
}

fn crumbs_html(rel: &str, kind: PageKind) -> String {
    if kind == PageKind::Search {
        return "<span class=\"current\">搜索</span>".to_string();
    }
    if kind == PageKind::Other {
        return String::new();
    }
    let parts: Vec<&str> = rel.split('/').filter(|part| !part.is_empty()).collect();
    if parts.is_empty() {
        return String::new();
    }
    let mut html = String::new();
    let mut accumulated = String::new();
    for (index, part) in parts.iter().enumerate() {
        if index > 0 {
            html.push_str(icon("chevron"));
        }
        accumulated.push('/');
        accumulated.push_str(part);
        if index + 1 == parts.len() {
            html.push_str("<span class=\"current\">");
            html.push_str(&escape_html(part));
            html.push_str("</span>");
        } else {
            html.push_str("<a href=\"");
            html.push_str(&encode_path(&accumulated));
            html.push_str("/\">");
            html.push_str(&escape_html(part));
            html.push_str("</a>");
        }
    }
    html
}

fn page_crumbs(state: &AppState, rel: &str, kind: PageKind) -> String {
    let root = format!("<a href=\"/\">{}</a>", escape_html(&root_name(state)));
    let tail = crumbs_html(rel, kind);
    if tail.is_empty() {
        format!("{}{root}", icon("folder"))
    } else {
        format!("{}{root}{}{tail}", icon("folder"), icon("chevron"))
    }
}

fn topbar_search(query: &str) -> String {
    format!(
        "<div class=\"search-wrap\">\
         <a class=\"icon-btn search-open\" id=\"search-open\" href=\"/search\" \
         aria-label=\"搜索\" title=\"搜索（/）\" aria-expanded=\"false\">{search}</a>\
         <div class=\"search-pop\" id=\"search-pop\" hidden>\
         <form class=\"search-form\" id=\"search-form\" action=\"/search\" method=\"get\" role=\"search\">\
         {search}<input id=\"search-input\" type=\"search\" name=\"q\" value=\"{query}\" \
         placeholder=\"搜索文件名和内容\" aria-label=\"搜索文件名和内容\" autocomplete=\"off\">\
         <button class=\"search-submit\" type=\"submit\">搜索</button></form>\
         <div class=\"search-hint\"><span><kbd class=\"kbd\">Enter</kbd> 打开搜索页</span>\
         <span><kbd class=\"kbd\">Esc</kbd> 关闭</span></div></div></div>",
        search = icon("search"),
        query = escape_html(query)
    )
}

async fn html_page(state: &AppState, status: StatusCode, page: Page, is_head: bool) -> Response {
    let nonce = random_nonce();
    let version = crate::assets::asset_version();
    let search = if state.no_search {
        String::new()
    } else {
        topbar_search(&page.query)
    };
    let is_doc = page.kind == PageKind::Doc;
    let shell_class = if is_doc { "shell has-toc" } else { "shell" };
    let toc_rail = if is_doc {
        "<aside class=\"toc-rail\" id=\"toc-rail\" aria-label=\"本页目录\"></aside>".to_string()
    } else {
        String::new()
    };
    let page_class = match page.kind {
        PageKind::Dir => "dir",
        PageKind::Doc => "doc",
        PageKind::Source => "source",
        PageKind::Search => "search",
        PageKind::Other => "other",
    };
    let mut islands = vec!["theme", "nav"];
    if !state.no_search {
        islands.push("search");
    }
    islands.push("totop");
    if is_doc {
        islands.extend(["toc", "linetarget", "code", "zoom"]);
    }
    if page.kind == PageKind::Source {
        islands.push("source");
    }
    let islands = islands.join(" ");
    let root = escape_html(&root_name(state));
    let current_path = match page.kind {
        PageKind::Dir | PageKind::Doc | PageKind::Source => page.rel.as_str(),
        _ => "",
    };
    let current_is_dir = if page.kind == PageKind::Dir { "1" } else { "0" };
    let html = format!(
        "<!doctype html><html lang=\"zh-CN\" class=\"no-js\"><head><meta charset=\"utf-8\">\
         <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\
         <title>{title} · mdview</title>\
         <script nonce=\"{nonce}\">(function(){{try{{var t=localStorage.getItem('mdview-theme');\
         if(t==='light'||t==='dark'){{document.documentElement.dataset.theme=t;document.documentElement.dataset.themeMode=t;}}\
         else if(t==='system'){{document.documentElement.dataset.themeMode='system';}}\
         }}catch(e){{}}}})();</script>\
         <link rel=\"stylesheet\" href=\"/_assets/markdown.css?v={version}\">\
         <link rel=\"stylesheet\" href=\"/_assets/highlight.css?v={version}\">\
         <link rel=\"stylesheet\" href=\"/_assets/app.css?v={version}\">\
         <script nonce=\"{nonce}\" src=\"/_assets/highlight.js?v={version}\" defer></script>\
         <script nonce=\"{nonce}\" src=\"/_assets/app.js?v={version}\" defer></script>\
         </head><body data-totop=\"1\" data-page=\"{page_class}\" data-islands=\"{islands}\" \
         data-current-path=\"{current_path}\" data-current-dir=\"{current_is_dir}\">\
         <div class=\"app\"><header class=\"topbar\">\
         <button class=\"icon-btn nav-toggle\" id=\"nav-toggle\" type=\"button\" aria-label=\"打开全站导航\" aria-expanded=\"false\">{panel}</button>\
         <a class=\"brand\" href=\"/\"><span class=\"brand-mark\">m</span><span>mdview</span></a>\
         <div class=\"topbar-actions\">{search}<button class=\"icon-btn theme-toggle\" id=\"theme-toggle\" type=\"button\" aria-label=\"切换主题\" title=\"主题：跟随系统\">\
         <span class=\"theme-icon theme-system\">{monitor}</span>\
         <span class=\"theme-icon theme-light\">{sun}</span>\
         <span class=\"theme-icon theme-dark\">{moon}</span></button></div>\
         </header>\
         <aside class=\"nav-panel\" id=\"nav-panel\" data-root=\"{root}\" aria-label=\"全站导航\" aria-hidden=\"true\"></aside>\
         <div class=\"nav-scrim\" id=\"nav-scrim\"></div>\
         <div class=\"{shell_class}\" id=\"shell\"><main class=\"main\">{body}</main>{toc_rail}</div></div></body></html>",
        title = escape_html(&page.title),
        nonce = nonce,
        version = version,
        page_class = page_class,
        islands = islands,
        root = root,
        current_path = escape_html(current_path),
        current_is_dir = current_is_dir,
        panel = icon("panel"),
        search = search,
        shell_class = shell_class,
        toc_rail = toc_rail,
        monitor = icon("monitor"),
        sun = icon("sun"),
        moon = icon("moon"),
        body = page.body
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

async fn error_page(
    state: &AppState,
    status: StatusCode,
    message: &str,
    is_head: bool,
) -> Response {
    let title = match status {
        StatusCode::FORBIDDEN => "无法访问",
        StatusCode::BAD_REQUEST => "请求无法处理",
        StatusCode::METHOD_NOT_ALLOWED => "请求无法处理",
        _ => "页面不存在",
    };
    let body = format!(
        "<div class=\"content-card\"><div class=\"empty-state\"><h1>{title}</h1>\
         <p>{message}</p><a class=\"action primary\" href=\"/\">返回首页</a></div></div>",
        title = escape_html(title),
        message = escape_html(message)
    );
    html_page(
        state,
        status,
        Page {
            title: title.to_string(),
            rel: String::new(),
            query: String::new(),
            kind: PageKind::Other,
            body,
        },
        is_head,
    )
    .await
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
    escape_html_into(&mut out, value);
    out
}

fn escape_html_into(out: &mut String, value: &str) {
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
         form-action 'self'; connect-src 'self'; base-uri 'none'; object-src 'none'"
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
    let offset = time::UtcOffset::current_local_offset().unwrap_or(time::UtcOffset::UTC);
    let datetime = OffsetDateTime::from(time).to_offset(offset);
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
        return "0 KB".to_string();
    }
    const KIB: u64 = 1024;
    if bytes < KIB {
        return "<1 KB".to_string();
    }
    const UNITS: [&str; 5] = ["KB", "MB", "GB", "TB", "PB"];
    let mut value = bytes as f64 / KIB as f64;
    let mut unit = 0usize;
    while value >= 1024.0 && unit + 1 < UNITS.len() {
        value /= 1024.0;
        unit += 1;
    }
    let mut rounded = (value * 10.0).round() / 10.0;
    if rounded >= 1024.0 && unit + 1 < UNITS.len() {
        rounded /= 1024.0;
        unit += 1;
        rounded = (rounded * 10.0).round() / 10.0;
    }
    if rounded.fract() == 0.0 {
        format!("{} {}", rounded as u64, UNITS[unit])
    } else {
        format!("{rounded:.1} {}", UNITS[unit])
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
        assert!(!html.contains("id=\"toc-nav\""));

        let (_, _, body) = call(app.clone(), Method::GET, "/sub/").await;
        let html = String::from_utf8(body).unwrap();
        assert!(html.contains("aria-label=\"面包屑\""), "{html}");
        assert!(html.contains("<a href=\"/\">"), "{html}");
        assert!(!html.contains("上级目录"), "{html}");
        assert!(!html.contains("<h2>目录</h2>"), "{html}");
        assert!(!html.contains("<h2>文件</h2>"), "{html}");
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
        assert!(html.contains("<h1>a.md</h1>"), "{html}");
        assert!(html.contains("预览"), "{html}");
        assert!(html.contains("href=\"/a.md\""), "{html}");
        assert!(html.contains("id=\"L1\""), "{html}");
        assert!(html.contains("<1 KB"), "{html}");
        assert!(html.contains("更新于"), "{html}");

        let (status, _, body) = call(app.clone(), Method::GET, "/b.txt").await;
        assert_eq!(status, StatusCode::OK);
        let html = String::from_utf8(body).unwrap();
        assert!(html.contains("<h1>b.txt</h1>"), "{html}");
        assert!(html.contains(">文本<"), "{html}");
        assert!(html.contains("3 行"), "{html}");

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
    async fn large_source_page_renders_full_content_in_chunks() {
        let dir = fixture();
        let mut content = "line with some text 0123456789\n".repeat(11_999);
        content.push_str("last line marker");
        std::fs::write(dir.path().join("big.txt"), &content).unwrap();
        let app = app(state(dir.path(), false, 0, 0));

        let (status, _, body) = call(app, Method::GET, "/big.txt").await;
        assert_eq!(status, StatusCode::OK);
        let html = String::from_utf8(body).unwrap();
        assert!(
            html.contains("class=\"source-wrap source-chunked\""),
            "{html}"
        );
        assert!(html.contains("data-source-lines=\"12000\""), "{html}");
        assert!(html.contains("data-chunk-lines=\"500\""), "{html}");
        assert_eq!(html.matches("class=\"source-chunk\"").count(), 24);
        assert!(html.contains("last line marker"), "last line missing");
        assert!(html.contains("已加载完整内容"), "{html}");
        assert!(!html.contains("浏览器按可视区域"), "{html}");
        assert!(!html.contains("source-virtual"), "{html}");
        assert!(!html.contains("?text=1"), "{html}");
        assert!(!html.contains("前 1000 行"), "{html}");
    }

    #[tokio::test]
    async fn markdown_renders_when_trusted() {
        let dir = fixture();
        let app = app(state(dir.path(), false, 0, 0));
        let (status, _, body) = call(app.clone(), Method::GET, "/a.md").await;
        assert_eq!(status, StatusCode::OK);
        let html = String::from_utf8(body).unwrap();
        assert!(html.contains(">hi</h1>"));
        assert!(html.contains("class=\"markdown-body\""));
        assert!(html.contains("data-sourcepos="), "{html}");
        assert!(html.contains("class=\"shell has-toc\""));
        assert!(html.contains("class=\"toc-rail\" id=\"toc-rail\""));
        assert!(html.contains("id=\"toc-slot\""));
        assert!(html.contains("data-islands=\"theme nav search totop toc linetarget code zoom\""));
        assert!(html.contains("id=\"nav-toggle\""));
        assert!(html.contains("id=\"nav-panel\""));
        assert!(!html.contains("sidebar-toggle"));
        assert!(html.contains("class=\"search-wrap\""));
        assert!(!html.contains("id=\"toc-toggle\""));
        assert!(!html.contains("<h1>源码</h1>"));

        let (status, _, body) = call(app, Method::GET, "/a.md?raw=1").await;
        assert_eq!(status, StatusCode::OK);
        let html = String::from_utf8(body).unwrap();
        assert!(html.contains("<h1>a.md</h1>"));
        assert!(!html.contains("<h1>源码</h1>"));
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
        assert!(html.contains(">hi</h1>"));

        let (_, _, body) = call(app.clone(), Method::GET, &uri).await;
        let html = String::from_utf8(body).unwrap();
        assert!(html.contains("仍要打开"));

        let (status, _, body) = call(app, Method::GET, "/a.md?raw=1").await;
        assert_eq!(status, StatusCode::OK);
        let html = String::from_utf8(body).unwrap();
        assert!(html.contains("<h1>a.md</h1>"));
        assert!(!html.contains("<h1>源码</h1>"));
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
        assert!(html.contains(">hi</h1>"), "{html}");
    }

    #[tokio::test]
    async fn nav_endpoint_lists_full_tree_without_hidden_dirs() {
        let dir = fixture();
        std::fs::create_dir(dir.path().join(".hidden")).unwrap();
        std::fs::write(dir.path().join(".hidden").join("h.md"), "# hidden\n").unwrap();
        let app = app(state(dir.path(), false, 0, 0));
        let (status, headers, body) = call(app, Method::GET, "/_nav").await;
        assert_eq!(status, StatusCode::OK);
        assert!(
            headers
                .get(header::CONTENT_TYPE)
                .unwrap()
                .to_str()
                .unwrap()
                .starts_with("application/json")
        );
        let payload: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert_eq!(
            payload["root"],
            dir.path().file_name().unwrap().to_str().unwrap()
        );
        let tree = payload["tree"].as_array().unwrap();
        assert_eq!(tree[0]["type"], "dir", "directories sort first");
        assert!(
            tree.iter()
                .any(|node| node["name"] == "img.png" && node["file_kind"] == "image")
        );
        assert!(
            tree.iter()
                .any(|node| node["name"] == "bin.dat" && node["file_kind"] == "binary")
        );
        let sub = tree.iter().find(|node| node["name"] == "sub").unwrap();
        assert!(
            sub["children"]
                .as_array()
                .unwrap()
                .iter()
                .any(|node| node["name"] == "c.md")
        );
        assert!(!body.windows(8).any(|window| window == b".hidden"));

        let safe_app = super::app(state(dir.path(), true, 0, 0));
        let (status, _, safe_body) = call(safe_app, Method::GET, "/_nav").await;
        assert_eq!(status, StatusCode::OK);
        assert!(!safe_body.windows(7).any(|window| window == b"bin.dat"));
        assert!(safe_body.windows(7).any(|window| window == b"img.png"));
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
        assert!(csp.contains("form-action 'self'"));
        assert!(csp.contains("connect-src 'self'"));
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
    async fn search_groups_docs_text_and_files() {
        let dir = fixture();
        let app = app(state(dir.path(), false, 0, 0));
        let (status, _, body) = call(app.clone(), Method::GET, "/search?q=second").await;
        assert_eq!(status, StatusCode::OK);
        let html = String::from_utf8(body).unwrap();
        assert!(html.contains("a.md"), "{html}");
        assert!(
            html.contains("class=\"result-head\" href=\"/a.md\""),
            "{html}"
        );
        assert!(html.contains("href=\"/a.md#L3\""), "{html}");
        assert!(html.contains("1 条结果"), "{html}");
        assert!(!html.contains("打开文档"), "{html}");
        assert!(!html.contains("源码 Ln"), "{html}");
        assert!(!html.contains("命中"), "{html}");
        assert!(!html.contains("实时扫描"), "{html}");
        assert!(!html.contains("?raw=1#L3"), "{html}");

        let (_, _, body) = call(app.clone(), Method::GET, "/search?q=hello").await;
        let html = String::from_utf8(body).unwrap();
        assert!(html.contains("b.txt"), "{html}");
        assert!(html.contains("href=\"/b.txt#L1\""), "{html}");
        assert!(!html.contains("源码 Ln"), "{html}");

        let (_, _, body) = call(app.clone(), Method::GET, "/search?q=fn%20main").await;
        let html = String::from_utf8(body).unwrap();
        assert!(html.contains("code.rs"), "{html}");
        assert!(html.contains("href=\"/code.rs#L1\""), "{html}");
        assert!(!html.contains("源码 Ln"), "{html}");

        let (_, _, body) = call(app.clone(), Method::GET, "/search?q=img.png").await;
        let html = String::from_utf8(body).unwrap();
        assert!(html.contains("img.png"), "{html}");
        assert!(
            html.contains("class=\"result-head\" href=\"/img.png\""),
            "{html}"
        );
        assert!(!html.contains("文件名命中"), "{html}");

        let (_, _, body) = call(app.clone(), Method::GET, "/search?q=zzz").await;
        let html = String::from_utf8(body).unwrap();
        assert!(html.contains("没有找到相关内容"), "{html}");

        let (status, _, _) = call(app, Method::GET, "/search").await;
        assert_eq!(status, StatusCode::OK);
    }

    #[test]
    fn file_size_display_starts_at_kb() {
        assert_eq!(format_size(0), "0 KB");
        assert_eq!(format_size(1), "<1 KB");
        assert_eq!(format_size(1023), "<1 KB");
        assert_eq!(format_size(1024), "1 KB");
        assert_eq!(format_size(1536), "1.5 KB");
        assert_eq!(format_size(3985), "3.9 KB");
        assert_eq!(format_size(19442), "19 KB");
        assert_eq!(format_size(1024 * 1024 - 1), "1 MB");
        assert_eq!(format_size(1024 * 1024), "1 MB");
        assert_eq!(format_size(20 * 1024 * 1024), "20 MB");
        assert_eq!(format_size(1024 * 1024 * 1024), "1 GB");
    }

    #[test]
    fn source_language_labels_are_friendly() {
        let md = FileInfo {
            kind: Kind::Markdown,
            mime: String::new(),
        };
        let text = FileInfo {
            kind: Kind::Text,
            mime: String::new(),
        };
        assert_eq!(source_language_label(Path::new("a.md"), &md), "Markdown");
        assert_eq!(
            source_language_label(Path::new("a.markdown"), &text),
            "Markdown"
        );
        assert_eq!(source_language_label(Path::new("a.rs"), &text), "Rust");
        assert_eq!(
            source_language_label(Path::new("a.ts"), &text),
            "TypeScript"
        );
        assert_eq!(source_language_label(Path::new("a.txt"), &text), "文本");
        assert_eq!(
            source_language_label(Path::new("Makefile"), &text),
            "Makefile"
        );
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
        assert!(html.contains(">hi</h1>"));

        std::thread::sleep(Duration::from_millis(20));
        std::fs::write(dir.path().join("a.md"), "# changed\n").unwrap();

        let (_, _, body) = call(app, Method::GET, "/a.md").await;
        let html = String::from_utf8(body).unwrap();
        assert!(html.contains(">changed</h1>"));
        assert!(!html.contains(">hi</h1>"));
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
        let (status, _, _) = call(app.clone(), Method::GET, "/_assets/app.css").await;
        assert_eq!(status, StatusCode::OK);
        let (status, headers, body) = call(app.clone(), Method::GET, "/_assets/app.js").await;
        assert_eq!(status, StatusCode::OK);
        assert!(
            headers
                .get(header::CONTENT_TYPE)
                .unwrap()
                .to_str()
                .unwrap()
                .starts_with("text/javascript")
        );
        assert!(body.len() > 10_000);

        let (_, _, body) = call(app.clone(), Method::GET, "/a.md").await;
        let html = String::from_utf8(body).unwrap();
        assert!(html.contains("/_assets/markdown.css"));
        assert!(html.contains("/_assets/highlight.js"));
        assert!(html.contains("/_assets/app.css"));
        assert!(html.contains("/_assets/app.js"));
        assert!(html.contains(&format!("?v={}", crate::assets::asset_version())));
        assert!(html.contains("nonce="));

        let (_, _, body) = call(app, Method::GET, "/code.rs").await;
        let html = String::from_utf8(body).unwrap();
        assert!(html.contains("class=\"language-rust\""));
    }
}
