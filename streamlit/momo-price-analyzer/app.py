"""MOMO product price explorer (Streamlit)."""

import io
import re
import time
from collections import Counter

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from curl_cffi import requests

API_URL = "https://apisearch.momoshop.com.tw/momoSearchCloud/moec/textSearch"
HOME_URL = "https://www.momoshop.com.tw/"
HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    "Content-Type": "application/json;charset=UTF-8",
    "Origin": "https://www.momoshop.com.tw",
    "Referer": HOME_URL,
}
COLUMNS = ["品名", "價格", "來源頁數"]


def make_payload(keyword: str, page: int) -> dict:
    return {
        "host": "momoshop",
        "flag": "searchEngine",
        "data": {
            "searchValue": keyword,
            "searchType": "1",
            "cateLevel": "-1",
            "curPage": str(page),
            "priceS": "0",
            "priceE": "9999999",
            "showType": "chessboardType",
            "isFuzzy": "0",
            "rtnCateDatainfo": {
                "cateCode": "",
                "cateLv": "-1",
                "keyword": keyword,
                "curPage": str(page),
                "historyDoPush": "false",
                "timestamp": int(time.time() * 1000),
            },
            "flag": 2018,
            "serviceCode": "MT01",
            "addressSearchData": {},
        },
    }


def parse_price(value) -> int | None:
    """Convert '$1,299' or 1299 to a price; ignore invalid values."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value) if pd.notna(value) and value >= 0 else None
    cleaned = re.sub(r"[^0-9]", "", str(value))
    return int(cleaned) if cleaned else None


def scrape_momo(keyword: str, page_count: int, delay: float = 1.5):
    rows, warnings = [], []
    progress = st.progress(0, text="正在連線 MOMO...")
    session = requests.Session(impersonate="chrome")
    try:
        # The source notebook warms up a session to receive site cookies.
        try:
            session.get(HOME_URL, headers=HEADERS, timeout=20)
        except Exception as exc:
            warnings.append(f"首頁連線未成功：{exc}")

        for page in range(1, page_count + 1):
            progress.progress((page - 1) / page_count, text=f"正在擷取第 {page}/{page_count} 頁...")
            try:
                response = session.post(
                    API_URL,
                    headers=HEADERS,
                    json=make_payload(keyword, page),
                    timeout=25,
                )
                response.raise_for_status()
                body = response.json()
                products = body.get("rtnSearchData", {}).get("goodsInfoList", [])
                if not isinstance(products, list):
                    raise ValueError("API 的 goodsInfoList 不是清單")
                if not products:
                    warnings.append(f"第 {page} 頁沒有回傳商品。")
                for product in products:
                    if not isinstance(product, dict):
                        continue
                    price = parse_price(product.get("goodsPrice"))
                    name = str(product.get("goodsName") or "").strip()
                    if name and price is not None:
                        rows.append({"品名": name, "價格": price, "來源頁數": page})
            except Exception as exc:
                warnings.append(f"第 {page} 頁擷取失敗：{exc}")
            progress.progress(page / page_count, text=f"已處理 {page}/{page_count} 頁")
            if page < page_count:
                time.sleep(delay)
    finally:
        session.close()
        progress.empty()
    return pd.DataFrame(rows, columns=COLUMNS), warnings


def price_band(price: int) -> str:
    if price < 500:
        return "NT$0–499"
    if price < 1000:
        return "NT$500–999"
    if price < 2000:
        return "NT$1,000–1,999"
    if price < 5000:
        return "NT$2,000–4,999"
    return "NT$5,000+"


st.set_page_config(page_title="MOMO 商品價格分析", page_icon="🛒", layout="wide")
st.title("🛒 MOMO 商品價格分析")
st.caption("以 curl_cffi 擷取 MOMO 搜尋資料，使用 pandas 與 Plotly 進行價格分析。")

with st.form("search_form"):
    col1, col2 = st.columns([3, 1])
    with col1:
        keyword = st.text_input("商品名稱／搜尋關鍵字", value="行動電源")
    with col2:
        pages = st.number_input("擷取頁數", min_value=1, max_value=20, value=3, step=1)
    submitted = st.form_submit_button("開始擷取並分析", type="primary")

if submitted:
    if not keyword.strip():
        st.error("請輸入商品名稱。")
    else:
        with st.spinner("正在擷取商品資料..."):
            df, warnings = scrape_momo(keyword.strip(), int(pages))
        st.session_state["results"] = df
        st.session_state["warnings"] = warnings
        st.session_state["keyword"] = keyword.strip()

if "results" in st.session_state:
    df = st.session_state["results"]
    keyword_used = st.session_state["keyword"]
    for warning in st.session_state.get("warnings", []):
        st.warning(warning)

    if df.empty:
        st.info("沒有取得可分析的商品。請確認關鍵字、網路連線，或 MOMO API 是否變更。")
    else:
        st.success(f"取得 {len(df)} 筆有效商品資料（可能包含跨頁重複商品）。")
        a, b, c, d = st.columns(4)
        a.metric("商品筆數", f"{len(df):,}")
        b.metric("平均價格", f"NT$ {df['價格'].mean():,.0f}")
        c.metric("最高價格", f"NT$ {df['價格'].max():,}")
        d.metric("最低價格", f"NT$ {df['價格'].min():,}")

        st.subheader("商品資料")
        st.dataframe(df, use_container_width=True, hide_index=True)
        csv_bytes = df.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "下載 CSV",
            data=csv_bytes,
            file_name="MOMO_products.csv",
            mime="text/csv",
        )

        st.subheader("價格折線圖")
        plot_df = df.head(70).reset_index(drop=True).copy()
        plot_df["商品序號"] = plot_df.index + 1
        fig_line = px.line(
            plot_df,
            x="商品序號",
            y="價格",
            hover_data=["品名", "來源頁數"],
            markers=True,
            title=f"MOMO 電商網站上「{keyword_used}」售價（前 {len(plot_df)} 筆）",
        )
        fig_line.add_hline(
            y=float(df["價格"].mean()),
            line_dash="dash",
            line_color="red",
            annotation_text=f"整體平均 NT$ {df['價格'].mean():,.0f}",
        )
        fig_line.update_layout(yaxis_title="價格 (NT$)")
        st.plotly_chart(fig_line, use_container_width=True)

        chart_df = df.copy()
        chart_df["價格區間"] = chart_df["價格"].map(price_band)
        bands = ["NT$0–499", "NT$500–999", "NT$1,000–1,999", "NT$2,000–4,999", "NT$5,000+"]
        counts = chart_df["價格區間"].value_counts().reindex(bands, fill_value=0)
        counts = counts[counts > 0]

        left, right = st.columns(2)
        with left:
            st.subheader("價格區間圓餅圖")
            fig_pie = px.pie(
                names=counts.index.tolist(),
                values=counts.values.tolist(),
                title="商品數量占比（依價格區間）",
                hole=0,
            )
            st.plotly_chart(fig_pie, use_container_width=True)
        with right:
            st.subheader("旭日圖（Sunburst）")
            chart_df["頁數"] = chart_df["來源頁數"].map(lambda p: f"第 {p} 頁")
            grouped = chart_df.groupby(["頁數", "價格區間"], as_index=False).size()
            grouped = grouped.rename(columns={"size": "商品數量"})
            fig_sunburst = px.sunburst(
                grouped,
                path=["頁數", "價格區間"],
                values="商品數量",
                title="頁數 → 價格區間 → 商品數量",
            )
            st.plotly_chart(fig_sunburst, use_container_width=True)

st.caption("提醒：MOMO 搜尋 API 可能變更或限制自動存取；請遵守網站使用規範並避免頻繁請求。")
