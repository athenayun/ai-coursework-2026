"""PChome vs MOMO product price comparison dashboard."""
import re
import time
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st
from curl_cffi import requests as curl_requests

PCHOME_API = "https://ecshweb.pchome.com.tw/search/v3.3/all/results"
MOMO_API = "https://apisearch.momoshop.com.tw/momoSearchCloud/moec/textSearch"
MOMO_HOME = "https://www.momoshop.com.tw/"
COLUMNS = ["平台", "商品名稱", "價格", "來源頁數", "商品ID"]
BANDS = ["0–499", "500–999", "1,000–1,999", "2,000–4,999", "5,000+"]


def parse_price(value):
    if isinstance(value, dict):
        for key in ("P", "M", "price", "amount"):
            if key in value:
                return parse_price(value[key])
        return None
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value) if pd.notna(value) and value >= 0 else None
    cleaned = re.sub(r"[^0-9]", "", str(value))
    return float(cleaned) if cleaned else None


def fetch_pchome(keyword, pages):
    rows, warnings = [], []
    with requests.Session() as session:
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://24h.pchome.com.tw/",
        })
        for page in range(1, pages + 1):
            try:
                resp = session.get(PCHOME_API, params={"q": keyword, "page": page, "sort": "sale/dc"}, timeout=25)
                resp.raise_for_status()
                products = resp.json().get("prods", [])
                if not isinstance(products, list):
                    raise ValueError("Unexpected PChome product response")
                if not products:
                    warnings.append(f"PChome 第 {page} 頁沒有商品")
                for p in products:
                    if not isinstance(p, dict):
                        continue
                    price = parse_price(p.get("price"))
                    name = str(p.get("name") or "").strip()
                    if name and price is not None:
                        rows.append({"平台": "PChome", "商品名稱": name, "價格": price,
                                     "來源頁數": page, "商品ID": str(p.get("Id") or "")})
            except (requests.RequestException, ValueError, TypeError) as exc:
                warnings.append(f"PChome 第 {page} 頁失敗：{exc}")
            if page < pages:
                time.sleep(1)
    return rows, warnings


def momo_payload(keyword, page):
    return {
        "host": "momoshop", "flag": "searchEngine",
        "data": {
            "searchValue": keyword, "searchType": "1", "cateLevel": "-1",
            "curPage": str(page), "priceS": "0", "priceE": "9999999",
            "showType": "chessboardType", "isFuzzy": "0",
            "rtnCateDatainfo": {
                "cateCode": "", "cateLv": "-1", "keyword": keyword,
                "curPage": str(page), "historyDoPush": "false",
                "timestamp": int(time.time() * 1000),
            },
            "flag": 2018, "serviceCode": "MT01", "addressSearchData": {},
        },
    }


def fetch_momo(keyword, pages):
    rows, warnings = [], []
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
        "Content-Type": "application/json;charset=UTF-8",
        "Origin": MOMO_HOME.rstrip("/"), "Referer": MOMO_HOME,
    }
    session = curl_requests.Session(impersonate="chrome")
    try:
        try:
            session.get(MOMO_HOME, headers=headers, timeout=20)
        except Exception as exc:
            warnings.append(f"MOMO 首頁連線異常：{exc}")
        for page in range(1, pages + 1):
            try:
                resp = session.post(MOMO_API, headers=headers,
                                    json=momo_payload(keyword, page), timeout=25)
                resp.raise_for_status()
                products = resp.json().get("rtnSearchData", {}).get("goodsInfoList", [])
                if not isinstance(products, list):
                    raise ValueError("Unexpected MOMO product response")
                if not products:
                    warnings.append(f"MOMO 第 {page} 頁沒有商品")
                for p in products:
                    if not isinstance(p, dict):
                        continue
                    name = str(p.get("goodsName") or "").strip()
                    price = parse_price(p.get("goodsPrice"))
                    if name and price is not None:
                        rows.append({"平台": "MOMO", "商品名稱": name, "價格": price,
                                     "來源頁數": page,
                                     "商品ID": str(p.get("goodsCode") or p.get("goodsId") or "")})
            except Exception as exc:
                warnings.append(f"MOMO 第 {page} 頁失敗：{exc}")
            if page < pages:
                time.sleep(1)
    finally:
        session.close()
    return rows, warnings


def clean_data(rows):
    df = pd.DataFrame(rows, columns=COLUMNS)
    if df.empty:
        return df
    df["價格"] = pd.to_numeric(df["價格"], errors="coerce")
    df = df.dropna(subset=["價格"])
    df = df[df["價格"] >= 0].copy()
    # Prefer product IDs; use name and price for records without IDs.
    df["去重鍵"] = df.apply(
        lambda r: f"id:{r['商品ID']}" if r["商品ID"] else f"name:{r['商品名稱']}|{r['價格']}", axis=1
    )
    df = df.drop_duplicates(subset=["平台", "去重鍵"]).drop(columns="去重鍵")
    return df.reset_index(drop=True)


def price_band(price):
    if price < 500:
        return BANDS[0]
    if price < 1000:
        return BANDS[1]
    if price < 2000:
        return BANDS[2]
    if price < 5000:
        return BANDS[3]
    return BANDS[4]


st.set_page_config(page_title="PChome × MOMO 價格比較", page_icon="🛒", layout="wide")
st.title("🛒 PChome × MOMO 商品價格比較")
st.caption("同一搜尋關鍵字、相同擷取頁數；比較兩個平台搜尋結果的價格分布。資料僅供參考，並非相同商品的逐項比價。")

with st.form("search"):
    left, right = st.columns([3, 1])
    with left:
        keyword = st.text_input("商品名稱／關鍵字", value="行動電源")
    with right:
        pages = st.number_input("每個平台擷取頁數", min_value=1, max_value=20, value=3, step=1)
    submit = st.form_submit_button("開始擷取與比較", type="primary")

if submit:
    if not keyword.strip():
        st.error("請輸入商品名稱。")
    else:
        with st.spinner("正在擷取 PChome 和 MOMO，請稍候..."):
            with ThreadPoolExecutor(max_workers=2) as pool:
                f1 = pool.submit(fetch_pchome, keyword.strip(), int(pages))
                f2 = pool.submit(fetch_momo, keyword.strip(), int(pages))
                p_rows, p_warnings = f1.result()
                m_rows, m_warnings = f2.result()
        st.session_state["df"] = clean_data(p_rows + m_rows)
        st.session_state["warnings"] = p_warnings + m_warnings
        st.session_state["keyword"] = keyword.strip()

if "df" in st.session_state:
    df = st.session_state["df"]
    for warning in st.session_state.get("warnings", []):
        st.warning(warning)
    if df.empty:
        st.error("兩個平台都沒有取得有效商品。請確認網路連線、API 回應與網站存取限制。")
    else:
        keyword_used = st.session_state["keyword"]
        stats = df.groupby("平台")["價格"].agg(商品數="count", 平均價格="mean", 最低價格="min", 最高價格="max").reset_index()
        st.subheader("平台價格統計")
        st.dataframe(stats.style.format({"平均價格": "NT$ {:,.0f}", "最低價格": "NT$ {:,.0f}", "最高價格": "NT$ {:,.0f}"}),
                     use_container_width=True, hide_index=True)
        if df["平台"].nunique() < 2:
            st.info("目前只有一個平台有資料，跨平台比較圖將只顯示已取得的資料。")
        st.subheader("商品資料")
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button("下載完整 CSV", df.to_csv(index=False).encode("utf-8-sig"),
                           file_name="pchome_momo_comparison.csv", mime="text/csv")

        st.subheader("📈 折線圖：各平台前 70 筆商品價格")
        line_frames = []
        for platform, group in df.groupby("平台"):
            part = group.head(70).reset_index(drop=True).copy()
            part["商品序號"] = part.index + 1
            line_frames.append(part)
        line_df = pd.concat(line_frames, ignore_index=True)
        fig_line = px.line(line_df, x="商品序號", y="價格", color="平台", markers=True,
                           hover_data=["商品名稱", "來源頁數"],
                           title=f"「{keyword_used}」搜尋結果價格（各平台前 70 筆）")
        st.plotly_chart(fig_line, use_container_width=True)

        df_plot = df.copy()
        df_plot["價格區間"] = df_plot["價格"].map(price_band)
        st.subheader("🥧 圓餅圖：兩平台商品數量占比")
        counts = df_plot.groupby("平台", as_index=False).size()
        fig_pie = px.pie(counts, names="平台", values="size", hole=0.25,
                         title="已擷取有效商品數量占比（不是市場占有率）")
        st.plotly_chart(fig_pie, use_container_width=True)

        st.subheader("☀️ 旭日圖：平台 → 價格區間")
        sun = df_plot.groupby(["平台", "價格區間"], as_index=False).size().rename(columns={"size": "商品數"})
        fig_sun = px.sunburst(sun, path=["平台", "價格區間"], values="商品數",
                              title="各平台商品價格分布（筆數）")
        st.plotly_chart(fig_sun, use_container_width=True)

        st.subheader("📊 柱狀圖：平均、最低、最高價格比較")
        bar = stats.melt(id_vars="平台", value_vars=["平均價格", "最低價格", "最高價格"],
                         var_name="統計項目", value_name="價格")
        fig_bar = px.bar(bar, x="統計項目", y="價格", color="平台", barmode="group",
                         text_auto=".0f", title="PChome 與 MOMO 價格統計比較")
        st.plotly_chart(fig_bar, use_container_width=True)

        st.info("注意：兩站的搜尋排序、商品規格、促銷方式與資料筆數可能不同；這些圖表比較搜尋樣本，不代表同款商品的實際價差。")
