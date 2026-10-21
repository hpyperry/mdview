use std::env;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

fn require_asset(path: &Path) {
    let metadata = fs::metadata(path)
        .unwrap_or_else(|error| panic!("web asset {} is missing: {error}", path.display()));
    if !metadata.is_file() {
        panic!("web asset {} is not a file", path.display());
    }
    if metadata.len() == 0 {
        panic!(
            "web asset {} is empty; run `npm --prefix web run build:web` or fix MDVIEW_WEB_PREBUILT",
            path.display()
        );
    }
}

fn main() {
    for path in [
        "web/src",
        "web/build.mjs",
        "web/package.json",
        "web/package-lock.json",
        "web/tsconfig.json",
    ] {
        println!("cargo:rerun-if-changed={path}");
    }
    for name in ["MDVIEW_WEB_OUTDIR", "MDVIEW_WEB_PREBUILT"] {
        println!("cargo:rerun-if-env-changed={name}");
    }

    let out_dir = PathBuf::from(env::var("OUT_DIR").expect("OUT_DIR"));
    let web = PathBuf::from("web");

    if let Ok(prebuilt) = env::var("MDVIEW_WEB_PREBUILT") {
        let prebuilt = PathBuf::from(prebuilt);
        for asset in ["app.js", "app.css"] {
            let source = prebuilt.join(asset);
            require_asset(&source);
            fs::copy(&source, out_dir.join(asset))
                .unwrap_or_else(|error| panic!("copy {}: {error}", source.display()));
        }
        return;
    }

    if !web.join("node_modules").is_dir() {
        panic!("web/node_modules is missing; run `npm ci` in ./web before cargo build");
    }

    let mut command = if cfg!(windows) {
        let mut command = Command::new("cmd");
        command.args(["/C", "npm", "run", "build:web"]);
        command
    } else {
        let mut command = Command::new("npm");
        command.args(["run", "build:web"]);
        command
    };
    let status = command
        .current_dir(&web)
        .env("MDVIEW_WEB_OUTDIR", &out_dir)
        .status()
        .expect("failed to start npm; install Node/npm and run `npm ci` in ./web");
    if !status.success() {
        panic!("`npm run build:web` failed with {status}");
    }
    for asset in ["app.js", "app.css"] {
        require_asset(&out_dir.join(asset));
    }
}
