import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from collections import Counter
import re
from wordcloud import WordCloud

# 設置 Matplotlib 後端（PyCharm 兼容）
plt.switch_backend('TkAgg')

# 設定中文字型
plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei']  # Windows 用微軟正黑體
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['font.size'] = 8  # 保持字型大小

# 載入 CSV 檔案
file_path = 'job_data_jobcat_1022_20251019.csv'
df = pd.read_csv(file_path)

# 列出 job_title 前 10 筆
print("職缺標題前 10 筆:")
print(df['job_title'].head(10))

# 定義經驗排序
exp_order = ['經歷不拘', '1年以上', '2年以上', '3年以上', '4年以上', '5年以上', '6年以上', '7年以上', '8年以上', '10年以上']
df['experience'] = pd.Categorical(df['experience'], categories=exp_order, ordered=True)

# 檢查 experience 欄位
print("經驗欄位唯一值:")
print(df['experience'].value_counts())

# 填補缺失薪資
def fill_salary(row):
    if pd.isna(row['salary_avg']):
        experience = row['experience']
        if any(x in experience for x in ['1年', '2年', '3年']):
            return 57000
        elif any(x in experience for x in ['4年', '5年']):
            return 60000
        elif any(x in experience for x in ['6年', '7年', '8年', '9年', '10年']):
            return 65000
        else:
            return 50000  # 默認值
    return row['salary_avg']

# 創建遠端工作和上市上櫃欄位
df['is_remote'] = df['tags'].str.contains('遠端工作', na=False)
df['is_listed'] = df['tags'].str.contains('上市上櫃', na=False)

# 推估公司規模
df['company_size'] = df['company'].apply(lambda x: '大型' if any(kw in x for kw in ['國際', '集團', '股份', '科技', '電子']) else '中小型')

# 應用薪資填補
df['salary_avg'] = df.apply(fill_salary, axis=1)

# 檢查數據
print("總職缺數:", len(df))
print("缺失值統計:")
print(df.isnull().sum())

# 過濾有薪資的職缺
df_salary = df.dropna(subset=['salary_avg'])[['job_title', 'industry', 'location', 'experience', 'education', 'salary_avg', 'is_remote', 'is_listed', 'tags', 'company_size']]
print("有薪資資訊的職缺數:", len(df_salary))

# 提前定義全局變數
industry_counts = df['industry'].value_counts().head(10)
print("\n產業分佈 (前 10):")
print(industry_counts)
industry_salary = df_salary.groupby('industry')['salary_avg'].agg(['mean', 'median', 'count']).sort_values('count', ascending=False).head(10)
print("\n按產業分組的薪資 (前 10):")
print(industry_salary)
location_salary = df_salary.groupby('location')['salary_avg'].agg(['mean', 'count']).reset_index()
print("\n地區與薪資:")
print(location_salary.head(10))

# 技能提取
skills = ['python', 'sql', 'etl', 'big data', 'hadoop', 'spark', 'aws', 'gcp', 'azure', 'machine learning', 'llm', 'mongodb', 'mysql', 'pandas', 'tableau', 'docker', 'kubernetes', 'data analysis', 'cloud', 'power bi', 'tensorflow', 'pytorch']
skill_counts = Counter()
for title in df['job_title'].dropna():
    title_lower = title.lower()
    title_clean = re.sub(r'工程師|資料|數據|analyst|engineer|scientist|developer|ai\s|人工智慧|機器學習|資深|主任|專案|管理|系統|技術|資訊|研發|助理|中心|維運|應屆|新鮮人|應用|軟體|it|php|ml', '', title_lower)
    for skill in skills:
        if skill in title_clean:
            skill_counts[skill] += 1
skill_counts_df = pd.DataFrame(skill_counts.most_common(10), columns=['Skill', 'Count'])
print("\n熱門技能 (前 10):")
print(skill_counts_df)

# 技能與薪資
skill_salary = []
for skill in skills:
    skill_jobs = df_salary[df_salary['job_title'].str.lower().str.contains(skill, na=False)]
    if len(skill_jobs) > 0:
        skill_salary.append({
            'Skill': skill,
            'Mean_Salary': skill_jobs['salary_avg'].mean(),
            'Count': len(skill_jobs)
        })
skill_salary_df = pd.DataFrame(skill_salary).sort_values('Mean_Salary', ascending=False).head(10)
print("\n技能與薪資 (前 10):")
print(skill_salary_df)

# 1. 薪資分析圖表
fig_salary, axes_salary = plt.subplots(2, 2, figsize=(20, 12))
fig_salary.suptitle('薪資分析', fontsize=12)

# 子圖 1：薪資分佈直方圖
sns.histplot(df_salary['salary_avg'], bins=20, kde=True, ax=axes_salary[0, 0])
axes_salary[0, 0].set_title('薪資分佈 (月薪)')
axes_salary[0, 0].set_xlabel('平均薪資 (元)')
axes_salary[0, 0].set_ylabel('職缺數')
axes_salary[0, 0].tick_params(axis='both', labelsize=6)

# 子圖 2：按經驗的薪資箱形圖
sns.boxplot(x='experience', y='salary_avg', data=df_salary, ax=axes_salary[0, 1], order=exp_order)
axes_salary[0, 1].set_title('按經驗要求的薪資')
axes_salary[0, 1].set_xlabel('經驗要求')
axes_salary[0, 1].set_ylabel('平均薪資 (元)')
axes_salary[0, 1].tick_params(axis='x', rotation=45, labelsize=6)

# 子圖 3：按產業的薪資長條圖
sns.barplot(x='mean', y=industry_salary.index, data=industry_salary, ax=axes_salary[1, 0])
axes_salary[1, 0].set_title('按產業的薪資 (前 10)')
axes_salary[1, 0].set_xlabel('平均薪資 (元)')
axes_salary[1, 0].set_ylabel('產業')
axes_salary[1, 0].tick_params(axis='y', labelsize=6)

# 子圖 4：遠端工作與薪資箱形圖
sns.boxplot(x='is_remote', y='salary_avg', data=df_salary, ax=axes_salary[1, 1])
axes_salary[1, 1].set_title('遠端工作與薪資')
axes_salary[1, 1].set_xlabel('是否遠端工作')
axes_salary[1, 1].set_ylabel('平均薪資 (元)')
axes_salary[1, 1].set_xticks([0, 1])
axes_salary[1, 1].set_xticklabels(['否', '是'], fontsize=6)

fig_salary.subplots_adjust(wspace=0.4, hspace=0.5)
plt.savefig('salary_analysis.png', dpi=300, bbox_inches='tight')
plt.show()
plt.close(fig_salary)

# 2. 產業分析圖表
fig_industry, axes_industry = plt.subplots(2, 2, figsize=(20, 12))
fig_industry.suptitle('產業分析', fontsize=12)

# 子圖 1：產業分佈長條圖
sns.barplot(x=industry_counts.values, y=industry_counts.index, ax=axes_industry[0, 0])
axes_industry[0, 0].set_title('職缺產業分佈 (前 10)')
axes_industry[0, 0].set_xlabel('職缺數')
axes_industry[0, 0].set_ylabel('產業')
axes_industry[0, 0].tick_params(axis='y', labelsize=6)

# 子圖 2：產業與薪資長條圖
sns.barplot(x='mean', y=industry_salary.index, data=industry_salary, ax=axes_industry[0, 1])
axes_industry[0, 1].set_title('按產業的薪資 (前 10)')
axes_industry[0, 1].set_xlabel('平均薪資 (元)')
axes_industry[0, 1].set_ylabel('產業')
axes_industry[0, 1].tick_params(axis='y', labelsize=6)

# 子圖 3：遠端工作與產業長條圖
remote_industry = df[df['is_remote']].groupby('industry')['job_id'].count().sort_values(ascending=False).head(10)
sns.barplot(x=remote_industry.values, y=remote_industry.index, ax=axes_industry[1, 0])
axes_industry[1, 0].set_title('遠端工作產業分佈 (前 10)')
axes_industry[1, 0].set_xlabel('職缺數')
axes_industry[1, 0].set_ylabel('產業')
axes_industry[1, 0].tick_params(axis='y', labelsize=6)

# 子圖 4：產業與經驗熱圖
exp_industry = df.pivot_table(index='industry', columns='experience', values='job_id', aggfunc='count', fill_value=0, observed=True).head(10)
sns.heatmap(exp_industry, annot=True, cmap='Blues', fmt='d', ax=axes_industry[1, 1])
axes_industry[1, 1].set_title('經驗與產業分佈熱圖')
axes_industry[1, 1].set_xlabel('經驗要求')
axes_industry[1, 1].set_ylabel('產業')
axes_industry[1, 1].tick_params(axis='x', rotation=45, labelsize=6)

fig_industry.subplots_adjust(wspace=0.4, hspace=0.5)
plt.savefig('industry_analysis.png', dpi=300, bbox_inches='tight')
plt.show()
plt.close(fig_industry)

# 3. 經歷分析圖表
fig_experience, axes_experience = plt.subplots(2, 2, figsize=(20, 12))
fig_experience.suptitle('經歷分析', fontsize=12)

# 子圖 1：經驗要求分佈長條圖
exp_counts = df['experience'].value_counts()
sns.barplot(x=exp_counts.values, y=exp_counts.index, ax=axes_experience[0, 0])
axes_experience[0, 0].set_title('經驗要求分佈')
axes_experience[0, 0].set_xlabel('職缺數')
axes_experience[0, 0].set_ylabel('經驗要求')
axes_experience[0, 0].tick_params(axis='y', labelsize=6)

# 子圖 2：經驗與薪資箱形圖
sns.boxplot(x='experience', y='salary_avg', data=df_salary, ax=axes_experience[0, 1], order=exp_order)
axes_experience[0, 1].set_title('按經驗要求的薪資')
axes_experience[0, 1].set_xlabel('經驗要求')
axes_experience[0, 1].set_ylabel('平均薪資 (元)')
axes_experience[0, 1].tick_params(axis='x', rotation=45, labelsize=6)

# 子圖 3：經驗與技能長條圖
exp_skills = Counter()
for idx, row in df.iterrows():
    title_lower = row['job_title'].lower() if pd.notna(row['job_title']) else ''
    title_clean = re.sub(r'工程師|資料|數據|analyst|engineer|scientist|developer|ai\s|人工智慧|機器學習|資深|主任|專案|管理|系統|技術|資訊|研發|助理|中心|維運|應屆|新鮮人|應用|軟體|it|php|ml', '', title_lower)
    for skill in skills[:5]:  # 前 5 技能
        if skill in title_clean:
            exp_skills[(row['experience'], skill)] += 1
exp_skills_df = pd.DataFrame(exp_skills.most_common(10), columns=['Exp_Skill', 'Count'])
exp_skills_df[['Experience', 'Skill']] = pd.DataFrame(exp_skills_df['Exp_Skill'].tolist(), index=exp_skills_df.index)
sns.barplot(x='Count', y='Skill', hue='Experience', data=exp_skills_df, ax=axes_experience[1, 0])
axes_experience[1, 0].set_title('經驗與技能 (前 5 技能)')
axes_experience[1, 0].set_xlabel('出現次數')
axes_experience[1, 0].set_ylabel('技能')
axes_experience[1, 0].legend(fontsize=6)
axes_experience[1, 0].tick_params(axis='y', labelsize=6)

# 子圖 4：經驗與遠端工作熱圖
exp_remote = df.pivot_table(index='experience', columns='is_remote', values='job_id', aggfunc='count', fill_value=0, observed=True)
sns.heatmap(exp_remote, annot=True, cmap='Blues', fmt='d', ax=axes_experience[1, 1])
axes_experience[1, 1].set_title('經驗與遠端工作熱圖')
axes_experience[1, 1].set_xlabel('是否遠端工作')
axes_experience[1, 1].set_ylabel('經驗要求')
axes_experience[1, 1].set_xticklabels(['否', '是'], fontsize=6)
axes_experience[1, 1].tick_params(axis='y', labelsize=6)

fig_experience.subplots_adjust(wspace=0.4, hspace=0.5)
plt.savefig('experience_analysis.png', dpi=300, bbox_inches='tight')
plt.show()
plt.close(fig_experience)

# 4. 遠端工作分析圖表
fig_remote, axes_remote = plt.subplots(2, 2, figsize=(20, 12))
fig_remote.suptitle('遠端工作分析', fontsize=12)

# 子圖 1：遠端工作分佈長條圖
remote_counts = df['is_remote'].value_counts()
sns.barplot(x=remote_counts.index, y=remote_counts.values, ax=axes_remote[0, 0])
axes_remote[0, 0].set_title('遠端工作分佈')
axes_remote[0, 0].set_xlabel('是否遠端工作')
axes_remote[0, 0].set_ylabel('職缺數')
axes_remote[0, 0].set_xticks([0, 1])
axes_remote[0, 0].set_xticklabels(['否', '是'], fontsize=6)
axes_remote[0, 0].tick_params(axis='x', labelsize=6)

# 子圖 2：遠端工作與薪資箱形圖
sns.boxplot(x='is_remote', y='salary_avg', data=df_salary, ax=axes_remote[0, 1])
axes_remote[0, 1].set_title('遠端工作與薪資')
axes_remote[0, 1].set_xlabel('是否遠端工作')
axes_remote[0, 1].set_ylabel('平均薪資 (元)')
axes_remote[0, 1].set_xticks([0, 1])
axes_remote[0, 1].set_xticklabels(['否', '是'], fontsize=6)
axes_remote[0, 1].tick_params(axis='x', labelsize=6)

# 子圖 3：遠端工作與產業長條圖
sns.barplot(x=remote_industry.values, y=remote_industry.index, ax=axes_remote[1, 0])
axes_remote[1, 0].set_title('遠端工作產業分佈 (前 10)')
axes_remote[1, 0].set_xlabel('職缺數')
axes_remote[1, 0].set_ylabel('產業')
axes_remote[1, 0].tick_params(axis='y', labelsize=6)

# 子圖 4：遠端工作與學歷長條圖
remote_edu = df[df['is_remote']].groupby('education')['job_id'].count().sort_values(ascending=False)
sns.barplot(x=remote_edu.values, y=remote_edu.index, ax=axes_remote[1, 1])
axes_remote[1, 1].set_title('遠端工作與學歷分佈')
axes_remote[1, 1].set_xlabel('職缺數')
axes_remote[1, 1].set_ylabel('學歷')
axes_remote[1, 1].tick_params(axis='y', labelsize=6)

fig_remote.subplots_adjust(wspace=0.4, hspace=0.5)
plt.savefig('remote_analysis.png', dpi=300, bbox_inches='tight')
plt.show()
plt.close(fig_remote)

# 5. 技能分析圖表
fig_skills, axes_skills = plt.subplots(2, 2, figsize=(20, 12))
fig_skills.suptitle('技能分析', fontsize=12)

# 子圖 1：技能分佈長條圖
sns.barplot(x='Count', y='Skill', data=skill_counts_df, ax=axes_skills[0, 0])
axes_skills[0, 0].set_title('熱門技能分佈 (前 10)')
axes_skills[0, 0].set_xlabel('出現次數')
axes_skills[0, 0].set_ylabel('技能')
axes_skills[0, 0].tick_params(axis='y', labelsize=6)

# 子圖 2：技能與薪資長條圖
sns.barplot(x='Mean_Salary', y='Skill', data=skill_salary_df, ax=axes_skills[0, 1])
axes_skills[0, 1].set_title('技能與薪資 (前 10)')
axes_skills[0, 1].set_xlabel('平均薪資 (元)')
axes_skills[0, 1].set_ylabel('技能')
axes_skills[0, 1].tick_params(axis='y', labelsize=6)

# 子圖 3：技能與遠端工作長條圖
remote_skills = Counter()
for title in df[df['is_remote']]['job_title'].dropna():
    title_lower = title.lower()
    title_clean = re.sub(r'工程師|資料|數據|analyst|engineer|scientist|developer|ai\s|人工智慧|機器學習|資深|主任|專案|管理|系統|技術|資訊|研發|助理|中心|維運|應屆|新鮮人|應用|軟體|it|php|ml', '', title_lower)
    for skill in skills:
        if skill in title_clean:
            remote_skills[skill] += 1
remote_skills_df = pd.DataFrame(remote_skills.most_common(10), columns=['Skill', 'Count'])
sns.barplot(x='Count', y='Skill', data=remote_skills_df, ax=axes_skills[1, 0])
axes_skills[1, 0].set_title('技能與遠端工作 (前 10)')
axes_skills[1, 0].set_xlabel('出現次數')
axes_skills[1, 0].set_ylabel('技能')
axes_skills[1, 0].tick_params(axis='y', labelsize=6)

# 子圖 4：技能與學歷長條圖
edu_skills = Counter()
for idx, row in df.iterrows():
    title_lower = row['job_title'].lower() if pd.notna(row['job_title']) else ''
    title_clean = re.sub(r'工程師|資料|數據|analyst|engineer|scientist|developer|ai\s|人工智慧|機器學習|資深|主任|專案|管理|系統|技術|資訊|研發|助理|中心|維運|應屆|新鮮人|應用|軟體|it|php|ml', '', title_lower)
    for skill in skills[:5]:  # 前 5 技能
        if skill in title_clean:
            edu_skills[(row['education'], skill)] += 1
edu_skills_df = pd.DataFrame(edu_skills.most_common(10), columns=['Edu_Skill', 'Count'])
edu_skills_df[['Education', 'Skill']] = pd.DataFrame(edu_skills_df['Edu_Skill'].tolist(), index=edu_skills_df.index)
sns.barplot(x='Count', y='Skill', hue='Education', data=edu_skills_df, ax=axes_skills[1, 1])
axes_skills[1, 1].set_title('技能與學歷 (前 5 技能)')
axes_skills[1, 1].set_xlabel('出現次數')
axes_skills[1, 1].set_ylabel('技能')
axes_skills[1, 1].legend(fontsize=6)
axes_skills[1, 1].tick_params(axis='y', labelsize=6)

fig_skills.subplots_adjust(wspace=0.4, hspace=0.5)
plt.savefig('skills_analysis.png', dpi=300, bbox_inches='tight')
plt.show()
plt.close(fig_skills)

# 6. 總覽分析圖表（六個重要分析）
fig_main, axes_main = plt.subplots(2, 3, figsize=(24, 12))
fig_main.suptitle('資料工程師職缺分析 - 總覽', fontsize=12)

# 子圖 1：薪資分佈直方圖
sns.histplot(df_salary['salary_avg'], bins=20, kde=True, ax=axes_main[0, 0])
axes_main[0, 0].set_title('薪資分佈 (月薪)')
axes_main[0, 0].set_xlabel('平均薪資 (元)')
axes_main[0, 0].set_ylabel('職缺數')
axes_main[0, 0].tick_params(axis='both', labelsize=6)

# 子圖 2：按經驗的薪資箱形圖
sns.boxplot(x='experience', y='salary_avg', data=df_salary, ax=axes_main[0, 1], order=exp_order)
axes_main[0, 1].set_title('按經驗要求的薪資')
axes_main[0, 1].set_xlabel('經驗要求')
axes_main[0, 1].set_ylabel('平均薪資 (元)')
axes_main[0, 1].tick_params(axis='x', rotation=45, labelsize=6)

# 子圖 3：按產業的薪資長條圖
sns.barplot(x='mean', y=industry_salary.index, data=industry_salary, ax=axes_main[0, 2])
axes_main[0, 2].set_title('按產業的薪資 (前 10)')
axes_main[0, 2].set_xlabel('平均薪資 (元)')
axes_main[0, 2].set_ylabel('產業')
axes_main[0, 2].tick_params(axis='y', labelsize=6)

# 子圖 4：遠端工作與薪資箱形圖
sns.boxplot(x='is_remote', y='salary_avg', data=df_salary, ax=axes_main[1, 0])
axes_main[1, 0].set_title('遠端工作與薪資')
axes_main[1, 0].set_xlabel('是否遠端工作')
axes_main[1, 0].set_ylabel('平均薪資 (元)')
axes_main[1, 0].set_xticks([0, 1])
axes_main[1, 0].set_xticklabels(['否', '是'], fontsize=6)
axes_main[1, 0].tick_params(axis='x', labelsize=6)

# 子圖 5：技能分佈長條圖
sns.barplot(x='Count', y='Skill', data=skill_counts_df, ax=axes_main[1, 1])
axes_main[1, 1].set_title('熱門技能分佈 (前 10)')
axes_main[1, 1].set_xlabel('出現次數')
axes_main[1, 1].set_ylabel('技能')
axes_main[1, 1].tick_params(axis='y', labelsize=6)

# 子圖 6：經驗與遠端工作熱圖
exp_remote = df.pivot_table(index='experience', columns='is_remote', values='job_id', aggfunc='count', fill_value=0, observed=True)
sns.heatmap(exp_remote, annot=True, cmap='Blues', fmt='d', ax=axes_main[1, 2])
axes_main[1, 2].set_title('經驗與遠端工作熱圖')
axes_main[1, 2].set_xlabel('是否遠端工作')
axes_main[1, 2].set_ylabel('經驗要求')
axes_main[1, 2].set_xticklabels(['否', '是'], fontsize=6)
axes_main[1, 2].tick_params(axis='y', labelsize=6)

fig_main.subplots_adjust(wspace=0.4, hspace=0.5)
plt.savefig('main_analysis.png', dpi=300, bbox_inches='tight')
plt.show()
plt.close(fig_main)
