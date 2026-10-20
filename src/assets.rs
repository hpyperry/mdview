//! Embedded assets.
//!
//! Static vendor assets live in `assets/`; the island bundle and application
//! styles are produced by `web/build.mjs` into Cargo's OUT_DIR.

pub const HIGHLIGHT_JS: &[u8] = include_bytes!("../assets/highlight.min.js");
pub const HIGHLIGHT_CSS: &str = include_str!("../assets/highlight.css");
pub const MARKDOWN_CSS: &str = include_str!("../assets/markdown.css");
pub const APP_JS: &[u8] = include_bytes!(concat!(env!("OUT_DIR"), "/app.js"));
pub const APP_CSS: &str = include_str!(concat!(env!("OUT_DIR"), "/app.css"));

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
            APP_JS,
            APP_CSS.as_bytes(),
        ] {
            for &byte in bytes {
                hash ^= u64::from(byte);
                hash = hash.wrapping_mul(0x0000_0100_0000_01b3);
            }
        }
        format!("{hash:016x}")
    })
}

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
