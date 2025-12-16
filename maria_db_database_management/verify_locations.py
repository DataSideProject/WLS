import sys
import os
from sqlalchemy import create_engine, text
import pandas as pd

# Add current directory to path to find db_config
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

# Try to find db_config in parent directory if not found
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

def verify_locations():
    engine = create_engine(CONNECTION_STRING)
    
    print(f"Connecting to database: {DB_NAME}")
    
    with engine.connect() as conn:
        # 1. Total count
        result = conn.execute(text("SELECT COUNT(*) FROM dim_locations"))
        total_count = result.scalar()
        print(f"Total locations in dim_locations: {total_count}")
        
        # 2. List distinct Countries
        print("\n--- Distinct Countries ---")
        countries = [r[0] for r in conn.execute(text("SELECT DISTINCT country FROM dim_locations")).fetchall()]
        for c in countries:
            print(f"- {c}")
        
        # 3. List distinct Cities
        print("\n--- Distinct Cities (Top 50) ---")
        cities = [r[0] for r in conn.execute(text("SELECT DISTINCT city FROM dim_locations ORDER BY city")).fetchall()]
        for c in cities[:50]:
            print(f"- {c}")
        
        # 4. Check for potential duplicates (similar names)
        print("\n--- Distinct City-District Pairs (Sample 20) ---")
        dists = [f"{r[0]} - {r[1]}" for r in conn.execute(text("SELECT DISTINCT city, district FROM dim_locations ORDER BY city, district LIMIT 20")).fetchall()]
        for d in dists:
            print(d)
        
        # 5. Check specifically for 'Taipei' anomalies or CakeResume specifics if any
        print("\n--- Checking for 'Taipei' variants ---")
        taipei_vars = [r[0] for r in conn.execute(text("SELECT DISTINCT city FROM dim_locations WHERE city LIKE '%Taipei%' OR city LIKE '%台北%'")).fetchall()]
        for t in taipei_vars:
            print(f"- {t}")


if __name__ == "__main__":
    verify_locations()
