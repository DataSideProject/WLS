import pandas as pd
from datetime import datetime, timezone
import re
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from etl_transformers import (
    parse_salary, parse_location, 
    parse_salary_cakeresume, parse_location_cakeresume, 
    parse_experience_cakeresume, parse_management_cakeresume,
    get_md5_id, normalize_remote
)

import sys
import os
import re

# 引入 Schema 定義
from importlib import import_module
# Add parent directory to path to find db_config
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from db_config import DB_HOST, DB_USER, DB_PASSWORD
    
create_schema = import_module("01_create_schema")
Base = create_schema.Base
engine = create_schema.engine
DimCompany = create_schema.DimCompany
DimLocation = create_schema.DimLocation
DimSource = create_schema.DimSource
DimCategory = create_schema.DimCategory
DimSkill = create_schema.DimSkill
DimBenefit = create_schema.DimBenefit
FactJobPosting = create_schema.FactJobPosting
BridgeJobCategory = create_schema.BridgeJobCategory
BridgeJobSkill = create_schema.BridgeJobSkill
BridgeJobBenefit = create_schema.BridgeJobBenefit

# ==================== Helper Functions ====================

def parse_salary(salary_str):
    """
    簡易解析薪資字串，回傳 (min, max, type)
    支援格式: "月薪30,000~50,000元", "年薪600,000元以上", "待遇面議"
    """
    if pd.isna(salary_str) or '面議' in str(salary_str):
        return None, None, '面議'
    
    clean_str = str(salary_str).replace(',', '')
    # 提取所有數字
    nums = [int(n) for n in re.findall(r'\d+', clean_str)]
    
    salary_type = '月薪'
    if '年薪' in str(salary_str):
        salary_type = '年薪'
    elif '日薪' in str(salary_str):
        salary_type = '日薪'
    elif '時薪' in str(salary_str):
        salary_type = '時薪'
        
    if not nums:
        return None, None, salary_type
    
    s_min = nums[0]
    s_max = nums[1] if len(nums) > 1 else s_min # 如果只有一個數字 (e.g. 4萬以上)，視為 min=max 或 min only
    
    return s_min, s_max, salary_type

def get_or_create_dim(session, Model, filters, defaults=None, cache=None):
    """
    Generic function to get or create a dimension row.
    cache: dict key -> id
    """
    # 建立 Cache Key (假設 filters 只有一個欄位)
    filter_key = list(filters.values())[0]
    
    if cache is not None and filter_key in cache:
        return cache[filter_key]
    
    instance = session.query(Model).filter_by(**filters).first()
    if not instance:
        params = {**filters, **(defaults or {})}
        instance = Model(**params)
        session.add(instance)
        session.flush() # 取得 ID
        
    if cache is not None:
        cache[filter_key] = list(instance.__table__.primary_key.columns)[0].type.python_type(getattr(instance, list(instance.__table__.primary_key.columns)[0].name))
        
    return getattr(instance, list(instance.__table__.primary_key.columns)[0].name)

# 引入 ETL Mapping
try:
    from etl_mappings import ETL_MAPPINGS
except ImportError:
    # Fallback default if file missing
    print("Warning: etl_mappings.py not found, using default 104 mapping.")
    ETL_MAPPINGS = {
        '104': {
            'table_name': '104rawdata',
            'source_id': 1,
            'columns': {
                'job_id': 'job_id', 'company': 'company', 'industry': 'industry', 'location': 'location',
                'job_title': 'job_title', 'salary': 'salary', 'experience': 'experience', 'education': 'education',
                'link': 'link', 'management_responsibility': 'management_responsibility',
                'work_shift': 'work_shift', 'remote_work': 'remote_work', 'bt_exp': 'BT_EXP',
                'languages': 'languages', 'job_description': 'job_description', 'other_conditions': 'other_conditions',
                'update_date': 'update_date_clean', 'job_categories': 'job_categories',
                'tools': 'tools', 'work_skills': 'work_skills', 'tags': 'tags'
            }
        }
    }

# ==================== Main ETL Logic ====================

def run_etl(source_key='104'):
    print(f"開始 ETL 流程 (Source: {source_key})...")
    
    if source_key not in ETL_MAPPINGS:
        print(f"錯誤: 找不到來源 {source_key} 的設定檔")
        return
        
    config = ETL_MAPPINGS[source_key]
    cols = config['columns'] # Column Mapping Dict
    SOURCE_TABLE = config['table_name']
    SOURCE_ID_VAL = config['source_id']

    # 0. 建立 Source Connection (Raw Data)
    SOURCE_DB = 'rawdata'
    conn_str_source = f'mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:3306/{SOURCE_DB}'
    source_engine = create_engine(conn_str_source)
    
    print(f"從資料庫 {SOURCE_DB} 讀取原始資料表 {SOURCE_TABLE}...")
    try:
        query = f"SELECT * FROM {SOURCE_TABLE}" 
        df = pd.read_sql(query, source_engine)
        print(f"已從 DB 讀取 {len(df)} 筆原始資料")
    except Exception as e:
        print(f"讀取 Source DB 失敗: {e}")
        return

    Session = sessionmaker(bind=engine)
    session = Session()

    # 2. 初始化 Cache (加速查找)
    print("載入維度快取...")
    cache_company = {r.name: r.company_id for r in session.query(DimCompany).all()}
    cache_location = {r.full_address: r.location_id for r in session.query(DimLocation).all()}
    cache_category = {r.category_name: r.category_id for r in session.query(DimCategory).all()}
    cache_skill = {r.skill_name: r.skill_id for r in session.query(DimSkill).all()}
    cache_benefit = {r.benefit_name: r.benefit_id for r in session.query(DimBenefit).all()}
    
    # 載入已存在的 Job ID + Post Date 以進行去重 (Deduplication)
    # 支援歷史資料：若同一 job_id 但不同 post_date，視為新資料
    print("載入現有資料 (Job ID + Date) 以去重...")
    existing_jobs = set((r.job_id, r.post_date) for r in session.query(FactJobPosting.job_id, FactJobPosting.post_date).all())
    print(f"已存在 {len(existing_jobs)} 筆職缺記錄")

    print("開始逐筆寫入資料庫...")
    count = 0
    duplicate_count = 0
    success_count = 0
    fail_count = 0
    
    for _, row in df.iterrows():
        count += 1
        try:
            # Dynamic Column Access
            # Date Parsing moved UP for Deduplication Check
            post_date_val = None
            try:
                date_raw = str(row.get(cols['update_date'], '')).strip()
                if source_key == 'cakeresume':
                     # 假設 CakeResume 是 datetime 物件或完整字串
                     if isinstance(row.get(cols['update_date']), datetime):
                         post_date_val = row.get(cols['update_date']).date()
                     else:
                         post_date_val = datetime.strptime(date_raw.split(' ')[0], '%Y-%m-%d').date()
                else:
                    d_str = date_raw.split(' ')[0] 
                    post_date_val = datetime.strptime(d_str, '%Y-%m-%d').date()
            except:
                post_date_val = datetime.today().date()

            # Job ID Logic
            job_id_val = row.get(cols['job_id'])
            if source_key == 'cakeresume':
                # User Request: source_id + id (e.g., "2_software-engineer-slug")
                # No MD5, uses raw slug
                raw_id = str(job_id_val).strip()
                job_id_str = f"{SOURCE_ID_VAL}_{raw_id}"
            else:
                job_id_str = str(job_id_val) if pd.notnull(job_id_val) else 'UNKNOWN'

            # ---> Deduplication Check (Composite Key) <---
            if (job_id_str, post_date_val) in existing_jobs:
                duplicate_count += 1
                if duplicate_count % 1000 == 0:
                     print(f"已跳過 {duplicate_count} 筆重複資料...")
                continue
            # -----------------------------

            # --- Dimensions ---
            
            # Company
            comp_name = str(row.get(cols['company'], 'Unknown')).strip().replace('\r', '').replace('\n', ' ')
            comp_id = get_or_create_dim(session, DimCompany, {'name': comp_name}, 
                                      defaults={'industry': row.get(cols['industry'], '')}, 
                                      cache=cache_company)
            
            # Location
            loc_full = str(row.get(cols['location'], 'Unknown')).strip().replace('\r', '').replace('\n', ' ')
            if source_key == 'cakeresume':
                 country, city, dist = parse_location_cakeresume(loc_full)
            else:
                 country, city, dist = parse_location(loc_full)
            
            loc_id = get_or_create_dim(session, DimLocation, {'full_address': loc_full}, 
                                     defaults={'country': country, 'city': city, 'district': dist}, 
                                     cache=cache_location)
            
            # --- Fact Job Postings ---
            
            if source_key == 'cakeresume':
                s_min, s_max, s_type = parse_salary_cakeresume(row.get(cols['salary'], ''))
                exp_req = parse_experience_cakeresume(row.get(cols['experience'], ''))
                is_mgr = parse_management_cakeresume(row.get(cols['management_responsibility'], ''))
            else:
                s_min, s_max, s_type = parse_salary(row.get(cols['salary'], ''))
                exp_req = str(row.get(cols['experience'], '')).strip()
                is_mgr = (str(row.get(cols['management_responsibility'], '')) != 'nan' and str(row.get(cols['management_responsibility'], '')) != '不需負擔管理責任')
            
            fact = FactJobPosting(
                job_id = job_id_str,
                company_id = comp_id,
                location_id = loc_id,
                source_id = SOURCE_ID_VAL,
                job_title = str(row.get(cols['job_title'], '')).strip().replace('\r', '').replace('\n', ' '),
                salary_min = s_min,
                salary_max = s_max,
                salary_type = s_type,
                experience_req = exp_req,
                education_req = str(row.get(cols['education'], '')).strip(), 
                post_date = post_date_val,
                # New Columns
                job_url = str(row.get(cols['link'], f'https://www.104.com.tw/job/{job_id_str}')).strip(),
                isManager = is_mgr,
                work_shift = str(row.get(cols['work_shift'], '')).strip(),
                remote_work = normalize_remote(str(row.get(cols['remote_work'], '')).strip()),

                bt_exp = str(row.get(cols['bt_exp'], '')).strip(),
                language = str(row.get(cols['languages'], '')).strip(), 
                job_description = str(row.get(cols['job_description'], '')).strip(), 
                other_conditions = str(row.get(cols['other_conditions'], '')).strip()
            )

            session.add(fact)
            session.flush() # 為了取得 posting_id
            
            # --- Bridge Tables ---
            
            # Categories 
            cats_raw = str(row.get(cols['job_categories'], ''))
            cats = re.split(r'[,、]', cats_raw)
            for c_name in cats:
                c_name = c_name.strip()
                if not c_name: continue
                c_id = get_or_create_dim(session, DimCategory, {'category_name': c_name}, cache=cache_category)
                session.add(BridgeJobCategory(posting_id=fact.posting_id, category_id=c_id))
            
            # Skills (Tools)
            tools_raw = str(row.get(cols['tools'], '')) 
            tools = re.split(r'[,、]', tools_raw)
            for t_name in tools:
                t_name = t_name.strip()
                if not t_name: continue
                s_id = get_or_create_dim(session, DimSkill, {'skill_name': t_name}, 
                                       defaults={'type': 'tool'}, 
                                       cache=cache_skill)
                session.add(BridgeJobSkill(posting_id=fact.posting_id, skill_id=s_id, types='tool'))
            
            # Work Skills
            skills_raw = str(row.get(cols['work_skills'], '')) 
            skills = re.split(r'[,、]', skills_raw)
            for s_name in skills:
                s_name = s_name.strip()
                if not s_name: continue
                s_id = get_or_create_dim(session, DimSkill, {'skill_name': s_name}, 
                                       defaults={'type': 'work_skill'}, 
                                       cache=cache_skill)
                session.add(BridgeJobSkill(posting_id=fact.posting_id, skill_id=s_id, types='work_skill'))
            
            # Application Tags / Benefits
            tags_raw = str(row.get(cols['tags'], '')) 
            tags = re.split(r'[,、]', tags_raw)
            for tag_name in tags:
                tag_name = tag_name.strip()
                if not tag_name: continue
                b_id = get_or_create_dim(session, DimBenefit, {'benefit_name': tag_name}, 
                                       cache=cache_benefit)
                session.add(BridgeJobBenefit(posting_id=fact.posting_id, benefit_id=b_id))

            success_count += 1
            if success_count % 1000 == 0:
                session.commit()
                print(f"進度：已處理 {count} 筆 | 成功匯入: {success_count} | 跳過重複: {duplicate_count} | 失敗: {fail_count}")
            
            # Important: Update local set for intra-batch deduplication
            existing_jobs.add((job_id_str, post_date_val))
                
        except Exception as e:
            fail_count += 1
            error_msg = f"[Error] Row {count} (Job ID: {row.get(cols['job_id'])}) Failed: {e}"
            print(error_msg)
            
            # Log to file for detailed inspection
            with open('etl_failure_log.txt', 'a', encoding='utf-8') as f:
                f.write(f"{datetime.now(timezone.utc)} - {error_msg}\n")
                f.write(f"Row Data: {row.to_dict()}\n")
                f.write("-" * 30 + "\n")
            
            session.rollback()
            # CRITICAL: Rollback means IDs created in this transaction are gone from DB, 
            # but they might still be in our local cache! We MUST clear caches to prevent FK errors.
            cache_company.clear()
            cache_location.clear()
            cache_category.clear()
            cache_skill.clear()
            cache_benefit.clear()
            continue

    session.commit()
    print("="*50)
    print(f"ETL 執行完成報告 ({source_key})")
    print("="*50)
    print(f"資料來源總筆數: {len(df)}")
    print(f"成功寫入 (Inserted): {success_count}")
    print(f"重複跳過 (Skipped) : {duplicate_count}")
    print(f"寫入失敗 (Failed)  : {fail_count}")
    print("="*50)

if __name__ == "__main__":
    # 可從參數讀取 user 指定的 source_key，預設 104
    source_arg = '104'
    if len(sys.argv) > 1:
        source_arg = sys.argv[1]
    
    run_etl(source_key=source_arg)
