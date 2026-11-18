# Multi-Strategy RAG — Render Free ONNX experiment

No Cohere key. Uses a local multilingual SentenceTransformer ONNX model (Xenova/paraphrase-multilingual-MiniLM-L12-v2), Groq for text generation, and a lightweight in-memory index. Preserves eight retrieval strategies, Gradio chat history, PDF/DOCX upload, and CSV/DOCX export.

## Deploy to your existing Render service

1. Replace the files inside `ai-coursework-2026/gradio/rag-gradio-render-app/` with this folder's contents, and commit/push to `main`.
2. Render: existing Web Service → Settings: Language **Docker**, Root Directory **`gradio/rag-gradio-render-app`**, Free plan. The Dockerfile downloads the ONNX model during the image build.
3. Render: Manual Deploy → Deploy latest commit, unless auto-deploy starts.
4. Wait for `Live`. Open the Gradio URL, enter your Groq API key, connect, upload a small PDF/DOCX, and ask a question.

No Cohere key, environment variable, or remote embedding quota is needed. `GROQ_API_KEY` is optional: you can enter it through the UI. Do not publish API keys in GitHub.

## Local test

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

## Memory caveat

This is an **experiment**, not a guarantee of fitting 512 MiB. ONNX Runtime, tokenizer, model weights, Gradio, and dependencies still consume memory. Model is loaded on first document indexing, so initial HTTP startup may succeed even if indexing later exceeds the limit. The embedding model is downloaded once (at Docker build time). The fallback `onnx/model.onnx` is unquantized and may exceed Free RAM; if the Docker build selects that file, do not assume this version will fit.

## Known limitations

- This app uses a small in-memory cosine vector index, not ChromaDB. Indexed documents and chat records are temporary and disappear on restart/spin-down.
- Only selectable-text PDFs are supported (no OCR).
- Multi-query, HyDE, compression, and rerank use extra Groq requests and count against Groq rate limits.
- No user authentication; do not use sensitive documents or a shared server-side API key on a public site.
- Character-limited prompts are not a precise model-token budget; context length errors can still occur.
- No full production security, durability, or end-to-end validation has been performed.
