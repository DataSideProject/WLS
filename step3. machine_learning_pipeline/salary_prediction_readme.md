# Machine Learning Pipeline Documentation

本目錄包含薪資預測模型的完整流程，從資料載入、模型訓練、預測產出到分析報表生成。

## 檔案說明

### 1. 資料載入 (Core)

- **`ml_data_loader.py`**
  - 負責從資料庫 View (`view_ml_dataset`) 讀取原始職缺資料。
  - **薪資正規化 (Normalization)**: 自動排除時薪/日薪資料，並將「年薪」除以 13 換算為**月薪**基準。
  - **資料整合**: 自動 Join 技能 (`bridge_job_skills`)、類別 (`bridge_job_categories`) 與福利 (`bridge_job_benefits`) 表，產出扁平化的 DataFrame 供模型使用。

### 2. 模型驗證與實驗 (Experimentation)

- **`predict_salary_model.py`**
  - 用於開發階段的模型訓練與驗證。
  - 執行特徵工程 (Feature Engineering)，包含 TF-IDF (工作描述)、One-Hot Encoding (地區/公司/技能/福利)。
  - 使用 Ensemble 模型 (RandomForest + XGBoost + GradientBoosting + CatBoost)。
  - 產出效能報告 (`salary_prediction_report.txt`) 與 R²/MAE/RMSE 指標，協助評估模型準確度。

### 3. 正式預測 (Production)

- **`generate_predictions.py`**
  - 正式環境使用的預測腳本。
  - 讀取最新資料，重新訓練模型，並對所有職缺進行薪資預測。
  - **歷史紀錄模式 (History Mode)**: 採 **Append** 方式寫入資料庫 `fact_job_predictions` 表，保留每次執行的預測快照 (Snapshot)，便於追蹤趨勢。

### 4. 數據呈現 (Frontend)

- **`frontend_dashboard_vm/`**
  - 包含獨立運行的 Flask App (`app.py`)。
  - 直接連接資料庫讀取 `view_ml_dataset` 與 `fact_job_predictions`，即時計算 Dashboard 數據。
  - (原 `generate_analysis.py` 邏輯已整合至前端 App 中，不再需要單獨執行)

### 5. 輔助工具 (Utils)

- `export_db_to_csv.py`: 將資料庫完整內容匯出為 CSV (備份/除錯用)。
- `inspect_preds.py`: 快速查看資料庫中最新的預測結果筆數與範例。

## 執行流程 (Workflow)

若要更新整個 Pipeline，請依序執行：

1.  **產生預測** (更新資料庫):
    ```bash
    python generate_predictions.py
    ```
2.  **更新報表** (更新 Dashboard):
    ```bash
    python generate_analysis.py
    ```

## 最近更新摘要

- **薪資單位**: 全面統一為 **月薪 (Monthly Salary)**。
- **預測紀錄**: 改為保留歷史紀錄，不會清空舊的預測值。
- **特徵增強**: 加入「公司福利 (Benefits)」作為預測特徵。
