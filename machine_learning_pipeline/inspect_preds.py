
import pandas as pd
from sqlalchemy import create_engine
import sys
import os

# Setup paths
current_dir = os.path.dirname(os.path.abspath(__file__))
wls_root = os.path.dirname(current_dir)
if wls_root not in sys.path: sys.path.insert(0, wls_root)

try:
    from db_config import DB_HOST, DB_USER, DB_PASSWORD
    DB_NAME = 'job_data_warehouse'
except ImportError:
    print("Config error")
    sys.exit(1)

engine = create_engine(f'mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:3306/{DB_NAME}')

try:
    df = pd.read_sql("SELECT * FROM fact_job_predictions LIMIT 1", engine)
    for col in df.columns:
        print(col)
except Exception as e:
    print(e)
