// Desktop entry point for the macOS application.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    openscience_lib::run()
}
