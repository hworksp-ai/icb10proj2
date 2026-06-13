"""
네이버 오픈API 수집 및 분석 Streamlit 대시보드 (app.py)

이 파일은 Streamlit을 이용하여 네이버의 통합 검색어 트렌드, 쇼핑, 블로그, 카페글, 뉴스 검색 데이터를
수집하고 시각적으로 탐색 및 분석(EDA)하는 인터랙티브 대시보드 애플리케이션입니다.

주요 화면 및 시각화:
- Datalab 검색어 트렌드 분석 (Plotly Line Chart)
- 쇼핑 상품 통계 및 트렌드 (최저가 분포, 브랜드/제조사 점유율, Pareto 차트, 카테고리별 분석)
- 블로그, 뉴스, 카페글 수집 결과 및 일자별 발행 빈도
- 비정형 텍스트 분석: TF-IDF를 이용한 요약글 속 핵심 키워드 30개 추출 및 시각화
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import re
import os
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional
from sklearn.feature_extraction.text import TfidfVectorizer

# .env 파일 로드 (로컬 환경 지원)
load_dotenv()

# 네이버 API 클라이언트 임포트
from naver_api import NaverAPIClient

# Streamlit 페이지 기본 설정
st.set_page_config(
    page_title="네이버 API 데이터 수집 및 분석 대시보드",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -----------------------------------------------------------------------------
# 텍스트 전처리 및 TF-IDF 도구 정의
# -----------------------------------------------------------------------------
def clean_korean_text(text: Any) -> str:
    """HTML 태그 및 한글 이외의 특수 기호를 제거하는 정제 함수"""
    if not isinstance(text, str):
        return ""
    # 네이버 API 응답에 섞여 있는 HTML 굵게(<b>, </b>) 태그 제거
    text = re.sub(r'<[^>]+>', ' ', text)
    # 한글 및 공백을 제외한 문자 제거
    text = re.sub(r'[^가-힣\s]', ' ', text)
    # 중복 공백 제거
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

@st.cache_data
def analyze_tfidf(texts: List[str], top_n: int = 30) -> pd.DataFrame:
    """
    비정형 텍스트 코퍼스를 대상으로 TF-IDF를 분석하여 상위 단어들을 추출합니다.
    형태소 분석기 없이 빠르고 가볍게 단어 기반 빈도/가중치를 계산합니다.
    """
    cleaned_texts = [clean_korean_text(t) for t in texts if t]
    if not cleaned_texts or len(cleaned_texts) == 0:
        return pd.DataFrame(columns=["단어", "TF-IDF 점수"])
        
    # 최소 2글자 이상 10글자 이하의 단어들을 토큰화
    vectorizer = TfidfVectorizer(
        max_features=100,
        token_pattern=r'\b\w{2,10}\b',
        stop_words=["네이버", "검색", "블로그", "카페", "뉴스", "오늘", "진짜", "대한", "관련", "대해"]
    )
    
    try:
        tfidf_matrix = vectorizer.fit_transform(cleaned_texts)
        feature_names = vectorizer.get_feature_names_out()
        sums = tfidf_matrix.sum(axis=0)
        
        data = []
        for col, term in enumerate(feature_names):
            data.append({
                "단어": term,
                "TF-IDF 점수": round(float(sums[0, col]), 4)
            })
            
        df = pd.DataFrame(data)
        if not df.empty:
            df = df.sort_values(by="TF-IDF 점수", ascending=False).head(top_n)
        return df
    except Exception:
        # 텍스트 수가 너무 적거나 토큰화에 실패할 경우 빈 DataFrame 반환
        return pd.DataFrame(columns=["단어", "TF-IDF 점수"])

# -----------------------------------------------------------------------------
# 페이지 네비게이션 상태 초기화
# -----------------------------------------------------------------------------
if "current_page" not in st.session_state:
    st.session_state.current_page = "대시보드 소개"
# 네이버 API 자격증명 초기화 (우선순위: st.secrets -> os.environ -> "")
default_client_id = ""
default_client_secret = ""

try:
    if "NAVER_CLIENT_ID" in st.secrets:
        default_client_id = st.secrets["NAVER_CLIENT_ID"]
    if "NAVER_CLIENT_SECRET" in st.secrets:
        default_client_secret = st.secrets["NAVER_CLIENT_SECRET"]
except Exception:
    pass

if not default_client_id:
    default_client_id = os.getenv("NAVER_CLIENT_ID", "")
if not default_client_secret:
    default_client_secret = os.getenv("NAVER_CLIENT_SECRET", "")

if "naver_client_id" not in st.session_state:
    st.session_state["naver_client_id"] = default_client_id
if "naver_client_secret" not in st.session_state:
    st.session_state["naver_client_secret"] = default_client_secret

# 사이드바 CSS 스타일 (카테고리 그룹 + 버튼 스타일 네비게이션)
st.markdown("""
<style>
/* 네비게이션 카테고리 헤더 */
.nav-category {
    font-size: 0.75rem;
    font-weight: 700;
    color: #9ca3af;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    padding: 0.75rem 0 0.25rem 0;
    margin: 0;
}
/* 네비게이션 버튼 기본 스타일 */
[data-testid="stSidebar"] .stButton > button {
    width: 100%;
    text-align: left;
    background: transparent;
    border: 1px solid rgba(128,128,128,0.2);
    border-radius: 0.5rem;
    padding: 0.5rem 0.75rem;
    font-size: 0.9rem;
    color: inherit;
    cursor: pointer;
    transition: background 0.15s ease, border-color 0.15s ease;
    margin-bottom: 4px;
    opacity: 1 !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(128,128,128,0.15);
    border-color: rgba(128,128,128,0.4);
}
/* 선택된 페이지 버튼 강조 스타일 */
[data-testid="stSidebar"] .stButton > button[kind="primary"] {
    background: rgba(99, 102, 241, 0.2) !important;
    border-color: #6366f1 !important;
    color: #818cf8 !important;
    font-weight: 600;
}
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 사이드바 레이아웃
# -----------------------------------------------------------------------------
with st.sidebar:
    # 로고 / 타이틀
    st.markdown("## 📊 네이버 API 대시보드")
    st.markdown("---")

    # ── 안내 그룹 ──────────────────────────────────────────
    st.markdown('<p class="nav-category">안내</p>', unsafe_allow_html=True)

    def nav_button(label: str, page_name: str):
        """현재 선택 여부에 따라 강조 스타일이 달라지는 네비게이션 버튼"""
        is_active = st.session_state.current_page == page_name
        btn_type = "primary" if is_active else "secondary"
        if st.button(label, key=f"nav_{page_name}", type=btn_type, use_container_width=True):
            st.session_state.current_page = page_name

    nav_button("🏠  대시보드 소개", "대시보드 소개")

    st.markdown("")

    # ── 데이터랩 트렌드 분석 그룹 ─────────────────────────
    st.markdown('<p class="nav-category">데이터랩 트렌드 분석</p>', unsafe_allow_html=True)
    nav_button("📈  검색어 트렌드 분석", "검색어 트렌드 분석")
    nav_button("🛍️  쇼핑 트렌드 분석", "쇼핑 트렌드 분석")

    st.markdown("")

    # ── 검색 데이터 다차원 분석 그룹 ──────────────────────
    st.markdown('<p class="nav-category">검색 데이터 다차원 분석</p>', unsafe_allow_html=True)
    nav_button("🛒  쇼핑 검색 분석", "쇼핑 검색 분석")
    nav_button("📝  블로그 검색 분석", "블로그 검색 분석")
    nav_button("👥  카페글 검색 분석", "카페글 검색 분석")
    nav_button("📰  뉴스 검색 분석", "뉴스 검색 분석")

    st.markdown("---")

    # ── API 키 입력 ────────────────────────────────────────
    st.markdown("#### 🔑 네이버 API 설정")
    if default_client_id and default_client_secret:
        st.success("✅ API 키가 자동 설정되었습니다. (.env / Secrets)")
    else:
        st.text_input("Client ID", type="password", key="naver_client_id", help="네이버 개발자 센터에서 발급받은 ID를 입력하세요.")
        st.text_input("Client Secret", type="password", key="naver_client_secret", help="네이버 개발자 센터에서 발급받은 Secret을 입력하세요.")
    st.markdown("---")

    # ── 공통 검색 설정 ─────────────────────────────────────
    st.markdown("#### 🔍 수집 및 분석 제어")

    # 콤마(,) 구분으로 다중 키워드 입력받기
    keywords_input = st.text_input(
        "검색어 입력 (쉼표 , 로 구분)",
        value="스마트폰, 노트북, 태블릿",
        help="여러 검색어를 쉼표로 구분하여 입력해 주세요."
    )
    keywords = [k.strip() for k in keywords_input.split(",") if k.strip()]

    # 검색 기간 설정
    today = datetime.today()
    three_months_ago = today - timedelta(days=90)
    date_range = st.date_input(
        "검색 기간 설정",
        value=(three_months_ago, today),
        max_value=today,
        help="조회할 시작일과 종료일을 지정하세요. (최대 오늘 날짜까지)"
    )

    # 수집 건수 설정
    display_count = st.slider(
        "수집 건수 (검색어당)",
        min_value=10,
        max_value=100,
        value=50,
        step=10,
        help="API 1회당 조회할 최대 건수입니다."
    )

# -----------------------------------------------------------------------------
# 현재 페이지 및 API 키 가져오기
# -----------------------------------------------------------------------------
current_page = st.session_state.current_page
client_id = st.session_state.get("naver_client_id", "")
client_secret = st.session_state.get("naver_client_secret", "")

# -----------------------------------------------------------------------------
# 대시보드 소개 페이지 (API 키 없이도 볼 수 있음)
# -----------------------------------------------------------------------------
if current_page == "대시보드 소개":
    st.title("📊 네이버 API 통합 데이터 수집 및 분석 대시보드")
    st.markdown("네이버 검색 서비스와 트렌드 데이터를 실시간으로 수집하고 분석하는 스마트 대시보드입니다.")
    st.markdown("")

    col_a, col_b = st.columns(2)
    with col_a:
        st.info("**🏁 시작하는 방법**\n\n1. 왼쪽 사이드바에서 **네이버 API Client ID / Secret** 을 입력하세요.\n2. 분석할 **검색어** 를 쉼표로 구분하여 입력하세요.\n3. **검색 기간** 과 **수집 건수** 를 설정하세요.\n4. 왼쪽 메뉴에서 원하는 분석 페이지를 선택하세요.")
    with col_b:
        st.success("**📌 제공 기능**\n\n- 📈 검색어 트렌드 분석 (Datalab)\n- 🛍️ 쇼핑 트렌드 다차원 분석\n- 🛒 쇼핑 상품 검색 분석\n- 📝 블로그 게시글 분석\n- 👥 카페글 커뮤니티 분석\n- 📰 뉴스 기사 분석")

    st.markdown("---")
    st.markdown("#### 💡 API 키 발급 방법")
    st.markdown("""
    1. [네이버 개발자 센터](https://developers.naver.com/) 접속 및 로그인
    2. **Application > 애플리케이션 등록** 메뉴에서 새 앱 생성
    3. 사용할 API 선택: **Datalab(검색어트렌드)**, **검색 (쇼핑/블로그/뉴스/카페글)**
    4. 발급된 **Client ID** 와 **Client Secret** 을 왼쪽 사이드바에 입력
    """)
    st.stop()

# -----------------------------------------------------------------------------
# 이하 페이지는 API 키 필요 → 검증
# -----------------------------------------------------------------------------
if not client_id or not client_secret:
    st.warning("⚠️ 왼쪽 사이드바에서 네이버 API Client ID와 Client Secret을 입력해 주세요.")
    st.stop()

# API 클라이언트 초기화
client = NaverAPIClient(client_id, client_secret)

# 날짜 검증
if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date_str = date_range[0].strftime("%Y-%m-%d")
    end_date_str = date_range[1].strftime("%Y-%m-%d")
else:
    st.error("검색 기간 범위(시작일, 종료일)를 정확히 지정해 주세요.")
    st.stop()

if not keywords:
    st.warning("분석할 검색어를 최소 한 개 이상 입력해 주세요.")
    st.stop()

# 각 페이지별 조건부 렌더링
PAGE_TREND       = current_page == "검색어 트렌드 분석"
PAGE_SHOPPING    = current_page == "쇼핑 검색 분석"
PAGE_BLOG        = current_page == "블로그 검색 분석"
PAGE_NEWS        = current_page == "뉴스 검색 분석"
PAGE_CAFE        = current_page == "카페글 검색 분석"
PAGE_SHOP_TREND  = current_page == "쇼핑 트렌드 분석"

# -----------------------------------------------------------------------------
# 1. 검색어 트렌드 분석 페이지
# -----------------------------------------------------------------------------
if PAGE_TREND:
    st.header("📈 네이버 검색어 트렌드 (Datalab)")
    st.markdown("입력한 검색어들의 네이버 통합검색 내 기간별 검색 트렌드를 상댓값 비율(최대 100)로 분석합니다.")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        time_unit = st.selectbox("구간 단위", ["date", "week", "month"], index=0, format_func=lambda x: {"date": "일간", "week": "주간", "month": "월간"}[x])
    with col2:
        device_filter = st.selectbox("기기 필터", [None, "pc", "mo"], index=0, format_func=lambda x: {None: "모든 기기", "pc": "PC", "mo": "모바일"}[x])
    with col3:
        gender_filter = st.selectbox("성별 필터", [None, "m", "f"], index=0, format_func=lambda x: {None: "모든 성별", "m": "남성", "f": "여성"}[x])

    # Datalab API 구조상 그룹명과 검색어를 매칭해야 함
    # 편의상 각 입력 키워드명을 주제어로 하고, 그 하위 검색어를 자신으로 지정하여 1:1 매칭
    keywords_dict = {kw: [kw] for kw in keywords}

    if st.button("트렌드 데이터 수집 및 시각화", key="btn_trend"):
        with st.spinner("네이버 데이터랩 API로부터 트렌드 추이 수집 중..."):
            try:
                df_trend = client.get_search_trend(
                    keywords_dict=keywords_dict,
                    start_date=start_date_str,
                    end_date=end_date_str,
                    time_unit=time_unit,
                    device=device_filter,
                    gender=gender_filter
                )
                
                if df_trend.empty:
                    st.info("조회된 트렌드 데이터가 없습니다. 검색 조건이나 기간을 변경해 보세요.")
                else:
                    # 요약 통계 KPI
                    st.markdown("### 📊 주요 요약 지표")
                    kpi_cols = st.columns(len(keywords))
                    for i, kw in enumerate(keywords):
                        kw_df = df_trend[df_trend["주제어"] == kw]
                        if not kw_df.empty:
                            mean_ratio = kw_df["검색비율"].mean()
                            max_ratio = kw_df["검색비율"].max()
                            kpi_cols[i].metric(
                                label=f"🎯 {kw} 평균 비율",
                                value=f"{mean_ratio:.2f}%",
                                delta=f"최대 {max_ratio:.1f}%"
                            )
                    
                    # 시계열 추이 시각화 (Plotly)
                    st.markdown("### 📉 검색 추이 시계열 차트")
                    fig_line = px.line(
                        df_trend,
                        x="날짜",
                        y="검색비율",
                        color="주제어",
                        title="기간별 네이버 검색 상대 비율 변화 (최댓값 = 100)",
                        labels={"검색비율": "상대적 검색량 (%)", "날짜": "날짜"},
                        template="plotly_white"
                    )
                    fig_line.update_layout(hovermode="x unified")
                    st.plotly_chart(fig_line, use_container_width=True)
                    
                    # 데이터 테이블 표시 및 다운로드
                    st.markdown("### 📋 트렌드 원본 데이터")
                    st.dataframe(df_trend.sort_values(by=["날짜", "주제어"], ascending=[False, True]), use_container_width=True)
                    
            except Exception as e:
                st.error(f"데이터랩 API 호출 중 오류가 발생했습니다: {e}")

# -----------------------------------------------------------------------------
# 2. 쇼핑 검색 분석 페이지
# -----------------------------------------------------------------------------
if PAGE_SHOPPING:
    st.header("🛒 네이버 쇼핑 검색 분석")
    st.markdown("각 검색어에 대한 네이버 쇼핑 상품 정보를 수집하고 가격 분포 및 브랜드/제조사 시장 점유율을 분석합니다.")
    
    shopping_sort = st.selectbox(
        "정렬 방식", 
        ["sim", "date", "asc", "dsc"], 
        index=0, 
        format_func=lambda x: {"sim": "유사도순 (정확도)", "date": "날짜순", "asc": "가격 낮은순", "dsc": "가격 높은순"}[x]
    )

    if st.button("쇼핑 데이터 수집 및 분석", key="btn_shopping"):
        with st.spinner("네이버 쇼핑 API로부터 상품 수집 중..."):
            try:
                all_shop_df = []
                for kw in keywords:
                    df_kw = client.search_shopping(kw, display=display_count, sort=shopping_sort)
                    if not df_kw.empty:
                        df_kw["검색어"] = kw
                        all_shop_df.append(df_kw)
                
                if not all_shop_df:
                    st.info("수집된 쇼핑 데이터가 없습니다.")
                else:
                    df_shop = pd.concat(all_shop_df, ignore_index=True)
                    # HTML 태그 제거 작업 (상품명 등)
                    df_shop["상품명"] = df_shop["상품명"].apply(lambda x: re.sub(r'<[^>]+>', '', str(x)))
                    
                    # 1. KPI 카드 배치
                    st.markdown("### 📊 수집 상품 현황")
                    kpi_cols = st.columns(3)
                    kpi_cols[0].metric("총 수집 상품 수", f"{len(df_shop)} 건")
                    kpi_cols[1].metric("평균 최저가", f"{int(df_shop['최저가'].mean()):,} 원")
                    kpi_cols[2].metric("분석 대상 브랜드 수", f"{df_shop['브랜드'].nunique()} 개")
                    
                    # 2. 가격 분석 시각화 (Boxplot & Histogram)
                    st.markdown("### 💵 상품 최저가 가격 분포 분석")
                    col_chart1, col_chart2 = st.columns(2)
                    
                    with col_chart1:
                        fig_box = px.box(
                            df_shop, 
                            x="검색어", 
                            y="최저가", 
                            color="검색어",
                            title="키워드별 상품 최저 가격 분포 (Box Plot)",
                            labels={"최저가": "가격 (원)"},
                            points="all"
                        )
                        st.plotly_chart(fig_box, use_container_width=True)
                        st.caption("※ 각 상자는 데이터의 사분위수(IQR)를 나타내며, 점들은 개별 상품의 최저가입니다.")
                        
                    with col_chart2:
                        fig_hist = px.histogram(
                            df_shop, 
                            x="최저가", 
                            color="검색어", 
                            marginal="rug", 
                            barmode="overlay",
                            title="최저가 가격대별 상품 빈도 분포 (Histogram)",
                            labels={"최저가": "가격 (원)", "count": "상품 수"}
                        )
                        st.plotly_chart(fig_hist, use_container_width=True)
                        st.caption("※ 가격 분포의 왜도와 쏠림 현상을 시각적으로 확인할 수 있습니다.")

                    # 3. 브랜드 & 제조사 분석
                    st.markdown("### 🏢 브랜드 및 제조사 점유율")
                    col_brand1, col_brand2 = st.columns(2)
                    
                    with col_brand1:
                        # 결측치나 빈 문자열 제거 및 상위 10개 추출
                        brand_counts = df_shop[df_shop["브랜드"].str.strip() != ""].groupby(["검색어", "브랜드"]).size().reset_index(name="개수")
                        brand_counts = brand_counts.sort_values(by="개수", ascending=False)
                        
                        fig_brand_pie = px.pie(
                            brand_counts.head(15), 
                            values="개수", 
                            names="브랜드", 
                            color="검색어",
                            title="상위 15대 상품 브랜드 점유율",
                            hole=0.4
                        )
                        st.plotly_chart(fig_brand_pie, use_container_width=True)
                        
                    with col_brand2:
                        maker_counts = df_shop[df_shop["제조사"].str.strip() != ""].groupby(["검색어", "제조사"]).size().reset_index(name="개수")
                        maker_counts = maker_counts.sort_values(by="개수", ascending=False)
                        
                        fig_maker_bar = px.bar(
                            maker_counts.head(15), 
                            x="개수", 
                            y="제조사", 
                            color="검색어", 
                            orientation="h",
                            title="상위 15대 상품 제조사 빈도",
                            labels={"개수": "등록 상품 수", "제조사": "제조업체"}
                        )
                        fig_maker_bar.update_layout(yaxis={'categoryorder':'total ascending'})
                        st.plotly_chart(fig_maker_bar, use_container_width=True)

                    # 4. 쇼핑몰 점유율 분석
                    st.markdown("### 🏪 유통 쇼핑몰 빈도 분석")
                    mall_counts = df_shop.groupby("쇼핑몰").size().reset_index(name="상품수").sort_values(by="상품수", ascending=False).head(20)
                    fig_mall = px.bar(
                        mall_counts,
                        x="상품수",
                        y="쇼핑몰",
                        title="상위 20대 등록 유통 쇼핑몰",
                        labels={"상품수": "등록 상품 수", "쇼핑몰": "쇼핑몰 명"},
                        color="상품수",
                        color_continuous_scale=px.colors.sequential.Viridis
                    )
                    fig_mall.update_layout(yaxis={'categoryorder':'total ascending'})
                    st.plotly_chart(fig_mall, use_container_width=True)
                    
                    # 5. 데이터 목록
                    st.markdown("### 📋 수집 쇼핑 데이터 목록")
                    st.dataframe(
                        df_shop[["검색어", "상품명", "최저가", "최고가", "브랜드", "제조사", "쇼핑몰", "카테고리1", "카테고리2"]],
                        use_container_width=True
                    )
                    
            except Exception as e:
                st.error(f"쇼핑 API 호출 및 가공 중 오류 발생: {e}")

# -----------------------------------------------------------------------------
# 3. 블로그 검색 분석 페이지
# -----------------------------------------------------------------------------
if PAGE_BLOG:
    st.header("📝 네이버 블로그 검색 분석")
    st.markdown("블로그 포스트 내 작성 트렌드와 본문 요약의 TF-IDF 분석을 통해 핵심 관심사 키워드를 추출합니다.")
    
    col_bl_s, col_bl_d = st.columns(2)
    with col_bl_s:
        blog_sort = st.selectbox("블로그 정렬", ["sim", "date"], format_func=lambda x: {"sim": "유사도순", "date": "날짜순"}[x])

    if st.button("블로그 데이터 수집 및 분석", key="btn_blog"):
        with st.spinner("블로그 데이터 수집 중..."):
            try:
                all_blog_df = []
                for kw in keywords:
                    df_kw = client.search_blog(kw, display=display_count, sort=blog_sort)
                    if not df_kw.empty:
                        df_kw["검색어"] = kw
                        all_blog_df.append(df_kw)
                
                if not all_blog_df:
                    st.info("수집된 블로그 데이터가 없습니다.")
                else:
                    df_blog = pd.concat(all_blog_df, ignore_index=True)
                    df_blog["제목"] = df_blog["제목"].apply(lambda x: re.sub(r'<[^>]+>', '', str(x)))
                    df_blog["요약"] = df_blog["요약"].apply(lambda x: re.sub(r'<[^>]+>', '', str(x)))
                    
                    # 시계열 작성 분포
                    st.markdown("### 📅 일자별 블로그 글 작성 추이")
                    # 유효한 날짜만 집계
                    date_counts = df_blog[df_blog["작성일"].notna()].groupby(["작성일", "검색어"]).size().reset_index(name="작성수")
                    fig_blog_trend = px.line(
                        date_counts, 
                        x="작성일", 
                        y="작성수", 
                        color="검색어", 
                        title="검색어별 블로그 업로드 추이",
                        markers=True
                    )
                    st.plotly_chart(fig_blog_trend, use_container_width=True)
                    
                    # TF-IDF 텍스트 분석
                    st.markdown("### 🔤 TF-IDF 핵심 키워드 분석")
                    st.markdown("> **형태소 분석(KoNLPy) 생략형 TF-IDF 분석 기법**: 본문 요약문에 포함된 한글 텍스트 패턴을 TF-IDF 가중치 모델로 연산하여 상위 30개 핵심 화두를 찾아냅니다.")
                    
                    col_tfidf_ch, col_tfidf_tb = st.columns([2, 1])
                    
                    with col_tfidf_ch:
                        df_tfidf = analyze_tfidf(df_blog["요약"].tolist(), top_n=30)
                        if df_tfidf.empty or "단어" not in df_tfidf.columns:
                            st.info("텍스트가 부족하여 TF-IDF 키워드 분석을 진행할 수 없습니다.")
                        else:
                            fig_tfidf = px.bar(
                                df_tfidf, 
                                x="TF-IDF 점수", 
                                y="단어", 
                                orientation="h",
                                title="블로그 요약글 분석 상위 30개 핵심 키워드",
                                color="TF-IDF 점수",
                                color_continuous_scale=px.colors.sequential.Bluered
                            )
                            fig_tfidf.update_layout(yaxis={'categoryorder':'total ascending'})
                            st.plotly_chart(fig_tfidf, use_container_width=True)
                            
                    with col_tfidf_tb:
                        if not df_tfidf.empty:
                            st.markdown("**키워드 가중치 순위표**")
                            st.dataframe(df_tfidf.reset_index(drop=True), height=380, use_container_width=True)
                    
                    # 블로거 점유율
                    st.markdown("### 👤 주요 블로거 분포")
                    blogger_counts = df_blog.groupby("블로거").size().reset_index(name="작성수").sort_values(by="작성수", ascending=False).head(15)
                    fig_blogger = px.bar(blogger_counts, x="작성수", y="블로거", title="가장 많이 업로드한 블로거 Top 15")
                    fig_blogger.update_layout(yaxis={'categoryorder':'total ascending'})
                    st.plotly_chart(fig_blogger, use_container_width=True)
                    
                    # 데이터 테이블
                    st.markdown("### 📋 수집 블로그 데이터 목록")
                    st.dataframe(df_blog[["검색어", "제목", "요약", "블로거", "작성일"]], use_container_width=True)
            except Exception as e:
                st.error(f"블로그 데이터 분석 중 오류 발생: {e}")

# -----------------------------------------------------------------------------
# 4. 뉴스 검색 분석 페이지
# -----------------------------------------------------------------------------
if PAGE_NEWS:
    st.header("📰 네이버 뉴스 검색 분석")
    st.markdown("언론사 도메인 분포, 뉴스 게시 트렌드 및 기사 제목/요약 텍스트의 TF-IDF 분석을 수행합니다.")
    
    col_nw_s = st.selectbox("뉴스 정렬", ["sim", "date"], format_func=lambda x: {"sim": "유사도순", "date": "날짜순"}[x])

    if st.button("뉴스 데이터 수집 및 분석", key="btn_news"):
        with st.spinner("뉴스 데이터 수집 중..."):
            try:
                all_news_df = []
                for kw in keywords:
                    df_kw = client.search_news(kw, display=display_count, sort=col_nw_s)
                    if not df_kw.empty:
                        df_kw["검색어"] = kw
                        all_news_df.append(df_kw)
                
                if not all_news_df:
                    st.info("수집된 뉴스 데이터가 없습니다.")
                else:
                    df_news = pd.concat(all_news_df, ignore_index=True)
                    df_news["제목"] = df_news["제목"].apply(lambda x: re.sub(r'<[^>]+>', '', str(x)))
                    df_news["요약"] = df_news["요약"].apply(lambda x: re.sub(r'<[^>]+>', '', str(x)))
                    
                    # 1. 기사 발행 날짜 트렌드
                    st.markdown("### 📅 뉴스 기사 발행 추이")
                    df_news["게시날짜"] = df_news["게시일"].dt.date
                    news_trend = df_news.groupby(["게시날짜", "검색어"]).size().reset_index(name="기사수")
                    fig_news_trend = px.line(
                        news_trend, 
                        x="게시날짜", 
                        y="기사수", 
                        color="검색어", 
                        title="일자별 뉴스 보도 트렌드",
                        markers=True
                    )
                    st.plotly_chart(fig_news_trend, use_container_width=True)
                    
                    # 2. 언론사 분석 (원문링크의 호스트명 추출)
                    st.markdown("### 🏢 주요 언론사(출처) 분포")
                    def get_domain(url):
                        if not isinstance(url, str):
                            return "기타"
                        match = re.search(r'https?://([^/]+)', url)
                        return match.group(1) if match else "기타"
                    df_news["출처도메인"] = df_news["원문링크"].apply(get_domain)
                    domain_counts = df_news.groupby("출처도메인").size().reset_index(name="기사수").sort_values(by="기사수", ascending=False).head(15)
                    
                    fig_domain = px.bar(
                        domain_counts, 
                        x="기사수", 
                        y="출처도메인", 
                        title="상위 15개 뉴스 출처 도메인",
                        color="기사수",
                        color_continuous_scale=px.colors.sequential.Sunsetdark
                    )
                    fig_domain.update_layout(yaxis={'categoryorder':'total ascending'})
                    st.plotly_chart(fig_domain, use_container_width=True)
                    
                    # 3. TF-IDF 키워드 분석
                    st.markdown("### 🔤 뉴스 핵심 키워드 분석 (TF-IDF)")
                    col_news_tfidf_ch, col_news_tfidf_tb = st.columns([2, 1])
                    
                    # 제목과 요약을 합쳐서 텍스트 풍부하게 구성
                    news_corpus = (df_news["제목"] + " " + df_news["요약"]).tolist()
                    df_news_tfidf = analyze_tfidf(news_corpus, top_n=30)
                    
                    with col_news_tfidf_ch:
                        if df_news_tfidf.empty:
                            st.info("분석할 키워드가 부족합니다.")
                        else:
                            fig_news_tfidf = px.bar(
                                df_news_tfidf,
                                x="TF-IDF 점수",
                                y="단어",
                                orientation="h",
                                title="뉴스 기사 제목/요약 분석 핵심 키워드",
                                color="TF-IDF 점수",
                                color_continuous_scale=px.colors.sequential.Electric
                            )
                            fig_news_tfidf.update_layout(yaxis={'categoryorder':'total ascending'})
                            st.plotly_chart(fig_news_tfidf, use_container_width=True)
                            
                    with col_news_tfidf_tb:
                        if not df_news_tfidf.empty:
                            st.markdown("**뉴스 키워드 순위표**")
                            st.dataframe(df_news_tfidf.reset_index(drop=True), height=380, use_container_width=True)
                            
                    # 4. 데이터 목록
                    st.markdown("### 📋 수집 뉴스 데이터 목록")
                    st.dataframe(df_news[["검색어", "제목", "출처도메인", "게시일", "원문링크"]], use_container_width=True)
            except Exception as e:
                st.error(f"뉴스 데이터 분석 중 오류 발생: {e}")

# -----------------------------------------------------------------------------
# 5. 카페글 검색 분석 페이지
# -----------------------------------------------------------------------------
if PAGE_CAFE:
    st.header("☕ 네이버 카페글 검색 분석")
    st.markdown("카페 게시글의 수집 및 카페 커뮤니티 점유율 분석, TF-IDF 핵심 어휘 시각화를 제공합니다.")
    
    col_cf_s = st.selectbox("카페글 정렬", ["sim", "date"], format_func=lambda x: {"sim": "유사도순", "date": "날짜순"}[x])

    if st.button("카페 데이터 수집 및 분석", key="btn_cafe"):
        with st.spinner("카페 데이터 수집 중..."):
            try:
                all_cafe_df = []
                for kw in keywords:
                    df_kw = client.search_cafearticle(kw, display=display_count, sort=col_cf_s)
                    if not df_kw.empty:
                        df_kw["검색어"] = kw
                        all_cafe_df.append(df_kw)
                        
                if not all_cafe_df:
                    st.info("수집된 카페 데이터가 없습니다.")
                else:
                    df_cafe = pd.concat(all_cafe_df, ignore_index=True)
                    df_cafe["제목"] = df_cafe["제목"].apply(lambda x: re.sub(r'<[^>]+>', '', str(x)))
                    df_cafe["요약"] = df_cafe["요약"].apply(lambda x: re.sub(r'<[^>]+>', '', str(x)))
                    
                    # 1. 주요 네이버 카페 분포
                    st.markdown("### 👥 주요 출처 네이버 카페명 분포")
                    cafe_counts = df_cafe.groupby("카페명").size().reset_index(name="게시글수").sort_values(by="게시글수", ascending=False).head(15)
                    
                    fig_cafe_bar = px.bar(
                        cafe_counts, 
                        x="게시글수", 
                        y="카페명", 
                        title="가장 게시글이 많이 수집된 상위 15개 카페",
                        color="게시글수",
                        color_continuous_scale=px.colors.sequential.Agsunset
                    )
                    fig_cafe_bar.update_layout(yaxis={'categoryorder':'total ascending'})
                    st.plotly_chart(fig_cafe_bar, use_container_width=True)
                    
                    # 2. TF-IDF 키워드 분석
                    st.markdown("### 🔤 카페 요약문 키워드 분석 (TF-IDF)")
                    col_cafe_tfidf_ch, col_cafe_tfidf_tb = st.columns([2, 1])
                    
                    cafe_corpus = df_cafe["요약"].tolist()
                    df_cafe_tfidf = analyze_tfidf(cafe_corpus, top_n=30)
                    
                    with col_cafe_tfidf_ch:
                        if df_cafe_tfidf.empty:
                            st.info("분석할 키워드가 부족합니다.")
                        else:
                            fig_cafe_tfidf = px.bar(
                                df_cafe_tfidf,
                                x="TF-IDF 점수",
                                y="단어",
                                orientation="h",
                                title="카페글 요약글 분석 핵심 키워드",
                                color="TF-IDF 점수",
                                color_continuous_scale=px.colors.sequential.YlOrRd
                            )
                            fig_cafe_tfidf.update_layout(yaxis={'categoryorder':'total ascending'})
                            st.plotly_chart(fig_cafe_tfidf, use_container_width=True)
                            
                    with col_cafe_tfidf_tb:
                        if not df_cafe_tfidf.empty:
                            st.markdown("**카페 키워드 순위표**")
                            st.dataframe(df_cafe_tfidf.reset_index(drop=True), height=380, use_container_width=True)
                            
                    # 3. 데이터 목록
                    st.markdown("### 📋 수집 카페 데이터 목록")
                    st.dataframe(df_cafe[["검색어", "제목", "카페명", "링크"]], use_container_width=True)
            except Exception as e:
                st.error(f"카페 데이터 분석 중 오류 발생: {e}")

# -----------------------------------------------------------------------------
# 6. 쇼핑 트렌드 분석 페이지
# -----------------------------------------------------------------------------
if PAGE_SHOP_TREND:
    st.header("📊 쇼핑 시장 트렌드 및 다차원 관계 분석")
    st.markdown("쇼핑 상품 데이터를 다차원으로 결합하여 카테고리별 동향 및 브랜드의 시장 점유율 집중도(Pareto)를 정량적으로 분석합니다.")

    if st.button("쇼핑 트렌드 종합 분석 실행", key="btn_sh_trend"):
        with st.spinner("상품 정보를 수집하고 가공 분석 데이터셋을 작성하는 중..."):
            try:
                all_shop_df = []
                for kw in keywords:
                    df_kw = client.search_shopping(kw, display=display_count, sort="sim")
                    if not df_kw.empty:
                        df_kw["검색어"] = kw
                        all_shop_df.append(df_kw)
                        
                if not all_shop_df:
                    st.info("트렌드를 분석할 쇼핑 상품 데이터가 없습니다.")
                else:
                    df_shop = pd.concat(all_shop_df, ignore_index=True)
                    df_shop["상품명"] = df_shop["상품명"].apply(lambda x: re.sub(r'<[^>]+>', '', str(x)))
                    
                    # 1. 카테고리 대분류(카테고리1) 및 중분류(카테고리2) 점유율 분석
                    st.markdown("### 📂 상품 카테고리별 구조 분포")
                    col_cat1, col_cat2 = st.columns(2)
                    
                    with col_cat1:
                        cat1_counts = df_shop.groupby(["검색어", "카테고리1"]).size().reset_index(name="상품수")
                        fig_cat1 = px.sunburst(
                            cat1_counts, 
                            path=["검색어", "카테고리1"], 
                            values="상품수",
                            title="검색어 및 카테고리 대분류 계층 구조 (Sunburst)"
                        )
                        st.plotly_chart(fig_cat1, use_container_width=True)
                        
                    with col_cat2:
                        # 상위 15개 중분류 카테고리
                        cat2_counts = df_shop.groupby(["검색어", "카테고리2"]).size().reset_index(name="상품수")
                        cat2_counts = cat2_counts.sort_values(by="상품수", ascending=False).head(15)
                        fig_cat2 = px.bar(
                            cat2_counts, 
                            x="상품수", 
                            y="카테고리2", 
                            color="검색어",
                            title="상위 15대 카테고리 중분류(카테고리2) 분포",
                            orientation="h"
                        )
                        fig_cat2.update_layout(yaxis={'categoryorder':'total ascending'})
                        st.plotly_chart(fig_cat2, use_container_width=True)
                        
                    # 2. 카테고리별 평균 가격대 비교 분석
                    st.markdown("### 💵 카테고리 대분류별 평균 최저 가격 분석")
                    cat_price = df_shop.groupby("카테고리1")["최저가"].mean().reset_index(name="평균최저가").sort_values(by="평균최저가", ascending=False)
                    fig_cat_price = px.bar(
                        cat_price, 
                        x="카테고리1", 
                        y="평균최저가", 
                        title="카테고리별 평균 최저 판매가격 비교",
                        labels={"평균최저가": "평균 가격 (원)", "카테고리1": "대분류"},
                        color="평균최저가",
                        color_continuous_scale=px.colors.sequential.Mint
                    )
                    st.plotly_chart(fig_cat_price, use_container_width=True)
                    
                    # 3. 브랜드 시장 집중도 (Pareto 차트 분석)
                    # Pareto Chart (80/20 법칙): 브랜드 누적 점유율 분석
                    st.markdown("### 📈 브랜드 파레토 분석 (시장 집중도)")
                    st.markdown("> **파레토 법칙 (80/20)**: 시장에 출시된 전체 상품 수의 80%가 소수의 몇 개 지배적인 핵심 브랜드에 의해 구성되는지 확인하는 통계적 분석 기법입니다.")
                    
                    # 유효한 브랜드 정보 추출
                    valid_brands = df_shop[df_shop["브랜드"].str.strip() != ""]
                    if valid_brands.empty:
                        st.info("분석할 수 있는 유효 브랜드 정보가 상품에 등록되어 있지 않습니다.")
                    else:
                        brand_stats = valid_brands.groupby("브랜드").size().reset_index(name="빈도").sort_values(by="빈도", ascending=False)
                        brand_stats["누적빈도"] = brand_stats["빈도"].cumsum()
                        total_count = brand_stats["빈도"].sum()
                        brand_stats["누적비율"] = (brand_stats["누적빈도"] / total_count) * 100
                        
                        # 상위 20개 브랜드만 차트 표시
                        chart_data = brand_stats.head(20)
                        
                        fig_pareto = go.Figure()
                        # 바 차트 (빈도)
                        fig_pareto.add_trace(
                            go.Bar(
                                x=chart_data["브랜드"],
                                y=chart_data["빈도"],
                                name="등록 상품 수 (좌축)",
                                marker_color="rgb(55, 83, 109)"
                            )
                        )
                        # 라인 차트 (누적 비율)
                        fig_pareto.add_trace(
                            go.Scatter(
                                x=chart_data["브랜드"],
                                y=chart_data["누적비율"],
                                name="누적 점유율 % (우축)",
                                yaxis="y2",
                                mode="lines+markers",
                                marker_color="rgb(219, 64, 82)",
                                line=dict(width=3)
                            )
                        )
                        
                        fig_pareto.update_layout(
                            title="상위 20개 브랜드의 시장 누적 점유율 (Pareto Chart)",
                            xaxis=dict(title="브랜드명"),
                            yaxis=dict(title="등록 상품 수 (건)"),
                            yaxis2=dict(
                                title="누적 비율 (%)",
                                overlaying="y",
                                side="right",
                                range=[0, 105]
                            ),
                            template="plotly_white",
                            legend=dict(x=0.01, y=0.99)
                        )
                        
                        st.plotly_chart(fig_pareto, use_container_width=True)
                        
                        # 해석 텍스트 동적 제공
                        top_brand_name = brand_stats.iloc[0]["브랜드"]
                        top_brand_share = (brand_stats.iloc[0]["빈도"] / total_count) * 100
                        st.write(f"📝 **분석 결과**: 수집된 브랜드 중 가장 높은 점유율을 차지하는 브랜드는 **'{top_brand_name}'**이며, 전체 상품 수 중 약 **{top_brand_share:.1f}%**의 점유율을 독점하고 있습니다.")
            except Exception as e:
                st.error(f"쇼핑 트렌드 종합 분석 중 오류 발생: {e}")
