"""
Klook 검색 결과 스크래퍼 (SQLite 저장 버전)

이 스크립트는 Klook의 검색 API를 사용하여 대한민국 관련 제품 정보를 수집합니다.
- 수집 범위: 1페이지 ~ 10페이지 (페이지당 15개)
- 저장 형식: SQLite 데이터베이스 (klook/data/klook_products.db)
- 사람의 접근을 모사하기 위해 페이지 간 무작위 대기 시간(0.1~1.0초) 적용
- 매 페이지마다 수집 즉시 DB에 저장하여 중간 오류 시에도 데이터 보존
- 수집 항목: 상품명, 가격, 판매가, 리뷰 별점, 리뷰 수, 예약 건수, 위치, 상품 URL
"""

import urllib.request
import urllib.parse
import json
import os
import time
import random
import sqlite3
from datetime import datetime


def init_db(db_path: str) -> sqlite3.Connection:
    """
    SQLite 데이터베이스 및 테이블을 초기화합니다.
    
    Args:
        db_path: 데이터베이스 파일 경로
    
    Returns:
        sqlite3.Connection: 데이터베이스 연결 객체
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 상품 정보 테이블 생성 (이미 존재하면 유지)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS klook_products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            price TEXT,
            sell_price TEXT,
            review_star TEXT,
            review_total TEXT,
            booking_count TEXT,
            location TEXT,
            url TEXT,
            deep_link TEXT,
            page_num INTEGER,
            collected_at TEXT
        )
    """)
    
    # 수집 로그 테이블 생성 (페이지별 수집 결과 기록)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scraping_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            page_num INTEGER,
            status TEXT,
            item_count INTEGER,
            message TEXT,
            logged_at TEXT
        )
    """)
    
    conn.commit()
    print(f"데이터베이스 초기화 완료: {db_path}")
    return conn


def save_to_db(conn: sqlite3.Connection, products: list, page_num: int) -> int:
    """
    수집한 상품 데이터를 SQLite DB에 저장합니다.
    
    Args:
        conn: 데이터베이스 연결 객체
        products: 저장할 상품 데이터 리스트
        page_num: 현재 페이지 번호
    
    Returns:
        int: 저장된 데이터 건수
    """
    cursor = conn.cursor()
    collected_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    rows = [
        (
            p["title"],
            p["price"],
            p["sell_price"],
            p["review_star"],
            p["review_total"],
            p["booking_count"],
            p["location"],
            p["url"],
            p["deep_link"],
            page_num,
            collected_at
        )
        for p in products
    ]
    
    cursor.executemany("""
        INSERT INTO klook_products
            (title, price, sell_price, review_star, review_total,
             booking_count, location, url, deep_link, page_num, collected_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows)
    
    conn.commit()
    return len(rows)


def log_page(conn: sqlite3.Connection, page_num: int, status: str, item_count: int, message: str = ""):
    """
    페이지별 수집 결과를 로그 테이블에 기록합니다.
    
    Args:
        conn: 데이터베이스 연결 객체
        page_num: 페이지 번호
        status: 수집 상태 ('success' 또는 'error')
        item_count: 수집된 항목 수
        message: 추가 메시지 (오류 메시지 등)
    """
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO scraping_log (page_num, status, item_count, message, logged_at)
        VALUES (?, ?, ?, ?, ?)
    """, (page_num, status, item_count, message, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()


def parse_card(card: dict) -> dict:
    """
    API 응답의 카드 데이터에서 필요한 정보를 추출합니다.
    
    Args:
        card: API 응답의 개별 카드 딕셔너리
    
    Returns:
        dict: 추출된 상품 정보 딕셔너리
    """
    card_data = card.get("data", {})
    
    # 상품명 추출 (여러 키 우선순위 적용)
    title = (
        card_data.get("title")
        or card_data.get("activity_title")
        or card_data.get("name")
        or "제목 없음"
    )
    
    # URL 및 딥링크 추출
    url_path = card_data.get("url", "")
    full_url = "https://www.klook.com" + url_path if url_path else ""
    deep_link = card_data.get("deep_link", "")
    
    return {
        "title": title,
        "price": str(card_data.get("price", "")),
        "sell_price": str(card_data.get("sell_price", "")),
        "review_star": str(card_data.get("review_star", "")),
        "review_total": str(card_data.get("review_total", "")),
        "booking_count": str(card_data.get("recent_book_text", "")),
        "location": str(card_data.get("location_text", "")),
        "url": full_url,
        "deep_link": deep_link,
    }


def scrape_klook_sqlite():
    """
    Klook 검색 결과를 1~10페이지까지 수집하여 SQLite DB에 저장하는 메인 함수입니다.
    """
    # 설정값
    start_page = 1
    max_pages = 10
    size = 15  # 페이지당 결과 수
    
    # 출력 경로 설정 (klook/data/klook_products.db)
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output_dir = os.path.join(base_dir, "data")
    os.makedirs(output_dir, exist_ok=True)
    db_path = os.path.join(output_dir, "klook_products.db")
    
    # DB 초기화
    conn = init_db(db_path)
    
    # HTTP 요청 헤더 설정 (브라우저 모사)
    headers_http = {
        "accept-language": "ko_KR",
        "cache-control": "no-cache",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
        "referer": "https://www.klook.com/ko/search/result/?query=%EB%8C%80%ED%95%9C%EB%AF%BC%EA%B5%AD",
        "x-klook-market": "global",
        "x-klook-host": "www.klook.com",
        "x-klook-traffic-channel": "google_sem",
        "x-klook-user-residence": "10_KR",
        "x-platform": "desktop",
        "x-requested-with": "XMLHttpRequest",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
    }
    
    total_saved = 0
    print(f"{'='*60}")
    print(f"Klook 스크래핑 시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"수집 범위: 1~{max_pages}페이지 | 저장 경로: {db_path}")
    print(f"{'='*60}")
    
    for page_num in range(start_page, max_pages + 1):
        # start 파라미터는 페이지 번호 (1부터 시작)
        api_url = (
            "https://www.klook.com/v1/cardinfocenterservicesrv/search/platform/complete_search_v3"
            f"?location=158%2C157%2C156%2C25723%2C5031%2C8928%2C24975%2C28741%2C545%2C6166%2C6268"
            "%2C703649%2C703648%2C705582%2C6955%2C15088%2C701102%2C16467%2C707516%2C26374%2C7204"
            "%2C20296%2C28972%2C28785%2C8898%2C23546%2C30633%2C15378%2C16365%2C28742%2C10956"
            "%2C26961%2C10093%2C16560%2C25178%2C30570%2C7558%2C7741%2C11925%2C24865%2C25140"
            "%2C707332%2C8989%2C10706%2C11364%2C11745%2C13523%2C14446%2C15281%2C15603%2C16655"
            "%2C18214%2C18323%2C20392%2C22390%2C22675%2C23237%2C24520%2C24762%2C25060%2C26454"
            "%2C27895%2C29136%2C29872%2C30051%2C30265%2C30376%2C30466%2C31247%2C7030%2C705101%2C9079"
            f"&sort=most_relevant&tab_key=0&start={page_num}"
            f"&query=%EB%8C%80%ED%95%9C%EB%AF%BC%EA%B5%AD&size={size}&k_lang=ko_KR&k_currency=KRW"
        )
        
        print(f"\n[페이지 {page_num}/{max_pages}] 요청 중...")
        
        try:
            req = urllib.request.Request(api_url, headers=headers_http)
            with urllib.request.urlopen(req, timeout=15) as response:
                raw = response.read().decode("utf-8")
                data = json.loads(raw)
                
                cards = data.get("result", {}).get("search_result", {}).get("cards", [])
                
                if not cards:
                    msg = f"페이지 {page_num}: 카드 데이터 없음 - 수집 종료"
                    print(msg)
                    log_page(conn, page_num, "empty", 0, msg)
                    break
                
                # 카드 데이터 파싱
                products = [parse_card(card) for card in cards]
                
                # DB에 저장
                saved_count = save_to_db(conn, products, page_num)
                log_page(conn, page_num, "success", saved_count)
                
                total_saved += saved_count
                print(f"  ✓ {saved_count}개 저장 완료 (누적: {total_saved}개)")
                
                # 샘플 출력 (첫 번째 상품)
                if products:
                    sample = products[0]
                    print(f"  ↳ 샘플: [{sample['title'][:30]}...] | 판매가: {sample['sell_price']} | 위치: {sample['location']}")
        
        except urllib.error.HTTPError as e:
            msg = f"HTTP 오류 {e.code}: {e.reason}"
            print(f"  ✗ {msg}")
            log_page(conn, page_num, "error", 0, msg)
            # 심각한 오류가 아닌 경우 계속 진행
            if e.code in (429, 403):
                print("  → 요청 제한/차단 감지. 5초 대기 후 재시도를 권장합니다.")
                break
        
        except Exception as e:
            msg = f"오류 발생: {str(e)}"
            print(f"  ✗ {msg}")
            log_page(conn, page_num, "error", 0, msg)
        
        # 마지막 페이지가 아닌 경우 대기 (요청 속도 제어)
        if page_num < max_pages:
            sleep_time = random.uniform(0.1, 1.0)
            print(f"  → {sleep_time:.2f}초 대기...")
            time.sleep(sleep_time)
    
    # 최종 결과 출력
    print(f"\n{'='*60}")
    print(f"스크래핑 완료: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"총 저장된 상품 수: {total_saved}개")
    print(f"데이터베이스 위치: {db_path}")
    
    # DB 최종 통계 출력
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM klook_products")
    total_in_db = cursor.fetchone()[0]
    print(f"DB 내 전체 레코드 수: {total_in_db}개")
    print(f"{'='*60}")
    
    conn.close()


if __name__ == "__main__":
    scrape_klook_sqlite()
