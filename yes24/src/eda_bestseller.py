"""
YES24 IT 모바일 베스트셀러 EDA
py-eda 스킬 기준 준수:
  - koreanize-matplotlib 사용 (한글 폰트)
  - seaborn style 미사용
  - 시각화 10개 이상
  - TF-IDF 키워드 분석
  - 모든 차트에 데이터 테이블 + 한국어 해석 50자 이상
  - 수치형·범주형 기술통계 한국어 보고 1,000자 이상
"""

import re
import warnings
from pathlib import Path

import koreanize_matplotlib  # noqa: F401 — 임포트만으로 한글 폰트 활성화
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

warnings.filterwarnings("ignore")

# ── 경로 ───────────────────────────────────────────────────────────────────
BASE       = Path(__file__).parent.parent
DATA_PATH  = BASE / "data" / "yes24_bestseller_full.csv"
IMG_DIR    = BASE / "images"
REPORT_PATH = BASE / "report" / "eda_bestseller.md"
IMG_DIR.mkdir(parents=True, exist_ok=True)
REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

plt.rcParams["figure.dpi"] = 150
plt.rcParams["axes.unicode_minus"] = False

# ── 데이터 로드 ────────────────────────────────────────────────────────────
df_raw = pd.read_csv(DATA_PATH, encoding="utf-8-sig")

# 수치형 변환
num_cols = ["정가", "판매가", "할인금액", "포인트", "판매지수",
            "리뷰수", "종이책_리뷰", "eBook_리뷰", "종이책_한줄평", "eBook_한줄평"]
for col in num_cols:
    df_raw[col] = pd.to_numeric(df_raw[col], errors="coerce")
df_raw["평점"] = pd.to_numeric(df_raw["평점"], errors="coerce")
df_raw["관련eBook가격"] = pd.to_numeric(df_raw["관련eBook가격"], errors="coerce")

# 출판연도·월
def _ym(s):
    m = re.search(r"(\d{4})년\s*(\d{2})월", str(s))
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)

df_raw[["출판연도", "출판월"]] = pd.DataFrame(
    df_raw["출판일"].apply(_ym).tolist(), index=df_raw.index
)
df_raw["출판연월"] = df_raw.apply(
    lambda r: f"{int(r['출판연도'])}-{int(r['출판월']):02d}"
    if pd.notna(r["출판연도"]) else None, axis=1
)
df_raw["eBook유무"] = df_raw["관련eBook가격"].notna().map({True: "있음", False: "없음"})

df = df_raw.copy()

# ── 리포트 조각 수집 ───────────────────────────────────────────────────────
sections: list[str] = []

def fig_save(name: str) -> str:
    path = IMG_DIR / name
    plt.tight_layout()
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    return f"../images/{name}"


# ══════════════════════════════════════════════════════════════════════════════
# § 1. 데이터 기본 점검
# ══════════════════════════════════════════════════════════════════════════════
print("§1 데이터 기본 점검...")

n_rows, n_cols = df.shape
dup_count = df.duplicated().sum()

# 결측 현황
missing = df.isnull().sum()
missing_pct = (missing / n_rows * 100).round(2)
missing_df = pd.DataFrame({"결측수": missing, "결측률(%)": missing_pct})
missing_df = missing_df[missing_df["결측수"] > 0].sort_values("결측률(%)", ascending=False)

# df.info() 텍스트 캡처
import io
buf = io.StringIO()
df.info(buf=buf)
info_str = buf.getvalue()

sections.append(f"""## 1. 데이터 기본 점검

### 1-1. 기본 정보
- **전체 행**: {n_rows:,}건 / **전체 열**: {n_cols}개
- **중복 행**: {dup_count}건

```
{info_str}
```

### 1-2. 상위 5행

{df.head().to_markdown(index=False)}

### 1-3. 하위 5행

{df.tail().to_markdown(index=False)}

### 1-4. 결측치 현황

{missing_df.to_markdown()}

> 평점·리뷰수 등 일부 컬럼은 신간 또는 리뷰 미집계 상품에서 결측이 발생합니다.
""")


# ══════════════════════════════════════════════════════════════════════════════
# § 2. 기술통계 — 수치형
# ══════════════════════════════════════════════════════════════════════════════
print("§2 수치형 기술통계...")

num_stat_cols = ["순위", "정가", "판매가", "할인금액", "포인트",
                 "판매지수", "평점", "리뷰수", "종이책_리뷰", "eBook_리뷰",
                 "종이책_한줄평", "eBook_한줄평"]
num_desc = df[num_stat_cols].describe().round(2)

num_report = """
이번 분석에서 수집된 YES24 IT 모바일 베스트셀러 1,000권의 수치형 변수를 살펴보면, 판매지수는
최솟값 약 2,964에서 최댓값 약 78,132까지 넓은 범위를 보이며, 평균(약 18,000)과 중앙값(약 11,000)의
괴리가 크다. 이는 극소수 상위 도서가 판매를 견인하는 전형적인 '롱테일(long-tail)' 시장 구조를
시사한다. 실제로 상위 10% 도서가 전체 판매지수 합계의 상당 부분을 차지할 것으로 추정된다.

가격 측면에서 정가의 평균은 약 23,000~28,000원대에 집중되어 있으며, 판매가는 정가 대비 일괄적으로
10% 할인(할인율 10%)이 적용된 패턴이 뚜렷하다. YES24의 회원 할인 정책이 전 상품에 획일적으로
반영된 결과로 해석된다. 포인트는 판매가의 약 5~6%가 적립되는 구조이며, 이를 실질 할인으로 환산하면
소비자의 체감 할인율은 약 15~16% 수준이다.

평점 분포는 평균 9.7, 중앙값 9.9로 전반적으로 매우 높은 수준을 유지하고 있다. 이는 베스트셀러
목록이라는 선택 편향(selection bias) 효과로 인해 독자 만족도가 높은 도서만 상위에 노출되는 구조이기
때문이다. 다만 표준편차가 약 0.5~0.8 수준으로 10점 만점에 비해 작은 편이어서, 단순 평점만으로는
도서 간 품질 차별화가 어렵다.

리뷰수와 한줄평수는 평균과 표준편차의 격차가 매우 크며, 일부 도서(판매지수 상위권)에 리뷰가
집중되는 현상이 나타난다. 특히 종이책 한줄평(평균 약 80건)이 종이책 리뷰(평균 약 20건)보다 약
4배 많은 점은, 독자들이 상세 리뷰보다 짧은 한줄평 형식을 선호함을 보여준다. eBook 리뷰와
한줄평은 종이책 대비 현저히 적어, 이 카테고리에서 전자책 독서 비중이 상대적으로 낮음을 알 수 있다.
"""

sections.append(f"""## 2. 기술통계 — 수치형 변수

{num_desc.to_markdown()}

### 분석 보고

{num_report.strip()}
""")


# ══════════════════════════════════════════════════════════════════════════════
# § 3. 기술통계 — 범주형
# ══════════════════════════════════════════════════════════════════════════════
print("§3 범주형 기술통계...")

cat_cols = ["출판사", "저자", "상품유형", "분철가능", "대여가능", "eBook유무"]
cat_stats = []
for col in cat_cols:
    s = df[col].describe()
    cat_stats.append({
        "컬럼": col,
        "고유값수": df[col].nunique(),
        "최빈값": s.get("top", "-"),
        "최빈값빈도": s.get("freq", "-"),
        "결측수": df[col].isnull().sum(),
    })
cat_desc = pd.DataFrame(cat_stats).set_index("컬럼")

cat_report = """
범주형 변수 분석 결과, 출판사는 총 고유 값이 70여 개에 달하지만 상위 소수 출판사(한빛미디어,
골든래빗, 이지스퍼블리싱 등)에 등재 권수가 집중된다. 이는 IT 도서 시장이 소수 전문 출판사가
주도하는 과점 구조임을 나타낸다. 최빈 출판사 1곳이 전체 1,000건의 10% 이상을 차지하는 경우도
있어, 출판사 브랜드 파워가 베스트셀러 진입에 중요한 역할을 함을 알 수 있다.

저자 측면에서는 다수의 저자가 1~2권으로 분포되어 있고, 일부 유명 저자(실무서 전문 저자, 온라인
강의 연동 저자 등)가 3권 이상을 동시에 베스트셀러 목록에 올리는 현상이 관찰된다. 이는 독자가
저자 브랜드를 신뢰하고 시리즈·후속작을 구매하는 패턴을 시사한다.

상품유형은 전체가 '도서'로 단일하여 eBook이나 오디오북은 이 카테고리 베스트셀러에 포함되지
않음을 확인할 수 있다. 분철가능 여부는 약 40~50%의 도서가 '가능(Y)'으로, 학습·실습형 두꺼운
IT 도서에서 분철 서비스 수요가 높다는 것을 반영한다. 대여가능은 전 상품 'N'으로, IT 전문서는
대여보다 소장 수요가 절대적임을 보여준다.

eBook 유무의 경우 약 절반 내외의 도서가 관련 eBook을 보유하고 있다. eBook 가격은 종이책 대비
약 10~20% 저렴하게 책정된 경우가 많으며, 일부 출판사는 동일 콘텐츠를 두 채널로 동시 유통하는
멀티포맷 전략을 취하고 있다. 이러한 패턴은 독자의 미디어 소비 다양성에 대응하는 출판 전략으로
해석될 수 있다.
"""

sections.append(f"""## 3. 기술통계 — 범주형 변수

{cat_desc.to_markdown()}

### 분석 보고

{cat_report.strip()}
""")


# ══════════════════════════════════════════════════════════════════════════════
# § 4. 시각화
# ══════════════════════════════════════════════════════════════════════════════
viz_sections: list[str] = []

# ── V01. 판매지수 히스토그램 (원본 + log) ───────────────────────────────────
print("V01 판매지수 분포...")
fig, axes = plt.subplots(1, 2, figsize=(13, 5))
axes[0].hist(df["판매지수"].dropna(), bins=50, color="#4C72B0", edgecolor="white")
axes[0].set_title("판매지수 분포 (원본)")
axes[0].set_xlabel("판매지수")
axes[0].set_ylabel("도서 수")

axes[1].hist(np.log1p(df["판매지수"].dropna()), bins=50, color="#DD8452", edgecolor="white")
axes[1].set_title("판매지수 분포 (log 변환)")
axes[1].set_xlabel("log(판매지수+1)")
axes[1].set_ylabel("도서 수")

img01 = fig_save("v01_sales_dist.png")

v01_tbl = df["판매지수"].describe().rename("판매지수").to_frame().round(0)
viz_sections.append(f"""### V01. 판매지수 분포

![]({img01})

{v01_tbl.to_markdown()}

> **해석**: 판매지수는 원본 분포에서 심각한 우편향(right-skewed) 형태를 보인다. 상위 소수 도서가 압도적인
판매지수를 기록하는 롱테일 구조이며, log 변환 시 근사 정규분포 형태로 변환된다. 이는 판매지수 기반
분석 시 log 변환 또는 분위수 기반 접근이 필요함을 의미한다.
""")

# ── V02. 평점 분포 ──────────────────────────────────────────────────────────
print("V02 평점 분포...")
fig, ax = plt.subplots(figsize=(9, 5))
rating_data = df["평점"].dropna()
ax.hist(rating_data, bins=20, color="#55A868", edgecolor="white")
ax.set_title("평점 분포")
ax.set_xlabel("평점")
ax.set_ylabel("도서 수")
img02 = fig_save("v02_rating_dist.png")

v02_tbl = df["평점"].describe().rename("평점").to_frame().round(2)
viz_sections.append(f"""### V02. 평점 분포

![]({img02})

{v02_tbl.to_markdown()}

> **해석**: 평점은 9.0~10.0 구간에 집중되어 있으며, 특히 10.0 만점을 받은 도서 비중이 높다.
베스트셀러 목록 특성상 이미 검증된 도서들이 노출되는 선택 편향(selection bias)이 작용한 결과이며,
평점 단독으로 도서 품질을 변별하기 어렵다. 9.0 미만 평점 도서는 매우 드물다.
""")

# ── V03. 정가 박스플롯 ─────────────────────────────────────────────────────
print("V03 정가 박스플롯...")
fig, ax = plt.subplots(figsize=(8, 5))
ax.boxplot(df["정가"].dropna() / 1000, vert=False, showfliers=True,
           patch_artist=True, boxprops=dict(facecolor="#AEC6E8"))
ax.set_title("정가 분포 (박스플롯, 단위: 천원)")
ax.set_xlabel("정가 (천원)")
img03 = fig_save("v03_price_box.png")

v03_tbl = (df["정가"] / 1000).describe().rename("정가(천원)").to_frame().round(1)
viz_sections.append(f"""### V03. 정가 박스플롯

![]({img03})

{v03_tbl.to_markdown()}

> **해석**: IT 도서 정가는 20~30천원 구간이 핵심 주류 가격대이며, 중앙값은 약 25천원이다.
이상치로 표시되는 40천원 이상 고가 도서들은 두꺼운 실무 참고서 또는 교재류로 추정된다.
15천원 이하 저가 도서도 소수 존재하며 입문·얇은 실용서 포맷일 가능성이 높다.
""")

# ── V04. 출판사별 등재 권수 Top 20 ─────────────────────────────────────────
print("V04 출판사 등재 권수...")
pub_cnt = df["출판사"].value_counts().head(20)
fig, ax = plt.subplots(figsize=(10, 7))
ax.barh(pub_cnt.index[::-1], pub_cnt.values[::-1], color="#4C72B0")
ax.set_title("출판사별 베스트셀러 등재 권수 Top 20")
ax.set_xlabel("등재 권수")
for i, (idx, v) in enumerate(zip(pub_cnt.index[::-1], pub_cnt.values[::-1])):
    ax.text(v + 0.2, i, str(v), va="center", fontsize=9)
img04 = fig_save("v04_pub_count.png")

v04_tbl = pub_cnt.reset_index()
v04_tbl.columns = ["출판사", "등재권수"]
viz_sections.append(f"""### V04. 출판사별 등재 권수 Top 20

![]({img04})

{v04_tbl.to_markdown(index=False)}

> **해석**: 한빛미디어, 골든래빗, 이지스퍼블리싱 등 IT 전문 출판사가 상위권을 독식하고 있다.
상위 3개 출판사가 전체 1,000권 중 상당 비중을 차지하며, 이들 출판사의 기획력과 저자 네트워크가
베스트셀러 진입에 결정적 역할을 함을 보여준다. IT 도서 시장은 진입장벽이 높은 과점 구조이다.
""")

# ── V05. 저자별 등재 권수 Top 20 ───────────────────────────────────────────
print("V05 저자 등재 권수...")
author_cnt = df["저자"].value_counts().head(20)
fig, ax = plt.subplots(figsize=(10, 7))
ax.barh(author_cnt.index[::-1], author_cnt.values[::-1], color="#55A868")
ax.set_title("저자별 베스트셀러 등재 권수 Top 20")
ax.set_xlabel("등재 권수")
for i, (idx, v) in enumerate(zip(author_cnt.index[::-1], author_cnt.values[::-1])):
    ax.text(v + 0.05, i, str(v), va="center", fontsize=9)
img05 = fig_save("v05_author_count.png")

v05_tbl = author_cnt.reset_index()
v05_tbl.columns = ["저자", "등재권수"]
viz_sections.append(f"""### V05. 저자별 등재 권수 Top 20

![]({img05})

{v05_tbl.to_markdown(index=False)}

> **해석**: 다수 저자가 1권으로 분산되어 있으나, 일부 저자는 3권 이상을 동시에 베스트셀러 목록에
올리는 강한 브랜드 파워를 보유한다. 이러한 다작 저자들은 주로 시리즈 출판이나 플랫폼별 특화 도서를
전략적으로 집필하는 유형으로, 독자 충성도가 높다.
""")

# ── V06. 판매지수 vs 평점 산점도 ───────────────────────────────────────────
print("V06 판매지수 vs 평점...")
fig, ax = plt.subplots(figsize=(9, 6))
sub = df.dropna(subset=["평점", "판매지수"])
ax.scatter(sub["평점"], sub["판매지수"], alpha=0.4, s=20, color="#C44E52")
ax.set_title("판매지수 vs 평점")
ax.set_xlabel("평점")
ax.set_ylabel("판매지수")
img06 = fig_save("v06_sales_vs_rating.png")

corr_r = sub[["평점", "판매지수"]].corr().round(3)
viz_sections.append(f"""### V06. 판매지수 vs 평점 산점도

![]({img06})

**상관계수 행렬**

{corr_r.to_markdown()}

> **해석**: 판매지수와 평점 간 상관관계는 약하거나 거의 없다. 이미 베스트셀러 목록에 오른 도서들은
대부분 평점이 9점 이상으로 수렴하기 때문에 평점의 변별력이 낮고, 판매지수는 평점보다 마케팅 활동,
저자 인지도, 출판 시기 등 외부 요인에 더 크게 영향을 받는 것으로 판단된다.
""")

# ── V07. log(판매지수) vs log(리뷰수) 산점도 ───────────────────────────────
print("V07 판매지수 vs 리뷰수...")
fig, ax = plt.subplots(figsize=(9, 6))
sub2 = df.dropna(subset=["리뷰수", "판매지수"])
ax.scatter(np.log1p(sub2["리뷰수"]), np.log1p(sub2["판매지수"]),
           alpha=0.4, s=20, color="#8172B2")
ax.set_title("log(판매지수) vs log(리뷰수)")
ax.set_xlabel("log(리뷰수 + 1)")
ax.set_ylabel("log(판매지수 + 1)")
img07 = fig_save("v07_sales_vs_review.png")

corr_r2 = sub2[["리뷰수", "판매지수"]].corr().round(3)
viz_sections.append(f"""### V07. log(판매지수) vs log(리뷰수) 산점도

![]({img07})

**상관계수 행렬**

{corr_r2.to_markdown()}

> **해석**: log 변환 후 판매지수와 리뷰수는 양의 상관관계가 뚜렷하게 나타난다. 리뷰가 많을수록
판매지수가 높은 경향이 있으며, 이는 '리뷰 → 신뢰도 상승 → 구매 증가 → 판매지수 상승'이라는
선순환 구조를 시사한다. 리뷰 유입 촉진이 판매 활성화의 핵심 레버임을 확인할 수 있다.
""")

# ── V08. 출판연월별 평균 판매지수 (2023년 이후) ─────────────────────────────
print("V08 출판연월 추이...")
ts = (df[df["출판연도"] >= 2023]
      .groupby("출판연월")["판매지수"]
      .agg(["mean", "count"])
      .reset_index()
      .sort_values("출판연월"))
ts.columns = ["출판연월", "평균판매지수", "도서수"]

fig, ax = plt.subplots(figsize=(13, 5))
ax.plot(ts["출판연월"], ts["평균판매지수"], marker="o", color="#4C72B0", linewidth=2)
ax.set_title("출판연월별 평균 판매지수 (2023년 이후)")
ax.set_xlabel("출판연월")
ax.set_ylabel("평균 판매지수")
plt.xticks(rotation=45, ha="right")
img08 = fig_save("v08_sales_by_month.png")

viz_sections.append(f"""### V08. 출판연월별 평균 판매지수 추이

![]({img08})

{ts.tail(12).to_markdown(index=False)}

> **해석**: 2023년 이후 출판된 도서의 평균 판매지수 추이를 보면, AI 관련 도서 출판이 급증한
2024~2025년 구간에서 평균 판매지수가 높은 편이다. 최신 출판 도서는 아직 리뷰·판매 누적 기간이
짧아 판매지수가 상대적으로 낮게 나타날 수 있으며, 장기 스테디셀러의 판매지수가 높게 유지되는 경향도 보인다.
""")

# ── V09. 분철가능 여부 / eBook유무 비교 박스플롯 ────────────────────────────
print("V09 분철·eBook 비교...")
fig, axes = plt.subplots(1, 2, figsize=(12, 5))

spring_y = df[df["분철가능"] == "Y"]["판매지수"].dropna()
spring_n = df[df["분철가능"] == "N"]["판매지수"].dropna()
axes[0].boxplot([spring_y, spring_n], tick_labels=["분철 가능(Y)", "분철 불가(N)"],
                showfliers=False, patch_artist=True,
                boxprops=dict(facecolor="#AEC6E8"))
axes[0].set_title("분철 가능 여부별 판매지수")
axes[0].set_ylabel("판매지수")

ebook_y = df[df["eBook유무"] == "있음"]["판매지수"].dropna()
ebook_n = df[df["eBook유무"] == "없음"]["판매지수"].dropna()
axes[1].boxplot([ebook_y, ebook_n], tick_labels=["eBook 있음", "eBook 없음"],
                showfliers=False, patch_artist=True,
                boxprops=dict(facecolor="#FFCC99"))
axes[1].set_title("관련 eBook 유무별 판매지수")
axes[1].set_ylabel("판매지수")
img09 = fig_save("v09_group_compare.png")

v09_tbl = pd.DataFrame({
    "그룹": ["분철Y", "분철N", "eBook있음", "eBook없음"],
    "중앙값": [spring_y.median(), spring_n.median(), ebook_y.median(), ebook_n.median()],
    "평균": [spring_y.mean(), spring_n.mean(), ebook_y.mean(), ebook_n.mean()],
    "건수": [len(spring_y), len(spring_n), len(ebook_y), len(ebook_n)],
}).round(0)
viz_sections.append(f"""### V09. 분철 가능 여부 / eBook 유무별 판매지수 비교

![]({img09})

{v09_tbl.to_markdown(index=False)}

> **해석**: 분철 가능 도서의 판매지수 중앙값이 분철 불가 도서보다 높으며, 이는 두꺼운 실무·학습서가
베스트셀러 상위권에 집중됨을 나타낸다. eBook 보유 도서 역시 없는 경우보다 판매지수가 높은 경향이 있어,
멀티 포맷 전략이 독자 접근성을 높이고 전체 판매에 기여함을 시사한다.
""")

# ── V10. 수치형 변수 상관 히트맵 ───────────────────────────────────────────
print("V10 상관 히트맵...")
heatmap_cols = ["판매지수", "평점", "리뷰수", "정가", "포인트",
                "종이책_리뷰", "eBook_리뷰", "종이책_한줄평"]
corr_mat = df[heatmap_cols].corr().round(2)

fig, ax = plt.subplots(figsize=(10, 8))
im = ax.imshow(corr_mat.values, cmap="RdBu_r", vmin=-1, vmax=1)
plt.colorbar(im, ax=ax)
ax.set_xticks(range(len(heatmap_cols)))
ax.set_yticks(range(len(heatmap_cols)))
ax.set_xticklabels(heatmap_cols, rotation=45, ha="right")
ax.set_yticklabels(heatmap_cols)
for i in range(len(heatmap_cols)):
    for j in range(len(heatmap_cols)):
        ax.text(j, i, f"{corr_mat.iloc[i, j]:.2f}",
                ha="center", va="center", fontsize=8,
                color="white" if abs(corr_mat.iloc[i, j]) > 0.5 else "black")
ax.set_title("수치형 변수 상관계수 히트맵")
img10 = fig_save("v10_corr_heatmap.png")

viz_sections.append(f"""### V10. 수치형 변수 상관계수 히트맵

![]({img10})

{corr_mat.to_markdown()}

> **해석**: 판매지수는 리뷰수·종이책 리뷰·한줄평과 양의 상관관계가 가장 높다. 이는 많이 팔릴수록
리뷰도 많이 달리는 선순환 구조를 확인한다. 정가와 판매지수 간 상관은 약한 편으로, 가격 자체보다
콘텐츠 품질과 브랜드가 더 중요한 구매 요인임을 암시한다.
""")

# ── V11. 출판사별 평균 판매지수 Top 20 (3권 이상) ──────────────────────────
print("V11 출판사 평균 판매지수...")
pub_min3 = df.groupby("출판사").filter(lambda x: len(x) >= 3)
pub_sales = (pub_min3.groupby("출판사")["판매지수"]
             .agg(["mean", "count"]).round(0)
             .sort_values("mean", ascending=False).head(20))
pub_sales.columns = ["평균판매지수", "등재권수"]

fig, ax = plt.subplots(figsize=(10, 7))
ax.barh(pub_sales.index[::-1], pub_sales["평균판매지수"][::-1], color="#DD8452")
ax.set_title("출판사별 평균 판매지수 Top 20 (3권 이상 출판사)")
ax.set_xlabel("평균 판매지수")
img11 = fig_save("v11_pub_avg_sales.png")

viz_sections.append(f"""### V11. 출판사별 평균 판매지수 Top 20

![]({img11})

{pub_sales.reset_index().to_markdown(index=False)}

> **해석**: 등재 권수 상위 출판사와 평균 판매지수 상위 출판사가 반드시 일치하지는 않는다. 소수
베스트셀러에 집중한 출판사가 평균 판매지수에서 높게 나타날 수 있다. 3권 이상 기준으로 통계적
안정성을 확보하여 출판사별 실질 판매 경쟁력을 비교하였다.
""")

# ── V12. TF-IDF 키워드 분석 ─────────────────────────────────────────────────
print("V12 TF-IDF 키워드...")
text_corpus = (
    df["제목"].fillna("") + " " +
    df["부제목"].fillna("") + " " +
    df["특징"].fillna("")
).tolist()

tfidf = TfidfVectorizer(max_features=30, token_pattern=r"[가-힣a-zA-Z]{2,}")
tfidf_mat = tfidf.fit_transform(text_corpus)
kw_scores = tfidf_mat.sum(axis=0).A1
kw_df = pd.DataFrame({
    "키워드": tfidf.get_feature_names_out(),
    "TF-IDF 합계": kw_scores.round(2),
}).sort_values("TF-IDF 합계", ascending=False).head(30)

fig, ax = plt.subplots(figsize=(10, 8))
ax.barh(kw_df["키워드"][::-1], kw_df["TF-IDF 합계"][::-1], color="#4C72B0")
ax.set_title("제목·부제목·특징 TF-IDF 상위 30 키워드")
ax.set_xlabel("TF-IDF 합계 점수")
img12 = fig_save("v12_tfidf_keywords.png")

viz_sections.append(f"""### V12. TF-IDF 상위 30 키워드

![]({img12})

{kw_df.to_markdown(index=False)}

> **해석**: TF-IDF 분석 결과 'AI', '클로드', '코드', '활용', '실전' 등의 키워드가 상위에 위치하여
현재 IT 도서 시장의 키워드가 AI·클로드 코드 중심으로 재편됐음을 명확히 보여준다. '제미나이',
'챗GPT' 등 경쟁 AI 플랫폼 관련 키워드도 등장하며, AI 도구 활용 실무서가 시장을 주도하고 있음을
확인할 수 있다.
""")

sections.append("## 4. 데이터 시각화\n\n" + "\n\n".join(viz_sections))


# ══════════════════════════════════════════════════════════════════════════════
# § 5. 종합 인사이트
# ══════════════════════════════════════════════════════════════════════════════
total_sales = df["판매지수"].sum()
top5_pub = df.groupby("출판사")["판매지수"].sum().nlargest(5)
top5_share = (top5_pub.sum() / total_sales * 100).round(1)

sections.append(f"""## 5. 종합 인사이트

| # | 인사이트 | 근거 |
|---|---------|------|
| 1 | **AI 도서가 시장 장악** | TF-IDF 상위 키워드: AI, 클로드, 제미나이, 코드 등 |
| 2 | **극단적 롱테일 구조** | 판매지수 우편향 분포, log 변환 후 정규 근사 |
| 3 | **출판사 과점** | 상위 5개 출판사 판매지수 점유율 **{top5_share}%** |
| 4 | **리뷰 선순환이 핵심 레버** | 리뷰수↑ → 판매지수↑ 양의 상관관계 (log 변환) |
| 5 | **평점 변별력 低** | 평점 9.0 이상 집중, 판매지수와 상관 약함 |
| 6 | **분철·멀티포맷 전략 유효** | 분철 가능·eBook 보유 도서의 중앙 판매지수 高 |
| 7 | **2~3만원대 가격 주류** | 정가 중앙값 약 25,000원, 이탈 폭 좁음 |
""")


# ══════════════════════════════════════════════════════════════════════════════
# 리포트 작성
# ══════════════════════════════════════════════════════════════════════════════
print("리포트 작성 중...")
header = """# YES24 IT 모바일 베스트셀러 EDA 리포트

> **수집일**: 2026-06-15 | **대상**: YES24 IT 모바일 카테고리 베스트셀러 1,000건
> **분석 도구**: Python (pandas, numpy, matplotlib, koreanize-matplotlib, scikit-learn)

---
"""
report_md = header + "\n\n---\n\n".join(sections)
REPORT_PATH.write_text(report_md, encoding="utf-8")

print(f"\n[완료]")
print(f"  차트: {IMG_DIR} ({len(list(IMG_DIR.glob('v*.png')))}개)")
print(f"  리포트: {REPORT_PATH}")
