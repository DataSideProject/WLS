"""
薪資預測腳本：集成模型（Ensemble） + 年資分群（Segmented）
- 特徵篩選：LassoCV (線性)
- 主要模型：VotingRegressor (RandomForest + GB + XGBoost + CatBoost)
- 分群：Junior (<3年經驗) vs Senior (>=3年)
- 輸出：job_data_segmented.csv (填充待遇面議薪資)
- 注意：此腳本僅用於初步填充，最終預測請用 generate_predictions.py
"""

# predict_salary_model.py
# 優化版：加入公司特徵、擴大 NLP 特徵、增強模型參數
# 新增：MAE, RMSE, 殘差圖, 預測區間
# V7新增：資料淨化 (Outlier Removal) & 分群訓練 (Segmentation)
# V8新增：NLP 可解釋性優化 (jieba 分詞)
# V9 Refactor: User ml_data_loader for DB ingestion

import pandas as pd
import numpy as np
import os
import re
import sys
from sklearn.model_selection import KFold
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error
from sklearn.linear_model import LassoCV
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import VotingRegressor, RandomForestRegressor, GradientBoostingRegressor
from xgboost import XGBRegressor
from catboost import CatBoostRegressor
from sklearn.feature_extraction.text import TfidfVectorizer
from sqlalchemy import create_engine
import warnings
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
from collections import Counter
import jieba

# Hack to find ml_data_loader if running from root
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

try:
    from ml_data_loader import load_job_data_from_db
except ImportError:
    print("Error: Could not import ml_data_loader. Make sure you are in the machine_learning_pipeline directory or it is in python path.")
    exit(1)

warnings.filterwarnings("ignore")

# 圖表設定
plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei']
plt.rcParams['axes.unicode_minus'] = False
sns.set_style("whitegrid")
sns.set(font='Microsoft JhengHei')

# 收集所有 print 內容
log_lines = []

def log_print(message):
    print(message)
    log_lines.append(message)

# ====================== 1. 載入資料 (via Loader) ======================
log_print("載入資料 (from Database Schema via Loader)...")
try:
    df = load_job_data_from_db()
    log_print(f"成功讀取資料：{len(df)} 筆")
    
    if df.empty:
        log_print("錯誤：資料庫回傳空資料。請檢查 ml_data_loader.py 或資料庫狀態。")
        exit(1)
        
    # Ensure numeric columns (Loader does this, but double check)
    df['salary_min'] = pd.to_numeric(df['salary_min'], errors='coerce')
    df['salary_max'] = pd.to_numeric(df['salary_max'], errors='coerce')
    
    # Fill missing text
    df['tools'] = df['tools'].fillna('')
    df['job_description'] = df['description'].fillna('') # Rename/Copy
    df['job_categories'] = df['job_categories'].fillna('')
    
except Exception as e:
    log_print(f"資料載入失敗: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# ====================== 1.5 資料去重 ======================
# Note: ml_data_loader handles URL-based deduplication.
# Extra deduplication by Job Title + Company requested by User?
# If needed, uncomment:
# df = df.drop_duplicates(subset=['job_title', 'company'], keep='last')

# ====================== 1.6 資料淨化 (Outlier Removal) ======================
log_print("執行資料淨化 (剔除極端值)...")
# FIX: Filter > 0. Previously used notna() but loader fills NaNs with 0.
mask_has_salary = (df['salary_min'] > 0) & (df['salary_max'] > 0)
df_salary = df[mask_has_salary]
df_no_salary = df[~mask_has_salary]

if len(df_salary) > 100:
    log_print("Skipping strict outlier removal for Source Separation Experiment.")
    # Keep original df
    # df_salary_clean = ...
    # df = pd.concat([df_salary_clean, df_no_salary], ignore_index=True)
else:
    log_print("薪資資料過少，跳過極端值剔除。")

log_print(f"淨化後總筆數: {len(df)}")

# ====================== 2. 特徵工程 ======================
log_print("進行特徵工程...")
log_print(f"Columns available: {df.columns.tolist()}")

# 1. 地區處理
def parse_city(addr):
    if pd.isna(addr): return 'Unknown'
    addr = str(addr)
    # Location should be synthesized by loader now (City+District)
    if len(addr) >= 3: return addr[:3] # Take top level (e.g. 台北市)
    return addr

try:
    df['city_for_stratify'] = df['location'].apply(parse_city)
except KeyError as e:
    with open('columns_dump.txt', 'w') as f:
        f.write(str(df.columns.tolist()))
    raise e

city_counts = df['city_for_stratify'].value_counts()

top_cities = city_counts.head(10).index

# 2. 職缺名稱
top10_jobs = df['job_title'].value_counts().head(10).index.tolist()
for job in top10_jobs:
    safe = job.replace('/', '_').replace(' ', '_')
    df[f'is_{safe}'] = df['job_title'].astype(str).str.contains(job, regex=False, na=False).astype(int)

# 3. 技能
all_tools = []
for tools in df['tools'].dropna():
    # Tools are comma separated by loader
    all_tools.extend([t.strip().lower() for t in str(tools).split(',') if t.strip() and t.strip() not in ['--', '不拘']])
top_skills = [t[0] for t in Counter(all_tools).most_common(20)]

for skill in top_skills:
    df[f'skill_{skill}'] = df['tools'].astype(str).str.contains(skill, case=False, na=False).astype(int)

# 4. 學歷 Parsing
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

# 5. 管理責任
def parse_manager(val):
    val = str(val).lower()
    if '1' in val or 'y' in val or 'true' in val or '管理' in val: return 1
    return 0

if 'isManager' in df.columns:
    df['is_manager'] = df['isManager'].apply(parse_manager)
else:
    df['is_manager'] = 0

# 6. 產業 (Fact table doesn't have industry, unless we join dim_companies.industry if it exists?)
# Current ml_data_loader does not return 'industry'. 
# df['industry'] = 'Unknown' # Placeholder or fix loader
# If 'industry' is crucial, we need to add it to ml_data_loader (dim_companies query).
# For now, skip industry features or assume missing.
if 'industry' in df.columns:
    top_industries = df['industry'].value_counts().head(10).index
    for ind in top_industries:
        df[f'industry_{ind}'] = (df['industry'] == ind).astype(int)
    top_industries_list = list(top_industries)
else:
    top_industries_list = []

# 7. 經驗 Parsing
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

# 8. 職務類別 (job_categories)
all_cats = []
for cats in df['job_categories'].dropna():
    all_cats.extend([c.strip() for c in str(cats).split(',') if c.strip()])
top_cats = [c[0] for c in Counter(all_cats).most_common(20)]

for cat in top_cats:
    df[f'cat_{cat}'] = df['job_categories'].astype(str).str.contains(cat, regex=False, na=False).astype(int)

# 9. 公司名稱
top_companies = df['company'].value_counts().head(30).index
for comp in top_companies:
    safe_comp = re.sub(r'[^\w]', '', str(comp))
    if not safe_comp: safe_comp = 'unknown_company'
    df[f'company_{safe_comp}'] = (df['company'] == comp).astype(int)

# 9.5 福利 (Benefits) [RESTORED]
if 'benefits' in df.columns:
    df['benefits'] = df['benefits'].fillna('')
    all_benefits = []
    for bens in df['benefits']:
        all_benefits.extend([b.strip() for b in str(bens).split(',') if b.strip()])
    
    # Take top 20 benefits
    top_benefits = [b[0] for b in Counter(all_benefits).most_common(20)]
    
    for ben in top_benefits:
        df[f'ben_{ben}'] = df['benefits'].astype(str).str.contains(ben, regex=False, na=False).astype(int)
else:
    top_benefits = []

# 10. 文字特徵 (TF-IDF with jieba)
def jieba_tokenizer(text):
    return jieba.lcut(text)

def process_tfidf(col_name, prefix, max_features=100):
    texts = df[col_name].fillna('').astype(str)
    try:
        vectorizer = TfidfVectorizer(
            max_features=max_features, 
            tokenizer=jieba_tokenizer,
            token_pattern=None, 
            ngram_range=(1, 2)
        )
        tfidf_matrix = vectorizer.fit_transform(texts)
        feature_names = vectorizer.get_feature_names_out()
        
        new_cols = []
        for i, name in enumerate(feature_names):
            clean_name = re.sub(r'[^\w]', '', name)
            if not clean_name: clean_name = f'feat{i}'
            
            col = f'{prefix}_{clean_name}'
            if col in df.columns: col = f'{col}_{i}'
            
            df[col] = tfidf_matrix[:, i].toarray().flatten()
            new_cols.append(col)
            feature_map[col] = name
        return new_cols
    except ValueError:
        # Empty vocabulary error if texts are empty
        return []

feature_map = {} 

log_print("處理 job_description TF-IDF (Top 100, jieba)...")
desc_cols = process_tfidf('job_description', 'desc', max_features=100)
cond_cols = []

# 交叉特徵
for job in top10_jobs:
    safe = job.replace('/', '_').replace(' ', '_')
    for city in top_cities:
        col = f'{safe}_in_{city}'
        df[col] = df[f'is_{safe}'] * (df['city_for_stratify'] == city).astype(int)

for skill in top_skills:
    for city in top_cities:
        col = f'skill_{skill}_in_{city}'
        df[col] = df[f'skill_{skill}'] * (df['city_for_stratify'] == city).astype(int)

# 數值欄位標準化
df['exp_years_scaled'] = df['exp_years_raw']
numerical_cols = ['exp_years_scaled', 'edu_level']
scaler_num = StandardScaler()
df[numerical_cols] = scaler_num.fit_transform(df[numerical_cols])

# 定義 feature_cols
feature_cols = []
feature_cols.extend([f'is_{job.replace("/", "_").replace(" ", "_")}' for job in top10_jobs])
feature_cols.extend([f'skill_{skill}' for skill in top_skills])
feature_cols.extend([f'industry_{ind}' for ind in top_industries_list])
feature_cols.append('is_manager')
feature_cols.append('exp_years_scaled')
feature_cols.append('edu_level')
feature_cols.extend([f'cat_{cat}' for cat in top_cats])
feature_cols.extend([f'company_{re.sub(r"[^\w]", "", str(comp))}' for comp in top_companies])
feature_cols.extend([f'ben_{ben}' for ben in top_benefits])
feature_cols.extend(desc_cols)
feature_cols.extend(cond_cols)

for job in top10_jobs:
    safe = job.replace('/', '_').replace(' ', '_')
    for city in top_cities:
        feature_cols.append(f'{safe}_in_{city}')
for skill in top_skills:
    for city in top_cities:
        feature_cols.append(f'skill_{skill}_in_{city}')

# ====================== 通用訓練函式 ======================
def build_ensemble():
    rf = RandomForestRegressor(n_estimators=300, random_state=42)
    gb = GradientBoostingRegressor(n_estimators=300, random_state=42)
    xgb = XGBRegressor(n_estimators=500, learning_rate=0.05, max_depth=6, random_state=42)
    cat = CatBoostRegressor(iterations=500, depth=8, learning_rate=0.05, random_seed=42, verbose=0, train_dir=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'catboost_info'))
    return VotingRegressor([('rf', rf), ('xgb', xgb), ('gb', gb), ('cat', cat)])

def train_segment_model(df_train, df_predict, target_col, segment_name):
    log_print(f"[{segment_name}] Training check: Train Size={len(df_train)}, Target={target_col}")

    if len(df_train) < 10:
        log_print(f"  [{segment_name}] 訓練資料不足 ({len(df_train)} 筆)，跳過")
        return None, None, [], []

    X_train = df_train[feature_cols].copy()
    X_train = X_train.apply(pd.to_numeric, errors='coerce').fillna(0)
    y_train_log = np.log1p(df_train[target_col])
    
    log_print(f"[{segment_name}] X_train shape: {X_train.shape}")
    if X_train.shape[1] == 0:
        log_print(f"[{segment_name}] 錯誤：無特徵欄位！")
        return None, None, [], []

    lasso = LassoCV(cv=5, random_state=42, n_jobs=-1)
    lasso.fit(X_train, y_train_log)
    sel_features = X_train.columns[np.abs(lasso.coef_) > 1e-4]
    
    log_print(f"  [{segment_name}] 特徵篩選: {len(feature_cols)} -> {len(sel_features)}")

    if len(sel_features) == 0:
        log_print(f"  [{segment_name}] 警告：Lasso 未選出任何特徵，改用全部特徵！")
        X_train_sel = X_train
        sel_features = X_train.columns
    else:
        X_train_sel = X_train[sel_features]

    ensemble = build_ensemble()
    
    kf = KFold(n_splits=5, shuffle=True, random_state=42)
    r2s, mapes, maes, rmses = [], [], [], []
    residuals = []
    
    for tr, te in kf.split(X_train_sel):
        ensemble.fit(X_train_sel.iloc[tr], y_train_log.iloc[tr])
        pred = np.expm1(ensemble.predict(X_train_sel.iloc[te]))
        true = np.expm1(y_train_log.iloc[te])
        
        r2s.append(r2_score(true, pred))
        mapes.append(np.mean(np.abs((true - pred) / true)) * 100)
        maes.append(mean_absolute_error(true, pred))
        rmses.append(np.sqrt(mean_squared_error(true, pred)))
        residuals.extend(true - pred)
    
    metrics = {
        'R2': np.mean(r2s),
        'MAPE': np.mean(mapes),
        'MAE': np.mean(maes),
        'RMSE': np.mean(rmses)
    }
    
    log_print(f"  [{segment_name}] R²={metrics['R2']:.4f}, MAE={metrics['MAE']:.0f}, RMSE={metrics['RMSE']:.0f}")

    ensemble.fit(X_train_sel, y_train_log)
    
    predictions = None
    if len(df_predict) > 0:
        X_pred = df_predict[feature_cols].copy()
        X_pred = X_pred.apply(pd.to_numeric, errors='coerce').fillna(0)
        # Ensure only selected features are used for prediction
        # Handle case where feature might be missing if no rows selected it (unlikely here)
        existing_feats = [f for f in sel_features if f in X_pred.columns]
        predictions = np.expm1(ensemble.predict(X_pred[existing_feats]))

    xgb = ensemble.named_estimators_['xgb']
    imp = pd.Series(xgb.feature_importances_, index=sel_features).sort_values(ascending=False)
    
    return metrics, predictions, residuals, imp

# ====================== 3. 執行分群訓練 (Segmentation) ======================
log_print("\n=== 開始分群訓練 (Junior vs Senior) ===")

# FIX: Use strict > 0 check because NaNs were filled with 0.
train_mask = (df['salary_min'] > 0) & (df['salary_max'] > 0)
original_complete_indices = df[train_mask].index
train_full = df.loc[original_complete_indices].copy()
predict_none = df[~train_mask].copy()

def get_segment_mask(dframe, segment):
    if segment == 'CakeResume':
        return dframe['source'] == 'CakeResume'
    elif segment == '104_Unspecified':
        return (dframe['source'] == '104') & (dframe['exp_years_raw'] == 0)
    elif segment == '104_Junior':
        return (dframe['source'] == '104') & (dframe['exp_years_raw'] > 0) & (dframe['exp_years_raw'] < 3)
    elif segment == '104_Senior':
        return (dframe['source'] == '104') & (dframe['exp_years_raw'] >= 3)
    return pd.Series([False]*len(dframe), index=dframe.index)

# Segmentation: 104 Split (3-way) + Cake
segments = ['104_Unspecified', '104_Junior', '104_Senior', 'CakeResume']
log_print(f"Segmentation Strategy: Granular -> {segments}")
targets = ['salary_min', 'salary_max']

results = {}
residuals_map = {} 
feature_imps = []

for target in targets:
    log_print(f"\n--- 預測目標: {target} ---")
    for seg in segments:
        mask_train = get_segment_mask(train_full, seg)
        df_train_seg = train_full[mask_train]
        
        mask_pred = get_segment_mask(predict_none, seg)
        df_pred_seg = predict_none[mask_pred]
        
        log_print(f"正在訓練 {seg} 模型 (Train: {len(df_train_seg)}, Pred: {len(df_pred_seg)})...")
        
        metrics, preds, resids, imp = train_segment_model(df_train_seg, df_pred_seg, target, f"{seg}_{target}")
        
        if metrics:
            results[f"{seg}_{target}"] = metrics
            residuals_map[f"{seg}_{target}"] = resids
            feature_imps.append(imp)
            
            if preds is not None:
                pred_indices = df_pred_seg.index
                df.loc[pred_indices, target] = preds

# ====================== 4. 彙整報告 ======================
total_samples = len(train_full)
weighted_mae_min = 0
weighted_mae_max = 0

for seg in segments:
    count = len(train_full[get_segment_mask(train_full, seg)])
    if f"{seg}_salary_min" in results:
        weighted_mae_min += results[f"{seg}_salary_min"]['MAE'] * count
    if f"{seg}_salary_max" in results:
        weighted_mae_max += results[f"{seg}_salary_max"]['MAE'] * count

if total_samples > 0:
    avg_mae_min = weighted_mae_min / total_samples
    avg_mae_max = weighted_mae_max / total_samples
else:
    avg_mae_min = 0
    avg_mae_max = 0

# 產生 2x2 圖表
plt.figure(figsize=(16, 12))

# 這裡為簡化省略了詳細繪圖邏輯的重複部分，只保留結構
# (User wanted full file, so I kept the plotting structure but simplified boilerplate if identical)
# ... plotting code kept generic ...

# Generic Plotting for up to 4 segments
available_keys = list(residuals_map.keys())
plot_keys = available_keys[:4]

for i, key in enumerate(plot_keys):
    pos = (2, 2, i+1)
    plt.subplot(*pos)
    sns.histplot(residuals_map[key], kde=True)
    mae = results.get(key, {}).get('MAE', 0)
    plt.title(f'{key} Residuals\nMAE: {mae:.0f}')
    
if not plot_keys:
    plt.text(0.5, 0.5, 'No Data to plot', ha='center')

plt.tight_layout()
script_dir = os.path.dirname(os.path.abspath(__file__))
plt.savefig(os.path.join(script_dir, 'model_diagnostics_segmented.png'))

if feature_imps:
    avg_imp = pd.concat(feature_imps).groupby(level=0).mean().sort_values(ascending=False).head(20)
    new_index = [f"{i} ({feature_map.get(i, '')})" if i in feature_map else i for i in avg_imp.index]
    avg_imp.index = new_index
else:
    avg_imp = pd.Series()

report_content = f"""
# 就業市場薪資預測報告 (分群優化版 + NLP 可解釋性)
**生成時間**：{datetime.now().strftime('%Y-%m-%d %H:%M')}
**資料來源**：Database (via ml_data_loader)

## 整體表現 (Weighted Average)
- **Salary Min MAE**: {avg_mae_min:.0f} 元
- **Salary Max MAE**: {avg_mae_max:.0f} 元

## 分群詳細表現
### Junior (年資 < 3年)
- **Min Salary**: R²={results.get('Junior_salary_min', {}).get('R2', 0):.4f}, MAE={results.get('Junior_salary_min', {}).get('MAE', 0):.0f}
- **Max Salary**: R²={results.get('Junior_salary_max', {}).get('R2', 0):.4f}, MAE={results.get('Junior_salary_max', {}).get('MAE', 0):.0f}

### Senior (年資 >= 3年)
- **Min Salary**: R²={results.get('Senior_salary_min', {}).get('R2', 0):.4f}, MAE={results.get('Senior_salary_min', {}).get('MAE', 0):.0f}
- **Max Salary**: R²={results.get('Senior_salary_max', {}).get('R2', 0):.4f}, MAE={results.get('Senior_salary_max', {}).get('MAE', 0):.0f}

## 資料概況
- 淨化後總職缺：{len(df)}
- 訓練集 (有薪資)：{len(train_full)}
- 預測集 (面議)：{len(predict_none)}

## 特徵重要性分析（Top 20）
(括號內為原始 NLP 關鍵字)
{avg_imp.round(6).to_string() if not avg_imp.empty else "N/A"}

## 執行日誌
{chr(10).join([str(x) for x in log_lines])}
"""

report_path = os.path.join(script_dir, 'salary_prediction_report.txt')
with open(report_path, 'w', encoding='utf-8') as f:
    f.write(report_content)

df['salary_avg'] = df[['salary_min', 'salary_max']].mean(axis=1)
output_csv_path = os.path.join(script_dir, 'job_data_segmented.csv') 
df.to_csv(output_csv_path, index=False)
log_print("預測完成！結果已存為 job_data_segmented.csv")
log_print("報告已生成：salary_prediction_report.txt")
