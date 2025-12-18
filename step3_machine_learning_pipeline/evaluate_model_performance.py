"""
ML Model Evaluation & Diagnostic Script
---------------------------------------
Purpose: 
1. Audit training data quality (specifically checking for Low Salary/Hourly Wage pollution).
2. Train the ensemble model (replicating generate_predictions.py logic).
3. Generate performance metrics (R2, MAE, RMSE).
4. Generate diagnostic plots (Residuals, Actual vs Predicted).
"""

import pandas as pd
import numpy as np
import os
import sys
import re
import matplotlib.pyplot as plt
import seaborn as sns
from collections import Counter
import jieba
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import KFold
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error
from sklearn.ensemble import VotingRegressor, RandomForestRegressor, GradientBoostingRegressor
from xgboost import XGBRegressor
from catboost import CatBoostRegressor

# Setup paths
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

# Import Loader
try:
    from ml_data_loader import load_job_data_from_db
except ImportError:
    print("Error: Could not import ml_data_loader.")
    exit(1)

# Diagnostic Configuration
REPORT_DIR = os.path.join(current_dir, 'model_reports')
if not os.path.exists(REPORT_DIR):
    os.makedirs(REPORT_DIR)

# Configure Plotting (Chinese Font Support)
plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei']
plt.rcParams['axes.unicode_minus'] = False
sns.set_style("whitegrid")
sns.set(font='Microsoft JhengHei')

def log_print(msg):
    print(f"[EVAL] {msg}")

def evaluate_pipeline():
    # ================= 1. Load Data =================
    log_print("Loading data...")
    df = load_job_data_from_db()
    
    if df.empty:
        log_print("Error: No data loaded.")
        return

    # ================= 2. DATA QUALITY CHECK (The Investigation) =================
    log_print("--- DATA QUALITY CHECK ---")
    
    # Check Salary Type Distribution if available
    if 'salary_type' in df.columns:
        log_print("Salary Type Distribution:")
        print(df['salary_type'].value_counts())
    
    # Check for Low Salary Outliers (e.g. < 27,000 TWD which is min monthly wage)
    # Filter for valid salary rows first
    salary_rows = df[df['salary_min'].notna() & (df['salary_min'] > 0)]
    
    low_wage_threshold = 27000
    low_wage_jobs = salary_rows[salary_rows['salary_min'] < low_wage_threshold]
    
    log_print(f"Total rows with salary: {len(salary_rows)}")
    log_print(f"Rows with salary < {low_wage_threshold}: {len(low_wage_jobs)} ({len(low_wage_jobs)/len(salary_rows)*100:.2f}%)")
    
    if len(low_wage_jobs) > 0:
        log_print("SAMPLE LOW WAGE JOBS (Potential Hourly/Daily data):")
        print(low_wage_jobs[['job_title', 'salary_type', 'salary_min', 'salary_max']].head(10))
        
        # Plot Salary Distribution
        plt.figure(figsize=(10, 6))
        sns.histplot(salary_rows['salary_min'], bins=50, kde=True)
        plt.axvline(low_wage_threshold, color='r', linestyle='--', label='Min Monthly Wage (27k)')
        plt.title('Salary Min Distribution (Check for Low-End Mode)')
        plt.xlabel('Salary Min (TWD)')
        plt.savefig(os.path.join(REPORT_DIR, '01_salary_distribution_check.png'))
        plt.close()

    # ================= 3. Feature Engineering (Replicating generate_predictions.py) =================
    # Clean numeric
    df['salary_min'] = pd.to_numeric(df['salary_min'], errors='coerce')
    df['salary_max'] = pd.to_numeric(df['salary_max'], errors='coerce')
    df['tools'] = df['tools'].fillna('')
    df['job_description'] = df['description'].fillna('')
    df['job_categories'] = df['job_categories'].fillna('')

    # 1. City / Location
    def parse_city(addr):
        if pd.isna(addr): return 'Unknown'
        addr = str(addr)
        if len(addr) >= 3: return addr[:3]
        return addr
    df['city_for_stratify'] = df['location'].apply(parse_city)  # Assuming location exists from loader
    top_cities = df['city_for_stratify'].value_counts().head(10).index

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
    def parse_edu(text):
        if pd.isna(text): return 0
        text = str(text).lower()
        if any(x in text for x in ['博士', 'phd']): return 5
        if any(x in text for x in ['碩士', 'master']): return 4
        if any(x in text for x in ['大學', 'bachelor']): return 3
        if any(x in text for x in ['專科', 'associate']): return 2
        return 1
    df['edu_level'] = df['education'].apply(parse_edu)

    # 6. Experience
    def parse_exp(text):
        if pd.isna(text): return 0.0
        s = str(text).lower()
        match = re.search(r'(\d+)\s*年以上', s)
        if match: return float(match.group(1))
        return 0.0
    df['exp_years_raw'] = df['experience'].apply(parse_exp)

    # 9. TF-IDF
    def jieba_tokenizer(text):
        return jieba.lcut(text)
    texts = df['job_description'].fillna('').astype(str)
    vectorizer = TfidfVectorizer(max_features=50, tokenizer=jieba_tokenizer, token_pattern=None)
    try:
        tfidf_matrix = vectorizer.fit_transform(texts)
        for i, name in enumerate(vectorizer.get_feature_names_out()):
            clean = re.sub(r'[^\w]', '', name)
            df[f'desc_{clean}_{i}'] = tfidf_matrix[:, i].toarray().flatten()
    except Exception:
        pass

    # Scaling
    df['exp_years_scaled'] = df['exp_years_raw']
    scaler = StandardScaler()
    df[['exp_years_scaled', 'edu_level']] = scaler.fit_transform(df[['exp_years_scaled', 'edu_level']])

    # Define Features
    features = [c for c in df.columns if any(x in c for x in ['is_', 'skill_', 'desc_', 'exp_years_scaled', 'edu_level'])]
    # Remove targets
    features = [f for f in features if f not in ['salary_min', 'salary_max', 'predicted_salary_min', 'predicted_salary_max']]
    
    log_print(f"Features selected: {len(features)}")

    # ================= 4. Train & Evaluate =================
    mask_train = df['salary_min'].notna() & df['salary_min'] > 0
    df_train = df[mask_train].copy()
    
    X = df_train[features].apply(pd.to_numeric, errors='coerce').fillna(0).values
    y = np.log1p(df_train['salary_min']) # Predict Min Salary Log

    # Split for Evaluation (K-Fold)
    kf = KFold(n_splits=5, shuffle=True, random_state=42)
    
    r2_scores = []
    mae_scores = []
    
    y_preds_all = []
    y_true_all = []

    log_print("Starting Cross-Validation (5 Folds)...")
    
    # Simplified Ensemble for speed in eval (Reduced Estimators)
    rf = RandomForestRegressor(n_estimators=50, random_state=42, n_jobs=-1)
    xgb = XGBRegressor(n_estimators=50, max_depth=6, n_jobs=-1)
    ens = VotingRegressor([('rf', rf), ('xgb', xgb)])

    for fold, (train_idx, val_idx) in enumerate(kf.split(X)):
        X_tr, X_val = X[train_idx], X[val_idx]
        y_tr, y_val = y.iloc[train_idx], y.iloc[val_idx]
        
        ens.fit(X_tr, y_tr)
        pred_log = ens.predict(X_val)
        
        pred_real = np.expm1(pred_log)
        true_real = np.expm1(y_val)
        
        r2 = r2_score(true_real, pred_real)
        mae = mean_absolute_error(true_real, pred_real)
        
        r2_scores.append(r2)
        mae_scores.append(mae)
        
        y_preds_all.extend(pred_real)
        y_true_all.extend(true_real)
        
        log_print(f"Fold {fold+1}: R2={r2:.4f}, MAE={mae:.0f}")

    avg_r2 = np.mean(r2_scores)
    avg_mae = np.mean(mae_scores)
    
    log_print(f"AVERAGE PERFORMANCE: R2={avg_r2:.4f}, MAE={avg_mae:.0f}")
    
    # Generate Report Text
    with open(os.path.join(REPORT_DIR, 'evaluation_summary.txt'), 'w', encoding='utf-8') as f:
        f.write(f"Model Evaluation Summary\n")
        f.write(f"=========================\n")
        f.write(f"Total Training Samples: {len(df_train)}\n")
        f.write(f"Features Used: {len(features)}\n")
        f.write(f"Average R2: {avg_r2:.4f}\n")
        f.write(f"Average MAE: {avg_mae:.0f} TWD\n")
        if len(low_wage_jobs) > 0:
            f.write(f"\nWARNING: DATA POLLUTION DETECTED\n")
            f.write(f"Found {len(low_wage_jobs)} jobs with salary < {low_wage_threshold}.\n")
            f.write(f"This likely includes Hourly/Daily wages, distorting predictions.\n")
    
    # Plot Actual vs Predicted
    plt.figure(figsize=(10, 6))
    plt.scatter(y_true_all, y_preds_all, alpha=0.5)
    plt.plot([min(y_true_all), max(y_true_all)], [min(y_true_all), max(y_true_all)], 'r--')
    plt.xlabel('Actual Salary')
    plt.ylabel('Predicted Salary')
    plt.title(f'Actual vs Predicted (R2={avg_r2:.2f})')
    plt.savefig(os.path.join(REPORT_DIR, '02_actual_vs_predicted.png'))
    plt.close()

if __name__ == "__main__":
    evaluate_pipeline()
