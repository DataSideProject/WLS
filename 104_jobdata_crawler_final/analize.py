# analize_fixed_v5.py
# --------------------------------------------------------------
# 1. 讀資料
# 2. 解析 skills + tools（排除 --、空白）
# 3. 經驗箱形圖 **強制排序**：不拘 → 1年 → 2年 → ...
# 4. 6 張圖 + CSV 輸出
# --------------------------------------------------------------

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from collections import Counter
import warnings
warnings.filterwarnings("ignore")

df = df.dropna(subset=['salary_avg']).copy()
print(f"有薪資的職缺：{len(df)} 筆")

# ---------- 2. 基本統計 ----------
print("\n=== 整體薪資統計 ===")
print(df['salary_avg'].describe().round(0))

# ---------- 3. 解析 skills + tools（排除無意義）----------
print("\n正在解析 skills + tools（排除 --、空白、無意義）...")
EXCLUDE_WORDS = {'--', 'n/a', '無', '不拘', '不限', 'nan', ''}

all_tech = []
for idx, row in df.iterrows():
    row_tech = set()
    for col in ['skills', 'tools']:
        if col not in df.columns or pd.isna(row[col]):
            continue
        items = [item.strip().lower() for item in str(row[col]).split(',')]
        for item in items:
            if item and item not in EXCLUDE_WORDS:
                row_tech.add(item)
    all_tech.extend(list(row_tech))

top_n = 15
tech_counts = Counter(all_tech).most_common(top_n)
tech_df = pd.DataFrame(tech_counts, columns=['Tech', 'Count'])
tech_df['Tech'] = tech_df['Tech'].str.title()

print(f"共找到 {len(set(all_tech))} 種有效技術關鍵字")

# ---------- 4. 經驗欄位強制排序 ----------
# 定義排序順序
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

# 清理 experience 欄位（統一格式）
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

# 建立排序映射
exp_order_unique = []
seen = set()
for e in exp_order:
    if e in df['exp_clean'].values and e not in seen:
        exp_order_unique.append(e)
        seen.add(e)

# 補上資料中有的但順序表沒寫的（放在最後）
for e in df['exp_clean'].unique():
    if e not in seen:
        exp_order_unique.append(e)

df['exp_clean'] = pd.Categorical(df['exp_clean'], categories=exp_order_unique, ordered=True)

# ---------- 5. 圖表 ----------
fig, axes = plt.subplots(3, 2, figsize=(16, 12), constrained_layout=True)
fig.suptitle('104 資料工程師職缺市場分析（經驗排序正確）', fontsize=18, fontweight='bold')

(ax1, ax2), (ax3, ax4), (ax5, ax6) = axes

# 圖 1：薪資分佈
sns.histplot(data=df, x='salary_avg', bins=40, kde=True, ax=ax1, color='#3498db', alpha=0.7)
ax1.set_title('月薪分佈')
ax1.set_xlabel('平均月薪 (元)')
ax1.set_ylabel('職缺數')

# 圖 2：經驗 vs 薪資（強制排序）
sns.boxplot(data=df, x='exp_clean', y='salary_avg', ax=ax2, hue=None, legend=False)
ax2.set_title('經驗要求 vs 薪資（排序：不拘 → 1年 → ...）')
ax2.set_xlabel('經驗要求')
ax2.set_ylabel('平均月薪 (元)')
ax2.tick_params(axis='x', rotation=45)

# 圖 3：熱門技術
sns.barplot(data=tech_df, y='Tech', x='Count', ax=ax3, hue=None, legend=False, palette='viridis')
ax3.set_title(f'熱門技術 Top {top_n}')
ax3.set_xlabel('出現次數')
ax3.set_ylabel('')

# 圖 4：技術平均薪資
tech_salary = []
for tech_lower, _ in tech_counts:
    tech = tech_lower.title()
    mask = (
        df['skills'].astype(str).str.contains(tech_lower, case=False, na=False) |
        df['tools'].astype(str).str.contains(tech_lower, case=False, na=False)
    )
    if mask.sum() >= 5:
        mean_sal = df.loc[mask, 'salary_avg'].mean()
        tech_salary.append({'Tech': tech, 'Mean_Salary': mean_sal})

tech_salary_df = pd.DataFrame(tech_salary).sort_values('Mean_Salary', ascending=False)
if not tech_salary_df.empty:
    sns.barplot(data=tech_salary_df, y='Tech', x='Mean_Salary', ax=ax4, hue=None, legend=False, palette='magma')
    ax4.set_title('技術平均薪資（出現≥5次）')
else:
    ax4.text(0.5, 0.5, '無符合條件的技術', ha='center', va='center', transform=ax4.transAxes)
ax4.set_xlabel('平均月薪 (元)')
ax4.set_ylabel('')

# 圖 5：職務+技術組合
combo_list = [
    ('資料工程師', 'python'), ('資料工程師', 'sql'), ('資料工程師', 'aws'),
    ('資料科學家', 'python'), ('資料科學家', 'sql')
]
combo_salary = []
for job, tech in combo_list:
    m1 = df['job_title'].str.contains(job, case=False, na=False)
    m2 = (
        df['skills'].astype(str).str.contains(tech, case=False, na=False) |
        df['tools'].astype(str).str.contains(tech, case=False, na=False)
    )
    if (m1 & m2).sum() >= 3:
        mean_sal = df.loc[m1 & m2, 'salary_avg'].mean()
        combo_salary.append({'Combo': f'{job}+{tech.upper()}', 'Salary': mean_sal})

combo_df = pd.DataFrame(combo_salary)
if not combo_df.empty:
    combo_df = combo_df.sort_values('Salary', ascending=False)
    sns.barplot(data=combo_df, y='Combo', x='Salary', ax=ax5, hue=None, legend=False, palette='Set3')
    ax5.set_title('職務+技術組合薪資')
else:
    ax5.text(0.5, 0.5, '無符合條件的組合', ha='center', va='center', transform=ax5.transAxes)
ax5.set_xlabel('平均月薪 (元)')
ax5.set_ylabel('')

# 圖 6：城市平均薪資（若欄位存在）
if 'city_for_stratify' in df.columns:
    city_salary = df.groupby('city_for_stratify')['salary_avg'].mean().sort_values(ascending=False).head(10)
    sns.barplot(x=city_salary.values, y=city_salary.index, ax=ax6, hue=None, legend=False, palette='coolwarm')
    ax6.set_title('Top 10 城市平均薪資')
else:
    ax6.text(0.5, 0.5, '無城市欄位', ha='center', va='center', transform=ax6.transAxes)
    ax6.set_title('城市薪資')
ax6.set_xlabel('平均月薪 (元)')
ax6.set_ylabel('')

# ---------- 6. 儲存 ----------
plt.savefig('104_data_engineer_analysis_v5.png', dpi=300, bbox_inches='tight')
plt.show()

# CSV 輸出
tech_df.to_csv('top_tech_v5.csv', index=False, encoding='utf-8-sig')
tech_salary_df.to_csv('tech_salary_v5.csv', index=False, encoding='utf-8-sig')
combo_df.to_csv('combo_salary_v5.csv', index=False, encoding='utf-8-sig')

print("\n圖表已儲存：104_data_engineer_analysis_v5.png")
print("CSV 已匯出：top_tech_v5.csv, tech_salary_v5.csv, combo_salary_v5.csv")