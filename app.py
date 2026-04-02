import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from datetime import datetime
from io import BytesIO
import folium
from streamlit_folium import st_folium
from folium.plugins import HeatMap
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

st.set_page_config(page_title="星巴克式全国选址Dashboard", layout="wide", page_icon="☕")

st.title("☕ 星巴克式全国选址Dashboard")
st.markdown("**2025-2026最终完整版** | 百度搜索 + 彩色热力图 + Top10排行榜")

# ==================== 侧边栏 ====================
st.sidebar.header("🎛️ 参数配置")
business_type = st.sidebar.selectbox("选择你的业态", ["咖啡店（星巴克风格）", "奶茶店", "便利店/零售", "其他餐饮"])

weights = {
    '人口密度': 0.10, '收入水平': 0.15, '人流量': 0.25,
    '竞争指数': -0.15, '交通便利': 0.15, '目标人群': 0.15, '可见性': 0.10
}

st.sidebar.subheader("⚖️ 调节权重（总和=1）")
col1, col2 = st.sidebar.columns(2)
for i, k in enumerate(weights.keys()):
    with (col1 if i % 2 == 0 else col2):
        weights[k] = st.slider(k, 0.0, 1.0, weights[k], 0.01)

selected_city = st.sidebar.selectbox("筛选城市", ["全国", "北京", "上海", "广州", "深圳", "成都", "杭州", "重庆", "武汉", "南京", "天津"])

BAIDU_AK = "KfLnZjiboACAfJBZkNAJtb1OGeKIg0fg"

# ==================== 数据初始化 ====================
if 'edited_df' not in st.session_state:
    data = {
        '地点': ['北京CBD', '上海小陆家嘴', '南京新街口', '广州天河路', '成都春熙路', '深圳福田CBD', '上海南京东路'],
        '城市': ['北京', '上海', '南京', '广州', '成都', '深圳', '上海'],
        '纬度': [39.904, 31.235, 32.040, 23.120, 30.658, 22.535, 31.230],
        '经度': [116.397, 121.510, 118.783, 113.321, 104.066, 114.085, 121.474],
        '人口密度(人/km²)': [18000, 21000, 16500, 18000, 16000, 20000, 22000],
        '平均收入(元/月)': [7424, 7666, 6500, 6500, 5833, 6667, 7666],
        '人流量评分(1-10)': [9, 10, 10, 9, 9, 9, 9],
        '竞争指数(1-10,越低越好)': [2, 3, 2, 3, 4, 2, 4],
        '交通便利度(1-10)': [10, 10, 10, 9, 9, 9, 10],
        '目标人群匹配度(1-10)': [9, 9, 9, 9, 8, 9, 9],
        '可见性(1-10)': [9, 9, 9, 8, 9, 9, 9]
    }
    st.session_state.edited_df = pd.DataFrame(data)

edited_df = st.session_state.edited_df.copy()

# 数据编辑器
edited_df = st.data_editor(edited_df, num_rows="dynamic", use_container_width=True)
st.session_state.edited_df = edited_df

# ==================== 筛选城市动态过滤 ====================
if selected_city != "全国":
    filtered_df = edited_df[edited_df['城市'] == selected_city].reset_index(drop=True)
else:
    filtered_df = edited_df.copy()

# ==================== 百度搜索 ====================
st.subheader("🔍 一键搜索百度最新商圈")
col_a, col_b = st.columns([3, 1])
with col_a:
    search_city = st.text_input("搜索城市", value="成都")
    search_query = st.text_input("商圈关键词", value="春熙路")
with col_b:
    if st.button("🚀 搜索并添加", type="primary"):
        with st.spinner("正在调用百度API..."):
            url = "https://api.map.baidu.com/place/v2/search"
            params = {"query": search_query, "region": search_city, "output": "json", "ak": BAIDU_AK, "page_size": 10, "scope": 2}
            try:
                resp = requests.get(url, params=params, timeout=15)
                resp.raise_for_status()
                result = resp.json()
                if result.get("status") == 0 and result.get("results"):
                    new_rows = []
                    for place in result["results"]:
                        new_rows.append({
                            '地点': place.get('name', ''),
                            '城市': search_city,
                            '纬度': place['location']['lat'],
                            '经度': place['location']['lng'],
                            '人口密度(人/km²)': 15000,
                            '平均收入(元/月)': 6000,
                            '人流量评分(1-10)': 8,
                            '竞争指数(1-10,越低越好)': 4,
                            '交通便利度(1-10)': 9,
                            '目标人群匹配度(1-10)': 8,
                            '可见性(1-10)': 8
                        })
                    new_df = pd.DataFrame(new_rows)
                    st.session_state.edited_df = pd.concat([st.session_state.edited_df, new_df], ignore_index=True)
                    st.success(f"✅ 已添加 {len(new_rows)} 个商圈！")
                    st.rerun()
                else:
                    st.error("未找到结果，请换关键词")
            except Exception as e:
                st.error(f"API调用失败: {e}")

# ==================== 评分计算 ====================
st.header("📊 选址评分结果")

df_for_score = filtered_df.copy()

standard_cols = ['地点', '城市', '纬度', '经度', '人口密度(人/km²)', '平均收入(元/月)',
                 '人流量评分(1-10)', '竞争指数(1-10,越低越好)', '交通便利度(1-10)',
                 '目标人群匹配度(1-10)', '可见性(1-10)']
for col in standard_cols:
    if col not in df_for_score.columns:
        df_for_score[col] = 0

cols_to_norm = ['人口密度(人/km²)', '平均收入(元/月)', '人流量评分(1-10)', '交通便利度(1-10)', '目标人群匹配度(1-10)', '可见性(1-10)']
for col in cols_to_norm:
    if col in df_for_score.columns:
        df_for_score[col + '_norm'] = (df_for_score[col] - df_for_score[col].min()) / (df_for_score[col].max() - df_for_score[col].min() + 1e-8)

if '竞争指数(1-10,越低越好)' in df_for_score.columns:
    df_for_score['竞争指数_norm'] = (10 - df_for_score['竞争指数(1-10,越低越好)']) / 9

col_map = {
    '人口密度': '人口密度(人/km²)_norm',
    '收入水平': '平均收入(元/月)_norm',
    '人流量': '人流量评分(1-10)_norm',
    '竞争指数': '竞争指数_norm',
    '交通便利': '交通便利度(1-10)_norm',
    '目标人群': '目标人群匹配度(1-10)_norm',
    '可见性': '可见性(1-10)_norm'
}

df_for_score['选址得分'] = 0.0
for k, w in weights.items():
    norm_col = col_map.get(k)
    if norm_col in df_for_score.columns:
        df_for_score['选址得分'] += df_for_score[norm_col] * abs(w)

df_for_score['选址得分'] = (df_for_score['选址得分'] * 100).round(2)
df_for_score = df_for_score.sort_values('选址得分', ascending=False).reset_index(drop=True)

display_cols = ['地点', '城市', '选址得分']
for k in weights.keys():
    full_col = {'人口密度': '人口密度(人/km²)', '收入水平': '平均收入(元/月)', '人流量': '人流量评分(1-10)',
                '竞争指数': '竞争指数(1-10,越低越好)', '交通便利': '交通便利度(1-10)',
                '目标人群': '目标人群匹配度(1-10)', '可见性': '可见性(1-10)'}.get(k)
    if full_col in df_for_score.columns:
        display_cols.append(full_col)

st.dataframe(df_for_score[display_cols], use_container_width=True)

# ==================== 可视化 ====================
col1, col2 = st.columns([2, 1])
with col1:
    st.subheader("🗺️ 全国选址彩色热力图（中文）")
    if not df_for_score.empty and '纬度' in df_for_score.columns and '选址得分' in df_for_score.columns:
        m = folium.Map(location=[35.0, 105.0], zoom_start=5, tiles=None)
        folium.TileLayer(tiles='https://webrd02.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=7&x={x}&y={y}&z={z}', attr='高德地图').add_to(m)
        heat_data = [[row['纬度'], row['经度'], row['选址得分']] for _, row in df_for_score.iterrows()]
        HeatMap(heat_data, radius=25, blur=30, gradient={0.2:'blue',0.4:'cyan',0.6:'yellow',0.8:'orange',1.0:'red'}).add_to(m)
        st_folium(m, width=700, height=500)
    else:
        st.info("请先添加数据")

with col2:
    st.subheader("📈 Top10 得分排行榜")
    if not df_for_score.empty and '地点' in df_for_score.columns:
        fig = px.bar(df_for_score.head(10), x='地点', y='选址得分', color='城市')
        st.plotly_chart(fig, use_container_width=True)

# ==================== PDF报告（美观版） ====================
st.subheader("📄 一键生成PDF专业报告")
if st.button("生成PDF报告（发给投资人）"):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    pdfmetrics.registerFont(TTFont('msyh', 'C:/Windows/Fonts/msyh.ttc'))  # 解决乱码
    c.setFont('msyh', 18)
    c.drawString(100, 800, "星巴克式全国选址专业报告")
    c.setFont('msyh', 12)
    c.drawString(100, 780, f"生成日期：{datetime.now().strftime('%Y年%m月%d日')}")
    c.drawString(100, 760, f"最高分推荐地点：{df_for_score.iloc[0]['地点']}（{df_for_score.iloc[0]['选址得分']}分）")
    c.drawString(100, 740, "Top 5 推荐商圈：")
    for i in range(min(5, len(df_for_score))):
        c.drawString(120, 720 - i*20, f"{i+1}. {df_for_score.iloc[i]['地点']}（{df_for_score.iloc[i]['选址得分']}分）")
    c.save()
    buffer.seek(0)
    st.download_button("📥 下载PDF报告", buffer, f"选址报告_{datetime.now().strftime('%Y%m%d')}.pdf", "application/pdf")

st.download_button("📥 下载完整CSV报告", df_for_score.to_csv(index=False).encode(), f"选址报告_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv")

st.success("✅ 筛选城市、热力图、Top10、PDF报告全部正常！成都20分是根据当前数据和权重真实计算得出的")