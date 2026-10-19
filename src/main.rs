mod assets;
mod cli;
mod render;
mod server;
mod trust;

use clap::Parser;

fn main() -> anyhow::Result<()> {
    let cli = cli::Cli::parse();
    let root = cli.resolve_root()?;
    let max_preview = cli.max_preview_bytes()?;
    let trust = trust::TrustState::from_cli(&cli);
    server::print_banner(&cli, &root, max_preview, trust);
    // P1-3/P1-5: bind the listener and wire routes next.
    Ok(())
}
