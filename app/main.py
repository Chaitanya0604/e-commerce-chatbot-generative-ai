# main.py
# -----------------------------------------------------------------------------
# This is the file you actually RUN. It is the Streamlit web app — the
# chat-style screen the user types into. Every other file (faq.py, router.py,
# sql.py) is a back-end helper; this file is the "front door" that ties all
# of them together into one working chatbot.
#
# Big picture flow:
#   1. Show a chat-style web page (title + text box) using Streamlit.
#   2. Before the page even loads, ingest the FAQ CSV into ChromaDB once.
#   3. On every user question, ask the semantic router whether it's an
#      'faq' question or a 'sql' (product/pricing) question.
#   4. Call the matching chain (faq_chain or sql_chain) and display the
#      answer, while keeping the full conversation visible on screen.
# -----------------------------------------------------------------------------

import streamlit as st                      # Turns this plain script into an interactive web app (no HTML/CSS/JS needed). Alias 'st' so we can write st.something.
from faq import ingest_faq_data, faq_chain  # ingest_faq_data: loads FAQ CSV into ChromaDB. faq_chain: answers FAQ-style questions via semantic search + LLM.
from sql import sql_chain                   # sql_chain: answers product/pricing questions by generating SQL, running it, and explaining the results.
from smalltalk import talk                 # talk: answers small-talk questions via LLM.
from pathlib import Path                    # Cross-platform way to build file paths (works on Windows, Mac, Linux alike).
from router import router                   # The RouteLayer object built in router.py. Calling router(question) classifies a query as 'faq' or 'sql'.

# -----------------------------------------------------------------------------
# Load the FAQ data into ChromaDB BEFORE the chat window appears.
# This runs once, at startup — not inside ask(), so we don't re-ingest the
# same FAQs every single time the user asks a question (that would be slow
# and pointless). ingest_faq_data() itself also guards against duplicate
# ingestion, so even if this ran more than once it wouldn't corrupt data.
# -----------------------------------------------------------------------------
faqs_path = Path(__file__).parent / "resources/faq_data.csv"  # __file__ = path to this script; .parent = the folder containing it; "/" joins paths safely.
ingest_faq_data(faqs_path)                                    # Reads the CSV, embeds the questions, stores answers as metadata in ChromaDB (skips if already done).


def ask(query):
    """
    The 'traffic controller' of the app. Every question the user types
    eventually passes through here. It asks the router which path to take,
    then delegates to the matching chain function.
    """
    route = router(query).name   # Classify the question by meaning -> 'faq', 'sql', or None if it doesn't clearly match either.

    if route == 'faq':
        return faq_chain(query)      # FAQ pipeline: semantic search in ChromaDB -> build context -> LLM generates a clean answer.
    elif route == 'sql':
        return sql_chain(query)      # SQL pipeline: LLM generates SQL -> runs on SQLite -> LLM turns results into a natural-language answer.
    elif route == 'small-talk':
        return talk(query)           # Small-talk pipeline: LLM generates a friendly response to casual conversation.
    else:
        # Safety net / fallback: if the router couldn't confidently match either
        # category (route is often None here), don't crash — return a friendly
        # message that shows exactly what route value we got, useful for debugging.
        return f"Route {route} not implemented yet"


# -----------------------------------------------------------------------------
# Visible page elements.
# -----------------------------------------------------------------------------
st.title("E-commerce Bot ")                       # Renders a large heading at the top of the page. Purely visual.
query = st.chat_input("Write your query")        # Renders a ChatGPT-style input box at the bottom. Returns None until the user types something and hits enter.

# -----------------------------------------------------------------------------
# Session state: Streamlit re-runs this ENTIRE script top to bottom every time
# the user interacts with the page. A normal Python variable would be wiped
# out and recreated empty on every re-run, so we need persistent storage that
# survives across re-runs for this user's session -> st.session_state.
# -----------------------------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state["messages"] = []            # Only runs on the very first load for this user; creates an empty list to hold the full chat history.

# -----------------------------------------------------------------------------
# Redraw the entire conversation on every re-run.
# Nothing Streamlit draws "remembers itself" between re-runs, so we must
# manually loop through saved history and redisplay every message each time.
# -----------------------------------------------------------------------------
for message in st.session_state.messages:
    with st.chat_message(message['role']):       # Opens a styled chat bubble; 'user' shows a person icon, 'assistant' shows a robot icon.
        st.markdown(message['content'])          # Renders the text (markdown allows bold/bullets/etc. if the LLM's answer includes formatting).

# -----------------------------------------------------------------------------
# Handle a new question, if one was submitted on this run.
# query is None until the user types something and presses enter, and None
# is "falsy" in Python, so `if query:` really means "did the user just ask
# something on this run?"
# -----------------------------------------------------------------------------
if query:
    # --- Show and save the user's question -------------------------------
    with st.chat_message("user"):
        st.markdown(query)
    st.session_state.messages.append({"role": "user", "content": query})  # Persist it so the redraw loop above can show it again on future re-runs.

    # --- Generate the answer ----------------------------------------------
    response = ask(query)   # This is where faq.py, router.py, and sql.py all come together: route the question, call the right chain, get the answer text.

    # --- Show and save the assistant's answer ------------------------------
    with st.chat_message("assistant"):
        st.markdown(response)
    st.session_state.messages.append({"role": "assistant", "content": response})  # Persist so it's part of the permanent, redrawable conversation history.

# -----------------------------------------------------------------------------
# Known scope limits (Phase 1, per the project notes):
# - No conversation memory is sent to the LLM: each faq_chain/sql_chain call
#   only sees the CURRENT question, not prior turns. The chat UI shows full
#   history, but the LLM itself does not yet.
# -----------------------------------------------------------------------------