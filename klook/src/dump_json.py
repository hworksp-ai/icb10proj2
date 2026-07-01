import urllib.request, json
url = 'https://www.klook.com/v1/cardinfocenterservicesrv/search/platform/complete_search_v3?location=158&sort=most_relevant&tab_key=0&start=1&query=korea&size=1&k_lang=ko_KR&k_currency=KRW'
req = urllib.request.Request(url, headers={'accept-language': 'ko_KR', 'user-agent': 'Mozilla/5.0'})
res = urllib.request.urlopen(req)
data = json.loads(res.read())
card = data.get('result', {}).get('search_result', {}).get('cards', [])[0]
with open('card_sample.json', 'w', encoding='utf-8') as f:
    json.dump(card, f, indent=2, ensure_ascii=False)
