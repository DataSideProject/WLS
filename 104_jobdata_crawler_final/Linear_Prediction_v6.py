# predict_salary_v6_hybrid_optimized.py
# 優化版：加入公司特徵、擴大 NLP 特徵、增強模型參數
# 新增：MAE, RMSE, 殘差圖, 預測區間

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
    # 嘗試轉換日期格式以確保排序正確 (假設有 update_date)
    if 'update_date' in df.columns:
        df['update_date'] = pd.to_datetime(df['update_date'], errors='coerce')
        df = df.sort_values(by=['job_id', 'update_date'])
    
    # 保留最後一筆 (最新的)
    df = df.drop_duplicates(subset=['job_id'], keep='last')
    log_print(f"已移除重複資料: {initial_count - len(df)} 筆 (剩餘 {len(df)} 筆)")
else:
    log_print("警告: 無法去重 (找不到 job_id 欄位)")

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
    all_tools.extend([t.strip().lower() for t in str(tools).split(',') if t.strip()])
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
df['exp_years'] = df['experience'].apply(parse_exp)

# 8. 職務類別 (job_categories)
all_cats = []
for cats in df['job_categories'].dropna():
    all_cats.extend([c.strip() for c in str(cats).split(',') if c.strip()])
top_cats = [c[0] for c in Counter(all_cats).most_common(20)]

for cat in top_cats:
    df[f'cat_{cat}'] = df['job_categories'].astype(str).str.contains(cat, regex=False, na=False).astype(int)

# 9. 公司名稱 (New)
# 注意：根據之前的 debug，欄位名稱是 'company'
top_companies = df['company'].value_counts().head(30).index
for comp in top_companies:
    safe_comp = re.sub(r'[^\w]', '', str(comp))
    if not safe_comp: safe_comp = 'unknown_company'
    df[f'company_{safe_comp}'] = (df['company'] == comp).astype(int)

# 10. 文字特徵 (TF-IDF) - Expanded to 100
def process_tfidf(col_name, prefix, max_features=100):
    texts = df[col_name].fillna('').astype(str)
    # 使用字元級 n-gram (1~3) 捕捉中英文關鍵字
    vectorizer = TfidfVectorizer(max_features=max_features, analyzer='char', ngram_range=(1, 3))
    tfidf_matrix = vectorizer.fit_transform(texts)
    feature_names = vectorizer.get_feature_names_out()
    
    new_cols = []
    for i, name in enumerate(feature_names):
        # 簡單清理欄位名
        clean_name = re.sub(r'[^\w]', '', name)
        if not clean_name: clean_name = f'feat{i}'
        col = f'{prefix}_{clean_name}'
        # 避免欄位名重複
        if col in df.columns: col = f'{col}_{i}'
        df[col] = tfidf_matrix[:, i].toarray().flatten()
        new_cols.append(col)
    return new_cols

log_print("處理 job_description TF-IDF (Top 100)...")
desc_cols = process_tfidf('job_description', 'desc', max_features=100)

log_print("處理 other_conditions TF-IDF (Top 100)...")
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
numerical_cols = ['exp_years', 'edu_level']
scaler_num = StandardScaler()
df[numerical_cols] = scaler_num.fit_transform(df[numerical_cols])
df.rename(columns={'exp_years': 'exp_years_scaled'}, inplace=True)

# 定義 feature_cols
feature_cols = []
feature_cols.extend([f'is_{job.replace("/", "_").replace(" ", "_")}' for job in top10_jobs])
feature_cols.extend([f'skill_{skill}' for skill in top_skills])
feature_cols.extend([f'industry_{ind}' for ind in top_industries])
feature_cols.append('is_manager')
feature_cols.append('exp_years_scaled')
feature_cols.append('edu_level')
feature_cols.extend([f'cat_{cat}' for cat in top_cats])
feature_cols.extend([f'company_{re.sub(r"[^\w]", "", str(comp))}' for comp in top_companies]) # Add companies
feature_cols.extend(desc_cols)
feature_cols.extend(cond_cols)

for job in top10_jobs:
    safe = job.replace('/', '_').replace(' ', '_')
    for city in top_cities:
        feature_cols.append(f'{safe}_in_{city}')
for skill in top_skills:
    for city in top_cities:
        feature_cols.append(f'skill_{skill}_in_{city}')

log_print("\n=== 階段一：預測 salary_max ===")
# 標記原始完整資料的索引，用於階段二避免資料洩漏
original_complete_indices = df[df['salary_min'].notna() & df['salary_max'].notna()].index

train_max = df[df['salary_min'].notna() & df['salary_max'].notna()].copy()
predict_max = df[df['salary_min'].notna() & df['salary_max'].isna()].copy()

r2_stage1, mape_stage1, mae_stage1, rmse_stage1 = 0, 0, 0, 0
residuals_stage1 = []

if len(train_max) > 0:
    scaler_min = StandardScaler()
    train_max['salary_min_scaled'] = scaler_min.fit_transform(train_max[['salary_min']])
    
    if len(predict_max) > 0:
        predict_max['salary_min_scaled'] = scaler_min.transform(predict_max[['salary_min']])

    X_train = train_max[feature_cols + ['salary_min_scaled']].copy()
    X_train = X_train.apply(pd.to_numeric, errors='coerce').fillna(0)
    
    y_train = np.log1p(train_max['salary_max'])

    lasso = LassoCV(cv=5, random_state=42, n_jobs=-1)
    lasso.fit(X_train, y_train)
    sel_features = X_train.columns[np.abs(lasso.coef_) > 1e-4]
    X_train_sel = X_train[sel_features]

    def build_ensemble():
        # 增強模型參數
        rf = RandomForestRegressor(n_estimators=300, random_state=42)
        gb = GradientBoostingRegressor(n_estimators=300, random_state=42)
        xgb = XGBRegressor(n_estimators=500, learning_rate=0.05, max_depth=6, random_state=42)
        cat = CatBoostRegressor(iterations=500, depth=8, learning_rate=0.05, random_seed=42, verbose=0)
        return VotingRegressor([('rf', rf), ('xgb', xgb), ('gb', gb), ('cat', cat)])

    def evaluate_log_model(model, X, y, name="Model"):
        kf = KFold(n_splits=5, shuffle=True, random_state=42)
        r2s, mapes, maes, rmses = [], [], [], []
        all_residuals = []
        
        for tr, te in kf.split(X):
            model.fit(X.iloc[tr], y.iloc[tr])
            pred = np.expm1(model.predict(X.iloc[te]))
            true = np.expm1(y.iloc[te])
            
            # Metrics
            r2s.append(r2_score(true, pred))
            mapes.append(np.mean(np.abs((true - pred) / true)) * 100)
            maes.append(mean_absolute_error(true, pred))
            rmses.append(np.sqrt(mean_squared_error(true, pred)))
            
            # Residuals for plotting
            all_residuals.extend(true - pred)
            
        return np.mean(r2s), np.mean(mapes), np.mean(maes), np.mean(rmses), all_residuals

    ensemble_max = build_ensemble()
    r2_stage1, mape_stage1, mae_stage1, rmse_stage1, residuals_stage1 = evaluate_log_model(ensemble_max, X_train_sel, y_train, "Stage1_Max")
    log_print(f"階段一 (log+CV): R²={r2_stage1:.4f}, MAPE={mape_stage1:.2f}%, MAE={mae_stage1:.0f}, RMSE={rmse_stage1:.0f}")

    if len(predict_max) > 0:
        ensemble_max.fit(X_train_sel, y_train)
        X_pred = predict_max[feature_cols + ['salary_min_scaled']].copy()
        X_pred = X_pred.apply(pd.to_numeric, errors='coerce').fillna(0)
        X_pred = X_pred[sel_features]
        pred = np.expm1(ensemble_max.predict(X_pred))
        df.loc[predict_max.index, 'salary_max'] = np.maximum(pred, predict_max['salary_min'])
else:
    log_print("無足夠資料進行階段一訓練")

# ====================== 5. 階段二：面議預測 ======================
log_print("\n=== 階段二：面議預測 ===")
# 修正：只使用原始就有 min 和 max 的資料進行訓練
train_full = df.loc[original_complete_indices].copy()
log_print(f"階段二訓練資料集大小 (Ground Truth): {len(train_full)} 筆")
predict_none = df[df['salary_min'].isna() & df['salary_max'].isna()].copy()

r2_min_full, mape_min_full, mae_min_full, rmse_min_full = 0, 0, 0, 0
r2_max_full, mape_max_full, mae_max_full, rmse_max_full = 0, 0, 0, 0
residuals_min = []
residuals_max = []
imp_avg = pd.Series()

if len(train_full) > 0 and len(predict_none) > 0:
    X_train = train_full[feature_cols].copy()
    X_train = X_train.apply(pd.to_numeric, errors='coerce').fillna(0)
    y_min_log = np.log1p(train_full['salary_min'])
    y_max_log = np.log1p(train_full['salary_max'])

    lasso_min = LassoCV(cv=5, random_state=42, n_jobs=-1)
    lasso_min.fit(X_train, y_min_log)
    sel_min = X_train.columns[np.abs(lasso_min.coef_) > 1e-4]
    X_train_sel_min = X_train[sel_min]

    lasso_max = LassoCV(cv=5, random_state=42, n_jobs=-1)
    lasso_max.fit(X_train, y_max_log)
    sel_max = X_train.columns[np.abs(lasso_max.coef_) > 1e-4]
    X_train_sel_max = X_train[sel_max]

    ensemble_min = build_ensemble()
    ensemble_max = build_ensemble()

    r2_min_full, mape_min_full, mae_min_full, rmse_min_full, residuals_min = evaluate_log_model(ensemble_min, X_train_sel_min, y_min_log, "Stage2_Min")
    r2_max_full, mape_max_full, mae_max_full, rmse_max_full, residuals_max = evaluate_log_model(ensemble_max, X_train_sel_max, y_max_log, "Stage2_Max")
    
    log_print(f"面議預測 salary_min (log+CV): R²={r2_min_full:.4f}, MAPE={mape_min_full:.2f}%, MAE={mae_min_full:.0f}, RMSE={rmse_min_full:.0f}")
    log_print(f"面議預測 salary_max (log+CV): R²={r2_max_full:.4f}, MAPE={mape_max_full:.2f}%, MAE={mae_max_full:.0f}, RMSE={rmse_max_full:.0f}")

    # 繪製殘差圖 (Persuasiveness)
    plt.figure(figsize=(15, 5))
    
    plt.subplot(1, 3, 1)
    sns.histplot(residuals_min, kde=True, color='blue')
    plt.title(f'Residuals Distribution (Min Salary)\nMean: {np.mean(residuals_min):.0f}, Std: {np.std(residuals_min):.0f}')
    plt.xlabel('Error (True - Pred)')
    
    plt.subplot(1, 3, 2)
    sns.histplot(residuals_max, kde=True, color='green')
    plt.title(f'Residuals Distribution (Max Salary)\nMean: {np.mean(residuals_max):.0f}, Std: {np.std(residuals_max):.0f}')
    plt.xlabel('Error (True - Pred)')

    plt.subplot(1, 3, 3)
    plt.scatter(range(len(residuals_min)), residuals_min, alpha=0.3, label='Min Residuals', s=10)
    plt.scatter(range(len(residuals_max)), residuals_max, alpha=0.3, label='Max Residuals', s=10, color='green')
    plt.axhline(0, color='red', linestyle='--')
    plt.title('Residuals Scatter Plot')
    plt.legend()
    
    plt.tight_layout()
    plt.savefig('model_diagnostics.png')
    log_print("殘差分析圖已儲存：model_diagnostics.png")

    # 特徵重要性
    ensemble_min.fit(X_train_sel_min, y_min_log)
    ensemble_max.fit(X_train_sel_max, y_max_log)
    
    xgb_min = ensemble_min.named_estimators_['xgb']
    xgb_max = ensemble_max.named_estimators_['xgb']

    imp_min = pd.Series(xgb_min.feature_importances_, index=sel_min).sort_values(ascending=False)
    imp_max = pd.Series(xgb_max.feature_importances_, index=sel_max).sort_values(ascending=False)
    imp_avg = (imp_min.add(imp_max, fill_value=0) / 2).sort_values(ascending=False).head(20)

    log_print("\n特徵重要性（Top 20，平均 min 和 max）：")
    log_print(imp_avg.round(6))

    # 最終預測
    X_pred = predict_none[feature_cols].copy()
    X_pred = X_pred.apply(pd.to_numeric, errors='coerce').fillna(0)
    pred_min = np.expm1(ensemble_min.predict(X_pred[sel_min]))
    pred_max = np.expm1(ensemble_max.predict(X_pred[sel_max]))

    df.loc[predict_none.index, 'salary_min'] = pred_min
    df.loc[predict_none.index, 'salary_max'] = pred_max
else:
    log_print("無足夠資料進行階段一訓練")

# ====================== 6. 最終計算 ======================
df['salary_avg'] = df[['salary_min', 'salary_max']].mean(axis=1)
df.to_csv('job_data_with_full_salary_v6.csv', index=False)
log_print("預測完成！結果已存為 job_data_with_full_salary_v6.csv")

# ====================== 7. 報告 ======================
# 計算 95% 預測區間 (Prediction Interval)
# 假設殘差常態分佈，95% 區間約為 ± 1.96 * std(residuals)
std_min = np.std(residuals_min) if residuals_min else 0
std_max = np.std(residuals_max) if residuals_max else 0
interval_min = 1.96 * std_min
interval_max = 1.96 * std_max

report_content = f"""
# 就業市場薪資預測報告 (增強版)
**生成時間**：{datetime.now().strftime('%Y-%m-%d %H:%M')}

## 模型表現 (Model Performance)
模型經過公司特徵、NLP 擴增與參數優化，並加入 MAE/RMSE 指標評估。

### 階段一（上限預測 - 已知下限求上限）
- **R² (解釋力)**: {r2_stage1:.4f} (模型解釋了 {r2_stage1*100:.1f}% 的變異)
- **MAPE (平均誤差率)**: {mape_stage1:.2f}%
- **MAE (平均誤差金額)**: {mae_stage1:.0f} 元
- **RMSE (均方根誤差)**: {rmse_stage1:.0f} 元

### 階段二（面議預測 - 全盲預測）
對於完全沒有薪資資訊的「面議」職缺：

#### Salary Min (下限)
- **R²**: {r2_min_full:.4f}
- **MAPE**: {mape_min_full:.2f}%
- **MAE**: {mae_min_full:.0f} 元
- **RMSE**: {rmse_min_full:.0f} 元
- **95% 信心預測區間**: 預測值 ± {interval_min:.0f} 元

#### Salary Max (上限)
- **R²**: {r2_max_full:.4f}
- **MAPE**: {mape_max_full:.2f}%
- **MAE**: {mae_max_full:.0f} 元
- **RMSE**: {rmse_max_full:.0f} 元
- **95% 信心預測區間**: 預測值 ± {interval_max:.0f} 元

> [!TIP]
> **如何解讀預測區間？**
> 如果模型預測某個面議職缺的起薪是 40,000 元，我們有 95% 的信心，實際起薪會落在 {40000 - interval_min:.0f} ~ {40000 + interval_min:.0f} 元之間。

## 資料概況
- 總職缺：{len(df)}
- 真實薪資：{len(df[df['salary_min'].notna() & ~df['salary'].astype(str).str.contains('面議', na=False)])}
- 面議填補：{len(predict_none)}

## 特徵重要性分析（Top 20）
{imp_avg.round(6).to_string() if not imp_avg.empty else "N/A"}

## 執行日誌
{chr(10).join([str(x) for x in log_lines])}

## 結論
模型成功填補 {len(predict_none)} 筆面議薪資。殘差分析圖 (model_diagnostics.png) 顯示誤差分佈情形。
"""

with open('salary_prediction_report.txt', 'w', encoding='utf-8') as f:
    f.write(report_content)

log_print("報告已生成：salary_prediction_report.txt")