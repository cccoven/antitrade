# App Icon Workflow

`../app-icon.png` is the canonical 1024x1024 source icon.

Files in this directory are generated outputs for Tauri platforms. Do not edit
them directly. Update `../app-icon.png`, then run:

```bash
cd frontend
npm run icons:generate
```

The source icon keeps transparent outer corners and a centered white rounded
tile so macOS Dock rendering stays visually consistent with other app icons.
