"""Streamlit dashboard for Taiwan OTC company greenhouse-gas disclosures."""
from io import BytesIO
import re

import pandas as pd
import requests
import streamlit as st

DATASET_PAGE = "https://data.gov.tw/dataset/156375"
CSV_URL = "https://mopsfin.twse.com.tw/opendata/t187ap46_O_1.csv"

st.set_page_config(page_title="上櫃公司 ESG 溫室氣體排放", page_icon="🌱", layout="wide")
st.title("🌱 上櫃公司 ESG 溫室氣體排放資料")
st.caption("資料來源：政府資料開放平臺／公開資訊觀測站（櫃買中心）")
st.markdown(f"[資料集說明]({DATASET_PAGE}) · [官方 CSV]({CSV_URL})")

@st.cache_data(ttl=3600, show_spinner=False)
def load_data(url: str) -> pd.DataFrame:
    # Preserve the class exercise: requests.get -> CSV -> pandas.read_csv.
    response = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; EducationalESGDashboard/1.0)",
                 "Accept": "text/csv,*/*"},
        timeout=(10, 40),
    )
    response.raise_for_status()
    payload = response.content
    if not payload:
        raise ValueError("CSV response was empty.")
    # Check for HTML error pages returned with HTTP 200.
    if payload[:500].lstrip().lower().startswith((b"<!doctype html", b"<html")):
        raise ValueError("Server returned HTML instead of CSV. Check the official CSV URL.")
    for encoding in ("utf-8-sig", "utf-8", "cp950", "big5"):
        try:
            frame = pd.read_csv(BytesIO(payload), encoding=encoding, dtype=str, low_memory=False)
            if len(frame.columns) < 2:
                raise ValueError("CSV has fewer than two columns.")
            frame.columns = frame.columns.astype(str).str.strip().str.replace("\ufeff", "", regex=False)
            return frame
        except UnicodeDecodeError:
            continue
    raise ValueError("Unable to decode CSV with UTF-8 or traditional Chinese encodings.")

with st.sidebar:
    st.header("資料設定")
    source = st.text_input("CSV 下載網址", value=CSV_URL, help="預設為資料集 156375 的官方 CSV 連結")
    if st.button("重新取得資料", use_container_width=True):
        load_data.clear()
    st.caption("僅輸入您信任的公開 CSV 來源；此工具會對網址發送 HTTP 請求。")

try:
    with st.spinner("正在下載與解析 CSV…"):
        df = load_data(source)
except (requests.RequestException, ValueError, pd.errors.ParserError) as exc:
    st.error(f"資料下載或解析失敗：{type(exc).__name__}: {exc}")
    st.info("請在瀏覽器開啟官方 CSV 連結確認可用性，或稍後重試。")
    st.stop()

# Keep original raw data intact; convert numeric columns only in an analysis copy.
raw_df = df.copy()
company_col = "公司名稱" if "公司名稱" in df.columns else None
code_col = "公司代號" if "公司代號" in df.columns else None
year_col = "報告年度" if "報告年度" in df.columns else None
emission_cols = [c for c in df.columns if "排放量" in c and "CO2" in c.upper().replace("₂", "2")]
# Also support minor spelling differences in CO2 units.
if not emission_cols:
    emission_cols = [c for c in df.columns if "範疇" in c and "排放量" in c]

with st.sidebar:
    st.header("篩選條件")
    keyword = st.text_input("公司代號／公司名稱關鍵字", placeholder="例如：半導體、1234")
    if year_col:
        years = sorted(df[year_col].dropna().astype(str).unique().tolist(), reverse=True)
        selected_years = st.multiselect("報告年度", years, default=years)
    else:
        selected_years = []
    drop_missing = st.checkbox("排除所有排放量皆缺漏的資料", value=False)

filtered = df.copy()
if keyword:
    searchable = pd.Series(False, index=filtered.index)
    for col in (code_col, company_col):
        if col:
            searchable |= filtered[col].fillna("").astype(str).str.contains(keyword, case=False, regex=False)
    filtered = filtered[searchable]
if year_col:
    filtered = filtered[filtered[year_col].astype(str).isin(selected_years)]

numeric = filtered.copy()
for col in emission_cols:
    numeric[col] = pd.to_numeric(
        numeric[col].astype(str).str.replace(",", "", regex=False).str.strip(),
        errors="coerce"
    )
if drop_missing and emission_cols:
    mask = numeric[emission_cols].notna().any(axis=1)
    numeric = numeric.loc[mask]
    filtered = filtered.loc[mask]

count, companies, years_count = st.columns(3)
count.metric("篩選後資料筆數", f"{len(filtered):,}")
companies.metric("公司數", f"{filtered[code_col].nunique():,}" if code_col else "N/A")
years_count.metric("報告年度數", f"{filtered[year_col].nunique():,}" if year_col else "N/A")

st.subheader("資料表")
st.dataframe(filtered, use_container_width=True, hide_index=True)
st.download_button(
    "⬇️ 下載篩選後 CSV", filtered.to_csv(index=False).encode("utf-8-sig"),
    file_name="OTC_ESG_GHG_filtered.csv", mime="text/csv", disabled=filtered.empty,
)

if emission_cols and not numeric.empty:
    st.subheader("排放量分析")
    selected_scope = st.selectbox("選擇排放量欄位（單位：公噸 CO₂e）", emission_cols)
    chart_data = numeric.dropna(subset=[selected_scope]).copy()
    if chart_data.empty:
        st.info("目前篩選條件下沒有可用的數值排放量資料。")
    else:
        st.metric("所選範疇排放量總和", f"{chart_data[selected_scope].sum():,.2f} 公噸 CO₂e")
        if company_col:
            top = (chart_data.groupby(company_col, dropna=False)[selected_scope]
                   .sum().sort_values(ascending=False).head(15))
            st.caption("所選範疇排放量最高的 15 家公司（依目前篩選資料彙總）")
            st.bar_chart(top)
        if year_col:
            trend = chart_data.groupby(year_col)[selected_scope].sum().sort_index()
            if len(trend) > 1:
                st.caption("依報告年度彙總（不同年度涵蓋公司可能不同）")
                st.line_chart(trend)
else:
    st.info("未找到排放量數值欄位；仍可使用資料表、搜尋與 CSV 匯出功能。")

with st.expander("原始資料檢查"):
    st.write("欄位名稱：", raw_df.columns.tolist())
    st.write("原始資料筆數：", len(raw_df))
    st.write("各欄缺漏數：")
    st.dataframe(raw_df.isna().sum().rename("缺漏筆數"), use_container_width=True)
    st.caption("原始 CSV 的缺漏值會保留；僅在分析時把排放量欄位轉換為數值。")
