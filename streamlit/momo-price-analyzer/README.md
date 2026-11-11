# MOMO Product Price Analyzer

Streamlit app combining MOMO product search scraping and price analysis.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
streamlit run app.py
```

Enter a product keyword and number of pages, then view a data table, average/min/max prices, line chart, pie chart, and sunburst chart. Download the results as CSV.

Plotly displays Chinese labels using the browser's available fonts, so no `!wget` or custom font installation is needed.

MOMO's search API may change or restrict requests; scraping success cannot be guaranteed.
