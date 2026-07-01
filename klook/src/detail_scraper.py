"""
Klook 상품 상세페이지 스크래퍼 (Chrome + API 인터셉트 방식)

klook_products.db에서 상위 10개 상품 URL(deep_link 우선)을 가져와
실제 Chrome 브라우저(DataDome 우회)로 상세페이지에 접근하고,
Klook 내부 API 응답을 인터셉트해 상세 정보를 수집합니다.

인터셉트 대상 API:
  - get_spu_list_section       -> 상품 옵션/패키지
  - get_platform_overview      -> 별점/리뷰
  - detail_page_dynamic_info   -> 가격 정보
  - get_activity_faq_section   -> FAQ
  - images/show                -> 리뷰 이미지

DOM 셀렉터 수집 항목:
  - [class*='about']           -> 상세 설명/공지/포함사항
  - [class*='highlight']       -> 하이라이트
  - 상품 이미지                 -> 갤러리 이미지 src

저장 테이블: klook_detail
조인 뷰:    v_klook_joined
"""

import sqlite3
import json
import os
import re
import time
import random
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout


# ─── 설정 상수 ──────────────────────────────────────────────────────────────────

TOP_N        = 10
PAGE_TIMEOUT = 35_000       # ms
WAIT_AFTER   = 6_000        # 페이지 로드 후 API 완료 대기(ms)
WAIT_MIN, WAIT_MAX = 2.0, 4.0
VIEWPORT     = {"width": 1440, "height": 900}
USER_AGENT   = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

INTERCEPT_KEYS = [
    "get_spu_list_section",
    "get_platform_overview",
    "detail_page_dynamic_info",
    "get_activity_faq_section",
    "images/show",
    "images/get",
    "get_product_about_page",
]


# ─── DB 초기화 ──────────────────────────────────────────────────────────────────

def get_db_path() -> str:
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "data", "klook_products.db")


def init_detail_table(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS klook_detail (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id          INTEGER NOT NULL,
            activity_id         TEXT,
            description         TEXT,
            highlights          TEXT,
            includes            TEXT,
            excludes            TEXT,
            notice              TEXT,
            address             TEXT,
            latitude            REAL,
            longitude           REAL,
            open_time           TEXT,
            options             TEXT,
            images              TEXT,
            tags                TEXT,
            min_price           TEXT,
            currency            TEXT,
            cancellation_policy TEXT,
            avg_rating          TEXT,
            review_count        TEXT,
            validity            TEXT,
            raw_json            TEXT,
            collected_at        TEXT NOT NULL,
            FOREIGN KEY (product_id) REFERENCES klook_products(id)
        )
    """)
    cursor.execute("DROP VIEW IF EXISTS v_klook_joined")
    cursor.execute("""
        CREATE VIEW v_klook_joined AS
        SELECT
            p.id            AS product_id,
            p.title,
            p.price,
            p.sell_price,
            p.review_star,
            p.review_total,
            p.booking_count,
            p.location,
            p.url,
            p.deep_link,
            d.activity_id,
            d.description,
            d.highlights,
            d.includes,
            d.excludes,
            d.notice,
            d.address,
            d.latitude,
            d.longitude,
            d.open_time,
            d.options,
            d.images,
            d.tags,
            d.min_price,
            d.currency,
            d.cancellation_policy,
            d.avg_rating,
            d.review_count,
            d.validity,
            d.collected_at  AS detail_collected_at
        FROM klook_products p
        LEFT JOIN klook_detail d ON p.id = d.product_id
    """)
    # 기존 테이블에 새 컬럼이 없으면 추가 (스키마 마이그레이션)
    cursor.execute("PRAGMA table_info(klook_detail)")
    existing_cols = {row[1] for row in cursor.fetchall()}
    new_cols = {
        "avg_rating":  "TEXT",
        "review_count": "TEXT",
        "validity":    "TEXT",
    }
    for col, col_type in new_cols.items():
        if col not in existing_cols:
            cursor.execute(f"ALTER TABLE klook_detail ADD COLUMN {col} {col_type}")
            print(f"[DB] 컬럼 추가: {col}")

    conn.commit()
    print("[DB] klook_detail 테이블 및 v_klook_joined 뷰 초기화 완료")


def fetch_top_products(conn: sqlite3.Connection, n: int = TOP_N) -> list[dict]:
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, title, url, deep_link
        FROM klook_products
        ORDER BY id
        LIMIT ?
    """, (n,))
    rows = cursor.fetchall()
    return [
        {
            "id": r[0],
            "title": r[1],
            "url": r[2] or r[3] or "",   # url 없으면 deep_link 사용
            "deep_link": r[3] or "",
        }
        for r in rows
    ]


# ─── 헬퍼 ──────────────────────────────────────────────────────────────────────

def extract_activity_id(url: str) -> str:
    if not url:
        return ""
    m = re.search(r'/activity/(\d+)', url)
    return m.group(1) if m else ""


def _get(data, *keys):
    for k in keys:
        if not isinstance(data, dict):
            return None
        data = data.get(k)
        if data is None:
            return None
    return data


def _texts(items, *text_keys) -> list[str]:
    result = []
    if not isinstance(items, list):
        return result
    for item in items:
        if isinstance(item, str) and item.strip():
            result.append(item.strip())
            continue
        if isinstance(item, dict):
            for key in text_keys or ("text", "content", "description", "name", "title"):
                v = item.get(key)
                if v and isinstance(v, str) and v.strip():
                    result.append(v.strip())
                    break
    return result


def safe_text(page, selector: str) -> str:
    try:
        el = page.locator(selector).first
        if el.count() == 0:
            return ""
        return (el.inner_text(timeout=3000) or "").strip()
    except Exception:
        return ""


def safe_texts(page, selector: str) -> list[str]:
    try:
        els = page.locator(selector).all()
        out = []
        for e in els:
            try:
                t = (e.inner_text(timeout=2000) or "").strip()
                if t:
                    out.append(t)
            except Exception:
                pass
        return out
    except Exception:
        return []


# ─── API 응답 파싱 ──────────────────────────────────────────────────────────────

def parse_spu(spu_data: dict) -> tuple[list[dict], list[str], str, str, str]:
    """
    Returns: (options, tags, min_price, validity, cancellation_policy)
    """
    options = []
    tags = []
    min_price = ""
    validity = ""
    cancellation_policy = ""

    r = spu_data.get("result", spu_data)
    if not r:
        return options, tags, min_price, validity, cancellation_policy

    # 옵션 목록
    for grp in r.get("spu_group_info", []):
        grp_name = grp.get("name", "")
        for spu in grp.get("spu_list", [])[:30]:
            opt = {
                "group": grp_name,
                "name": spu.get("spu_name", ""),
                "spu_id": spu.get("spu_id", ""),
                "price": spu.get("price", ""),
            }
            if opt["name"]:
                options.append(opt)

    # icon_items -> tags + validity + cancellation
    first_spu = r.get("first_spu_detail", {})
    icon_items = first_spu.get("icon_items", [])
    for item in icon_items:
        title = item.get("title", "")
        if not title:
            continue
        tags.append(title)
        if "유효기간" in title or "유효" in title:
            validity = title
        if "취소" in title or "환불" in title:
            cancellation_policy = title

    # sections -> includes, address, how_to_use
    for section in first_spu.get("sections", []):
        for comp in section.get("components", []):
            data = comp.get("data", {})
            render_obj = data.get("render_obj", [])
            for obj in render_obj:
                content = obj.get("content", "")
                if content and "주소" in (data.get("title") or ""):
                    pass  # address 별도 처리

    return options, tags, min_price, validity, cancellation_policy


def parse_spu_sections(spu_data: dict) -> tuple[list[str], str, str]:
    """
    first_spu_detail.sections에서 includes, address, open_time 파싱.
    Returns: (includes, address, open_time)
    """
    includes = []
    address = ""
    open_time = ""

    r = spu_data.get("result", spu_data)
    first_spu = (r or {}).get("first_spu_detail", {})

    for section in first_spu.get("sections", []):
        for comp in section.get("components", []):
            data = comp.get("data", {})
            field_key = data.get("props", {}).get("field_key", "")
            render_obj = data.get("render_obj", [])
            title = data.get("title", "")

            if "whats_include" in field_key or "include" in field_key.lower():
                for obj in render_obj:
                    c = obj.get("content", "")
                    if c:
                        includes.append(c)

            if "location" in field_key or "주소" in title:
                for obj in render_obj:
                    c = obj.get("content", "")
                    if c and not address:
                        address = c

            if "time" in field_key or "시간" in title:
                for obj in render_obj:
                    c = obj.get("content", "")
                    if c and not open_time:
                        open_time = c

    return includes, address, open_time


def parse_price(dyn_data: dict) -> tuple[str, str]:
    """Returns: (min_price, currency)"""
    r = dyn_data.get("result", dyn_data)
    if not r:
        return "", "KRW"
    price = r.get("price", {})
    min_p = price.get("sale_price_value") or price.get("from_price_value") or price.get("sale_price", "")
    currency = "KRW"
    sale_price_str = price.get("sale_price", "")
    if "₩" in sale_price_str:
        currency = "KRW"
    elif "$" in sale_price_str:
        currency = "USD"
    return str(min_p), currency


def parse_rating(ov_data: dict) -> tuple[str, str]:
    """Returns: (avg_rating, review_count)"""
    r = ov_data.get("result", ov_data)
    if not r:
        return "", ""
    ri = r.get("rating_info", {})
    return str(ri.get("avg_rating", "")), str(ri.get("review_count", ""))


def parse_images(img_show_data: dict, page) -> list[str]:
    """리뷰 이미지 + 상품 갤러리 이미지"""
    images = []

    # API 이미지 (review images)
    r = img_show_data.get("result", img_show_data)
    for item in (r.get("image_info") or [])[:20]:
        url = item.get("image_url") or item.get("url") or ""
        if url and url not in images:
            images.append(url)

    # DOM 갤러리 이미지 (상품 공식 이미지)
    for sel in [
        "[class*='swiper-slide'] img",
        "[class*='gallery'] img",
        "[class*='carousel'] img",
        "[class*='activity-img'] img",
        ".klk-img img",
        "picture img",
    ]:
        try:
            els = page.locator(sel).all()
            for el in els[:20]:
                src = el.get_attribute("src") or el.get_attribute("data-src") or ""
                if src and ("klook.com" in src or "cdn.klook" in src) and src not in images:
                    images.append(src)
        except Exception:
            pass

    return images[:40]


# ─── 상세페이지 스크래핑 ────────────────────────────────────────────────────────

def scrape_detail(page, product: dict) -> dict:
    url = product["url"] or product.get("deep_link", "")
    activity_id = extract_activity_id(url)

    print(f"  -> [{product['id']}] {product['title'][:45]}")
    print(f"     URL: {url}")

    # 한국어 URL 보장
    if url and "/ko/" not in url:
        url = url.replace("www.klook.com/", "www.klook.com/ko/")

    # 인터셉트 버킷
    captured: dict[str, dict] = {}

    def on_response(response):
        for key in INTERCEPT_KEYS:
            if key in response.url:
                try:
                    captured[key] = response.json()
                except Exception:
                    pass

    page.on("response", on_response)

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
    except PlaywrightTimeout:
        print(f"     [TIMEOUT] 타임아웃 (계속 진행)")
    except Exception as e:
        print(f"     [ERR] goto: {e}")

    # 핵심 콘텐츠 로드 대기
    try:
        page.wait_for_selector("[class*='highlight'], [class*='about'], h1", timeout=8000)
    except Exception:
        pass
    page.wait_for_timeout(WAIT_AFTER)
    page.remove_listener("response", on_response)

    # ── API 데이터 파싱 ──
    spu_raw  = captured.get("get_spu_list_section", {})
    dyn_raw  = captured.get("detail_page_dynamic_info", {})
    ov_raw   = captured.get("get_platform_overview", {})
    img_raw  = captured.get("images/show", {})
    faq_raw  = captured.get("get_activity_faq_section", {})

    options, tags, _, validity, cancellation_policy = parse_spu(spu_raw)
    includes, address, open_time = parse_spu_sections(spu_raw)
    min_price, currency = parse_price(dyn_raw)
    avg_rating, review_count = parse_rating(ov_raw)
    images = parse_images(img_raw, page)

    # ── DOM 파싱 ──
    # 설명: about > component > description 순으로 시도
    about_text = safe_text(page, "[class*='about']")
    component_text = safe_text(page, "[class*='component']")
    description_text = safe_text(page, "[class*='description']")
    description = ""
    for candidate in [about_text, component_text, description_text]:
        if candidate and len(candidate) > 30:
            description = candidate[:5000]
            break

    # 하이라이트: highlight 또는 component 텍스트 줄단위 분리
    highlight_text = safe_text(page, "[class*='highlight']")
    if not highlight_text or len(highlight_text) < 10:
        highlight_text = component_text or ""
    highlights_raw = [h.strip() for h in highlight_text.split("\n") if len(h.strip()) > 5]
    highlights = highlights_raw[:30]

    # 옵션: API에서 얻지 못한 경우 DOM에서 보완
    if not options:
        package_text = safe_text(page, "[class*='package']")
        if package_text and len(package_text) > 10:
            for line in package_text.split("\n"):
                line = line.strip()
                if len(line) > 3 and line not in ("패키지 옵션", "패키지 옵션 선택", "재설정"):
                    options.append({"name": line, "group": "", "spu_id": "", "price": ""})
            options = options[:20]

    # FAQ
    faq_list = []
    faq_result = (faq_raw.get("result") or faq_raw) or {}
    act_faq = faq_result.get("activity_faq", {})
    if isinstance(act_faq, dict):
        for q in (act_faq.get("faq") or []):
            if isinstance(q, dict):
                faq_list.append({
                    "q": q.get("question", ""),
                    "a": q.get("answer", ""),
                })

    raw_summary = {
        "captured_apis": list(captured.keys()),
        "dyn_price": (dyn_raw.get("result") or dyn_raw or {}).get("price", {}),
        "rating": (ov_raw.get("result") or ov_raw or {}).get("rating_info", {}),
        "faq_count": len(faq_list),
        "image_count": len(images),
        "options_count": len(options),
    }
    raw_json_str = json.dumps(raw_summary, ensure_ascii=False)

    result = {
        "product_id": product["id"],
        "activity_id": activity_id,
        "description": description,
        "highlights": json.dumps(highlights, ensure_ascii=False),
        "includes": json.dumps(includes, ensure_ascii=False),
        "excludes": json.dumps([], ensure_ascii=False),
        "notice": json.dumps(faq_list, ensure_ascii=False),
        "address": address[:500],
        "latitude": None,
        "longitude": None,
        "open_time": open_time[:500],
        "options": json.dumps(options, ensure_ascii=False),
        "images": json.dumps(images, ensure_ascii=False),
        "tags": json.dumps(tags, ensure_ascii=False),
        "min_price": min_price,
        "currency": currency,
        "cancellation_policy": cancellation_policy[:500],
        "avg_rating": avg_rating,
        "review_count": review_count,
        "validity": validity,
        "raw_json": raw_json_str,
        "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    print(f"     [OK] desc={len(description)}chars | hl={len(highlights)} | "
          f"img={len(images)} | opt={len(options)} | "
          f"rating={avg_rating} | addr={bool(address)}")

    return result


# ─── DB 저장 ────────────────────────────────────────────────────────────────────

def save_detail(conn: sqlite3.Connection, detail: dict) -> None:
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM klook_detail WHERE product_id = ?", (detail["product_id"],))
    existing = cursor.fetchone()

    fields = [
        "activity_id", "description", "highlights", "includes",
        "excludes", "notice", "address", "latitude", "longitude",
        "open_time", "options", "images", "tags", "min_price",
        "currency", "cancellation_policy", "avg_rating", "review_count",
        "validity", "raw_json", "collected_at"
    ]
    values = [detail[f] for f in fields]

    if existing:
        set_clause = ", ".join(f"{f}=?" for f in fields)
        cursor.execute(
            f"UPDATE klook_detail SET {set_clause} WHERE product_id=?",
            values + [detail["product_id"]]
        )
    else:
        col_list = "product_id, " + ", ".join(fields)
        ph = ", ".join(["?"] * (len(fields) + 1))
        cursor.execute(
            f"INSERT INTO klook_detail ({col_list}) VALUES ({ph})",
            [detail["product_id"]] + values
        )
    conn.commit()


# ─── 메인 ───────────────────────────────────────────────────────────────────────

def main():
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)

    print("=" * 70)
    print(f"Klook 상세페이지 스크래핑 시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"DB: {db_path}")
    print("=" * 70)

    init_detail_table(conn)
    products = fetch_top_products(conn, TOP_N)
    print(f"\n수집 대상: {len(products)}개 상품\n")

    if not products:
        print("klook_products 테이블에 데이터가 없습니다.")
        conn.close()
        return

    success_count = fail_count = 0

    with sync_playwright() as pw:
        # 실제 Chrome 브라우저 사용 (DataDome 우회)
        try:
            browser = pw.chromium.launch(
                channel="chrome",
                headless=False,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                    "--lang=ko-KR",
                ]
            )
            print("[INFO] Chrome 브라우저 사용")
        except Exception:
            browser = pw.chromium.launch(
                headless=False,
                args=[
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--lang=ko-KR",
                ]
            )
            print("[INFO] Chromium 브라우저 사용 (fallback)")

        ctx = browser.new_context(
            viewport=VIEWPORT,
            user_agent=USER_AGENT,
            locale="ko-KR",
            extra_http_headers={
                "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "DNT": "1",
            }
        )
        ctx.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
        """)

        page = ctx.new_page()

        for i, product in enumerate(products, 1):
            print(f"\n[{i}/{len(products)}] 수집 중...")
            try:
                detail = scrape_detail(page, product)
                save_detail(conn, detail)
                success_count += 1
            except Exception as e:
                print(f"     [FAIL] {e}")
                fail_count += 1

            if i < len(products):
                wait = random.uniform(WAIT_MIN, WAIT_MAX)
                print(f"     -> {wait:.1f}초 대기...")
                time.sleep(wait)

        browser.close()

    # ── 결과 요약 ──
    print("\n" + "=" * 70)
    print(f"완료: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"성공: {success_count} | 실패: {fail_count}")

    cursor = conn.cursor()
    cursor.execute("""
        SELECT product_id, title, activity_id, min_price, avg_rating, review_count,
               LENGTH(description) as desc_len,
               json_array_length(images) as img_count,
               json_array_length(options) as opt_count,
               json_array_length(highlights) as hl_count
        FROM v_klook_joined
        WHERE activity_id IS NOT NULL OR detail_collected_at IS NOT NULL
        ORDER BY product_id
    """)
    rows = cursor.fetchall()

    print(f"\n=== v_klook_joined 미리보기 ({len(rows)}개) ===")
    header = f"{'PID':>4} | {'상품명':^28} | {'AID':^8} | {'가격':>8} | {'별점':>4} | {'설명':>5} | {'이미지':>4} | {'옵션':>4} | {'HL':>3}"
    print(header)
    print("-" * len(header))
    for r in rows:
        tit = str(r[1] or "")[:26]
        print(f"{r[0]:>4} | {tit:<28} | {str(r[2] or ''):^8} | {str(r[3] or ''):>8} | "
              f"{str(r[4] or ''):>4} | {r[6] or 0:>5} | {r[7] or 0:>4} | {r[8] or 0:>4} | {r[9] or 0:>3}")

    print("=" * 70)
    print(f"DB: {db_path}")
    print("조회 예시:")
    print("  SELECT title, description, highlights, options FROM v_klook_joined WHERE product_id=1;")
    print("=" * 70)

    conn.close()


if __name__ == "__main__":
    main()
