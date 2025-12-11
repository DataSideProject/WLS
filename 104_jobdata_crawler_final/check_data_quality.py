# check_data_quality.py
import pandas as pd
from sqlalchemy import create_engine

# GCP MariaDB 資訊
try:
    from db_config import DB_HOST, DB_USER, DB_PASSWORD, DB_NAME
except ImportError:
    print("錯誤：找不到 db_config.py")
    exit(1)

HOST = DB_HOST
USER = DB_USER
PASSWORD = DB_PASSWORD
DATABASE = DB_NAME

connection_string = f'mysql+pymysql://{USER}:{PASSWORD}@{HOST}:3306/{DATABASE}'
engine = create_engine(connection_string)

print("正在檢查 job_details 資料表中的異常資料...")

# 檢查 company 欄位是否包含不該出現的值（例如 "全職"）
query_anomalies = """
SELECT id, url, job_title, company, industry, salary
FROM job_details 
WHERE salary LIKE '1' 
   OR salary LIKE '2' 
   OR salary LIKE '3'
LIMIT 20
"""

try:
    df = pd.read_sql(query_anomalies, engine)
    if not df.empty:
        print(f"找到 {len(df)} 筆可疑資料 (salary 欄位異常):")
        print(df.head(10))
    else:
        print("未發現 salary 欄位包含 '1/2/3' 的明顯異常。")

    # 另外檢查一下是否有資料位移的狀況 (例如 job_title 為空但後面有值)
    query_empty_title = "SELECT id, company FROM job_details WHERE job_title = '' OR job_title IS NULL LIMIT 5"
    df_empty_title = pd.read_sql(query_empty_title, engine)
    if not df_empty_title.empty:
        print("\n發現 job_title 為空的資料:")
        print(df_empty_title)

except Exception as e:
    print(f"查詢失敗: {e}")
