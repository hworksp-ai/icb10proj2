"""
DB 스키마 및 데이터 확인 스크립트

klook_products.db의 테이블 구조, 컬럼 정보, 샘플 데이터를 출력합니다.
"""

import sqlite3
import os

def check_db():
    """DB 스키마 및 샘플 데이터를 출력합니다."""
    # 스크립트 위치 기준으로 DB 경로 설정
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(base_dir, "data", "klook_products.db")
    
    print(f"DB 경로: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 테이블 목록 확인
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print(f"\n=== 테이블 목록 ===")
    print(tables)
    
    # 각 테이블 상세 정보 확인
    for table in tables:
        tname = table[0]
        cursor.execute(f"PRAGMA table_info({tname})")
        cols = cursor.fetchall()
        cursor.execute(f"SELECT COUNT(*) FROM {tname}")
        count = cursor.fetchone()[0]
        
        print(f"\n=== Table: {tname} ({count}개 행) ===")
        for col in cols:
            print(f"  {col}")
        
        # 샘플 데이터 출력
        cursor.execute(f"SELECT * FROM {tname} LIMIT 3")
        rows = cursor.fetchall()
        print(f"\n  샘플 데이터 (최대 3행):")
        for r in rows:
            print(f"  {r}")
    
    conn.close()

if __name__ == "__main__":
    check_db()
