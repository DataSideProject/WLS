import sys
import os
from sqlalchemy import create_engine, text

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

def patch_experience():
    engine = create_engine(CONNECTION_STRING)
    print(f"Connecting to {DB_NAME}...")
    
    with engine.connect() as conn:
        print("Starting experience patch...")
        
        # Check for bad records
        query_check = "SELECT COUNT(*) FROM fact_job_postings WHERE experience_req LIKE '20%年以上'"
        count = conn.execute(text(query_check)).scalar()
        print(f"Found {count} records with suspicious experience (e.g., 2025年以上).")
        
        if count > 0:
            # We will reset them to '經歷不拘' or attempt to re-parse (but re-parsing from raw is hard without Source Raw).
            # Simplest is to set to '經歷不拘' as a safe fallback or NULL.
            # Or if it's 2025, it's definitely wrong.
            stmt = text("UPDATE fact_job_postings SET experience_req = '經歷不拘' WHERE experience_req LIKE '20%年以上'")
            result = conn.execute(stmt)
            conn.commit()
            print(f"Updated {result.rowcount} rows to '經歷不拘'.")
        else:
            print("No bad records found.")

if __name__ == "__main__":
    patch_experience()
