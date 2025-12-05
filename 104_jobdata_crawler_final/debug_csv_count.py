import pandas as pd
import os

base_dir = r'e:\Antigravity_HOME_PC\WLS\104_jobdata_crawler_final'
file1 = os.path.join(base_dir, 'job_data_final_with_predictions.csv')
file2 = os.path.join(base_dir, 'job_data_with_full_salary_v7_segmented.csv')

print(f"Checking {file1}...")
if os.path.exists(file1):
    try:
        df1 = pd.read_csv(file1)
        print(f"File 1 Row Count: {len(df1)}")
    except Exception as e:
        print(f"File 1 Error: {e}")
else:
    print("File 1 does not exist")

print(f"Checking {file2}...")
if os.path.exists(file2):
    try:
        df2 = pd.read_csv(file2)
        print(f"File 2 Row Count: {len(df2)}")
    except Exception as e:
        print(f"File 2 Error: {e}")
else:
    print("File 2 does not exist")
