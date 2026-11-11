# PChome × MOMO 商品價格比較

Streamlit app combining the PChome search API and MOMO search API to compare keyword-based product price samples.

## Run

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

Enter a keyword and number of pages **per platform** (1–20), then click **開始擷取與比較**. The dashboard shows product data, per-platform summary statistics, line, pie, sunburst and grouped bar charts, plus a CSV download.

## Notes

- Both endpoints are third-party and may change, rate-limit, or reject automated requests. Live API access was not verified during packaging.
- Different platforms may return different products, variants, promotions, and sorting. Comparisons are descriptive, **not matched-SKU price comparisons**.
- Plotly charts display Chinese in the browser; no `!wget` font installation is required.
