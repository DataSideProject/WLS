import pandas as pd
import numpy as np
import json

try:
    df = pd.read_csv(r'e:\Antigravity_HOME_PC\WLS\104_jobdata_crawler_final\job_data_final_with_predictions.csv')
    print(f"Loaded {len(df)} rows.")

    # Check for NaNs
    nans = df.isna().sum().sum()
    print(f"Total NaNs: {nans}")

    # Check for Infinite
    # Select numeric columns first
    numeric_df = df.select_dtypes(include=[np.number])
    inf_count = np.isinf(numeric_df).sum().sum()
    print(f"Total Infinite values: {inf_count}")
    
    if inf_count > 0:
        print("Infinite values found! This breaks JSON.")
        # Show which columns have inf
        for col in numeric_df.columns:
            c = np.isinf(numeric_df[col]).sum()
            if c > 0:
                print(f"{col}: {c} infs")

    # Check tools column for "--"
    if 'tools' in df.columns:
        dash_tools = df[df['tools'] == '--'].shape[0]
        print(f"Rows with tools='--': {dash_tools}")

except Exception as e:
    print(f"Error: {e}")
