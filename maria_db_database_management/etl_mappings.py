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
        'table_name': 'job_details', # 請修改為實際 Table 名稱
        'source_id': 2,
        
        'columns': {
            'job_id': 'id',          
            'company': 'company',    
            'industry': None,  
            'location': 'location',   
            'job_title': 'job_title',         
            'salary': 'salary',     
            'experience': 'experience',      
            'education': None,       
            'link': 'url',
            'management_responsibility': 'management', 
            'work_shift': None,
            'remote_work': 'remote',
            'bt_exp': None,
            'languages': None,
            'job_description': 'content',
            'other_conditions': 'original_tags',
            'update_date': 'created_at',
            
            'job_categories': 'category',
            'tools': 'analyzed_skills',
            'work_skills': None,
            'tags': None
        }
    }
}
