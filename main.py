import streamlit as st

# Streamlit 설정은 스크립트 실행 최상단에 위치해야 합니다.
st.set_page_config(
    page_title="전국 시군구별 청소년 인구 비율 지도",
    page_layout="wide"
)

import pandas as pd
import requests
import plotly.express as px

st.title("🗺️ 전국 시군구별 청소년(10~19세) 인구 비율 지도")
st.caption("최신 연도 데이터 기준 전국 시군구별 10세 이상 20세 미만 인구 비율을 5단계 푸른색 계열 단계구분도로 나타냅니다.")

# -----------------------------------------------------------------------------
# 1. 데이터 불러오기 함수 (캐싱 적용으로 로딩 속도 최적화)
# -----------------------------------------------------------------------------
@st.cache_data
def load_data():
    # 인구 데이터 URL
    pop_url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz"
    # '코드' 열은 10자리 문자열(str)로 읽어 오발생 방지
    df = pd.read_csv(pop_url, compression='gzip', dtype={'코드': str})
    
    # 전국 시군구 GeoJSON 데이터 URL
    geo_url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/boundaries/sigungu_kr.geojson"
    geojson = requests.get(geo_url).json()
    
    return df, geojson

with st.spinner("전국 인구 및 지도 데이터를 불러오는 중입니다..."):
    df_raw, geojson_data = load_data()

# -----------------------------------------------------------------------------
# 2. 데이터 전처리
# -----------------------------------------------------------------------------
# (1) 가장 최신 연도 추출
latest_year = int(df_raw['연도'].max())

# (2) 최신 연도 데이터만 필터링
df_latest = df_raw[df_raw['연도'] == latest_year].copy()

# (3) 행정동 코드(10자리)의 앞 5자리를 잘라서 시군구 코드(sigungu_code) 생성
df_latest['sigungu_code'] = df_latest['코드'].str[:5]

# (4) 10세 이상 20세 미만(10세~19세) '계_' 인구 열 이름 목록 생성
age_cols_10_19 = [f'계_{i}세' for i in range(10, 20)]

# (5) 전체 인구('계_'로 시작하는 모든 열) 목록 추출
all_total_cols = [col for col in df_latest.columns if col.startswith('계_')]

# (6) 시군구 코드 단위로 그룹화하여 인구수 합산
# (시도, 시군구 명칭을 함께 유지하기 위해 그룹화 키에 포함)
df_grouped = df_latest.groupby(['sigungu_code', '시도', '시군구'], as_index=False)[all_total_cols].sum()

# (7) 시군구별 총인구수 및 10~19세 청소년 인구수 계산
df_grouped['총인구'] = df_grouped[all_total_cols].sum(axis=1)
df_grouped['청소년인구'] = df_grouped[age_cols_10_19].sum(axis=1)

# (8) 청소년 비율(%) 계산 및 소수점 둘째 자리 표기용 열 생성
df_grouped['청소년비율'] = (df_grouped['청소년인구'] / df_grouped['총인구']) * 100
df_grouped['청소년비율_표시'] = df_grouped['청소년비율'].round(2)

# -----------------------------------------------------------------------------
# 3. 5단계 구간 나눔 (19% 미만, 19~23%, 23~28%, 28~38%, 38% 이상)
# -----------------------------------------------------------------------------
bins = [0, 19, 23, 28, 38, 100]
labels = ['19% 미만', '19% 이상 ~ 23% 미만', '23% 이상 ~ 28% 미만', '28% 이상 ~ 38% 미만', '38% 이상']

# 지정한 구간 경계값으로 데이터 범주화
df_grouped['비율구간'] = pd.cut(
    df_grouped['청소년비율'], 
    bins=bins, 
    labels=labels, 
    right=False
)

# -----------------------------------------------------------------------------
# 4. Plotly 지도 생성 (푸른색 계열 5단계)
# -----------------------------------------------------------------------------
# 낮은 쪽(옅은 푸른색)에서 높은 쪽(진한 푸른색)으로 이어지는 5단계 매핑
color_discrete_map = {
    '19% 미만': '#f7fbff',
    '19% 이상 ~ 23% 미man': '#c6dbef',
    '19% 이상 ~ 23% 미만': '#c6dbef',
    '23% 이상 ~ 28% 미만': '#6baed6',
    '28% 이상 ~ 38% 미만': '#2171b5',
    '38% 이상': '#08306b'
}

fig = px.choropleth_mapbox(
    df_grouped,
    geojson=geojson_data,
    locations='sigungu_code',         # 데이터의 5자리 시군구 코드
    featureidkey='properties.코드',    # GeoJSON의 5자리 시군구 코드 속성
    color='비율구간',                  # 5단계 범주형 색상 기준
    color_discrete_map=color_discrete_map,
    category_orders={'비율구간': labels}, # 범례 순서 고정
    hover_name='시군구',              # 툴팁 제목
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
    mapbox_style="white-bg",          # 지도 타일 배경 없이 경계선 중심
    center={"lat": 35.90775, "lon": 127.766922},  # 대한민국 중앙 좌표
    zoom=6.2,                         # 한반도 전체가 보이도록 확대 정도 설정
    opacity=0.85
)

# 지도 외곽선 및 레이아웃 설정
fig.update_traces(marker_line_width=0.6, marker_line_color="#444444")
fig.update_layout(
    margin={"r":0, "t":10, "l":0, "b":0},
    legend_title_text="청소년 비율 구간",
    height=650
)

# Streamlit 화면에 지도 출력
st.subheader(f"📌 {latest_year}년 전국 시군구별 청소년 인구 비율 단계구분도")
st.plotly_chart(fig, use_container_width=True)

# -----------------------------------------------------------------------------
# 5. 하단 데이터 테이블 (비율 높은 곳 TOP 10 / 비율 낮은 곳 TOP 10)
# -----------------------------------------------------------------------------
st.markdown("---")

# 표 출력용 데이터 정리
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
