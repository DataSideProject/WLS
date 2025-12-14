import pandas as pd
from sqlalchemy import create_engine, text
import re
import datetime
import uuid
from typing import Optional, Tuple
import json
import os
import traceback

# Import credentials
try:
    from db_config import DB_HOST, DB_USER, DB_PASSWORD, DB_NAME
except ImportError:
    print("Error: db_config.py not found.")
    exit(1)

# ==================== Configuration ====================
DB_URL_TEMPLATE = f'mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:3306/{DB_NAME}'
TABLE_NAME = 'jobs_unified'

# ==================== Helper Functions ====================

taxonomy = {}
try:
    if os.path.exists('skill_taxonomy.json'):
        with open('skill_taxonomy.json', 'r', encoding='utf-8') as f:
            taxonomy = json.load(f)
        print(f"Loaded skill taxonomy with {len(taxonomy)} categories.")
    else:
        print("Warning: skill_taxonomy.json not found.")
except Exception as e:
    print(f"Warning: Could not load skill_taxonomy.json: {e}")

def extract_skills_from_text(text: str) -> list:
    """Scan text for keywords defined in taxonomy."""
    if not text or pd.isna(text): return []
    
    found_skills = set()
    text_lower = str(text).lower()
    
    for category, skills in taxonomy.items():
        for skill in skills:
            skill_lower = skill.lower()
            if len(skill_lower) < 2:
                pattern = r'(?:\b|[^a-zA-Z])' + re.escape(skill_lower) + r'(?:\b|[^a-zA-Z])'
                if re.search(pattern, text_lower):
                    found_skills.add(skill)
            else:
                if skill_lower in text_lower:
                    found_skills.add(skill)
                    
    return list(found_skills)



def parse_education_from_text(text: str) -> str:
    if pd.isna(text): return "Unknown"
    text = str(text).lower()
    if any(x in text for x in ['博士', 'phd', 'doctorate']): return "Doctorate"
    if any(x in text for x in ['碩士', 'master', 'graduate']): return "Master"
    if any(x in text for x in ['大學', 'bachelor', 'university', 'degree']): return "Bachelor"
    if any(x in text for x in ['專科', 'associate']): return "Associate"
    if any(x in text for x in ['高中', '高職', 'high school']): return "High School"
    return "Unknown"

def standardize_location(loc: str) -> str:
    if pd.isna(loc): return "Unknown"
    loc = str(loc).strip()
    norm_loc = loc.replace('臺', '台')
    tw_cities = [
        "台北市", "新北市", "桃園市", "台中市", "台南市", "高雄市",
        "基隆市", "新竹市", "嘉義市", 
        "新竹縣", "苗栗縣", "彰化縣", "南投縣", "雲林縣", "嘉義縣", "屏東縣", "宜蘭縣", "花蓮縣", "台東縣", "澎湖縣", "金門縣", "連江縣"
    ]
    for city in tw_cities:
        if city in norm_loc: return city
    country_map = {
        'vietnam': '越南', 'hanoi': '越南', 'ho chi minh': '越南',
        'philippines': '菲律賓', 'manila': '菲律賓',
        'thailand': '泰國', 'bangkok': '泰國',
        'indonesia': '印尼', 'jakarta': '印尼',
        'malaysia': '馬來西亞', 'kuala lumpur': '馬來西亞',
        'singapore': '新加坡',
        'japan': '日本', 'tokyo': '日本', 'osaka': '日本',
        'korea': '韓國', 'seoul': '韓國',
        'china': '中國', 'shanghai': '中國', 'beijing': '中國', 'shenzhen': '中國',
        'hong kong': '香港',
        'macau': '澳門',
        'usa': '美國', 'united states': '美國', 'america': '美國',
        'uk': '英國', 'united kingdom': '英國', 'london': '英國',
        'germany': '德國', 'berlin': '德國',
        'france': '法國', 'paris': '法國',
        'australia': '澳洲', 'sydney': '澳洲', 'melbourne': '澳洲',
        'canada': '加拿大', 'toronto': '加拿大', 'vancouver': '加拿大',
        'india': '印度', 'switzerland': '瑞士'
    }
    loc_lower = loc.lower()
    for eng_key, ch_val in country_map.items():
        if eng_key in loc_lower: return ch_val
    if 'taiwan' in loc_lower or '台灣' in loc_lower:
        return "台灣地區" 
    return loc 

def upsert_data(df, engine):
    if df.empty: return
    print(f"Upserting {len(df)} rows...")
    records = df.to_dict(orient='records')
    for row in records:
        for k, v in row.items():
            if pd.isna(v): row[k] = None
            elif isinstance(v, pd.Timestamp): row[k] = v.to_pydatetime()

    sql = text(f"""
    INSERT INTO {TABLE_NAME} (
        uuid, job_title, company, industry, category, location, salary,
        education, experience, management_responsibility, remote_work,
        description, skills, url, source, original_id, updated_at
    ) VALUES (
        :uuid, :job_title, :company, :industry, :category, :location, :salary,
        :education, :experience, :management_responsibility, :remote_work,
        :description, :skills, :url, :source, :original_id, :updated_at
    )
    ON DUPLICATE KEY UPDATE
        salary = VALUES(salary),
        education = VALUES(education),
        experience = VALUES(experience),
        management_responsibility = VALUES(management_responsibility),
        remote_work = VALUES(remote_work),
        description = VALUES(description),
        skills = VALUES(skills),
        url = VALUES(url),
        source = VALUES(source),
        updated_at = VALUES(updated_at);
    """)

    BATCH_SIZE = 1000
    with engine.begin() as conn:
        for i in range(0, len(records), BATCH_SIZE):
            batch = records[i : i + BATCH_SIZE]
            conn.execute(sql, batch)
            print(f"  Processed {i + len(batch)} / {len(records)}", flush=True)
    print("Upsert complete.", flush=True)

# ==================== Main ETL ====================

def run_etl():
    engine = create_engine(DB_URL_TEMPLATE)
    print(f"--- DB: {DB_NAME} ---")
    
    # 1. Create Table (Rebuild)
    print(f"Creating table {TABLE_NAME} (DROP & CREATE)...")
    with engine.connect() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS {TABLE_NAME}"))
        conn.execute(text(f"""
        CREATE TABLE {TABLE_NAME} (
            uuid VARCHAR(64) PRIMARY KEY,
            job_title VARCHAR(255),
            company VARCHAR(100),
            industry VARCHAR(100),
            category VARCHAR(255),
            location VARCHAR(255),
            salary VARCHAR(255),
            education VARCHAR(100),
            experience VARCHAR(100),
            management_responsibility VARCHAR(255),
            remote_work VARCHAR(255),
            description LONGTEXT,
            skills TEXT,
            url TEXT,
            source VARCHAR(20), 
            original_id VARCHAR(100),
            updated_at DATETIME
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
        """))
        conn.commit()

    # 2. Process 104 Data
    print("Processing 104 data...")
    try:
        df_104 = pd.read_sql("SELECT * FROM 104rawdata", engine)
        records_104 = []
        for _, row in df_104.iterrows():
            raw_salary = row.get('salary')
            edu = str(row.get('education', '')).strip()
            exp = str(row.get('experience', '')).strip()
            mgmt = str(row.get('management_responsibility', '')).strip()
            remote = str(row.get('remote_work', '')).strip()
            desc = str(row.get('job_description', '')) + "\n" + str(row.get('other_conditions', ''))
            skills = row.get('tools', '')
            
            records_104.append({
                'uuid': f"104_{row['job_id']}",
                'job_title': row['job_title'],
                'company': row['company'],
                'industry': row['industry'],
                'category': row.get('job_categories', ''),
                'location': standardize_location(row['location']),
                'salary': raw_salary,
                'education': edu,
                'experience': exp,
                'management_responsibility': mgmt,
                'remote_work': remote,
                'description': desc,
                'skills': skills,
                'url': f"https://www.104.com.tw/job/{row['job_id']}",
                'source': '104',
                'original_id': row['job_id'],
                'updated_at': datetime.datetime.now()
            })
        upsert_data(pd.DataFrame(records_104), engine)
    except Exception as e:
        print(f"Error processing 104 data: {e}")

    # 3. Process Cake Data
    print("Processing CakeResume data...")
    try:
        df_cake = pd.read_sql("SELECT * FROM job_details", engine)
    except Exception as e:
        print(f"Error loading 'job_details': {e}")
        df_cake = pd.DataFrame()

    if not df_cake.empty:
        print(f"Loaded {len(df_cake)} rows from job_details.")
        records_cake = []
        for _, row in df_cake.iterrows():
            raw_salary = row.get('salary')
            edu = parse_education_from_text(row.get('content', ''))
            exp = ""
            if 'experience' in row and pd.notna(row['experience']):
                 exp = str(row['experience']).strip()
                 if exp in ['Entry', 'Senior', 'Management', 'Mid-Senior level', 'Associate', 'Director', 'Executive', '初階', '中高階', '高階', '助理']:
                     exp = ""
            
            mgmt = str(row.get('management', '')).strip() 
            remote = str(row.get('remote', '')).strip()   
            desc = str(row.get('content', '')) + "\n" + str(row.get('original_tags', ''))
            
            # Skills Processing
            existing_skills_str = ""
            if 'analyzed_skills' in row and pd.notna(row['analyzed_skills']):
                existing_skills_str = str(row['analyzed_skills'])
            elif 'original_tags' in row and pd.notna(row['original_tags']):
                existing_skills_str = str(row.get('original_tags', ''))
                
            current_skills = [s.strip() for s in existing_skills_str.split(',') if s.strip()]
            extracted_skills = extract_skills_from_text(desc)
            
            final_skills_map = {}
            for s in current_skills:
                final_skills_map[s.lower()] = s
            for s in extracted_skills:
                final_skills_map[s.lower()] = s
            skills = ",".join(list(final_skills_map.values())) 
            
            # Industry Normalization
            raw_ind = str(row.get('industry', ''))
            industry = raw_ind
            if '軟體' in raw_ind or 'Software' in raw_ind: industry = '電腦軟體服務業'
            elif '半導體' in raw_ind or 'Semiconductor' in raw_ind: industry = '半導體業'
            elif '金融' in raw_ind or 'Finance' in raw_ind or 'Bank' in raw_ind: industry = '金融控股業'
            
            source_id = 'cakeresume'
            records_cake.append({
                'uuid': f"{source_id}_{row.get('id')}",
                'job_title': row['job_title'],
                'company': row['company'],
                'industry': industry, 
                'category': row.get('category', ''),
                'location': standardize_location(row['location']),
                'salary': raw_salary,
                'education': edu,
                'experience': exp,
                'management_responsibility': mgmt,
                'remote_work': remote,
                'description': desc,
                'skills': skills,
                'url': row.get('url', ''),
                'source': source_id,
                'original_id': row.get('id'),
                'updated_at': datetime.datetime.now()
            })
            
        # Deduplicate
        uuids = [r['uuid'] for r in records_cake]
        unique_uuids = set(uuids)
        print(f"Stats: Total Records: {len(records_cake)}, Unique UUIDs: {len(unique_uuids)}")
        
        upsert_data(pd.DataFrame(records_cake), engine)
        
    print("\n--- FINAL VERIFICATION ---")
    with engine.connect() as conn:
        res = conn.execute(text(f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE source='cakeresume'"))
        print(f"Final CakeResume Count in DB: {res.fetchone()[0]}")

if __name__ == "__main__":
    try:
        run_etl()
    except Exception:
        traceback.print_exc()
