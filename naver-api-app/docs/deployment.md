# Streamlit 대시보드 배포 가이드

이 문서는 네이버 API 데이터 수집 및 분석 대시보드를 **Streamlit Community Cloud**에 배포하는 방법을 안내합니다.

---

## 1. 사전 준비 사항

배포를 진행하기 전에 아래 조건이 충족되었는지 확인하십시오.
1. **GitHub 계정** 및 해당 프로젝트 저장소([hworksp-ai/icb10proj2](https://github.com/hworksp-ai/icb10proj2))에 대한 접근 권한
2. **Streamlit Community Cloud 계정** (GitHub 계정으로 간편 가입 가능)
3. 네이버 개발자 센터에서 발급받은 **Client ID** 및 **Client Secret**

---

## 2. 배포 설정 파일 확인

대시보드 앱 배포를 위해 다음 파일들이 `naver-api-app` 폴더 내에 생성되어 있습니다.
- `requirements.txt`: Streamlit Cloud 환경에서 설치할 의존성 패키지 명세서 (streamlit, pandas, plotly, scikit-learn 등)
- `.streamlit/config.toml`: 대시보드 실행 포트 설정 및 네이버 그린(#00C73C) 포인트 컬러 테마 설정

---

## 3. Streamlit Community Cloud 배포 단계

1. **Streamlit Share 로그인**
   - [Streamlit Community Cloud](https://share.streamlit.io/)에 접속하여 **Sign in with GitHub**로 로그인합니다.

2. **새로운 앱 생성 (Deploy an app)**
   - 대시보드 우측 상단의 **[Create app]** 또는 **[Deploy an app]** 버튼을 클릭합니다.

3. **저장소 및 파일 설정**
   - **Repository**: `hworksp-ai/icb10proj2`를 선택합니다.
   - **Branch**: `main` (혹은 배포할 브랜치)
   - **Main file path**: `naver-api-app/src/app.py`  
     > [!IMPORTANT]
     > `app.py`가 `naver-api-app/src/` 하위에 위치하므로 반드시 경로를 `naver-api-app/src/app.py`로 지정해 주어야 합니다.
   - **App URL**: 원하는 서브도메인을 설정합니다 (예: `naver-api-dashboard`).

4. **배포 시작**
   - 하단의 **[Deploy!]** 버튼을 누릅니다.
   - 처음 배포 시 패키지 빌드 및 환경 구성으로 인해 약 1~3분 정도 시간이 소요됩니다.

---

## 4. 로컬 및 다른 서버에서 수동 실행 방법

만약 로컬 환경이나 개별 서버에서 해당 앱을 실행하려면 가상환경 활성화 후 다음 명령어를 실행합니다.

```bash
# naver-api-app 디렉터리로 이동
cd naver-api-app

# Streamlit 앱 실행
streamlit run src/app.py
```
브라우저에서 자동으로 `http://localhost:8501` 페이지가 열립니다.

---

## 5. API 보안 및 설정 안내

본 대시보드는 소스코드에 API 키를 하드코딩하지 않으며, 로컬 환경 및 배포 환경에서 각각 보안성을 확보할 수 있도록 구현되어 있습니다.

### 로컬 환경에서 실행 시 (.env 파일)
1. 프로젝트 루트 또는 `naver-api-app/` 폴더 내에 있는 `.env.template` 파일을 복사하여 `.env` 파일을 만듭니다.
2. 생성한 `.env` 파일에 발급받은 네이버 API 자격증명을 입력합니다:
   ```env
   NAVER_CLIENT_ID=실제_클라이언트_ID
   NAVER_CLIENT_SECRET=실제_클라이언트_시크릿
   ```
3. `.env` 파일은 `.gitignore`에 이미 등록되어 있어 Git에 커밋되거나 노출되지 않습니다.

### 배포 환경에서 실행 시 (Streamlit Secrets)
Streamlit Cloud에 배포된 상태에서는 대시보드 관리 창(Settings)에서 Secrets를 설정하여 안전하게 키를 주입할 수 있습니다.
1. Streamlit Cloud 대시보드에서 해당 앱의 **[Settings]** -> **[Secrets]** 메뉴로 이동합니다.
2. 아래 형식으로 자격증명을 입력하고 저장합니다:
   ```toml
   NAVER_CLIENT_ID = "실제_클라이언트_ID"
   NAVER_CLIENT_SECRET = "실제_클라이언트_시크릿"
   ```

### 자격증명 자동 로드 및 수동 입력 순서
- **1순위**: Streamlit Cloud Secrets (`st.secrets`)에서 키 확인
- **2순위**: 로컬 `.env` 파일 (`os.environ`)에서 키 확인
- **3순위**: 위 두 방법 모두 자격증명이 감지되지 않는 경우, 사이드바의 **네이버 API 설정** 영역에서 사용자가 직접 수동으로 입력할 수 있는 폼을 제공합니다. (직접 입력 후 엔터를 치면 즉시 적용됩니다.)
