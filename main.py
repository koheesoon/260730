import streamlit as st

# Streamlit 최상단 설정은 반드시 최상위에 위치해야 합니다!
st.set_page_config(
    page_title="충남 청소년 인구 비율 지도",
    page_layout="wide"
)

import pandas as pd
import requests
import plotly.express as px

st.title("🗺️ 충청남도 시군구별 청소년(10~19세) 인구 비율 지도")
st.caption("최신 연도 데이터 기준 시군구별 10세 이상 20세 미만 인구 비율을 5단계로 나타냅니다.")

# -----------------------------------------------------------------------------
# 1. 데이터 불러오기 함수 (캐싱 적용)
# -----------------------------------------------------------------------------
@st.cache_data
def load_data():
    # 인구 데이터 URL
    pop_url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz"
    
    # 코드를 10자리 문자열(str)로 읽기 위해 dtype 지정
    df = pd.read_csv(pop_url, compression='gzip', dtype={'코드': str})
    
    # 시군구 GeoJSON 데이터 URL
    geo_url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/boundaries/sigungu_kr.geojson"
    geojson = requests.get(geo_url).json()
    
    return df, geojson

with st.spinner("데이터를 불러오는 중입니다..."):
    df_raw, geojson_data = load_data()

# -----------------------------------------------------------------------------
# 2. 데이터 전처리
# -----------------------------------------------------------------------------
# (1) 가장 최신 연도 추출
latest_year = df_raw['연도'].max()

# (2) 최신 연도 데이터 및 충청남도 데이터만 필터링
df_cn = df_raw[(df_raw['연도'] == latest_year) & (df_raw['시도'] == '충청남도')].copy()

# (3) 행정동 코드 앞 5자리를 잘라서 시군구 코드(sigungu_code) 생성
df_cn['sigungu_code'] = df_cn['코드'].str[:5]

# (4) 10세 이상 20세 미만(10세~19세) '계_' 인구 열 이름 목록 생성
age_cols_10_19 = [f'계_{i}세' for i in range(10, 20)]

# (5) 전체 인구('계_0세'부터 '계_100세 이상'까지) 계산을 위한 전체 '계_' 열 목록 추출
all_total_cols = [col for col in df_cn.columns if col.startswith('계_')]

# (6) 시군구 코드 단위로 그룹화하여 인구 합산
df_grouped = df_cn.groupby(['sigungu_code', '시도', '시군구'], as_index=False)[
    all_total_cols
].sum()

# (7) 총인구수 및 10~19세 인구수 계산
df_grouped['총인구'] = df_grouped[all_total_cols].sum(axis=1)
df_grouped['청소년인구'] = df_grouped[age_cols_10_19].sum(axis=1)

# (8) 청소년 비율(%) 계산
df_grouped['청소년비율'] = (df_grouped['청소년인구'] / df_grouped['총인구']) * 100
df_grouped['청소년비율_표시'] = df_grouped['청소년비율'].round(2)

# -----------------------------------------------------------------------------
# 3. 범주화 (5단계 끊기: ~19%, ~23%, ~28%, ~38%, 38%~)
# -----------------------------------------------------------------------------
bins = [0, 19, 23, 28, 38, 100]
labels = ['19% 미만', '19% 이상 ~ 23% 미만', '23% 이상 ~ 28% 미만', '28% 이상 ~ 38% 미만', '38% 이상']

# 지정한 구간으로 데이터 나누기
df_grouped['비율구간'] = pd.cut(
    df_grouped['청소년비율'], 
    bins=bins, 
    labels=labels, 
    right=False
)

# -----------------------------------------------------------------------------
# 4. Plotly 지도가 인식할 수 있도록 GeoJSON 필터링
# -----------------------------------------------------------------------------
cn_codes = set(df_grouped['sigungu_code'])

filtered_features = [
    feat for feat in geojson_data['features'] 
    if feat['properties']['코드'] in cn_codes
]
cn_geojson = {
    "type": "FeatureCollection",
    "features": filtered_features
}

# -----------------------------------------------------------------------------
# 5. Plotly 지도 생성
# -----------------------------------------------------------------------------
# 범주형 색상 팔레트 (연한 색 -> 진한 색)
color_discrete_map = {
    '19% 미만': '#edf8fb',
    '19% 이상 ~ 23% 미만': '#b2e2e2',
    '23% 이상 ~ 28% 미만': '#66c2a4',
    '28% 이상 ~ 38% 미만': '#2ca25f',
    '38% 이상': '#006d2c'
}

fig = px.choropleth_mapbox(
    df_grouped,
    geojson=cn_geojson,
    locations='sigungu_code',         # 데이터의 시군구 코드
    featureidkey='properties.코드',    # GeoJSON의 5자리 코드 속성
    color='비율구간',                  # 5단계 범주형 열
    color_discrete_map=color_discrete_map,
    category_orders={'비율구간': labels}, # 범례 순서 고정
    hover_name='시군구',              # 툴팁 제목
    hover_data={
        '시도': True,
        '청소년비율_표시': True,
        'sigungu_code': False,
        '비율구간': False
    },
    labels={'청소년비율_표시': '청소년 비율(%)'},
    mapbox_style="white-bg",          # 타일 배경 없이 경계선 중심
    center={"lat": 36.5184, "lon": 126.8000},  # 충남 중심 좌표
    zoom=8.2,
    opacity=0.8
)

# 지도 스타일 및 바운더리 선 설정
fig.update_traces(marker_line_width=1, marker_line_color="black")
fig.update_layout(
    margin={"r":0, "t":10, "l":0, "b":0},
    legend_title_text="청소년 비율 구간",
    height=550
)

# Streamlit 화면에 지도 표시
st.subheader(f"📌 {latest_year}년 충청남도 시군구별 청소년 인구 비율")
st.plotly_chart(fig, use_container_width=True)

# -----------------------------------------------------------------------------
# 6. 하단 데이터 테이블 (상위 10개 / 하위 10개)
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
