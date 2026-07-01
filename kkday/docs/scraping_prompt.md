# Scraping Prompt
1) HTTP 요청정보
Request URL
https://www.kkday.com/api/_nuxt/category/get-search-products
Request Method
POST
Status Code
200 OK
Remote Address
3.168.178.116:443
Referrer Policy
strict-origin-when-cross-origin

2) HTTP 헤더정보
accept
application/json
accept-encoding
gzip, deflate, br, zstd
accept-language
ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7
content-length
119
content-type
application/json
dnt
1
market
ko
origin
https://www.kkday.com
priority
u=1, i
referer
https://www.kkday.com/ko/category/kr-south-korea/experiences/list?currency=USD&sort=prec&page=2&count=10
sec-ch-ua
"Google Chrome";v="149", "Chromium";v="149", "Not)A;Brand";v="24"
sec-ch-ua-mobile
?0
sec-ch-ua-platform
"Windows"
sec-fetch-dest
empty
sec-fetch-mode
cors
sec-fetch-site
same-origin
user-agent
Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36
x-csrf-token
39d6d9e6-6449-4b50-9903-665250d00e17

3) Payload 정보
{"productCategory":"CATEGORY_018","destination":"D-KR-120","keyword":"","filters":{},"sort":"prec","page":1,"count":10}

4) 응답의 일부를 Response 에서 일부를 복사해서 넣어주기 (전체는 토큰 수 제한으로 어렵습니다.)

{
    "products": [
        {
            "prod_mid": 119655,
            "prod_oid": 119655,
            "name": "용인 캐리비안베이 할인 이용권 (종일권/오후권)",
            "introduction": "지금 KKday에서 할인가로 캐리비안베이 입장권을 예약해보세요. QR코드 스캔으로 바로 입장 가능하답니다. 스릴 만점 어트랙션이 가득한 캐리비언베이로 떠나세요!",
            "rating_count": 429,
            "rating_star": 4.86,
            "show_order_count": "10K+",
            "earliest_sale_date": "20260702",
            "sale_status": 1,
            "purchase_type": null,
            "purchase_date": null,
            "is_tourism_product": true,
            "readable_url": "",
            "product_category": {
                "main": "CATEGORY_033",
                "sub": []
            },

5) 한페이지가 성공적으로 수집되는지 확인하고 csv 파일로 저장할 것