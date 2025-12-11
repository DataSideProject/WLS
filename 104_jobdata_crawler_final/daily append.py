# import_to_mariadb.py
# 自動把 job_data_master_raw.csv 的新資料匯入 MariaDB，並自動去重

import pandas as pd
from sqlalchemy import create_engine, text
import os
from datetime import datetime
import time

# ==================== 1. 設定 ====================
# 請修改成你的 GCP MariaDB 資訊
try:
    from db_config import DB_HOST, DB_USER, DB_PASSWORD, DB_NAME
except ImportError:
    print("錯誤：找不到 db_config.py")
    exit(1)

HOST = DB_HOST
USER = DB_USER
PASSWORD = DB_PASSWORD
DATABASE = DB_NAME
TABLE = '104rawdata'

# 連線
engine = create_engine(f'mysql+mysqlconnector://{USER}:{PASSWORD}@{HOST}:3306/{DATABASE}')

# CSV 檔案（你爬蟲產生的 master 檔）
CSV_FILE = 'job_data_master_raw.csv'

# import_to_mariadb_safe.py
# 可與爬蟲同時執行，不會衝突！
def import_safe():
    if not os.path.exists(CSV_FILE):
        print("CSV 不存在，跳過")
        return 0

    # 讀取 CSV（允許爬蟲正在寫）
    try:
        df_csv = pd.read_csv(CSV_FILE, dtype={'job_id': str})
    except Exception as e:
        print(f"讀檔失敗（可能爬蟲正在寫）: {e}")
        return 0

    if 'unique_key' not in df_csv.columns:
        print("缺少 unique_key，跳過")
        return 0

    # 讀取資料庫現有 key
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT unique_key FROM 104rawdata"))
            existing_keys = {row[0] for row in result}
    except Exception as e:
        print(f"連線失敗: {e}")
        return 0

    # 找出新資料
    new_df = df_csv[~df_csv['unique_key'].isin(existing_keys)]
    if len(new_df) == 0:
        print("無新資料")
        return 0

    # 匯入（MariaDB 會自動跳過重複）
    try:
        new_df.to_sql('104rawdata', engine, if_exists='append', index=False, chunksize=500)
        print(f"匯入 {len(new_df)} 筆新資料")
        return len(new_df)
    except Exception as e:
        print(f"匯入失敗: {e}")
        return 0

# 主程式（可無限迴圈）
if __name__ == "__main__":
    print("開始監聽匯入（每 30 分鐘檢查一次）")
    while True:
        imported = import_safe()
        if imported > 0:
            print(f"{datetime.now()} 成功匯入 {imported} 筆")
        time.sleep(1800)  # 30 分鐘
