import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './i18n'
import './index.css'
import App from './App'
import { isTauriShell } from './lib/window-chrome'

document.documentElement.classList.toggle("tauri-shell", isTauriShell());

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
