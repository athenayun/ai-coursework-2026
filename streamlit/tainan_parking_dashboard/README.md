# Tainan Public Parking Dashboard | 臺南市公有收費停車場

A bilingual Streamlit dashboard for the Taiwan Government Open Data dataset [102773](https://data.gov.tw/dataset/102773).

## Run locally

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

Features: `requests.get()` CSV download, sidebar search and filtering, capacity summary, bar/pie/sunburst charts, ranking, column explorer, and CSV export.

**Data source:** Tainan City Government Transportation Bureau. The app's default CSV URL is taken from the government's dataset page. If the provider changes the download URL, paste the updated CSV link in the sidebar. Live data availability has not been verified.
