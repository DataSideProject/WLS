import os
import sys

# Add parent directory to path to find real db_config.py
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

import pandas as pd
from sqlalchemy import create_engine, text
from ml_data_loader import load_job_data_from_db
import db_config

def check_job():
    print("Loading data...")
    df = load_job_data_from_db()
    
    # Search for the job
    search_term = "AXI 演算法研發工程師"
    matches = df[df['job_title'].str.contains(search_term, na=False)]
    
    if matches.empty:
        print(f"No job found matching '{search_term}'")
        return

    print(f"Found {len(matches)} matches:")
    for _, row in matches.iterrows():
        p_id = row.get('posting_id')
        j_id = row.get('job_id')
        print(f"  Title: {row['job_title']}")
        print(f"  Posting ID: {p_id}")
        print(f"  Job ID: {j_id}")
        
        # Check prediction for this posting_id
        db_name = getattr(db_config, 'DB_NAME', 'job_data_warehouse')
        engine = create_engine(f'mysql+pymysql://{db_config.DB_USER}:{db_config.DB_PASSWORD}@{db_config.DB_HOST}:3306/{db_name}')
        with engine.connect() as conn:
            query = text(f"SELECT * FROM fact_job_predictions WHERE posting_id = '{p_id}'")
            preds = pd.read_sql(query, conn)
            
            if preds.empty:
                print("  => PREDICTION: MISSING in DB")
            else:
                print("  => PREDICTION: FOUND")
                print(preds.iloc[0].to_dict())

if __name__ == "__main__":
    check_job()
