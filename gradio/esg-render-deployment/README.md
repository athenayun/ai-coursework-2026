# Taiwan Open Data Explorer — Gradio + Responsive PWA (Render)

A Gradio frontend backed by Python requests/pandas. FastAPI serves the Gradio UI plus same-origin PWA manifest, icons, offline fallback and service worker.

## Preview on Mac

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --host 127.0.0.1 --port 7860
```

Open http://127.0.0.1:7860. Chrome DevTools > Toggle device toolbar previews mobile sizes. Inspect Application > Manifest / Service Workers to verify PWA assets.

## Deploy on Render

1. Push this folder's contents to a GitHub repository (render.yaml at repo root).
2. In Render, choose **New > Blueprint**, connect the repository and approve the service in render.yaml. Alternatively, create a **Web Service** with Python runtime, build command `pip install -r requirements.txt`, start command `uvicorn app:app --host 0.0.0.0 --port $PORT`.
3. Wait for deploy; open the Render HTTPS URL.
4. Verify `/manifest.webmanifest`, `/service-worker.js`, and `/icon-192.png` all load. Inspect browser DevTools > Application. Browser support and installation criteria vary.

## Colab

Use the original Colab version with `%run app.py` for notebook preview. This Render version is intended to be run by Uvicorn. The hosted interface uses the same Gradio components.

## Notes

- The PWA provides a cached offline **fallback page**, not offline CSV retrieval or offline Gradio processing.
- The external CSV host may deny requests from Render's server IP, even when it works locally. Test the download after deployment.
- Free-tier availability, sleep policies, and pricing depend on Render's current offerings.
- Avoid exposing an unrestricted arbitrary-URL downloader to untrusted users on a public site. For production, add an allowlist of approved CSV hosts, request-size/time limits and rate limiting.
