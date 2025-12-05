from flask import Flask, render_template, jsonify, request
import pandas as pd
import numpy as np
import json
import os
import re
import analysis_utils

app = Flask(__name__)

# Load Data
DATA_PATH = r'job_data_final_with_predictions.csv'
TAXONOMY_PATH = r'skill_taxonomy.json'

# Global variables
df = None
taxonomy = {}




def load_data():
    global df, taxonomy
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        data_path = os.path.join(base_dir, 'job_data_final_with_predictions.csv')
        fallback_path = os.path.join(base_dir, 'job_data_with_full_salary_v7_segmented.csv')
        
        if os.path.exists(data_path):
            print(f"Loading primary data from {data_path}...")
            df = pd.read_csv(data_path)
        elif os.path.exists(fallback_path):
            print(f"Loading fallback data from {fallback_path}...")
            df = pd.read_csv(fallback_path)
        else:
            print(f"Error: No data file found in {base_dir}")
            df = None  # 顯式設定 None
            return
        
        print(f"Loaded {len(df)} rows successfully.")
        
        # Convert job_id to string for consistent matching
        if 'job_id' in df.columns:
            df['job_id'] = df['job_id'].astype(str)
        
        # Load taxonomy
        taxonomy_path = os.path.join(base_dir, 'skill_taxonomy.json')
        if os.path.exists(taxonomy_path):
            with open(taxonomy_path, 'r', encoding='utf-8') as f:
                taxonomy = json.load(f)
            print(f"Loaded taxonomy with {len(taxonomy)} categories")
        else:
            print(f"Warning: skill_taxonomy.json not found at {taxonomy_path}")
            taxonomy = {}
        
    except Exception as e:
        print(f"Error loading data: {str(e)}")
        df = None


def categorize_skills(tools_str):
    if not tools_str or str(tools_str).strip() == '--':
        return {}
    
    raw_skills = [t.strip() for t in str(tools_str).split(',') if t.strip()]
    categorized = {}
    
    # Reverse taxonomy for easier lookup
    skill_to_cat = {}
    for cat, skills in taxonomy.items():
        for skill in skills:
            skill_to_cat[skill.lower()] = cat
            
    # Default category
    categorized['Uncategorized'] = []
    
    for raw in raw_skills:
        found = False
        raw_lower = raw.lower()
        
        # Exact match check
        if raw_lower in skill_to_cat:
            cat = skill_to_cat[raw_lower]
            if cat not in categorized:
                categorized[cat] = []
            categorized[cat].append(raw)
            found = True
        else:
            # Partial match check (e.g. "Python 3" matches "Python")
            for skill_key, cat in skill_to_cat.items():
                if skill_key in raw_lower or raw_lower in skill_key:
                    if cat not in categorized:
                        categorized[cat] = []
                    categorized[cat].append(raw)
                    found = True
                    break
        
        if not found:
            categorized['Uncategorized'].append(raw)
            
    # Remove empty Uncategorized
    if not categorized['Uncategorized']:
        del categorized['Uncategorized']
        
    return categorized

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/jobs')
def get_jobs():
    if df is None:
        return jsonify([])
    
    # Get filter parameters
    location = request.args.get('location')
    salary_min = request.args.get('salary_min', type=float)
    salary_max = request.args.get('salary_max', type=float)
    category = request.args.get('category')
    is_manager = request.args.get('is_manager', type=int)
    remote_work = request.args.get('remote_work')
    search = request.args.get('search')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    
    # Start with full dataset
    filtered_df = df.copy()
    
    # Apply filters
    if location and location != 'All':
        filtered_df = filtered_df[filtered_df['location'].str.contains(location, na=False)]
    
    if salary_min is not None:
        filtered_df = filtered_df[filtered_df['salary_min'] >= salary_min]
    
    if salary_max is not None:
        filtered_df = filtered_df[filtered_df['salary_max'] <= salary_max]
    
    if category and category != 'All':
        # Check if category column exists
        cat_col = f'cat_{category}'
        if cat_col in filtered_df.columns:
            filtered_df = filtered_df[filtered_df[cat_col] == 1]
    
    if is_manager == 1:
        filtered_df = filtered_df[filtered_df['is_manager'] == 1]
    
    if remote_work and remote_work != 'All':
        if remote_work == '部分遠端':
            filtered_df = filtered_df[filtered_df['remote_work'].str.contains('部分遠端', na=False)]
        elif remote_work == '完全遠端':
            filtered_df = filtered_df[filtered_df['remote_work'].str.contains('完全遠端', na=False)]
            
    if search:
        search_term = search.lower()
        filtered_df = filtered_df[
            filtered_df['job_title'].str.lower().str.contains(search_term, na=False) | 
            filtered_df['company'].str.lower().str.contains(search_term, na=False)
        ]
    
    # Calculate pagination
    total_count = len(filtered_df)
    total_pages = (total_count + per_page - 1) // per_page
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    
    # Get page data
    page_df = filtered_df.iloc[start_idx:end_idx]
    
    # Select columns
    cols = ['job_id', 'job_title', 'company', 'location', 'salary_min', 'salary_max', 'salary_note']
    if 'pred_min' in page_df.columns:
        cols.extend(['pred_min', 'pred_max'])
    if 'is_manager' in page_df.columns:
        cols.append('is_manager')
    if 'remote_work' in page_df.columns:
        cols.append('remote_work')
    
    # Replace NaN with None for valid JSON
    jobs_df = page_df[cols].copy()
    jobs_df = jobs_df.replace({np.nan: None})
    jobs = jobs_df.to_dict(orient='records')
    
    return jsonify({
        'jobs': jobs,
        'total_count': total_count,
        'page': page,
        'per_page': per_page,
        'total_pages': total_pages
    })

@app.route('/api/job/<job_id>')
def get_job_details(job_id):
    if df is None:
        return jsonify({'error': 'Data not loaded'}), 500
    
    job_id_str = str(job_id)  # 確保 str
    job = df[df['job_id'] == job_id_str]
    if job.empty:
        print(f"Job not found for ID: {job_id_str}")  # 加 log
        return jsonify({'error': 'Job not found'}), 404
    
    # Replace NaN with None for valid JSON
    job_series = job.iloc[0].replace({np.nan: None})
    job_data = job_series.to_dict()
    
    # Build Tree Structure for ECharts
    tools = job_data.get('tools', '')
    categorized_skills = categorize_skills(tools)
    
    tree_data = {
        "name": job_data['job_title'],
        "symbolSize": 20,
        "itemStyle": {"color": "#ff0000"}, # Root color
        "children": []
    }
    
    for cat, skills in categorized_skills.items():
        cat_node = {
            "name": cat,
            "itemStyle": {"color": "#00ff00"}, # Category color
            "children": []
        }
        for skill in skills:
            cat_node["children"].append({
                "name": skill,
                "itemStyle": {"color": "#0000ff"}, # Skill color
                "value": 1 # Weight
            })
        tree_data["children"].append(cat_node)
        
    return jsonify({
        'job': job_data,
        'tree': tree_data
    })

@app.route('/api/filters/options')
def get_filter_options():
    if df is None:
        return jsonify({})
    
    # Get unique locations (top 20 most common)
    locations = df['location'].value_counts().head(20).index.tolist()
    
    # Get salary range
    salary_range = {
        'min': int(df['salary_min'].min()),
        'max': int(df['salary_max'].max()),
        'median': int(df['salary_avg'].median())
    }
    
    # Get remote work options
    remote_options = ['All', '部分遠端', '完全遠端']
    
    # Count management positions
    manager_count = int(df['is_manager'].sum())
    
    # Get job categories from columns
    job_categories = [col.replace('cat_', '') for col in df.columns if col.startswith('cat_')]
    
    return jsonify({
        'locations': locations,
        'categories': job_categories,
        'salary_range': salary_range,
        'remote_options': remote_options,
        'manager_count': manager_count
    })

@app.route('/api/analysis/stats')
def get_analysis_stats():
    if df is None:
        return jsonify({})
    
    filters = {}
    category = request.args.get('category')
    city = request.args.get('city')
    
    if category and category != 'All':
        filters['category'] = category
    if city and city != 'All':
        filters['city'] = city
    
    # New filters for dashboard
    is_manager = request.args.get('is_manager')
    if is_manager == 'true' or is_manager == '1':
        filters['is_manager'] = True
        
    remote = request.args.get('remote')
    if remote and remote != 'All':
        filters['remote'] = remote
        
    stats = analysis_utils.get_dashboard_stats(df, filters)
    return jsonify(stats)

# 在這裡呼叫 load_data()，確保每次應用啟動都載入
load_data()

if __name__ == '__main__':
    # host='0.0.0.0' 允許外部連線（區域網路或 Ngrok）
    # 如果只想本地測試，改成 host='127.0.0.1'
    app.run(debug=True, host='0.0.0.0', port=5000)
