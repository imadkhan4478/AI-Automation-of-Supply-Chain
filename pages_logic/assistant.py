"""AI Assistant — branded chat interface ("QadriBot").

The chat UI is ours. When a message is sent we hand it to the backend
assistant function, which returns what it understood plus an answer and
optional table. Today that's a canned stub reply; the real intelligence
(local LLM + report mapping) connects behind db.ask_assistant() later.

Empty state is a centered "hero search" (Google-homepage style: big mark,
centered pill search bar) rather than a top-anchored chat box with nothing
in it. Once the first message is sent, it becomes a normal chat with
history + a bottom-pinned input -- like a search homepage turning into a
results page after the first query.
"""

import streamlit as st

from backend import data_access as db
from components import ui, theme as T

SUGGESTED = [
    "Which purchase orders are delayed?",
    "Which supplier has the most delays?",
    "Which items are below reorder level?",
    "Show imports pending clearance",
]


def render():
    ui.assistant_header()

    if "chat" not in st.session_state:
        st.session_state.chat = []

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

    for turn in st.session_state.chat:
        if turn["role"] == "assistant":
            with st.chat_message("assistant", avatar=avatar):
                st.markdown(turn["content"])
                if turn.get("table") is not None:
                    st.dataframe(turn["table"], width="stretch", hide_index=True)
        else:
            with st.chat_message("user"):
                st.markdown(turn["content"])

    if prompt := st.chat_input(f"Message {ui.ASSISTANT_NAME}..."):
        _handle(prompt)
        st.rerun()

    if st.button("Clear conversation", key="clear_chat"):
        st.session_state.chat = []
        st.rerun()


def _handle(question):
    st.session_state.chat.append({"role": "user", "content": question})
    result = db.ask_assistant(question)
    answer = (
        f"*I understood: {result['understood']}*\n\n{result['answer']}"
    )
    st.session_state.chat.append(
        {"role": "assistant", "content": answer, "table": result.get("table")}
    )
