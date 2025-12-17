# 104 Job Crawler & Raw Data ETL

本目錄 (`step1. 104_jobdata_crawler_final`) 包含職缺爬蟲程式與 Raw Data 匯入工具。

## 1. 爬蟲程式 (`104_crawler_final.py`)

這是基於 `Selenium` 與 `undetected_chromedriver` 的自動化爬蟲，專門針對 104 人力銀行設計。

### 特色

- **抗反爬蟲**: 使用 `undetected_chromedriver` 繞過偵測。
- **斷點續爬**: 自動記錄 `checkpoint.json`，中斷後可接續執行。
- **複合去重**: 使用 `unique_key` (job_id + update_date) 避免重複抓取同一天的相同職缺。
- **加速模式**: 停用圖片載入、採用 Eager Loading 策略。

### 設定方式

打開 `104_crawler_final.py`，編輯開頭的 `SEARCH_CONFIG` 變數：

```python
SEARCH_CONFIG = {
    "active_mode": "category_scan", # 切換模式: category_scan, keyword_scan, custom_url
    "modes": {
        "category_scan": {
            # jobcat 代碼列表
            "params": "jobcat=2007001022,2007001012...",
            "split_by": "jobcat"
        },
        "keyword_scan": {
            # 關鍵字搜尋
            "params": "keyword=Python,Data Scientist...",
            "split_by": "keyword"
        }
    }
}
```

### 執行爬蟲

```bash
# 預設模式 (讀取 Config)
python 104_crawler_final.py

# 無頭模式 (不顯示瀏覽器視窗，適合 VM)
python 104_crawler_final.py --headless
```

### 輸出結果

- **`job_data_master_raw.csv`**: 所有爬取資料的總表 (Master File)。爬蟲會自動將新資料 Append 到此檔案。
- **`logs/`**: 執行日誌。

---

## 2. 增量匯入 Raw Data (`daily_append.py`)

此程式負責將爬下來的 CSV 資料匯入到 MariaDB 的 `rawdata` 資料庫中。它被設計為 **Daemon (常駐程式)**。

### 運作邏輯

1.  每 30 分鐘讀取一次 `job_data_master_raw.csv`。
2.  比對資料庫 `104rawdata` 表中的 `unique_key`。
3.  **僅將新資料** (New Rows) 匯入資料庫，自動略過已存在的資料。

### 設定

確保根目錄 (`WLS/`) 下有 `db_config.py`，且設定正確：

```python
DATABASE = 'rawdata' # 必須確保是連線到 rawdata schema
```

### 執行方式

建議在背景執行，讓它持續監聽 CSV 變化：

```bash
# 前景執行 (測試用)
python daily_append.py

# 背景執行 (Linux/VM)
nohup python daily_append.py > append.log 2>&1 &
```

---

## 自動化工作流 (Workflow)

1.  **啟動爬蟲**: `python 104_crawler_final.py` -> 持續寫入 CSV。
2.  **啟動匯入**: `python daily_append.py` (在背景運行) -> 偵測到 CSV 變大 -> 寫入 DB。
3.  **結果**: 資料將即時流向 MariaDB `rawdata.104rawdata` 表，供後續 Step 2 ETL 使用。
