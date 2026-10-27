//! mdview library surface.
//!
//! The binary is a thin wrapper; modules are public so integration tests can
//! exercise the renderer and server without going through the process boundary.

pub mod archive;
pub mod assets;
pub mod cli;
pub mod encoding;
pub mod render;
pub mod server;
pub mod trust;
