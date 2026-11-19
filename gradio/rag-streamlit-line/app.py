"""Streamlit frontend for local-ONNX RAG + LINE broadcast."""
import hashlib
import os
import tempfile
import time
from pathlib import Path

import streamlit as st
from rag_engine import RAGSession, STRATEGIES, export_csv, export_docx
from line_messaging import prepare_message, send_line_message

st.set_page_config(page_title="RAG + LINE Broadcast", page_icon="📚", layout="wide")
st.title("📚 Multi-Strategy RAG · LINE Broadcast")
st.caption("PDF/DOCX → local ONNX embeddings → retrieval → Groq answers → optional LINE broadcast")

if "rag" not in st.session_state:
    st.session_state.rag = RAGSession()
if "records" not in st.session_state:
    st.session_state.records = []
if "indexed_hash" not in st.session_state:
    st.session_state.indexed_hash = None
if "index_status" not in st.session_state:
    st.session_state.index_status = "No document indexed"
if "logs" not in st.session_state:
    st.session_state.logs = []
if "last_answer" not in st.session_state:
    st.session_state.last_answer = ""

def secret_or_env(name):
    try:
        return st.secrets.get(name, os.environ.get(name, ""))
    except Exception:
        return os.environ.get(name, "")

rag = st.session_state.rag

with st.sidebar:
    st.header("Configuration")
    default_groq = secret_or_env("GROQ_API_KEY")
    groq_key = st.text_input("Groq API key", type="password", value=default_groq,
                             help="Use Streamlit Secrets for deployed apps; never commit keys to GitHub.")
    rag.groq_key = groq_key.strip()
    if st.button("Fetch Groq models", disabled=not rag.groq_key):
        try:
            with st.spinner("Fetching available models..."):
                st.session_state.available_models = rag.models()
            st.success("Model list loaded")
        except Exception as exc:
            st.error(f"Groq connection failed: {exc}")
    models = st.session_state.get("available_models", ["openai/gpt-oss-20b"])
    model = st.selectbox("Groq model", models)
    rag.model = model
    strategy = st.selectbox("Retrieval strategy", STRATEGIES)
    top_k = st.slider("Top-K", 1, 6, 3)
    st.divider()
    st.header("LINE Messaging API")
    default_line = secret_or_env("LINE_CHANNEL_ACCESS_TOKEN")
    line_token = st.text_input("Channel access token", value=default_line, type="password")
    st.caption("Broadcasts to **all eligible followers**, not only the current visitor. No webhook or user ID.")

left, right = st.columns([1, 1.35], gap="large")
with left:
    st.subheader("1 · Index a document")
    uploaded = st.file_uploader("Upload PDF or DOCX (max 3 MB)", type=["pdf", "docx"])
    if uploaded and uploaded.size > 3 * 1024 * 1024:
        st.error("File is larger than 3 MB.")
    elif uploaded:
        digest = hashlib.sha256(uploaded.getvalue()).hexdigest()
        if digest == st.session_state.indexed_hash:
            st.success("This document is already indexed in your session.")
        elif st.session_state.indexed_hash:
            st.warning("New document selected. Click Index document to replace the existing index.")
    if st.button("Index document", type="primary", disabled=not uploaded or uploaded.size > 3 * 1024 * 1024):
        st.session_state.logs = []
        progress = st.empty()
        def report(message):
            st.session_state.logs.append(message)
            progress.info(message)
        suffix = Path(uploaded.name).suffix.lower()
        path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
                f.write(uploaded.getvalue())
                path = f.name
            start = time.perf_counter()
            result = rag.load(path, uploaded.name, progress=report)
            st.session_state.index_status = result
            st.session_state.indexed_hash = hashlib.sha256(uploaded.getvalue()).hexdigest()
            st.session_state.records = []
            st.session_state.last_answer = ""
            st.success(f"Indexed successfully in {time.perf_counter()-start:.1f}s")
        except Exception as exc:
            st.error(f"Indexing failed: {exc}")
        finally:
            if path:
                Path(path).unlink(missing_ok=True)
    st.info(st.session_state.index_status)
    with st.expander("Indexing activity log", expanded=False):
        st.code("\n".join(st.session_state.logs) or "No indexing activity yet")

    st.subheader("3 · Export results")
    if st.session_state.records:
        st.download_button("Download CSV", export_csv(st.session_state.records),
                           file_name="rag_chat.csv", mime="text/csv")
        st.download_button("Download DOCX", export_docx(st.session_state.records),
                           file_name="rag_chat.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    else:
        st.caption("Ask a question first to enable exports.")

    st.subheader("4 · Broadcast to LINE")
    if st.session_state.last_answer:
        preview = prepare_message(st.session_state.last_answer)
        st.text_area("Broadcast preview (maximum 500 characters)", value=preview, height=140, disabled=True)
        acknowledge = st.checkbox("I understand this message will go to ALL eligible LINE followers.")
        if st.button("Broadcast last answer", disabled=not acknowledge or not line_token):
            try:
                with st.spinner("Sending broadcast request..."):
                    outcome = send_line_message(preview, line_token)
                st.success(outcome)
            except Exception as exc:
                st.error(f"Broadcast failed: {exc}")
    else:
        st.caption("Generate an answer to enable broadcasting.")

with right:
    st.subheader("2 · Document Q&A")
    for record in st.session_state.records:
        with st.chat_message("user"):
            st.write(record["question"])
        with st.chat_message("assistant"):
            st.write(record["answer"])
            with st.expander("Sources"):
                for source in record["sources"]:
                    st.markdown(f"**[{source['id']}] {source['location']}**")
                    st.write(source["text"])
    question = st.chat_input("Ask a question about the indexed document")
    if question:
        if not rag.chunks:
            st.warning("Index a document before asking questions.")
        elif not rag.groq_key:
            st.warning("Enter a Groq API key first.")
        else:
            try:
                with st.spinner("Retrieving evidence and generating answer..."):
                    answer, sources = rag.answer(question, strategy, top_k, st.session_state.records)
                st.session_state.records.append({"question": question, "answer": answer,
                    "strategy": strategy, "model": model, "sources": sources})
                st.session_state.last_answer = answer
                st.rerun()
            except Exception as exc:
                st.error(f"Question failed: {exc}")
    if st.button("Clear chat"):
        st.session_state.records = []
        st.session_state.last_answer = ""
        st.rerun()

st.divider()
st.caption("Demo limitation: document index and chat are in session memory. Streamlit Cloud may restart or exceed memory during ONNX inference. Never upload confidential documents to a public demo without appropriate access controls.")
