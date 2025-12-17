import pandas as pd
from sqlalchemy import create_engine, text
import sys
import os

# 引入設定
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db_config import DB_HOST, DB_USER, DB_PASSWORD

def verify_warehouse():
    print("="*50)
    print("資料倉儲驗收報告 (Warehouse Verification Report)")
    print("="*50)
    
    DB_NAME = 'job_data_warehouse'
    conn_str = f'mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:3306/{DB_NAME}'
    
    try:
        engine = create_engine(conn_str)
        with engine.connect() as conn:
            # 1. 總量檢查
            print("[1] 資料表筆數統計 (Table Counts):")
            tables = [
                'fact_job_postings', 
                'dim_companies', 
                'dim_locations', 
                'dim_categories', 
                'dim_skills', 
                'dim_benefits',
                'dim_sources',
                'bridge_job_skills',
                'bridge_job_categories',
                'bridge_job_benefits'
            ]
            
            for tbl in tables:
                try:
                    cnt = conn.execute(text(f"SELECT COUNT(*) FROM {tbl}")).scalar()
                    print(f"   - {tbl:<25}: {cnt:>6}rows")
                except Exception as e:
                    print(f"   - {tbl:<25}: error ({e})")
                
            print("-" * 30)

            # 1.5. 來源分佈 (Source Breakdown)
            print("[1.5] 資料來源分佈 (Source Breakdown):")
            try:
                src_res = conn.execute(text("SELECT source_id, COUNT(*) FROM fact_job_postings GROUP BY source_id")).fetchall()
                for sid, scnt in src_res:
                    print(f"   - Source {sid}: {scnt} rows")
            except Exception as e:
                print(f"   - Check failed: {e}")
            
            print("-" * 30)
            
            # 2. 資料完整性 (Integrity Check)
            print("[2] 資料品質檢查 (Data Quality):")
            
            # A. 薪資解析率
            total_jobs = conn.execute(text("SELECT COUNT(*) FROM fact_job_postings")).scalar()
            sal_parsed = conn.execute(text("SELECT COUNT(*) FROM fact_job_postings WHERE salary_min > 0")).scalar()
            if total_jobs > 0:
                print(f"   - 薪資解析成功率: {sal_parsed}/{total_jobs} ({sal_parsed/total_jobs*100:.1f}%)")
            
            # B. 管理職比例
            mgr_cnt = conn.execute(text("SELECT COUNT(*) FROM fact_job_postings WHERE isManager = 1")).scalar()
            if total_jobs > 0:
                print(f"   - 管理職缺比例  : {mgr_cnt}/{total_jobs} ({mgr_cnt/total_jobs*100:.1f}%)")
            
            print("-" * 30)
            
            # 3. 隨機抽樣 (Sample View) - 確認 Join 正常
            print("[3] 隨機抽樣檢核 (Sample Check):")
            sql = """
            SELECT 
                f.job_id, 
                LEFT(f.job_title, 20) as job_title, 
                LEFT(c.name, 10) as company, 
                l.city, 
                f.salary_min, 
                f.salary_type
            FROM fact_job_postings f
            JOIN dim_companies c ON f.company_id = c.company_id
            JOIN dim_locations l ON f.location_id = l.location_id
            ORDER BY RAND()
            LIMIT 5
            """
            try:
                df_sample = pd.read_sql(sql, engine)
                print(df_sample.to_string(index=False))
            except Exception as e:
                print(f"抽樣失敗: {e}")
            
    except Exception as e:
        print(f"連線失敗或資料庫未建立: {e}")

    print("="*50)

if __name__ == "__main__":
    verify_warehouse()
