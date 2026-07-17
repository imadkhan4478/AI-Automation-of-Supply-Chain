"""AI Assistant — branded chat interface ("QadriBot").

The chat UI is ours. When a message is sent we hand it to the backend
assistant function, which returns what it understood plus an answer and
optional table. Today that's a canned stub reply; the real intelligence
(local LLM + report mapping) connects behind db.ask_assistant() later.
"""

import streamlit as st

from backend import data_access as db
from components import ui

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

    avatar = ui.qadri_avatar_svg(36)

    # --- Empty state: greeting + suggestion chips ---
    if not st.session_state.chat:
        st.markdown(
            f"<p style='color:#5A6478;font-size:0.95rem;margin-bottom:10px;'>"
            f"Hello 👋 I'm <b>{ui.ASSISTANT_NAME}</b>. Ask me about purchases, "
            f"inventory, imports, or logistics — or start with one of these:</p>",
            unsafe_allow_html=True,
        )
        cols = st.columns(2)
        for i, q in enumerate(SUGGESTED):
            if cols[i % 2].button(q, key=f"sugg_{i}", width="stretch"):
                _handle(q)
                st.rerun()

    # --- Conversation history ---
    for turn in st.session_state.chat:
        if turn["role"] == "assistant":
            with st.chat_message("assistant", avatar=avatar):
                st.markdown(turn["content"])
                if turn.get("table") is not None:
                    st.dataframe(turn["table"], width="stretch", hide_index=True)
        else:
            with st.chat_message("user"):
                st.markdown(turn["content"])

    # --- Input ---
    if prompt := st.chat_input(f"Message {ui.ASSISTANT_NAME}..."):
        _handle(prompt)
        st.rerun()

    # --- Clear conversation ---
    if st.session_state.chat:
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
