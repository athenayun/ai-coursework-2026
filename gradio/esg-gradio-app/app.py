"""Gradio CSV explorer with responsive layout and optional PWA hosting via FastAPI."""
import io
import os
import tempfile
from urllib.parse import urlparse

import gradio as gr
import pandas as pd
import requests
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, Response

DEFAULT_URL = "https://mopsfin.twse.com.tw/opendata/t187ap46_O_1.csv"
BASE = os.path.dirname(os.path.abspath(__file__))

CSS = """
.gradio-container {max-width: 1100px !important; margin: 0 auto !important; padding: clamp(12px, 3vw, 32px) !important;}
#app-title {text-align: center; margin-bottom: 1rem;}
#app-title h1 {font-size: clamp(1.5rem, 4vw, 2.4rem); line-height: 1.2;}
#filter-row {gap: 12px;}
#results-table {overflow-x: auto;}
#results-table .table-wrap {overflow-x: auto;}
@media (max-width: 700px) {
  #filter-row {flex-direction: column !important;}
  #filter-row > * {width: 100% !important; min-width: 0 !important;}
  .gradio-container {padding: 12px !important;}
  button {min-height: 44px;}
}
"""

# Register service worker only on the hosted root-origin PWA.
# Gradio's Colab iframe/proxy may not support PWA installation.
HEAD = """
<link rel="manifest" href="/manifest.webmanifest">
<meta name="theme-color" content="#173f5f">
<meta name="viewport" content="width=device-width, initial-scale=1">
<script>
if ('serviceWorker' in navigator && window.location.pathname === '/') {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/service-worker.js', {scope: '/'})
      .catch(err => console.info('PWA registration unavailable:', err));
  });
}
</script>
"""


def load_csv(url, missing, keyword, max_rows):
    url = (url or "").strip()
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise gr.Error("Enter a valid HTTP or HTTPS CSV URL.")
    try:
        with requests.get(url, timeout=(10, 35), headers={"User-Agent": "Mozilla/5.0"}, stream=True) as response:
            response.raise_for_status()
            content = bytearray()
            for chunk in response.iter_content(chunk_size=65536):
                content.extend(chunk)
                if len(content) > 25 * 1024 * 1024:
                    raise gr.Error("The downloaded CSV exceeds 25 MB.")
        df = pd.read_csv(io.BytesIO(content), encoding="utf-8-sig", dtype=str)
    except requests.RequestException as exc:
        raise gr.Error(f"Download failed: {exc}") from exc
    except (UnicodeError, pd.errors.ParserError, ValueError, pd.errors.EmptyDataError) as exc:
        raise gr.Error(f"CSV parsing failed: {exc}") from exc

    original_count = len(df)
    if missing == "Drop rows with any missing values":
        df = df.dropna()
    elif missing == "Drop entirely empty rows":
        df = df.dropna(how="all")
    keyword = (keyword or "").strip()
    if keyword:
        mask = df.fillna("").apply(lambda col: col.str.contains(keyword, case=False, regex=False)).any(axis=1)
        df = df.loc[mask]
    df = df.reset_index(drop=True)
    path = os.path.join(tempfile.mkdtemp(prefix="gradio_csv_"), "filtered_data.csv")
    df.to_csv(path, index=False, encoding="utf-8-sig")
    summary = f"Downloaded {original_count:,} rows; {len(df):,} remain. Columns: {len(df.columns)}."
    return df.head(int(max_rows)), summary, path


with gr.Blocks(title="Taiwan Open Data Explorer", css=CSS, head=HEAD) as demo:
    gr.Markdown("# Taiwan Open Data Explorer\nResponsive CSV downloader, cleaner, and viewer.", elem_id="app-title")
    url = gr.Textbox(label="CSV URL", value=DEFAULT_URL)
    with gr.Row(elem_id="filter-row"):
        missing = gr.Dropdown(
            choices=["Keep missing values", "Drop entirely empty rows", "Drop rows with any missing values"],
            value="Drop entirely empty rows", label="Missing-value handling"
        )
        keyword = gr.Textbox(label="Keyword (optional)", placeholder="Company name or code")
        max_rows = gr.Slider(10, 500, value=50, step=10, label="Preview rows")
    run = gr.Button("Fetch and process CSV", variant="primary")
    summary = gr.Textbox(label="Result", interactive=False)
    preview = gr.Dataframe(label="Data preview (scroll horizontally on mobile)", interactive=False, elem_id="results-table")
    download = gr.File(label="Download filtered CSV")
    run.click(load_csv, inputs=[url, missing, keyword, max_rows], outputs=[preview, summary, download])

# Hosted mode: serve manifest, SW, and Gradio on the SAME origin.
web_app = FastAPI()

@web_app.get("/manifest.webmanifest", include_in_schema=False)
def manifest():
    return JSONResponse({
        "name": "Taiwan Open Data Explorer", "short_name": "Open Data",
        "start_url": "/", "scope": "/", "display": "standalone",
        "background_color": "#ffffff", "theme_color": "#173f5f",
        "icons": [
            {"src": "/icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png"}
        ]
    }, media_type="application/manifest+json")

@web_app.get("/service-worker.js", include_in_schema=False)
def service_worker():
    return FileResponse(os.path.join(BASE, "static", "service-worker.js"), media_type="application/javascript", headers={"Service-Worker-Allowed": "/", "Cache-Control": "no-cache"})

@web_app.get("/offline.html", include_in_schema=False)
def offline():
    return FileResponse(os.path.join(BASE, "static", "offline.html"), media_type="text/html")

@web_app.get("/icon-{size}.png", include_in_schema=False)
def icon(size: int):
    if size not in (192, 512):
        return Response(status_code=404)
    return FileResponse(os.path.join(BASE, "static", f"icon-{size}.png"), media_type="image/png")

app = gr.mount_gradio_app(web_app, demo, path="/")

if __name__ == "__main__":
    # Colab-friendly mode: responsive Gradio; full PWA requires HTTPS hosting below.
    demo.launch(share=False, debug=True)
