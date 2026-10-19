//! Server startup and HTTP routing.
//!
//! P1-5 wires axum/tokio routes here. This module currently owns the banner so
//! the CLI can be exercised before the listener exists.

use std::path::Path;

use crate::cli::Cli;
use crate::trust::TrustState;

pub fn print_banner(cli: &Cli, root: &Path, max_preview: u64, trust: TrustState) {
    println!(
        "mdview {}  单文件离线 Markdown 预览",
        env!("CARGO_PKG_VERSION")
    );
    println!("  root:        {}", root.display());
    println!("  listen:      http://{}:{}", cli.host, cli.port);
    println!("  max preview: {}", format_size(max_preview));
    println!("  safe:        {}", on_off(cli.safe));
    println!("  search:      {}", on_off(!cli.no_search));
    println!("  trust:       {}", trust.describe());
    println!(
        "  security:    {}",
        security_label(cli.security_level.unwrap_or(0))
    );
    println!("  warning:     HTTP server routes are not wired yet (P1-5)");

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

fn format_size(bytes: u64) -> String {
    if bytes == 0 {
        return "unlimited".to_string();
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
        format!("{bytes} bytes")
    }
}
