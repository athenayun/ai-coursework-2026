# MOPS Announcement Explorer (macOS thread-safe version)

Uses the exact successful Colab requests/BeautifulSoup parsing logic.
The network request runs in a background Python thread; a thread-safe Queue sends results to the Tk main loop. No Tk calls are made from the worker thread.

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Click Fetch / Refresh, then filter by company code/name or announcement subject. Export visible results as CSV. Double-click a row to open its linked announcement if available.

If a fetch fails, the app displays the exact exception and elapsed time.
