
import streamlit as st
import pandas as pd
import requests
import json
import numpy as np

# Streamlit 페이지 설정
st.set_page_config(
    page_title="충남 청소년 인구 비율 지도",
    page_layout="wide"
)

st.title("🗺️ 충청남도 시군구별 청소년(10~19세) 인구 비율 지도")
st.caption("2015~2026년 전국 읍·면·동 인구 데이터를 기준으로 시군구별 10세 이상 20세 미만 인구 비율을 5단계로 나타냅니다.")

# -----------------------------------------------------------------------------
# 1. 데이터 불러오기 함수 (캐싱 적용으로 속도 향상)
# -----------------------------------------------------------------------------
@st.cache_data
def load_data():
    # 인구 데이터 URL
    pop_url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz"
    # 코드를 10자리 문자열(str)로 읽기 위해 dtype 지정
    df = pd.read_csv(pop_url, compression='gzip', dtype={'코드': str})
    
    # 시군구 GeoJSON 데이터 URL
    geo_url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/boundaries/sigungu_kr.geojson"
    geojson_raw = requests.get(geo_url).json()
    
    return df, geojson_raw

with st.spinner("데이터를 불러오는 중입니다..."):
    df_raw, geojson_raw = load_data()

# -----------------------------------------------------------------------------
# 2. 데이터 전처리
# -----------------------------------------------------------------------------
# (1) 가장 최신 연도 추출
latest_year = df_raw['연도'].max()

# (2) 최신 연도 데이터 및 충청남도 데이터만 필터링
df_cn = df_raw[(df_raw['연도'] == latest_year) & (df_raw['시도'] == '충청남도')].copy()

# (3) 행정동 코드(10자리)에서 시군구 코드(5자리) 추출
# 문자열 공백 제거 및 앞 5자리 추출
df_cn['시군구코드'] = df_cn['코드'].str.strip().str[:5]

# (4) 10세 이상 20세 미만(10세~19세) '계_' 인구 열 이름 목록 생성
age_cols_10_19 = [f'계_{i}세' for i in range(10, 20)]

# (5) 전체 인구('계_0세'부터 '계_100세 이상'까지) 계산을 위한 전체 '계_' 열 목록 추출
all_total_cols = [col for col in df_cn.columns if col.startswith('계_')]

# (6) 시군구 코드 단위로 그룹화하여 인구 합산
df_grouped = df_cn.groupby(['시군구코드', '시도', '시군구'], as_index=False)[
    all_total_cols
].sum()

# (7) 총인구수 및 10~19세 인구수 계산
df_grouped['총인구'] = df_grouped[all_total_cols].sum(axis=1)
df_grouped['청소년인구'] = df_grouped[age_cols_10_19].sum(axis=1)

# (8) 청소년 비율(%) 계산 및 소수점 둘째 자리 반올림 열 생성
df_grouped['청소년비율'] = (df_grouped['청소년인구'] / df_grouped['총인구']) * 100
df_grouped['청소년비율_표시'] = df_grouped['청소년비율'].round(2)

# (9) 데이터 매핑을 위한 열 이름 변경
df_grouped.rename(columns={'시군구코드': '코드'}, inplace=True)

# -----------------------------------------------------------------------------
# 3. GeoJSON 전처리 (Plotly 매핑 강화)
# -----------------------------------------------------------------------------
# GeoJSON의 각 Feature에 'id' 속성을 추가하여 데이터 프레임의 '코드'와 직접 매핑
# 'properties' 안의 '코드' 값을 'id'로 사용
for feature in geojson_raw['features']:
    feature['id'] = feature['properties']['코드']

# -----------------------------------------------------------------------------
# 4. 범주화 (5단계 끊기: ~19%, ~23%, ~28%, ~38%, 38%~)
# -----------------------------------------------------------------------------
bins = [0, 19, 23, 28, 38, np.inf]
labels = ['19% 미만', '19% 이상 ~ 23% 미만', '23% 이상 ~ 28% 미만', '28% 이상 ~ 38% 미만', '38% 이상']

# 지정한 구간으로 데이터 나누기 (오른쪽 구간 포함 안 함)
df_grouped['비율구간'] = pd.cut(
    df_grouped['청소년비율'], 
    bins=bins, 
    labels=labels, 
    right=False
)

# -----------------------------------------------------------------------------
# 5. Plotly 지도 생성
# -----------------------------------------------------------------------------
import plotly.express as px

# 범주형 색상 팔레트 (연한 색 -> 진한 색, 5단계 푸른색 계열)
color_discrete_map = {
    '19% 미만': '#edf8fb',
    '19% 이상 ~ 23% 미만': '#b2e2e2',
    '23% 이상 ~ 28% 미만': '#66c2a4',
    '28% 이상 ~ 38% 미만': '#2ca25f',
    '38% 이상': '#006d2c'
}

# 충남 중심 좌표 및 줌 레벨 설정 (세부 조정됨)
cn_center = {"lat": 36.63, "lon": 126.85}
cn_zoom = 8.5

fig = px.choropleth_mapbox(
    df_grouped,
    geojson=geojson_raw,            # 전처리된 GeoJSON 데이터
    locations='코드',               # 데이터 프레임의 매핑 열
    # featureidkey='id',             # GeoJSON에서 'id'를 직접 찾음 (생략 가능)
    color='비율구간',                  # 5단계 범주형 열
    color_discrete_map=color_discrete_map,
    category_orders={'비율구간': labels}, # 범례 순서 고정
    hover_name='시군구',              # 툴팁 제목
    hover_data={
        '시도': True,
        '청소년비율_표시': True,
        '코드': False,
        '비율구간': False
    },
    labels={'청소년비율_표시': '청소년 비율(%)'},
    mapbox_style="white-bg",          # 타일 배경 없이 경계선 중심
    center=cn_center,
    zoom=cn_zoom,
    opacity=0.9,                      # 불투명도를 높임
    color_discrete_sequence=px.colors.qualitative.Prism, # 예비용
)

# 지도 스타일 및 바운더리 선 설정
fig.update_traces(marker_line_width=1.5, marker_line_color="#7f7f7f") # 경계선 스타일 수정
fig.update_layout(
    margin={"r":0, "t":10, "l":0, "b":0},
    legend_title_text="청소년 비율 구간",
    height=600 # 지도 높이 조정
)

# Streamlit 화면에 지도 표시
st.subheader(f"📌 {latest_year}년 충청남도 시군구별 청소년 인구 비율")
st.plotly_chart(fig, use_container_width=True)

# -----------------------------------------------------------------------------
# 6. 하단 데이터 테이블 (상위 10개 / 하위 10개)
# -----------------------------------------------------------------------------
st.markdown("---")

# 보여줄 열 정리 및 소수점 포맷팅
df_display = df_grouped[['시도', '시군구', '청소년비율_표시', '총인구', '청소년인구']].copy()
df_display.columns = ['시도', '시군구', '청소년 비율(%)', '총 인구수', '청소년 인구수']

col1, col2 = st.columns(2)

# 표 스타일 설정을 위한 함수
def format_table(df, title):
    st.subheader(title)
    # 총 인구수, 청소년 인구수 천 단위 구분 기호 표시
    formatted_df = df.style.format({
        '총 인구수': '{:,}',
        '청소년 인구수': '{:,}',
        '청소년 비율(%)': '{:.2f}'
    })
    st.dataframe(formatted_df, use_container_width=True, hide_index=True)

with col1:
    top_10 = df_display.sort_values(by='청소년 비율(%)', ascending=False).head(10)
    format_table(top_10, "🔝 청소년 비율 높은 곳 TOP 10")

with col2:
    bottom_10 = df_display.sort_values(by='청소년 비율(%)', ascending=True).head(10)
    format_table(bottom_10, "🔻 청소년 비율 낮은 곳 TOP 10")
