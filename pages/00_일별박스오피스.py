import pandas as pd
import plotly.express as px
import requests
import streamlit as st
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

st.set_page_config(page_title="박스오피스 대시보드", layout="wide")
st.title("🎬 어제의 박스오피스")

# 비밀 금고에서 인증키 꺼내기
KOBIS_KEY = st.secrets["KOBIS_KEY"]

# 한국 시간 기준 어제 날짜
yesterday = datetime.now(ZoneInfo("Asia/Seoul")) - timedelta(days=1)
target_dt = yesterday.strftime("%Y%m%d")
st.caption(f"조회 기준일(어제): {yesterday.strftime('%Y-%m-%d')}")

url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
res = requests.get(url, params={"key": KOBIS_KEY, "targetDt": target_dt}, timeout=10)

if res.status_code != 200:
    st.error(f"요청이 실패했습니다 (상태코드: {res.status_code})")
    st.stop()

data = res.json()

if "faultInfo" in data:
    st.error("인증키가 올바르지 않습니다. 금고(Secrets)의 KOBIS_KEY를 확인해 주세요.")
    st.stop()

box_list = data.get("boxOfficeResult", {}).get("dailyBoxOfficeList", [])
if not box_list:
    st.warning("그날 자료가 없습니다. 날짜를 하루 더 앞으로 옮겨 보세요.")
    st.stop()

df = pd.DataFrame(box_list)

# 숫자 데이터 변환
for col in ["rank", "audiCnt", "audiAcc", "scrnCnt", "showCnt"]:
    df[col] = pd.to_numeric(df[col])

# 1위 영화 지표 카드
top = df.sort_values("rank").iloc[0]
c1, c2, c3 = st.columns(3)
c1.metric("어제 1위", top["movieNm"])
c2.metric("어제 관객수", f"{top['audiCnt']:,}명")
c3.metric("누적 관객", f"{top['audiAcc']:,}명")

# 표 정리
table = df[["rank", "movieNm", "openDt", "audiCnt", "audiAcc", "scrnCnt"]].copy()
table.columns = ["순위", "영화명", "개봉일", "관객수", "누적관객", "스크린수"]
table = table.sort_values("순위").reset_index(drop=True)

st.subheader("📋 박스오피스 TOP 10")
st.dataframe(table, use_container_width=True)

# ---------------------------------------------------------
# 시각화 개선 섹션 (Plotly 적용)
# ---------------------------------------------------------
st.subheader("📈 관객수 상위 5편 시각화")

top5 = table.sort_values("관객수", ascending=True).tail(5) # 가로 막대는 관객수 많은 순이 위로 오도록 오름차순 정렬

# Plotly 가로 막대 그래프 생성
fig = px.bar(
    top5,
    x="관객수",
    y="영화명",
    orientation="h",
    text_auto=",d",  # 막대 끝에 숫자 천단위 콤마 표시
    color="관객수",  # 관객수에 따라 색상 그라데이션 적용
    color_continuous_scale="Blues",  # 테마 색상 (Viridis, Teal, Redor 등 변경 가능)
    hover_data={"관객수": ":,명", "누적관객": ":,명", "스크린수": ":,개"},
)

# 그래프 레이아웃 세부 조정
fig.update_layout(
    xaxis_title="어제 관객 수 (명)",
    yaxis_title="",
    coloraxis_showscale=False,  # 색상 범주 바 숨기기
    height=380,
    margin=dict(l=20, r=20, t=30, b=20),
)

# 막대 내부/외부 텍스트 위치 및 스타일 조정
fig.update_traces(
    textposition="outside",
    cliponaxis=False
)

st.plotly_chart(fig, use_container_width=True)
