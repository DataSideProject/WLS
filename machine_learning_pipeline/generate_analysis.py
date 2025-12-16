
import pandas as pd
import numpy as np
import sys
import os
import json
from datetime import datetime
from collections import Counter
from sqlalchemy import create_engine

# Setup paths
current_dir = os.path.dirname(os.path.abspath(__file__))
wls_root = os.path.dirname(current_dir)
crawler_path = os.path.join(wls_root, '104_jobdata_crawler_final')

if current_dir not in sys.path: sys.path.append(current_dir)
if wls_root not in sys.path: sys.path.insert(0, wls_root)
if crawler_path not in sys.path: sys.path.append(crawler_path)

# Import dependencies
try:
    from ml_data_loader import load_job_data_from_db
    from db_config import DB_HOST, DB_USER, DB_PASSWORD
    from analysis_utils import get_dashboard_stats  # Importing directly from crawler folder
    DB_NAME = 'job_data_warehouse'
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)

def get_db_engine():
    return create_engine(f'mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:3306/{DB_NAME}')

def prepare_dataframe_for_analysis(df):
    """
    Replicates necessary feature engineering for analysis_utils.
    """
    # 1. City for Stratify
    def parse_city(addr):
        if pd.isna(addr): return 'Unknown'
        addr = str(addr)
        if len(addr) >= 3: return addr[:3]
        return addr
    df['city_for_stratify'] = df['location'].apply(parse_city)

    # 2. Categories (One-Hot for Boxplot)
    all_cats = []
    for cats in df['job_categories'].dropna():
        all_cats.extend([c.strip() for c in str(cats).split(',') if c.strip()])
    
    # Use top 20 like logic
    top_cats = [c[0] for c in Counter(all_cats).most_common(20)]
    for cat in top_cats:
        df[f'cat_{cat}'] = df['job_categories'].astype(str).str.contains(cat, regex=False, na=False).astype(int)

    # 3. Calculate Salary Averages
    # Actual Average
    df['salary_avg'] = (pd.to_numeric(df['salary_min'], errors='coerce') + pd.to_numeric(df['salary_max'], errors='coerce')) / 2
    
    # Predicted Average (if available)
    if 'predicted_salary_min' in df.columns:
        df['pred_min'] = pd.to_numeric(df['predicted_salary_min'], errors='coerce')
        df['pred_max'] = pd.to_numeric(df['predicted_salary_max'], errors='coerce')
        df['pred_avg'] = (df['pred_min'] + df['pred_max']) / 2
        
        # Fallback to actual if prediction missing (or purely visual preference)
        # analysis_utils prefers pred_avg if present.
    
    return df

def main():
    print("Loading Job Data...")
    df = load_job_data_from_db()
    print(f"Loaded {len(df)} rows form DB.")

    print("Loading Predictions from DB...")
    engine = get_db_engine()
    from sqlalchemy import text
    with engine.connect() as conn:
        pred_df = pd.read_sql(text("SELECT posting_id, pred_salary_min, pred_salary_max FROM fact_job_predictions"), conn)
    
    # Merge Predictions
    # Ensure posting_id is string/int consistent
    df['posting_id'] = df['posting_id'].astype(str)
    pred_df['posting_id'] = pred_df['posting_id'].astype(str)
    
    # Rename for consistency if needed (analysis_utils uses pred_min/max derived from predicted_salary_min)
    pred_df.rename(columns={
        'pred_salary_min': 'predicted_salary_min', 
        'pred_salary_max': 'predicted_salary_max'
    }, inplace=True)
    
    # Deduplicate predictions if needed (though pipeline clears table first)
    pred_df = pred_df.drop_duplicates(subset=['posting_id'], keep='last')
    
    df_merged = pd.merge(df, pred_df, on='posting_id', how='left')
    print(f"Merged with {len(pred_df)} predictions. Total rows: {len(df_merged)}")
    
    # Prepare Data
    print("Preprocessing for Dashboard...")
    df_final = prepare_dataframe_for_analysis(df_merged)
    
    # Generate Stats
    print("Generating Dashboard Stats...")
    stats = get_dashboard_stats(df_final)
    
    # Output
    output_file = 'dashboard_data.json'
    
    # Convert numpy types to native for JSON serialization
    class NpEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, np.integer):
                return int(obj)
            if isinstance(obj, np.floating):
                return float(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            return super(NpEncoder, self).default(obj)
            
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2, cls=NpEncoder)
        
    print(f"Success! Metrics saved to {output_file}")
    
    # Print key metrics for log verification
    print("Key Metrics:")
    print(json.dumps(stats['key_metrics'], indent=2, ensure_ascii=False))
    print(f"Salary Boxplot Cats: {stats['salary_boxplot']['categories']}")

if __name__ == "__main__":
    main()
