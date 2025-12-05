import pandas as pd
import numpy as np
import re
import os

FINAL_CSV = 'job_data_final_with_predictions.csv'
RAW_CSV = r'E:\Antigravity_HOME_PC\WLS\job_data_master_raw.csv'

def parse_salary(salary):
    """解析薪資，提取 min、max 和 note"""
    if pd.isna(salary):
        return None, None, "無薪資資訊"
        
    salary = str(salary).strip()
    if not salary or salary == "待遇面議":
        return None, None, "無薪資資訊"
        
    salary = salary.replace(",", "")
    
    # Monthly salary
    match = re.match(r"月薪(\d+)(?:~(\d+))?元", salary)
    if match:
        min_salary = int(match.group(1))
        max_salary = int(match.group(2)) if match.group(2) else None
        note = "最低保證薪資" if not max_salary else ""
        return min_salary, max_salary, note
        
    # Annual salary
    match = re.match(r"年薪(\d+)(?:~(\d+))?元", salary)
    if match:
        min_salary = int(match.group(1)) // 13
        max_salary = int(match.group(2)) // 13 if match.group(2) else None
        note = "年薪轉換為月薪"
        return min_salary, max_salary, note
        
    return None, None, "其他格式"

def main():
    print(f"Loading final CSV: {FINAL_CSV}")
    df_final = pd.read_csv(FINAL_CSV)
    print(f"Final CSV rows: {len(df_final)}")
    
    print(f"Loading raw CSV: {RAW_CSV}")
    try:
        df_raw = pd.read_csv(RAW_CSV)
        print(f"Raw CSV rows: {len(df_raw)}")
    except Exception as e:
        print(f"Failed to load raw CSV: {e}")
        return

    # Ensure job_id is string
    if 'job_id' in df_final.columns:
        df_final['job_id'] = df_final['job_id'].astype(str)
    if 'job_id' in df_raw.columns:
        df_raw['job_id'] = df_raw['job_id'].astype(str)
        
    # Create a mapping from job_id to salary string
    salary_map = df_raw.set_index('job_id')['salary'].to_dict()
    
    print("Regenerating salary_note...")
    
    def get_note(row):
        # If we already have a valid note, keep it (unless it's NaN)
        if pd.notna(row.get('salary_note')):
            return row['salary_note']
            
        job_id = str(row['job_id'])
        raw_salary = salary_map.get(job_id)
        
        _, _, note = parse_salary(raw_salary)
        return note

    df_final['salary_note'] = df_final.apply(get_note, axis=1)
    
    print("\nNew salary_note counts:")
    print(df_final['salary_note'].value_counts())
    
    print(f"\nSaving patched CSV to {FINAL_CSV}...")
    df_final.to_csv(FINAL_CSV, index=False)
    print("Done.")

if __name__ == "__main__":
    main()
