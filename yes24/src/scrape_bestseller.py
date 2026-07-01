import requests
from bs4 import BeautifulSoup
import csv
import re
import json
import time
from pathlib import Path

BASE_URL = (
    "https://www.yes24.com/product/category/BestSellerContents"
    "?categoryNumber=001001003&sumGb=06&sex=A&age=255&goodsTp=0"
    "&addOptionTp=0&excludeTp=2&pageNumber={page}&pageSize=24"
    "&goodsStatGb=06&eBookTp=0&bestType=YES24_BESTSELLER"
    "&type=&saleYear=0&saleMonth=0&weekNo=0&saleDts=&viewMode=&freeYn="
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/149.0.0.0 Safari/537.36"
    ),
    "Referer": (
        "https://www.yes24.com/product/category/bestseller"
        "?categoryNumber=001001003&pageNumber=1&pageSize=24"
    ),
    "sec-ch-ua": '"Google Chrome";v="149", "Chromium";v="149", "Not)A;Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "x-requested-with": "XMLHttpRequest",
    "viewport-width": "1318",
    "rtt": "50",
}

OUTPUT_PATH = Path(__file__).parent.parent / "data" / "yes24_bestseller_full.csv"

FIELDS = [
    "순위", "상품번호", "상품분류코드", "상품분류명", "상품유형",
    "제목", "부제목", "특징",
    "저자", "출판사", "출판일",
    "정가", "판매가", "할인율", "할인금액", "포인트",
    "평점", "리뷰수", "종이책_리뷰", "eBook_리뷰", "종이책_한줄평", "eBook_한줄평",
    "판매지수",
    "분철가능", "대여가능", "북클루", "옵션여부", "상품상태",
    "구매혜택", "배송예정일", "관련eBook가격", "해시태그",
    "이미지URL", "상품URL",
]


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip() if text else ""


def parse_yesalert(item) -> dict:
    result = {"종이책_리뷰": "", "eBook_리뷰": "", "종이책_한줄평": "", "eBook_한줄평": ""}
    lis = item.select("ul.yesAlertLi li")
    labels = ["종이책_리뷰", "eBook_리뷰", "종이책_한줄평", "eBook_한줄평"]
    for i, li in enumerate(lis[:4]):
        m = re.search(r"\((\d+)건\)", li.get_text())
        result[labels[i]] = m.group(1) if m else ""
    return result


def parse_item(item, page_rank_offset: int) -> dict:
    # hidden input (JSON)
    opt_input = item.select_one("input[name=ORD_GOODS_OPT]")
    opt = json.loads(opt_input["value"]) if opt_input else {}

    rank_tag = item.select_one("em.ico.rank")
    rank = clean(rank_tag.text) if rank_tag else str(page_rank_offset)

    goods_no = str(opt.get("goods_no", ""))
    product_url = f"https://www.yes24.com/product/goods/{goods_no}" if goods_no else ""

    title_tag = item.select_one("a.gd_name")
    title = clean(title_tag.text) if title_tag else clean(str(opt.get("goods_name", "")))

    subtitle_tag = item.select_one("span.gd_nameE")
    subtitle = clean(subtitle_tag.text) if subtitle_tag else ""

    feature_tags = item.select("span.gd_feature span.feature")
    features = " | ".join(clean(f.text) for f in feature_tags)

    goods_type_tag = item.select_one("span.gd_res")
    goods_type = clean(goods_type_tag.text).strip("[]") if goods_type_tag else ""

    author_tag = item.select_one("span.info_auth a")
    author = clean(author_tag.text) if author_tag else clean(str(opt.get("goodsAuth", "")))

    pub_tag = item.select_one("span.info_pub a")
    publisher = clean(pub_tag.text) if pub_tag else ""

    date_tag = item.select_one("span.info_date")
    pub_date = clean(date_tag.text) if date_tag else ""

    sale_price = str(int(opt["salePrice"])) if opt.get("salePrice") else ""
    orig_price = str(int(opt["shopPrice"])) if opt.get("shopPrice") else ""
    disc_amount = str(int(opt["discountShopPrice"])) if opt.get("discountShopPrice") else ""

    disc_tag = item.select_one("span.txt_sale em.num")
    discount_rate = clean(disc_tag.text) if disc_tag else ""

    point_tag = item.select_one("span.yPoint")
    if point_tag:
        point_text = point_tag.get_text()
        m = re.search(r"([\d,]+)원", point_text)
        points = m.group(1).replace(",", "") if m else ""
    else:
        points = ""

    rating_tag = item.select_one("span.rating_grade em.yes_b")
    rating = clean(rating_tag.text) if rating_tag else ""

    review_tag = item.select_one("span.rating_rvCount em.txC_blue")
    review_count = clean(review_tag.text) if review_tag else ""

    alert = parse_yesalert(item)

    sales_tag = item.select_one("span.saleNum")
    sales_index = ""
    if sales_tag:
        m = re.search(r"[\d,]+", sales_tag.text)
        sales_index = m.group().replace(",", "") if m else ""

    spring_tag = item.select_one("span.iconC.spring")
    spring = "Y" if spring_tag else "N"

    rent = "Y" if str(opt.get("rent_goods_yn", "N")) == "Y" else "N"
    bookclue = "Y" if str(opt.get("bookclue_yn", "N")) == "Y" else "N"
    opt_yn = str(opt.get("opt_yn", ""))
    goods_state = str(opt.get("goods_state", ""))

    benefit_tag = item.select_one("dl.info_present dd a")
    benefit = clean(benefit_tag.text) if benefit_tag else ""

    deli_tag = item.select_one("span.deli_date strong.deli_act")
    delivery = clean(deli_tag.text) if deli_tag else ""

    ebook_tag = item.select_one("div.info_relG span.relG")
    ebook_price = ""
    if ebook_tag:
        m = re.search(r"([\d,]+)원", ebook_tag.get_text())
        ebook_price = m.group(1).replace(",", "") if m else ""

    tag_els = item.select("div.info_tag span.tag a")
    hashtags = " | ".join(clean(t.text) for t in tag_els)

    img_tag = item.select_one("img.lazy")
    image_url = img_tag.get("data-original", img_tag.get("src", "")) if img_tag else ""

    return {
        "순위": rank,
        "상품번호": goods_no,
        "상품분류코드": str(opt.get("goodsSortNo", "")),
        "상품분류명": str(opt.get("goodsSortNm", "")),
        "상품유형": goods_type,
        "제목": title,
        "부제목": subtitle,
        "특징": features,
        "저자": author,
        "출판사": publisher,
        "출판일": pub_date,
        "정가": orig_price,
        "판매가": sale_price,
        "할인율": discount_rate,
        "할인금액": disc_amount,
        "포인트": points,
        "평점": rating,
        "리뷰수": review_count,
        "종이책_리뷰": alert["종이책_리뷰"],
        "eBook_리뷰": alert["eBook_리뷰"],
        "종이책_한줄평": alert["종이책_한줄평"],
        "eBook_한줄평": alert["eBook_한줄평"],
        "판매지수": sales_index,
        "분철가능": spring,
        "대여가능": rent,
        "북클루": bookclue,
        "옵션여부": opt_yn,
        "상품상태": goods_state,
        "구매혜택": benefit,
        "배송예정일": delivery,
        "관련eBook가격": ebook_price,
        "해시태그": hashtags,
        "이미지URL": image_url,
        "상품URL": product_url,
    }


def scrape_page(page: int) -> list[dict]:
    url = BASE_URL.format(page=page)
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    items = soup.select("div.itemUnit")
    offset = (page - 1) * 24 + 1
    return [parse_item(item, offset + i) for i, item in enumerate(items)]


def find_last_page() -> int:
    lo, hi = 1, 50
    while lo < hi:
        mid = (lo + hi + 1) // 2
        url = BASE_URL.format(page=mid)
        resp = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        if soup.select("div.itemUnit"):
            lo = mid
        else:
            hi = mid - 1
        time.sleep(0.3)
    return lo


def save_csv(records: list[dict]) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(records)


if __name__ == "__main__":
    # 1페이지 검증
    print("[1/3] 1페이지 수집 검증 중...")
    test = scrape_page(1)
    if not test:
        raise SystemExit("1페이지 수집 실패 - 중단")
    print(f"  1페이지 {len(test)}건 수집 성공")
    print(f"  샘플: [{test[0]['순위']}위] {test[0]['제목']} / {test[0]['저자']}")

    # 전체 페이지 수 탐색
    print("[2/3] 전체 페이지 수 탐색 중...")
    last_page = find_last_page()
    print(f"  마지막 페이지: {last_page}페이지")

    # 전체 수집
    print(f"[3/3] 전체 {last_page}페이지 수집 시작...")
    all_records: list[dict] = []
    for page in range(1, last_page + 1):
        records = scrape_page(page)
        all_records.extend(records)
        print(f"  [{page:3d}/{last_page}] {len(records)}건 수집 (누계 {len(all_records)}건)")
        time.sleep(0.5)

    save_csv(all_records)
    print(f"\n완료: 총 {len(all_records)}건 → {OUTPUT_PATH}")
