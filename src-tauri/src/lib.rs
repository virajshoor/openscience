mod sidecar;

use std::sync::Mutex;
use tauri::Manager;

struct AppState {
    sidecar: Mutex<Option<sidecar::SidecarHandle>>,
}

#[tauri::command]
fn sidecar_port(state: tauri::State<AppState>) -> u16 {
    state
        .sidecar
        .lock()
        .unwrap()
        .as_ref()
        .map(|h| h.port)
        .unwrap_or(0)
}

#[tauri::command]
fn sidecar_health(state: tauri::State<AppState>) -> bool {
    state
        .sidecar
        .lock()
        .unwrap()
        .as_ref()
        .map(|h| h.is_healthy())
        .unwrap_or(false)
}

pub fn run() {
    env_logger::init();

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(AppState {
            sidecar: Mutex::new(None),
        })
        .setup(|app| {
            let handle = sidecar::spawn_sidecar()?;
            let state: tauri::State<AppState> = app.state();
            *state.sidecar.lock().unwrap() = Some(handle);
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                if let Some(state) = window.app_handle().try_state::<AppState>() {
                    if let Some(mut h) = state.sidecar.lock().unwrap().take() {
                        h.kill();
                    }
                }
            }
        })
        .invoke_handler(tauri::generate_handler![sidecar_port, sidecar_health])
        .run(tauri::generate_context!())
        .expect("error while running OpenScience app");
}
