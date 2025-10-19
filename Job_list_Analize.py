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
plt.rcParams['font.size'] = 6  # 保持字型大小

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

# 1. 遠端工作分析
remote_salary = df_salary.groupby('is_remote', observed=True)['salary_avg'].agg(['mean', 'median', 'count'])
print("\n遠端工作薪資統計:")
print(remote_salary)

# 2. 上市上櫃
listed_salary = df_salary.groupby('is_listed', observed=True)['salary_avg'].agg(['mean', 'median', 'count'])
print("\n上市上櫃薪資統計:")
print(listed_salary)

# 3. 職缺新鮮度
df['update_date'] = pd.to_datetime(df['update_date'], format='%m/%d').apply(lambda x: x.replace(year=2025))
date_counts = df['update_date'].value_counts().sort_index()
print("\n職缺更新日期分佈:")
print(date_counts)

# 4. 學歷與經驗
edu_exp_salary = df_salary.groupby(['education', 'experience'], observed=True)['salary_avg'].agg(['mean', 'count']).reset_index()
print("\n學歷與經驗薪資統計:")
print(edu_exp_salary.head(10))

# 5. 福利與產業
industry_tags = df.groupby('industry')['tags'].apply(lambda x: ', '.join(x.dropna())).str.split(', ', expand=True).stack().value_counts().head(10)
print("\n熱門福利 (前 10):")
print(industry_tags)

# 6. 技能提取（優化清理）
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

# 7. 地區與技能
location_skills = df.groupby('location')['job_title'].apply(lambda x: ' '.join(x.dropna()).lower())
location_skill_counts = Counter()
for loc, titles in location_skills.items():
    titles_clean = re.sub(r'工程師|資料|數據|analyst|engineer|scientist|developer|ai\s|人工智慧|機器學習|資深|主任|專案|管理|系統|技術|資訊|研發|助理|中心|維運|應屆|新鮮人|應用|軟體|it|php|ml', '', titles)
    for skill in skills:
        if skill in titles_clean:
            location_skill_counts[(loc, skill)] += titles_clean.count(skill)
location_skill_df = pd.DataFrame(location_skill_counts.most_common(10), columns=['Location_Skill', 'Count'])
location_skill_df[['Location', 'Skill']] = pd.DataFrame(location_skill_df['Location_Skill'].tolist(), index=location_skill_df.index)
print("\n地區與技能 (前 10):")
print(location_skill_df)

# 8. 遠端工作與產業
remote_industry = df[df['is_remote']].groupby('industry')['job_id'].count().sort_values(ascending=False).head(10)
print("\n遠端工作產業分佈 (前 10):")
print(remote_industry)

# 9. 技能與薪資
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

# 10. 經驗與產業熱圖
exp_industry = df.pivot_table(index='industry', columns='experience', values='job_id', aggfunc='count', fill_value=0, observed=True).head(10)
print("\n經驗與產業分佈:")
print(exp_industry)

# 11. 福利與薪資
tags = ['遠端工作', '年終獎金', '分紅配股', '優於勞基法特休', '彈性上下班']
tag_salary = []
for tag in tags:
    tag_jobs = df_salary[df_salary['tags'].str.contains(tag, na=False)]
    if len(tag_jobs) > 0:
        tag_salary.append({
            'Tag': tag,
            'Mean_Salary': tag_jobs['salary_avg'].mean(),
            'Count': len(tag_jobs)
        })
tag_salary_df = pd.DataFrame(tag_salary).sort_values('Mean_Salary', ascending=False)
print("\n福利與薪資 (前 5):")
print(tag_salary_df)

# 12. 技能與學歷
edu_skills = Counter()
for idx, row in df.iterrows():
    title_lower = row['job_title'].lower() if pd.notna(row['job_title']) else ''
    title_clean = re.sub(r'工程師|資料|數據|analyst|engineer|scientist|developer|ai\s|人工智慧|機器學習|資深|主任|專案|管理|系統|技術|資訊|研發|助理|中心|維運|應屆|新鮮人|應用|軟體|it|php|ml', '', title_lower)
    for skill in skills:
        if skill in title_clean:
            edu_skills[(row['education'], skill)] += 1
edu_skills_df = pd.DataFrame(edu_skills.most_common(10), columns=['Edu_Skill', 'Count'])
edu_skills_df[['Education', 'Skill']] = pd.DataFrame(edu_skills_df['Edu_Skill'].tolist(), index=edu_skills_df.index)
print("\n技能與學歷 (前 10):")
print(edu_skills_df)

# 13. 遠端工作與學歷
remote_edu = df[df['is_remote']].groupby('education')['job_id'].count().sort_values(ascending=False)
print("\n遠端工作與學歷分佈:")
print(remote_edu)

# 14. 遠端工作與更新日期
remote_date = df[df['is_remote']].groupby('update_date')['job_id'].count().sort_index()
print("\n遠端工作與更新日期分佈:")
print(remote_date)

# 第一組圖表（前 7 張）
fig1, axes1 = plt.subplots(2, 4, figsize=(28, 14))
fig1.suptitle('資料工程師職缺分析 - 第一部分', fontsize=10)

# 子圖 1：薪資分佈直方圖
sns.histplot(df_salary['salary_avg'], bins=20, kde=True, ax=axes1[0, 0])
axes1[0, 0].set_title('薪資分佈 (月薪)')
axes1[0, 0].set_xlabel('平均薪資 (元)')
axes1[0, 0].set_ylabel('職缺數')
axes1[0, 0].tick_params(axis='both', labelsize=5)

# 子圖 2：按經驗的薪資箱形圖
sns.boxplot(x='experience', y='salary_avg', data=df_salary, ax=axes1[0, 1], order=exp_order)
axes1[0, 1].set_title('按經驗要求的薪資')
axes1[0, 1].set_xlabel('經驗要求')
axes1[0, 1].set_ylabel('平均薪資 (元)')
axes1[0, 1].tick_params(axis='x', rotation=45, labelsize=5)

# 子圖 3：地區分佈圓餅圖
location_counts = df['location'].value_counts().head(10)
location_counts.plot.pie(autopct='%1.1f%%', ax=axes1[0, 2], textprops={'fontsize': 5})
axes1[0, 2].set_title('職缺地區分佈 (前 10)')
axes1[0, 2].set_ylabel('')

# 子圖 4：產業分佈長條圖
sns.barplot(x=industry_counts.values, y=industry_counts.index, ax=axes1[0, 3])
axes1[0, 3].set_title('職缺產業分佈 (前 10)')
axes1[0, 3].set_xlabel('職缺數')
axes1[0, 3].set_ylabel('產業')
axes1[0, 3].tick_params(axis='y', labelsize=5)

# 子圖 5：按學歷的薪資箱形圖
edu_order = ['高中', '專科', '大學', '碩士', '學歷不拘']
df_salary['education'] = pd.Categorical(df_salary['education'], categories=edu_order, ordered=True)
sns.boxplot(x='salary_avg', y='education', data=df_salary, ax=axes1[1, 0], order=edu_order)
axes1[1, 0].set_title('按學歷的薪資分佈')
axes1[1, 0].set_xlabel('平均薪資 (元)')
axes1[1, 0].set_ylabel('學歷')
axes1[1, 0].tick_params(axis='y', labelsize=5)

# 子圖 6：遠端工作薪資箱形圖
sns.boxplot(x='is_remote', y='salary_avg', data=df_salary, ax=axes1[1, 1])
axes1[1, 1].set_title('遠端工作與薪資')
axes1[1, 1].set_xlabel('是否遠端工作')
axes1[1, 1].set_ylabel('平均薪資 (元)')
axes1[1, 1].set_xticks([0, 1])
axes1[1, 1].set_xticklabels(['否', '是'], fontsize=5)

# 子圖 7：上市上櫃薪資箱形圖
sns.boxplot(x='is_listed', y='salary_avg', data=df_salary, ax=axes1[1, 2])
axes1[1, 2].set_title('上市上櫃與薪資')
axes1[1, 2].set_xlabel('是否上市上櫃')
axes1[1, 2].set_ylabel('平均薪資 (元)')
axes1[1, 2].set_xticks([0, 1])
axes1[1, 2].set_xticklabels(['否', '是'], fontsize=5)

# 關閉多餘子圖
axes1[1, 3].axis('off')

# 調整第一組布局
fig1.subplots_adjust(wspace=0.5, hspace=0.6)
plt.savefig('job_analysis_part1.png', dpi=300, bbox_inches='tight')
plt.show()
plt.close(fig1)

# 第二組圖表（後 7 張）
fig2, axes2 = plt.subplots(2, 4, figsize=(28, 14))
fig2.suptitle('資料工程師職缺分析 - 第二部分', fontsize=10)

# 子圖 8：職缺標題詞雲
wordcloud = WordCloud(font_path='C:/Windows/Fonts/msjh.ttc', width=400, height=200, background_color='white').generate(' '.join(df['job_title'].dropna()))
axes2[0, 0].imshow(wordcloud, interpolation='bilinear')
axes2[0, 0].set_title('職缺標題詞雲')
axes2[0, 0].axis('off')

# 子圖 9：遠端工作與產業
sns.barplot(x=remote_industry.values, y=remote_industry.index, ax=axes2[0, 1])
axes2[0, 1].set_title('遠端工作產業分佈 (前 10)')
axes2[0, 1].set_xlabel('職缺數')
axes2[0, 1].set_ylabel('產業')
axes2[0, 1].tick_params(axis='y', labelsize=5)

# 子圖 10：經驗與產業熱圖
sns.heatmap(exp_industry, annot=True, cmap='Blues', ax=axes2[0, 2])
axes2[0, 2].set_title('經驗與產業分佈熱圖')
axes2[0, 2].set_xlabel('經驗要求')
axes2[0, 2].set_ylabel('產業')
axes2[0, 2].tick_params(axis='x', rotation=45, labelsize=5)

# 子圖 11：福利與薪資
sns.barplot(x='Mean_Salary', y='Tag', data=tag_salary_df, ax=axes2[0, 3])
axes2[0, 3].set_title('福利與薪資 (前 5)')
axes2[0, 3].set_xlabel('平均薪資 (元)')
axes2[0, 3].set_ylabel('福利')
axes2[0, 3].tick_params(axis='y', labelsize=5)

# 子圖 12：技能與學歷
sns.barplot(x='Count', y='Skill', hue='Education', data=edu_skills_df, ax=axes2[1, 0])
axes2[1, 0].set_title('技能與學歷 (前 10)')
axes2[1, 0].set_xlabel('出現次數')
axes2[1, 0].set_ylabel('技能')
axes2[1, 0].legend(fontsize=5)
axes2[1, 0].tick_params(axis='y', labelsize=5)

# 子圖 13：遠端工作與學歷
sns.barplot(x=remote_edu.values, y=remote_edu.index, ax=axes2[1, 1])
axes2[1, 1].set_title('遠端工作與學歷分佈')
axes2[1, 1].set_xlabel('職缺數')
axes2[1, 1].set_ylabel('學歷')
axes2[1, 1].tick_params(axis='y', labelsize=5)

# 子圖 14：遠端工作與更新日期
sns.barplot(x=remote_date.index, y=remote_date.values, ax=axes2[1, 2])
axes2[1, 2].set_title('遠端工作與更新日期')
axes2[1, 2].set_xlabel('更新日期')
axes2[1, 2].set_ylabel('職缺數')
axes2[1, 2].tick_params(axis='x', rotation=45, labelsize=5)

# 關閉多餘子圖
axes2[1, 3].axis('off')

# 調整第二組布局
fig2.subplots_adjust(wspace=0.5, hspace=0.6)
plt.savefig('job_analysis_part2.png', dpi=300, bbox_inches='tight')
plt.show()
plt.close(fig2)
