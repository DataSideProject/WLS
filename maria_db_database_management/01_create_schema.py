import sys
import os
from sqlalchemy import create_engine, Column, Integer, String, Date, DateTime, ForeignKey, Boolean, BigInteger, Text, text
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from datetime import datetime

# 1. 自動尋找上層目錄的 db_config.py
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

try:
    from db_config import DB_HOST, DB_USER, DB_PASSWORD, DB_NAME
    print(f"成功載入設定: {DB_HOST} / {DB_NAME}")
except ImportError:
    print("錯誤：找不到 db_config.py，請確保它位於上一層目錄")
    exit(1)

# 2. 連線設定與資料庫建立
# 先連到 MySQL Server (不指定 DB) 來建立 Database
ROOT_CONNECTION_STRING = f'mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:3306'
root_engine = create_engine(ROOT_CONNECTION_STRING)

NEW_DB_NAME = 'job_data_warehouse'

with root_engine.connect() as conn:
    conn.execute(text(f"CREATE DATABASE IF NOT EXISTS {NEW_DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
    print(f"資料庫 {NEW_DB_NAME} 已確保存在。")

# 再連到新資料庫
CONNECTION_STRING = f'mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:3306/{NEW_DB_NAME}'
engine = create_engine(CONNECTION_STRING, echo=True)
Base = declarative_base()

# ==================== 維度表 (Dimensions) ====================

class DimCompany(Base):
    __tablename__ = 'dim_companies'
    company_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), unique=True, nullable=False)
    industry = Column(String(255))
    
class DimLocation(Base):
    __tablename__ = 'dim_locations'
    location_id = Column(Integer, primary_key=True, autoincrement=True)
    country = Column(String(50)) # e.g., 台灣
    city = Column(String(50))     # e.g., 台北市
    district = Column(String(50)) # e.g., 中正區
    full_address = Column(String(255), unique=True) # 用來作為查找 Key

class DimSource(Base):
    __tablename__ = 'dim_sources'
    source_id = Column(Integer, primary_key=True)
    source_name = Column(String(50), unique=True) # 104, CakeResume

class DimCategory(Base):
    __tablename__ = 'dim_categories'
    category_id = Column(Integer, primary_key=True, autoincrement=True)
    category_name = Column(String(100), unique=True)

class DimSkill(Base):
    __tablename__ = 'dim_skills'
    skill_id = Column(Integer, primary_key=True, autoincrement=True)
    skill_name = Column(String(100), unique=True)
    type = Column(String(20)) # 'tool' or 'work_skill'

class DimBenefit(Base):
    __tablename__ = 'dim_benefits'
    benefit_id = Column(Integer, primary_key=True, autoincrement=True)
    benefit_name = Column(String(100), unique=True) # e.g. 年終獎金

# ==================== 事實表 (Fact Tables) ====================

class FactJobPosting(Base):
    __tablename__ = 'fact_job_postings'
    
    posting_id = Column(BigInteger, primary_key=True, autoincrement=True)
    job_id = Column(String(50), nullable=False, index=True) # Business Key, 加 Index 加速搜尋
    
    # Foreign Keys (通常資料庫會自動對 FK 設 Index，但在 SQLAlchemy 顯式宣告有助於釐清)
    company_id = Column(Integer, ForeignKey('dim_companies.company_id'), index=True)
    location_id = Column(Integer, ForeignKey('dim_locations.location_id'), index=True)
    source_id = Column(Integer, ForeignKey('dim_sources.source_id'), index=True)
    
    # Attributes
    job_title = Column(String(255), index=True) # 常用於 LIKE 搜尋
    salary_min = Column(Integer, index=True)    # 常用於 Range 搜尋 (> 50000)
    salary_max = Column(Integer)
    salary_type = Column(String(20)) # '年薪' or '月薪' or '時薪' or '日薪' or '面議'
    experience_req = Column(String(50))
    education_req = Column(String(50))
    post_date = Column(Date, index=True)        # 常用於時間區間篩選
    job_url = Column(String(255)) # https://www.104.com.tw/job/{job_id}
    isManager = Column(Boolean)
    work_shift = Column(String(100)) # '日班' or '晚班' or '大夜班'
    remote_work = Column(String(50)) # '完全遠端' or '部分遠端' or '現場'
    bt_exp = Column(String(50)) # '外派出差需求'
    language = Column(String(50))
    job_description = Column(Text) # Source of Truth for NLP
    other_conditions = Column(Text)
    
    created_at = Column(DateTime, default=datetime.now)

class FactJobPrediction(Base):
    __tablename__ = 'fact_job_predictions'
    
    prediction_id = Column(BigInteger, primary_key=True, autoincrement=True)
    # 這裡關聯到 posting_id (Specific Snapshot) 還是 job_id (General Job)? 
    # MLOps 通常針對Specific Snapshot預測
    posting_id = Column(BigInteger, ForeignKey('fact_job_postings.posting_id'))
    
    model_version = Column(String(50))
    pred_salary_min = Column(Integer)
    pred_salary_max = Column(Integer)
    prediction_time = Column(DateTime, default=datetime.now)

# ==================== 橋接表 (Bridge Tables) ====================

class BridgeJobCategory(Base):
    __tablename__ = 'bridge_job_categories'
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    posting_id = Column(BigInteger, ForeignKey('fact_job_postings.posting_id'))
    category_id = Column(Integer, ForeignKey('dim_categories.category_id'))

class BridgeJobSkill(Base):
    __tablename__ = 'bridge_job_skills'
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    posting_id = Column(BigInteger, ForeignKey('fact_job_postings.posting_id'))
    skill_id = Column(Integer, ForeignKey('dim_skills.skill_id'))
    types = Column(String(20))

class BridgeJobBenefit(Base):
    __tablename__ = 'bridge_job_benefits'
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    posting_id = Column(BigInteger, ForeignKey('fact_job_postings.posting_id'))
    benefit_id = Column(Integer, ForeignKey('dim_benefits.benefit_id'))

# ==================== 執行建立 ====================
if __name__ == "__main__":
    print("正在建立資料庫 Schema...")
    # Base.metadata.drop_all(engine) # 小心使用，這會刪除所有表
    Base.metadata.create_all(engine)
    
    # 初始化預設資料 (Source)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # 預設來源
    sources = [{'id': 1, 'name': '104'}, {'id': 2, 'name': 'CakeResume'}]
    for s in sources:
        exist = session.query(DimSource).filter_by(source_id=s['id']).first()
        if not exist:
            session.add(DimSource(source_id=s['id'], source_name=s['name']))
    
    session.commit()
    print("Schema 建立完成，並已初始化 DimSource。")
