import sys
import os
from sqlalchemy import create_engine, text
import pandas as pd

# Path setup
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

def verify_columns():
    engine = create_engine(CONNECTION_STRING)
    print(f"Connecting to {DB_NAME}...")
    
    with engine.connect() as conn:
        with open('column_report.txt', 'w', encoding='utf-8') as f:
            
            # --- Helper to write section ---
            def write_section(title):
                f.write(f"\n{'='*30}\n{title}\n{'='*30}\n")
                print(f"Analyzing {title}...")

            # 1. Remote Work
            write_section("1. Remote Work Distribution")
            query = """
            SELECT 
                COALESCE(f.remote_work, 'NULL') as val, 
                s.source_name,
                COUNT(*) as count
            FROM fact_job_postings f
            JOIN dim_sources s ON f.source_id = s.source_id
            GROUP BY f.remote_work, s.source_name
            ORDER BY count DESC
            """
            df = pd.read_sql(query, conn)
            for idx, row in df.iterrows():
                f.write(f"[{row['source_name']}] {row['val']}: {row['count']}\n")

            # 2. Management Responsibility
            write_section("2. Management Responsibility (isManager)")
            query = """
            SELECT 
                f.isManager, 
                s.source_name,
                COUNT(*) as count
            FROM fact_job_postings f
            JOIN dim_sources s ON f.source_id = s.source_id
            GROUP BY f.isManager, s.source_name
            ORDER BY s.source_name, count DESC
            """
            df = pd.read_sql(query, conn)
            for idx, row in df.iterrows():
                f.write(f"[{row['source_name']}] isManager={row['isManager']}: {row['count']}\n")

            # 3. Experience Requirements
            write_section("3. Experience Requirements (Top 30)")
            query = """
            SELECT 
                COALESCE(f.experience_req, 'NULL') as val, 
                s.source_name,
                COUNT(*) as count
            FROM fact_job_postings f
            JOIN dim_sources s ON f.source_id = s.source_id
            GROUP BY f.experience_req, s.source_name
            ORDER BY count DESC
            LIMIT 30
            """
            df = pd.read_sql(query, conn)
            for idx, row in df.iterrows():
                f.write(f"[{row['source_name']}] {row['val']}: {row['count']}\n")

            # 4. Salary Type Distribution
            write_section("4. Salary Type Distribution")
            query = """
            SELECT 
                COALESCE(f.salary_type, 'NULL') as val, 
                s.source_name,
                COUNT(*) as count
            FROM fact_job_postings f
            JOIN dim_sources s ON f.source_id = s.source_id
            GROUP BY f.salary_type, s.source_name
            ORDER BY s.source_name, count DESC
            """
            df = pd.read_sql(query, conn)
            for idx, row in df.iterrows():
                f.write(f"[{row['source_name']}] {row['val']}: {row['count']}\n")

            # 5. Salary Statistics (Min Salary) by Type & Source
            write_section("5. Salary Statistics (Min Salary for Non-Null records)")
            query = """
            SELECT 
                s.source_name,
                f.salary_type,
                COUNT(*) as count,
                MIN(f.salary_min) as min_val,
                MAX(f.salary_min) as max_val,
                AVG(f.salary_min) as avg_val
            FROM fact_job_postings f
            JOIN dim_sources s ON f.source_id = s.source_id
            WHERE f.salary_min IS NOT NULL AND f.salary_min > 0
            GROUP BY s.source_name, f.salary_type
            ORDER BY s.source_name, f.salary_type
            """
            df = pd.read_sql(query, conn)
            f.write(f"{'Source':<12} | {'Type':<15} | {'Count':<6} | {'Min':<8} | {'Max':<10} | {'Avg':<10}\n")
            f.write("-" * 75 + "\n")
            
            for idx, row in df.iterrows():
                avg_display = f"{row['avg_val']:.0f}" if row['avg_val'] else 'N/A'
                f.write(f"{row['source_name']:<12} | {row['salary_type']:<15} | {row['count']:<6} | {row['min_val']:<8} | {row['max_val']:<10} | {avg_display:<10}\n")

    print("Column report generated in 'column_report.txt'")

if __name__ == "__main__":
    verify_columns()
