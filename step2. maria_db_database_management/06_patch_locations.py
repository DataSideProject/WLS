import sys
import os
from sqlalchemy import create_engine, text
from etl_transformers import COUNTRY_MAPPING

# Path setup
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
try:
    from db_config import DB_HOST, DB_USER, DB_PASSWORD
except ImportError:
    print("Error: Could not find db_config.py")
    exit(1)

DB_NAME = 'job_data_warehouse'
CONNECTION_STRING = f'mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:3306/{DB_NAME}'

def patch_locations():
    engine = create_engine(CONNECTION_STRING)
    print(f"Connecting to {DB_NAME}...")
    
    with engine.connect() as conn:
        print("Starting batch update of country names...")
        updated_count = 0
        
        transaction = conn.begin()
        try:
            for eng_name, zhtw_name in COUNTRY_MAPPING.items():
                print(f"Update: '{eng_name}' -> '{zhtw_name}'")
                stmt = text("UPDATE dim_locations SET country = :zh WHERE country = :eng")
                result = conn.execute(stmt, {'zh': zhtw_name, 'eng': eng_name})
                if result.rowcount > 0:
                    print(f"  -> Updated {result.rowcount} rows.")
                    updated_count += result.rowcount
            
            transaction.commit()
            print("="*30)
            print(f"Patch complete. Total rows updated: {updated_count}")
        except Exception as e:
            transaction.rollback()
            print(f"Error during patch: {e}")
            raise

if __name__ == "__main__":
    patch_locations()
