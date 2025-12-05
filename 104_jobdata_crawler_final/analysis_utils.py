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
        if 'category' in filters and filters['category'] and filters['category'] != 'All':
            cat = filters['category']
            # Try to match cat_{category} column
            cat_col = f"cat_{cat}"
            if cat_col in filtered_df.columns:
                filtered_df = filtered_df[filtered_df[cat_col] == 1]
            
        # Filter by City
        if 'city' in filters and filters['city'] and filters['city'] != 'All':
            city = filters['city']
            if 'location' in filtered_df.columns:
                filtered_df = filtered_df[filtered_df['location'].astype(str).str.contains(city, na=False)]

        # Filter by Manager (bool/int)
        if 'is_manager' in filters and filters['is_manager']:
            # Assuming filters['is_manager'] is truthy (True or 'true' or 1)
            if 'is_manager' in filtered_df.columns:
                filtered_df = filtered_df[filtered_df['is_manager'] == 1]
        
        # Filter by Remote Work
        if 'remote' in filters and filters['remote'] and filters['remote'] != 'All':
            remote = filters['remote']
            if 'remote_work' in filtered_df.columns:
                if remote == '部分遠端':
                    filtered_df = filtered_df[filtered_df['remote_work'].str.contains('部分遠端', na=False)]
                elif remote == '完全遠端':
                    filtered_df = filtered_df[filtered_df['remote_work'].str.contains('完全遠端', na=False)]

    # Debug info
    debug_msg = f"Total: {len(df)}"
    if filters:
        debug_msg += f", Filters: {filters}"
    
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
        if 'category' in filters and filters['category'] and filters['category'] != 'All':
            cat = filters['category']
            # Try to match cat_{category} column
            cat_col = f"cat_{cat}"
            if cat_col in filtered_df.columns:
                filtered_df = filtered_df[filtered_df[cat_col] == 1]
            
        # Filter by City
        if 'city' in filters and filters['city'] and filters['city'] != 'All':
            city = filters['city']
            if 'location' in filtered_df.columns:
                filtered_df = filtered_df[filtered_df['location'].astype(str).str.contains(city, na=False)]

        # Filter by Manager (bool/int)
        if 'is_manager' in filters and filters['is_manager']:
            # Assuming filters['is_manager'] is truthy (True or 'true' or 1)
            if 'is_manager' in filtered_df.columns:
                filtered_df = filtered_df[filtered_df['is_manager'] == 1]
        
        # Filter by Remote Work
        if 'remote' in filters and filters['remote'] and filters['remote'] != 'All':
            remote = filters['remote']
            if 'remote_work' in filtered_df.columns:
                if remote == '部分遠端':
                    filtered_df = filtered_df[filtered_df['remote_work'].str.contains('部分遠端', na=False)]
                elif remote == '完全遠端':
                    filtered_df = filtered_df[filtered_df['remote_work'].str.contains('完全遠端', na=False)]

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
        'count': len(filtered_df),
        'key_metrics': {
            'avg_min_salary': int(filtered_df['salary_min'].mean()) if not filtered_df['salary_min'].isna().all() else 0,
            'avg_max_salary': int(filtered_df['salary_max'].mean()) if not filtered_df['salary_max'].isna().all() else 0,
            'top_skill': get_top_skills(filtered_df, 1)[0]['name'] if get_top_skills(filtered_df, 1) else 'N/A',
            'active_location': filtered_df['city_for_stratify'].mode()[0] if not filtered_df['city_for_stratify'].empty else 'N/A'
        },
        'map_data': [{'name': k, 'value': v} for k, v in filtered_df['city_for_stratify'].value_counts().items()]
    }
