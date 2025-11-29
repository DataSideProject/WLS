# export_from_database_fixed.py
import pandas as pd
from sqlalchemy import create_engine
import re

# ==================== 1. 設定 ====================
# 請修改成你的 GCP MariaDB 資訊
HOST = '34.81.186.201'          # 你的 GCP 外部 IP
USER = 'datauser'
PASSWORD = '123456'
DATABASE = 'rawdata'
TABLE = '104rawdata'

# 連線
engine = create_engine(f'mysql+mysqlconnector://{USER}:{PASSWORD}@{HOST}:3306/{DATABASE}')

print("正在匯出 104rawdata ...")
df = pd.read_sql("SELECT * FROM 104rawdata", engine)

# 關鍵：清理非法字元（一鍵解決！）
def clean_text(text):
    if pd.isna(text):
        return ""
    # 移除 \x00 到 \x1F（Excel 不接受的控制字元）
    text = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', str(text))
    # 移除零寬空格之類的隱藏字元
    text = re.sub(r'[\u200B-\u200D\uFEFF]', '', text)
    # 限制長度（Excel 單格上限 32767）
    return text[:32767]

# 對所有文字欄位做清理
text_columns = ['job_title', 'company', 'job_description', 'job_categories',
                'other_conditions', 'tags', 'tools', 'work_skills']
for col in text_columns:
    if col in df.columns:
        print(f"正在清理欄位：{col}")
        df[col] = df[col].apply(clean_text)

# 匯出（保證成功！）
df.to_csv('job_data_master_raw_export.csv', index=False, encoding='UTF-8')
print(f"匯出成功！共 {len(df):,} 筆")
