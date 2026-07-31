# AGENTS.md

This file gives AI coding agents the minimum project context needed to work safely in this repository.

## Repo Shape

- `frontend/`: Vite + React + TypeScript
- `backend/`: FastAPI + SQLite
- `docs/hyperframes/`: HyperFrames compositions, capture assets, and rendered product videos

Do not commit design notes, implementation plans, research notes, or other
agent-generated working documents under `docs/`.

## Run Commands

Frontend:

```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0
```

Backend:

```bash
cd backend
./.venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

Use `backend/.venv` if it exists. Do not assume the system Python is correct.

## Frontend Conventions

- UI stack: React + TypeScript + Tailwind v4 utilities + `shadcn/ui`-style open-code primitives.
- Shared UI primitives live in `frontend/src/components/ui/`.
- Keep the existing AntiTrade visual identity. Do not replace it with stock shadcn styling.
- Theme tokens live in `frontend/src/index.css`.
- Dark theme base is neutral `#181818`, not blue-toned.
- Main toolbar / settings / drawer interactions should feel compact and tool-like, not marketing-site-like.

### Frontend Theme And Typography

- The frontend now uses the shadcn/Tailwind v4 CSS-variable theming approach directly in `frontend/src/index.css`.
- Theme switching is class-based: the app toggles `.dark` on `document.documentElement`. Do not reintroduce `data-theme="dark"`-style theme switching.
- Semantic theme tokens exposed to Tailwind live in the `@theme inline` block in `frontend/src/index.css`.
- Light/dark theme colors should be added through semantic tokens such as `--background`, `--foreground`, `--card`, `--popover`, `--primary`, `--secondary`, `--muted`, `--border`, `--input`, and `--ring`.
- Prefer Tailwind semantic utilities like `bg-popover`, `text-foreground`, `border-border`, `text-muted-foreground`, `bg-primary`, `text-primary-foreground` instead of hardcoded color values in TSX.
- Font sizing is centrally managed in `frontend/src/index.css` through base tokens:
  - `--font-heading`, `--font-subheading`, `--font-body`, `--font-ui`, `--font-caption`, `--font-micro`
- Tailwind text utilities are mapped from those tokens via `@theme inline`:
  - `text-heading`, `text-subheading`, `text-body`, `text-ui`, `text-caption`, `text-micro`
- When editing UI primitives or shared UI, prefer those semantic text classes over `text-[12px]`, `text-[13px]`, etc.
- Default UI icon sizing is also centrally managed in `frontend/src/index.css` with:
  - `--icon-xs`, `--icon-sm`, `--icon-md`, `--icon-lg`
- For default primitive/icon sizing, prefer token-driven sizing such as `size-[var(--icon-sm)]`. Do not expand one-off business icon sizes into the global token system unless the pattern is clearly becoming shared.
- If you need a new shared font or icon size, add it to the token system in `frontend/src/index.css` first rather than scattering new arbitrary pixel values across TSX and CSS.

### Frontend UI Composition Rules

- The current UI direction is compact, tool-like, and shadcn-composed. Prefer `Button`, `Input`, `Select`, `Popover`, `SheetFooter`, `Table`, `ToggleGroup`, `DialogFooter`, and other shared primitives over hand-rolled wrapper shells.
- Keep AntiTrade's visual identity, but do it through composition and token usage rather than page-specific ad hoc button/input implementations.
- Prefer replacing old custom control shells over layering more override classes on top. If a page still has bespoke wrapper components or CSS that duplicate shared primitives, refactor toward the primitive and delete the redundant code.
- Default control text hierarchy should stay consistent:
  - action buttons and form values: `ui`
  - placeholder, helper, secondary metadata: `caption`
  - panel/dialog titles: `subheading`
- Prefer semantic token-driven sizing over arbitrary pixel values. If a control needs a repeated page-specific size choice, centralize it in a nearby `*-ui-config.ts` file rather than scattering literals.
- For compact page actions, the current defaults are:
  - standard page/form buttons: `sm`
  - toolbar icon-only actions: `icon-sm`
  - dense chart/panel icon actions: `icon-xs`
- **All form controls must explicitly set `fontSize: "var(--font-ui)"`** via inline `style` prop. This applies to `Input`, `SelectTrigger`, `ToggleGroupItem`, and `Button`. The shadcn component defaults may render larger than the project's 13px compact sizing. Each page should define `btnStyle` and `inputStyle` objects from its `*-ui-config.ts` and apply them to every form element. Do not rely on Tailwind `text-ui` class alone — use inline `style` to guarantee the font size.
- Dialogs and drawers should prefer clear footer actions over tiny bespoke header icon actions when the workflow has an obvious primary/secondary action pair. `Close` + primary action in the footer is the default pattern unless the interaction is truly lightweight.
- For page-local UI rules, keep small config files close to the page layer instead of creating broad architecture shells. If only one page family uses the config, prefer files like `frontend/src/pages/journal-ui-config.ts` or `frontend/src/pages/market-overview-ui-config.ts`.
- Do not create or keep empty architectural layers such as a `features/` directory that only holds one or two small config files. Add a new layer only when a real feature boundary with multiple files has emerged.

### Frontend State

Persisted local UI state is stored in the browser, not the backend. This includes:

- theme mode and accent color
- language mode
- sidebar collapsed state

Relevant files:

- `frontend/src/state/ui-storage.ts`
- `frontend/src/theme/theme-storage.ts`
- `frontend/src/i18n/i18n-storage.ts`

### i18n

- i18n uses `i18next` + `react-i18next`
- Supported languages: Simplified Chinese and English
- Language setting supports `system`, `zh`, `en`
- TradingView embedded chart locale should stay in sync with app language

Relevant files:

- `frontend/src/i18n/index.ts`
- `frontend/src/i18n/i18n-context.tsx`
- `frontend/src/i18n/messages.ts`

### AI Analysis UI

- The default LLM provider is configurable; `demo` is available for UI testing
- Market analysis is initiated through the AI assistant and its read-only market tools
- The home overview displays deterministic market data and does not invoke an LLM
- Do not expose raw provider/CLI errors directly to users

Relevant files:

- `frontend/src/pages/AssistantPage.tsx`
- `frontend/src/pages/MarketOverviewPage.tsx`
- `backend/providers/demo_provider.py`
- `backend/services/market_research.py`

## Backend Conventions

- FastAPI app entry: `backend/main.py`
- Single router: `backend/routers/analyze.py` (3 endpoints under `/api/analyze`)
- Single service: `backend/services/analyzer.py` (OHLCV fetch via tvdatafeed, TA-Lib indicators, LLM analysis)
- Backend i18n: `backend/i18n.py` (centralized translations, language from Accept-Language header)
- Analysis jobs and cache are in-memory (not persisted to DB)
- Shared API response contract is:

```json
{
  "code": 0,
  "data": {},
  "message": "ok"
}
```

- `code === 0` means success
- Frontend API helpers unwrap this format in `frontend/src/api/client.ts`
- On failures, prefer returning a useful `message`, but frontend still normalizes unknown errors to generic user-facing copy

Relevant files:

- `backend/api_response.py`
- `backend/models.py`
- `frontend/src/api/client.ts`

## Market Overview Notes

- The home route is a compact cross-asset and US macro overview.
- Twelve Data supplies the quote strip; FRED supplies macro observations.
- Keep dashboard fetches within free-tier limits and display data timestamps.

Relevant files:

- `frontend/src/pages/MarketOverviewPage.tsx`
- `backend/services/market_research.py`
- `backend/routers/market.py`

## Working Style For Agents

- Prefer small, local changes over wide refactors unless explicitly requested
- If touching UI, preserve the current spacing density and neutral dark theme
- If touching API contracts, update both backend response models and frontend client unwrapping together
- Run verification before claiming completion:
  - frontend: `cd frontend && npm run build`
  - backend: `cd backend && ./.venv/bin/python -m py_compile ...`

## Known Non-Goals

- Do not reintroduce a cold-blue dark dashboard look
- Do not switch away from `i18next/react-i18next`
- Do not remove provider configurability just because `demo` is the default
