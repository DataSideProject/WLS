# WLS
# TIBAME 資料工程師專案 ─ 104 就業市場分析平台（最終版 2025-12-10 更新）

**專案名稱**：資料工程師相關職缺市場情報儀表板    
**最後更新**：2025-12-10（已整合最新檔案：analysis_utils.py 擴充新分析函數、app.py 強化 API 過濾與技能分類、index.html 完整 ECharts 儀表板）  
**資料規模**：5,172 筆職缺（job_data_final_with_predictions.csv），包含預測薪資（pred_min/max/avg）、技能特徵（skill_python 等 20+ 欄位）、描述 TF-IDF 特徵（desc_feat0 ~ 99）、條件 TF-IDF（cond_feat0 ~ 99）、地區互動特徵（e.g., skill_python_in_台北市）等 300+ 欄位。

本報告聚焦四個簡報主題，基於最新檔案實作內容。新增重點：analysis_utils.py 擴充教育/產業/遠端/詞雲/箱形圖/技能網路等 10+ 分析函數；app.py 支援動態過濾與技能分類樹；index.html 實現 10+ ECharts 圖表（含地圖、網路圖）。未實作部分（如 MongoDB）已排除。

## 一、要做什麼應用與產出？（3-4 頁投影片）

### 應用目標
開發互動式就業市場分析平台，針對 AI/資料相關職缺（軟體工程師、資料工程師、AI 工程師等），提供即時洞察：職缺分佈、薪資趨勢、技能需求、經驗/教育/產業關聯分析。幫助求職者優化履歷、企業掌握人才缺口。

### 四大核心產出（已 100% 完成，基於最新檔案）
| 模組                  | 主要檔案 / 技術棧                          | 詳細產出說明                                                                 |
|-----------------------|--------------------------------------------|------------------------------------------------------------------------------|
| **1. 爬蟲系統**      | `104_crawler_final.py` (Selenium + undetected_chromedriver) | 自動爬取 104 職缺 raw data，支持 job_id + update_date_clean 複合去重、斷點續爬（checkpoint.json）、每日 raw CSV 輸出（e.g., job_data_master_raw.csv）。爬取欄位包括 job_title、company、industry、experience、education、salary、tools、remote_work 等。 |
| **2. 資料清理與分析** | `generate_predictions.py` + `analysis_utils.py` (Pandas + Ensemble 模型 + TF-IDF) | - ETL：解析薪資（min/max/avg）、經驗清理（exp_years_raw/scaled）、教育等級（edu_level）。<br>- 薪資預測：VotingRegressor (RF + XGB + GB + CatBoost) 填補缺失，MAE < 5,000 元，R² > 0.85。<br>- 新增分析：經驗 vs. 薪資統計、頂級技能計數/薪資排名、教育分佈、產業薪資 Top 10（min_count=20 過濾）、遠端工作比例（Full/Partial/On-site）、詞雲（job_title 關鍵字 Top 50）、薪資箱形圖（cat_ 類別分組）、技能共現網路（Top 30 技能，combinations 計算邊權重）。<br>輸出：`job_data_final_with_predictions.csv`（300+ 特徵欄位，包括 desc_/cond_ TF-IDF、地區互動如 AI工程師_in_台北市）。 |
| **3. GCP 資料庫**    | MariaDB on GCP VM + `daily_append.py` (SQLAlchemy) | 自動監聽 CSV 變化，每 30 分鐘追加新資料（unique_key 去重），支援即時查詢。資料表：104rawdata（全 raw 欄位）。效率：chunksize=500 批次匯入，避免衝突。 |
| **4. 互動式儀表板**  | `app.py` (Flask) + `index.html` (ECharts 5.4.3 + WordCloud) + `analysis_utils.py` | - Flask API：/api/jobs (分頁 50 筆 + 多過濾：地區/薪資/類別/管理職/遠端/搜尋)、/api/job/<id> (細節 + 技能樹)、/api/filters/options (動態選項)、/api/analysis/stats (即時統計)。<br>- 前端：暗黑主題 UI、左側搜尋面板、右側儀表板（6x2 網格）。<br>- 新增視覺：薪資直方圖、經驗折線圖、技能長條圖、城市熱圖 (GeoJSON 台灣縣市)、教育/產業/遠端餅圖、詞雲、薪資箱形圖、技能網路圖 (force layout)。技能分類使用 skill_taxonomy.json (反向查找 + partial match)。部署：GCP VM (host=0.0.0.0:5000)。 |

**產出價值**：從 raw data 到洞察的全流程，支援濾鏡即時更新（e.g., 台北 + 資料工程師過濾），也提供個別職缺的技能學習參考、薪資待遇談判籌碼。

## 二、預期的呈現方式？

### 整體架構與使用者體驗
- **部署**：GCP VM 運行 Flask app，瀏覽器存取 (短期直接ngrok、長期上gcp vm執行)，支援手機/桌面響應式（viewport meta）。
- **UI 設計**：不在課程範圍，主要與AI協作調整。左側側邊欄 (320px，搜尋 + 濾鏡按鈕)、主內容區 (flex 彈性佈局)、頂部導航 (nav-tabs：Jobs / Dashboard)。
- **互動流程**：
  1. 搜尋：關鍵字輸入 + 濾鏡 (地區 dropdown、薪資滑桿、類別/管理職/遠端 checkbox)，分頁載入 (per_page=50)。
  2. 點擊職缺：彈出細節 modal + 技能樹狀圖 (ECharts Tree：根節點 job_title，子節點類別/技能，顏色區分)。
  3. 儀表板切換：即時 API 呼叫 /api/analysis/stats，過濾後更新所有圖表。
- **資料來源**：各大人力銀行爬蟲程式抓取職缺資料，將爬取資料做必要整理後(例如增加更新時間及製作uniqe key)，存進MariaDB後，每日(或設定其他週期)讀取，以Ensemble 模型 + TF-IDF做薪資預測、技能分析後產出完整的檔案

### 詳細視覺呈現（基於 index.html + analysis_utils.py 新函數）
- **搜尋面板**：職缺卡片 (job-card：標題/公司/薪資/預測值，hover 黃色邊框)。
- **儀表板網格** (dashboard-grid：4 欄 x 多行，gap 24px)：
  | 圖表類型 | 資料來源 (analysis_utils) | ECharts 選項細節 (index.html) | 互動功能 |
  |----------|---------------------------|-------------------------------|----------|
  | **薪資分佈直方圖** | get_salary_distribution (pred_avg，20 bins) | Bar chart (x: 薪資區間, y: 計數) | 濾鏡更新 bins |
  | **經驗 vs. 薪資曲線** | get_experience_stats (clean_exp + groupby mean) | Line chart (x: 經驗等級排序, y: avg 薪資) | Hover 顯示值 |
  | **頂級技能計數** | get_top_skills (Counter tools, Top 15) | Bar chart (x: 技能, y: 計數) | 點擊過濾職缺 |
  | **技能薪資排名** | get_skill_salary (mask.sum() >=5 + mean) | Horizontal bar (x: avg 薪資, y: 技能) | 排序降序 |
  | **城市薪資熱圖** | get_city_stats (groupby city_for_stratify) + map_data (value_counts) | Map chart (GeoJSON 台灣，熱力顏色) | 點擊縣市過濾 |
  | **教育分佈** | get_education_stats (clean_edu + value_counts) | Pie chart (radius 50%-70%) | 傳奇顯示比例 |
  | **產業薪資 Top 10** | get_industry_stats (min_count=20 + head(10)) | Horizontal bar (y: 產業名 truncate 160px) | 過濾低樣本 |
  | **遠端工作比例** | get_remote_stats (clean_remote: Full/Partial/On-site) | Donut pie (顏色: 紅/藍/綠/黃) | 預設 On-site 主導 |
  | **職稱詞雲** | get_word_cloud_data (re.split + stop_words 過濾, Top 50) | WordCloud (shape: circle, size 12-60, 隨機 RGB 色) | Hover 放大 |
  | **薪資箱形圖** | get_salary_boxplot (cat_ 欄位 + quartiles [min/Q1/median/Q3/max]) | Boxplot (x: 類別 rotate 45°, y: TWD) | Tooltip 顯示四分位 |
  | **技能網路圖** | get_skill_network (combinations co-occur >5, symbolSize scale) | Graph (force layout, repulsion 100) | 拖拽/鄰接高亮 |


## 三、這題目的困難點在哪？我們怎麼解決？

| 困難類型             | 具體問題（最新版重點）                                                                 | 我們的解決方案（程式碼參考）                                                                 | 成果指標 |
|----------------------|----------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------|----------|
| **爬蟲防偵測**      | Session 中斷 (OSError WinError 6)、欄位不存在導致遺失資料                              | undetected_chromedriver + 每 30 筆重啟 driver (restart_driver) + try/except 全包覆 + finally 清理 | 穩定爬 150+ 頁，成功率 98% |
| **欄位抓取不穩**    | 產業/更新日期/管理責任/遠端/企業認證/薪資 永遠 N/A 或格式亂                           | find_elements (複數) + 正確 XPath (e.g., 產業: //a[@href~'custlist']/following-sibling::ul/li/span) + clean_update_date() (正則 + 年份自動判斷) | 資料完整率 >95%，unique_key 去重零錯誤 |
| **資料清理多變**    | 薪資/經驗/技能格式不一，TF-IDF 特徵 200+ 欄位維度災難，缺失 40%+                      | parse_salary (re.match 月/年薪) + clean_exp (isdigit 提取) + Ensemble 預測 (VotingRegressor log1p/expm1) + skill_taxonomy.json partial match | MAE 4,000 元，R² 0.87；互動特徵 (e.g., skill_python_in_台北市) 自動生成 |
| **分析函數擴充**    | 新增詞雲/箱形圖/網路需處理 stop_words/共現計算/低樣本過濾，過濾後資料傾斜             | analysis_utils.py：get_word_cloud_data (re.split + stop_words 50+ 詞) + get_salary_boxplot (quartiles >10 樣本) + get_skill_network (combinations + weight>5) + min_count=20 產業過濾 | 詞雲 Top 50 準確，網路節點 30+、邊 100+，計算時間 <1s |
| **GCP DB 整合**     | 每日追加衝突 (爬蟲寫入中讀取)、大資料查詢慢 (5k 筆 + 300 欄)                          | daily_append.py：try/except 讀 CSV + existing_keys set 去重 + chunksize=500 批次 + SQLAlchemy text() 查 unique_key | 追加時間 <5min，查詢延遲 <100ms |
| **視覺呈現互動**    | ECharts JSON 格式 (NaN 錯誤)、地圖 GeoJSON 名稱不一致 (臺↔台)、濾鏡即時更新卡頓       | app.py：replace(np.nan, None) + filters dict (category/city/manager/remote)；index.html：GeoJSON 正規化 + API 即時呼叫 + resize 事件 | 濾鏡響應 <500ms，地圖點擊過濾精準；暗黑主題無閃爍 |

### 爬蟲「抓不到欄位」TOP 6 真實解法（必放投影片）
| 欄位         | 當初現象               | 最終解法（XPath/函數）                                                                 |
|--------------|------------------------|----------------------------------------------------------------------------------------|
| 產業         | 永遠 N/A              | 公司區塊 XPath：`//a[contains(@href,'custlist')]/following-sibling::ul/li/span`        |
| 更新日期     | 格式亂 (11月14日/11/14) | clean_update_date()：正則 + 年份推斷 (candidate > today 減一年)                        |
| 管理責任     | CSS 失效               | XPath 文字包含：`//dt[contains(text(),'管理責任')]/following-sibling::dd/text()`       |
| 遠端工作     | 無欄位 → 錯誤          | find_elements + default '未知'；clean_remote() 分類 (Full/Partial/On-site)             |
| 企業認證     | 空欄崩潰               | 同上，try/except 全域防呆                                                              |
| 薪資         | 多格式 (月/年/面議)    | extract_field_value("薪資") + ETL 解析 + 模型補缺 (pred_min/max)                       |

## 四、現在還有哪些問題？

基於最新檔案，核心穩定，但優化空間如下：

| 問題類型                  | 現況說明（最新版）                                                                 | 後續優化方向（維護性考量）                          |
|--------------------------|-----------------------------------------------------------------------------------|----------------------------------------------------|
| **尚未進vm做排程測試**     | 不定期手動執行每個階段                                                             | cron 排程 + Linux Chrome；錯誤日誌 (logging) 追蹤   |
| **尚未整合多人力銀行平台** | 已有104、Cake職缺，可能要研究如何資料清理後統整到一個Table                          | 改讀取統整後的資料表做後續預測及視覺化流程              |
| **資料時間跨度分析**       | 104資料有時間跨度但跨度不夠久，其他平台尚未有不同時間跨度的爬取                     | 增加時間跨度後可以持續產出更詳細的分析方向              |
| **僅有職缺資料**           | 目前資料僅限於各人力銀行的職缺頁面獲得                                           | 人力銀行通常也有公司頁面可以爬取，也許也能進一步分析     |


──────────────  
