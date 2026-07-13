//! Sidecar supervisor: spawns and manages the Python FastAPI server.
//!
//! In dev, prefers `uv run` from `../sidecar`. Falls back to `python -m sidecar`.
//! The spawned process is killed when the app exits.

use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::time::{Duration, Instant};

pub struct SidecarHandle {
    pub port: u16,
    child: Child,
}

impl SidecarHandle {
    pub fn is_healthy(&self) -> bool {
        let url = format!("http://127.0.0.1:{}/health", self.port);
        reqwest::blocking::get(&url)
            .map(|r| r.status().is_success())
            .unwrap_or(false)
    }

    pub fn kill(&mut self) {
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}

pub fn spawn_sidecar() -> Result<SidecarHandle, String> {
    let port = pick_port();
    let port_str = port.to_string();
    let runs_dir = home_runs_dir()
        .map(|p| p.to_string_lossy().to_string())
        .unwrap_or_default();

    let mut cmd = build_command(&port_str, &runs_dir)?;
    cmd.stdin(Stdio::null())
        .stdout(Stdio::inherit())
        .stderr(Stdio::inherit());

    let child = cmd
        .spawn()
        .map_err(|e| format!("failed to spawn sidecar: {e}"))?;

    let handle = SidecarHandle { port, child };

    // Wait up to 15s for health
    let start = Instant::now();
    while start.elapsed() < Duration::from_secs(15) {
        if handle.is_healthy() {
            log::info!("sidecar healthy on port {port}");
            return Ok(handle);
        }
        std::thread::sleep(Duration::from_millis(300));
    }
    log::warn!("sidecar did not report healthy within 15s — UI will retry");
    Ok(handle)
}

fn build_command(port: &str, runs_dir: &str) -> Result<Command, String> {
    if let Some(binary) = bundled_sidecar() {
        let mut cmd = Command::new(binary);
        configure_command(&mut cmd, port, runs_dir);
        return Ok(cmd);
    }

    let sidecar_dir = find_sidecar_dir()?;

    // Prefer uv if available
    if let Ok(uv) = which::which("uv") {
        let mut cmd = Command::new(uv);
        cmd.current_dir(&sidecar_dir)
            .arg("run")
            .arg("python")
            .arg("-m")
            .arg("sidecar.__main__");
        configure_command(&mut cmd, port, runs_dir);
        return Ok(cmd);
    }

    // Fallback: python -m sidecar
    let py = which::which("python3")
        .or_else(|_| which::which("python"))
        .map_err(|e| e.to_string())?;
    let mut cmd = Command::new(py);
    cmd.current_dir(&sidecar_dir)
        .arg("-m")
        .arg("sidecar.__main__");
    configure_command(&mut cmd, port, runs_dir);
    Ok(cmd)
}

fn configure_command(cmd: &mut Command, port: &str, runs_dir: &str) {
    cmd.env("OS_SIDECAR_PORT", port);
    cmd.env("OS_SIDECAR_HOST", "127.0.0.1");
    if !runs_dir.is_empty() {
        cmd.env("OS_RUNS_DIR", runs_dir);
    }
}

fn bundled_sidecar() -> Option<PathBuf> {
    let target = match (std::env::consts::OS, std::env::consts::ARCH) {
        ("macos", "aarch64") => "aarch64-apple-darwin",
        ("macos", "x86_64") => "x86_64-apple-darwin",
        ("windows", "x86_64") => "x86_64-pc-windows-msvc.exe",
        ("linux", "x86_64") => "x86_64-unknown-linux-gnu",
        _ => return None,
    };
    let exe = std::env::current_exe().ok()?;
    let app_dir = exe.parent()?;
    let target_binary = app_dir.join(format!("openscience-sidecar-{target}"));
    if target_binary.exists() {
        return Some(target_binary);
    }
    // Tauri strips the target-triple suffix when it copies an external binary
    // into a macOS .app bundle.
    let bundled_binary = app_dir.join("openscience-sidecar");
    bundled_binary.exists().then_some(bundled_binary)
}

fn find_sidecar_dir() -> Result<PathBuf, String> {
    // Try relative to current exe (release build)
    let from_exe = std::env::current_exe()
        .ok()
        .and_then(|p| {
            p.parent()
                .map(|n| n.join("..").join("sidecar").canonicalize().ok())
        })
        .flatten();
    if let Some(p) = from_exe {
        if p.join("pyproject.toml").exists() {
            return Ok(p);
        }
    }

    // Dev: relative to CARGO_MANIFEST_DIR via env, or look for sibling sidecar/
    let candidates = [
        PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("..")
            .join("sidecar")
            .canonicalize()
            .ok(),
        PathBuf::from("../sidecar").canonicalize().ok(),
        PathBuf::from("sidecar").canonicalize().ok(),
    ];
    for c in candidates.into_iter().flatten() {
        if c.join("pyproject.toml").exists() {
            return Ok(c);
        }
    }
    Err("could not locate sidecar/ directory".into())
}

fn home_runs_dir() -> Option<PathBuf> {
    dirs::home_dir().map(|h| h.join(".openscience").join("runs"))
}

fn pick_port() -> u16 {
    // Try fixed port 7100 first (matches the UI default), then a small range,
    // then fall back to an ephemeral port.
    for port in [7100u16, 7101, 7102, 7103, 7104, 7105] {
        if std::net::TcpListener::bind(("127.0.0.1", port)).is_ok() {
            return port;
        }
    }
    std::net::TcpListener::bind("127.0.0.1:0")
        .ok()
        .and_then(|l| l.local_addr().ok())
        .map(|a| a.port())
        .unwrap_or(7100)
}
