
import pandas as pd
from sqlalchemy import create_engine
from ml_data_loader import load_job_data_from_db, get_db_engine

def debug_specific_row(target_id=17540):
    print(f"--- DEBUGGING NORMALIZATION FOR ID {target_id} ---")
    
    # 1. Raw DB Check
    engine = get_db_engine()
    print("1. Raw DB Query:")
    from sqlalchemy import text
    with engine.connect() as conn:
        result = conn.execute(text(f"SELECT posting_id, salary_type, salary_min, salary_max FROM view_ml_dataset WHERE posting_id = {target_id}"))
        for row in result:
            print(f"   DB Row: {row}")
            stype = row[1]
            print(f"   Salary Type Hex: {stype.encode('utf-8').hex() if isinstance(stype, str) else type(stype)}")

    # 2. Logic Simulation
    print("\n2. Simulation:")
    df_view = pd.read_sql(f"SELECT * FROM view_ml_dataset WHERE posting_id = {target_id}", engine)
    
    val_before = df_view.iloc[0]['salary_min']
    type_before = df_view.iloc[0]['salary_type']
    print(f"   Before: Type='{type_before}', Min={val_before}")
    
    # Apply EXACT logic from ml_data_loader
    mask_annual = df_view['salary_type'].astype(str).str.strip() == '年薪'
    print(f"   Is Annual? {mask_annual.iloc[0]}")
    
    if mask_annual.any():
        print("   -> Normalizing...")
        df_view.loc[mask_annual, 'salary_min'] = df_view.loc[mask_annual, 'salary_min'] / 13.0
        df_view.loc[mask_annual, 'salary_max'] = df_view.loc[mask_annual, 'salary_max'] / 13.0
    
    val_after = df_view.iloc[0]['salary_min']
    print(f"   After: Min={val_after}")

    # 3. Full Loader Test
    print("\n3. Full Loader Test (loading all data):")
    df_full = load_job_data_from_db(limit=None)
    row_full = df_full[df_full['posting_id'] == target_id]
    if not row_full.empty:
        print(f"   Loaded Row: {row_full[['posting_id', 'salary_type', 'salary_min', 'salary_max']].to_dict('records')}")
    else:
        print("   Row not found in full load!")

if __name__ == "__main__":
    debug_specific_row()
