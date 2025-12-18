"""
薪資預測生成腳本 (Production)
- 讀取資料：Database (via ml_data_loader)
- 訓練模型：Ensemble (RandomForest + XGB + GB + CatBoost)
- 輸出：寫入資料庫 fact_job_predictions
"""

import pandas as pd
import numpy as np
import os
import sys
import re
from datetime import datetime
from collections import Counter
import jieba
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import VotingRegressor, RandomForestRegressor, GradientBoostingRegressor
from xgboost import XGBRegressor
from catboost import CatBoostRegressor
from sqlalchemy import create_engine, text

# Setup paths
current_dir = os.path.dirname(os.path.abspath(__file__))
wls_root = os.path.dirname(current_dir)
if current_dir not in sys.path:
    sys.path.append(current_dir)
if wls_root not in sys.path:
    sys.path.insert(0, wls_root)

# Import Loader & Config
try:
    from ml_data_loader import load_job_data_from_db
    from db_config import DB_HOST, DB_USER, DB_PASSWORD
    DB_NAME = 'job_data_warehouse'
except ImportError as e:

    with open('gen_error_global.txt', 'w') as f:
        f.write(f"Import Error: {e}")
    print(f"Import Error: {e}")
    exit(1)

def get_db_engine():
    return create_engine(f'mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:3306/{DB_NAME}')

def get_segment_name(row):
    src = str(row.get('source', '')).strip()
    exp = float(row.get('exp_years_raw', 0))
    
    if src == 'CakeResume':
        return 'CakeResume'
    elif src == '104':
        if exp >= 3:
            return '104_Senior'
        elif exp > 0:
            return '104_Junior'
        else: # exp == 0
            return '104_Unspecified'
    else:
        # Fallback for unknown sources (treat as 104 Unspecified or generic)
        return '104_Unspecified'

def log_print(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def main():
    # ================= 1. Load Data =================
    log_print("Loading data from database...")
    df = load_job_data_from_db()
    if df.empty:
        log_print("Error: No data loaded.")
        exit(1)
    log_print(f"Loaded {len(df)} rows.")
    dups = df.columns[df.columns.duplicated()].tolist()
    if dups:
        log_print(f"WARNING: Duplicate columns found: {dups}")
        df = df.loc[:, ~df.columns.duplicated()]
        log_print("Dropped duplicate columns.")

    # Ensure numeric
    df['salary_min'] = pd.to_numeric(df['salary_min'], errors='coerce')
    df['salary_max'] = pd.to_numeric(df['salary_max'], errors='coerce')
    df['tools'] = df['tools'].fillna('')
    df['job_description'] = df['description'].fillna('')
    df['job_categories'] = df['job_categories'].fillna('')

    # ================= 2. Feature Engineering (Mirrored) =================
    log_print("Feature Engineering...")

    # 1. City
    def parse_city(addr):
        if pd.isna(addr): return 'Unknown'
        addr = str(addr)
        # Location should be synthesized by loader now (City+District)
        if len(addr) >= 3: return addr[:3] # Take top level (e.g. 台北市)
        return addr

    df['city_for_stratify'] = df['location'].apply(parse_city)
    city_counts = df['city_for_stratify'].value_counts()
    top_cities = city_counts.head(10).index

    # 2. Job Title
    top10_jobs = df['job_title'].value_counts().head(10).index.tolist()
    for job in top10_jobs:
        safe = job.replace('/', '_').replace(' ', '_')
        df[f'is_{safe}'] = df['job_title'].astype(str).str.contains(job, regex=False, na=False).astype(int)

    # 3. Skills
    all_tools = []
    for tools in df['tools'].dropna():
        all_tools.extend([t.strip().lower() for t in str(tools).split(',') if t.strip() and t.strip() not in ['--', '不拘']])
    top_skills = [t[0] for t in Counter(all_tools).most_common(20)]
    for skill in top_skills:
        df[f'skill_{skill}'] = df['tools'].astype(str).str.contains(skill, case=False, na=False).astype(int)

    # 4. Education
    def parse_education_level_v7(text):
        if pd.isna(text): return 0
        text = str(text).lower()
        if any(x in text for x in ['博士', 'phd', 'doctorate']): return 5
        if any(x in text for x in ['碩士', 'master', 'graduate']): return 4
        if any(x in text for x in ['大學', 'bachelor', 'university', 'degree']): return 3
        if any(x in text for x in ['專科', 'associate']): return 2
        if any(x in text for x in ['高中', '高職', 'high school']): return 1
        return 0 
    df['edu_level'] = df['education'].apply(parse_education_level_v7)

    # 5. Manager
    if 'isManager' in df.columns:
        df['is_manager'] = df['isManager'].apply(lambda x: 1 if str(x) in ['1', 'Y', 'True'] else 0)
    else:
        df['is_manager'] = 0

    # 6. Experience
    def parse_experience_years_v7(text):
        if pd.isna(text): return 0.0
        s = str(text).lower()
        match = re.search(r'(\d+)\s*年以上', s)
        if match: return float(match.group(1))
        if "經歷不拘" in s or "經驗不拘" in s: return 0.0
        match = re.search(r'(\d+)\+?\s*years?', s)
        if match: return float(match.group(1))
        if "senior" in s: return 5.0
        if "mid" in s: return 3.0
        return 0.0
    df['exp_years_raw'] = df['experience'].apply(parse_experience_years_v7)

    # 7. Categories
    all_cats = []
    for cats in df['job_categories'].dropna():
        all_cats.extend([c.strip() for c in str(cats).split(',') if c.strip()])
    top_cats = [c[0] for c in Counter(all_cats).most_common(20)]
    for cat in top_cats:
        df[f'cat_{cat}'] = df['job_categories'].astype(str).str.contains(cat, regex=False, na=False).astype(int)

    # 8. Company
    top_companies = df['company'].value_counts().head(30).index
    for comp in top_companies:
        safe_comp = re.sub(r'[^\w]', '', str(comp))
        if not safe_comp: safe_comp = 'unknown_company'
        df[f'company_{safe_comp}'] = (df['company'] == comp).astype(int)

    # 9. Benefits
    if 'benefits' in df.columns:
        df['benefits'] = df['benefits'].fillna('')
        all_benefits = []
        for bens in df['benefits']:
            all_benefits.extend([b.strip() for b in str(bens).split(',') if b.strip()])
        top_benefits = [b[0] for b in Counter(all_benefits).most_common(20)]
        for ben in top_benefits:
            df[f'ben_{ben}'] = df['benefits'].astype(str).str.contains(ben, regex=False, na=False).astype(int)

    # 9. TF-IDF
    def jieba_tokenizer(text):
        return jieba.lcut(text)

    texts = df['job_description'].fillna('').astype(str)
    vectorizer = TfidfVectorizer(max_features=100, tokenizer=jieba_tokenizer, token_pattern=None, ngram_range=(1, 2))
    try:
        tfidf_matrix = vectorizer.fit_transform(texts)
        for i, name in enumerate(vectorizer.get_feature_names_out()):
            clean_name = re.sub(r'[^\w]', '', name)
            df[f'desc_{clean_name}_{i}'] = tfidf_matrix[:, i].toarray().flatten()
    except ValueError:
        pass # Empty vocabulary

    # 10. Cross Features
    for job in top10_jobs:
        safe = job.replace('/', '_').replace(' ', '_')
        for city in top_cities:
            df[f'{safe}_in_{city}'] = df[f'is_{safe}'] * (df['city_for_stratify'] == city).astype(int)
    for skill in top_skills:
        for city in top_cities:
            df[f'skill_{skill}_in_{city}'] = df[f'skill_{skill}'] * (df['city_for_stratify'] == city).astype(int)

    # Scaling
    df['exp_years_scaled'] = df['exp_years_raw']
    scaler_num = StandardScaler()
    df[['exp_years_scaled', 'edu_level']] = scaler_num.fit_transform(df[['exp_years_scaled', 'edu_level']])

    # Define Features List (Dynamically)
    features = []
    for col in df.columns:
        if col.startswith('is_') or col.startswith('skill_') or col.startswith('industry_') or \
        col.startswith('cat_') or col.startswith('company_') or col.startswith('desc_') or \
        col.startswith('ben_') or '_in_' in col:
            features.append(col)
    features.extend(['exp_years_scaled', 'edu_level', 'is_manager'])
    # Remove non-features
    features = [f for f in features if f not in ['salary_min', 'salary_max']]
    log_print(f"Training with {len(features)} features.")

    # ================= 3. Training & Prediction (Granular Segmentation) =================
    
    # 1. Prepare Features & Data
    # Use STRICT Filtering for Training (Fix Data Leakage: exclude 0/Negotiable salaries)
    # Note: NaNs were filled with 0 by loader, so we must check > 0
    mask_train_strict = (df['salary_min'] > 0) & (df['salary_max'] > 0)
    train_full = df[mask_train_strict].copy()
    
    if train_full.empty:
        log_print("Error: No valid training data (salary > 0).")
        exit(1)
        
    log_print(f"Training Data Size (Strict > 0): {len(train_full)} rows.")
    
    # Helper to build model
    def build_ensemble(segment_name):
        rf = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
        gb = GradientBoostingRegressor(n_estimators=100, random_state=42)
        xgb = XGBRegressor(n_estimators=200, learning_rate=0.05, max_depth=6, random_state=42, n_jobs=-1)
        # Use unique train_dir to avoid conflict
        cat = CatBoostRegressor(iterations=200, depth=8, learning_rate=0.05, random_seed=42, verbose=0, 
                               train_dir=os.path.join(current_dir, f'catboost_info_{segment_name}'))
        return VotingRegressor([('rf', rf), ('xgb', xgb), ('gb', gb), ('cat', cat)])

    # Identify Segments
    train_full['segment'] = train_full.apply(get_segment_name, axis=1)
    df['segment'] = df.apply(get_segment_name, axis=1) # Apply to all data for prediction lookup
    
    segments = ['104_Senior', '104_Junior', '104_Unspecified', 'CakeResume']
    models_min = {}
    models_max = {}
    
    # Initialize prediction columns with NaN
    df['predicted_salary_min'] = np.nan
    df['predicted_salary_max'] = np.nan

    # 2. Train and Predict by Segment
    for seg in segments:
        log_print(f"\nProcessing Segment: {seg}...")
        
        # --- Training ---
        seg_train_data = train_full[train_full['segment'] == seg]
        n_train = len(seg_train_data)
        
        if n_train < 10:
            log_print(f"  Warning: Not enough training data for {seg} ({n_train} rows). Skipping custom model (Fallback behavior needed?).")
            # If CakeResume has 0 rows (unlikely), we might skip. 
            # But currently Cake has ~280 rows.
            # If skipped, predictions will remain NaN? Or fallback to global?
            # For now, let's assume we have data. If not, we might need a fallback.
            if n_train == 0: continue
            
        X_train_seg = seg_train_data[features].apply(pd.to_numeric, errors='coerce').fillna(0).values
        y_min_seg = np.log1p(seg_train_data['salary_min'])
        y_max_seg = np.log1p(seg_train_data['salary_max'])
        
        log_print(f"  Training Min Model ({n_train} rows)...")
        model_min = build_ensemble(f"{seg}_min")
        model_min.fit(X_train_seg, y_min_seg)
        models_min[seg] = model_min
        
        log_print(f"  Training Max Model ({n_train} rows)...")
        model_max = build_ensemble(f"{seg}_max")
        model_max.fit(X_train_seg, y_max_seg)
        models_max[seg] = model_max
        
        # --- Prediction (Apply to ALL rows belonging to this segment) ---
        mask_seg_all = (df['segment'] == seg)
        X_all_seg = df.loc[mask_seg_all, features].apply(pd.to_numeric, errors='coerce').fillna(0).values
        
        if len(X_all_seg) > 0:
            pred_min_log = model_min.predict(X_all_seg)
            pred_max_log = model_max.predict(X_all_seg)
            
            df.loc[mask_seg_all, 'predicted_salary_min'] = np.expm1(pred_min_log)
            df.loc[mask_seg_all, 'predicted_salary_max'] = np.expm1(pred_max_log)
            log_print(f"  Generated predictions for {len(X_all_seg)} rows.")
            
    # Fallback for any rows that didn't get a segment or failed prediction (fill with Unspecified model if available?)
    # For now, we leave them as NaN or check counts
    missing_pred = df['predicted_salary_min'].isna().sum()
    if missing_pred > 0:
        log_print(f"Warning: {missing_pred} rows have no prediction (Unknown segment or empty model).")

    log_print("PreparingDB Insert...")
    # Handle duplicate posting_id columns safely (if any, though loader handles posting_id usually)
    # Loader returns 'posting_id' in df
    if 'posting_id' not in df.columns:
        # Fallback if loader didn't return it? (It should)
        log_print("Error: posting_id missing from dataframe")
        return

    posting_ids = df['posting_id']
    if isinstance(posting_ids, pd.DataFrame): posting_ids = posting_ids.iloc[:, 0]

    # Handle duplicate salary columns safely
    pred_min = df['predicted_salary_min']
    if isinstance(pred_min, pd.DataFrame): pred_min = pred_min.iloc[:, 0]
    
    pred_max = df['predicted_salary_max']
    if isinstance(pred_max, pd.DataFrame): pred_max = pred_max.iloc[:, 0]

    db_df = pd.DataFrame({
        'posting_id': posting_ids,
        'pred_salary_min': pred_min,
        'pred_salary_max': pred_max
    })
    db_df['model_version'] = 'v1.0'
    db_df['prediction_time'] = datetime.now() # Schema has prediction_time, matches created_at logic

    # Clean nulls
    db_df = db_df.dropna(subset=['posting_id'])

    # Connect to DB
    engine = get_db_engine()
    conn = engine.connect()
    trans = conn.begin()

    try:
        # 1. Clear Table (Removed to keep history)
        # log_print("Clearing fact_job_predictions table...")
        # conn.execute(text("DELETE FROM fact_job_predictions")) 
        
        # 2. Insert
        log_print(f"Appending {len(db_df)} predictions to DB (History Mode)...")
        # Chunk insert to avoid packet size issues
        chunk_size = 1000
        for i in range(0, len(db_df), chunk_size):
            chunk = db_df.iloc[i:i+chunk_size]
            chunk.to_sql('fact_job_predictions', conn, if_exists='append', index=False)
            log_print(f"  Inserted batch {i//chunk_size + 1}...")
        
        trans.commit()
        log_print("Success! Predictions committed to database.")
        
    except Exception as e:
        trans.rollback()
        raise e
    finally:
        conn.close()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        with open('gen_error_global.txt', 'w') as f:
            f.write(str(e))
        import traceback
        traceback.print_exc()
        exit(1)
