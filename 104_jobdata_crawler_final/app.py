from flask import Flask, render_template, jsonify, request
import pandas as pd
import json
import os
import re

app = Flask(__name__)

# Load Data
DATA_PATH = r'job_data_with_full_salary_v7_segmented.csv'
TAXONOMY_PATH = r'skill_taxonomy.json'

# Global variables
df = None
taxonomy = {}

def load_data():
    global df, taxonomy
    if os.path.exists(DATA_PATH):
        df = pd.read_csv(DATA_PATH)
        # Ensure job_id is string
        if 'job_id' in df.columns:
            df['job_id'] = df['job_id'].astype(str)
        else:
            # Create a dummy job_id if missing
            df['job_id'] = df.index.astype(str)
            
        # Fill NaNs
        df = df.fillna('')
    else:
        print(f"Error: Data file {DATA_PATH} not found.")
        
    if os.path.exists(TAXONOMY_PATH):
        with open(TAXONOMY_PATH, 'r', encoding='utf-8') as f:
            taxonomy = json.load(f)
    else:
        print(f"Error: Taxonomy file {TAXONOMY_PATH} not found.")

def categorize_skills(tools_str):
    if not tools_str:
        return []
    
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
    
    # Return a lightweight list for the sidebar
    # Filter columns to reduce payload
    jobs = df[['job_id', 'job_title', 'company', 'location', 'salary_min', 'salary_max']].to_dict(orient='records')
    return jsonify(jobs)

@app.route('/api/job/<job_id>')
def get_job_details(job_id):
    if df is None:
        return jsonify({'error': 'Data not loaded'}), 500
        
    job = df[df['job_id'] == job_id]
    if job.empty:
        return jsonify({'error': 'Job not found'}), 404
    
    job_data = job.iloc[0].to_dict()
    
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

if __name__ == '__main__':
    load_data()
    app.run(debug=True, port=5000)
