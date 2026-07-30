import streamlit as st

# st.set_page_config의 올바른 옵션명은 'layout'입니다.
st.set_page_config(
    page_title="전국 시군구별 청소년 인구 비율 지도",
    layout="wide"
)

import pandas as pd
import requests
import plotly.express as px

st.title("🗺️ 전국 시군구별 청소년(10~19세) 인구 비율 지도")
st.caption("최신 연도 데이터 기준 전국 시군구별 10세 이상 20세 미만 인구 비율을 5단계 푸른색 계열 단계구분도로 나타냅니다.")

# -----------------------------------------------------------------------------
# 1. 데이터 불러오기 함수
# -----------------------------------------------------------------------------
@st.cache_data
def load_data():
    pop_url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz"
    df = pd.read_csv(pop_url, compression='gzip', dtype={'코드': str})
    
    geo_url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/boundaries/sigungu_kr.geojson"
    geojson = requests.get(geo_url).json()
    
    return df, geojson

with st.spinner("전국 인구 및 지도 데이터를 불러오는 중입니다..."):
    df_raw, geojson_data = load_data()

# -----------------------------------------------------------------------------
# 2. 데이터 전처리
# -----------------------------------------------------------------------------
latest_year = int(df_raw['연도'].max())
df_latest = df_raw[df_raw['연도'] == latest_year].copy()

# 시군구 코드 (앞 5자리 추출)
df_latest['sigungu_code'] = df_latest['코드'].str[:5]

# 10세 이상 20세 미만 인구 열 목록
age_cols_10_19 = [f'계_{i}세' for i in range(10, 20)]
all_total_cols = [col for col in df_latest.columns if col.startswith('계_')]

# 시군구 단위 인구 합산
df_grouped = df_latest.groupby(['sigungu_code', '시도', '시군구'], as_index=False)[all_total_cols].sum()

df_grouped['총인구'] = df_grouped[all_total_cols].sum(axis=1)
df_grouped['청소년인구'] = df_grouped[age_cols_10_19].sum(axis=1)
df_grouped['청소년비율'] = (df_grouped['청소년인구'] / df_grouped['총인구']) * 100
df_grouped['청소년비율_표시'] = df_grouped['청소년비율'].round(2)

# -----------------------------------------------------------------------------
# 3. 5단계 구간 나누기
# -----------------------------------------------------------------------------
bins = [0, 19, 23, 28, 38, 100]
labels = ['19% 미만', '19% 이상 ~ 23% 미만', '23% 이상 ~ 28% 미만', '28% 이상 ~ 38% 미만', '38% 이상']

df_grouped['비율구간'] = pd.cut(
    df_grouped['청소년비율'], 
    bins=bins, 
    labels=labels, 
    right=False
)

# -----------------------------------------------------------------------------
# 4. Plotly 지도 생성 (푸른색 계열 5단계)
# -----------------------------------------------------------------------------
color_discrete_map = {
    '19% 미만': '#f7fbff',
    '19% 이상 ~ 23% 미만': '#c6dbef',
    '23% 이상 ~ 28% 미만': '#6baed6',
    '28% 이상 ~ 38% 미만': '#2171b5',
    '38% 이상': '#08306b'
}

fig = px.choropleth_mapbox(
    df_grouped,
    geojson=geojson_data,
    locations='sigungu_code',
    featureidkey='properties.코드',
    color='비율구간',
    color_discrete_map=color_discrete_map,
    category_orders={'비율구간': labels},
    hover_name='시군구',
    hover_data={
        '시도': True,
        '청소년비율_표시': True,
        'sigungu_code': False,
        '비율구간': False
    },
    labels={
        '청소년비율_표시': '청소년 비율(%)',
        '시도': '시도'
    },
    mapbox_style="white-bg",
    center={"lat": 35.90775, "lon": 127.766922},
    zoom=6.2,
    opacity=0.85
)

fig.update_traces(marker_line_width=0.6, marker_line_color="#444444")
fig.update_layout(
    margin={"r":0, "t":10, "l":0, "b":0},
    legend_title_text="청소년 비율 구간",
    height=650
)

st.subheader(f"📌 {latest_year}년 전국 시군구별 청소년 인구 비율 단계구분도")
st.plotly_chart(fig, use_container_width=True)

# -----------------------------------------------------------------------------
# 5. 하단 데이터 테이블 (상위 10개 / 하위 10개)
# -----------------------------------------------------------------------------
st.markdown("---")

df_display = df_grouped[['시도', '시군구', '청소년비율_표시', '총인구', '청소년인구']].copy()
df_display.columns = ['시도', '시군구', '청소년 비율(%)', '총 인구수', '청소년 인구수']

col1, col2 = st.columns(2)

with col1:
    st.subheader("🔝 청소년 비율 높은 곳 TOP 10")
    top_10 = df_display.sort_values(by='청소년 비율(%)', ascending=False).head(10).reset_index(drop=True)
    st.dataframe(top_10, use_container_width=True)

with col2:
    st.subheader("🔻 청소년 비율 낮은 곳 TOP 10")
    bottom_10 = df_display.sort_values(by='청소년 비율(%)', ascending=True).head(10).reset_index(drop=True)
    st.dataframe(bottom_10, use_container_width=True)
