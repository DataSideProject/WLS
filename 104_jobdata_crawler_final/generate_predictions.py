import pandas as pd
import numpy as np
import os
from sklearn.model_selection import KFold
from sklearn.ensemble import VotingRegressor, RandomForestRegressor, GradientBoostingRegressor
from xgboost import XGBRegressor
from catboost import CatBoostRegressor
from sklearn.metrics import mean_absolute_error, r2_score
import warnings

warnings.filterwarnings("ignore")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_FILE = os.path.join(BASE_DIR, 'job_data_with_full_salary_v7_segmented.csv')
OUTPUT_FILE = os.path.join(BASE_DIR, 'job_data_final_with_predictions.csv')

def load_data():
    print(f"Loading data from {INPUT_FILE}...")
    df = pd.read_csv(INPUT_FILE)
    print(f"Loaded {len(df)} rows.")
    return df

def get_feature_columns(df):
    feature_cols = []
    # Identify feature columns based on prefixes used in Linear_Prediction_v7.py
    prefixes = ['is_', 'skill_', 'industry_', 'cat_', 'company_', 'desc_', 'cond_']
    
    for col in df.columns:
        # Explicit features
        if col in ['exp_years_scaled', 'edu_level', 'is_manager']:
            feature_cols.append(col)
            continue
            
        # Pattern based features
        for prefix in prefixes:
            if col.startswith(prefix):
                feature_cols.append(col)
                break
                
    # Filter out target or non-feature columns that might match prefixes (e.g. 'is_manager' is already added)
    # Also 'salary_min', 'salary_max' etc.
    feature_cols = [c for c in feature_cols if c not in ['salary_min', 'salary_max', 'salary_avg', 'salary_note']]
    
    print(f"Identified {len(feature_cols)} feature columns.")
    return feature_cols

def build_ensemble():
    rf = RandomForestRegressor(n_estimators=200, random_state=42, n_jobs=-1)
    gb = GradientBoostingRegressor(n_estimators=200, random_state=42)
    xgb = XGBRegressor(n_estimators=300, learning_rate=0.05, max_depth=6, random_state=42, n_jobs=-1)
    cat = CatBoostRegressor(iterations=300, depth=8, learning_rate=0.05, random_seed=42, verbose=0)
    return VotingRegressor([('rf', rf), ('xgb', xgb), ('gb', gb), ('cat', cat)])

def train_and_predict(df, feature_cols):
    # Split into Train (Actual Salary) and Predict (No/Filled Salary)
    # We use 'salary_note' to distinguish. '無薪資資訊' means it was originally missing.
    # Note: The v7 CSV has filled values in salary_min/max for '無薪資資訊' rows.
    # We want to train on rows that were NOT '無薪資資訊'.
    
    # Filter out '無薪資資訊' AND ensure salary columns are not NaN
    mask_actual = (df['salary_note'] != '無薪資資訊') & (df['salary_min'].notna()) & (df['salary_max'].notna())
    df_train = df[mask_actual].copy()
    
    print(f"Training on {len(df_train)} rows with actual salary...")
    
    X = df[feature_cols].fillna(0)
    
    # We need to predict min and max
    targets = ['salary_min', 'salary_max']
    
    for target in targets:
        print(f"\n--- Processing {target} ---")
        y_train = df_train[target]
        
        # Log transform for training
        y_train_log = np.log1p(y_train)
        
        model = build_ensemble()
        model.fit(X.loc[df_train.index], y_train_log)
        
        # Predict for ALL rows
        print(f"Generating predictions for all {len(df)} rows...")
        preds_log = model.predict(X)
        preds = np.expm1(preds_log)
        
        # Save predictions
        pred_col = f'pred_{target.split("_")[1]}' # pred_min, pred_max
        df[pred_col] = preds
        
        # Calculate Error for Actual rows
        # Error = Predicted - Actual
        error_col = f'error_{target.split("_")[1]}'
        df[error_col] = np.nan # Initialize
        df.loc[mask_actual, error_col] = df.loc[mask_actual, pred_col] - df.loc[mask_actual, target]
        
        # Calculate metrics
        mae = mean_absolute_error(y_train, preds[df_train.index])
        r2 = r2_score(y_train, preds[df_train.index])
        print(f"Training Metrics for {target}: MAE={mae:.2f}, R2={r2:.4f}")

    return df

def main():
    df = load_data()
    feature_cols = get_feature_columns(df)
    
    df_result = train_and_predict(df, feature_cols)
    
    # Calculate average predicted salary for convenience
    df_result['pred_avg'] = (df_result['pred_min'] + df_result['pred_max']) / 2
    
    print(f"\nSaving results to {OUTPUT_FILE}...")
    df_result.to_csv(OUTPUT_FILE, index=False)
    print("Done.")

if __name__ == "__main__":
    main()
