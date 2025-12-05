import pandas as pd
import numpy as np
from collections import Counter

def get_salary_distribution(df):
    """Returns salary distribution data for histogram."""
    # Use pred_avg if available, else salary_avg
    if 'pred_avg' in df.columns:
        salaries = df['pred_avg'].dropna()
    else:
        salaries = df['salary_avg'].dropna()
        
    hist, bin_edges = np.histogram(salaries, bins=20)
    return {
        'bins': [f"{int(bin_edges[i])}-{int(bin_edges[i+1])}" for i in range(len(bin_edges)-1)],
        'counts': hist.tolist()
    }

def get_experience_stats(df):
    """Returns average salary by experience level."""
    # Define sort order
    exp_order = [
        '不拘', '經歷不拘',
        '1年', '1年以上', '1~2年',
        '2年', '2年以上', '2~3年',
        '3年', '3年以上', '3~5年',
        '4年', '4年以上',
        '5年', '5年以上', '5~7年',
        '6年', '6年以上',
        '7年', '7年以上',
        '8年', '8年以上',
        '9年', '9年以上',
        '10年以上'
    ]
    
    def clean_exp(exp):
        if pd.isna(exp): return '不拘'
        exp = str(exp).strip()
        if '不拘' in exp or '不限' in exp: return '不拘'
        if '年以上' in exp:
            num = ''.join(filter(str.isdigit, exp))
            return f"{num}年以上" if num else '不拘'
        if '~' in exp:
            return exp
        num = ''.join(filter(str.isdigit, exp))
        return f"{num}年" if num else '不拘'

    df['exp_clean'] = df['experience'].apply(clean_exp)
    
    stats = df.groupby('exp_clean')['salary_avg'].mean().round(0)
    
    # Sort by defined order
    sorted_stats = []
    for exp in exp_order:
        if exp in stats.index:
            sorted_stats.append({'name': exp, 'value': stats[exp]})
            
    # Add remaining
    for exp in stats.index:
        if exp not in exp_order:
            sorted_stats.append({'name': exp, 'value': stats[exp]})
            
    return sorted_stats

def get_top_skills(df, top_n=15):
    """Returns top skills by count."""
    EXCLUDE_WORDS = {'--', 'n/a', '無', '不拘', '不限', 'nan', ''}
    all_tech = []
    
    # Use 'tools' column (and 'skills' if exists, but usually tools covers it)
    # In v7 csv, we have 'tools' column.
    
    for tools in df['tools'].dropna():
        items = [item.strip().lower() for item in str(tools).split(',')]
        for item in items:
            if item and item not in EXCLUDE_WORDS:
                all_tech.append(item.title())
                
    counts = Counter(all_tech).most_common(top_n)
    return [{'name': k, 'value': v} for k, v in counts]

def get_skill_salary(df, top_n=15):
    """Returns average salary for top skills."""
    top_skills = get_top_skills(df, top_n)
    skill_salaries = []
    
    for item in top_skills:
        skill = item['name']
        mask = df['tools'].astype(str).str.contains(skill, case=False, na=False)
        if mask.sum() >= 5:
            avg_sal = df.loc[mask, 'salary_avg'].mean()
            skill_salaries.append({'name': skill, 'value': round(avg_sal, 0)})
            
    return sorted(skill_salaries, key=lambda x: x['value'], reverse=True)

def get_city_stats(df):
    """Returns average salary by city."""
    if 'city_for_stratify' not in df.columns:
        return []
        
    stats = df.groupby('city_for_stratify')['salary_avg'].mean().round(0).sort_values(ascending=False).head(10)
    return [{'name': city, 'value': val} for city, val in stats.items()]

def get_dashboard_stats(df, filters=None):
    """Aggregates all stats with optional filtering."""
    filtered_df = df.copy()
    
    if filters:
        # Filter by Job Category
        if 'category' in filters and filters['category']:
            cat = filters['category']
            # Map user-friendly names to CSV columns
            cat_map = {
                'Data Engineer': 'cat_資料工程師',
                'AI Engineer': 'cat_AI工程師',
                'Software Engineer': 'cat_軟體工程師',
                'Analyst': 'cat_數據分析師／資料分析師',
                'Scientist': 'cat_資料科學家'
            }
            
            col = cat_map.get(cat)
            if col and col in filtered_df.columns:
                filtered_df = filtered_df[filtered_df[col] == 1]
            elif cat == 'Manager':
                if 'is_manager' in filtered_df.columns:
                    filtered_df = filtered_df[filtered_df['is_manager'] == 1]

        # Filter by City
        if 'city' in filters and filters['city']:
            city = filters['city']
            if 'city_for_stratify' in filtered_df.columns:
                # Simple containment check or exact match
                filtered_df = filtered_df[filtered_df['city_for_stratify'].astype(str).str.contains(city)]

    # Debug info
    debug_msg = f"Total: {len(df)}"
    if filters:
        debug_msg += f", Filters: {filters}"
    
    return {
        'salary_dist': get_salary_distribution(filtered_df),
        'exp_stats': get_experience_stats(filtered_df),
        'top_skills': get_top_skills(filtered_df),
        'skill_salary': get_skill_salary(filtered_df),
        'city_stats': get_city_stats(filtered_df),
        'count': f"{len(filtered_df)} (Debug: {debug_msg})"
    }
