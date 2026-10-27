//! CLI definition and startup-time validation.

use std::path::PathBuf;

use anyhow::{Context, Result, bail};
use clap::Parser;

/// Zero-dependency offline Markdown preview server.
#[derive(Debug, Parser)]
#[command(name = "mdview", version, about = "单文件离线 Markdown 预览服务器")]
pub struct Cli {
    /// 监听地址
    #[arg(long, default_value = "0.0.0.0")]
    pub host: String,

    /// 监听端口
    #[arg(long, default_value_t = 8000)]
    pub port: u16,

    /// 端口被占用时向后尝试多少个
    #[arg(long = "port-tries", default_value_t = 10)]
    pub port_tries: u16,

    /// 服务根目录；默认当前目录
    #[arg(long)]
    pub root: Option<PathBuf>,

    /// 只放行 .md/.markdown、图片与 HTML 源码；HTML 只给源码
    #[arg(long)]
    pub safe: bool,

    /// 超过该大小的文件不再预览，改为下载；0 = 不限制
    #[arg(long = "max-preview", default_value = "20M")]
    pub max_preview: String,

    /// 关闭全文搜索页
    #[arg(long = "no-search")]
    pub no_search: bool,

    /// 本次运行强制信任根目录
    #[arg(long, conflicts_with = "untrusted")]
    pub trust: bool,

    /// 本次运行强制不信任根目录
    #[arg(long, conflicts_with = "trust")]
    pub untrusted: bool,

    /// VS Code 预览安全级别：0 Strict / 1 HTTP / 2 Disable / 3 localhost HTTP
    #[arg(long = "security-level", value_parser = clap::value_parser!(u8).range(0..=3))]
    pub security_level: Option<u8>,

    /// 把每个请求与耗时打到 stderr，用于诊断样式/导航等客户端问题
    #[arg(long)]
    pub verbose: bool,
}

impl Cli {
    /// Resolve and validate `--root` (or the current directory).
    pub fn resolve_root(&self) -> Result<PathBuf> {
        let raw = match &self.root {
            Some(path) => path.clone(),
            None => std::env::current_dir().context("无法获取当前目录")?,
        };
        let root = std::fs::canonicalize(&raw)
            .with_context(|| format!("无法解析根目录: {}", raw.display()))?;
        if !root.is_dir() {
            bail!("根目录不是目录: {}", root.display());
        }
        Ok(root)
    }

    /// Parse `--max-preview` into bytes. Supports bare bytes, K, M, G (case-insensitive).
    pub fn max_preview_bytes(&self) -> Result<u64> {
        parse_size(&self.max_preview)
    }
}

fn parse_size(raw: &str) -> Result<u64> {
    let text = raw.trim();
    if text.is_empty() {
        bail!("--max-preview 不能为空");
    }
    if text == "0" {
        return Ok(0);
    }
    let (number, multiplier) = match text.chars().last().map(|c| c.to_ascii_uppercase()) {
        Some('K') => (&text[..text.len() - 1], 1024u64),
        Some('M') => (&text[..text.len() - 1], 1024u64 * 1024),
        Some('G') => (&text[..text.len() - 1], 1024u64 * 1024 * 1024),
        _ => (text, 1),
    };
    let value: u64 = number
        .trim()
        .parse()
        .with_context(|| format!("无效的 --max-preview: {raw}"))?;
    value
        .checked_mul(multiplier)
        .with_context(|| format!("--max-preview 溢出: {raw}"))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_sizes() {
        assert_eq!(parse_size("0").unwrap(), 0);
        assert_eq!(parse_size("123").unwrap(), 123);
        assert_eq!(parse_size("512K").unwrap(), 512 * 1024);
        assert_eq!(parse_size("20M").unwrap(), 20 * 1024 * 1024);
        assert_eq!(parse_size("2G").unwrap(), 2 * 1024 * 1024 * 1024);
        assert_eq!(parse_size(" 20m ").unwrap(), 20 * 1024 * 1024);
    }

    #[test]
    fn rejects_bad_sizes() {
        for raw in ["", "abc", "20X", "-1", "1.5M"] {
            assert!(parse_size(raw).is_err(), "{raw:?} should be rejected");
        }
    }

    #[test]
    fn trust_flags_conflict() {
        assert!(Cli::try_parse_from(["mdview", "--trust", "--untrusted"]).is_err());
    }

    #[test]
    fn security_level_is_range_checked() {
        assert!(Cli::try_parse_from(["mdview", "--security-level", "3"]).is_ok());
        assert!(Cli::try_parse_from(["mdview", "--security-level", "4"]).is_err());
    }

    #[test]
    fn defaults_are_stable() {
        let cli = Cli::try_parse_from(["mdview"]).unwrap();
        assert_eq!(cli.host, "0.0.0.0");
        assert_eq!(cli.port, 8000);
        assert_eq!(cli.port_tries, 10);
        assert_eq!(cli.max_preview, "20M");
        assert!(cli.root.is_none());
        assert!(!cli.safe);
        assert!(!cli.no_search);
        assert!(!cli.trust);
        assert!(!cli.untrusted);
        assert!(cli.security_level.is_none());
        assert!(!cli.verbose);
    }
}
