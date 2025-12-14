import pandas as pd
from sqlalchemy import create_engine
import sys
import os

# 引入設定
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db_config import DB_HOST, DB_USER, DB_PASSWORD

def inspect_source_data():
    print("="*50)
    print("資料源檢測報告 (Data Inspection Report)")
    print("="*50)

    # 1. 連線 Raw Data
    SOURCE_DB = 'rawdata'
    conn_str = f'mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:3306/{SOURCE_DB}'
    try:
        engine = create_engine(conn_str)
        print(f"成功連線至來源資料庫: {SOURCE_DB}")
    except Exception as e:
        print(f"連線失敗: {e}")
        return

    # 2. 讀取資料
    # 使用者可以傳入 table name，目前先預設 104rawdata
    target_table = 'job_details' 
    if len(sys.argv) > 1:
        target_table = sys.argv[1]
        
    print(f"正在讀取資料 Table: {target_table} ...")
    try:
        df = pd.read_sql(f"SELECT * FROM {target_table} LIMIT 10", engine) # 先讀 10 筆看欄位
        print(f"資料表欄位清單: {list(df.columns)}")
        print("-" * 30)
        
        # 讀取全部以分析長度
        print(f"正在讀取全部資料以分析長度 (可能需要一點時間)...")
        df = pd.read_sql(f"SELECT * FROM {target_table}", engine)
        print(f"總筆數: {len(df)}")
        
    except Exception as e:
        print(f"讀取表格失敗: {e}")
        return

    print("-" * 30)

    # 3. 定義檢測規則 (Schema Constraints)
    # 這裡對照 01_create_schema.py 的設定
    # 如果要針對 CakeResume，請確保這裡的 key 是 'Mapping 後的 Source Column'
    # 但這個 Inspect 工具比較單純，我們先檢查 Target Schema 想要的核心欄位是否長度過長
    
    constraints = {
        'job_title': 500,
        # 'link': 65535, # OLD Check - Text is huge
        'languages': 500,
        'BT_EXP': 100,
        'title': 500,     # For generic usage if source has 'title'
        'job_link': 65535,
    }
    
    # 4. 執行檢測
    warnings = 0
    
    # 自動偵測有哪個欄位就檢查哪個
    for col, limit in constraints.items():
        if col not in df.columns:
            print(f"[?] 來源資料缺少欄位: {col}")
            continue
            
        # 計算字串長度 (處理 NaN 為空字串)
        # 注意: 這裡都先轉 str 以防原本是數字或 float
        max_len = df[col].astype(str).replace('nan', '').map(len).max()
        
        status = "OK"
        if max_len > limit:
            status = "WARNING (Truncation Risk)"
            warnings += 1
            
        print(f"欄位 {col:<15} | 最大長度: {max_len:<5} | 限制: {limit:<5} | {status}")

    print("-" * 30)
    
    # 5. 檢測必要欄位空值 (Null Check)
    required_cols = ['job_id', 'company', 'location']
    for col in required_cols:
        if col not in df.columns:
            print(f"[!] 缺少必要欄位: {col}")
            continue
            
        null_count = df[col].isnull().sum()
        empty_str_count = (df[col].astype(str).replace('nan', '').str.strip() == '').sum()
        total_missing = null_count + empty_str_count
        
        if total_missing > 0:
            print(f"欄位 {col:<15} | 發現缺值: {total_missing} 筆")
        else:
            print(f"欄位 {col:<15} | 完整 (No Nulls)")

    print("="*50)
    if warnings > 0:
        print(f"總結: 發現 {warnings} 個潛在風險，請檢視上方 WARNING。")
    else:
        print("總結: 資料源檢查通過，可安心匯入。")
    print("="*50)

if __name__ == "__main__":
    inspect_source_data()
