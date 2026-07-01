"""
klook_detail JSON 컬럼 파싱 및 확장 스크립트

klook_detail 테이블의 JSON 컬럼들을 파싱하여:
1. klook_detail 에 평면 컬럼 추가 (count, 번호별 값, 텍스트 요약)
2. 연관 테이블 생성
   - klook_highlights  : 하이라이트 행별 테이블
   - klook_images      : 이미지 URL 행별 테이블
   - klook_options     : 상품 옵션 행별 테이블
3. v_klook_full 통합 뷰 재생성 (products + detail + 첫 번째 이미지/옵션)

실행 후 조회 예시:
  SELECT * FROM klook_highlights WHERE product_id = 1;
  SELECT * FROM klook_images     WHERE product_id = 1;
  SELECT * FROM klook_options    WHERE product_id = 1;
  SELECT * FROM v_klook_full     WHERE product_id = 1;
"""

import sqlite3
import json
import os
from datetime import datetime


def get_db_path() -> str:
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "data", "klook_products.db")


# ─── 1. klook_detail 평면 컬럼 추가 ─────────────────────────────────────────────

FLAT_COLS = {
    # highlights
    "highlights_count":  "INTEGER",
    "highlight_1":       "TEXT",
    "highlight_2":       "TEXT",
    "highlight_3":       "TEXT",
    "highlights_text":   "TEXT",   # 전체 줄바꿈 연결

    # includes / excludes
    "includes_count":    "INTEGER",
    "includes_text":     "TEXT",
    "excludes_count":    "INTEGER",
    "excludes_text":     "TEXT",

    # tags
    "tags_count":        "INTEGER",
    "tag_1":             "TEXT",
    "tag_2":             "TEXT",
    "tag_3":             "TEXT",
    "tags_text":         "TEXT",   # 쉼표 연결

    # images
    "images_count":      "INTEGER",
    "image_url_1":       "TEXT",
    "image_url_2":       "TEXT",
    "image_url_3":       "TEXT",
    "image_url_4":       "TEXT",

    # options
    "options_count":     "INTEGER",
    "option_1_group":    "TEXT",
    "option_1_name":     "TEXT",
    "option_1_price":    "TEXT",
    "option_2_name":     "TEXT",
    "option_2_price":    "TEXT",
    "option_3_name":     "TEXT",
    "option_3_price":    "TEXT",

    # notice (FAQ)
    "notice_count":      "INTEGER",
    "notice_text":       "TEXT",   # "Q: ... A: ..." 형태 연결

    # raw_json 추출 필드
    "price_sale":        "TEXT",   # 판매가 (₩ 표시 포함)
    "price_underline":   "TEXT",   # 원가
    "rating_desc":       "TEXT",   # 별점 설명 (만족해요 등)
}


def add_flat_columns(conn: sqlite3.Connection) -> None:
    """klook_detail 에 평면 컬럼을 추가합니다 (이미 있으면 건너뜀)."""
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(klook_detail)")
    existing = {row[1] for row in cur.fetchall()}

    added = []
    for col, col_type in FLAT_COLS.items():
        if col not in existing:
            cur.execute(f"ALTER TABLE klook_detail ADD COLUMN {col} {col_type}")
            added.append(col)

    conn.commit()
    if added:
        print(f"[ALTER] 컬럼 {len(added)}개 추가: {added}")
    else:
        print("[ALTER] 추가할 컬럼 없음 (이미 존재)")


def _jloads(val) -> list | dict:
    """JSON 파싱 헬퍼."""
    if not val:
        return []
    try:
        return json.loads(val)
    except Exception:
        return []


def fill_flat_columns(conn: sqlite3.Connection) -> None:
    """모든 klook_detail 행을 읽어 평면 컬럼을 업데이트합니다."""
    cur = conn.cursor()
    cur.execute(
        "SELECT id, product_id, highlights, includes, excludes, "
        "tags, images, options, notice, raw_json FROM klook_detail"
    )
    rows = cur.fetchall()
    print(f"[FILL] {len(rows)}개 행 파싱 중...")

    updated = 0
    for row in rows:
        (det_id, prod_id,
         j_highlights, j_includes, j_excludes,
         j_tags, j_images, j_options, j_notice,
         j_raw) = row

        hl  = _jloads(j_highlights)
        inc = _jloads(j_includes)
        exc = _jloads(j_excludes)
        tgs = _jloads(j_tags)
        img = _jloads(j_images)
        opt = _jloads(j_options)
        ntc = _jloads(j_notice)
        raw = _jloads(j_raw) if isinstance(_jloads(j_raw), dict) else {}

        def _s(lst, i):
            """리스트의 i번째 값을 문자열로 반환."""
            return str(lst[i]).strip() if i < len(lst) else None

        def _opt_field(lst, i, field):
            """옵션 리스트의 i번째 딕셔너리에서 field 값을 반환."""
            if i < len(lst) and isinstance(lst[i], dict):
                return str(lst[i].get(field, "") or "").strip() or None
            return None

        # notice 텍스트 조합
        notice_parts = []
        for item in ntc:
            if isinstance(item, dict):
                q = item.get("q", "").strip()
                a = item.get("a", "").strip()
                if q:
                    notice_parts.append(f"Q: {q}")
                if a:
                    notice_parts.append(f"A: {a}")
            elif isinstance(item, str) and item.strip():
                notice_parts.append(item.strip())
        notice_text = "\n".join(notice_parts) if notice_parts else None

        # raw_json 중첩 필드 추출
        dyn_price = raw.get("dyn_price", {})
        if not isinstance(dyn_price, dict):
            dyn_price = {}
        rating_info = raw.get("rating", {})
        if not isinstance(rating_info, dict):
            rating_info = {}

        params = (
            # highlights
            len(hl),
            _s(hl, 0), _s(hl, 1), _s(hl, 2),
            "\n".join(str(h) for h in hl) or None,
            # includes / excludes
            len(inc),
            ", ".join(str(i) for i in inc) or None,
            len(exc),
            ", ".join(str(e) for e in exc) or None,
            # tags
            len(tgs),
            _s(tgs, 0), _s(tgs, 1), _s(tgs, 2),
            ", ".join(str(t) for t in tgs) or None,
            # images
            len(img),
            _s(img, 0), _s(img, 1), _s(img, 2), _s(img, 3),
            # options
            len(opt),
            _opt_field(opt, 0, "group"),
            _opt_field(opt, 0, "name"),
            _opt_field(opt, 0, "price"),
            _opt_field(opt, 1, "name"),
            _opt_field(opt, 1, "price"),
            _opt_field(opt, 2, "name"),
            _opt_field(opt, 2, "price"),
            # notice
            len(ntc),
            notice_text,
            # raw_json 추출
            str(dyn_price.get("sale_price", "") or "").strip() or None,
            str(dyn_price.get("underline_price", "") or "").strip() or None,
            str(rating_info.get("rating_desc", "") or "").strip() or None,
            # WHERE
            det_id,
        )

        cur.execute("""
            UPDATE klook_detail SET
                highlights_count=?, highlight_1=?, highlight_2=?, highlight_3=?,
                highlights_text=?,
                includes_count=?, includes_text=?,
                excludes_count=?, excludes_text=?,
                tags_count=?, tag_1=?, tag_2=?, tag_3=?, tags_text=?,
                images_count=?, image_url_1=?, image_url_2=?, image_url_3=?, image_url_4=?,
                options_count=?, option_1_group=?, option_1_name=?, option_1_price=?,
                option_2_name=?, option_2_price=?, option_3_name=?, option_3_price=?,
                notice_count=?, notice_text=?,
                price_sale=?, price_underline=?, rating_desc=?
            WHERE id=?
        """, params)
        updated += 1

    conn.commit()
    print(f"[FILL] {updated}개 행 업데이트 완료")


# ─── 2. 연관 테이블 생성 ─────────────────────────────────────────────────────────

def create_related_tables(conn: sqlite3.Connection) -> None:
    """klook_highlights / klook_images / klook_options 테이블을 생성합니다."""
    cur = conn.cursor()

    cur.execute("DROP TABLE IF EXISTS klook_highlights")
    cur.execute("""
        CREATE TABLE klook_highlights (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            detail_id   INTEGER NOT NULL,
            product_id  INTEGER NOT NULL,
            seq         INTEGER NOT NULL,
            text        TEXT NOT NULL,
            FOREIGN KEY (detail_id)  REFERENCES klook_detail(id),
            FOREIGN KEY (product_id) REFERENCES klook_products(id)
        )
    """)

    cur.execute("DROP TABLE IF EXISTS klook_images")
    cur.execute("""
        CREATE TABLE klook_images (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            detail_id   INTEGER NOT NULL,
            product_id  INTEGER NOT NULL,
            seq         INTEGER NOT NULL,
            image_url   TEXT NOT NULL,
            FOREIGN KEY (detail_id)  REFERENCES klook_detail(id),
            FOREIGN KEY (product_id) REFERENCES klook_products(id)
        )
    """)

    cur.execute("DROP TABLE IF EXISTS klook_options")
    cur.execute("""
        CREATE TABLE klook_options (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            detail_id   INTEGER NOT NULL,
            product_id  INTEGER NOT NULL,
            seq         INTEGER NOT NULL,
            option_group TEXT,
            option_name  TEXT,
            spu_id       TEXT,
            price        TEXT,
            FOREIGN KEY (detail_id)  REFERENCES klook_detail(id),
            FOREIGN KEY (product_id) REFERENCES klook_products(id)
        )
    """)

    conn.commit()
    print("[TABLE] klook_highlights / klook_images / klook_options 생성 완료")


def fill_related_tables(conn: sqlite3.Connection) -> None:
    """klook_detail JSON 컬럼을 파싱해 연관 테이블에 데이터를 삽입합니다."""
    cur = conn.cursor()
    cur.execute("SELECT id, product_id, highlights, images, options FROM klook_detail")
    rows = cur.fetchall()

    hl_rows = []
    img_rows = []
    opt_rows = []

    for det_id, prod_id, j_hl, j_img, j_opt in rows:
        hl  = _jloads(j_hl)
        img = _jloads(j_img)
        opt = _jloads(j_opt)

        for seq, text in enumerate(hl, 1):
            text = str(text).strip()
            if text:
                hl_rows.append((det_id, prod_id, seq, text))

        for seq, url in enumerate(img, 1):
            url = str(url).strip()
            if url:
                img_rows.append((det_id, prod_id, seq, url))

        for seq, o in enumerate(opt, 1):
            if isinstance(o, dict):
                name = str(o.get("name", "") or "").strip()
                if name:
                    opt_rows.append((
                        det_id, prod_id, seq,
                        str(o.get("group", "") or "").strip() or None,
                        name,
                        str(o.get("spu_id", "") or "").strip() or None,
                        str(o.get("price", "") or "").strip() or None,
                    ))

    cur.executemany(
        "INSERT INTO klook_highlights (detail_id, product_id, seq, text) VALUES (?,?,?,?)",
        hl_rows
    )
    cur.executemany(
        "INSERT INTO klook_images (detail_id, product_id, seq, image_url) VALUES (?,?,?,?)",
        img_rows
    )
    cur.executemany(
        "INSERT INTO klook_options (detail_id, product_id, seq, option_group, option_name, spu_id, price) VALUES (?,?,?,?,?,?,?)",
        opt_rows
    )
    conn.commit()
    print(f"[INSERT] 하이라이트 {len(hl_rows)}건 | 이미지 {len(img_rows)}건 | 옵션 {len(opt_rows)}건")


# ─── 3. 통합 뷰 재생성 ───────────────────────────────────────────────────────────

def recreate_views(conn: sqlite3.Connection) -> None:
    """v_klook_joined (기존) 및 v_klook_full (확장) 뷰를 생성합니다."""
    cur = conn.cursor()

    # 기존 v_klook_joined 재생성 (avg_rating 등 신규 컬럼 포함)
    cur.execute("DROP VIEW IF EXISTS v_klook_joined")
    cur.execute("""
        CREATE VIEW v_klook_joined AS
        SELECT
            p.id            AS product_id,
            p.title,
            p.price         AS price_raw,
            p.url,
            p.deep_link,
            d.activity_id,
            d.description,
            d.avg_rating,
            d.review_count,
            d.rating_desc,
            d.min_price,
            d.price_sale,
            d.price_underline,
            d.currency,
            d.address,
            d.latitude,
            d.longitude,
            d.open_time,
            d.validity,
            d.cancellation_policy,
            d.highlights_count,
            d.highlights_text,
            d.highlight_1, d.highlight_2, d.highlight_3,
            d.includes_count, d.includes_text,
            d.excludes_count, d.excludes_text,
            d.tags_count,   d.tags_text,
            d.tag_1, d.tag_2, d.tag_3,
            d.images_count,
            d.image_url_1, d.image_url_2, d.image_url_3, d.image_url_4,
            d.options_count,
            d.option_1_group, d.option_1_name, d.option_1_price,
            d.option_2_name,  d.option_2_price,
            d.option_3_name,  d.option_3_price,
            d.notice_count,
            d.notice_text,
            d.collected_at  AS detail_collected_at
        FROM klook_products p
        LEFT JOIN klook_detail d ON p.id = d.product_id
    """)

    # v_klook_full: products + detail 평면 컬럼 + 연관 테이블의 집계
    cur.execute("DROP VIEW IF EXISTS v_klook_full")
    cur.execute("""
        CREATE VIEW v_klook_full AS
        SELECT
            j.*,
            (SELECT GROUP_CONCAT(text, ' | ')
             FROM klook_highlights WHERE product_id = j.product_id
             ORDER BY seq) AS all_highlights,
            (SELECT GROUP_CONCAT(image_url, ' | ')
             FROM klook_images WHERE product_id = j.product_id
             ORDER BY seq) AS all_images,
            (SELECT GROUP_CONCAT(
                COALESCE(option_group || ' > ', '') || option_name ||
                CASE WHEN price IS NOT NULL AND price != '' THEN ' (' || price || ')' ELSE '' END,
                ' | ')
             FROM klook_options WHERE product_id = j.product_id
             ORDER BY seq) AS all_options
        FROM v_klook_joined j
    """)

    conn.commit()
    print("[VIEW] v_klook_joined / v_klook_full 뷰 재생성 완료")


# ─── 메인 ────────────────────────────────────────────────────────────────────────

def main():
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)

    print("=" * 70)
    print(f"JSON 컬럼 파싱 및 확장 시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"DB: {db_path}")
    print("=" * 70)

    # 1) 평면 컬럼 추가 및 채우기
    print("\n[1단계] klook_detail 평면 컬럼 추가")
    add_flat_columns(conn)
    fill_flat_columns(conn)

    # 2) 연관 테이블 생성 및 채우기
    print("\n[2단계] 연관 테이블 생성 (klook_highlights / klook_images / klook_options)")
    create_related_tables(conn)
    fill_related_tables(conn)

    # 3) 뷰 재생성
    print("\n[3단계] 뷰 재생성")
    recreate_views(conn)

    # ── 결과 확인 ──
    cur = conn.cursor()

    print("\n" + "=" * 70)
    print("=== klook_detail 평면 컬럼 확인 (상위 10개) ===")
    cur.execute("""
        SELECT product_id, activity_id,
               highlights_count, highlight_1,
               tags_count, tag_1, tag_2,
               images_count, image_url_1,
               options_count, option_1_name,
               price_sale, rating_desc,
               includes_text
        FROM klook_detail
        WHERE product_id <= 10
        ORDER BY product_id
    """)
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    for row in rows:
        d = dict(zip(cols, row))
        print(f"\n  [{d['product_id']}] activity_id={d['activity_id']}")
        print(f"    highlights: {d['highlights_count']}개 | 첫번째: {str(d['highlight_1'] or '')[:60]}")
        print(f"    tags: {d['tags_count']}개 | {d['tag_1']} / {d['tag_2']}")
        print(f"    images: {d['images_count']}개 | url_1: {str(d['image_url_1'] or '')[:60]}")
        print(f"    options: {d['options_count']}개 | 첫번째: {d['option_1_name']}")
        print(f"    price_sale={d['price_sale']} | rating_desc={d['rating_desc']}")
        print(f"    includes_text: {d['includes_text']}")

    print("\n" + "=" * 70)
    print("=== 연관 테이블 행 수 ===")
    for tbl in ["klook_highlights", "klook_images", "klook_options"]:
        cur.execute(f"SELECT COUNT(*) FROM {tbl}")
        cnt = cur.fetchone()[0]
        print(f"  {tbl}: {cnt}행")

    print("\n" + "=" * 70)
    print("=== v_klook_full 에버랜드 샘플 ===")
    cur.execute("""
        SELECT product_id, title, avg_rating, review_count, price_sale,
               address, tag_1, tag_2, tag_3,
               highlights_count, highlight_1,
               images_count, image_url_1,
               options_count, option_1_name,
               includes_text
        FROM v_klook_full
        WHERE product_id = 1
    """)
    row = cur.fetchone()
    if row:
        cols2 = [d[0] for d in cur.description]
        for k, v in zip(cols2, row):
            print(f"  {k}: {str(v or '')[:100]}")

    print("\n" + "=" * 70)
    print("조회 예시:")
    print("  -- 하이라이트 전체")
    print("  SELECT product_id, seq, text FROM klook_highlights WHERE product_id=1;")
    print("  -- 이미지 전체")
    print("  SELECT product_id, seq, image_url FROM klook_images WHERE product_id=1;")
    print("  -- 옵션 전체")
    print("  SELECT product_id, seq, option_group, option_name, price FROM klook_options WHERE product_id=1;")
    print("  -- 통합 뷰")
    print("  SELECT title, avg_rating, price_sale, tag_1, highlight_1, image_url_1 FROM v_klook_full WHERE product_id=1;")
    print("=" * 70)

    conn.close()


if __name__ == "__main__":
    main()
