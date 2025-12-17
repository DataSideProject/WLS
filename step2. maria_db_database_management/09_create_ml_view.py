import sys
import os
from sqlalchemy import create_engine, text
import pandas as pd

# Path setup to import db_config
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

try:
    from db_config import DB_HOST, DB_USER, DB_PASSWORD
except ImportError:
    print("Error: Could not find db_config.py")
    exit(1)

DB_NAME = 'job_data_warehouse'
CONNECTION_STRING = f'mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:3306/{DB_NAME}'

def create_ml_view():
    engine = create_engine(CONNECTION_STRING)
    print(f"Connecting to {DB_NAME}...")

    # SQL definition for the view
    create_view_sql = """
    CREATE OR REPLACE VIEW view_ml_dataset AS
    SELECT 
        sub.posting_id,
        sub.job_id,
        sub.job_url,
        sub.job_title,
        IFNULL(s.source_name, 'Unknown') AS source,
        IFNULL(c.name, 'Unknown') AS company,
        c.industry,
        l.country,
        l.city,
        l.district,
        sub.salary_min,
        sub.salary_max,
        sub.salary_type,
        sub.experience_req,
        sub.education_req,
        sub.post_date,
        sub.isManager,
        sub.work_shift,
        sub.remote_work,
        -- Combined text for NLP
        CONCAT(
            IFNULL(sub.job_description, ''), 
            '\n', 
            IFNULL(sub.other_conditions, '')
        ) AS full_description
    FROM (
        SELECT *,
               ROW_NUMBER() OVER (PARTITION BY job_url ORDER BY post_date DESC, posting_id DESC) as rn
        FROM fact_job_postings
        WHERE job_url IS NOT NULL AND job_url != ''
    ) sub
    LEFT JOIN dim_companies c ON sub.company_id = c.company_id
    LEFT JOIN dim_sources s ON sub.source_id = s.source_id
    LEFT JOIN dim_locations l ON sub.location_id = l.location_id
    WHERE sub.rn = 1;
    """

    try:
        with engine.connect() as conn:
            print("Executing CREATE VIEW statement...")
            conn.execute(text(create_view_sql))
            print("View 'view_ml_dataset' created successfully.")
            
            # Verify the view
            print("\nVerifying View Content (Top 3 rows):")
            df = pd.read_sql("SELECT * FROM view_ml_dataset LIMIT 3", conn)
            print(df.to_string(index=False))
            print("\nverification complete.")
            
    except Exception as e:
        print(f"Error creating view: {e}")

if __name__ == "__main__":
    create_ml_view()
