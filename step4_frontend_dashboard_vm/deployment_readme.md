# Frontend Dashboard Deployment Guide (GCP VM)

本指南提供一份**完全 Copy-Paste** 的操作流程，協助您從零開始在 GCP VM 上部署 Dashboard。
本流程採用 **Git Sparse Checkout** 方式，只抓取專案中的 `step4_frontend_dashboard_vm` 資料夾，保持環境乾淨。

---

## 前置準備 (Local 端)

1.  確保您的專案已 Push 到 GitHub (或其他 Git 伺服器)。
2.  記下您的 **Repo URL** (例如 `https://github.com/yourname/your-repo.git`)。

---

## 部署流程 (VM 端)

請依序在 GCP VM 的終端機執行以下步驟。

### Step 1: 系統更新與安裝必要軟體

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git nano mysql-client mariadb-server
```

### Step 2: 建立部署目錄與權限設定 (非 Root 執行)

我們將網站部署在 `/opt/dashboard`，並將權限開放給您的使用者帳號。

```bash
# 1. 建立資料夾
sudo mkdir -p /opt/dashboard

# 2. 修改擁有者為目前使用者 (這樣您就不需要一直用 sudo 寫入檔案)
sudo chown -R $USER:$USER /opt/dashboard

# 3. 進入目錄
cd /opt/dashboard
```

### Step 3: Git 初始化與單獨抓取資料夾 (Sparse Checkout)

這個步驟會只抓取 `step4_frontend_dashboard_vm` 資料夾的內容。

```bash
# 初始化空的 git repo
git init
git remote add origin <您的_GITHUB_REPO_URL>  # <--- 請替換成您的 Repo URL

# 開啟 Sparse Checkout 功能
git config core.sparseCheckout true

# 指定要抓取的資料夾路徑
# 指定要抓取的資料夾路徑
echo "step4_frontend_dashboard_vm/" >> .git/info/sparse-checkout

# 拉取程式碼 (假設主分支為 main)
git pull origin main

# 進入該資料夾
cd step4_frontend_dashboard_vm
```

### Step 4: 建立 Python 虛擬環境

```bash
# 建立 venv
python3 -m venv venv

# 啟動 venv
source venv/bin/activate

# 安裝套件
pip install -r requirements.txt
```

### Step 5: 設定資料庫連線

```bash
# 建立並編輯 db_config.py
nano db_config.py
```

請複製貼上以下內容 (按滑鼠右鍵可貼上)：

```python
import os

# Database Configuration
DB_HOST = 'localhost'       # 資料庫在同一台 VM
DB_USER = 'root'            # 資料庫使用者
DB_PASSWORD = ''            # 若無密碼留空，有密碼請填入
DB_NAME = 'job_data_warehouse'
```

_(保存離開：按 `Ctrl+O` -> `Enter` -> `Ctrl+X`)_

### Step 6: 更新資料庫 Schema (重要！)

確保資料庫有最新的 View 定義：

```bash
python 09_create_ml_view.py
```

> **注意：空的資料庫？**
> 如果這是全新的 VM，您的資料庫是空的。請參考 **[data_migration_guide.md](data_migration_guide.md)** 將本機資料匯入 VM。

### Step 7: 啟動網站 (背景執行)

使用 `nohup` 讓網站在背景執行，即使斷開 SSH 連線也不會停止。

```bash
# 啟動 app.py，日誌輸出到 app.log
nohup python3 app.py > app.log 2>&1 &
```

### Step 8: 驗證

打開瀏覽器，輸入您的 VM 外部 IP：
`http://<GCP_VM_EXTERNAL_IP>:5000`

若看到畫面，即表示部署成功！🎉

> **無法連線？**
> 若瀏覽器轉圈圈或顯示無法連線，通常是 **GCP 防火牆 (Firewall)** 沒開。
> 請參考同目錄下的 **[gcp_firewall_guide.md](gcp_firewall_guide.md)** 教學，設定開放 `tcp:5000` 連接埠。

---

## 常用維護指令

- **查看 Log (除錯用)**:
  ```bash
  tail -f app.log
  ```
- **停止網站**:
  ```bash
  pkill -f "python app.py"
  ```
- **更新程式碼**:
  ```bash
  cd /opt/dashboard
  git pull origin main
  # 若有新套件依賴，記得再 pip install -r step4_frontend_dashboard_vm/requirements.txt
  ```
