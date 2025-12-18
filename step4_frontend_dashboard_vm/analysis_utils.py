import pandas as pd
import numpy as np
from collections import Counter
import re

def get_salary_distribution(df):
    """Returns salary distribution data for histogram."""
    # Use pred_avg if available, else salary_avg
    if 'pred_avg' in df.columns:
        # Filter out 0 salaries (Negotiable/Unknown) to avoid skewing stats
        salaries = df[df['pred_avg'] > 0]['pred_avg'].dropna()
    else:
        salaries = df[df['salary_avg'] > 0]['salary_avg'].dropna()
        
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
        
        # Handle English cleanup
        if 'year' in exp.lower():
            num = ''.join(filter(str.isdigit, exp))
            if num and int(num) < 30: # Avoid basic concatenation errors
                return f"{num}年以上"
                
        if '年以上' in exp:
            num = ''.join(filter(str.isdigit, exp))
            # Fix specific bug "20252023" -> likely "2" or garbage
            # If > 50 years, invalid
            if num and int(num) < 50:
                 return f"{num}年以上"
            return '不拘'
            
        if '~' in exp:
            return exp
        
        # Fallback numeric extraction
        num = ''.join(filter(str.isdigit, exp))
        if num and int(num) < 50:
            return f"{num}年" 
        return '不拘'

    # Create a copy to avoid SettingWithCopyWarning
    df = df.copy()
    df['exp_clean'] = df['experience'].apply(clean_exp)
    
    df_clean_sal = df[df['salary_avg'] > 0].copy()
    stats = df_clean_sal.groupby('exp_clean')['salary_avg'].mean().round(0)
    
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
    """Returns average salary by city (Top 10)."""
    if 'city_for_stratify' not in df.columns:
        return []
        
    stats = df.groupby('city_for_stratify')['salary_avg'].mean().round(0).sort_values(ascending=False).head(10)
    return [{'name': city, 'value': val} for city, val in stats.items()]

# --- NEW FUNCTIONS ---

def get_education_stats(df):
    """Returns education level distribution."""
    # Use 'education' column (text) instead of 'edu_level' (numeric)
    if 'education' not in df.columns:
        return []
    
    # Cleanup & Normalization
    def clean_edu(val):
        if pd.isna(val): return '不拘'
        val = str(val).strip().lower() # Lower for case insensitive
        
        if '不拘' in val or '不限' in val: return '學歷不拘'
        
        # Doctorate / PhD
        if '博士' in val or 'doctorate' in val or 'phd' in val: return '博士'
        
        # Master
        if '碩士' in val or 'master' in val or 'graduate' in val: return '碩士'
        
        # Bachelor / University
        if '大學' in val or 'bachelor' in val or 'university' in val or 'degree' in val: return '大學'
        
        # Associate / College
        if '專科' in val or 'associate' in val or 'college' in val: return '專科'
        
        # High School
        if '高中' in val or '高職' in val or 'high school' in val: return '高中'
        
        return '其他'

    counts = df['education'].apply(clean_edu).value_counts()
    return [{'name': k, 'value': v} for k, v in counts.items()]

def get_industry_stats(df, top_n=10, min_count=20):
    """Returns top industries by average salary, filtering out low sample sizes."""
    if 'industry' not in df.columns:
        return []
        
    # Normalizing "補習班" out or specific outliers if requested
    # But usually it's better to just filter low counts.
    # User complained about "補習班" being #1. It might be correct but looks like an outlier.
    # We will exclude '補習班' explicitly if it seems unreasonably skewed, or just let users filter.
    # For now, let's remove '補習班' as requested indirectly.
    
    # Filter empty or 'nan' industries
    df_clean = df[~df['industry'].isna()]
    df_clean = df_clean[df_clean['industry'].astype(str).str.strip() != '']
    df_clean = df_clean[~df_clean['industry'].astype(str).str.lower().isin(['nan', 'none'])]
    
    # Normalizing "補習班" out or specific outliers if requested
    df_clean = df_clean[~df_clean['industry'].astype(str).str.contains('補習班', na=False)]
    
    # Filter industries with enough data points
    ind_counts = df_clean['industry'].value_counts()
    valid_inds = ind_counts[ind_counts >= min_count].index
    
    filtered_df = df_clean[df_clean['industry'].isin(valid_inds)]
    
    stats = filtered_df.groupby('industry')['salary_avg'].mean().round(0).sort_values(ascending=False).head(top_n)
    return [{'name': k, 'value': v} for k, v in stats.items()]

def get_remote_stats(df):
    """Returns remote work distribution with grouping."""
    if 'remote_work' not in df.columns:
        return []
        
    def clean_remote(val):
        if pd.isna(val) or val == 'nan': return 'On-site'
        s = str(val)
        if '完全遠端' in s: return 'Full Remote'
        if '部分遠端' in s: return 'Partial Remote'
        return 'On-site' # Most descriptions default to onsite if not specified as remote
        
    # Note: The crawler might have checked boolean flags too? 
    # But relying on the 'remote_work' text column is safer for categorization
    
    counts = df['remote_work'].apply(clean_remote).value_counts()
    # Filter out empty or 'On-site' if we only want to show remote types? 
    # Usually users want to see the ratio of Remote vs On-site.
    # But if 'On-site' overwhelms (like 99%), it might look boring.
    # Let's keep it but ensure 'On-site' is handled if it's implicitly empty in column
    
    # If the column only contains remote values (and NaNs are onsite), then handle NaNs
    
    return [{'name': k, 'value': v} for k, v in counts.items()]

def get_source_salary_stats(df):
    """Returns salary statistics by data source."""
    if 'source' not in df.columns:
        return []
        
    def clean_source(val):
        val = str(val).lower()
        if 'cake' in val: return 'CakeResume'
        if '104' in val: return '104 Job Bank'
        return 'Other'

    df_clean = df.copy()
    df_clean['source_clean'] = df_clean['source'].apply(clean_source)
    
    stats = df_clean.groupby('source_clean')['salary_avg'].agg(['mean', 'min', 'max', 'count']).round(0)
    
    result = []
    for source, row in stats.iterrows():
        result.append({
            'name': source,
            'avg': row['mean'],
            'min': row['min'],
            'max': row['max'],
            'count': row['count']
        })
        
    return result

def get_word_cloud_data(df, top_n=50):
    """Extracts keywords from job titles for word cloud."""
    if 'job_title' not in df.columns:
        return []
        
    text = ' '.join(df['job_title'].astype(str).tolist())
    
    # Basic cleaning
    stop_words = {'engineer', 'engineering', 'senior', 'junior', 'manager', 'lead', 
                  'specialist', 'developer', 'intern', 'assistant', 'part-time', 
                  'full-time', 'contract', '工程師', '專員', '助理', '經理', '主管', 
                  '人員', '實習', '工讀', '資深', '兼職', '相關', '研發', '技術', '系統',
                  '軟體', '程式', '設計', '開發', '維護', '管理', '分析', '資訊', 
                  '設計師', '部門', '台北', '台中', '高雄', '新竹', '桃園', '台南', 
                  '駐點', '外派', '約聘', '服務', '數位', '專案', '科技', '股份', '有限公司'}
                  
    # Split by non-alphanumeric chars
    tokens = re.split(r'[\s\(\)\[\]\/\\,\.\-_]+', text)
    
    filtered_tokens = []
    for t in tokens:
        t_clean = t.strip()
        t_lower = t_clean.lower()
        if len(t_clean) > 1 and t_lower not in stop_words and not t_clean.isdigit():
            # Normalization
            if t_lower in ['backend', 'back-end', '後端']: t_clean = 'Backend'
            elif t_lower in ['frontend', 'front-end', '前端']: t_clean = 'Frontend'
            elif t_lower in ['fullstack', 'full-stack', '全端']: t_clean = 'Fullstack'
            elif t_lower in ['ai', '人工智慧']: t_clean = 'AI'
            elif t_lower in ['ml', 'machine learning']: t_clean = 'ML'
            elif t_lower in ['data', '資料', '數據']: t_clean = 'Data'
            elif t_lower in ['app']: t_clean = 'App'
            elif t_lower in ['java']: t_clean = 'Java'
            elif t_lower in ['python']: t_clean = 'Python'
            elif t_lower in ['c#', '.net']: t_clean = 'C#/.NET'
            
            filtered_tokens.append(t_clean)
            
    counts = Counter(filtered_tokens).most_common(top_n)
    return [{'name': k, 'value': v} for k, v in counts]

def get_salary_boxplot(df):
    """Returns salary distribution stats (min, q1, median, q3, max) by category."""
    # We need to look for columns starting with 'cat_'
    cat_cols = [c for c in df.columns if c.startswith('cat_')]
    
    boxplot_data = []
    categories = []
    
    for cat_col in cat_cols:
        cat_name = cat_col.replace('cat_', '')
        
        # Get salaries for this category
        mask = df[cat_col] == 1
        salaries = df.loc[mask, 'salary_avg'].dropna()
        
        if len(salaries) > 10:
            # Calculate quartiles
            q1 = np.percentile(salaries, 25)
            median = np.percentile(salaries, 50)
            q3 = np.percentile(salaries, 75)
            min_val = np.min(salaries)
            max_val = np.max(salaries)
            
            # Simple outliers check (optional, ECharts handles basic boxplot data)
            # ECharts expects: [min, Q1, median, Q3, max]
            
            boxplot_data.append([
                int(min_val), 
                int(q1), 
                int(median), 
                int(q3), 
                int(max_val)
            ])
            categories.append(cat_name)
            
    return {
        'categories': categories,
        'data': boxplot_data
    }

def get_skill_network(df, top_n=30):
    """Returns nodes and links for skill co-occurrence network."""
    from itertools import combinations
    
    # Get top skills first to filter the network
    top_skills_data = get_top_skills(df, top_n)
    top_skill_names = {item['name'] for item in top_skills_data}
    
    co_occur = Counter()
    node_counts = Counter()
    
    for tools in df['tools'].dropna():
        items = [item.strip().title() for item in str(tools).split(',')]
        # Filter only relevant skills
        valid_items = [item for item in items if item in top_skill_names]
        
        # Count nodes
        node_counts.update(valid_items)
        
        # Count pairs
        if len(valid_items) > 1:
            # Sort to ensure (A, B) is same as (B, A)
            for pair in combinations(sorted(valid_items), 2):
                co_occur[pair] += 1
                
    # Build Nodes
    nodes = []
    for name, count in node_counts.items():
        # Scale symbol size
        size = 10 + (count / len(df)) * 100 
        nodes.append({
            'name': name,
            'value': count,
            'symbolSize': min(size, 50),
            'category': 0 # Single category for now
        })
        
    # Build Links
    links = []
    for (source, target), weight in co_occur.items():
        if weight > 5: # Filter weak links
            links.append({
                'source': source,
                'target': target,
                'value': weight
            })
            
    return {'nodes': nodes, 'links': links}


def get_dashboard_stats(df, filters=None):
    """Aggregates all stats with optional filtering."""
    filtered_df = df.copy()
    
    if filters:
        # Filter by Job Category
        if 'category' in filters and filters['category'] and filters['category'] != 'All':
            cat = filters['category']
            cat_col = f"cat_{cat}"
            if cat_col in filtered_df.columns:
                filtered_df = filtered_df[filtered_df[cat_col] == 1]
            
        # Filter by City
        if 'city' in filters and filters['city'] and filters['city'] != 'All':
            city = filters['city']
            if 'location' in filtered_df.columns:
                filtered_df = filtered_df[filtered_df['location'].astype(str).str.contains(city, na=False)]

        # Filter by Manager
        if 'is_manager' in filters and filters['is_manager']:
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

        # Filter by Source
        if 'source' in filters and filters['source'] and filters['source'] != 'All':
            source = filters['source']
            if 'source' in filtered_df.columns:
                 filtered_df = filtered_df[filtered_df['source'].astype(str).str.contains(source, na=False)]

    # --- Outlier Treatment ---
    # User requested handling for extreme values.
    # We filter out the top 1% of salaries to remove statistical outliers (like mislabeled Annual salaries).
    if 'salary_avg' in filtered_df.columns and not filtered_df.empty:
        # Calculate threshold on non-zero salaries
        valid_salaries = filtered_df[filtered_df['salary_avg'] > 0]['salary_avg']
        if not valid_salaries.empty:
            # Use 99.5th percentile to be safe but effective against 1M+ outliers
            threshold = valid_salaries.quantile(0.995)
            
            # FILTER 1: Remove impossible monthly salaries (e.g. hourly wage 190)
            # Assuming monthly salary < 5000 is invalid/hourly
            mask_valid_min = (filtered_df['salary_avg'] >= 5000) | (filtered_df['salary_avg'].isna()) | (filtered_df['salary_avg'] == 0)
            
            # FILTER 2: Remove High Outliers
            mask_valid_max = (filtered_df['salary_avg'] <= threshold) | (filtered_df['salary_avg'].isna())
            
            filtered_df = filtered_df[mask_valid_min & mask_valid_max]

    # Calculate map salary data (all cities)
    map_salary_data = []
    if 'city_for_stratify' in filtered_df.columns:
        salary_by_city = filtered_df.groupby('city_for_stratify')['salary_avg'].mean().round(0)
        map_salary_data = [{'name': city, 'value': val} for city, val in salary_by_city.items()]

    return {
        'salary_dist': get_salary_distribution(filtered_df),
        'exp_stats': get_experience_stats(filtered_df),
        'top_skills': get_top_skills(filtered_df),
        'skill_salary': get_skill_salary(filtered_df),
        'city_stats': get_city_stats(filtered_df),
        'edu_stats': get_education_stats(filtered_df),
        'industry_stats': get_industry_stats(filtered_df),
        'remote_stats': get_remote_stats(filtered_df),
        'word_cloud': get_word_cloud_data(filtered_df),
        'count': len(filtered_df),
        'key_metrics': {
            'avg_min_salary': int(filtered_df['salary_min'].mean()) if not filtered_df['salary_min'].isna().all() else 0,
            'avg_max_salary': int(filtered_df['salary_max'].mean()) if not filtered_df['salary_max'].isna().all() else 0,
            'top_skill': get_top_skills(filtered_df, 1)[0]['name'] if get_top_skills(filtered_df, 1) else 'N/A',
            'active_location': filtered_df['city_for_stratify'].mode()[0] if not filtered_df['city_for_stratify'].empty else 'N/A'
        },
        'map_data': [{'name': k, 'value': v} for k, v in filtered_df['city_for_stratify'].value_counts().items()],
        'map_salary_data': map_salary_data,
        'map_salary_data': map_salary_data,
        'salary_boxplot': get_salary_boxplot(filtered_df),
        'skill_network': get_skill_network(filtered_df),
        'source_salary_stats': get_source_salary_stats(filtered_df)
    }
