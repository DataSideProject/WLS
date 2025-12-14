# 現有 VM (n1-standard-1) 佈署指南

你目前的 VM 規格為 `n1-standard-1` (1 vCPU, 3.75 GB RAM)。
**結論：可以用，但非常緊繃。**

由於你的專案包含「機器學習模型訓練」與「Chrome 爬蟲」，這兩者都是吃記憶體怪獸。
若要在這台機器上穩定執行，**務必** 執行以下優化步驟（特別是 **增加 SWAP 虛擬記憶體**），否則很高機率會因為 OOM (Out Of Memory) 導致 MariaDB 被系統強制殺掉。

---

## 步驟 1：設定 SWAP (虛擬記憶體) 🚨 **最重要的一步**

因為實體記憶體只有 3.75GB，我們要從硬碟切 4GB 出來當作備用記憶體。

在 VM Terminal 端執行：

```bash
# 1. 建立 4GB 的 swap 檔案
sudo fallocate -l 4G /swapfile

# 2. 設定權限 (安全考量)
sudo chmod 600 /swapfile

# 3. 格式化為 swap
sudo mkswap /swapfile

# 4. 啟用 swap
sudo swapon /swapfile

# 5. 確認是否生效 (看到 Swap 行有 4.0G 即成功)
free -h

# 6. 設定開機自動掛載
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

---

## 步驟 2：安裝必要環境

```bash
# 更新系統
sudo apt-get update && sudo apt-get install -y wget unzip git python3-venv python3-pip

# 安裝 Chrome (爬蟲用)
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt-get install -y ./google-chrome-stable_current_amd64.deb

# 檢查 Chrome 版本
google-chrome --version
```

---

## 步驟 3：部署程式碼

```bash
# 1. 進入你的專案目錄 (假設你放在 home)
cd ~
git clone <你的 GitHub Repo 網址>  # 如果還沒 clone
cd 104_jobdata_crawler_final

# 2. 建立虛擬環境 (避免汙染全域)
python3 -m venv venv
source venv/bin/activate

# 3. 安裝 Python 套件 (我們剛才已經更新了 requirements.txt)
pip install -r requirements.txt
```

---

## 步驟 4：設定資料庫連線

由於你的 MariaDB 在同一台機器上，請編輯 `db_config.py`：

```python
# db_config.py
DB_HOST = "127.0.0.1"  # 本機
DB_USER = "<你的帳號>"
DB_PASSWORD = "<你的密碼>"
DB_NAME = "job_db"     # 確認你的 DB 名稱
```

---

## 步驟 5：設定自動排程 (Crontab)

這是讓它長期運作的關鍵。我們會設定每天凌晨跑爬蟲與更新模型。

輸入 `crontab -e` 進入編輯模式，加入以下內容：

```bash
# 確保使用 venv 裡的 python
# 每天 02:00 執行爬蟲 + ETL + 訓練 + 預測
0 2 * * * cd /home/<你的使用者名稱>/104_jobdata_crawler_final && ./venv/bin/python daily_pipeline.sh >> cron.log 2>&1
```

_(註：建議寫一個 simple shell script 串接所有 python 指令，這樣 crontab 比較乾淨)_

**daily_pipeline.sh 範例內容**：

```bash
#!/bin/bash
# 記得 chmod +x daily_pipeline.sh
source venv/bin/activate

# 1. 爬蟲 (限制頁數避免跑太久)
python 104_crawler_final.py --end_page 50

# 2. 匯入資料庫
python "daily append.py"

# 3. ETL
python merge_to_db.py

# 4. 訓練與預測 (最吃資源，建議加上 nice 指令降低優先權，避免卡死 DB)
nice -n 10 python predict_salary_ensemble_segmented_v7.py
nice -n 10 python generate_predictions.py
```

---

## 步驟 6：啟動網站 (背景執行)

```bash
# 使用 gunicorn 啟動 (4 workers 可能太多，這台機器建議 2 workers)
nohup gunicorn -w 2 -b 0.0.0.0:5000 app:app &
```

---

## 效能監控

佈署後，請偶爾登入 VM 輸入 `htop` 觀察資源。

- 如果 **Load Average** 長期 > 1.0，表示 CPU 太忙。
- 如果 **Mem** 用滿且 **Swp** 也用滿，那就必須升級機器 (Change Machine Type) 至 `e2-medium` 或更高。
