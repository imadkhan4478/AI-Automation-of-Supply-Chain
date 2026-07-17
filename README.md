# Supply Chain Intelligence — Frontend

Enterprise Streamlit frontend for the AI Supply Chain project. Executive-first
dashboard, interactive Plotly charts, styled data tables, navy/gold branding.
Runs on stub (fake) data today; swaps to the real backend with no page changes.

## Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

Office server (reachable by other machines on the LAN):

```bash
streamlit run app.py --server.address 0.0.0.0
```

## Structure

```
app.py                    entry point: navigation + routing only
.streamlit/config.toml    base theme
components/
  theme.py                design tokens — ALL colors/fonts defined once here
  ui.py                   header, KPI cards, badges, styled tables, styles
  charts.py               Plotly chart wrappers (themed, consistent)
pages_logic/              one file per page (UI only, no calculations)
backend/data_access.py    the ONLY data boundary the pages use
stubs/fake_data.py        fake data until the real backend is ready
```

## The rules that keep this maintainable

1. Pages never touch the database or do calculations — they call
   `backend.data_access` functions and display the result.
2. All colors/fonts come from `components/theme.py`. A rebrand = edit one file.
3. All charts go through `components/charts.py` so they stay consistent.
4. To reorder/rename menu items, edit the `PAGES` dict in `app.py`.

## Connecting the real backend later

Change ONLY the function bodies in `backend/data_access.py` to call the real
database/analytics modules instead of the stubs. Keep the same return shapes
(a dict of KPIs, or a DataFrame) and no page code changes. Do it one function
at a time, testing each.
