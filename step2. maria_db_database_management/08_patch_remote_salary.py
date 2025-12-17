import sys
import os
from sqlalchemy import create_engine, text
import pandas as pd
from etl_transformers import normalize_remote

# Path setup
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
try:
    from db_config import DB_HOST, DB_USER, DB_PASSWORD
except ImportError:
    print("Error: Could not find db_config.py")
    exit(1)

DB_NAME = 'job_data_warehouse'
CONNECTION_STRING = f'mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:3306/{DB_NAME}'


def patch_remote_salary():
    engine = create_engine(CONNECTION_STRING)
    print(f"Connecting to {DB_NAME}...")
    
    # 1. READ Data first (using engine to avoid connection state issues)
    print("=== 1. Reading Remote Work Data ===")
    query = "SELECT posting_id, remote_work FROM fact_job_postings WHERE remote_work IS NOT NULL AND remote_work != ''"
    df_remote = pd.read_sql(query, engine)
    
    updates = []
    for idx, row in df_remote.iterrows():
        new_val = normalize_remote(row['remote_work'])
        if new_val != row['remote_work']:
            updates.append({'p_id': row['posting_id'], 'val': new_val})
            
    if updates:
        print(f"Applying {len(updates)} remote work updates...")
        with engine.begin() as conn: # engine.begin() automatically handles transaction commit/rollback
            stmt = text("UPDATE fact_job_postings SET remote_work = :val WHERE posting_id = :p_id")
            for i, u in enumerate(updates):
                conn.execute(stmt, {'val': u['val'], 'p_id': u['p_id']})
                if i % 1000 == 0:
                    print(f"  Processed {i}...")
        print("Remote Work patch complete.")
    else:
        print("No remote work updates needed.")


    print("\n=== 2. Patching Salary (USD/JPY) ===")
    query_sal = """
        SELECT posting_id, salary_min, salary_max, salary_type 
        FROM fact_job_postings 
        WHERE salary_type LIKE '%USD%' OR salary_type LIKE '%JPY%'
    """
    df_sal = pd.read_sql(query_sal, engine)
    
    if not df_sal.empty:
        print(f"Found {len(df_sal)} currency records to patch.")
        
        with engine.begin() as conn:
            for idx, row in df_sal.iterrows():
                currency = 'USD' if 'USD' in row['salary_type'] else 'JPY'
                rate = 32.5 if currency == 'USD' else 0.22
                
                # Careful with None types
                s_min = row['salary_min']
                s_max = row['salary_max']
                
                new_min = int(s_min * rate) if pd.notnull(s_min) else None
                new_max = int(s_max * rate) if pd.notnull(s_max) else None
                
                # Clean type
                new_type = row['salary_type'].replace(f'({currency})', '').replace(currency, '').strip()
                if not new_type: new_type = '年薪'
                
                conn.execute(text("""
                    UPDATE fact_job_postings 
                    SET salary_min = :min, salary_max = :max, salary_type = :type 
                    WHERE posting_id = :pid
                """), {'min': new_min, 'max': new_max, 'type': new_type, 'pid': row['posting_id']})
                
        print("Salary patch complete.")
    else:
        print("No salary currency updates needed.")


if __name__ == "__main__":
    patch_remote_salary()
