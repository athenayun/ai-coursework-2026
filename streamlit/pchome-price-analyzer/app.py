# -*- coding: utf-8 -*-
"""PChome product search and price visualization using Streamlit."""

import io
import math
import time
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import font_manager
import pandas as pd
import plotly.express as px
import requests
import streamlit as st

API_URL = "https://ecshweb.pchome.com.tw/search/v3.3/all/results"
FONT_URL = "https://drive.google.com/uc?export=download&id=1eGAsTN1HBpJAkeVM57_C7ccp7hbgSz3_"
FONT_PATH = Path(__file__).resolve().parent / "TaipeiSansTCBeta-Regular.ttf"

st.set_page_config(page_title="PChome 商品價格分析", page_icon="🛍️", layout="wide")


@st.cache_resource(show_spinner=False)
def configure_chinese_font():
    """Try existing CJK fonts first; download the class font if needed."""
    preferred = ["Taipei Sans TC Beta", "Noto Sans CJK TC", "Noto Sans CJK JP", "PingFang TC", "Microsoft JhengHei", "Heiti TC"]
    available = {f.name for f in font_manager.fontManager.ttflist}
    for family in preferred:
        if family in available:
            plt.rcParams["font.family"] = family
            plt.rcParams["axes.unicode_minus"] = False
            return family

    if not FONT_PATH.exists():
        try:
            response = requests.get(FONT_URL, timeout=20)
            response.raise_for_status()
            # A valid TTF starts with 0x00010000, 'true', or 'OTTO'.
            if response.content[:4] in (b"\x00\x01\x00\x00", b"true", b"OTTO"):
                FONT_PATH.write_bytes(response.content)
        except (requests.RequestException, OSError):
            pass

    if FONT_PATH.exists():
        try:
            font_manager.fontManager.addfont(str(FONT_PATH))
            family = font_manager.FontProperties(fname=str(FONT_PATH)).get_name()
            plt.rcParams["font.family"] = family
            plt.rcParams["axes.unicode_minus"] = False
            return family
        except (OSError, ValueError, RuntimeError):
            pass
    return None


def fetch_products(keyword: str, pages: int, pause: float = 1.0):
    """Fetch PChome JSON search results, returning records and page warnings."""
    records = []
    warnings = []
    progress = st.progress(0, text="準備爬取資料...")
    with requests.Session() as session:
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://24h.pchome.com.tw/",
        })
        for page in range(1, pages + 1):
            try:
                response = session.get(
                    API_URL,
                    params={"q": keyword, "page": page, "sort": "sale/dc"},
                    timeout=25,
                )
                response.raise_for_status()
                payload = response.json()
                prods = payload.get("prods", [])
                if not isinstance(prods, list):
                    raise ValueError("Unexpected 'prods' format")
                for product in prods:
                    if isinstance(product, dict):
                        records.append({**product, "來源頁數": page})
                if not prods:
                    warnings.append(f"第 {page} 頁沒有回傳商品資料。")
            except (requests.RequestException, ValueError) as exc:
                warnings.append(f"第 {page} 頁抓取失敗：{exc}")
            progress.progress(page / pages, text=f"已處理 {page}/{pages} 頁")
            if page < pages:
                time.sleep(pause)
    progress.empty()
    return records, warnings


def prepare_dataframe(records):
    raw = pd.DataFrame(records)
    if raw.empty:
        return pd.DataFrame(columns=["商品名稱", "價格", "來源頁數", "商品ID"])
    if "name" not in raw.columns or "price" not in raw.columns:
        raise ValueError("API response does not contain expected 'name' and 'price' fields.")

    # The PChome API can return numeric prices or nested price objects.
    def extract_price(value):
        if isinstance(value, dict):
            for key in ("P", "M", "price", "amount"):
                if key in value:
                    return extract_price(value[key])
            return math.nan
        if isinstance(value, str):
            value = value.replace(",", "").replace("$", "").strip()
        return pd.to_numeric(value, errors="coerce")

    df = pd.DataFrame({
        "商品名稱": raw["name"].astype(str),
        "價格": raw["price"].map(extract_price),
        "來源頁數": raw["來源頁數"],
        "商品ID": raw["Id"].astype(str) if "Id" in raw.columns else "",
    })
    df = df.dropna(subset=["價格"])
    df = df[df["價格"] >= 0]
    if df["商品ID"].ne("").any():
        df = df.drop_duplicates(subset=["商品ID"])
    else:
        df = df.drop_duplicates(subset=["商品名稱", "價格"])
    return df.reset_index(drop=True)


def make_line_chart(df, keyword, font_family):
    subset = df.head(70).reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(12, 4.5))
    ax.plot(range(1, len(subset) + 1), subset["價格"], marker="o", markersize=3, linewidth=1.5)
    ax.axhline(df["價格"].mean(), color="red", linestyle="--", label=f"平均價格: {df['價格'].mean():,.0f}")
    ax.set_title(f"PChome「{keyword}」商品售價")
    ax.set_xlabel("商品序號")
    ax.set_ylabel("價格 (NT$)")
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()
    return fig


def make_price_bands(df):
    # Five equal-width price bands, with a special case for identical prices.
    if df["價格"].nunique() == 1:
        return pd.Series(["同一價格"] * len(df), index=df.index, name="價格區間")
    bands = pd.cut(df["價格"], bins=5, include_lowest=True, duplicates="drop")
    return bands.map(lambda b: f"NT${b.left:,.0f}–{b.right:,.0f}").rename("價格區間")


st.title("🛍️ PChome 商品價格分析")
st.caption("輸入商品關鍵字與頁數，擷取商品價格並產生折線圖、圓餅圖及旭日圖。")

with st.form("search_form"):
    left, right = st.columns([3, 1])
    with left:
        keyword = st.text_input("商品名稱 / 搜尋關鍵字", value="行動電源")
    with right:
        pages = st.number_input("爬取頁數", min_value=1, max_value=20, value=3, step=1)
    submitted = st.form_submit_button("開始爬取與分析", type="primary")

if submitted:
    if not keyword.strip():
        st.error("請輸入商品名稱。")
    else:
        with st.spinner("正在擷取 PChome 商品資料..."):
            records, warnings = fetch_products(keyword.strip(), int(pages))
        try:
            df = prepare_dataframe(records)
        except ValueError as exc:
            st.error(str(exc))
            df = pd.DataFrame()

        for warning in warnings:
            st.warning(warning)
        if df.empty:
            st.error("未取得有效商品資料。網站 API 可能變更、限制存取，或查無商品。")
        else:
            st.session_state["df"] = df
            st.session_state["keyword"] = keyword.strip()
            st.success(f"完成！取得 {len(df)} 筆不重複且具有有效價格的商品資料。")

if "df" in st.session_state:
    df = st.session_state["df"]
    keyword = st.session_state["keyword"]
    font_family = configure_chinese_font()
    if not font_family:
        st.info("找不到可用中文字型，Matplotlib 中文可能顯示為方框；可將 TaipeiSansTCBeta-Regular.ttf 放在 app.py 同一資料夾。")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("商品數量", f"{len(df):,}")
    c2.metric("平均價格", f"NT$ {df['價格'].mean():,.0f}")
    c3.metric("最高價格", f"NT$ {df['價格'].max():,.0f}")
    c4.metric("最低價格", f"NT$ {df['價格'].min():,.0f}")

    st.subheader("商品資料")
    st.dataframe(df, use_container_width=True, hide_index=True)
    csv_data = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button("下載 CSV", csv_data, file_name="pchome_products.csv", mime="text/csv")

    st.subheader("1. 商品價格折線圖（前 70 筆）")
    fig = make_line_chart(df, keyword, font_family)
    st.pyplot(fig)
    plt.close(fig)

    chart_df = df.copy()
    chart_df["價格區間"] = make_price_bands(chart_df)
    counts = chart_df.groupby("價格區間", observed=True).size().reset_index(name="商品數量")

    st.subheader("2. 價格區間圓餅圖")
    st.caption("依商品價格分成最多五個區間，呈現各區間商品數量比例。")
    pie = px.pie(counts, names="價格區間", values="商品數量", hole=0)
    st.plotly_chart(pie, use_container_width=True)

    st.subheader("3. 價格區間旭日圖（Sunburst）")
    st.caption("第一層：來源頁數；第二層：價格區間；面積代表商品數量。")
    sunburst_df = chart_df.groupby(["來源頁數", "價格區間"], observed=True).size().reset_index(name="商品數量")
    sunburst_df["來源頁數"] = sunburst_df["來源頁數"].map(lambda x: f"第 {x} 頁")
    sunburst = px.sunburst(sunburst_df, path=["來源頁數", "價格區間"], values="商品數量")
    st.plotly_chart(sunburst, use_container_width=True)

st.caption("資料來源：PChome 搜尋 API。請遵守網站使用條款及合理請求頻率。")
