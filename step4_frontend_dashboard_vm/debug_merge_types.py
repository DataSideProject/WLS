
import os
import sys

# Patch path for db_config
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

import pandas as pd
from sqlalchemy import create_engine, text
from ml_data_loader import load_job_data_from_db
import db_config

def check_merge():
    # 1. Load Job Data
    print("Loading Job Data...")
    job_df = load_job_data_from_db(limit=50) # Limit to save time
    if job_df.empty:
        print("Job Data Empty")
        return
    
    print(f"Job DF posting_id dtype: {job_df['posting_id'].dtype}")
    print(f"Sample Job posting_ids: {job_df['posting_id'].head().tolist()}")

    # 2. Load Predictions
    print("Loading Predictions...")
    db_name = getattr(db_config, 'DB_NAME', 'job_data_warehouse')
    engine = create_engine(f'mysql+pymysql://{db_config.DB_USER}:{db_config.DB_PASSWORD}@{db_config.DB_HOST}:3306/{db_name}')
    
    with engine.connect() as conn:
        pred_query = "SELECT posting_id, pred_salary_min, pred_salary_max FROM fact_job_predictions LIMIT 50"
        pred_df = pd.read_sql(text(pred_query), conn)
    
    if pred_df.empty:
        print("Pred Data Empty")
        return

    print(f"Pred DF posting_id dtype: {pred_df['posting_id'].dtype}")
    print(f"Sample Pred posting_ids: {pred_df['posting_id'].head().tolist()}")

    # 3. Simulate Merge
    print("\nAttempting Merge...")
    merged = pd.merge(job_df, pred_df, on='posting_id', how='inner')
    print(f"Merge Result Count: {len(merged)}")
    
    # Check if forcing type helps
    job_df['posting_id'] = job_df['posting_id'].astype(str)
    pred_df['posting_id'] = pred_df['posting_id'].astype(str)
    
    merged_str = pd.merge(job_df, pred_df, on='posting_id', how='inner')
    print(f"Merge Result (String Cast) Count: {len(merged_str)}")

if __name__ == "__main__":
    check_merge()
