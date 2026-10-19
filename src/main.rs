use clap::Parser;
use mdview::{cli, server, trust};

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let cli = cli::Cli::parse();
    let root = cli.resolve_root()?;
    let max_preview = cli.max_preview_bytes()?;
    let trust = trust::resolve(&cli, &root)?;
    server::run(cli, root, max_preview, trust).await
}
