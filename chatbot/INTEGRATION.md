# Integrating the Supply-Chain Chatbot

A self-contained **text-to-SQL agent**: give it a natural-language question, it
generates a read-only PostgreSQL `SELECT`, runs it, and returns the answer + the
result DataFrame. Built with LangGraph + an OpenAI chat model.

> **The one thing to know up front:** the engine is reusable, but its "brain" —
> the big system prompt in `agent.py` (`_SQL_SYSTEM`) — is **hand-tailored to this
> project's database schema** (imports, stock, issuance, exports, etc.). It only
> produces correct SQL against a database with the **same schema**. Point it at the
> same DB → works as-is. Different schema → you must rewrite `_SQL_SYSTEM` (see
> [Using a different database](#using-a-different-database)).

---

## 1. What to copy

| File | Required? | Purpose |
|------|-----------|---------|
| `chatbot/agent.py` | **Yes** | The entire engine. Self-contained — imports only third-party libs, nothing from the rest of this project. |
| `chatbot/__init__.py` | Yes* | Makes `from chatbot.agent import …` work as a package. (*Or drop `agent.py` in standalone and `from agent import …`.) |
| `pages/chatbot.py` | Optional | The Streamlit chat UI (chat box, table/chart rendering, Excel download). Skip it if your app has its own UI. |

`agent.py` opens its **own** database connection from environment variables — it
does **not** depend on any other module in this repo.

---

## 2. Dependencies

Core engine:

```bash
pip install pandas sqlalchemy psycopg2-binary python-dotenv \
            langchain langchain-core langchain-community langchain-openai langgraph
```

Only if you also use the Streamlit UI (`pages/chatbot.py`):

```bash
pip install streamlit plotly openpyxl
```

---

## 3. Configuration (environment variables)

Set these in the host process (or a `.env` file — `agent.py` calls `load_dotenv()`):

```dotenv
# OpenAI (or any OpenAI-compatible endpoint)
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini          # the chat model to use for every LLM call

# PostgreSQL connection
PGHOST=localhost
PGPORT=5432
PGDATABASE=supply_chain_db
PGUSER=postgres
PGPASSWORD=your_password
```

- **One model, everywhere.** Every LLM step (SQL generation, summarization, and the
  intent/date helpers) uses the single model named in `OPENAI_MODEL`. Change it in
  one place to swap models.
- If `OPENAI_MODEL` is unset it falls back to `gpt-4o-mini` (`DEFAULT_MODEL`).

---

## 4. Minimal usage (headless — no Streamlit)

```python
from chatbot.agent import answer_question

result = answer_question("how many items are out of stock")

print(result["answer"])     # -> "There are 1,407 items out of stock."
print(result["sql"])        # -> the generated SELECT
df = result["dataframe"]    # -> pandas.DataFrame | None (the raw rows)
```

`answer_question(...)` returns a dict:

| key | type | notes |
|-----|------|-------|
| `answer` | `str` | plain-English answer |
| `dataframe` | `pandas.DataFrame \| None` | the query result rows |
| `sql` | `str` | the SQL that was run |
| `error` | `str \| None` | set if the query failed after retries |
| `display` | `"text" \| "table" \| "chart"` | what the question implied |
| `chart_type` | `"bar" \| "line" \| "pie" \| None` | when `display == "chart"` |

### Follow-up questions

To let "show as a table" / "sort by X" reuse the previous query, pass the prior
turn back in:

```python
r1 = answer_question("which imports are overdue?")
r2 = answer_question("show me the table",
                     history={"question": "which imports are overdue?", "sql": r1["sql"]})
```

---

## 5. Public API

All exported from `chatbot.agent`:

| Function | Purpose |
|----------|---------|
| `answer_question(question, history=None, date_range=None)` | **Main entry point** (see above). |
| `detect_display(question) -> (mode, chart_type)` | Whether the user wants text / table / chart. |
| `detect_date_range_need(question) -> {needs_range, default_from, default_to}` | Should you ask "between which dates?" first. |
| `parse_date_range(reply) -> (from_iso, to_iso) \| None` | Turn a date reply into a window; feed to `answer_question(date_range=…)`. |
| `is_pure_format_directive(question) -> bool` | True for bare "show me the table" / "as a bar chart". |
| `extract_item_query(question) -> {is_item_detail, keyword}` | Detects a single-item question and its keyword. |
| `find_item_candidates(keyword, limit=1000) -> DataFrame` | Items matching a keyword (item_code + specs). |
| `resolve_selections(reply, candidates) -> [item_code, …]` | Maps "1 and 3" / "all" / a code to item_codes. |
| `answer_item_details(item_codes, original_question, history=None)` | Runs the pipeline pinned to specific item_codes. |

The item / date helpers are **optional** conversational niceties (the Streamlit UI
uses them for "which item did you mean?" and "which dates?"). For a plain
question→answer integration you only need `answer_question`.

---

## 6. Using the Streamlit UI

If you copy `pages/chatbot.py`, run it as a Streamlit page/app:

```bash
streamlit run pages/chatbot.py
```

It wires up the chat loop, item-disambiguation prompt, date-range prompt,
follow-up handling, and table/chart rendering with an Excel download. It imports
only from `chatbot.agent` plus `streamlit`, `pandas`, `plotly`, `io` (and
`openpyxl` at runtime for the `.xlsx` export).

---

## 7. Using a different database

Two things are DB-specific:

1. **The connection** — set the `PG*` env vars to the target database. (The engine
   is built in `get_db_uri()` / `get_engine()` in `agent.py`.)
2. **The system prompt** — `_SQL_SYSTEM` in `agent.py` encodes this project's
   tables, columns, value vocabularies, and business rules (status values,
   per-branch reorder logic, out-of-stock definition, aliases, etc.). For a
   different schema you **must** rewrite it to describe the new tables/columns and
   their quirks. The live schema is injected automatically via `get_schema()`
   (`{schema}` placeholder), but the prose rules around it are yours to adapt.

Everything else (SQL safety checks, retry loop, grounded summarization, display
detection) is schema-agnostic and works unchanged.

---

## 8. How it works (one-paragraph tour)

`answer_question` runs a small LangGraph:
`generate_sql → execute_sql → (retry on error, up to 3×) → summarize`.
`generate_sql` asks the model for one read-only `SELECT` using the live schema +
`_SQL_SYSTEM`. `execute_sql` runs it read-only (rejecting anything that isn't a
`SELECT`/`WITH`). `summarize` writes a short answer **grounded in exact
DB-computed facts** (row counts, per-column coverage, per-group totals) so it can't
invent numbers — and it's skipped entirely for table/chart results (which show the
data directly), saving a model round-trip.
