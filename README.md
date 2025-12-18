# WLS - 就業市場分析平台 (Job Market Analysis Platform)

**專案目標**：打造一個針對 AI 與資料工程相關職缺的自動化分析平台。從爬蟲、資料倉儲、薪資預測模型到前端視覺化儀表板，提供求職者與企業即時的市場洞察。

---

## 📂 專案架構 (Project Structure)

本專案分為四個核心階段，請依序執行：

### [Step 1] 職缺爬蟲 (Crawler)

- **目錄**: `step1_104_jobdata_crawler_final/`
- **功能**: 自動化爬取 104 人力銀行職缺資料。
- **核心檔案**:
  - `104_crawler_final.py`: 主爬蟲程式 (Selenium + undetected_chromedriver)。
  - `checkpoint.json`: 記錄爬取進度，支援斷點續爬。
  - `job_data_master.csv`: 爬取結果的原始資料 (Raw Data)。

### [Step 2] 資料庫與 ETL (Database Management)

- **目錄**: `step2_maria_db_database_management/`
- **功能**: 將原始 CSV 資料清洗、正規化並存入 MariaDB 資料倉儲。
- **核心檔案**:
  - `01_create_schema.py`: 建立資料庫 Schema (Fact/Dim Tables)。
  - `db_config.py`: 資料庫連線設定。
  - `run_etl.py`: 執行完整的 ETL 流程 (Extract, Transform, Load)。
  - `09_create_ml_view.py`: 建立供機器學習與前端使用的 View (`view_ml_dataset`)。
- **詳細說明**: 請參閱 [ETL README](step2_maria_db_database_management/etl_readme.md)。

### [Step 3] 機器學習與預測 (Machine Learning Pipeline)

- **目錄**: `step3_machine_learning_pipeline/`
- **功能**: 訓練薪資預測模型，並對現有職缺進行估價。採用進階的 **Granular Segmentation** 策略。
- **核心檔案**:
  - `ml_data_loader.py`: 從資料庫讀取訓練資料（含薪資正規化）。
  - **`generate_predictions.py`**: **[Production]** 正式預測腳本 (Training + Prediction + DB Write)。
  - `predict_salary_model.py`: **[Development]** 開發與診斷腳本 (用於驗證 R² 與分群效果)。
- **技術亮點**:
  - **細緻分群 (Granular Segmentation)**: 自動區分 `104_Senior`, `104_Junior`, `104_Unspecified`, `CakeResume` 四種情境，採用不同模型預測，R² 最高達 0.52。
  - **防資料洩漏 (Leakage Fix)**: 訓練階段嚴格排除面議/0 元職缺，確保模型準確度。
- **詳細說明**: 請參閱 [ML README](step3_machine_learning_pipeline/README.md)。

### [Step 4] 前端儀表板 (Frontend Dashboard)

- **目錄**: `step4_frontend_dashboard_vm/`
- **功能**: 最終的 Web 應用程式，用於呈現互動式報表。
- **核心檔案**:
  - `app.py`: Flask 後端，直接查詢 MariaDB (含最新的預測數據 `fact_job_predictions`)。
  - `templates/index.html`: ECharts 互動式圖表介面。
  - `deployment_readme.md`: **部署指南 (包含 GCP VM 架設與 Git Sparse Checkout 教學)**。
- **部署**: 此資料夾設計為可獨立部署至 VM，包含完整的 `requirements.txt` 與部署腳本。

---

## 🚀 快速上手 (Quick Start)

### 1. 初始化資料庫

```bash
# 設定 step2/db_config.py
cd "step2_maria_db_database_management"
python 01_create_schema.py
```

### 2. 執行 ETL (匯入資料)

```bash
python run_etl.py
```

### 3. 更新 View

```bash
python 09_create_ml_view.py
```

### 4. 訓練與預測

```bash
cd "../step3_machine_learning_pipeline"
# 產生預測與寫回資料庫
python generate_predictions.py
```

### 5. 啟動前端 (本地測試)

```bash
cd "../step4_frontend_dashboard_vm"
# 需確保目錄下有 db_config.py (參考 deployment_readme.md)
python app.py
```

---

## 🔄 自動化維護 (Maintenance)

日常更新只需執行以下流程：

1. **Crawler** (Step 1) -> 產出新 CSV -> 匯入 Rawdata DB。
2. **ETL** (Step 2) -> 執行 `run_etl.py` 匯入 Warehouse。
3. **Prediction** (Step 3) -> 執行 `generate_predictions.py` (自動讀取新資料、訓練、預測並寫入 DB)。
4. **Frontend** (Step 4) -> 重啟 Web App 以載入最新預測。
