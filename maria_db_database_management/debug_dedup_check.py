import pandas as pd
from sqlalchemy import create_engine
import sys
import os

# 引入設定
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db_config import DB_HOST, DB_USER, DB_PASSWORD

def analyze_uniqueness():
    print("="*50)
    print("資料唯一性與去重邏輯分析")
    print("="*50)
    
    SOURCE_DB = 'rawdata'
    conn_str = f'mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:3306/{SOURCE_DB}'
    engine = create_engine(conn_str)
    
    try:
        df = pd.read_sql("SELECT * FROM 104rawdata", engine)
        print(f"總筆數 (Total Rows): {len(df)}")
        print("-" * 30)
        
        # 1. 檢查 Job ID 唯一性
        uniq_jid = df['job_id'].nunique()
        print(f"不重複 Job ID 數: {uniq_jid}")
        print(f"重複 Job ID 數  : {len(df) - uniq_jid}")
        
        # 2. 檢查 Job ID + Update Date
        # 假設 update_date_clean 是日期字串
        df['combined_date'] = df['job_id'].astype(str) + '_' + df['update_date_clean'].astype(str)
        uniq_date = df['combined_date'].nunique()
        print(f"不重複 (Job ID + UpdateDate): {uniq_date}")
        
        # 3. 檢查 Unique Key (如果有)
        if 'unique_key' in df.columns:
            uniq_key = df['unique_key'].nunique()
            print(f"不重複 Unique Key: {uniq_key}")
            
        # 4. 檢查 Created At (爬取時間?)
        if 'created_at' in df.columns:
             df['combined_create'] = df['job_id'].astype(str) + '_' + df['created_at'].astype(str)
             uniq_create = df['combined_create'].nunique()
             print(f"不重複 (Job ID + CreatedAt): {uniq_create}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    analyze_uniqueness()
