# CTEE News Explorer (Mac)

CustomTkinter desktop app for the CTEE Financial Highlights and Taiwan Stock Market sections.

## Install and run

Requires macOS, Python 3.10+, and locally installed Google Chrome.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```

The application opens a **visible Chrome window** through Selenium (same approach as the successful local test), visits each selected topic, and extracts `time.news-time`, article links, and `p.news-summary` into a table. ChromeDriver is managed by Selenium Manager when possible.

Select one or both topics. Click **Fetch selected topics**. Optionally enable keyword filtering (comma-separated keywords, Any/All matching), then export the filtered rows as UTF-8-SIG CSV. Double-click a result to open its article in your browser.

## Notes

- Local Selenium worked for Financial Highlights in the user's test. Stock Market has not been independently verified.
- CTEE may restrict automated access at any time. This application does not circumvent challenges or CAPTCHAs.
- The website may change its HTML structure, requiring parser adjustments.
- Fetching occurs in a worker thread; only the main Tkinter thread updates widgets through a queue.
- Keep requests modest and respect website terms.
