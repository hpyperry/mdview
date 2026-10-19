//! Trust state for the served root.
//!
//! The startup prompt and persisted TOML config arrive in P1-6. For now this
//! only reflects the explicit `--trust` / `--untrusted` flags.

use crate::cli::Cli;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TrustState {
    Trusted,
    Untrusted,
    Unknown,
}

impl TrustState {
    pub fn from_cli(cli: &Cli) -> Self {
        if cli.trust {
            Self::Trusted
        } else if cli.untrusted {
            Self::Untrusted
        } else {
            Self::Unknown
        }
    }

    pub fn describe(self) -> &'static str {
        match self {
            Self::Trusted => "trusted (--trust)",
            Self::Untrusted => "untrusted (--untrusted)",
            Self::Unknown => "unknown (startup prompt lands in P1-6)",
        }
    }
}
