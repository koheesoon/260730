날짜 선택 피커 아래에 장르를 선택할 수 있는 셀렉트박스(드롭다운 목록)를 추가했습니다!

드롭다운에서 특정 장르(예: 액션, 애니메이션, 드라마 등)를 선택하면 해당 장르의 TOP 5 영화 표와 그래프만 깔끔하게 필터링되어 출력됩니다. 기본값인 전체 장르를 고르면 모든 영화 대상 TOP 5를 확인할 수 있습니다.

수정된 전체 코드
Python
import pandas as pd
import plotly.express as px
import requests
import streamlit as st
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

st.set_page_config(page_title="박스오피스 대시보드", layout="wide")
st.title("🎬 장르 & 기간별 박스오피스")

KOBIS_KEY = st.secrets["KOBIS_KEY"]

# 기준 가능한 가장 최근 날짜 (어제)
yesterday = datetime.now(ZoneInfo("Asia/Seoul")).date() - timedelta(days=1)
default_start = yesterday - timedelta(days=6)  # 기본값: 최근 일주일

# 1. 필터 영역 (기간 선택 & 장르 선택)
c_date, c_genre = st.columns([2, 1])

with c_date:
    date_range = st.date_input(
        "1. 조회할 기간을 선택하세요 (시작일 ~ 종료일)",
        value=(default_start, yesterday),
        max_value=yesterday,
        help="박스오피스는 어제 날짜까지만 조회 가능합니다."
    )

if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = date_range
else:
    st.info("시작일과 종료일을 모두 선택해 주세요.")
    st.stop()

# 2. 선택한 기간 동안의 daily 데이터 API 호출
all_daily_data = []
current_date = start_date
total_days = (end_date - start_date).days + 1

progress_text = "선택한 기간의 박스오피스 데이터를 불러오는 중입니다..."
my_bar = st.progress(0, text=progress_text)

url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"

for i in range(total_days):
    target_dt = current_date.strftime("%Y%m%d")
    res = requests.get(url, params={"key": KOBIS_KEY, "targetDt": target_dt}, timeout=10)
    
    if res.status_code == 200:
        data = res.json()
        if "faultInfo" in data:
            st.error("인증키가 올바르지 않습니다. 금고(Secrets)의 KOBIS_KEY를 확인해 주세요.")
            st.stop()
        
        box_list = data.get("boxOfficeResult", {}).get("dailyBoxOfficeList", [])
        if box_list:
            all_daily_data.extend(box_list)
            
    current_date += timedelta(days=1)
    my_bar.progress((i + 1) / total_days, text=progress_text)

my_bar.empty()

if not all_daily_data:
    st.warning("선택하신 기간의 집계 데이터가 없습니다.")
    st.stop()

# 데이터프레임 변환 및 수치 처리
df_raw = pd.DataFrame(all_daily_data)
for col in ["audiCnt", "audiAcc", "scrnCnt"]:
    df_raw[col] = pd.to_numeric(df_raw[col])

# 영화별 기간 합산 집계
df_summary = df_raw.groupby(["movieCd", "movieNm"]).agg(
    total_audiCnt=("audiCnt", "sum"),
    max_audiAcc=("audiAcc", "max"),
    openDt=("openDt", "first")
).reset_index()

# 3. 영화 상세정보 API 호출 (장르 수집)
detail_url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/movie/searchMovieInfo.json"
movie_genres = {}

with st.spinner("영화 장르 정보를 가져오는 중입니다..."):
    for movie_cd in df_summary["movieCd"]:
        try:
            detail_res = requests.get(detail_url, params={"key": KOBIS_KEY, "movieCd": movie_cd}, timeout=5)
            movie_info = detail_res.json().get("movieInfoResult", {}).get("movieInfo", {})
            g_list = [g["genreNm"] for g in movie_info.get("genres", [])]
            movie_genres[movie_cd] = g_list if g_list else ["기타"]
        except Exception:
            movie_genres[movie_cd] = ["기타"]

df_summary["genres"] = df_summary["movieCd"].map(movie_genres)

# 복수 장르를 개별 행으로 분리
df_exploded = df_summary.explode("genres").rename(columns={"genres": "genre"})

# 100만 관객 트로피 표시
def format_movie_title(row):
    title = row["movieNm"]
    if row["max_audiAcc"] >= 1_000_000:
        return f"{title} 🏆"
    return title

df_exploded["표시_영화명"] = df_exploded.apply(format_movie_title, axis=1)

# 추출된 전체 장르 목록 만들기 (드롭다운 용)
available_genres = sorted(list(df_exploded["genre"].unique()))
genre_options = ["전체 장르"] + available_genres

with c_genre:
    selected_genre = st.selectbox("2. 조회할 장르를 선택하세요", genre_options)

st.caption(f"조회 조건: {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')} | 장르: [{selected_genre}]")

# 4. 선택된 장르에 맞게 데이터 필터링
if selected_genre == "전체 장르":
    # 전체 장르일 때는 중복 분리 전 원본(df_summary) 데이터 기준
    filtered_df = df_summary.copy()
    filtered_df["표시_영화명"] = filtered_df.apply(format_movie_title, axis=1)
    filtered_df["genre_display"] = filtered_df["genres"].apply(lambda g: ", ".join(g))
else:
    # 특정 장르 선택 시 해당 장르만 필터링
    filtered_df = df_exploded[df_exploded["genre"] == selected_genre].copy()
    filtered_df["genre_display"] = selected_genre

# 관객수 기준 TOP 5 추출
top5_df = filtered_df.sort_values(by="total_audiCnt", ascending=False).head(5).reset_index(drop=True)

if top5_df.empty:
    st.warning("선택하신 조건에 해당하는 영화가 없습니다.")
    st.stop()

top5_df["순위"] = top5_df.index + 1

# 5. 결과 화면 (지표, 표, 그래프)
st.subheader(f"📊 [{selected_genre}] 관객수 TOP 5")

# 상단 지표 카드
top1 = top5_df.iloc[0]
c1, c2, c3 = st.columns(3)
c1.metric(f"{selected_genre} 1위", top1["표시_영화명"])
c2.metric("기간 내 관객수", f"{top1['total_audiCnt']:,}명")
c3.metric("최종 누적관객수", f"{top1['max_audiAcc']:,}명")

st.divider()

# 표 및 시각화 배치
col_table, col_chart = st.columns([3, 2])

with col_table:
    st.markdown("##### 📋 상위 5위 목록")
    display_table = top5_df[["순위", "표시_영화명", "genre_display", "openDt", "total_audiCnt", "max_audiAcc"]].copy()
    display_table.columns = ["순위", "영화명", "장르", "개봉일", "기간내 관객수", "누적 관객수"]
    
    # 천단위 콤마 포맷팅
    display_table["기간내 관객수"] = display_table["기간내 관객수"].apply(lambda x: f"{x:,}명")
    display_table["누적 관객수"] = display_table["누적 관객수"].apply(lambda x: f"{x:,}명")
    
    st.dataframe(display_table, use_container_width=True, hide_index=True)

with col_chart:
    st.markdown("##### 📈 관객수 비교")
    chart_data = top5_df.sort_values("total_audiCnt", ascending=True)
    
    fig = px.bar(
        chart_data,
        x="total_audiCnt",
        y="표시_영화명",
        orientation="h",
        text_auto=",d",
        color="total_audiCnt",
        color_continuous_scale="Blues"
    )
    fig.update_layout(
        height=280,
        margin=dict(l=10, r=10, t=20, b=10),
        xaxis_title="",
        yaxis_title="",
        coloraxis_showscale=False
    )
    fig.update_traces(textposition="outside", cliponaxis=False)
    st.plotly_chart(fig, use_container_width=True)
