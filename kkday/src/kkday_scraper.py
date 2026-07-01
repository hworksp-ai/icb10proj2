"""
이 모듈은 KKday API를 통해 카테고리 검색 결과를 크롤링하여 제품 정보를 수집하고 CSV 파일로 저장하는 역할을 합니다.
Cloudflare 등의 봇 차단(403 Forbidden)을 우회하기 위해 curl_cffi 라이브러리를 사용합니다.
작성자: Antigravity
생성일: 2026-07-01
"""
from curl_cffi import requests
import pandas as pd
import os
import re
import time

def get_csrf_token(session):
    """초기 페이지 로드로 CSRF 토큰을 획득한다."""
    init_url = "https://www.kkday.com/ko/category/kr-south-korea/experiences/list?currency=KRW"

    # 한국어/KRW 환경 강제 설정
    for cookie_name, cookie_val in [("currency", "KRW"), ("kkday_currency", "KRW"), ("kkday_lang", "ko"), ("language", "ko")]:
        session.cookies.set(cookie_name, cookie_val, domain="www.kkday.com")

    for attempt in range(3):
        res = session.get(init_url, headers={"Cache-Control": "no-cache", "Pragma": "no-cache"})
        print(f"Init page Status Code: {res.status_code} (attempt {attempt+1})")
        if res.status_code == 200:
            break
        time.sleep(2)
    else:
        print("Failed to load init page.")
        return None, res

    html = res.text

    # 1) 쿠키에서 csrf_token 확인 (서버가 Set-Cookie로 내려준 경우)
    csrf_from_cookie = session.cookies.get("csrf_token")
    if csrf_from_cookie:
        print(f"CSRF token from cookie: {csrf_from_cookie}")
        return csrf_from_cookie, res

    # 2) <meta name="csrf-token"> 탐색
    meta_match = re.search(r'<meta[^>]+name=["\']csrf-token["\'][^>]+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
    if not meta_match:
        meta_match = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']csrf-token["\']', html, re.IGNORECASE)
    if meta_match:
        print(f"CSRF token from meta tag: {meta_match.group(1)}")
        return meta_match.group(1), res

    # 3) window.__CSRF__ 또는 csrfToken 변수 탐색
    script_match = re.search(r'(?:csrfToken|csrf_token|__CSRF__)\s*[=:]\s*["\']([^"\']{8,})["\']', html, re.IGNORECASE)
    if script_match:
        print(f"CSRF token from script: {script_match.group(1)}")
        return script_match.group(1), res

    # 4) __NUXT_DATA__ 스크립트에서 UUID 탐색 (서버가 SSR payload에 포함한 경우)
    nuxt_data_match = re.search(r'<script[^>]*id="__NUXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    if nuxt_data_match:
        nuxt_uuids = re.findall(
            r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}',
            nuxt_data_match.group(1)
        )
        if nuxt_uuids:
            print(f"UUID candidates from __NUXT_DATA__: {nuxt_uuids}")
            return nuxt_uuids, res  # 리스트 반환 -> 순차 시도

    print("No CSRF token found.")
    return None, res


def get_twd_to_krw_rate():
    """Frankfurter 공개 API로 실시간 TWD→KRW 환율을 가져온다."""
    try:
        r = requests.get("https://open.er-api.com/v6/latest/TWD",
                         impersonate="chrome110", timeout=10)
        rate = r.json()["rates"]["KRW"]
        print(f"TWD→KRW exchange rate: {rate}")
        return rate
    except Exception as e:
        print(f"Exchange rate fetch failed ({e}), using fallback rate 42.0")
        return 42.0


def scrape_kkday():
    url = "https://www.kkday.com/api/_nuxt/category/get-search-products"

    payload = {
        "productCategory": "CATEGORY_018",
        "destination": "D-KR-120",
        "keyword": "",
        "filters": {},
        "sort": "prec",
        "page": 1,
        "count": 10,
        "lang": "ko",
    }

    session = requests.Session(impersonate="chrome110")

    print("Fetching CSRF token...")
    token_result, _ = get_csrf_token(session)

    if token_result is None:
        print("Could not obtain CSRF token. Aborting.")
        return

    tokens_to_try = token_result if isinstance(token_result, list) else [token_result]

    headers = {
        "accept": "application/json",
        "accept-language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "content-type": "application/json",
        "dnt": "1",
        "market": "ko",
        "origin": "https://www.kkday.com",
        "referer": "https://www.kkday.com/ko/category/kr-south-korea/experiences/list?currency=USD&sort=prec&page=2&count=10",
    }

    for token in tokens_to_try:
        session.cookies.set("csrf_token", token, domain="www.kkday.com")
        headers["x-csrf-token"] = token
        print(f"Trying token: {token}...")
        response = session.post(url, json=payload, headers=headers)
        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            if "products" in data:
                products = data["products"]
                print(f"Successfully retrieved {len(products)} items.")

                # TWD → KRW 변환
                rate = get_twd_to_krw_rate()
                price_cols = ["official_price", "max_price", "min_price"]
                for p in products:
                    if p.get("currency") == "TWD":
                        for col in price_cols:
                            if p.get(col) is not None:
                                p[col] = round(p[col] * rate)
                        p["currency"] = "KRW"

                df = pd.json_normalize(products)

                output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
                os.makedirs(output_dir, exist_ok=True)

                output_file = os.path.join(output_dir, "kkday_products.csv")
                df.to_csv(output_file, index=False, encoding='utf-8-sig')

                print(f"Data successfully saved to {output_file}")
                return output_file
            else:
                print("Unexpected JSON structure:", list(data.keys()))
            break
        else:
            print(f"Failed: {response.text[:200]}")

    print("All tokens exhausted.")


if __name__ == "__main__":
    scrape_kkday()
