from flask import Flask, render_template, jsonify, request
import pandas as pd
import numpy as np
import json
import os
import re
import analysis_utils
from sqlalchemy import create_engine
from ml_data_loader import load_job_data_from_db
import db_config
from collections import Counter

app = Flask(__name__)

# Global variables
df = None
taxonomy = {}

def get_db_engine():
    return create_engine(f'mysql+pymysql://{db_config.DB_USER}:{db_config.DB_PASSWORD}@{db_config.DB_HOST}:3306/{db_config.DB_NAME}')

def prepare_dataframe_for_analysis(df_in):
    """
    Replicates necessary feature engineering for analysis_utils.
    """
    df_out = df_in.copy()
    
    # 1. City for Stratify
    def parse_city(addr):
        if pd.isna(addr): return 'Unknown'
        addr = str(addr)
        if len(addr) >= 3: return addr[:3]
        return addr
    
    # Check if city_for_stratify already exists (ml_data_loader might not create it exactly same)
    if 'city_for_stratify' not in df_out.columns:
        df_out['city_for_stratify'] = df_out['location'].apply(parse_city)

    # 2. Categories (One-Hot for Boxplot)
    all_cats = []
    if 'job_categories' in df_out.columns:
        for cats in df_out['job_categories'].dropna():
            all_cats.extend([c.strip() for c in str(cats).split(',') if c.strip()])
    
    # Use top 20 like logic
    top_cats = [c[0] for c in Counter(all_cats).most_common(20)]
    for cat in top_cats:
        df_out[f'cat_{cat}'] = df_out['job_categories'].astype(str).str.contains(cat, regex=False, na=False).astype(int)

    # 3. Calculate Salary Averages
    # Actual Average
    df_out['salary_avg'] = (pd.to_numeric(df_out['salary_min'], errors='coerce') + pd.to_numeric(df_out['salary_max'], errors='coerce')) / 2
    
    # Predicted Average (if available)
    if 'predicted_salary_min' in df_out.columns:
        df_out['pred_min'] = pd.to_numeric(df_out['predicted_salary_min'], errors='coerce')
        df_out['pred_max'] = pd.to_numeric(df_out['predicted_salary_max'], errors='coerce')
        df_out['pred_avg'] = (df_out['pred_min'] + df_out['pred_max']) / 2
        
        # KEY FIX: If Actual Salary is 0 or NaN (Negotiable), use Predicted Salary
        mask_use_pred = (df_out['salary_avg'].fillna(0) == 0) & (df_out['pred_avg'] > 0)
        df_out.loc[mask_use_pred, 'salary_avg'] = df_out.loc[mask_use_pred, 'pred_avg']
        
    return df_out

def load_data():
    global df, taxonomy
    try:
        print("Loading Job Data from DB...")
        # Load core data using the shared loader
        # Ensure we are in the right directory or path is handled
        # ml_data_loader uses db_config from current dir (which we provided)
        job_df = load_job_data_from_db()
        
        if job_df.empty:
             print("Warning: No job data loaded from DB.")
             return

        print("Loading Predictions from DB...")
        engine = get_db_engine()
        from sqlalchemy import text
        with engine.connect() as conn:
            # Get latest predictions (naive query, assuming one prediction per job or cleaner table)
            # Or use logic to filter latest if needed. 
            # Given we are in history mode, we should fetch logical latest for each posting.
            # But for simplicity and speed, let's fetch all and dedupe by posting_id keeping last
            pred_query = "SELECT posting_id, pred_salary_min, pred_salary_max, prediction_time FROM fact_job_predictions ORDER BY prediction_time ASC"
            pred_df = pd.read_sql(text(pred_query), conn)
        
        # Deduplicate predictions to keep only the LATEST for each posting
        if not pred_df.empty:
            # posting_id could be int or str, normalize to logic in loader
            # ml_data_loader returns posting_id usually as int (from DB BigInt).
            pred_df.drop_duplicates(subset=['posting_id'], keep='last', inplace=True)
            
            # Rename for consistency
            pred_df.rename(columns={
                'pred_salary_min': 'predicted_salary_min', 
                'pred_salary_max': 'predicted_salary_max'
            }, inplace=True)
            
            # Type Safety for Merge
            job_df['posting_id'] = job_df['posting_id'].astype(str)
            pred_df['posting_id'] = pred_df['posting_id'].astype(str)
            
            # Merge
            job_df = pd.merge(job_df, pred_df, on='posting_id', how='left')
            print(f"Merged with predictions. Total rows: {len(job_df)}")
            
            # DEBUG
            missing_preds = job_df['predicted_salary_min'].isna().sum()
            print(f"DEBUG: Jobs with missing predictions: {missing_preds}/{len(job_df)}")
        else:
            print("No predictions found in DB.")

        # Preprocessing
        print("Preprocessing dataframe...")
        df = prepare_dataframe_for_analysis(job_df)
        
        # Ensure 'job_id' is present (View has it as 'job_id', loader keeps it)
        # Type cleanup
        if 'job_id' in df.columns:
            df['job_id'] = df['job_id'].astype(str)
        
        # Load taxonomy
        base_dir = os.path.dirname(os.path.abspath(__file__))
        taxonomy_path = os.path.join(base_dir, 'skill_taxonomy.json')
        if os.path.exists(taxonomy_path):
            with open(taxonomy_path, 'r', encoding='utf-8') as f:
                taxonomy = json.load(f)
            print(f"Loaded taxonomy with {len(taxonomy)} categories")
        else:
            print(f"Warning: skill_taxonomy.json not found at {taxonomy_path}")
            taxonomy = {}
        
        print("Data Load Complete!")
        
    except Exception as e:
        print(f"Error loading data: {str(e)}")
        import traceback
        traceback.print_exc()
        df = None

# ... (Helper functions categorize_skills remain mostly same) ...
def categorize_skills(tools_str):
    if not tools_str or str(tools_str).strip() == '--':
        return {}
    raw_skills = [t.strip() for t in str(tools_str).split(',') if t.strip()]
    categorized = {}
    skill_to_cat = {}
    for cat, skills in taxonomy.items():
        for skill in skills:
            skill_to_cat[skill.lower()] = cat
    categorized['Uncategorized'] = []
    
    for raw in raw_skills:
        found = False
        raw_lower = raw.lower()
        if raw_lower in skill_to_cat:
            cat = skill_to_cat[raw_lower]
            if cat not in categorized: categorized[cat] = []
            categorized[cat].append(raw)
            found = True
        else:
            for skill_key, cat in skill_to_cat.items():
                if skill_key in raw_lower or raw_lower in skill_key:
                    if cat not in categorized: categorized[cat] = []
                    categorized[cat].append(raw)
                    found = True
                    break
        if not found:
            categorized['Uncategorized'].append(raw)
    if not categorized['Uncategorized']: del categorized['Uncategorized']
    return categorized

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/jobs')
def get_jobs():
    try:
        if df is None: return jsonify([])
        
        # Filters
        location = request.args.get('location')
        salary_min = request.args.get('salary_min', type=float)
        salary_max = request.args.get('salary_max', type=float)
        category = request.args.get('category')
        is_manager = request.args.get('is_manager', type=int)
        remote_work = request.args.get('remote_work')
        search = request.args.get('search')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        
        filtered_df = df.copy()
        
        if location and location != 'All':
            filtered_df = filtered_df[filtered_df['location'].str.contains(location, na=False)]
        if salary_min is not None:
            filtered_df = filtered_df[filtered_df['salary_min'] >= salary_min]
        if salary_max is not None:
            filtered_df = filtered_df[filtered_df['salary_max'] <= salary_max]
        if category and category != 'All':
            cat_col = f'cat_{category}'
            if cat_col in filtered_df.columns:
                filtered_df = filtered_df[filtered_df[cat_col] == 1]
        
        if is_manager == 1:
            if 'isManager' in filtered_df.columns: # Map isManager from DB
                 filtered_df = filtered_df[filtered_df['isManager'] == 1]
            elif 'is_manager' in filtered_df.columns:
                 filtered_df = filtered_df[filtered_df['is_manager'] == 1]

        if remote_work and remote_work != 'All':
             if 'remote_work' in filtered_df.columns:
                if remote_work == '部分遠端':
                    filtered_df = filtered_df[filtered_df['remote_work'].str.contains('部分遠端', na=False)]
                elif remote_work == '完全遠端':
                    filtered_df = filtered_df[filtered_df['remote_work'].str.contains('完全遠端', na=False)]
        
        if search:
            search_term = search.lower()
            filtered_df = filtered_df[
                filtered_df['job_title'].str.lower().str.contains(search_term, na=False) | 
                filtered_df['company'].astype(str).str.lower().str.contains(search_term, na=False) # 'company' column name
            ]

        # Pagination
        total_count = len(filtered_df)
        total_pages = (total_count + per_page - 1) // per_page
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        
        page_df = filtered_df.iloc[start_idx:end_idx]
        
        # Columns to return
        # Adjust column names based on DB schema/loader
        # loader: 'company_name'? View has 'company_name'. ml_loader DOES NOT rename 'company_name' -> 'company'.
        # View has `company_name` as `company`? No, let's check view definition in 09.
        # 09 view: SELECT c.name as company_name ...
        # ml_loader doesn't rename it.
        # So we should expect 'company_name'. Let's alias it for frontend consistency or fix frontend.
        # Frontend expects 'company'. Let's rename in prepare or here.
        
        cols_map = {
            'job_id': 'job_id',
            'job_title': 'job_title',
            'company': 'company', # Map DB 'company' to frontend 'company'
            'location': 'location',
            'salary_min': 'salary_min',
            'salary_max': 'salary_max',
            'salary_note': 'salary_note',
            'predicted_salary_min': 'pred_min',
            'predicted_salary_max': 'pred_max',
            'isManager': 'is_manager',
            'remote_work': 'remote_work',
            'source': 'source',
            'job_url': 'link'
        }
        
        final_records = []
        for _, row in page_df.iterrows():
            rec = {}
            for db_col, fe_col in cols_map.items():
                if db_col in row:
                    val = row[db_col]
                    if pd.isna(val): val = None
                    rec[fe_col] = val
                else:
                    rec[fe_col] = None
            final_records.append(rec)

        return jsonify({
            'jobs': final_records,
            'total_count': total_count,
            'page': page,
            'per_page': per_page,
            'total_pages': total_pages
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/job/<job_id>')
def get_job_details(job_id):
    if df is None: return jsonify({'error': 'Data not loaded'}), 500
    job_id_str = str(job_id)
    job = df[df['job_id'] == job_id_str]
    if job.empty: return jsonify({'error': 'Job not found'}), 404
    
    row = job.iloc[0]
    # Construct detail obj
    # Similar mapping needed
    job_data = row.to_dict()
    # Ensure keys match frontend expectation
    job_data['company'] = job_data.get('company', '')
    job_data['link'] = job_data.get('job_url', '#')
    job_data['pred_min'] = job_data.get('predicted_salary_min')
    job_data['pred_max'] = job_data.get('predicted_salary_max')
    
    # Handle NaNs
    for k, v in job_data.items():
        if pd.isna(v): job_data[k] = None
        
    # Tree
    tools = job_data.get('tools', '')
    categorized_skills = categorize_skills(tools)
    tree_data = {
        "name": job_data['job_title'],
        "symbolSize": 20,
        "itemStyle": {"color": "#ff0000"},
        "children": []
    }
    for cat, skills in categorized_skills.items():
        cat_node = {"name": cat, "itemStyle": {"color": "#00ff00"}, "children": []}
        for skill in skills:
            cat_node["children"].append({"name": skill, "itemStyle": {"color": "#0000ff"}, "value": 1})
        tree_data["children"].append(cat_node)
        
    return jsonify({'job': job_data, 'tree': tree_data})

@app.route('/api/filters/options')
def get_filter_options():
    if df is None: return jsonify({})
    
    locations = sorted(df['location'].dropna().unique().tolist())
    salary_range = {
        'min': int(df['salary_min'].min()) if not df['salary_min'].empty else 0,
        'max': int(df['salary_max'].max()) if not df['salary_max'].empty else 0,
        'median': int(df['salary_avg'].median()) if not df['salary_avg'].empty else 0
    }
    remote_options = ['All', '部分遠端', '完全遠端']
    source_options = ['All']
    if 'source' in df.columns:
        source_options.extend(sorted(df['source'].astype(str).unique().tolist()))
        
    manager_count = 0
    if 'isManager' in df.columns:
        manager_count = int(df['isManager'].fillna(0).sum())
    
    job_categories = [col.replace('cat_', '') for col in df.columns if col.startswith('cat_')]
    
    return jsonify({
        'locations': locations,
        'categories': job_categories,
        'salary_range': salary_range,
        'remote_options': remote_options,
        'source_options': source_options,
        'manager_count': manager_count
    })

@app.route('/api/analysis/stats')
def get_analysis_stats():
    if df is None: return jsonify({})
    filters = {}
    category = request.args.get('category')
    city = request.args.get('city')
    if category and category != 'All': filters['category'] = category
    if city and city != 'All': filters['city'] = city
    is_manager = request.args.get('is_manager')
    if is_manager in ['true', '1']: filters['is_manager'] = True
    remote = request.args.get('remote')
    if remote and remote != 'All': filters['remote'] = remote
    source = request.args.get('source')
    if source and source != 'All': filters['source'] = source
    
    stats = analysis_utils.get_dashboard_stats(df, filters)
    return jsonify(stats)

# Load data on import/start
load_data()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
