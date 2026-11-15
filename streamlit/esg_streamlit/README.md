# Taiwan OTC ESG Greenhouse Gas Dashboard

Data source: https://data.gov.tw/dataset/156375
Official CSV: https://mopsfin.twse.com.tw/opendata/t187ap46_O_1.csv

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
streamlit run app.py
```

The app downloads CSV via `requests.get`, reads it with `pandas.read_csv`, offers company/year filters, displays greenhouse-gas emission charts, and exports filtered CSV. SSL certificate verification remains enabled. The app does not drop every row containing a missing value: ESG reporting columns can legitimately be incomplete.
