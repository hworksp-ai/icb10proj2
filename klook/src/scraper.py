"""
이 스크립트는 Klook의 검색 API를 사용하여 대한민국 관련 제품 정보를 한국어로 수집합니다.
총 1페이지부터 67페이지까지 수집하며, 사람의 접근을 모사하기 위해 페이지 간 무작위 대기 시간(0.1~1.0초)을 가집니다.
수집된 데이터는 csv 형식으로 klook/data 폴더에 저장됩니다.
제품의 상세 링크(URL)를 포함하여 수집합니다.
"""

import urllib.request
import urllib.parse
import json
import csv
import os
import time
import random

def scrape_klook():
    start = 1
    size = 15
    max_pages = 67
    
    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "klook_products.csv")

    # CSV 파일 초기화 및 헤더 작성
    headers_csv = ["title", "price", "sell_price", "review_star", "review_total", "booking_count", "location", "url"]
    with open(output_file, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(headers_csv)

    total_saved = 0

    for page_num in range(1, max_pages + 1):
        url = f"https://www.klook.com/v1/cardinfocenterservicesrv/search/platform/complete_search_v3?location=158%2C157%2C156%2C25723%2C5031%2C8928%2C24975%2C28741%2C545%2C6166%2C6268%2C703649%2C703648%2C705582%2C6955%2C15088%2C701102%2C16467%2C707516%2C26374%2C7204%2C20296%2C28972%2C28785%2C8898%2C23546%2C30633%2C15378%2C16365%2C28742%2C10956%2C26961%2C10093%2C16560%2C25178%2C30570%2C7558%2C7741%2C11925%2C24865%2C25140%2C707332%2C8989%2C10706%2C11364%2C11745%2C13523%2C14446%2C15281%2C15603%2C16655%2C18214%2C18323%2C20392%2C22390%2C22675%2C23237%2C24520%2C24762%2C25060%2C26454%2C27895%2C29136%2C29872%2C30051%2C30265%2C30376%2C30466%2C31247%2C7030%2C705101%2C9079&sort=most_relevant&tab_key=0&start={start}&query=%EB%8C%80%ED%95%9C%EB%AF%BC%EA%B5%AD&size={size}&k_lang=ko_KR&k_currency=KRW"

        headers_http = {
            "accept-language": "ko_KR",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
            "x-klook-market": "global",
            "x-platform": "desktop",
            "x-requested-with": "XMLHttpRequest"
        }

        req = urllib.request.Request(url, headers=headers_http)
        try:
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode('utf-8'))
                cards = data.get("result", {}).get("search_result", {}).get("cards", [])
                
                if not cards:
                    print(f"더 이상 수집할 데이터가 없습니다. (페이지: {page_num})")
                    break

                extracted_data = []
                for card in cards:
                    card_data = card.get("data", {})
                    
                    title = card_data.get("title", "")
                    if not title:
                        title = card_data.get("activity_title", "") or card_data.get("name", "제목 없음")
                        
                    price = str(card_data.get("price", ""))
                    sell_price = str(card_data.get("sell_price", ""))
                    review_star = str(card_data.get("review_star", ""))
                    review_total = str(card_data.get("review_total", ""))
                    booking_count = str(card_data.get("recent_book_text", ""))
                    location = str(card_data.get("location_text", ""))
                    url_path = card_data.get("url", "")
                    full_url = "https://www.klook.com" + url_path if url_path else ""

                    extracted_data.append([
                        title, price, sell_price, review_star, review_total, booking_count, location, full_url
                    ])

                # 매 페이지마다 CSV에 추가(Append) 저장
                with open(output_file, 'a', encoding='utf-8-sig', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerows(extracted_data)
                
                saved_count = len(extracted_data)
                total_saved += saved_count
                print(f"페이지 {page_num}/{max_pages}: {saved_count}개 제품 정보 저장 완료. (누적: {total_saved})")

                # 다음 페이지를 위해 start 증가 (페이지 번호 방식이므로 1씩 증가)
                start += 1

                # 마지막 페이지가 아니면 대기
                if page_num < max_pages:
                    sleep_time = random.uniform(0.1, 1.0)
                    print(f"{sleep_time:.2f}초 대기 중...")
                    time.sleep(sleep_time)

        except Exception as e:
            print(f"페이지 {page_num} 수집 중 오류가 발생했습니다: {e}")
            break

    print(f"크롤링이 완료되었습니다. 총 {total_saved}개의 제품 정보가 {output_file} 에 저장되었습니다.")

if __name__ == "__main__":
    scrape_klook()
