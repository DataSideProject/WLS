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
    Load job data from MySQL Data Warehouse (via View) and flatten it into a DataFrame
    suitable for Machine Learning.
    """
    engine = get_db_engine()
    print(f"Connected to DB: {engine.url.database}")
    
    # Sanity Check
    try:
        check = pd.read_sql("SELECT source FROM view_ml_dataset LIMIT 1", engine)
        print("Sanity Check Passed: view_ml_dataset is accessible.")
    except Exception as e:
        print(f"Sanity Check FAILED: {e}")
        return pd.DataFrame()

    try:
        # 1. Fetch from View (Already Deduped)
        print("Fetching Data from View...")
        query_view = "SELECT * FROM view_ml_dataset"
        if limit:
            query_view += f" ORDER BY post_date DESC LIMIT {limit}"
        
        df_view = pd.read_sql(query_view, engine)
        print(f"  -> Loaded {len(df_view)} rows from view_ml_dataset.")

        if df_view.empty:
            return pd.DataFrame()

        # 1.5 Filter & Normalize Salary (Monthly Basis)
        if 'salary_type' in df_view.columns and 'salary_min' in df_view.columns:
            print("Filtering & Normalizing Salaries...")
            # Filter: Keep only '月薪' and '年薪'
            original_count = len(df_view)
            df_view = df_view[df_view['salary_type'].isin(['月薪', '年薪'])].copy()
            print(f"  -> Filtered out Hourly/Daily. {original_count} -> {len(df_view)} rows.")
            
            # Normalize: Annual -> Monthly (/13)
            mask_annual = df_view['salary_type'] == '年薪'
            
            # Apply conversion
            df_view.loc[mask_annual, 'salary_min'] = df_view.loc[mask_annual, 'salary_min'] / 13.0
            df_view.loc[mask_annual, 'salary_max'] = df_view.loc[mask_annual, 'salary_max'] / 13.0
            
            # Round to integer
            df_view['salary_min'] = df_view['salary_min'].astype(int)
            df_view['salary_max'] = df_view['salary_max'].astype(int)
            print("  -> Normalized '年薪' to Monthly (div 13).")

        print("Fetching Dimension/Bridge Tables for Multi-valued attributes...")
        
        # 2. Fetch Bridge Tables & Aggregate
        
        # Skills (Tools & Work Skills)
        print("Fetching & Aggregating Skills...")
        df_skills = pd.read_sql("""
            SELECT posting_id, GROUP_CONCAT(skill_name SEPARATOR ',') as tools
            FROM bridge_job_skills b
            JOIN dim_skills s ON b.skill_id = s.skill_id
            GROUP BY posting_id
        """, engine)
        
        # Categories
        print("Fetching & Aggregating Categories...")
        df_cats = pd.read_sql("""
            SELECT posting_id, GROUP_CONCAT(category_name SEPARATOR ',') as job_categories
            FROM bridge_job_categories b
            JOIN dim_categories c ON b.category_id = c.category_id
            GROUP BY posting_id
        """, engine)

        # Benefits (New Feature)
        print("Fetching & Aggregating Benefits...")
        df_benefits = pd.read_sql("""
            SELECT posting_id, GROUP_CONCAT(benefit_name SEPARATOR ',') as benefits
            FROM bridge_job_benefits b
            JOIN dim_benefits bn ON b.benefit_id = bn.benefit_id
            GROUP BY posting_id
        """, engine)

        # 3. Merge Everything (Left Join to preserve jobs from view)
        print("Merging DataFrames...")
        df_merged = df_view.merge(df_skills, on='posting_id', how='left')
        df_merged = df_merged.merge(df_cats, on='posting_id', how='left')
        df_merged = df_merged.merge(df_benefits, on='posting_id', how='left')
        
        # 4. Rename Columns to match ML model expectations
        renames = {
            'full_description': 'description',
            'experience_req': 'experience',
            'education_req': 'education'
        }
        df_merged.rename(columns=renames, inplace=True)
        
        # 5. Handle missing location if necessary (View should handle it, but fallback logic kept simple)
        # In View: country, city, district are already columns.
        # We need a single 'location' column for stratify/features if widely used.
        if 'location' not in df_merged.columns:
             # Construct location from City + District
             df_merged['location'] = df_merged['city'].fillna('') + df_merged['district'].fillna('')
        
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
