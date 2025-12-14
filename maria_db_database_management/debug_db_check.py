import sys
import os
from sqlalchemy import create_engine, text

# Adjust path to find db_config in parent or specific location
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

# Try imports
try:
    from db_config import DB_HOST, DB_USER, DB_PASSWORD
    print(f"Loaded config for host: {DB_HOST}")
except ImportError:
    # Try adding 104_jobdata_crawler_final to path
    sys.path.append(os.path.join(parent_dir, '104_jobdata_crawler_final'))
    try:
        from db_config import DB_HOST, DB_USER, DB_PASSWORD
        print(f"Loaded config from subdirectory for host: {DB_HOST}")
    except ImportError:
        print("Failed to load db_config")
        exit(1)

# Connect to 'rawdata' DB
source_db = 'job_data_warehouse'
conn_str = f'mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:3306/{source_db}'
engine = create_engine(conn_str)

try:
    with engine.connect() as conn:
        print(f"Connected to {source_db} successfully!")
        result = conn.execute(text("SHOW TABLES"))
        print("Tables in rawdata:")
        for row in result:
            print(row)
        
        # Check if 104rawdata exists and has data
        result = conn.execute(text("SELECT count(*) FROM 104rawdata"))
        count = result.scalar()
        print(f"Row count in 104rawdata: {count}")
        
except Exception as e:
    print(f"Connection failed: {e}")
