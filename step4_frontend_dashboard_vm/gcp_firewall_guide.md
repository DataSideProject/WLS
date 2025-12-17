# GCP 防火牆設定指南 (GCP Firewall Setup Guide)

本指南將教您如何在 Google Cloud Platform (GCP) 上開放防火牆端口 (Port)，讓外部網路可以連線到您的 Flask 應用程式 (Port 5000)。

## 方法一：使用 GCP Console (圖形介面) - 推薦新手

這是最直觀的方法，適合不熟悉指令的使用者。

### 1. 進入防火牆設定頁面

1.  登入 [GCP Console](https://console.cloud.google.com/)。
2.  點擊左上角的漢堡選單 (≡)。
3.  導航至 **VPC network (VPC 網路)** > **Firewall (防火牆)**。

### 2. 建立新規則

1.  點擊頂部的 **Create Firewall Rule (建立防火牆規則)**。
2.  填寫以下資訊：
    - **Name (名稱)**: `allow-flask-5000` (或任何您容易辨識的名字)
    - **Network (網路)**: 選擇 `default` (除非您有自訂網路)
    - **Priority (優先順序)**: `1000` (預設即可)
    - **Direction of traffic (流量方向)**: `Ingress` (輸入)
    - **Action on match (對應動作)**: `Allow` (允許)
    - **Targets (目標)**: 選擇 `All instances in the network` (網路中的所有執行個體)
      - _進階安全建議_: 若只想針對該台 VM，可選 `Specified target tags` 並在 Target tags 欄位填入 `flask-server`，然後記得去您的 VM 編輯頁面加上 `flask-server` 這個標籤。
    - **Source filter (來源篩選器)**: `IPv4 ranges`
    - **Source IPv4 ranges (來源 IPv4 範圍)**: `0.0.0.0/0` (代表允許全世界連線)
    - **Protocols and ports (通訊協定和通訊埠)**:
      - 勾選 `Specified protocols and ports`
      - 勾選 `TCP`，並在後方欄位輸入 `5000`

### 3. 完成建立

點擊最下方的 **Create (建立)**。等待約 10-30 秒，規則生效後，您即可透過 `http://<VM_EXTERNAL_IP>:5000` 連線。

---

## 方法二：使用 gcloud Command Line (指令介面) - 快速

如果您已經安裝了 Google Cloud SDK (`gcloud`)，或正在使用 Cloud Shell，這是一行指令就能解決的方案。

### 1. 執行建立指令

開啟您的終端機 (或 VM 裡的 termial)，執行：

```bash
gcloud compute firewall-rules create allow-flask-5000 \
    --direction=INGRESS \
    --priority=1000 \
    --network=default \
    --action=ALLOW \
    --rules=tcp:5000 \
    --source-ranges=0.0.0.0/0
```

- `allow-flask-5000`: 規則名稱。
- `--rules=tcp:5000`: 指定開放 TCP 協定的 5000 Port。
- `--source-ranges=0.0.0.0/0`: 允許所有 IP 來源。

---

## 常見問題故障排除 (Troubleshooting)

### Q1: 防火牆規則建好了，但還是連不上？

1.  **檢查 App 是否監聽 0.0.0.0**:
    - 請確認您的 `app.py` 最後是寫 `app.run(host='0.0.0.0', port=5000)`。
    - 如果是寫 `host='127.0.0.1'` 或 `localhost`，則**只有 VM 自己能連**，防火牆開了也沒用。
2.  **檢查 VM 內部防火牆 (UFW)**:
    - 有些 Linux Image 預設開啟 UFW (Uncomplicated Firewall)。
    - 在 VM 內執行 `sudo ufw status` 檢查。
    - 若有開啟，需執行 `sudo ufw allow 5000/tcp`。
3.  **確認 IP 正確**:
    - 請確保瀏覽器輸入的是 VM 的 **External IP (外部 IP)**，而不是 Internal IP。

### Q2: 如何限制只有我自己的 IP 能連？

在設定 **Source IPv4 ranges** 時，不要填 `0.0.0.0/0`，改填您目前的 IP (您可以 Google "what is my ip" 查詢)。
例如：`203.0.113.1/32`。
