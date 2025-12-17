# MySQL/MariaDB Data Warehouse Management

本目錄包含 Job Recommendation System 的資料倉儲管理程式碼，負責資料庫的建立、ETL (資料抽取、轉換、載入) 流程以及資料維護。

## 檔案說明

### 1. 核心流程 (Core Pipeline)

- **`01_create_schema.py`**
  - **初始化**: 負責建立 `job_data_warehouse` 資料庫與所有資料表 (Dimensions, Facts, Bridges)。
  - 定義了 SQLAlchemy ORM 模型 (`DimCompany`, `FactJobPosting` 等)。
- **`02_run_etl.py`**
  - **主程式**: 執行完整的 ETL 流程。
  - **Extract**: 從 `job_source` 資料庫讀取原始爬蟲資料。
  - **Transform**: 使用 `etl_transformers.py` 清洗資料、標準化地區/薪資、對應維度表 ID。
  - **Load**: 將處理後的資料寫入 `fact_job_postings` 及相關 Bridge Tables。
- **`09_create_ml_view.py`**
  - **建立 View**: 建立 `view_ml_dataset`，這是一個已去重 (Deduplicated) 並正規化的視圖，專供 ML Pipeline 使用。

### 2. 資料維護與修正 (Maintenance & Patches)

- `05_cleanup_bad_ids.py`: 清除格式錯誤的 Job ID。
- `06_patch_locations.py`: 修正地區資料 (如國家名稱標準化)。
- `07_patch_experience.py`: 修正工作經驗欄位的格式。
- `08_patch_remote_salary.py`: 修正遠端工作與薪資欄位的資料品質。

### 3. 驗證與檢查 (Verification)

- `03_inspect_data.py`: 快速查看資料庫中的前幾筆資料，確認寫入是否成功。
- `04_verify_warehouse.py`: 執行完整的資料完整性檢查，包含 Row Count、Null Value 檢查以及維度關聯性驗證。

### 4. 輔助模組 (Utils)

- `etl_mappings.py`: 定義原始資料欄位與目標資料庫欄位的對應關係 (Mappings)。
- `etl_transformers.py`: 包含具體的資料轉換邏輯函數 (如 `parse_salary`, `clean_html` 等)。
- `db_config.py` (位於上層目錄): 資料庫連線設定檔。

## 執行流程 (Workflow)

如果是全新環境，請依序執行：

1.  **建立 Schema**:
    ```bash
    python 01_create_schema.py
    ```
2.  **執行 ETL**:
    ```bash
    python 02_run_etl.py
    ```
3.  **建立 ML View**:
    ```bash
    python 09_create_ml_view.py
    ```
4.  **驗證資料**:
    ```bash
    python 04_verify_warehouse.py
    ```
