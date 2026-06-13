"""
네이버 오픈API 연동 모듈 (naver_api.py)

이 파일은 네이버 검색 및 데이터랩(Datalab) API를 호출하고 데이터를 받아오기 위한 클라이언트 모듈입니다.
주요 기능:
- 통합 검색어 트렌드 조회 (Datalab)
- 블로그 검색 결과 조회
- 뉴스 검색 결과 조회
- 카페글 검색 결과 조회
- 쇼핑 검색 결과 조회
"""
import requests
import json
import pandas as pd
from typing import List, Dict, Any, Optional

class NaverAPIClient:
    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id.strip()
        self.client_secret = client_secret.strip()
        self.headers = {
            "X-Naver-Client-Id": self.client_id,
            "X-Naver-Client-Secret": self.client_secret,
            "Content-Type": "application/json"
        }

    def _get_headers(self, is_json: bool = True) -> Dict[str, str]:
        headers = {
            "X-Naver-Client-Id": self.client_id,
            "X-Naver-Client-Secret": self.client_secret
        }
        if is_json:
            headers["Content-Type"] = "application/json"
        return headers

    def get_search_trend(
        self,
        keywords_dict: Dict[str, List[str]],
        start_date: str,
        end_date: str,
        time_unit: str = "date",
        device: Optional[str] = None,
        gender: Optional[str] = None,
        ages: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        네이버 통합 검색어 트렌드 API를 조회합니다. (Datalab)
        - keywords_dict: {"주제어": ["검색어1", "검색어2", ...]} 구조
        """
        url = "https://openapi.naver.com/v1/datalab/search"
        
        keyword_groups = []
        for group_name, keywords in keywords_dict.items():
            keyword_groups.append({
                "groupName": group_name,
                "keywords": keywords
            })
            
        body = {
            "startDate": start_date,
            "endDate": end_date,
            "timeUnit": time_unit,
            "keywordGroups": keyword_groups
        }
        
        if device:
            body["device"] = device
        if gender:
            body["gender"] = gender
        if ages:
            body["ages"] = ages
            
        response = requests.post(url, headers=self._get_headers(is_json=True), data=json.dumps(body))
        
        if response.status_code == 200:
            res_data = response.json()
            # 데이터 가공하여 DataFrame으로 반환
            results = res_data.get("results", [])
            df_list = []
            for group in results:
                title = group.get("title")
                data_points = group.get("data", [])
                for dp in data_points:
                    df_list.append({
                        "날짜": dp.get("period"),
                        "검색비율": dp.get("ratio"),
                        "주제어": title
                    })
            if not df_list:
                return pd.DataFrame(columns=["날짜", "검색비율", "주제어"])
            df = pd.DataFrame(df_list)
            df["날짜"] = pd.to_datetime(df["날짜"])
            return df
        else:
            raise Exception(f"Datalab API 호출 실패 (Status Code: {response.status_code}): {response.text}")

    def _search(self, category: str, query: str, display: int = 20, start: int = 1, sort: str = "sim") -> Dict[str, Any]:
        """
        네이버 검색 공통 GET API
        """
        url = f"https://openapi.naver.com/v1/search/{category}.json"
        params = {
            "query": query,
            "display": min(max(display, 10), 100),
            "start": min(max(start, 1), 1000),
            "sort": sort
        }
        
        # 쇼핑이나 블로그 같은 일부 API의 헤더는 application/json 미필요
        response = requests.get(url, headers=self._get_headers(is_json=False), params=params)
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"검색 API ({category}) 호출 실패 (Status Code: {response.status_code}): {response.text}")

    def search_blog(self, query: str, display: int = 20, sort: str = "sim") -> pd.DataFrame:
        data = self._search("blog", query, display, sort=sort)
        items = data.get("items", [])
        if not items:
            return pd.DataFrame(columns=["제목", "링크", "요약", "블로거", "블로그주소", "작성일"])
            
        df = pd.DataFrame(items)
        # 컬럼 이름 매핑 및 전처리
        df = df.rename(columns={
            "title": "제목",
            "link": "링크",
            "description": "요약",
            "bloggername": "블로거",
            "bloggerlink": "블로그주소",
            "postdate": "작성일"
        })
        if "작성일" in df.columns:
            df["작성일"] = pd.to_datetime(df["작성일"], format="%Y%m%d", errors="coerce")
        return df

    def search_news(self, query: str, display: int = 20, sort: str = "sim") -> pd.DataFrame:
        data = self._search("news", query, display, sort=sort)
        items = data.get("items", [])
        if not items:
            return pd.DataFrame(columns=["제목", "원문링크", "네이버링크", "요약", "게시일"])
            
        df = pd.DataFrame(items)
        df = df.rename(columns={
            "title": "제목",
            "originallink": "원문링크",
            "link": "네이버링크",
            "description": "요약",
            "pubDate": "게시일"
        })
        if "게시일" in df.columns:
            df["게시일"] = pd.to_datetime(df["게시일"], errors="coerce")
        return df

    def search_cafearticle(self, query: str, display: int = 20, sort: str = "sim") -> pd.DataFrame:
        data = self._search("cafearticle", query, display, sort=sort)
        items = data.get("items", [])
        if not items:
            return pd.DataFrame(columns=["제목", "링크", "요약", "카페명", "카페주소"])
            
        df = pd.DataFrame(items)
        df = df.rename(columns={
            "title": "제목",
            "link": "링크",
            "description": "요약",
            "cafename": "카페명",
            "cafeurl": "카페주소"
        })
        return df

    def search_shopping(self, query: str, display: int = 20, sort: str = "sim", filter_pay: Optional[str] = None, exclude: Optional[str] = None) -> pd.DataFrame:
        url = "https://openapi.naver.com/v1/search/shop.json"
        params = {
            "query": query,
            "display": min(max(display, 10), 100),
            "start": 1,
            "sort": sort
        }
        if filter_pay:
            params["filter"] = filter_pay
        if exclude:
            params["exclude"] = exclude
            
        response = requests.get(url, headers=self._get_headers(is_json=False), params=params)
        if response.status_code == 200:
            data = response.json()
            items = data.get("items", [])
            if not items:
                return pd.DataFrame(columns=["상품명", "링크", "이미지", "최저가", "최고가", "쇼핑몰", "상품ID", "상품타입", "브랜드", "제조사", "카테고리1", "카테고리2", "카테고리3", "카테고리4"])
                
            df = pd.DataFrame(items)
            df = df.rename(columns={
                "title": "상품명",
                "link": "링크",
                "image": "이미지",
                "lprice": "최저가",
                "hprice": "최고가",
                "mallName": "쇼핑몰",
                "productId": "상품ID",
                "productType": "상품타입",
                "brand": "브랜드",
                "maker": "제조사",
                "category1": "카테고리1",
                "category2": "카테고리2",
                "category3": "카테고리3",
                "category4": "카테고리4"
            })
            
            # 수치형 컬럼 변환
            if "최저가" in df.columns:
                df["최저가"] = pd.to_numeric(df["최저가"], errors="coerce").fillna(0).astype(int)
            if "최고가" in df.columns:
                df["최고가"] = pd.to_numeric(df["최고가"], errors="coerce").fillna(0).astype(int)
            return df
        else:
            raise Exception(f"쇼핑 검색 API 호출 실패 (Status Code: {response.status_code}): {response.text}")
