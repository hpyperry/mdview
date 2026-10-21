//! Read-only archive preview backed by a process-private extraction cache.
//!
//! The server exposes an archive as a virtual directory (`/a.zip/docs/x.md`).
//! This module only detects archive paths, extracts them safely and caches the
//! extracted tree. URL parsing and page rendering stay in `server.rs`.

use std::collections::hash_map::DefaultHasher;
use std::collections::{HashMap, HashSet};
use std::fmt;
use std::fs;
use std::hash::{Hash, Hasher};
use std::io::{self, Read};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Mutex};
use std::time::{Duration, SystemTime, UNIX_EPOCH};

const MAX_ARCHIVE_BYTES: u64 = 200 * 1024 * 1024;
const MAX_EXTRACTED_BYTES: u64 = 1024 * 1024 * 1024;
const MAX_ENTRIES: usize = 20_000;
const MAX_ENTRY_BYTES: u64 = 100 * 1024 * 1024;
const MAX_CACHE_BYTES: u64 = 4 * 1024 * 1024 * 1024;
const STALE_AGE: Duration = Duration::from_secs(24 * 60 * 60);

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ArchiveKind {
    Zip,
    TarGz,
    SevenZ,
}

impl ArchiveKind {
    pub fn detect(path: &Path) -> Option<Self> {
        let name = path.file_name()?.to_str()?.to_ascii_lowercase();
        if name.ends_with(".zip") {
            Some(Self::Zip)
        } else if name.ends_with(".tar.gz") || name.ends_with(".tgz") {
            Some(Self::TarGz)
        } else if name.ends_with(".7z") {
            Some(Self::SevenZ)
        } else {
            None
        }
    }

    pub fn label(self) -> &'static str {
        match self {
            Self::Zip => "ZIP",
            Self::TarGz => "tar.gz",
            Self::SevenZ => "7Z",
        }
    }
}

#[derive(Debug, Clone)]
pub struct ArchiveRequest {
    pub path: PathBuf,
    pub archive_rel: String,
    pub entry_rel: String,
    pub kind: ArchiveKind,
    pub size: u64,
    pub mtime: SystemTime,
}

/// Find the first path segment that is a real archive file. A real directory
/// named `foo.zip` wins and is traversed as a normal directory.
pub async fn detect(root: &Path, rel: &str) -> Option<ArchiveRequest> {
    let segments: Vec<&str> = rel.split('/').filter(|part| !part.is_empty()).collect();
    let mut prefix = String::new();
    for (index, segment) in segments.iter().enumerate() {
        if !prefix.is_empty() {
            prefix.push('/');
        }
        prefix.push_str(segment);
        let candidate = root.join(&prefix);
        let canonical = tokio::fs::canonicalize(&candidate).await.ok()?;
        if !canonical.starts_with(root) {
            return None;
        }
        let metadata = tokio::fs::metadata(&canonical).await.ok()?;
        if metadata.is_dir() {
            continue;
        }
        if !metadata.is_file() {
            return None;
        }
        let kind = ArchiveKind::detect(&canonical)?;
        return Some(ArchiveRequest {
            path: canonical,
            archive_rel: prefix,
            entry_rel: segments[index + 1..].join("/"),
            kind,
            size: metadata.len(),
            mtime: metadata.modified().unwrap_or(UNIX_EPOCH),
        });
    }
    None
}

#[derive(Debug, Clone)]
pub struct ArchiveError {
    pub message: String,
    pub too_large: bool,
}

impl ArchiveError {
    fn new(message: impl Into<String>) -> Self {
        Self {
            message: message.into(),
            too_large: false,
        }
    }

    fn too_large(message: impl Into<String>) -> Self {
        Self {
            message: message.into(),
            too_large: true,
        }
    }
}

impl fmt::Display for ArchiveError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.message)
    }
}

impl std::error::Error for ArchiveError {}

#[derive(Debug)]
pub struct Extracted {
    pub root: PathBuf,
    pub bytes: u64,
    pub entries: usize,
    pub kind: ArchiveKind,
    last_used: AtomicU64,
}

impl Extracted {
    fn touch(&self, tick: u64) {
        self.last_used.store(tick, Ordering::Relaxed);
    }

    fn last_used(&self) -> u64 {
        self.last_used.load(Ordering::Relaxed)
    }
}

#[derive(Clone, Debug, Hash, PartialEq, Eq)]
struct CacheKey {
    path: PathBuf,
    mtime_secs: u64,
    mtime_nanos: u32,
    size: u64,
}

impl CacheKey {
    fn new(request: &ArchiveRequest) -> Self {
        let (mtime_secs, mtime_nanos) = request
            .mtime
            .duration_since(UNIX_EPOCH)
            .map(|duration| (duration.as_secs(), duration.subsec_nanos()))
            .unwrap_or((0, 0));
        Self {
            path: request.path.clone(),
            mtime_secs,
            mtime_nanos,
            size: request.size,
        }
    }
}

#[derive(Default)]
struct CacheState {
    entries: HashMap<CacheKey, Arc<Extracted>>,
    total_bytes: u64,
}

struct StoreInner {
    temp: Mutex<Option<tempfile::TempDir>>,
    cache: Mutex<CacheState>,
    extract_lock: Mutex<()>,
    tick: AtomicU64,
}

#[derive(Clone)]
pub struct ArchiveStore {
    inner: Arc<StoreInner>,
}

impl Default for ArchiveStore {
    fn default() -> Self {
        Self::new()
    }
}

impl ArchiveStore {
    pub fn new() -> Self {
        Self {
            inner: Arc::new(StoreInner {
                temp: Mutex::new(None),
                cache: Mutex::new(CacheState::default()),
                extract_lock: Mutex::new(()),
                tick: AtomicU64::new(1),
            }),
        }
    }

    /// Extract an archive once and return the cached tree. This is blocking;
    /// callers run it inside `spawn_blocking`.
    pub fn get(&self, request: &ArchiveRequest) -> Result<Arc<Extracted>, ArchiveError> {
        if request.size > MAX_ARCHIVE_BYTES {
            return Err(ArchiveError::too_large("压缩包超过 200 MB 上限"));
        }
        let key = CacheKey::new(request);
        let tick = self.inner.tick.fetch_add(1, Ordering::Relaxed);

        {
            let cache = self.inner.cache.lock().unwrap();
            if let Some(entry) = cache.entries.get(&key) {
                entry.touch(tick);
                return Ok(entry.clone());
            }
        }

        // A single first-open extraction at a time keeps the cache simple and
        // avoids two requests racing on the same archive.
        let _extract_guard = self.inner.extract_lock.lock().unwrap();
        {
            let cache = self.inner.cache.lock().unwrap();
            if let Some(entry) = cache.entries.get(&key) {
                entry.touch(tick);
                return Ok(entry.clone());
            }
        }

        let temp_root = self.temp_root()?;
        let mut hasher = DefaultHasher::new();
        key.hash(&mut hasher);
        let dest = temp_root.join(format!("{:016x}", hasher.finish()));
        if dest.exists() {
            fs::remove_dir_all(&dest).ok();
        }
        create_private_dir(&dest)?;

        let extracted = match extract_archive(request, &dest) {
            Ok(meta) => meta,
            Err(error) => {
                fs::remove_dir_all(&dest).ok();
                return Err(error);
            }
        };
        // Canonicalize once: on macOS the temp dir may be under `/var`,
        // while canonicalizing an entry returns `/private/var`.
        let root = fs::canonicalize(&dest).unwrap_or(dest);
        let entry = Arc::new(Extracted {
            root,
            bytes: extracted.bytes,
            entries: extracted.entries,
            kind: request.kind,
            last_used: AtomicU64::new(tick),
        });

        {
            let mut cache = self.inner.cache.lock().unwrap();
            cache.total_bytes = cache.total_bytes.saturating_add(entry.bytes);
            cache.entries.insert(key, entry.clone());
            evict(&mut cache);
        }
        Ok(entry)
    }

    fn temp_root(&self) -> Result<PathBuf, ArchiveError> {
        let mut guard = self.inner.temp.lock().unwrap();
        if let Some(dir) = guard.as_ref() {
            return Ok(dir.path().to_path_buf());
        }
        cleanup_stale();
        let dir = tempfile::Builder::new()
            .prefix("mdview-archive-")
            .tempdir()
            .map_err(|error| ArchiveError::new(format!("无法创建解压临时目录: {error}")))?;
        let path = dir.path().to_path_buf();
        *guard = Some(dir);
        Ok(path)
    }
}

fn evict(cache: &mut CacheState) {
    while cache.total_bytes > MAX_CACHE_BYTES && cache.entries.len() > 1 {
        let victim = cache
            .entries
            .iter()
            .min_by_key(|(_, entry)| entry.last_used())
            .map(|(key, _)| key.clone());
        let Some(key) = victim else {
            break;
        };
        if let Some(entry) = cache.entries.remove(&key) {
            cache.total_bytes = cache.total_bytes.saturating_sub(entry.bytes);
            fs::remove_dir_all(&entry.root).ok();
        } else {
            break;
        }
    }
}

fn cleanup_stale() {
    let base = std::env::temp_dir();
    let Ok(entries) = fs::read_dir(&base) else {
        return;
    };
    let now = SystemTime::now();
    for entry in entries.flatten() {
        let name = entry.file_name();
        let Some(name) = name.to_str() else {
            continue;
        };
        if !name.starts_with("mdview-archive-") {
            continue;
        }
        let Ok(metadata) = entry.metadata() else {
            continue;
        };
        let stale = metadata
            .modified()
            .ok()
            .and_then(|mtime| now.duration_since(mtime).ok())
            .is_some_and(|age| age > STALE_AGE);
        if stale {
            fs::remove_dir_all(entry.path()).ok();
        }
    }
}

#[cfg(unix)]
fn create_private_dir(path: &Path) -> Result<(), ArchiveError> {
    use std::os::unix::fs::DirBuilderExt;
    fs::DirBuilder::new()
        .mode(0o700)
        .create(path)
        .map_err(|error| ArchiveError::new(format!("无法创建解压目录: {error}")))
}

#[cfg(not(unix))]
fn create_private_dir(path: &Path) -> Result<(), ArchiveError> {
    fs::create_dir(path).map_err(|error| ArchiveError::new(format!("无法创建解压目录: {error}")))
}

struct ExtractedMeta {
    bytes: u64,
    entries: usize,
}

#[derive(Default)]
struct Budget {
    bytes: u64,
    entries: usize,
    seen: HashSet<String>,
}

impl Budget {
    fn add_entry(&mut self, rel: &Path) -> Result<(), ArchiveError> {
        self.entries += 1;
        if self.entries > MAX_ENTRIES {
            return Err(ArchiveError::too_large("压缩包条目超过 20000 个"));
        }
        let key = if cfg!(windows) {
            rel.to_string_lossy().to_lowercase()
        } else {
            rel.to_string_lossy().into_owned()
        };
        if !self.seen.insert(key) {
            return Err(ArchiveError::new("压缩包包含重复路径"));
        }
        Ok(())
    }
}

fn extract_archive(request: &ArchiveRequest, dest: &Path) -> Result<ExtractedMeta, ArchiveError> {
    let mut budget = Budget::default();
    match request.kind {
        ArchiveKind::Zip => extract_zip(&request.path, dest, &mut budget)?,
        ArchiveKind::TarGz => extract_tar_gz(&request.path, dest, &mut budget)?,
        ArchiveKind::SevenZ => extract_7z(&request.path, dest, &mut budget)?,
    }
    Ok(ExtractedMeta {
        bytes: budget.bytes,
        entries: budget.entries,
    })
}

pub fn safe_entry_path(name: &str) -> Result<PathBuf, ArchiveError> {
    if name.is_empty() || name.contains('\0') || name.starts_with('/') || name.starts_with('\\') {
        return Err(ArchiveError::new("压缩包包含非法路径"));
    }
    let mut path = PathBuf::new();
    for part in name.split('/') {
        if part.is_empty() || part == "." {
            continue;
        }
        if part == ".." || part.contains('\\') || part.contains(':') {
            return Err(ArchiveError::new("压缩包包含越界路径"));
        }
        path.push(part);
    }
    if path.as_os_str().is_empty() {
        return Err(ArchiveError::new("压缩包包含空路径"));
    }
    Ok(path)
}

fn write_file(
    root: &Path,
    rel: &Path,
    reader: &mut dyn Read,
    declared: u64,
    mtime: Option<SystemTime>,
    budget: &mut Budget,
) -> Result<(), ArchiveError> {
    if declared > MAX_ENTRY_BYTES {
        return Err(ArchiveError::too_large("压缩包单个条目超过 100 MB 上限"));
    }
    if budget.bytes.saturating_add(declared) > MAX_EXTRACTED_BYTES {
        return Err(ArchiveError::too_large("压缩包解压后超过 1 GB 上限"));
    }
    let target = root.join(rel);
    if let Some(parent) = target.parent() {
        fs::create_dir_all(parent)
            .map_err(|error| ArchiveError::new(format!("无法创建解压目录: {error}")))?;
    }
    let mut file = fs::File::create(&target)
        .map_err(|error| ArchiveError::new(format!("无法写入解压文件: {error}")))?;
    let mut limited = reader.take(MAX_ENTRY_BYTES + 1);
    let written = io::copy(&mut limited, &mut file)
        .map_err(|error| ArchiveError::new(format!("解压写入失败: {error}")))?;
    if written > MAX_ENTRY_BYTES {
        return Err(ArchiveError::too_large("压缩包单个条目超过 100 MB 上限"));
    }
    budget.bytes = budget.bytes.saturating_add(written);
    if budget.bytes > MAX_EXTRACTED_BYTES {
        return Err(ArchiveError::too_large("压缩包解压后超过 1 GB 上限"));
    }
    if let Some(mtime) = mtime {
        let _ = filetime::set_file_mtime(&target, filetime::FileTime::from_system_time(mtime));
    }
    Ok(())
}

fn create_dir_entry(root: &Path, rel: &Path) -> Result<(), ArchiveError> {
    fs::create_dir_all(root.join(rel))
        .map_err(|error| ArchiveError::new(format!("无法创建解压目录: {error}")))
}

fn decode_text(raw: &[u8]) -> String {
    if let Ok(text) = std::str::from_utf8(raw) {
        return text.to_string();
    }
    let (decoded, _, had_errors) = encoding_rs::GBK.decode(raw);
    if !had_errors {
        return decoded.into_owned();
    }
    String::from_utf8_lossy(raw).into_owned()
}

fn zip_name(
    file: &zip::read::ZipFile<'_, fs::File>,
    utf8_flag: bool,
) -> Result<String, ArchiveError> {
    let raw = file.name_raw();
    if let Ok(text) = std::str::from_utf8(raw) {
        return Ok(text.to_string());
    }
    if !utf8_flag {
        let (decoded, _, had_errors) = encoding_rs::GBK.decode(raw);
        if !had_errors {
            return Ok(decoded.into_owned());
        }
    }
    file.name()
        .map(|name| name.into_owned())
        .map_err(|error| ArchiveError::new(format!("ZIP 文件名编码无法解析: {error}")))
}

fn zip_mtime(value: zip::DateTime) -> Option<SystemTime> {
    let month = time::Month::try_from(value.month()).ok()?;
    let date = time::Date::from_calendar_date(i32::from(value.year()), month, value.day()).ok()?;
    let hour = value.hour();
    let minute = value.minute();
    let second = value.second();
    let clock = time::Time::from_hms(hour, minute, second).ok()?;
    let stamp = time::PrimitiveDateTime::new(date, clock)
        .assume_utc()
        .unix_timestamp();
    (stamp >= 0).then(|| UNIX_EPOCH + Duration::from_secs(stamp as u64))
}

fn extract_zip(path: &Path, dest: &Path, budget: &mut Budget) -> Result<(), ArchiveError> {
    let file = fs::File::open(path)
        .map_err(|error| ArchiveError::new(format!("无法打开 ZIP: {error}")))?;
    let mut archive = zip::ZipArchive::new(file)
        .map_err(|error| ArchiveError::new(format!("ZIP 格式错误: {error}")))?;
    for index in 0..archive.len() {
        let mut file = archive
            .by_index(index)
            .map_err(|error| ArchiveError::new(format!("ZIP 条目读取失败: {error}")))?;
        if file.encrypted() {
            return Err(ArchiveError::new("加密压缩包不支持预览"));
        }
        if file.is_symlink() {
            return Err(ArchiveError::new("压缩包包含符号链接"));
        }
        let utf8_flag = file.flags().as_u16() & 0x0800 != 0;
        let name = zip_name(&file, utf8_flag)?;
        let rel = safe_entry_path(&name)?;
        budget.add_entry(&rel)?;
        if file.is_dir() {
            create_dir_entry(dest, &rel)?;
            continue;
        }
        let mtime = file.last_modified().and_then(zip_mtime);
        let size = file.size();
        write_file(dest, &rel, &mut file, size, mtime, budget)?;
    }
    Ok(())
}

fn extract_tar_gz(path: &Path, dest: &Path, budget: &mut Budget) -> Result<(), ArchiveError> {
    let file = fs::File::open(path)
        .map_err(|error| ArchiveError::new(format!("无法打开 tar.gz: {error}")))?;
    let decoder = flate2::read::GzDecoder::new(file);
    let mut archive = tar::Archive::new(decoder);
    let entries = archive
        .entries()
        .map_err(|error| ArchiveError::new(format!("tar.gz 格式错误: {error}")))?;
    for entry in entries {
        let mut entry =
            entry.map_err(|error| ArchiveError::new(format!("tar.gz 条目读取失败: {error}")))?;
        let kind = entry.header().entry_type();
        if kind.is_symlink()
            || kind.is_hard_link()
            || kind.is_character_special()
            || kind.is_block_special()
            || kind.is_fifo()
        {
            return Err(ArchiveError::new("压缩包包含不支持的链接或设备文件"));
        }
        if kind.is_gnu_longname()
            || kind.is_gnu_longlink()
            || kind.is_pax_global_extensions()
            || kind.is_pax_local_extensions()
        {
            continue;
        }
        let name = decode_text(&entry.path_bytes());
        let rel = safe_entry_path(&name)?;
        budget.add_entry(&rel)?;
        if kind.is_dir() {
            create_dir_entry(dest, &rel)?;
            continue;
        }
        if !kind.is_file() {
            continue;
        }
        let mtime = entry
            .header()
            .mtime()
            .ok()
            .and_then(|seconds| UNIX_EPOCH.checked_add(Duration::from_secs(seconds)));
        let size = entry.size();
        write_file(dest, &rel, &mut entry, size, mtime, budget)?;
    }
    Ok(())
}

fn extract_7z(path: &Path, dest: &Path, budget: &mut Budget) -> Result<(), ArchiveError> {
    let root = dest.to_path_buf();
    let result = sevenz_rust2::decompress_file_with_extract_fn(path, dest, |entry, reader, _| {
        if entry.is_anti_item || entry.name.is_empty() {
            return Ok(true);
        }
        let rel = safe_entry_path(&entry.name)
            .map_err(|error| sevenz_rust2::Error::Other(error.message.into()))?;
        budget
            .add_entry(&rel)
            .map_err(|error| sevenz_rust2::Error::Other(error.message.into()))?;
        if entry.is_directory {
            create_dir_entry(&root, &rel)
                .map_err(|error| sevenz_rust2::Error::Other(error.message.into()))?;
            return Ok(true);
        }
        let mtime = entry
            .has_last_modified_date
            .then(|| SystemTime::from(entry.last_modified_date));
        write_file(&root, &rel, reader, entry.size, mtime, budget)
            .map_err(|error| sevenz_rust2::Error::Other(error.message.into()))?;
        Ok(true)
    });
    result.map_err(|error| match error {
        sevenz_rust2::Error::PasswordRequired | sevenz_rust2::Error::MaybeBadPassword(_) => {
            ArchiveError::new("加密压缩包不支持预览")
        }
        other => ArchiveError::new(format!("7z 解压失败: {other}")),
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;

    #[test]
    fn cache_reuses_extraction() {
        let dir = tempfile::tempdir().unwrap();
        let zip_path = dir.path().join("a.zip");
        {
            let file = fs::File::create(&zip_path).unwrap();
            let mut writer = zip::ZipWriter::new(file);
            writer
                .start_file(
                    "a.txt",
                    zip::write::SimpleFileOptions::default()
                        .compression_method(zip::CompressionMethod::Stored),
                )
                .unwrap();
            writer.write_all(b"hello").unwrap();
            writer.finish().unwrap();
        }
        let metadata = fs::metadata(&zip_path).unwrap();
        let request = ArchiveRequest {
            path: zip_path,
            archive_rel: "a.zip".to_string(),
            entry_rel: String::new(),
            kind: ArchiveKind::Zip,
            size: metadata.len(),
            mtime: metadata.modified().unwrap(),
        };
        let store = ArchiveStore::new();
        let first = store.get(&request).unwrap();
        let second = store.get(&request).unwrap();
        assert!(Arc::ptr_eq(&first, &second));
        assert_eq!(first.entries, 1);
    }

    #[test]
    fn safe_paths_reject_escapes() {
        assert_eq!(
            safe_entry_path("docs/a.md").unwrap(),
            PathBuf::from("docs/a.md")
        );
        assert_eq!(safe_entry_path("./a.md").unwrap(), PathBuf::from("a.md"));
        for bad in ["", ".", "../x", "/etc/passwd", "a\\b", "C:/x", "a/../../b"] {
            assert!(safe_entry_path(bad).is_err(), "{bad:?}");
        }
    }

    #[test]
    fn gbk_fallback_decodes() {
        let (raw, _, _) = encoding_rs::GBK.encode("中文");
        assert_eq!(decode_text(&raw), "中文");
    }

    #[test]
    fn budget_rejects_duplicate_paths() {
        let mut budget = Budget::default();
        budget.add_entry(Path::new("a.txt")).unwrap();
        assert!(budget.add_entry(Path::new("a.txt")).is_err());
    }

    #[test]
    fn detects_supported_extensions() {
        assert_eq!(
            ArchiveKind::detect(Path::new("a.zip")),
            Some(ArchiveKind::Zip)
        );
        assert_eq!(
            ArchiveKind::detect(Path::new("a.tar.gz")),
            Some(ArchiveKind::TarGz)
        );
        assert_eq!(
            ArchiveKind::detect(Path::new("a.TGZ")),
            Some(ArchiveKind::TarGz)
        );
        assert_eq!(
            ArchiveKind::detect(Path::new("a.7z")),
            Some(ArchiveKind::SevenZ)
        );
        assert_eq!(ArchiveKind::detect(Path::new("a.tar")), None);
        assert_eq!(ArchiveKind::detect(Path::new("a.txt")), None);
    }
}
