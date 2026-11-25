# Multi-Strategy RAG — Tkinter for macOS

Desktop version of the **Render Free ONNX** project. Uses the same `rag_engine.py`, eight retrieval strategies, local ONNX multilingual MiniLM embeddings, Groq for chat, PDF/DOCX import, chat history, evidence display, and CSV/DOCX export. No Gradio, Docker, Cohere, or PyTorch.

## macOS setup

Check Tkinter:
```bash
python -m tkinter
```
A small window should appear. If not, use a Python build with Tk support (for example the python.org macOS installer, or your pyenv Python with Tcl/Tk configured).

Create an isolated environment in the extracted folder:
```bash
cd rag-tkinter-mac
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python app_tk.py
```

If you prefer pyenv, select your working Python 3.12 installation before creating the venv.

## Usage
1. Enter Groq key and click **Connect / Fetch Models**.
2. Choose a PDF/DOCX and click **Index Document**. The first indexing run downloads the ONNX model from Hugging Face, so it can take time.
3. Choose strategy, Top-K and Groq model. Ask questions; conversation history appears on the right.
4. Export CSV or DOCX.

## Important limitations
- No OCR for scanned PDFs; only selectable text.
- The original engine caps indexing at 120 parent and 400 child chunks, and limits prompt context by characters rather than tokens.
- Advanced strategies call Groq more often and are subject to Groq quotas.
- This is a local desktop application, not a hosted server. Your uploaded document and records stay in memory, while retrieved excerpts are sent to Groq for generation.
- The original ONNX engine and its API integrations have not been fully tested end to end in this environment.
