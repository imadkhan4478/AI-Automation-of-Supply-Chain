# Project Handoff — AI Supply Chain Intelligence Platform (Frontend)

_A context file so any assistant can pick up this work with full understanding._

## What this project is

An internal **AI Supply Chain Intelligence Platform** for **Qadri Group**, a
manufacturing company. It turns supply-chain data (currently Excel exports,
later a PostgreSQL database) into dashboards, custom reports, analytics, and an
AI assistant. It runs on a **local office server** (no cloud), accessed by staff
over the internal network. Users range from directors to clerks, so the UI must
be simple yet powerful. It will be presented to **top management / C-level**.

## My role

I own the **Streamlit frontend** only. Other teammates own the database
(Muhtasham), analytics/calculations, and the chatbot's AI logic. My job is the
UI shell that everyone's modules plug into.

## The single most important architectural rule

**The frontend never touches the database or performs calculations.** Every page
calls functions in `backend/data_access.py` and just displays what comes back.
Today those functions return **stub (fake) data**; when the real backend is
ready, only the bodies of `backend/data_access.py` change — no page code
changes. This "separation of concerns" is deliberate and must be preserved.

## Tech stack (decided)

- **Streamlit** (single `app.py` + `streamlit-option-menu` sidebar navigation)
- **Plotly** for all charts
- **pandas** for data (DataFrames are the common return shape)
- Later: **PostgreSQL** backend, simple statistical forecasting, and a
  **local LLM via Ollama** for the chatbot (no data leaves the network)
- Kept UI-tool-swappable: engine logic stays separate from the display layer

## Folder structure

```
supply_chain_app/
├── app.py                    entry point: navigation + routing ONLY
├── requirements.txt
├── .streamlit/config.toml    base theme
├── assets/                   qadri_logo.png + qadri_logo_transparent.png
├── components/
│   ├── theme.py              ALL colors/fonts/status meanings (design tokens)
│   ├── ui.py                 header, KPI cards, badges, styled tables,
│   │                         logo/avatar helpers, global CSS + animations
│   └── charts.py             Plotly chart wrappers (themed, consistent)
├── pages_logic/              one file per page (UI only, no calculations)
│   ├── dashboard.py          executive dashboard (KPIs, trend, alerts, charts)
│   ├── purchases.py
│   ├── inventory.py
│   ├── imports.py
│   ├── logistics.py
│   ├── reports.py            custom report builder (column picker + filters +
│   │                         Export CSV/Excel + Create Dashboard + Save buttons)
│   └── assistant.py          "QadriBot" branded chat UI
├── backend/
│   └── data_access.py        THE ONLY data boundary — forwards to stubs today
└── stubs/
    └── fake_data.py          fake data until the real backend is ready
```

## Design system

- **Navy** `#1F2D4E` = structure. **Gold** `#BF9000` = brand accent (sparingly).
- **Red/Amber/Green** used ONLY for status (risk / watch / healthy), never
  decoration.
- Qadri logo shown in the sidebar and used as the QadriBot avatar.
- Subtle enterprise motion: fade-up on load, hover-lift on cards/buttons, depth
  shadows. Streamlit's top "Deploy" header bar is hidden for a clean look.

## What's DONE

- Full running app on stub data: 7 pages, sidebar nav, executive dashboard.
- Enterprise visual pass: Plotly charts, KPI cards with trend arrows, styled
  status-colored tables, navy/gold theme, logo, animations, hidden top bar.
- **QadriBot** assistant: branded header, logo avatar, suggestion chips,
  chat history, "Online" pill. Calls `db.ask_assistant()` (stub reply for now).
- **Reports builder**: pick source, choose any columns, filter on any column
  (value pickers for text, range sliders for numbers), preview, and action
  buttons — Export CSV, Export Excel, **Create Dashboard**, Save Report. The
  dashboard/save buttons capture the report definition into session state; the
  backend will consume it later. (Buttons are wired; backend action is pending.)

## What's PENDING (backend, owned by others)

- Real PostgreSQL data — swap stub bodies in `backend/data_access.py`.
- Real analytics/forecasting behind the same functions.
- Real chatbot: local LLM (Ollama) + question→report mapping behind
  `db.ask_assistant()`. Scoped narrowly: it answers using existing reports and
  shows what it understood — not open-ended free-form AI.
- Real Excel export (currently CSV stand-in) and the Create-Dashboard action.

## How to run

```bash
cd supply_chain_app
pip install -r requirements.txt
streamlit run app.py
# office server: streamlit run app.py --server.address 0.0.0.0
```

## Conventions to keep

- To reorder/rename menu items: edit the `PAGES` dict in `app.py` only.
- All colors/fonts come from `components/theme.py` (rebrand = one file).
- All charts go through `components/charts.py`.
- Pages must never contain SQL or business calculations — call `backend/`.
- Connect the real backend one function at a time, testing each; keep the same
  return shapes (dict of KPIs, or a DataFrame) so pages don't change.

## Database schema note (for cross-team context)

The database uses `BIGSERIAL` surrogate primary keys, original business IDs kept
as separate TEXT columns, `NUMERIC(18,2)` for money and `NUMERIC(14,3)` for
weights. Shared master tables (`items`, `suppliers`, `purchase_order`) are
defined in the imports schema and must be created before stores/purchases.
Item transactions reference `items(item_code)` directly.
