"""Tainan City public paid parking lots: government open-data dashboard."""
from __future__ import annotations

from io import BytesIO
import re

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

DATASET_PAGE = 'https://data.gov.tw/dataset/102773'
CSV_URL = 'https://data.tainan.gov.tw/File/ResourceCsvDownload/24b8d897-7971-45f9-8489-b4918ee41ed7'
CAPACITY_FIELDS = [
    '一般大型車數量', '一般小型車數量', '身障者小型車數量', '婦幼者小型車數量',
    '綠能小型車數量', '一般機車數量', '身障者機車數量',
    '小型車充電樁數量', '機車綠能數量',
]

st.set_page_config(page_title='Tainan Parking Dashboard | 臺南市公有收費停車場', page_icon='🅿️', layout='wide', initial_sidebar_state='expanded')

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_csv(url: str) -> pd.DataFrame:
    response = requests.get(url, timeout=35, headers={'User-Agent': 'Mozilla/5.0 (compatible; TainanParkingDashboard/1.0)', 'Accept': 'text/csv,*/*'})
    response.raise_for_status()
    raw = response.content
    if not raw:
        raise ValueError('The CSV response is empty.')
    errors = []
    for encoding in ('utf-8-sig', 'utf-8', 'cp950', 'big5'):
        try:
            frame = pd.read_csv(BytesIO(raw), encoding=encoding, dtype=str, on_bad_lines='skip')
            if len(frame.columns) < 2:
                raise ValueError('CSV contains fewer than two columns.')
            frame.columns = [str(col).strip().replace('\ufeff', '') for col in frame.columns]
            return frame
        except (UnicodeError, pd.errors.ParserError, ValueError) as exc:
            errors.append(f'{encoding}: {exc}')
    raise ValueError('Could not decode the CSV. ' + '; '.join(errors))


def numeric_series(frame: pd.DataFrame, field: str) -> pd.Series:
    return pd.to_numeric(frame[field].astype('string').str.replace(',', '', regex=False).str.replace(r'[^0-9.\-]', '', regex=True), errors='coerce')


st.title('🅿️ Tainan Public Parking Dashboard | 臺南市公有收費停車場')
st.caption('Government Open Data · 臺南市政府交通局 · CSV via requests.get()')

with st.sidebar:
    st.header('Data & Filters')
    st.markdown('[Official dataset / 政府資料集](https://data.gov.tw/dataset/102773)')
    source_url = st.text_input('CSV source URL', value=CSV_URL, help='Official CSV resource URL from the dataset page.')
    if st.button('↻ Refresh data', use_container_width=True):
        fetch_csv.clear()
        st.rerun()

try:
    with st.spinner('Downloading government CSV data...'):
        df = fetch_csv(source_url)
except (requests.RequestException, ValueError, pd.errors.EmptyDataError) as exc:
    st.error(f'Unable to load the CSV: {exc}')
    st.info('Open the official dataset link in the sidebar, copy its current CSV download URL, paste it into “CSV source URL”, and refresh. Government resource URLs can change.')
    st.stop()

if df.empty:
    st.warning('The downloaded CSV has no rows.')
    st.stop()

name_field = next((c for c in ('停車場名稱', '停車場名', '名稱') if c in df.columns), None)
type_field = next((c for c in ('停車場型態', '停車場類型') if c in df.columns), None)

with st.sidebar:
    keyword = st.text_input('Search parking lot / 搜尋停車場', placeholder='Enter a name or address')
    if type_field:
        types = sorted(df[type_field].dropna().astype(str).unique().tolist())
        chosen_types = st.multiselect('Parking lot type / 停車場型態', types, default=types)
    else:
        chosen_types = []
    st.divider()
    st.header('Chart Settings')
    top_n = st.slider('Number of parking lots to display', 5, 40, 15)
    chart_style = st.selectbox('Capacity chart', ['Bar chart', 'Pie chart', 'Sunburst chart'])

filtered = df.copy()
if keyword:
    mask = filtered.astype(str).apply(lambda col: col.str.contains(re.escape(keyword), case=False, na=False)).any(axis=1)
    filtered = filtered.loc[mask]
if type_field:
    filtered = filtered.loc[filtered[type_field].astype(str).isin(chosen_types)]

capacity_available = [c for c in CAPACITY_FIELDS if c in filtered.columns]
for c in capacity_available:
    filtered[c + '_numeric'] = numeric_series(filtered, c)

st.subheader('Overview | 資料概覽')
a, b, c, d = st.columns(4)
a.metric('Parking lots / 停車場數', f'{len(filtered):,}')
if '一般小型車數量_numeric' in filtered:
    b.metric('Regular car spaces / 一般小型車位', f"{filtered['一般小型車數量_numeric'].sum():,.0f}")
else:
    b.metric('Available columns', len(df.columns))
if '一般機車數量_numeric' in filtered:
    c.metric('Motorcycle spaces / 機車位', f"{filtered['一般機車數量_numeric'].sum():,.0f}")
else:
    c.metric('Source rows', f'{len(df):,}')
if '小型車充電樁數量_numeric' in filtered:
    d.metric('Car charging points / 充電樁', f"{filtered['小型車充電樁數量_numeric'].sum():,.0f}")
else:
    d.metric('Filtered rows', f'{len(filtered):,}')

if filtered.empty:
    st.warning('No records match your filters. Adjust the sidebar selections.')
    st.stop()

st.subheader('Parking Capacity Analysis | 停車容量分析')
if capacity_available:
    capacity_totals = pd.DataFrame({
        'Space category': capacity_available,
        'Count': [float(filtered[c + '_numeric'].sum()) for c in capacity_available],
    })
    capacity_totals = capacity_totals[capacity_totals['Count'] > 0]
    if not capacity_totals.empty:
        left, right = st.columns([3, 2])
        with left:
            if chart_style == 'Bar chart':
                fig = px.bar(capacity_totals, x='Space category', y='Count', title='Spaces by category', text_auto='.0f')
            elif chart_style == 'Pie chart':
                fig = px.pie(capacity_totals, names='Space category', values='Count', title='Share of parking spaces')
            else:
                hierarchy = capacity_totals.assign(Group='Parking capacity')
                fig = px.sunburst(hierarchy, path=['Group', 'Space category'], values='Count', title='Capacity hierarchy')
            st.plotly_chart(fig, use_container_width=True)
        with right:
            if type_field:
                counts = filtered[type_field].fillna('Unknown').value_counts().reset_index()
                counts.columns = ['Parking type', 'Parking lots']
                st.plotly_chart(px.pie(counts, names='Parking type', values='Parking lots', title='Parking lot types'), use_container_width=True)
            else:
                st.info('Parking type column not found in this CSV.')
    else:
        st.info('Capacity columns exist, but contain no positive numeric values.')
else:
    st.info('No expected parking-capacity columns were found. Use the field explorer below.')

if name_field and '一般小型車數量_numeric' in filtered:
    st.subheader('Largest Parking Lots | 停車場容量排行')
    ranked = filtered[[name_field, '一般小型車數量_numeric']].dropna().sort_values('一般小型車數量_numeric', ascending=False).head(top_n)
    if not ranked.empty:
        ranked = ranked.rename(columns={name_field: 'Parking lot', '一般小型車數量_numeric': 'Regular car spaces'})
        st.plotly_chart(px.bar(ranked.sort_values('Regular car spaces'), x='Regular car spaces', y='Parking lot', orientation='h', title=f'Top {len(ranked)} by regular car spaces'), use_container_width=True)

st.subheader('Explore Any Column | 自訂欄位分析')
usable_fields = [c for c in df.columns if c in filtered.columns]
col1, col2 = st.columns(2)
with col1:
    selected_field = st.selectbox('Select a column', usable_fields, index=usable_fields.index(type_field) if type_field in usable_fields else 0)
with col2:
    mode = st.selectbox('Visualization', ['Value counts (bar)', 'Value counts (pie)', 'Numeric distribution (histogram)'])
if mode.startswith('Numeric'):
    values = numeric_series(filtered, selected_field).dropna()
    if values.empty:
        st.info('This column does not contain numeric values.')
    else:
        st.plotly_chart(px.histogram(x=values, nbins=25, labels={'x': selected_field}, title=f'Distribution: {selected_field}'), use_container_width=True)
else:
    counts = filtered[selected_field].fillna('Missing').astype(str).value_counts().head(20).reset_index()
    counts.columns = ['Value', 'Records']
    fig = (px.bar(counts, x='Value', y='Records', title=f'Top values: {selected_field}') if mode.endswith('(bar)') else px.pie(counts, names='Value', values='Records', title=f'Top values: {selected_field}'))
    st.plotly_chart(fig, use_container_width=True)

st.subheader('Dataset Records | 資料明細')
st.caption(f'{len(filtered):,} filtered records · {len(df.columns)} source columns')
st.dataframe(filtered[df.columns], use_container_width=True, hide_index=True)
st.download_button('⬇ Download filtered CSV / 下載 CSV', data=filtered[df.columns].to_csv(index=False).encode('utf-8-sig'), file_name='tainan_public_parking_filtered.csv', mime='text/csv', use_container_width=True)
with st.expander('Data notes / 資料說明'):
    st.markdown('The dataset is published by the Tainan City Government Transportation Bureau. Numeric capacity fields are summed across filtered records. This dashboard does not claim that the published CSV represents live occupancy. Data availability and column names may change. [Official dataset](https://data.gov.tw/dataset/102773).')
