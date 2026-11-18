# Taiwan Open Data Explorer — Gradio + RWD + PWA shell

## Run in Google Colab

```python
!pip -q install -r requirements.txt
!python app.py
```

Or paste/upload `app.py` into Colab and call `demo.launch()` after installing the dependencies. This gives you the responsive Gradio UI. **Colab's embedded iframe/proxy is not a reliable installable-PWA origin.**

## Run locally

```bash
python -m pip install -r requirements.txt
python app.py
```

## Deploy as an installable PWA

Host the entire folder on an HTTPS domain (or use localhost for local PWA testing) and start the FastAPI wrapper:

```bash
uvicorn app:app --host 0.0.0.0 --port 7860
```

The root path serves Gradio; `/manifest.webmanifest`, `/service-worker.js`, icons, and `/offline.html` are served from the same origin. Check browser DevTools > Application for installability. Some browsers have additional install requirements and behavior differs on iOS. A browser may offer Add to Home Screen even without full install prompts.

The service worker caches **only static icons and the offline fallback**, not CSV content, data requests, or Gradio APIs. Fresh CSV retrieval requires connectivity. This is a PWA *shell*, not a fully offline CSV editor.

The original CSV workflow is preserved: requests -> pandas -> missing-value handling -> keyword filter -> preview/download.

Security note: the editable URL triggers server-side HTTP requests. For public deployment, restrict allowed domains and implement rate limits/SSRF defenses. This demo is intended for trusted/local use.
