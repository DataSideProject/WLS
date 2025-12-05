import pandas as pd

# Load data
df = pd.read_csv(r'e:\Antigravity_HOME_PC\WLS\104_jobdata_crawler_final\job_data_with_full_salary_v7_segmented.csv')

print("\n=== Category Columns ===")
cat_cols = [c for c in df.columns if 'cat_' in c]
print(cat_cols)

print("\n=== Sample Category Data ===")
for col in cat_cols:
    print(f"{col}: {df[col].sum()} ones")

print("\n=== City Values ===")
if 'city_for_stratify' in df.columns:
    print(df['city_for_stratify'].unique())
else:
    print("Column 'city_for_stratify' not found!")
