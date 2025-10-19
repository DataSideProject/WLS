import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib import font_manager
from collections import Counter

# 設定中文字型
plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei']  # Windows 用微軟正黑體
# plt.rcParams['font.sans-serif'] = ['PingFang SC']  # Mac 用蘋方（取消註解如果用 Mac）
# plt.rcParams['font.sans-serif'] = ['Noto Sans CJK JP']  # Linux 用 Noto Sans（取消註解如果用 Linux）
plt.rcParams['axes.unicode_minus'] = False  # 解決負號顯示問題

# 載入 CSV 檔案（替換成你的實際檔案名稱）
file_path = 'job_data_jobcat_1022_20251019.csv'  # 例如你的檔案
df = pd.read_csv(file_path)

# 填補缺失薪資（根據經驗年資）
def fill_salary(row):
    if pd.isna(row['salary_avg']):
        experience = row['experience']
        if '1年' in experience or '2年' in experience or '3年' in experience:
            return 57000  # 1-3 年中位數
        elif '4年' in experience or '5年' in experience:
            return 60000  # 3-5 年中位數
        elif '6年' in experience or '7年' in experience or '8年' in experience or '9年' in experience or '10年' in experience:
            return 65000  # 5-10 年中位數
        else:
            return None  # 其他情況不填補
    return row['salary_avg']

# 應用填補邏輯
df['salary_avg'] = df.apply(fill_salary, axis=1)

# 檢查數據
print("總職缺數:", len(df))
print("前 5 筆數據:")
print(df.head())
print("欄位資訊:")
print(df.info())
print("缺失值統計:")
print(df.isnull().sum())

# 過濾掉仍無薪資資訊的職缺
df_salary = df.dropna(subset=['salary_avg'])
print("有薪資資訊的職缺數:", len(df_salary))

# 按經驗分組的薪資
salary_by_exp = df_salary.groupby('experience')['salary_avg'].agg(['mean', 'median', 'count']).sort_values('mean', ascending=False)
print("按經驗分組的薪資:")
print(salary_by_exp)

# 按地區分組的薪資（前 10）
salary_by_location = df_salary.groupby('location')['salary_avg'].agg(['mean', 'median', 'count']).sort_values('count', ascending=False).head(10)
print("按地區分組的薪資 (前 10):")
print(salary_by_location)

# 產業分佈（前 10）
industry_counts = df['industry'].value_counts().head(10)
print("\n產業分佈 (前 10):")
print(industry_counts)

# 按產業分組的薪資（前 10）
industry_salary = df_salary.groupby('industry')['salary_avg'].agg(['mean', 'median', 'count']).sort_values('count', ascending=False).head(10)
print("\n按產業分組的薪資 (前 10，按職缺數排序):")
print(industry_salary)

# 熱門技能（從 tags 欄位，前 10）
all_tags = []
for tags in df['tags'].dropna():
    split_tags = [tag.strip() for tag in tags.split(',')]
    all_tags.extend(split_tags)
tag_counts = pd.DataFrame(Counter(all_tags).most_common(10), columns=['Tag', 'Count'])
print("\n熱門標籤 (前 10):")
print(tag_counts)

# 創建子圖網格（2 行 3 列）
fig, axes = plt.subplots(2, 3, figsize=(18, 10))
fig.suptitle('資料工程師職缺分析', fontsize=16)

# 子圖 1：薪資分佈直方圖
sns.histplot(df_salary['salary_avg'], bins=20, kde=True, ax=axes[0, 0])
axes[0, 0].set_title('薪資分佈 (月薪)')
axes[0, 0].set_xlabel('平均薪資 (元)')
axes[0, 0].set_ylabel('職缺數')

# 子圖 2：按經驗的薪資箱形圖
sns.boxplot(x='experience', y='salary_avg', data=df_salary, ax=axes[0, 1])
axes[0, 1].set_title('按經驗要求的薪資')
axes[0, 1].set_xlabel('經驗要求')
axes[0, 1].set_ylabel('平均薪資 (元)')
axes[0, 1].tick_params(axis='x', rotation=45)

# 子圖 3：地區分佈圓餅圖
location_counts = df['location'].value_counts().head(10)
location_counts.plot.pie(autopct='%1.1f%%', ax=axes[0, 2])
axes[0, 2].set_title('職缺地區分佈 (前 10)')
axes[0, 2].set_ylabel('')

# 子圖 4：產業分佈長條圖
sns.barplot(x=industry_counts.values, y=industry_counts.index, ax=axes[1, 0])
axes[1, 0].set_title('職缺產業分佈 (前 10)')
axes[1, 0].set_xlabel('職缺數')
axes[1, 0].set_ylabel('產業')

# 子圖 5：按產業的薪資箱形圖
sns.boxplot(x='salary_avg', y='industry', data=df_salary[df_salary['industry'].isin(industry_counts.index)], ax=axes[1, 1])
axes[1, 1].set_title('按產業的薪資分佈 (前 10)')
axes[1, 1].set_xlabel('平均薪資 (元)')
axes[1, 1].set_ylabel('產業')

# 子圖 6：熱門標籤長條圖
sns.barplot(x='Count', y='Tag', data=tag_counts, ax=axes[1, 2])
axes[1, 2].set_title('熱門標籤分佈 (前 10)')
axes[1, 2].set_xlabel('出現次數')
axes[1, 2].set_ylabel('技能')

# 調整布局，防止重疊
plt.tight_layout(rect=[0, 0, 1, 0.95])
plt.show()

# 保存圖表為圖片
plt.savefig('job_analysis_combined.png', dpi=300, bbox_inches='tight')
print("圖表已保存為 'job_analysis_combined.png'")