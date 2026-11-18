# Multi-Strategy Document RAG

A deployable Gradio document Q&A app: **PDF/DOCX → sentence-aware chunks → multilingual E5 embeddings → ChromaDB + TF-IDF → 8 retrieval strategies → Groq chat LLM**.

## Features

- Eight strategies: semantic, TF-IDF, hybrid (RRF), rerank (LLM batch), multi-query, compression, parent-child, HyDE.
- Chat interface, recent conversation context (last 2 turns), and cited retrieved passages (`[S#]`).
- Export Q&A history to CSV or DOCX, including evidence excerpts.
- Dynamic Groq model list, excluding obvious speech/safety models. **A listed model may still be incompatible**; choose a chat model such as `openai/gpt-oss-20b` if available.
- Per-browser-session document, key and conversation state; no persistent document store.
- Context is conservatively truncated to reduce context-limit errors, **not an exact tokenizer or a guaranteed limit**.

## Run locally

Python 3.11 recommended. For macOS Apple Silicon, SentenceTransformers uses CPU by default in this deployment example.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open `http://localhost:7860`, enter your Groq API key, load a PDF or DOCX, and ask a question. Optionally set `GROQ_API_KEY` in your local environment (do not commit it).

## Deploy on Render (GitHub)

1. Create a **private GitHub repository** and commit these files. Never commit API keys or private documents.
2. In Render choose **New → Blueprint** and connect the repo. Render reads `render.yaml` and builds the Dockerfile.
3. The blueprint uses **Starter** by default. CPU RAM usage and model download can make smaller instances unreliable; check Render's current plans and pricing.
4. Wait for the model to download and the service to become healthy. Open your Render URL.
5. Enter your Groq API key inside the app. Alternatively set a secret `GROQ_API_KEY` in Render environment settings. **Shared server keys are not recommended for a public app**.

Render may restart instances or lose in-memory sessions. Upload the document again after a restart. This is a demo, not durable chat storage.

## Security and limitations

- Sessions are keyed by random browser tokens and expire after ~1 hour of inactivity. This is **not authentication**. Public apps should add access control, rate limiting, quotas, and stronger isolation before accepting untrusted users.
- Documents are parsed on the server; Groq receives retrieved text excerpts and prompts. Do not upload confidential material without reviewing data-processing policies.
- PDF scans require OCR (not included). Word headers, images and embedded objects may not be extracted.
- Citations identify retrieved chunks and page/block labels; they are **not independently verified factual citations**.
- LLM-based strategies cost more and may fail due to model/API limits.
- `gr.File` uploads and exported files may be temporarily stored on disk by Gradio; the in-memory vector store does not mean the platform stores no temporary files.
- The included tests cover utility behavior, not retrieval quality. To evaluate production accuracy, build a labeled query-document dataset and measure Recall@K, MRR, answer faithfulness and latency.

## Project layout

```
app.py              # Gradio UI, per-session state, exports
rag_engine.py       # Extraction, embeddings, indexing, 8 strategies, answer generation
requirements.txt    # Python dependencies
Dockerfile          # Container deployment
render.yaml         # Render Blueprint
.dockerignore
.gitignore
tests/test_helpers.py
```

## Evaluate retrieval quality

Use `evaluate.py` with a document and a JSON list of queries with manually labeled **zero-based chunk IDs**. Run `python evaluate.py document.pdf labels.json` to compare Recall@3, MRR@3 and mean retrieval latency for semantic, TF-IDF, hybrid and parent-child retrieval. Labels must correspond to the chunks created by this code. This is an evaluation harness, not a benchmark result. LLM-assisted strategies are excluded from the offline evaluation because they require an API key.
