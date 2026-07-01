"""
DB URL 데이터 확인 스크립트

klook_products.db에서 상위 10개 상품의 URL 및 deep_link 정보를 확인합니다.
"""

import sqlite3
import os

def check_urls():
    """DB에서 URL 샘플 데이터를 출력합니다."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(base_dir, "data", "klook_products.db")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, title, url, deep_link FROM klook_products ORDER BY id LIMIT 10")
    rows = cursor.fetchall()
    
    for r in rows:
        print(f"ID={r[0]}")
        print(f"  title={str(r[1])[:60]}")
        print(f"  url={r[2]}")
        print(f"  deep_link={r[3]}")
        print()
    
    conn.close()

if __name__ == "__main__":
    check_urls()
