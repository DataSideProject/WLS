# 台灣科技職缺薪資預測平台  
**104 人力銀行 x Cakeresume × AI 薪資預測 × 視覺化儀表板**  
Live Demo：http://localhost:5000 （執行 app.py 後開啟）ngrok link: https://trisomic-nonpermissively-suzanna.ngrok-free.dev/

## 專案特色
1. **每日自動爬蟲 + 資料庫增量更新** → 永遠掌握最新職缺  
2. **雙階段薪資預測模型**  
   - 第一階段：Ensemble + 年資分群（Junior / Senior）  
   - 第二階段：僅用真實薪資訓練，最終預測無洩漏  
3. **AI 自動填補「待遇面議」薪資**，使用者永遠只看到一組乾淨數字  
4. **ECharts 技能樹 + 互動式市場儀表板**，視覺化  
5. **完整資料工程管線**：爬蟲 → MariaDB → 預測 → Flask 前後端分離

## 專案架構圖

```mermaid
flowchart TD
    subgraph 爬蟲與資料匯入
        A[定期執行爬蟲<br>104_crawler_final.py]
        AA[定期執行cakeresume爬蟲<br>]
        A --> B[/存成各自的raw.csv<br>/]
        AA --> B
        B --> C[daily_append.py<br>增量匯入資料庫<br>或用 Workbench 手動匯入]
        C --> D[/GCP MariaDB<br>104: 104rawdata資料表<br>cake: job_details資料表/]
    end

    subgraph 薪資預測與視覺化應用
        AB[合併多平台資料<br>整理成統一格式<br>merge_to_db.py]
        D --> AB
        AB --> E[predict_salary_ensemble_segmented_v7.py<br>年資分群<br>Ensemble模型預測]
        E --> F[/job_data_with_full_salary_v7_segmented.csv<br>薪資填補完成<br>含報告.txt 與殘差圖.png/]
        F --> G[generate_predictions.py<br>最終預測 無資料洩漏]
        G --> H[/job_data_final_with_predictions.csv<br>唯一上線資料/]
        H --> I[啟動 Flask 伺服器<br>app.py]
        I --> J[本地測試<br>http://localhost:5000<br>技能樹 + 儀表板 + 搜尋]
        J --> K1[使用 ngrok<br>快速暴露到公網<br>臨時分享測試用]
        J --> K2[部署到 Vercel<br>永久上線<br>自動 HTTPS + 自訂域名]
        K1 --> L[任何人用 ngrok 提供的 URL<br>即可瀏覽你的專題網站]
        K2 --> M[任何人用 Vercel 提供的域名<br>即可瀏覽你的專題網站]
    end

    classDef process fill:#2F80ED,stroke:#fff,color:#fff
    classDef file fill:#27AE60,stroke:#fff,color:#fff

    class A,AA,AB,C,E,G,I,J,K1,K2 process
    class B,D,F,H,L,M file
```


## 檔案說明（只保留必要檔案）

| 檔案名稱                                    | 用途說明                                      |
|--------------------------------------------|---------------------------------------------|
| `104_crawler_final.py`                     | 每日執行，抓104職缺（支援斷點續爬）            |
| `daily_append.py`                          | 把新資料增量匯入 GCP MariaDB（可排程）         |
| `merge_to_db.py`                          | 把不同人力銀行資料清洗並統整             |
| `predict_salary_ensemble_segmented_v7.py`  | 從資料庫讀最新資料 → Ensemble + 分群預測（產生報告） |
| `generate_predictions.py`                  | 最終預測腳本（無資料洩漏）→ 產生 Flask 用的 CSV |
| `app.py`                                   | Flask 主程式，啟動網頁                        |
| `skill_taxonomy.json`                      | 技能樹分類                   |
| `analysis_utils.py`                        | 儀表板統計函數                               |
| `templates/index.html`                     | 前端                                |
| `job_data_final_with_predictions.csv`      | Flask 載入的唯一資料來源                      |

## 快速啟動（5 步驟，10 分鐘內跑起來）

```bash
# 1. 爬蟲（範例抓前50頁）
python 104_crawler_final.py --end_page 50

# 2. 匯入資料庫
python daily_append.py

# 3. 不同人力銀行格式清理後合併匯入新table
merge_to_db.py

# 4. 初步預測 + 產生報告
python predict_salary_ensemble_segmented_v7.py

# 5. 最終預測（無資料洩漏）
python generate_predictions.py

# 6. 啟動網站
python app.py
# → 瀏覽器打開 http://localhost:5000
```
## 技術棧

Python, Selenium, Pandas, Scikit-learn, XGBoost, CatBoost
Flask + ECharts 5
MariaDB (GCP)
jieba 中文分詞
