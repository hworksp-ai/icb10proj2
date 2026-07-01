"""
이 모듈은 Klook API를 통해 검색 결과를 크롤링하여 제품 정보를 수집하고 CSV 파일로 저장하는 역할을 합니다.
작성자: Antigravity
생성일: 2026-07-01
"""
import requests
import json
import pandas as pd
import os

def scrape_klook():
    url = "https://www.klook.com/v1/cardinfocenterservicesrv/search/platform/complete_search_v3"
    params = {
        "location": "158,157,156,25723,5031,8928,24975,28741,545,6166,6268,703649,703648,705582,6955,15088,701102,16467,707516,26374,7204,20296,28972,28785,8898,23546,30633,15378,16365,28742,10956,26961,10093,16560,25178,30570,7558,7741,11925,24865,25140,707332,8989,10706,11364,11745,13523,14446,15281,15603,16655,18214,18323,20392,22390,22675,23237,24520,24762,25060,26454,27895,29136,29872,30051,30265,30376,30466,31247,7030,705101,9079",
        "sort": "most_relevant",
        "tab_key": "0",
        "start": "1",
        "query": "대한민국",
        "size": "15",
        "k_lang": "ko_KR",
        "k_currency": "KRW"
    }

    headers = {
        "accept-language": "ko_KR",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
        "referer": "https://www.klook.com/ko/search/result/?query=%EB%8C%80%ED%95%9C%EB%AF%BC%EA%B5%AD",
        "x-klook-market": "global",
        "x-requested-with": "XMLHttpRequest",
        "x-platform": "desktop",
        "x-klook-host": "www.klook.com"
    }

    print(f"Requesting data from {url}...")
    response = requests.get(url, params=params, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        if "result" in data and "search_result" in data["result"]:
            cards = data["result"]["search_result"].get("cards", [])
            print(f"Successfully retrieved {len(cards)} items.")
            
            # Extract the 'data' part from each card
            product_list = [card.get("data", {}) for card in cards]
            
            # Create a dataframe and save to csv
            df = pd.DataFrame(product_list)
            
            # Create data directory if it doesn't exist
            output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
            os.makedirs(output_dir, exist_ok=True)
            
            output_file = os.path.join(output_dir, "klook_products.csv")
            df.to_csv(output_file, index=False, encoding='utf-8-sig')
            
            print(f"Data successfully saved to {output_file}")
            return output_file
        else:
            print("Unexpected JSON structure:", list(data.keys()))
    else:
        print(f"Failed to fetch data. Status Code: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    scrape_klook()
