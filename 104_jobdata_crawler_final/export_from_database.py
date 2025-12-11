# export_from_database_fixed.py
import pandas as pd
from sqlalchemy import create_engine, inspect
import re

# ==================== 1. 設定 ====================
try:
    from db_config import DB_HOST, DB_USER, DB_PASSWORD, DB_NAME
except ImportError:
    print("錯誤：找不到 db_config.py，請確認已建立設定檔。")
    exit(1)

# 使用設定檔中的資訊
HOST = DB_HOST
USER = DB_USER
PASSWORD = DB_PASSWORD
DATABASE = DB_NAME

# 連線
# 注意：若遇到 "pandas only supports SQLAlchemy..." 警告，請確保已安裝 SQLAlchemy 和 pymysql
connection_string = f'mysql+pymysql://{USER}:{PASSWORD}@{HOST}:3306/{DATABASE}'
engine = create_engine(connection_string)

print(f"正在連線至資料庫 {DATABASE} ...")

# 獲取所有資料表名稱
inspector = inspect(engine)
tables = inspector.get_table_names()
print(f"找到以下資料表：{tables}")

# ==================== 2. 清理函式 ====================
def clean_text(text):
    if pd.isna(text):
        return ""
    text = str(text)
    # 將換行符號取代為空白，避免 CSV 換行
    text = re.sub(r'[\r\n\t]', ' ', text)
    # 移除 unicode 行分隔符號 (這些也會造成 Excel 換行)
    text = re.sub(r'[\u2028\u2029]', ' ', text)
    # 移除其他控制字元
    text = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', text)
    # 移除零寬空格之類的隱藏字元
    text = re.sub(r'[\u200B-\u200D\uFEFF]', '', text)
    # 限制長度（Excel 單格上限 32767）
    return text[:32767].strip()

# ==================== 3. 逐一匯出 ====================
for table in tables:
    print(f"\n[{table}] 正在匯出...")
    try:
        query = f"SELECT * FROM {table}"
        df = pd.read_sql(query, engine)
        
        # 執行清理：針對所有文字類型的欄位 (object) 都進行清理
        for col in df.columns:
            if df[col].dtype == 'object':
                # print(f"  正在清理欄位：{col}") # 減少輸出雜訊
                df[col] = df[col].apply(clean_text)
        
        output_filename = f'{table}_export.csv'
        df.to_csv(output_filename, index=False, encoding='UTF-8')
        print(f"  ✅ 成功匯出：{output_filename} (共 {len(df):,} 筆)")
        
    except Exception as e:
        print(f"  ❌ 匯出失敗：{e}")

print("\n全部完成！")
