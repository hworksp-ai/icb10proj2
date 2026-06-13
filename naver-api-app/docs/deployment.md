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

## 5. API 보안 안내
- 본 대시보드는 네이버 API 자격증명(Client ID 및 Client Secret)을 소스코드나 환경설정에 하드코딩하지 않고, **사이드바에서 유저가 직접 입력**하여 세션 상태에 저장하는 구조로 구현되어 있습니다.
- 따라서 배포 시 API 키 유출 염려 없이 안전하게 공개 배포할 수 있습니다.
