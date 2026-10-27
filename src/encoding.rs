//! File encoding detection for previews.
//!
//! The detection is intentionally heuristic: BOM first, a full-file UTF-8
//! validation, a conservative UTF-16 heuristic, then chardetng. The server only
//! uses this for mdview-generated previews and search; HTML raw bytes keep their
//! own BOM/meta semantics (ADR 0015).

use chardetng::{EncodingDetector, Iso2022JpDetection, Utf8Detection};
use encoding_rs::{Encoding, UTF_8, UTF_16BE, UTF_16LE};

/// Streaming responses only read this much before choosing a charset.
pub const DETECT_WINDOW: usize = 64 * 1024;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DetectionSource {
    Bom,
    Utf8,
    Utf16Heuristic,
    Detector,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Detected {
    pub encoding: &'static Encoding,
    pub bom: bool,
    pub source: DetectionSource,
}

impl Detected {
    /// Human-facing label: encoding name plus ` BOM` when the input had one.
    pub fn label(self) -> String {
        let mut label = self.encoding.name().to_string();
        if self.bom {
            label.push_str(" BOM");
        }
        label
    }

    /// Value for a `Content-Type` charset parameter.
    pub fn charset(self) -> &'static str {
        self.encoding.name()
    }
}

#[derive(Debug)]
pub struct Decoded {
    pub text: String,
    pub detected: Detected,
    /// True when decoding had to insert one or more U+FFFD replacement chars.
    pub had_errors: bool,
}

impl Decoded {
    /// Label for the page: encoding name + BOM + `（有替换）` when needed.
    pub fn label(&self) -> String {
        let mut label = self.detected.label();
        if self.had_errors {
            label.push_str("（有替换）");
        }
        label
    }
}

/// UTF-32 BOMs. encoding_rs would mistake `FF FE 00 00` for UTF-16LE.
pub fn is_utf32_bom(bytes: &[u8]) -> bool {
    bytes.starts_with(&[0xFF, 0xFE, 0x00, 0x00]) || bytes.starts_with(&[0x00, 0x00, 0xFE, 0xFF])
}

/// UTF-16 BOM, excluding UTF-32LE's overlapping `FF FE 00 00`.
pub fn has_utf16_bom(bytes: &[u8]) -> bool {
    if is_utf32_bom(bytes) {
        return false;
    }
    bytes.starts_with(&[0xFF, 0xFE]) || bytes.starts_with(&[0xFE, 0xFF])
}

/// UTF-32 is out of preview scope. BOM is authoritative; the NUL pattern guard
/// catches BOM-less UTF-32 of mostly-ASCII text without guessing a decoder.
pub fn is_unsupported_utf32(bytes: &[u8]) -> bool {
    is_utf32_bom(bytes) || looks_like_utf32(bytes)
}

/// Detect an encoding, or `None` for unsupported UTF-32 input.
pub fn detect(bytes: &[u8], allow_utf16_heuristic: bool) -> Option<Detected> {
    if is_unsupported_utf32(bytes) {
        return None;
    }
    if let Some((encoding, _)) = Encoding::for_bom(bytes) {
        return Some(Detected {
            encoding,
            bom: true,
            source: DetectionSource::Bom,
        });
    }
    if allow_utf16_heuristic && let Some(encoding) = utf16_without_bom(bytes) {
        return Some(Detected {
            encoding,
            bom: false,
            source: DetectionSource::Utf16Heuristic,
        });
    }
    if std::str::from_utf8(bytes).is_ok() {
        return Some(Detected {
            encoding: UTF_8,
            bom: false,
            source: DetectionSource::Utf8,
        });
    }

    let mut detector = EncodingDetector::new(Iso2022JpDetection::Allow);
    detector.feed(detection_sample(bytes), true);
    let encoding = detector.guess(None, Utf8Detection::Allow);
    Some(Detected {
        encoding,
        bom: false,
        source: DetectionSource::Detector,
    })
}

/// Decode complete bytes to a UTF-8 `String`, stripping a matching BOM.
pub fn decode(bytes: &[u8], allow_utf16_heuristic: bool) -> Option<Decoded> {
    let detected = detect(bytes, allow_utf16_heuristic)?;
    let (text, had_errors) = detected.encoding.decode_with_bom_removal(bytes);
    Some(Decoded {
        text: text.into_owned(),
        detected,
        had_errors,
    })
}

/// Decode a prefix for streaming `Content-Type` charset selection. The bytes
/// themselves are not rewritten.
pub fn detect_prefix(bytes: &[u8], allow_utf16_heuristic: bool) -> Option<Detected> {
    detect(bytes, allow_utf16_heuristic)
}

fn detection_sample(bytes: &[u8]) -> &[u8] {
    if bytes.len() <= DETECT_WINDOW {
        return bytes;
    }
    let Some(first_non_ascii) = bytes.iter().position(|byte| !byte.is_ascii()) else {
        return &bytes[..DETECT_WINDOW];
    };
    let start = first_non_ascii.saturating_sub(4096);
    let end = (start + DETECT_WINDOW).min(bytes.len());
    &bytes[start..end]
}

/// Conservative UTF-16LE/BE guess for known text files without a BOM.
/// ASCII-heavy UTF-16 has many NULs in one parity; binary files are left to the
/// normal detector.
fn utf16_without_bom(bytes: &[u8]) -> Option<&'static Encoding> {
    let len = bytes.len().min(4096);
    if len < 8 {
        return None;
    }
    let mut even_nuls = 0usize;
    let mut odd_nuls = 0usize;
    for (index, byte) in bytes[..len].iter().enumerate() {
        if *byte == 0 {
            if index % 2 == 0 {
                even_nuls += 1;
            } else {
                odd_nuls += 1;
            }
        }
    }
    let pairs = len / 2;
    let even_ratio = even_nuls as f64 / pairs as f64;
    let odd_ratio = odd_nuls as f64 / pairs as f64;
    if odd_ratio > 0.30 && even_ratio < 0.02 {
        Some(UTF_16LE)
    } else if even_ratio > 0.30 && odd_ratio < 0.02 {
        Some(UTF_16BE)
    } else {
        None
    }
}

/// UTF-32LE/BE without a BOM: most 4-byte groups have their high two bytes as
/// NUL and form a valid Unicode scalar. Require a strong ratio so UTF-16
/// (two-byte code units) does not match.
fn looks_like_utf32(bytes: &[u8]) -> bool {
    let len = bytes.len().min(512);
    let groups = len / 4;
    if groups < 2 {
        return false;
    }
    let mut le = 0usize;
    let mut be = 0usize;
    for chunk in bytes[..groups * 4].chunks(4) {
        let le_cp = u32::from_le_bytes([chunk[0], chunk[1], chunk[2], chunk[3]]);
        if chunk[2] == 0 && chunk[3] == 0 && le_cp <= 0x10FFFF {
            le += 1;
        }
        let be_cp = u32::from_be_bytes([chunk[0], chunk[1], chunk[2], chunk[3]]);
        if chunk[0] == 0 && chunk[1] == 0 && be_cp <= 0x10FFFF {
            be += 1;
        }
    }
    le * 5 >= groups * 4 || be * 5 >= groups * 4
}

#[cfg(test)]
mod tests {
    use super::*;

    fn decoded(bytes: &[u8], allow_utf16: bool) -> Decoded {
        decode(bytes, allow_utf16).unwrap()
    }

    #[test]
    fn utf8_and_ascii_are_utf8() {
        let ascii = decoded(b"plain text\n", true);
        assert_eq!(ascii.detected.encoding, UTF_8);
        assert!(!ascii.detected.bom);
        assert_eq!(ascii.detected.source, DetectionSource::Utf8);
        assert_eq!(ascii.label(), "UTF-8");

        let utf8 = decoded("中文 UTF-8\n".as_bytes(), true);
        assert_eq!(utf8.text, "中文 UTF-8\n");
        assert_eq!(utf8.label(), "UTF-8");
    }

    #[test]
    fn utf8_bom_is_detected_and_stripped() {
        let value = decoded(b"\xEF\xBB\xBFhello\n", true);
        assert_eq!(value.detected.encoding, UTF_8);
        assert!(value.detected.bom);
        assert_eq!(value.text, "hello\n");
        assert_eq!(value.label(), "UTF-8 BOM");
    }

    #[test]
    fn utf16_boms_are_detected_and_stripped() {
        let le = decoded(b"\xFF\xFE\x2D\x4E\x87\x65", true);
        assert_eq!(le.detected.encoding, UTF_16LE);
        assert!(le.detected.bom);
        assert_eq!(le.text, "中文");
        assert_eq!(le.label(), "UTF-16LE BOM");

        let be = decoded(b"\xFE\xFF\x4E\x2D\x65\x87", true);
        assert_eq!(be.detected.encoding, UTF_16BE);
        assert_eq!(be.text, "中文");
        assert_eq!(be.label(), "UTF-16BE BOM");
    }

    #[test]
    fn no_bom_utf16_ascii_uses_heuristic() {
        let value = decoded(b"A\x00B\x00C\x00D\x00E\x00F\x00", true);
        assert_eq!(value.detected.encoding, UTF_16LE);
        assert_eq!(value.detected.source, DetectionSource::Utf16Heuristic);
        assert_eq!(value.text, "ABCDEF");
        assert_eq!(value.label(), "UTF-16LE");
    }

    #[test]
    fn gbk_and_shift_jis_are_detected() {
        let gbk = decoded(b"\xD6\xD0\xCE\xC4 GBK\n", true);
        assert_eq!(gbk.detected.encoding.name(), "GBK");
        assert_eq!(gbk.text, "中文 GBK\n");

        let sjis = decoded(
            b"\x93\xFA\x96\x7B\x8C\xEA\x82\xCC\x83e\x83L\x83X\x83g\x82\xC5\x82\xB7\x81\x42\n",
            true,
        );
        assert_eq!(sjis.detected.encoding.name(), "Shift_JIS");
        assert!(sjis.text.starts_with("日本語"));
    }

    #[test]
    fn utf32_bom_is_not_previewed() {
        assert!(is_utf32_bom(b"\xFF\xFE\x00\x00"));
        assert!(is_unsupported_utf32(b"\xFF\xFE\x00\x00A\x00\x00\x00"));
        assert!(detect(b"\xFF\xFE\x00\x00A\x00\x00\x00", true).is_none());
        assert!(detect_prefix(b"\xFF\xFE\x00\x00A\x00\x00\x00", true).is_none());
        assert!(!has_utf16_bom(b"\xFF\xFE\x00\x00A\x00\x00\x00"));

        let mut utf32 = Vec::new();
        for ch in "中文".chars() {
            utf32.extend_from_slice(&(ch as u32).to_le_bytes());
        }
        assert!(is_unsupported_utf32(&utf32));
        assert!(detect(&utf32, true).is_none());
    }

    #[test]
    fn replacement_chars_are_flagged() {
        let value = decoded(b"\xEF\xBB\xBF\xFF", true);
        assert_eq!(value.detected.encoding, UTF_8);
        assert!(value.had_errors);
        assert_eq!(value.label(), "UTF-8 BOM（有替换）");
    }

    #[test]
    fn large_gbk_sample_finds_non_ascii_tail() {
        let mut bytes = vec![b'a'; DETECT_WINDOW + 1024];
        bytes.extend_from_slice(b"\xD6\xD0\xCE\xC4\n");
        let value = decoded(&bytes, true);
        assert_eq!(value.detected.encoding.name(), "GBK");
        assert!(value.text.ends_with("中文\n"));
    }
}
