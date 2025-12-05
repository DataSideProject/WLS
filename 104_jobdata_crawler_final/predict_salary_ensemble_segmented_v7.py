"""
薪資預測腳本 v7：集成模型（Ensemble） + 年資分群（Segmented）
- 特徵篩選：LassoCV (線性)
- 主要模型：VotingRegressor (RandomForest + GB + XGBoost + CatBoost)
- 分群：Junior (<3年經驗) vs Senior (>=3年)
- 輸出：job_data_with_full_salary_v7_segmented.csv (填充待遇面議薪資)
- 注意：此腳本僅用於初步填充，最終預測請用 generate_predictions.py
"""

# predict_salary_v7_hybrid_optimized.py
# 優化版：加入公司特徵、擴大 NLP 特徵、增強模型參數
# 新增：MAE, RMSE, 殘差圖, 預測區間
# V7新增：資料淨化 (Outlier Removal) & 分群訓練 (Segmentation)
# V8新增：NLP 可解釋性優化 (jieba 分詞)

import pandas as pd
import numpy as np
import re
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

# ====================== 0. 輔助函式 ======================
def parse_salary(salary):
    """解析薪資，提取 min、max 和 note (不計算 avg)"""
    if not salary or salary == "待遇面議":
        return None, None, "無薪資資訊"
    salary = str(salary).replace(",", "")
    match = re.match(r"月薪(\d+)(?:~(\d+))?元", salary)
    if match:
        min_salary = int(match.group(1))
        max_salary = int(match.group(2)) if match.group(2) else None
        note = "最低保證薪資" if not max_salary else ""
        return min_salary, max_salary, note
    match = re.match(r"年薪(\d+)(?:~(\d+))?元", salary)
    if match:
        min_salary = int(match.group(1)) // 13
        max_salary = int(match.group(2)) // 13 if match.group(2) else None
        note = "年薪轉換為月薪"
        return min_salary, max_salary, note
    else:
        return None, None, "其他格式"

def parse_education(edu):
    """解析學歷為數值等級"""
    if pd.isna(edu): return 0
    edu = str(edu)
    if '博士' in edu: return 5
    if '碩士' in edu: return 4
    if '大學' in edu: return 3
    if '專科' in edu: return 2
    if '高中' in edu: return 1
    return 0

def parse_management(mgmt):
    """解析管理責任 (0/1)"""
    if pd.isna(mgmt): return 0
    if '不需負擔管理責任' in str(mgmt): return 0
    return 1

# ====================== 1. 載入資料 ======================
log_print("載入資料...")

# GCP MariaDB 設定
HOST = '34.81.186.201'
USER = 'datauser'
PASSWORD = '123456'
DATABASE = 'rawdata'

try:
    engine = create_engine(f'mysql+mysqlconnector://{USER}:{PASSWORD}@{HOST}:3306/{DATABASE}')
    log_print(f"連線至資料庫: {HOST}...")
    df = pd.read_sql('SELECT * FROM 104rawdata', engine)
    log_print(f"成功從資料庫讀取資料：{len(df)} 筆")
    
    # 應用 parse_salary
    log_print("解析薪資欄位...")
    parsed_data = df['salary'].apply(parse_salary)
    df['salary_min'] = parsed_data.apply(lambda x: x[0])
    df['salary_max'] = parsed_data.apply(lambda x: x[1])
    df['salary_note'] = parsed_data.apply(lambda x: x[2])
    
except Exception as e:
    log_print(f"資料庫連線失敗: {e}")
    log_print("嘗試讀取本地備份 CSV...")
    try:
        df = pd.read_csv(r'E:\Antigravity_HOME_PC\WLS\job_data_master_raw.csv') 
        log_print(f"成功讀取本地 CSV：{len(df)} 筆")
        log_print("解析 CSV 薪資欄位...")
        parsed_data = df['salary'].apply(parse_salary)
        df['salary_min'] = parsed_data.apply(lambda x: x[0])
        df['salary_max'] = parsed_data.apply(lambda x: x[1])
        df['salary_note'] = parsed_data.apply(lambda x: x[2])
    except Exception as e_csv:
        log_print(f"讀取本地 CSV 失敗: {e_csv}")
        raise

# ====================== 1.5 資料去重 ======================
if 'job_id' in df.columns:
    initial_count = len(df)
    if 'update_date' in df.columns:
        df['update_date'] = pd.to_datetime(df['update_date'], errors='coerce')
        df = df.sort_values(by=['job_id', 'update_date'])
    
    df = df.drop_duplicates(subset=['job_id'], keep='last')
    log_print(f"已移除重複資料: {initial_count - len(df)} 筆 (剩餘 {len(df)} 筆)")
else:
    log_print("警告: 無法去重 (找不到 job_id 欄位)")

# ====================== 1.6 資料淨化 (Outlier Removal) ======================
log_print("執行資料淨化 (剔除極端值)...")
mask_has_salary = df['salary_min'].notna() & df['salary_max'].notna()
df_salary = df[mask_has_salary]
df_no_salary = df[~mask_has_salary]

q01_min = df_salary['salary_min'].quantile(0.01)
q99_min = df_salary['salary_min'].quantile(0.99)
q01_max = df_salary['salary_max'].quantile(0.01)
q99_max = df_salary['salary_max'].quantile(0.99)

log_print(f"薪資範圍過濾: Min({q01_min:.0f}~{q99_min:.0f}), Max({q01_max:.0f}~{q99_max:.0f})")

df_salary_clean = df_salary[
    (df_salary['salary_min'] >= q01_min) & (df_salary['salary_min'] <= q99_min) &
    (df_salary['salary_max'] >= q01_max) & (df_salary['salary_max'] <= q99_max)
]

log_print(f"已剔除極端值: {len(df_salary) - len(df_salary_clean)} 筆")
df = pd.concat([df_salary_clean, df_no_salary], ignore_index=True)
log_print(f"淨化後總筆數: {len(df)}")

# ====================== 2. 特徵工程 ======================
log_print("進行特徵工程...")

# 1. 地區處理
def parse_city(addr):
    if pd.isna(addr): return 'Unknown'
    addr = str(addr)
    if len(addr) >= 3: return addr[:3]
    return addr

df['city_for_stratify'] = df['location'].apply(parse_city)
city_counts = df['city_for_stratify'].value_counts()
top_cities = city_counts.head(10).index

# 2. 職缺名稱
top10_jobs = df['job_title'].value_counts().head(10).index.tolist()
for job in top10_jobs:
    safe = job.replace('/', '_').replace(' ', '_')
    df[f'is_{safe}'] = (df['job_title'] == job).astype(int)

# 3. 技能
all_tools = []
for tools in df['tools'].dropna():
    # 過濾掉 '--', '不拘' 等無效值
    all_tools.extend([t.strip().lower() for t in str(tools).split(',') if t.strip() and t.strip() not in ['--', '不拘']])
top_skills = [t[0] for t in Counter(all_tools).most_common(20)]

for skill in top_skills:
    df[f'skill_{skill}'] = df['tools'].astype(str).str.contains(skill, case=False, na=False).astype(int)

# 4. 學歷
df['edu_level'] = df['education'].apply(parse_education)

# 5. 管理責任
df['is_manager'] = df['management_responsibility'].apply(parse_management)

# 6. 產業
top_industries = df['industry'].value_counts().head(10).index
for ind in top_industries:
    df[f'industry_{ind}'] = (df['industry'] == ind).astype(int)
# 7. 經驗
def parse_exp(exp):
    if pd.isna(exp): return 0
    exp = str(exp)
    match = re.search(r'(\d+)', exp)
    if match: return int(match.group(1))
    return 0
df['exp_years_raw'] = df['experience'].apply(parse_exp)

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

# 10. 文字特徵 (TF-IDF with jieba)
def jieba_tokenizer(text):
    return jieba.lcut(text)

def process_tfidf(col_name, prefix, max_features=100):
    texts = df[col_name].fillna('').astype(str)
    # 使用 jieba 分詞，並過濾過短的詞
    vectorizer = TfidfVectorizer(
        max_features=max_features, 
        tokenizer=jieba_tokenizer,
        token_pattern=None, # 使用自定義 tokenizer 時需設為 None
        ngram_range=(1, 2) # 考慮單詞和雙詞組合
    )
    tfidf_matrix = vectorizer.fit_transform(texts)
    feature_names = vectorizer.get_feature_names_out()
    
    new_cols = []
    for i, name in enumerate(feature_names):
        # 保留原始詞彙以便辨識
        clean_name = re.sub(r'[^\w]', '', name)
        if not clean_name: clean_name = f'feat{i}'
        
        # 為了避免欄位名稱衝突或非法字元，還是要做一點處理，但盡量保留原意
        # 例如: "C++" -> "C" (re.sub 會拿掉 ++)，這點要注意
        # 這裡我們用一個簡單的 mapping 技巧：
        # 欄位名用 safe string，但我們另外存一個 mapping dict 供報告使用
        
        col = f'{prefix}_{clean_name}'
        if col in df.columns: col = f'{col}_{i}'
        
        df[col] = tfidf_matrix[:, i].toarray().flatten()
        new_cols.append(col)
        
        # 記錄 mapping (全域變數 feature_map)
        feature_map[col] = name
        
    return new_cols

feature_map = {} # 用來存儲 欄位名 -> 原始關鍵字 的對照表

log_print("處理 job_description TF-IDF (Top 100, jieba)...")
desc_cols = process_tfidf('job_description', 'desc', max_features=100)

log_print("處理 other_conditions TF-IDF (Top 100, jieba)...")
cond_cols = process_tfidf('other_conditions', 'cond', max_features=100)

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
feature_cols.extend([f'industry_{ind}' for ind in top_industries])
feature_cols.append('is_manager')
feature_cols.append('exp_years_scaled')
feature_cols.append('edu_level')
feature_cols.extend([f'cat_{cat}' for cat in top_cats])
feature_cols.extend([f'company_{re.sub(r"[^\w]", "", str(comp))}' for comp in top_companies])
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
    cat = CatBoostRegressor(iterations=500, depth=8, learning_rate=0.05, random_seed=42, verbose=0)
    return VotingRegressor([('rf', rf), ('xgb', xgb), ('gb', gb), ('cat', cat)])

def train_segment_model(df_train, df_predict, target_col, segment_name):
    if len(df_train) < 10:
        log_print(f"  [{segment_name}] 訓練資料不足 ({len(df_train)} 筆)，跳過")
        return None, None, [], []

    X_train = df_train[feature_cols].copy()
    X_train = X_train.apply(pd.to_numeric, errors='coerce').fillna(0)
    y_train_log = np.log1p(df_train[target_col])

    lasso = LassoCV(cv=5, random_state=42, n_jobs=-1)
    lasso.fit(X_train, y_train_log)
    sel_features = X_train.columns[np.abs(lasso.coef_) > 1e-4]
    X_train_sel = X_train[sel_features]
    
    log_print(f"  [{segment_name}] 特徵篩選: {len(feature_cols)} -> {len(sel_features)}")

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
        predictions = np.expm1(ensemble.predict(X_pred[sel_features]))

    xgb = ensemble.named_estimators_['xgb']
    imp = pd.Series(xgb.feature_importances_, index=sel_features).sort_values(ascending=False)
    
    return metrics, predictions, residuals, imp

# ====================== 3. 執行分群訓練 (Segmentation) ======================
log_print("\n=== 開始分群訓練 (Junior vs Senior) ===")

original_complete_indices = df[df['salary_min'].notna() & df['salary_max'].notna()].index
train_full = df.loc[original_complete_indices].copy()
predict_none = df[df['salary_min'].isna() & df['salary_max'].isna()].copy()

def get_segment_mask(dframe, segment):
    if segment == 'Junior':
        return dframe['exp_years_raw'] < 3
    else:
        return dframe['exp_years_raw'] >= 3

segments = ['Junior', 'Senior']
targets = ['salary_min', 'salary_max']

results = {}
all_residuals_min = []
all_residuals_max = []
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
            if target == 'salary_min':
                all_residuals_min.extend(resids)
            else:
                all_residuals_max.extend(resids)
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

avg_mae_min = weighted_mae_min / total_samples
avg_mae_max = weighted_mae_max / total_samples

plt.figure(figsize=(15, 5))
plt.subplot(1, 2, 1)
sns.histplot(all_residuals_min, kde=True, color='blue')
plt.title(f'Overall Residuals (Min)\nMAE: {avg_mae_min:.0f}')

plt.subplot(1, 2, 2)
sns.histplot(all_residuals_max, kde=True, color='green')
plt.title(f'Overall Residuals (Max)\nMAE: {avg_mae_max:.0f}')

plt.tight_layout()
plt.savefig('model_diagnostics_segmented.png')

# 彙整特徵重要性 (並還原 NLP 關鍵字)
avg_imp = pd.concat(feature_imps).groupby(level=0).mean().sort_values(ascending=False).head(20)
# 替換 index 名稱為原始關鍵字 (如果有的話)
new_index = [f"{i} ({feature_map.get(i, '')})" if i in feature_map else i for i in avg_imp.index]
avg_imp.index = new_index

report_content = f"""
# 就業市場薪資預測報告 (分群優化版 + NLP 可解釋性)
**生成時間**：{datetime.now().strftime('%Y-%m-%d %H:%M')}
**優化策略**：資料淨化 + 年資分群 + jieba 分詞

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

## 結論
透過分群訓練與 jieba 分詞，我們現在能更清楚看到哪些具體技能或描述影響薪資。
"""

with open('salary_prediction_report.txt', 'w', encoding='utf-8') as f:
    f.write(report_content)

df['salary_avg'] = df[['salary_min', 'salary_max']].mean(axis=1)
df.to_csv('job_data_with_full_salary_v7_segmented.csv', index=False)
log_print("預測完成！結果已存為 job_data_with_full_salary_v7_segmented.csv")
log_print("報告已生成：salary_prediction_report.txt")