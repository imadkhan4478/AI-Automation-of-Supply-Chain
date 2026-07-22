"""AI Assistant — branded chat interface ("QadriBot").

The chat UI is ours: a centered "hero search" empty state (Google-homepage
style — big mark, centered pill search bar, a few suggested queries) that turns
into a normal chat with history + a bottom-pinned input once the first message
is sent.

Behind that UI sits the real text-to-SQL engine from `chatbot.agent`: it turns a
natural-language question into a read-only SQL SELECT, runs it, and returns an
answer plus (when asked) a table or chart. It also handles the conversational
niceties — "which item did you mean?", "between which dates?", and follow-ups
like "show that as a bar chart".
"""

import io
import re
import pandas as pd
import plotly.express as px
import streamlit as st

from chatbot.agent import (answer_question, extract_item_query,
                           find_item_candidates, resolve_selections,
                           answer_item_details, detect_date_range_need,
                           parse_date_range, is_pure_format_directive)
from components import ui, theme as T

SUGGESTED = [
    "Which purchase orders are delayed?",
    "Which supplier has the most delays?",
    "Which items are below reorder level?",
    "Show imports pending clearance",
]

# A keyword matching more than this many items is a broad CATEGORY (e.g. "ball
# bearing" = 442 items) → show them ALL as a table instead of a "which one?"
# pick-list. At or below it, it's genuine disambiguation (a few same-named items).
MANY_ITEMS = 8

# Charts trim to this many rows for readability — UNLESS the user names a count in
# their request ("31 rows", "top 50", "40 bars"), which overrides the default.
CHART_ROWS = 30
_CHART_ROWS_RE = re.compile(
    r"\b(\d{1,4})\s+(?:rows?|bars?|points?|slices?|items?|categor\w*|entries|records?)\b"
    r"|\btop\s+(\d{1,4})\b",
    re.I,
)


def detect_chart_rows(question: str, default: int = CHART_ROWS) -> int:
    """Rows to plot in a chart. A count named in the request ("31 rows", "top 50",
    "40 bars") overrides the default; time ranges like "last 7 days" are ignored
    (no row-unit keyword). Returns the default when no count is given."""
    m = _CHART_ROWS_RE.search(question or "")
    if not m:
        return default
    n = int(m.group(1) or m.group(2))
    return n if n >= 1 else default

# The global app style (components/ui.py) sets `overflow:hidden` on every
# st.dataframe so its rounded corners clip the grid — but that also clips away
# the dataframe's hover toolbar (search / hide-columns / fullscreen / download).
# Re-enable that toolbar for the ASSISTANT'S tables ONLY by wrapping them in a
# `.st-key-asst_tbl*` container and overriding overflow just inside it. Other
# pages keep the clipped look.
_ASSISTANT_TABLE_CSS = """
<style>
div[class*="st-key-asst_tbl"] [data-testid="stDataFrame"] { overflow: visible !important; }
div[class*="st-key-asst_tbl"] [data-testid="stDataFrameResizable"],
div[class*="st-key-asst_tbl"] .dvn-scroller { border-radius: 10px; }
</style>
"""


# --------------------------------------------------------------------------
# Rendering helpers
# --------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def to_excel_bytes(df: pd.DataFrame) -> bytes:
    """Serialize a DataFrame to an .xlsx file (openpyxl) for download. Cached so a
    given result is serialized ONCE, not rebuilt for every past table message on
    each Streamlit rerun (which grew laggy as the conversation got longer)."""
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Results")
    return buf.getvalue()


def render_chart(df: pd.DataFrame, chart_type: str, key: str, rows: int = CHART_ROWS):
    """Draw a simple pie/bar/line from the result. x = first categorical column,
    y = first numeric column.Plots the first `rows` rows. Falls back to a table if there's nothing to plot."""
    num_cols = df.select_dtypes(include="number").columns.tolist()
    cat_cols = [c for c in df.columns if c not in num_cols]
    if not num_cols:
        st.info("Nothing numeric to chart — showing the data instead.")
        st.dataframe(df, width="stretch", hide_index=True)
        return
    y = num_cols[0]
    x = cat_cols[0] if cat_cols else df.columns[0]
    d = df.head(rows)
    if chart_type == "pie":
        fig = px.pie(d, names=x, values=y, title=f"{y} by {x}")
    elif chart_type == "line":
        fig = px.line(d, x=x, y=y, markers=True, title=f"{y} by {x}")
    else:
        fig = px.bar(d, x=x, y=y, title=f"{y} by {x}")
    st.plotly_chart(fig, width="stretch", key=f"chart_{key}")
    if len(df) > rows:
        st.caption(f"Showing the first {rows} rows in the chart.")


def _msg_from_result(result: dict, question:str = "") -> dict:
    """Build an assistant message dict from an answer_question() result. `question`
    is used to pick the chart row limit (a count named in the request overrides the 
    CHART_ROWS default)"""
    return {
        "role": "assistant",
        "content": result.get("answer") or "",
        "df": result.get("dataframe"),
        "display": result.get("display", "text"),
        "chart_type": result.get("chart_type"),
        "chart_rows": detect_chart_rows(question)
    }


def render_result(msg: dict, key: str):
    """Render one assistant turn. Text always; table or chart only if asked."""
    if msg.get("content"):
        st.markdown(msg["content"])

    df = msg.get("df")
    display = msg.get("display", "text")
    if not isinstance(df, pd.DataFrame) or df.empty:
        return

    if display == "chart":
        render_chart(df, msg.get("chart_type") or "bar", key, msg.get("chart_rows",CHART_ROWS))
    elif display == "table":
        # Keyed container so the scoped CSS above can un-clip this table's
        # toolbar (search / hide-columns / fullscreen) without touching any
        # other page's tables.
        with st.container(key=f"asst_tbl_{key}"):
            st.dataframe(df, width="stretch", hide_index=True)
            st.download_button(
                "⬇️ Download Excel",
                data=to_excel_bytes(df),
                file_name="query_result.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"dl_{key}",
            )
            st.caption(f"{len(df)} row(s) · click a column header to sort")


# --------------------------------------------------------------------------
# Page
# --------------------------------------------------------------------------
def render():
    ui.assistant_header()
    st.markdown(_ASSISTANT_TABLE_CSS, unsafe_allow_html=True)

    # Conversation + agent state.
    st.session_state.setdefault("chat", [])            # list of message dicts
    st.session_state.setdefault("pending", None)       # {"candidates": df, "question": str}
    st.session_state.setdefault("pending_dates", None) # {"question": str} awaiting a date range
    st.session_state.setdefault("last_turn", None)     # {"question","sql"} of prior turn

    if not st.session_state.chat:
        _render_hero()
    else:
        _render_conversation()


def _render_hero():
    """Centered empty state — the QadriBot equivalent of a search homepage."""
    avatar = ui.qadri_avatar_svg(64)
    left, mid, right = st.columns([1, 2, 1])
    with mid:
        st.write("")
        st.write("")
        ui._html_block(f"""
            <div style="text-align:center;">
                <img src="{avatar}" width="64" height="64"
                     style="border-radius:18px;box-shadow:0 10px 28px rgba(79,70,229,.28);margin-bottom:18px;"/>
                <p style="font-family:{T.DISPLAY_FONT_STACK};font-size:1.9rem;font-weight:800;
                          color:{T.NAVY};margin:0 0 8px 0;letter-spacing:-0.02em;">
                    Ask {ui.ASSISTANT_NAME} anything</p>
                <p style="color:{T.MUTED};font-size:1rem;margin:0 0 26px 0;">
                    Purchases, inventory, imports, or logistics — in plain language.</p>
            </div>
            """)

        with st.container(key="hero_search"):
            with st.form("hero_ask_form", clear_on_submit=True, border=False):
                c1, c2 = st.columns([10, 1])
                with c1:
                    q = st.text_input(
                        "Ask", placeholder="Ask about purchases, inventory, imports, or logistics...",
                        label_visibility="collapsed",
                    )
                with c2:
                    asked = st.form_submit_button("→")
            if asked and q:
                _handle(q)
                st.rerun()

            st.write("")
            chip_cols = st.columns(2)
            for i, sug in enumerate(SUGGESTED):
                if chip_cols[i % 2].button(sug, key=f"sugg_{i}", width="stretch"):
                    _handle(sug)
                    st.rerun()


def _render_conversation():
    avatar = ui.qadri_avatar_svg(36)

    for i, msg in enumerate(st.session_state.chat):
        if msg["role"] == "user":
            with st.chat_message("user"):
                st.markdown(msg["content"])
        else:
            with st.chat_message("assistant", avatar=avatar):
                render_result(msg, key=f"msg_{i}")

    if prompt := st.chat_input(f"Message {ui.ASSISTANT_NAME}..."):
        _handle(prompt)
        st.rerun()

    if st.button("Clear conversation", key="clear_chat"):
        for k in ("chat", "pending", "pending_dates", "last_turn"):
            st.session_state.pop(k, None)
        st.rerun()


# --------------------------------------------------------------------------
# The brain — the full text-to-SQL pipeline from the standalone chatbot,
# adapted to append into st.session_state.chat (the caller reruns after).
# --------------------------------------------------------------------------
def _handle(question):
    st.session_state.chat.append({"role": "user", "content": question})

    pending = st.session_state.pending
    pending_dates = st.session_state.pending_dates
    history = st.session_state.get("last_turn")   # {"question","sql"} of prior turn
    result = None
    asked_question = question                     # what to remember for follow-ups

    try:
        if pending:                                    # resolving an item clarification
            codes = resolve_selections(question, pending["candidates"])
            asked_question = pending["question"]
            if not codes:
                assistant_msg = {
                    "role": "assistant", "display": "text", "df": None,
                    "content": "I couldn't tell which item(s) you mean — reply with "
                               "the **item code(s)** or **row number(s)** above "
                               "(e.g. `1 and 3`, or `all`), or ask a new question.",
                }
            else:
                st.session_state.pending = None
                with st.spinner("Fetching item details…"):
                    result = answer_item_details(codes, pending["question"],
                                                 history=history)
                assistant_msg = _msg_from_result(result, asked_question)
        elif pending_dates:                            # resolving a date-range question
            st.session_state.pending_dates = None
            asked_question = pending_dates["question"]
            date_range = parse_date_range(question)
            span = ("all dates" if not date_range else
                    f"{date_range[0] or '…'} → {date_range[1] or '…'}")
            with st.spinner(f"Querying the database ({span})…"):
                result = answer_question(asked_question, history=history,
                                         date_range=date_range)
            assistant_msg = _msg_from_result(result, asked_question)
        elif is_pure_format_directive(question) and not (
                history and history.get("sql")):
            # Bare format directive ("show me the table") with no previous
            # result to reformat -> ask instead of running a subject-less query
            # (which would otherwise dump a whole table).
            assistant_msg = {
                "role": "assistant", "display": "text", "df": None,
                "content": "I don't have a previous result to reformat. What data "
                           "would you like to see as a table or chart? For example: "
                           "*“issuances last month”* or *“imports for supplier SQ”*.",
            }
        else:
            intent = extract_item_query(question)      # fresh question
            cands = (find_item_candidates(intent["keyword"])
                     if intent["is_item_detail"] and intent["keyword"] else None)
            date_need = (detect_date_range_need(question)
                         if cands is None or cands.empty else
                         {"needs_range": False})
            if cands is not None and not cands.empty:
                n = len(cands)
                kw = intent["keyword"]
                if n > MANY_ITEMS:
                    # Broad category (e.g. "ball bearing") — show ALL matching
                    # items as a table, no "which one?" step. Each row is a
                    # distinct item_code with its own specs.
                    types = int(cands["item"].nunique())
                    content = (
                        f"Found **{n} items** matching **“{kw}”**"
                        + (f" across **{types} product names**" if types > 1 else "")
                        + " — showing them all below (each row is a distinct "
                        "item code with its specs):"
                    )
                    assistant_msg = {"role": "assistant", "content": content,
                                     "df": cands, "display": "table"}
                else:
                    # A few same-named items — genuine disambiguation, ask which.
                    st.session_state.pending = {"candidates": cands,
                                                "question": question}
                    content = (
                        f"I found **1 item** matching **“{kw}”** — is this the one? "
                        f"Reply **yes** or the item code."
                        if n == 1 else
                        f"I found **{n} items** matching **“{kw}”**. Which one(s)? "
                        f"Reply with the **item code(s)** or **row number(s)** — "
                        f"e.g. `1`, `1 and 3`, or `all`."
                    )
                    assistant_msg = {"role": "assistant", "content": content,
                                     "df": cands, "display": "table"}
            elif date_need.get("needs_range"):
                st.session_state.pending_dates = {"question": question}
                eg = ""
                if date_need.get("default_from") and date_need.get("default_to"):
                    eg = (f" — for example `{date_need['default_from']} to "
                          f"{date_need['default_to']}`")
                content = (
                    "That data covers a time span. **From when to when** should I look?"
                    f"{eg}\n\nReply with a range like `2026-01-01 to 2026-06-30`, a "
                    "phrase like `last 3 months`, or **`all`** for no date limit."
                )
                assistant_msg = {"role": "assistant", "content": content,
                                 "df": None, "display": "text"}
            else:
                with st.spinner("Querying the database…"):
                    result = answer_question(question, history=history)
                assistant_msg = _msg_from_result(result, question)
    except Exception as exc:
        assistant_msg = {
            "role": "assistant", "display": "text", "df": None,
            "content": f"⚠️ Something went wrong: {exc}",
        }

    if result and result.get("sql"):              # remember this turn for follow-ups
        st.session_state.last_turn = {
            "question": asked_question,
            "sql": result["sql"],
        }

    st.session_state.chat.append(assistant_msg)
