fn main() {
    let manifest_dir = std::env::var("CARGO_MANIFEST_DIR").expect("CARGO_MANIFEST_DIR is set");

    for icon in [
        "app-icon.png",
        "icons/32x32.png",
        "icons/64x64.png",
        "icons/128x128.png",
        "icons/128x128@2x.png",
        "icons/icon.png",
        "icons/icon.icns",
        "icons/icon.ico",
    ] {
        println!("cargo:rerun-if-changed={manifest_dir}/{icon}");
    }

    tauri_build::build()
}
