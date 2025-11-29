# 3.預測結果檢查_加強版.py
# 完整可視化 + 統計分析 + 異常檢測

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
import warnings
warnings.filterwarnings("ignore")
df.loc[df['salary_min'].isna() & df['salary_max'].notna(), 'data_type'] = '預測起薪'
df.loc[df['salary'].astype(str).str.contains('面議', na=False), 'data_type'] = '面議預測'

# 計算平均薪資
df['salary_avg'] = df[['salary_min', 'salary_max']].mean(axis=1)

# ====================== 2. 整體統計 ======================
print("\n" + "="*60)
print("整體薪資統計")
print("="*60)
stats_df = df.groupby('data_type')['salary_avg'].agg(['count', 'mean', 'std', 'min', 'max']).round(0)
print(stats_df)

# ====================== 3. 圖表 1：薪資分布比較 ======================
plt.figure(figsize=(15, 10))

# 子圖1：直方圖 + KDE
plt.subplot(2, 3, 1)
for typ, color in zip(['真實薪資', '面議預測'], ['skyblue', 'orange']):
    subset = df[df['data_type'] == typ]
    sns.histplot(subset['salary_avg'], kde=True, label=typ, alpha=0.6, color=color, bins=50)
plt.title('薪資分布比較（真實 vs 面議預測）', fontsize=14, fontweight='bold')
plt.xlabel('平均月薪 (元)')
plt.ylabel('職缺數')
plt.legend()

# 子圖2：箱形圖
plt.subplot(2, 3, 2)
sns.boxplot(data=df[df['data_type'].isin(['真實薪資', '面議預測'])], x='data_type', y='salary_avg', palette=['skyblue', 'orange'])
plt.title('薪資箱形圖')
plt.ylabel('平均月薪 (元)')

# 子圖3：累積分布
plt.subplot(2, 3, 3)
for typ, color in zip(['真實薪資', '面議預測'], ['blue', 'red']):
    subset = df[df['data_type'] == typ]['salary_avg'].sort_values()
    plt.plot(subset.values, np.arange(len(subset))/len(subset), label=typ, color=color)
plt.title('累積分布函數 (CDF)')
plt.xlabel('平均月薪 (元)')
plt.ylabel('累積比例')
plt.legend()
plt.grid(True, alpha=0.3)

# ====================== 4. 圖表 2：Top 10 職務薪資比較 ======================
plt.subplot(2, 3, 4)
top_jobs = df['job_title'].value_counts().head(10).index
job_stats = df[df['job_title'].isin(top_jobs)].groupby(['job_title', 'data_type'])['salary_avg'].mean().unstack()
job_stats.plot(kind='barh', ax=plt.gca(), color=['skyblue', 'orange', 'lightgray'], width=0.8)
plt.title('Top 10 職務平均薪資比較')
plt.xlabel('平均月薪 (元)')
plt.legend(title='資料類型')

# ====================== 5. 圖表 3：薪資範圍散佈圖 ======================
plt.subplot(2, 3, 5)
real = df[df['data_type'] == '真實薪資']
pred = df[df['data_type'] == '面議預測']
plt.scatter(real['salary_min'], real['salary_max'], alpha=0.5, label='真實', color='blue', s=10)
plt.scatter(pred['salary_min'], pred['salary_max'], alpha=0.5, label='面議預測', color='red', s=10)
plt.plot([20000, 150000], [20000, 150000], 'k--', label='y=x')
plt.title('薪資範圍散佈圖')
plt.xlabel('起薪')
plt.ylabel('上限')
plt.legend()

# ====================== 6. 圖表 4：異常值檢測 ======================
plt.subplot(2, 3, 6)
df['range'] = df['salary_max'] - df['salary_min']
outliers = df[df['range'] < 5000]
plt.scatter(df['salary_avg'], df['range'], c='green', alpha=0.5, s=10, label='正常')
if len(outliers) > 0:
    plt.scatter(outliers['salary_avg'], outliers['range'], c='red', s=20, label=f'異常 ({len(outliers)}筆)')
plt.title('薪資範圍 vs 平均薪資')
plt.xlabel('平均月薪')
plt.ylabel('薪資範圍')
plt.legend()

plt.tight_layout()
plt.show()

# ====================== 7. 異常值報告 ======================
print("\n" + "="*60)
print("異常值檢測報告")
print("="*60)
outliers = df[df['range'] < 5000]
print(f"薪資範圍 < 5000 元：{len(outliers)} 筆")
if len(outliers) > 0:
    print("\n範例：")
    print(outliers[['job_title', 'company', 'salary_min', 'salary_max', 'data_type']].head(10))

# ====================== 8. 統計檢定：真實 vs 預測是否有顯著差異 ======================
print("\n" + "="*60)
print("統計檢定：真實 vs 面議預測")
print("="*60)
real_avg = df[df['data_type'] == '真實薪資']['salary_avg']
pred_avg = df[df['data_type'] == '面議預測']['salary_avg']

t_stat, p_val = stats.ttest_ind(real_avg, pred_avg, equal_var=False)
print(f"t-test: t = {t_stat:.2f}, p-value = {p_val:.2e}")
if p_val < 0.05:
    print("→ 兩者平均薪資有顯著差異（p < 0.05）")
else:
    print("→ 兩者平均薪資無顯著差異")

# ====================== 9. 輸出摘要報告 ======================
summary = {
    '總職缺數': len(df),
    '真實薪資': len(df[df['data_type'] == '真實薪資']),
    '面議預測': len(df[df['data_type'] == '面議預測']),
    '真實平均薪資': real_avg.mean().round(0),
    '預測平均薪資': pred_avg.mean().round(0),
    '異常職缺數': len(outliers)
}
print("\n" + "="*60)
print("預測摘要報告")
print("="*60)
for k, v in summary.items():
    print(f"{k}：{v}")

# 儲存摘要
pd.Series(summary).to_csv('prediction_summary.csv')
print("\n摘要已儲存：prediction_summary.csv")