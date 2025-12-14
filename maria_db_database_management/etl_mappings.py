# ETL Column Mappings Configuration
# 用於對應不同資料來源 (Source) 的欄位名稱到統一的標準欄位 (Target)

# Target Field: 程式邏輯中使用的標準名稱
# Source Field: 資料庫原始表 (Raw Data) 中的欄位名稱

ETL_MAPPINGS = {
    '104': {
        # Source Table Name in 'rawdata' DB
        'table_name': '104rawdata', 
        'source_id': 1,
        
        # Column Mappings (Target -> Source)
        'columns': {
            'job_id': 'job_id',
            'company': 'company',
            'industry': 'industry',
            'location': 'location',
            'job_title': 'job_title',
            'salary': 'salary',
            'experience': 'experience',
            'education': 'education',
            'link': 'link',
            'management_responsibility': 'management_responsibility',
            'work_shift': 'work_shift',
            'remote_work': 'remote_work',
            'bt_exp': 'BT_EXP',
            'languages': 'languages',
            'job_description': 'job_description',
            'other_conditions': 'other_conditions',
            'update_date': 'update_date_clean',
            
            # Bridge Tables
            'job_categories': 'job_categories',
            'tools': 'tools',
            'work_skills': 'work_skills',
            'tags': 'tags'
        }
    },
    
    # 範例：CakeResume (請依照實際欄位名稱修改右側字串)
    'cakeresume': {
        'table_name': 'cake_raw_table_name', # 請修改為實際 Table 名稱
        'source_id': 2,
        
        'columns': {
            'job_id': 'job_id',           # 假設
            'company': 'company_name',    # 假設
            'industry': 'industry_type',  # 假設
            'location': 'location_str',   # 假設
            'job_title': 'title',         # 假設
            'salary': 'salary_range',     # 假設
            'experience': 'exp_req',      # 假設
            'education': 'edu_req',       # 假設
            'link': 'url',
            'management_responsibility': 'is_manager', # 需確認邏輯
            'work_shift': 'shift',
            'remote_work': 'remote',
            'bt_exp': 'business_trip',
            'languages': 'lang',
            'job_description': 'desc',
            'other_conditions': 'requirements',
            'update_date': 'date',
            
            'job_categories': 'category',
            'tools': 'tech_stack',
            'work_skills': 'skills',
            'tags': 'benefits'
        }
    }
}
