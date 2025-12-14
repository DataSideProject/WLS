import pandas as pd
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text, create_engine
from datetime import datetime
import sys
import os
import re

# 引入 Schema 定義
from importlib import import_module
try:
    # Try importing from the same directory first
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) # Add parent for db_config
    from db_config import DB_HOST, DB_USER, DB_PASSWORD, DB_NAME
except ImportError:
    print("Warning: Could not import db_config directly.")
    
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

def parse_location(loc_str):
    """
    解析地點，回傳 (Country, City, District)
    邏輯：
    1. 檢查是否為台灣縣市 -> Country='台灣'
    2. 檢查常見國家關鍵字 (日本, 美國...) -> Country=關鍵字
    3. 其他 -> Country=原始字串
    """
    if pd.isna(loc_str): return 'Unknown', 'Unknown', 'Unknown'
    loc_str = str(loc_str).strip()
    
    # 台灣縣市列表
    tw_cities = ['台北市', '新北市', '桃園市', '台中市', '台南市', '高雄市', 
                 '基隆市', '新竹市', '嘉義市', '新竹縣', '苗栗縣', '彰化縣', 
                 '南投縣', '雲林縣', '嘉義縣', '屏東縣', '宜蘭縣', '花蓮縣', 
                 '台東縣', '澎湖縣', '金門縣', '連江縣']
                 
    for city in tw_cities:
        if loc_str.startswith(city):
            # e.g. "台北市中正區" -> TW, 台北市, 中正區
            # e.g. "台北市" -> TW, 台北市, ''
            dist = loc_str[len(city):]
            return '台灣', city, dist
            
    # 國際地點簡易判斷
    if any(c in loc_str for c in ['日本', '越南', '印尼', '泰國', '菲律賓', '馬來西亞', '新加坡', '韓國']):
        # 假設前兩個字是國家 (e.g. 日本大阪) -> 日本, 大阪
        # 但有些是 "亞洲其他"
        if len(loc_str) >= 2:
            return loc_str[:2], loc_str[2:], ''
            
    if '美國' in loc_str: return '美國', loc_str, ''
    if '中國' in loc_str or '大陸' in loc_str: return '中國', loc_str, ''
    if '洲' in loc_str: return loc_str, '', '' # 中美洲, 亞洲其他
    
    # Fallback: 視為國家/地區本身
    return loc_str, '', ''

# ==================== Main ETL Logic ====================

def run_etl():
    print("開始 ETL 流程...")
    
    # 0. 建立 Source Connection (Raw Data)
    SOURCE_DB = 'rawdata'
    # 假設 db_config 來自 parent 或 current
    conn_str_source = f'mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:3306/{SOURCE_DB}'
    source_engine = create_engine(conn_str_source)
    
    print(f"從資料庫 {SOURCE_DB} 讀取原始資料...")
    try:
        # 只選取需要的欄位或是全拿 (全拿比較保險，反正欄位多)
        # 注意：DB中的欄位名稱可能跟 CSV Header 略有不同，需確認 (通常是一樣的，因為 CSV 是匯出的)
        query = "SELECT * FROM 104rawdata" 
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
    
    # Source ID (假設都來自 104 = 1)
    source_id_104 = 1 

    print("開始逐筆寫入資料庫...")
    count = 0
    for _, row in df.iterrows():
        try:
            # --- Dimensions ---
            
            # Company
            comp_name = str(row.get('company', 'Unknown'))
            comp_id = get_or_create_dim(session, DimCompany, {'name': comp_name}, 
                                      defaults={'industry': row.get('industry', '')}, 
                                      cache=cache_company)
            
            # Location
            loc_full = str(row.get('location', 'Unknown'))
            country, city, dist = parse_location(loc_full)
            
            loc_id = get_or_create_dim(session, DimLocation, {'full_address': loc_full}, 
                                     defaults={'country': country, 'city': city, 'district': dist}, 
                                     cache=cache_location)
            
            # --- Fact Job Postings ---
            
            s_min, s_max, s_type = parse_salary(row.get('salary', ''))
            
            # 轉換日期
            post_date_val = None
            try:
                # 假設 raw data 格式是 '2024-12-14'
                d_str = str(row.get('update_date_clean', '')).split(' ')[0] # 移除可能的誤導字元
                post_date_val = datetime.strptime(d_str, '%Y-%m-%d').date()
            except:
                post_date_val = datetime.today().date() # Fallback

            fact = FactJobPosting(
                job_id = str(row['job_id']),
                company_id = comp_id,
                location_id = loc_id,
                source_id = source_id_104,
                job_title = row.get('job_title', ''),
                salary_min = s_min,
                salary_max = s_max,
                salary_type = s_type,
                experience_req = str(row.get('experience', '')),
                education_req = str(row.get('education', '')), # educat... in header check?
                post_date = post_date_val,
                # New Columns
                job_url = str(row.get('link', f'https://www.104.com.tw/job/{row["job_id"]}')),
                isManager = (str(row.get('management_responsibility', '')) != 'nan' and str(row.get('management_responsibility', '')) != '不需負擔管理責任'),
                work_shift = str(row.get('work_shift', '')),
                remote_work = str(row.get('remote_work', '')),
                bt_exp = str(row.get('BT_EXP', '')),
                language = str(row.get('languages', '')), 
                job_description = str(row.get('job_description', '')),
                other_conditions = str(row.get('other_conditions', ''))
            )
            session.add(fact)
            session.flush() # 為了取得 posting_id
            
            # --- Bridge Tables ---
            
            # Categories (Split by comma or ideographic comma)
            cats_raw = str(row.get('job_categories', ''))
            cats = re.split(r'[,、]', cats_raw)
            for c_name in cats:
                c_name = c_name.strip()
                if not c_name: continue
                c_id = get_or_create_dim(session, DimCategory, {'category_name': c_name}, cache=cache_category)
                session.add(BridgeJobCategory(posting_id=fact.posting_id, category_id=c_id))
            
            # Skills (Tools + Work Skills)
            # 假設 user 有 tools 和 work_skills 欄位，或合併
            # 這裡示範 tools
            tools_raw = str(row.get('tools', '')) # 確保 header 正確
            tools = re.split(r'[,、]', tools_raw)
            for t_name in tools:
                t_name = t_name.strip()
                if not t_name: continue
                s_id = get_or_create_dim(session, DimSkill, {'skill_name': t_name}, 
                                       defaults={'type': 'tool'}, 
                                       cache=cache_skill)
                session.add(BridgeJobSkill(posting_id=fact.posting_id, skill_id=s_id, types='tool'))
            
            # Work Skills
            skills_raw = str(row.get('work_skills', '')) 
            skills = re.split(r'[,、]', skills_raw)
            for s_name in skills:
                s_name = s_name.strip()
                if not s_name: continue
                s_id = get_or_create_dim(session, DimSkill, {'skill_name': s_name}, 
                                       defaults={'type': 'work_skill'}, 
                                       cache=cache_skill)
                session.add(BridgeJobSkill(posting_id=fact.posting_id, skill_id=s_id, types='work_skill'))
            
            # Application Tags / Benefits
            # e.g. "年終獎金, 節日獎金/禮品, 津貼/補助"
            tags_raw = str(row.get('tags', '')) 
            tags = re.split(r'[,、]', tags_raw)
            for tag_name in tags:
                tag_name = tag_name.strip()
                if not tag_name: continue
                # 如果是 "津貼/補助" 這種，可以切更細或保持原樣，這裡保持原樣
                b_id = get_or_create_dim(session, DimBenefit, {'benefit_name': tag_name}, 
                                       cache=cache_benefit)
                session.add(BridgeJobBenefit(posting_id=fact.posting_id, benefit_id=b_id))

            count += 1
            if count % 100 == 0:
                session.commit()
                print(f"已處理 {count} 筆...")
                
        except Exception as e:
            print(f"Error processing row {count}: {e}")
            session.rollback()
            continue

    session.commit()
    print(f"全部完成！共匯入 {count} 筆職缺與相關維度資料。")

if __name__ == "__main__":
    run_etl()
