import pandas as pd
import plotly.express as px
import requests
import streamlit as st
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

st.set_page_config(page_title="박스오피스 대시보드", layout="wide")
st.title("🎬 박스오피스 대시보드")

# 비밀 금고에서 인증키 꺼내기
KOBIS_KEY = st.secrets["KOBIS_KEY"]

# 1. 날짜 선택 기능 (최대 선택 가능 날짜: 어제)
yesterday = datetime.now(ZoneInfo("Asia/Seoul")).date() - timedelta(days=1)

selected_date = st.date_input(
    "조회할 날짜를 선택하세요",
    value=yesterday,
    max_value=yesterday,
    help="박스오피스는 어제 날짜까지만 조회 가능합니다."
)

target_dt = selected_date.strftime("%Y%m%d")
st.caption(f"조회 기준일: {selected_date.strftime('%Y-%m-%d')}")

# 일별 박스오피스 API 호출
url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
res = requests.get(url, params={"key": KOBIS_KEY, "targetDt": target_dt}, timeout=10)

if res.status_code != 200:
    st.error(f"요청이 실패했습니다 (상태코드: {res.status_code})")
    st.stop()

data = res.json()

# KOBIS faultInfo 처리
if "faultInfo" in data:
    st.error("인증키가 올바르지 않습니다. 금고(Secrets)의 KOBIS_KEY를 확인해 주세요.")
    st.stop()

box_list = data.get("boxOfficeResult", {}).get("dailyBoxOfficeList", [])

# 2. 고른 날짜에 데이터가 없을 경우 안내 문구
if not box_list:
    st.warning("그날은 아직 집계 전입니다.")
    st.stop()

df = pd.DataFrame(box_list)

# 숫자 데이터 변환 (rankInten 추가)
for col in ["rank", "rankInten", "audiCnt", "audiAcc", "scrnCnt", "showCnt"]:
    df[col] = pd.to_numeric(df[col])

# 영화 상세정보 API를 호출하여 장르(genreNm) 가져오기
detail_url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/movie/searchMovieInfo.json"
genres = []

for movie_cd in df["movieCd"]:
    try:
        detail_res = requests.get(detail_url, params={"key": KOBIS_KEY, "movieCd": movie_cd}, timeout=5)
        movie_info = detail_res.json().get("movieInfoResult", {}).get("movieInfo", {})
        genre_list = [g["genreNm"] for g in movie_info.get("genres", [])]
        genres.append(", ".join(genre_list) if genre_list else "미상")
    except Exception:
        genres.append("미상")

df["genre"] = genres

# 3. rankInten 활용 순위 증감 표시 포맷팅 함수
def format_rank_change(row):
    rank = row["rank"]
    inten = row["rankInten"]
    is_new = row.get("rankOldAndNew") == "NEW"
    
    if is_new:
        return f"{rank} (🆕 NEW)"
    elif inten > 0:
        return f"{rank} (🔺{inten})"  # 오른 영화 (빨간 위 화살표)
    elif inten < 0:
        return f"{rank} (🔹{abs(inten)})"  # 내린 영화 (파란 아래 화살표)
    else:
        return f"{rank} (-)"

df["순위(증감)"] = df.apply(format_rank_change, axis=1)

# 4. 누적관객 100만 명 이상 트로피 이모지 붙이기
def format_movie_title(row):
    title = row["movieNm"]
    if row["audiAcc"] >= 1_000_000:
        return f"{title} 🏆"
    return title

df["표시_영화명"] = df.apply(format_movie_title, axis=1)

# 1위 영화 지표 카드
top = df.sort_values("rank").iloc[0]
c1, c2, c3 = st.columns(3)
c1.metric("해당 일자 1위", top["표시_영화명"])
c2.metric("당일 관객수", f"{top['audiCnt']:,}명")
c3.metric("누적 관객", f"{top['audiAcc']:,}명")

# 표 정리
table = df[["순위(증감)", "표시_영화명", "genre", "openDt", "audiCnt", "audiAcc", "scrnCnt"]].copy()
table.columns = ["순위", "영화명", "장르", "개봉일", "당일관객수", "누적관객", "스크린수"]

st.subheader("📋 박스오피스 TOP 10")
st.dataframe(table, use_container_width=True)

# ---------------------------------------------------------
# 시각화 섹션 (Plotly 적용)
# ---------------------------------------------------------
st.subheader("📈 관객수 상위 5편 시각화")

# 차트용 데이터 (영화명에 트로피 포함)
top5 = df.sort_values("audiCnt", ascending=True).tail(5)

fig = px.bar(
    top5,
    x="audiCnt",
    y="표시_영화명",
    orientation="h",
    text_auto=",d",
    color="audiCnt",
    color_continuous_scale="Blues",
    hover_data={"audiCnt": ":,명", "audiAcc": ":,명", "scrnCnt": ":,개"},
)

fig.update_layout(
    xaxis_title="당일 관객 수 (명)",
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
