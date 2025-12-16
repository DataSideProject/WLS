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

def analyze_overseas():
    engine = create_engine(CONNECTION_STRING)
    print(f"Connecting to {DB_NAME}...")
    
    with engine.connect() as conn:
        with open('overseas_report_final.txt', 'w', encoding='utf-8') as f:
            # 1. Get all locations with job counts by Source
            query = """
            SELECT 
                loc.country, 
                loc.city, 
                s.source_name,
                COUNT(f.posting_id) as job_count
            FROM fact_job_postings f
            JOIN dim_locations loc ON f.location_id = loc.location_id
            JOIN dim_sources s ON f.source_id = s.source_id
            GROUP BY loc.country, loc.city, s.source_name
            ORDER BY job_count DESC
            """
            
            df = pd.read_sql(query, conn)
            
            f.write("=== Top Locations by Source ===\n")
            # Write row by row
            for idx, row in df.head(50).iterrows():
                f.write(f"{row['source_name']}: {row['country']} - {row['city']} ({row['job_count']})\n")
            
            f.write("\n=== Distinct Countries in 104 ===\n")
            countries_104 = sorted([str(x) for x in df[df['source_name'] == '104']['country'].unique()])
            for c in countries_104:
                f.write(f"- {c}\n")
            
            f.write("\n=== Distinct Countries in CakeResume ===\n")
            countries_cake = sorted([str(x) for x in df[df['source_name'] == 'CakeResume']['country'].unique()])
            for c in countries_cake:
                f.write(f"- {c}\n")

            # Check for potential overlaps
            f.write("\n=== Potential Mixed Language Countries (Jobs Count) ===\n")
            summary = df.groupby(['country', 'source_name'])['job_count'].sum().unstack(fill_value=0)
            summary['total'] = summary.sum(axis=1)
            summary = summary.sort_values('total', ascending=False)
            
            # Write basic table
            f.write(f"{'Country':<30} | {'104':<5} | {'Cake':<5} | {'Total':<5}\n")
            f.write("-" * 60 + "\n")
            for country, row in summary.iterrows():
                if country is None: continue
                country_str = str(country)
                c104 = int(row.get('104', 0))
                ccake = int(row.get('CakeResume', 0))
                ctotal = int(row.get('total', 0))
                f.write(f"{country_str:<30} | {c104:<5} | {ccake:<5} | {ctotal:<5}\n")

    print("Report written to overseas_report_final.txt")


if __name__ == "__main__":
    try:
        analyze_overseas()
    except Exception as e:
        print(f"Error: {e}")
