# main.py
# -----------------------------------------------------------------------------
# Streamlit web app for the E-commerce chatbot.
#   - The shoe-store screenshot is shown as the FULL, uncovered background.
#   - The chatbot is a floating widget in the bottom-right corner — a round
#     🤖 button (FAB) that expands into a chat window directly ABOVE it and
#     collapses back down, exactly like Intercom / Tidio / Drift widgets.
#   - IMPORTANT: the FAB and the chat window live inside ONE shared fixed
#     container (`chat_widget`), stacked vertically. This guarantees they're
#     always anchored to the exact same corner — no risk of the button and
#     the panel drifting to different sides.
#   - Bot messages use a 🤖 avatar, user messages use a 🙋 avatar.
#   - All backend logic (routing, FAQ, SQL, small-talk) is unchanged from the
#     original main.py — only the presentation layer has been restyled.
#
# NOTE: this relies on `st.container(key=...)` generating a stable CSS class
# (`.st-key-<key>`) to target with custom positioning — available in
# Streamlit >= 1.32. If you're on an older version, run `pip install -U streamlit`.
#
# NOTE (input row): the message input is a PLAIN st.text_input + st.button —
# intentionally NOT wrapped in st.form. Forms submit on Enter by default;
# using plain widgets means Enter just commits the text (harmless rerun),
# while sending only happens when the ➤ button is clicked.
# -----------------------------------------------------------------------------

import base64
from pathlib import Path

import streamlit as st
from faq import ingest_faq_data, faq_chain
from sql import sql_chain
from smalltalk import talk
from router import router

# -----------------------------------------------------------------------------
# Page config — must be the first Streamlit call.
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Solely Feminine · Shopping Assistant",
    page_icon="👠",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# -----------------------------------------------------------------------------
# Ingest FAQ data once at startup (guarded against duplicate ingestion inside
# ingest_faq_data itself, so re-running this script is safe).
# -----------------------------------------------------------------------------
faqs_path = Path(__file__).parent / "resources/faq_data.csv"
ingest_faq_data(faqs_path)


def ask(query):
    """Traffic controller: route the question, then delegate to the right chain."""
    route = router(query).name

    if route == "faq":
        return faq_chain(query)
    elif route == "sql":
        return sql_chain(query)
    elif route == "small-talk":
        return talk(query)
    else:
        return f"Route {route} not implemented yet"


# -----------------------------------------------------------------------------
# Background image (the site screenshot) — shown at full clarity, no tint.
# -----------------------------------------------------------------------------
def get_base64(path: Path) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


bg_path = Path(__file__).parent / "resources/background.png"
bg_base64 = get_base64(bg_path)

# -----------------------------------------------------------------------------
# Palette pulled from the screenshot itself:
#   deep teal   #0F3D38   (widget header / FAB)
#   cream       #F6EFE4   (chat window body)
#   dusty pink  #D98A94   (user bubble)
#   gold        #C9A961   (accents / borders)
# -----------------------------------------------------------------------------
st.markdown(
    f"""
    <style>
        /* ---- Full, uncovered background image ---- */
        .stApp {{
            background-image: url("data:image/png;base64,{bg_base64}");
            background-size: cover;
            background-position: center top;
            background-attachment: fixed;
        }}

        /* Hide the default (unused) Streamlit sidebar entirely */
        section[data-testid="stSidebar"],
        button[data-testid="stSidebarCollapsedControl"] {{
            display: none !important;
        }}

        /* ---- Hero text card ---- */
        .hero-card {{
            background: rgba(246, 239, 228, 0.88);
            border-left: 5px solid #C9A961;
            border-radius: 10px;
            padding: 1rem 1.4rem;
            max-width: 560px;
            margin-bottom: 1rem;
        }}
        .hero-title {{
            font-family: 'Georgia', serif;
            color: #0F3D38;
            font-size: 2.2rem;
            font-weight: 700;
            margin-bottom: 0.2rem;
        }}
        .hero-subtitle {{
            color: #4a3d33;
            font-size: 1rem;
            margin: 0;
        }}

        /* =========================================================
           FLOATING CHAT WIDGET
           One shared fixed container holds BOTH the chat panel and
           the toggle button, stacked vertically, right-aligned.
           This is what keeps them locked to the same corner.
           ========================================================= */
        div.st-key-chat_widget {{
            position: fixed;
            bottom: 24px;
            right: 28px;
            z-index: 9999;
            display: flex;
            flex-direction: column;
            align-items: flex-end;
            gap: 14px;
        }}

        /* ---- The chat window card ---- */
        div.st-key-chat_panel {{
            width: 440px;
            max-height: 680px;
            background: #F6EFE4;
            border: 2px solid #C9A961;
            border-radius: 18px;
            box-shadow: 0 10px 34px rgba(0,0,0,0.4);
            overflow: hidden;
            display: flex;
            flex-direction: column;
        }}

        .chat-header {{
            background: #0F3D38;
            padding: 0.9rem 1.2rem;
            display: flex;
            align-items: center;
            gap: 0.6rem;
            border-bottom: 2px solid #C9A961;
        }}
        .chat-header-title {{
            font-family: 'Georgia', serif;
            font-size: 1.2rem;
            font-weight: 700;
            color: #F6EFE4;
            margin: 0;
        }}
        .chat-header-sub {{
            font-size: 0.8rem;
            color: #D98A94;
            margin: 0;
        }}

        /* Scrollable message history */
        div.st-key-chat_messages {{
            overflow-y: auto;
            max-height: 480px;
            padding: 1rem 1.1rem 0.4rem 1.1rem;
        }}
        div.st-key-chat_messages div[data-testid="stChatMessage"] {{
            border-radius: 14px;
            padding: 0.4rem 0.6rem;
            margin-bottom: 0.5rem;
            font-size: 1.02rem;
        }}
        div.st-key-chat_messages div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) {{
            background-color: rgba(217, 138, 148, 0.28);
        }}
        div.st-key-chat_messages div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarAssistant"]) {{
            background-color: rgba(201, 169, 97, 0.22);
        }}

        /* Input row pinned to the bottom of the chat window */
        div.st-key-chat_input_row {{
            padding: 0.75rem 1rem 1rem 1rem;
            border-top: 1px solid #C9A961;
            background: #F6EFE4;
        }}
        div.st-key-chat_input_row input {{
            border-radius: 22px !important;
            padding: 0.6rem 1rem !important;
            font-size: 1rem !important;
        }}
        div.st-key-chat_input_row button {{
            border-radius: 50% !important;
            background: #0F3D38 !important;
            color: #F6EFE4 !important;
            border: none !important;
            width: 42px;
            height: 42px;
        }}

        /* ---- The round toggle button (FAB) — always sits below the panel ---- */
        div.st-key-chat_fab button {{
            width: 68px;
            height: 68px;
            border-radius: 50%;
            background: #0F3D38;
            border: 2px solid #C9A961;
            font-size: 1.8rem;
            box-shadow: 0 4px 16px rgba(0,0,0,0.35);
            padding: 0;
        }}
        div.st-key-chat_fab button:hover {{
            background: #14514A;
            border-color: #D98A94;
        }}
    </style>
    """,
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# Main page content (the storefront), fully visible in the background.
# -----------------------------------------------------------------------------
st.markdown(
    """
    <div class="hero-card">
        <p class="hero-title">Solely Feminine</p>
        <p class="hero-subtitle">Discover your perfect pair — tap the 🤖 in the
        corner any time to chat with our shopping assistant.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# Session state.
# -----------------------------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state["messages"] = []
if "chat_open" not in st.session_state:
    st.session_state["chat_open"] = False
if "chat_input_value" not in st.session_state:
    st.session_state["chat_input_value"] = ""

# -----------------------------------------------------------------------------
# Single shared floating container: panel (if open) stacked above the FAB.
# Both live in the SAME fixed div, so they can never end up on opposite sides.
# -----------------------------------------------------------------------------
widget = st.container(key="chat_widget")
with widget:
    if st.session_state.chat_open:
        panel = st.container(key="chat_panel")
        with panel:
            st.markdown(
                """
                <div class="chat-header">
                    <div style="font-size: 1.6rem;">🤖</div>
                    <div>
                        <p class="chat-header-title">Shopping Assistant</p>
                        <p class="chat-header-sub">Ask about products, prices & more</p>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # ---- Scrollable message history ----
            messages_container = st.container(key="chat_messages")
            with messages_container:
                for message in st.session_state.messages:
                    avatar = "🤖" if message["role"] == "assistant" else "🙋"
                    with st.chat_message(message["role"], avatar=avatar):
                        st.markdown(message["content"])

            # ---- Input row ----
            # Intentionally plain widgets (NOT st.form): forms submit on
            # Enter by default. With plain widgets, pressing Enter in the
            # text box just commits its value and reruns the script — it
            # does NOT trigger `submitted`, so nothing gets sent unless the
            # ➤ button is actually clicked.
            #
            # NOTE on clearing the box: Streamlit forbids writing to
            # st.session_state["chat_input_value"] after that widget has
            # already been instantiated in the same run. So instead of
            # clearing it right after sending, we set a `clear_input` flag
            # and act on it here, BEFORE the text_input is created on the
            # next run.
            if st.session_state.get("clear_input"):
                st.session_state.chat_input_value = ""
                st.session_state.clear_input = False

            input_row = st.container(key="chat_input_row")
            with input_row:
                cols = st.columns([5, 1])
                with cols[0]:
                    query = st.text_input(
                        "message",
                        placeholder="Write your query",
                        label_visibility="collapsed",
                        key="chat_input_value",
                    )
                with cols[1]:
                    submitted = st.button("➤", key="send_btn")

            if submitted and query:
                st.session_state.messages.append({"role": "user", "content": query})
                response = ask(query)
                st.session_state.messages.append({"role": "assistant", "content": response})
                st.session_state.clear_input = True  # clear the box on next run
                st.rerun()

    # ---- The toggle button — always rendered last, so it sits at the
    # bottom of the shared container, directly under the panel when open.
    fab = st.container(key="chat_fab")
    with fab:
        fab_label = "✕" if st.session_state.chat_open else "💬"
        if st.button(fab_label, key="fab_btn"):
            st.session_state.chat_open = not st.session_state.chat_open
            st.rerun()

# -----------------------------------------------------------------------------
# Known scope limits (Phase 1, per the project notes):
# - No conversation memory is sent to the LLM: each faq_chain/sql_chain call
#   only sees the CURRENT question, not prior turns. The chat window shows
#   full history, but the LLM itself does not yet.
# -----------------------------------------------------------------------------