//! Trust state for the served root.
//!
//! The interactive prompt and TOML config are implemented here. The
//! untrusted `.md` interstitial is wired with the Markdown renderer in P2.

use std::collections::BTreeMap;
use std::io::{IsTerminal, Write};
use std::path::{Path, PathBuf};

use anyhow::{Context, Result};
use directories::ProjectDirs;
use serde::{Deserialize, Serialize};

use crate::cli::Cli;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct TrustState {
    pub trusted: bool,
    pub security_level: u8,
}

impl TrustState {
    pub fn new(trusted: bool, security_level: u8) -> Self {
        Self {
            trusted,
            security_level,
        }
    }

    pub fn describe(self) -> &'static str {
        if self.trusted { "trusted" } else { "untrusted" }
    }
}

#[derive(Debug, Default, Serialize, Deserialize)]
struct TrustConfig {
    #[serde(default)]
    roots: BTreeMap<String, RootTrust>,
}

#[derive(Debug, Default, Serialize, Deserialize)]
struct RootTrust {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    trusted: Option<bool>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    security_level: Option<u8>,
}

fn config_path() -> Option<PathBuf> {
    ProjectDirs::from("", "", "mdview").map(|dirs| dirs.config_dir().join("trust.toml"))
}

fn load_config_from(path: &Path) -> TrustConfig {
    match std::fs::read_to_string(path) {
        Ok(text) => toml::from_str(&text).unwrap_or_else(|err| {
            eprintln!(
                "warning: could not parse trust config {}: {err}",
                path.display()
            );
            TrustConfig::default()
        }),
        Err(_) => TrustConfig::default(),
    }
}

fn load_config() -> TrustConfig {
    config_path()
        .map(|path| load_config_from(&path))
        .unwrap_or_default()
}

fn save_config_to(path: &Path, config: &TrustConfig) -> Result<()> {
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)
            .with_context(|| format!("无法创建配置目录: {}", parent.display()))?;
    }
    let text = toml::to_string_pretty(config).context("无法序列化 trust config")?;
    std::fs::write(path, text).with_context(|| format!("无法写入 {}", path.display()))?;
    Ok(())
}

fn save_config(config: &TrustConfig) -> Result<()> {
    match config_path() {
        Some(path) => save_config_to(&path, config),
        None => Ok(()),
    }
}

fn read_prompt_answer() -> bool {
    if !std::io::stdin().is_terminal() {
        return false;
    }
    print!("是否信任该目录？[y/N] ");
    let _ = std::io::stdout().flush();
    let mut line = String::new();
    if std::io::stdin().read_line(&mut line).is_err() {
        return false;
    }
    matches!(
        line.trim().to_ascii_lowercase().as_str(),
        "y" | "yes" | "是" | "信任"
    )
}

/// Trust precedence: explicit flags, then the stored answer, then the
/// interactive prompt. Only a prompted answer is persisted.
fn decide_trust(
    cli_trust: bool,
    cli_untrusted: bool,
    stored: Option<bool>,
    prompt: impl FnOnce() -> bool,
) -> (bool, bool) {
    if cli_trust {
        (true, false)
    } else if cli_untrusted {
        (false, false)
    } else if let Some(value) = stored {
        (value, false)
    } else {
        (prompt(), true)
    }
}

/// Security level precedence: explicit flag (persisted), then stored, then 0.
fn decide_level(cli_level: Option<u8>, stored: Option<u8>) -> (u8, bool) {
    match cli_level {
        Some(level) => (level, true),
        None => (stored.unwrap_or(0), false),
    }
}

/// Resolve trust and security level for `root`.
///
/// `--trust` / `--untrusted` affect this run only; an interactive answer is
/// persisted. `--security-level` is persisted as a setting for this root.
pub fn resolve(cli: &Cli, root: &Path) -> Result<TrustState> {
    let key = root.to_string_lossy().to_string();
    let mut config = load_config();
    let entry = config.roots.entry(key).or_default();

    let (trusted, persist_trust) =
        decide_trust(cli.trust, cli.untrusted, entry.trusted, read_prompt_answer);
    if persist_trust {
        entry.trusted = Some(trusted);
    }

    let (level, persist_level) = decide_level(cli.security_level, entry.security_level);
    if persist_level {
        entry.security_level = Some(level);
    }

    if (persist_trust || persist_level)
        && let Err(err) = save_config(&config)
    {
        eprintln!("warning: could not save trust config: {err}");
    }

    Ok(TrustState::new(trusted, level))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn trust_flags_win_without_persisting() {
        assert_eq!(
            decide_trust(true, false, Some(false), || false),
            (true, false)
        );
        assert_eq!(
            decide_trust(false, true, Some(true), || true),
            (false, false)
        );
    }

    #[test]
    fn stored_trust_is_used_without_prompting() {
        assert_eq!(
            decide_trust(false, false, Some(true), || panic!("prompt")),
            (true, false)
        );
        assert_eq!(
            decide_trust(false, false, Some(false), || panic!("prompt")),
            (false, false)
        );
    }

    #[test]
    fn missing_trust_prompts_and_persists() {
        assert_eq!(decide_trust(false, false, None, || true), (true, true));
        assert_eq!(decide_trust(false, false, None, || false), (false, true));
    }

    #[test]
    fn security_level_flag_persists_and_stored_level_is_reused() {
        assert_eq!(decide_level(Some(3), Some(1)), (3, true));
        assert_eq!(decide_level(None, Some(1)), (1, false));
        assert_eq!(decide_level(None, None), (0, false));
    }

    #[test]
    fn config_round_trips_and_creates_parent_dirs() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("nested").join("trust.toml");
        let mut config = TrustConfig::default();
        config.roots.insert(
            "/tmp/docs".to_string(),
            RootTrust {
                trusted: Some(true),
                security_level: Some(3),
            },
        );
        save_config_to(&path, &config).unwrap();
        let text = std::fs::read_to_string(&path).unwrap();
        assert!(text.contains("trusted = true"));
        assert!(text.contains("security_level = 3"));

        let loaded = load_config_from(&path);
        let entry = loaded.roots.get("/tmp/docs").unwrap();
        assert_eq!(entry.trusted, Some(true));
        assert_eq!(entry.security_level, Some(3));
    }

    #[test]
    fn missing_config_is_empty_and_malformed_falls_back_to_default() {
        let dir = tempfile::tempdir().unwrap();
        let missing = dir.path().join("absent.toml");
        assert!(load_config_from(&missing).roots.is_empty());

        let malformed = dir.path().join("broken.toml");
        std::fs::write(&malformed, "not = [valid").unwrap();
        assert!(load_config_from(&malformed).roots.is_empty());
    }

    #[test]
    fn unset_fields_are_omitted_from_toml() {
        let mut config = TrustConfig::default();
        config.roots.insert(
            "/tmp/docs".to_string(),
            RootTrust {
                trusted: Some(false),
                security_level: None,
            },
        );
        let text = toml::to_string_pretty(&config).unwrap();
        assert!(text.contains("trusted = false"));
        assert!(!text.contains("security_level"));
    }
}
