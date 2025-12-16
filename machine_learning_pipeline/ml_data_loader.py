import pandas as pd
from sqlalchemy import create_engine
import sys
import os

# Ensure we can find db_config in the root directory (WLS)
current_dir = os.path.dirname(os.path.abspath(__file__))
wls_root = os.path.dirname(current_dir) # Go up one level
if wls_root not in sys.path:
    sys.path.insert(0, wls_root)

try:
    from db_config import DB_HOST, DB_USER, DB_PASSWORD
    DB_NAME = 'job_data_warehouse' # Default
except ImportError:
    # If running independently and config not found
    print("Error: Could not find db_config.py in WLS root.")
    DB_HOST = 'localhost'
    DB_USER = 'root'
    DB_PASSWORD = ''
    DB_NAME = 'job_data_warehouse'

def get_db_engine():
    return create_engine(f'mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:3306/{DB_NAME}')

def derive_note(row):
    """Derive salary note based on available data"""
    if pd.isna(row['salary_min']) and pd.isna(row['salary_max']):
        return "無薪資資訊"
    if row['salary_min'] == 0 and row['salary_max'] == 0:
        return "待遇面議"
    return "有薪資數據"

def load_job_data_from_db(limit=None):
    """
    Load job data from MySQL Data Warehouse and flatten it into a DataFrame
    suitable for Machine Learning (similar to the original CSV format).
    """
    engine = get_db_engine()
    print(f"Connected to DB: {engine.url.database}")
    
    # Sanity Check
    try:
        check = pd.read_sql("SELECT source_id FROM fact_job_postings LIMIT 1", engine)
        print("Sanity Check Passed: source_id exists.")
    except Exception as e:
        print(f"Sanity Check FAILED: {e}")
        return pd.DataFrame()

    try:
        # Use Pandas Merge Strategy
        print("Fetching Fact Table...")
        query_fact = "SELECT * FROM fact_job_postings"
        if limit:
            query_fact += f" ORDER BY post_date DESC LIMIT {limit}"
        
        df_fact = pd.read_sql(query_fact, engine)
        print(f"  -> Loaded {len(df_fact)} rows from fact_job_postings.")

        # Deduplication Logic
        if not df_fact.empty and 'job_url' in df_fact.columns:
             # Sort by update_date (if exists) or post_date to keep latest
             sort_col = 'update_date' if 'update_date' in df_fact.columns else 'post_date'
             df_fact[sort_col] = pd.to_datetime(df_fact[sort_col], errors='coerce')
             initial_len = len(df_fact)
             df_fact = df_fact.sort_values(by=sort_col, ascending=True)
             df_fact = df_fact.drop_duplicates(subset=['job_url'], keep='last')
             print(f"  -> Deduplicated: {initial_len} -> {len(df_fact)} rows (kept latest).")

        print("Fetching Dimension Tables...")
        
        # dim_companies: check for name
        df_comp = pd.read_sql("SELECT company_id, name as company_name, industry FROM dim_companies", engine)
        print(f"Comp Cols: {df_comp.columns.tolist()}")
        
        # dim_locations: use explicit columns
        # We verified 'full_address' exists in dims.json, but let's be safe
        try:
             df_loc = pd.read_sql("SELECT location_id, city, district, full_address as location_name FROM dim_locations", engine)
        except Exception:
             print("Warning: full_address/location_name missing, using city/district")
             df_loc = pd.read_sql("SELECT location_id, city, district FROM dim_locations", engine)
        print(f"Loc Cols: {df_loc.columns.tolist()}")
        
        # dim_sources: source_name
        df_src = pd.read_sql("SELECT source_id, source_name FROM dim_sources", engine)
        print(f"Src Cols: {df_src.columns.tolist()}")
        
        # 3. Fetch Bridge Tables & Aggregate
        print("Fetching & Aggregating Skills...")
        df_skills = pd.read_sql("""
            SELECT posting_id, GROUP_CONCAT(skill_name SEPARATOR ',') as tools
            FROM bridge_job_skills b
            JOIN dim_skills s ON b.skill_id = s.skill_id
            GROUP BY posting_id
        """, engine)
        
        print("Fetching & Aggregating Categories...")
        df_cats = pd.read_sql("""
            SELECT posting_id, GROUP_CONCAT(category_name SEPARATOR ',') as job_categories
            FROM bridge_job_categories b
            JOIN dim_categories c ON b.category_id = c.category_id
            GROUP BY posting_id
        """, engine)

        # 4. Merge Everything (Left Join to preserve jobs)
        print("Merging DataFrames...")
        df_merged = df_fact.merge(df_comp, on='company_id', how='left')
        df_merged = df_merged.merge(df_src, on='source_id', how='left')
        df_merged = df_merged.merge(df_loc, on='location_id', how='left')
        
        # Merge skills/cats on posting_id
        df_merged = df_merged.merge(df_skills, on='posting_id', how='left')
        df_merged = df_merged.merge(df_cats, on='posting_id', how='left')
        
        # 5. Rename Columns to match ML model expectations
        # target: company, location, source, description
        
        # Rename logic handles aliased columns or original
        renames = {}
        if 'company_name' in df_merged.columns: renames['company_name'] = 'company'
        if 'source_name' in df_merged.columns: renames['source_name'] = 'source'
        if 'location_name' in df_merged.columns: renames['location_name'] = 'location'
        if 'job_description' in df_merged.columns: renames['job_description'] = 'description'
        if 'education_req' in df_merged.columns: renames['education_req'] = 'education'
        if 'experience_req' in df_merged.columns: renames['experience_req'] = 'experience'
        
        df_merged.rename(columns=renames, inplace=True)
        
        # Drop duplicate columns if any (fail-safe)
        df_merged = df_merged.loc[:, ~df_merged.columns.duplicated()]
        
        # Robust Fallback for Location (if location_name was missing/failed)
        if 'location' not in df_merged.columns:
             if 'city' in df_merged.columns and 'district' in df_merged.columns:
                  # Ensure string type and combine
                  df_merged['location'] = df_merged['city'].fillna('').astype(str) + df_merged['district'].fillna('').astype(str)
             elif 'city' in df_merged.columns:
                  df_merged['location'] = df_merged['city']
             elif 'full_address' in df_merged.columns:
                  df_merged['location'] = df_merged['full_address']
        
        # Robust Fallback for Company/Source
        if 'company' not in df_merged.columns and 'name' in df_merged.columns:
             # If somehow name persisted
             df_merged['company'] = df_merged['name']
             
        df_merged['salary_note'] = df_merged.apply(derive_note, axis=1)
        
        print(f"Successfully constructed dataset: {len(df_merged)} rows.")
        return df_merged

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error loading data: {e}")
        return pd.DataFrame()

if __name__ == "__main__":
    df = load_job_data_from_db(limit=50)
    print("Final Columns:", df.columns.tolist())
    if not df.empty:
        print(df.head(1).T)
