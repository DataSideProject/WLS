# Ngrok 操作教學

這是將本地開發的網頁伺服器（localhost）公開到網際網路的操作步驟。

## 前置準備

確保你已經下載並安裝了 ngrok。

## 步驟 1：啟動 Flask App

首先，在一個終端機（Terminal）視窗中啟動你的應用程式：

```bash
python app.py
```

確認看到類似 `Running on http://0.0.0.0:5000` 的訊息，代表網站已在本地啟動。

## 步驟 2：啟動 Ngrok

開啟一個 **新的** 終端機視窗（不要關閉原本跑 app.py 的視窗），輸入以下指令：

```bash
ngrok http 5000
```

_注意：這裡的 `5000` 必須對應 `app.py` 中設定的 port 號。_

## 步驟 3：取得網址

Ngrok 會顯示類似以下的畫面：

```
Session Status                online
Account                       YourName (Plan: Free)
Forwarding                    https://xxxx-xxxx.ngrok-free.app -> http://localhost:5000
```

複製 `Forwarding` 那一行顯示的 `https` 網址（例如 `https://xxxx-xxxx.ngrok-free.app`），這就是可以分享給別人的外部連結。
