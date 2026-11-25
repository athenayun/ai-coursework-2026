# Multi-Strategy RAG + LINE Broadcast — Streamlit

Converted from the working Tkinter/ONNX/LINE Broadcast app. The existing `rag_engine.py` and `line_messaging.py` are reused unchanged.

## Features
- PDF/DOCX upload, extraction, local multilingual ONNX embeddings
- Eight retrieval strategies: semantic, tfidf, hybrid, rerank, multi_query, compress, parent_child, hyde
- Groq LLM answers, chat history, retrieved source evidence
- CSV/DOCX export
- LINE Broadcast API with 500-character preview and explicit confirmation
- Progress messages for indexing

**Important:** Broadcast sends to **all eligible followers** of your LINE Official Account. This app does **not** receive questions from LINE. No webhook or recipient user ID is used. Broadcasts may consume your LINE monthly message allowance.

## Local setup (macOS)
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
streamlit run app.py
```
The first ONNX model load downloads model files from Hugging Face. No Cohere key or PyTorch needed.

## Upload to GitHub
Create a new repository (recommended: `rag-streamlit-line`) or place this folder under `ai-coursework-2026/streamlit/rag-streamlit-line/`. Commit the files **except** `.streamlit/secrets.toml` and any `.env` file.

```bash
git add .
git commit -m "Add Streamlit RAG with LINE broadcast"
git push
```

## Deploy on Streamlit Community Cloud
1. Open https://share.streamlit.io/ and sign in with GitHub.
2. Choose **Create app** / **Deploy a public app from GitHub**.
3. Select your repo and branch (`main`). If using the monorepo, set **Main file path** to `streamlit/rag-streamlit-line/app.py`.
4. Set secrets in **Advanced settings** (or App settings → Secrets):
   ```toml
   GROQ_API_KEY = "..."
   LINE_CHANNEL_ACCESS_TOKEN = "..."
   ```
5. Deploy. On the page, index a small PDF, ask a question, preview the answer, confirm broadcast.

The app can also accept keys entered into password fields; for a public app, **prefer Streamlit Secrets** and restrict access to the app. Never commit real API tokens.

## Hosting caveats
- ONNX is executed locally on the Streamlit server, not your Mac. Cloud resource limits and model download time may still cause slow indexing or out-of-memory errors. A successful Mac run does not guarantee cloud success.
- The first model download requires internet access and sufficient disk. Model is cached within the running container only as supported by the host.
- Each browser session has its own in-memory document index and chat history; restarts lose state.
- Anyone with access to an unrestricted public app and a configured LINE token could potentially send a broadcast. **Do not deploy with LINE broadcast enabled publicly without authentication/access control.** For public demos, omit the LINE token and use the app only for RAG Q&A, or add authentication before enabling broadcasts. For sensitive use, add full authentication and authorization as well.
- `st.secrets` keys are read at runtime. Configure secrets before running on Cloud.
