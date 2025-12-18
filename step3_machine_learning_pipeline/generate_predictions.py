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

    # ================= 3. Training & Prediction =================
    def build_ensemble():
        rf = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
        gb = GradientBoostingRegressor(n_estimators=100, random_state=42)
        xgb = XGBRegressor(n_estimators=200, learning_rate=0.05, max_depth=6, random_state=42, n_jobs=-1)
        cat = CatBoostRegressor(iterations=200, depth=8, learning_rate=0.05, random_seed=42, verbose=0, train_dir=os.path.join(current_dir, 'catboost_info'))
        return VotingRegressor([('rf', rf), ('xgb', xgb), ('gb', gb), ('cat', cat)])

    # Prepare Data
    X = df[features].fillna(0)
    mask_train = df['salary_min'].notna() & df['salary_max'].notna() & (df['salary_min'] > 0)
    train_df = df[mask_train]

    if train_df.empty:
        log_print("Error: No training data available (empty salary cols).")
        exit(1)

    log_print(f"Training on {len(train_df)} rows...")
    log_print(f"Features: {features[:10]} ... ({len(features)} total)")
    
    X = df[features].apply(pd.to_numeric, errors='coerce').fillna(0)
    log_print(f"X shape: {X.shape}")
    mask_train = df['salary_min'].notna() & df['salary_max'].notna() & (df['salary_min'] > 0)
    train_df = df[mask_train]

    X_train = X.loc[mask_train]
    y_min = np.log1p(train_df['salary_min'])
    
    # Force numeric float and convert to numpy array to avoid DataFrame/XGBoost issues
    X_df = df[features].apply(pd.to_numeric, errors='coerce').fillna(0).astype(float)
    
    mask_train = df['salary_min'].notna() & df['salary_max'].notna() & (df['salary_min'] > 0)
    train_df = df[mask_train]

    # Convert to numpy
    X_train = X_df.loc[mask_train].values
    X_all = X_df.values # For prediction

    y_min = np.log1p(train_df['salary_min'])
    y_max = np.log1p(train_df['salary_max'])

    # Train Min Model
    log_print("Training Salary Min Model...")
    model_min = build_ensemble()
    model_min.fit(X_train, y_min)
    df['pred_min_log'] = model_min.predict(X_all)
    df['predicted_salary_min'] = np.expm1(df['pred_min_log'])

    # Train Max Model
    log_print("Training Salary Max Model...")
    model_max = build_ensemble()
    model_max.fit(X_train, y_max)
    df['pred_max_log'] = model_max.predict(X_all)
    df['predicted_salary_max'] = np.expm1(df['pred_max_log'])

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
