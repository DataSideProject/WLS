# Machine Learning Pipeline Documentation

本目錄包含薪資預測模型的完整流程，從資料載入、特徵工程、模型訓練到預測產出。
最新的模型採用 **Granular Segmentation (細緻分群)** 策略，大幅提升了預測準確度。

## 核心架構 (Core Architecture)

### 1. 分群策略 (Granular Segmentation)

為了應對不同來源與職涯階段的薪資結構差異，我們將模型拆分為 **4 個專屬子模型**，針對每一筆職缺的身分自動派送：

| 模型名稱            | 適用對象                    | 特徵                         | 預測表現 (R²)        |
| :------------------ | :-------------------------- | :--------------------------- | :------------------- |
| **104_Senior**      | 104 人力銀行, 經歷 >= 3 年  | 資深職缺，薪資與技能高度相關 | **0.52** (Excellent) |
| **104_Junior**      | 104 人力銀行, 經歷 1~2 年   | 初階職缺，薪資變異小         | **0.25** (Good)      |
| **104_Unspecified** | 104 人力銀行, 經歷不拘/0 年 | 經歷要求不明確的職缺         | 0.21 (Fair)          |
| **CakeResume**      | CakeResume 來源             | 外商/新創風格，薪資結構特殊  | (樣本累積中)         |

### 2. 資料淨化與防洩漏 (Data Leakage Prevention)

我們發現部分職缺雖然標示為「面議」，但在資料處理過程中被填補為 `0`。若將這些 `0` 值納入訓練，會導致模型嚴重失準 (R² < 0)。
**修正方案**：

- **訓練集 (Training Set)**：嚴格過濾，僅使用 `salary_min > 0` 且 `salary_max > 0` 的資料進行訓練。
- **預測集 (Prediction Set)**：對**所有**職缺 (包含面議) 進行預測，填補潛在薪資範圍。

### 3. 特徵工程 (Feature Engineering)

模型採用以下特徵組合 (約 500+ 維度)：

- **職缺描述 (Description)**: 使用 `jieba` 分詞 + TF-IDF 取前 100 關鍵字。
- **技能 (Skills)**: 常見技術關鍵字 (Python, Java, AWS...) One-Hot Encoding。
- **地點 (Location)**: 縣市層級特徵。
- **公司福利 (Benefits)**: _New!_ 加入福利關鍵字作為特徵。
- **交叉特徵 (Cross Features)**: 職稱 x 地點、技能 x 地點的交互作用。

## 檔案說明

### 系統核心

- **`generate_predictions.py`** : **[Production]** 正式預測腳本。執行完整的 ETL -> Training -> Prediction 流程，並將結果寫入資料庫 `fact_job_predictions`。
- **`ml_data_loader.py`** : 資料載入器。負責從資料庫讀取並正規化資料 (時薪轉月薪、排除極端值)。

### 實驗與診斷

- **`predict_salary_model.py`** : **[Development]** 開發與診斷腳本。用於測試新的分群策略、繪製 R² 診斷圖 (`model_diagnostics_segmented.png`)。
- **`evaluate_model_performance.py`** : 舊版評估腳本 (已整合至 predict_salary_model)。

## 執行方式

若要更新整個薪資預測資料庫：

```bash
# 1. 確保位於 step3 目錄
cd e:\Antigravity_HOME_PC\WLS\step3_machine_learning_pipeline

# 2. 執行預測 (需確保 DB 連線正常)
python generate_predictions.py
```

執行後，可至前端 Dashboard 查看最新預測結果 (記得重啟 Web App)。
