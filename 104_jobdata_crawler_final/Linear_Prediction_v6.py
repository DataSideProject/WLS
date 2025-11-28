# predict_salary_v6_hybrid_fixed.py
# 新增：將所有 console print 內容收集並寫入 report

import pandas as pd
import numpy as np
import re
from sklearn.model_selection import KFold
from sklearn.metrics import r2_score
from sklearn.linear_model import LassoCV
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import VotingRegressor, RandomForestRegressor, GradientBoostingRegressor
from xgboost import XGBRegressor
from catboost import CatBoostRegressor
from sqlalchemy import create_engine
import warnings
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime

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
        min_salary = int(match.group(1)) // 12
        max_salary = int(match.group(2)) // 12 if match.group(2) else None
        note = "年薪轉換為月薪"
        return min_salary, max_salary, note
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
        df = pd.read_csv('job_data_master_raw_export.csv') 
        log_print(f"成功讀取本地 CSV：{len(df)} 筆")
        log_print("解析 CSV 薪資欄位...")
        parsed_data = df['salary'].apply(parse_salary)
        df['salary_min'] = parsed_data.apply(lambda x: x[0])
        df['salary_max'] = parsed_data.apply(lambda x: x[1])
        df['salary_note'] = parsed_data.apply(lambda x: x[2])
    except Exception as e_csv:
        log_print(f"讀取本地 CSV 失敗: {e_csv}")
        raise

# 交叉特徵
top_cities = city_counts.head(10).index
for job in top10_jobs:
    safe = job.replace('/', '_').replace(' ', '_')
    for city in top_cities:
        col = f'{safe}_in_{city}'
        df[col] = df[f'is_{safe}'] * (df['city_for_stratify'] == city).astype(int)
for skill in top_skills:
    for city in top_cities:
        col = f'skill_{skill}_in_{city}'
        df[col] = df[f'skill_{skill}'] * (df['city_for_stratify'] == city).astype(int)
df[numerical_cols] = scaler_num.fit_transform(df[numerical_cols])
df.rename(columns={'exp_years': 'exp_years_scaled', 'work_years': 'work_years_scaled'}, inplace=True)
log_print("\n=== 階段一：預測 salary_max ===")
# 標記原始完整資料的索引，用於階段二避免資料洩漏
original_complete_indices = df[df['salary_min'].notna() & df['salary_max'].notna()].index

train_max = df[df['salary_min'].notna() & df['salary_max'].notna()].copy()
predict_max = df[df['salary_min'].notna() & df['salary_max'].isna()].copy()

r2_stage1, mape_stage1 = 0, 0

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
        rf = RandomForestRegressor(n_estimators=200, random_state=42)
        gb = GradientBoostingRegressor(n_estimators=200, random_state=42)
        xgb = XGBRegressor(n_estimators=300, learning_rate=0.05, max_depth=5, random_state=42)
        cat = CatBoostRegressor(iterations=300, depth=8, learning_rate=0.05, random_seed=42, verbose=0)
        return VotingRegressor([('rf', rf), ('xgb', xgb), ('gb', gb), ('cat', cat)])

    def evaluate_log_model(model, X, y):
        kf = KFold(n_splits=5, shuffle=True, random_state=42)
        r2s, mapes = [], []
        for tr, te in kf.split(X):
            model.fit(X.iloc[tr], y.iloc[tr])
            pred = np.expm1(model.predict(X.iloc[te]))
            true = np.expm1(y.iloc[te])
            r2s.append(r2_score(true, pred))
            mapes.append(np.mean(np.abs((true - pred) / true)) * 100)
        return np.mean(r2s), np.mean(mapes)

    ensemble_max = build_ensemble()
    r2_stage1, mape_stage1 = evaluate_log_model(ensemble_max, X_train_sel, y_train)
    log_print(f"階段一 (log+CV): R²={r2_stage1:.4f}, MAPE={mape_stage1:.2f}%")

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

r2_min_full, mape_min_full = 0, 0
r2_max_full, mape_max_full = 0, 0
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

    r2_min_full, mape_min_full = evaluate_log_model(ensemble_min, X_train_sel_min, y_min_log)
    r2_max_full, mape_max_full = evaluate_log_model(ensemble_max, X_train_sel_max, y_max_log)
    log_print(f"面議預測 salary_min (log+CV): R²={r2_min_full:.4f}, MAPE={mape_min_full:.2f}%")
    log_print(f"面議預測 salary_max (log+CV): R²={r2_max_full:.4f}, MAPE={mape_max_full:.2f}%")

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
    log_print("無面議資料可預測 或 訓練資料不足")

# ====================== 6. 最終計算 ======================
df['salary_avg'] = df[['salary_min', 'salary_max']].mean(axis=1)
df.to_csv('job_data_with_full_salary_v6.csv', index=False)
log_print("預測完成！結果已存為 job_data_with_full_salary_v6.csv")

# ====================== 7. 報告 ======================
report_content = f"""
# 就業市場薪資預測報告
**生成時間**：{datetime.now().strftime('%Y-%m-%d %H:%M')}

## 模型表現
- 階段一（上限預測）：R² = {r2_stage1:.4f}, MAPE = {mape_stage1:.2f}%
- 階段二（面議預測）：
  - salary_min：R² = {r2_min_full:.4f}, MAPE = {mape_min_full:.2f}%
  - salary_max：R² = {r2_max_full:.4f}, MAPE = {mape_max_full:.2f}%

## 資料概況
- 總職缺：{len(df)}
- 真實薪資：{len(df[df['salary_min'].notna() & ~df['salary'].astype(str).str.contains('面議', na=False)])}
- 面議填補：{len(predict_none)}

## 特徵重要性分析（Top 20）
{imp_avg.round(6).to_string() if not imp_avg.empty else "N/A"}

## 執行日誌
{chr(10).join([str(x) for x in log_lines])}

## 結論
模型成功填補 {len(predict_none)} 筆面議薪資。
"""

with open('salary_prediction_report.txt', 'w', encoding='utf-8') as f:
    f.write(report_content)

log_print("報告已生成：salary_prediction_report.txt")