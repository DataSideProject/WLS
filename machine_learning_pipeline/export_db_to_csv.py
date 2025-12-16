import pandas as pd
import sys
import os
from sqlalchemy import create_engine, text

# Setup paths
current_dir = os.path.dirname(os.path.abspath(__file__))
wls_root = os.path.dirname(current_dir)
crawler_dir = os.path.join(wls_root, '104_jobdata_crawler_final')

if wls_root not in sys.path: sys.path.insert(0, wls_root)

try:
    from ml_data_loader import load_job_data_from_db
    from db_config import DB_HOST, DB_USER, DB_PASSWORD
    DB_NAME = 'job_data_warehouse'
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)

def get_db_engine():
    return create_engine(f'mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:3306/{DB_NAME}')

def main():
    print("Loading Job Data from DB...")
    df = load_job_data_from_db()
    
    print("Loading Predictions from DB...")
    engine = get_db_engine()
    with engine.connect() as conn:
        pred_df = pd.read_sql(text("SELECT posting_id, pred_salary_min, pred_salary_max FROM fact_job_predictions"), conn)
    
    # Standardize IDs
    df['posting_id'] = df['posting_id'].astype(str)
    pred_df['posting_id'] = pred_df['posting_id'].astype(str)
    
    # Deduplicate predictions
    pred_df = pred_df.drop_duplicates(subset=['posting_id'], keep='last')
    
    # Merge
    print("Merging Data...")
    df_merged = pd.merge(df, pred_df, on='posting_id', how='left')
    
    # Rename for app compatibility (existing app expects 'predicted_salary_min' or similar? 
    # Let's check app.py columns. 
    # app.py reads: 'job_id', 'job_title', 'company', 'location', 'salary_min', 'salary_max', 'salary_note'
    # and optional 'pred_min', 'pred_max'.
    # So we should rename to match app expectations.
    
    df_merged.rename(columns={
        'pred_salary_min': 'pred_min',
        'pred_salary_max': 'pred_max',
        # app uses 'job_id' (uuid in DB?) -> DB has 'job_id' (string) and 'posting_id' (int).
        # app.py: if 'uuid' in df.columns: rename to job_id
        # Our loader returns 'job_id' as the main ID (VARCHAR).
        # Correct.
    }, inplace=True)
    
    # Fill NA for export
    # df_merged.fillna('', inplace=True) # Optional, CSV handles it.
    
    output_path = os.path.join(crawler_dir, 'job_data_final_with_predictions.csv')
    print(f"Exporting {len(df_merged)} rows to {output_path}...")
    
    df_merged.to_csv(output_path, index=False, encoding='utf-8-sig')
    print("Success! CSV generated.")

if __name__ == "__main__":
    main()
