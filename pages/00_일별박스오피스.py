import pandas as pd
import plotly.express as px
import requests
import streamlit as st
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

st.set_page_config(page_title="박스오피스 대시보드", layout="wide")
st.title("🎬 박스오피스 기간별 집계 대시보드")

KOBIS_KEY = st.secrets["KOBIS_KEY"]

# 기준 가능한 가장 최근 날짜 (어제)
yesterday = datetime.now(ZoneInfo("Asia/Seoul")).date() - timedelta(days=1)
default_start = yesterday - timedelta(days=6)  # 기본값: 최근 일주일

# 1. 기간 선택 달력 피커 (시작일, 종료일)
date_range = st.date_input(
    "조회할 기간을 선택하세요 (시작일 ~ 종료일)",
    value=(default_start, yesterday),
    max_value=yesterday,
    help="박스오피스는 어제 날짜까지만 조회 가능합니다."
)

# 시작일과 종료일이 모두 선택되었는지 확인
if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = date_range
else:
    st.info("시작일과 종료일을 모두 선택해 주세요.")
    st.stop()

st.caption(f"조회 기간: {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}")

# 2. 선택한 기간 내 모든 날짜에 대해 API 호출
all_daily_data = []
current_date = start_date

# 로딩 바 표시
progress_text = "선택한 기간의 박스오피스 데이터를 불러오는 중입니다..."
my_bar = st.progress(0, text=progress_text)
total_days = (end_date - start_date).days + 1

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

my_bar.empty()  # 로딩 바 제거

# 데이터가 비어 있는 경우 처리
if not all_daily_data:
    st.warning("선택하신 기간의 집계 데이터가 없습니다.")
    st.stop()

# 데이터프레임 생성 및 숫자 변환
df_raw = pd.DataFrame(all_daily_data)
for col in ["audiCnt", "audiAcc", "scrnCnt", "showCnt"]:
    df_raw[col] = pd.to_numeric(df_raw[col])

# 3. 영화별 기간 합산 데이터 집계
# 영화코드(movieCd)와 영화명(movieNm) 기준 데이터 그룹화
df_summary = df_raw.groupby(["movieCd", "movieNm"]).agg(
    total_audiCnt=("audiCnt", "sum"),     # 기간 내 총 관객수
    max_audiAcc=("audiAcc", "max"),        # 기간 기준 최신 누적 관객수
    avg_scrnCnt=("scrnCnt", "mean"),       # 기간 평균 스크린수
    openDt=("openDt", "first")             # 개봉일
).reset_index()

# 기간 관객수 기준 내림차순 정렬
df_summary = df_summary.sort_values(by="total_audiCnt", ascending=False).reset_index(drop=True)
df_summary["rank"] = df_summary.index + 1

# 영화 상세정보 API 호출 (장르 가져오기 - 상위 10개만 효율적으로 가져오기)
top10_summary = df_summary.head(10).copy()
detail_url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/movie/searchMovieInfo.json"
genres = []

for movie_cd in top10_summary["movieCd"]:
    try:
        detail_res = requests.get(detail_url, params={"key": KOBIS_KEY, "movieCd": movie_cd}, timeout=5)
        movie_info = detail_res.json().get("movieInfoResult", {}).get("movieInfo", {})
        genre_list = [g["genreNm"] for g in movie_info.get("genres", [])]
        genres.append(", ".join(genre_list) if genre_list else "미상")
    except Exception:
        genres.append("미상")

top10_summary["genre"] = genres

# 4. 100만 관객 표시 (누적관객 기준)
def format_movie_title(row):
    title = row["movieNm"]
    if row["max_audiAcc"] >= 1_000_000:
        return f"{title} 🏆"
    return title

top10_summary["표시_영화명"] = top10_summary.apply(format_movie_title, axis=1)

# 상단 지표 카드 (기간 내 1위 영화)
top_movie = top10_summary.iloc[0]
c1, c2, c3 = st.columns(3)
c1.metric("기간 1위 영화", top_movie["표시_영화명"])
c2.metric("기간 내 모은 관객", f"{top_movie['total_audiCnt']:,}명")
c3.metric("최종 누적 관객", f"{top_movie['max_audiAcc']:,}명")

# 표 구성
table = top10_summary[["rank", "표시_영화명", "genre", "openDt", "total_audiCnt", "max_audiAcc"]].copy()
table.columns = ["기간순위", "영화명", "장르", "개봉일", "기간내 관객수", "누적관객수"]

st.subheader("📋 선택 기간 박스오피스 TOP 10")
st.dataframe(table, use_container_width=True)

# ---------------------------------------------------------
# 시각화 (Plotly 가로 막대 그래프)
# ---------------------------------------------------------
st.subheader("📈 기간 내 관객수 상위 5편")

top5 = top10_summary.sort_values("total_audiCnt", ascending=True).tail(5)

fig = px.bar(
    top5,
    x="total_audiCnt",
    y="표시_영화명",
    orientation="h",
    text_auto=",d",
    color="total_audiCnt",
    color_continuous_scale="Blues",
    hover_data={"total_audiCnt": ":,명", "max_audiAcc": ":,명"},
)

fig.update_layout(
    xaxis_title="기간 내 관객 수 (명)",
    yaxis_title="",
    coloraxis_showscale=False,
    height=380,
    margin=dict(l=20, r=20, t=30, b=20),
)

fig.update_traces(
    textposition="outside",
    cliponaxis=False
)

st.plotly_chart(fig, use_container_width=True)
