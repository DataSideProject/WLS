
import pandas as pd
from sqlalchemy import create_engine
import sys

try:
    from db_config import DB_HOST, DB_USER, DB_PASSWORD, DB_NAME
except ImportError:
    DB_HOST = 'localhost'
    DB_USER = 'wilson'
    DB_PASSWORD = '' # Will fail if pass needed, but user environment might have it or we trust env
    DB_NAME = 'job_data_warehouse'

print("Connecting to DB...")
# User uses 'wilson' with password 'Wiwi0910sql' usually
connection_string = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:3306/{DB_NAME}"
if not DB_PASSWORD: # Fallback prompt or hardcode for this debug script if running on VM
    # The VM user is 'wilson' with 'Wiwi0910sql'
    connection_string = f"mysql+pymysql://wilson:Wiwi0910sql@localhost:3306/{DB_NAME}"

engine = create_engine(connection_string)

print("Fetching ALL DISTINCT salary_type from view_ml_dataset...")
df = pd.read_sql("SELECT DISTINCT salary_type FROM view_ml_dataset", engine)

print("\n--- RAW VALUES INSPECTION ---")
for idx, row in df.iterrows():
    val = row['salary_type']
    print(f"Index: {idx}")
    print(f"  Value: '{val}'")
    print(f"  Type: {type(val)}")
    print(f"  Repr: {repr(val)}")
    if isinstance(val, str):
        print(f"  Hex: {val.encode('utf-8').hex()}")
    print("-" * 20)

print("\nFetching outlier rows (> 1,000,000)...")
df_outliers = pd.read_sql("SELECT salary_type, salary_min, source FROM view_ml_dataset WHERE salary_max > 1000000 LIMIT 5;", engine)
print(df_outliers)
