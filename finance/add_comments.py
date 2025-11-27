import json

file_path = r'e:\Antigravity_HOME_PC\WLS\finance\tibame20251127.ipynb'

try:
    with open(file_path, 'r', encoding='utf-8') as f:
        nb = json.load(f)

    cells = nb['cells']

    # Cell 0
    if len(cells) > 0:
        cells[0]['source'] = [
            "import yfinance as yf # 匯入 yfinance 套件，用來抓取 Yahoo Finance 的股票資料\n",
            "import pandas as pd # 匯入 pandas 套件，用來處理表格資料 (DataFrame)\n",
            "import matplotlib.pyplot as plt # 匯入 matplotlib 的 pyplot，用來畫圖\n",
            "plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'sans-serif'] # 設定畫圖時使用的字型為微軟正黑體，避免中文顯示亂碼"
        ]

    # Cell 1
    if len(cells) > 1:
        cells[1]['source'] = [
            "symbols = [\n",
            "    '0050.TW',   # 台灣50\n",
            "    '00631L.TW', # 元大台灣50正2\n",
            "    '0056.TW',   # 元大高股息\n",
            "    '00929.TW',  # 復華台灣科技優息\n",
            "    '00878.TW',  # 國泰永續高股息\n",
            "    'QQQ',       # Invesco QQQ (美股 ETF)\n",
            "    'TQQQ'       # ProShares UltraPro QQQ (美股 ETF)\n",
            "]\n",
            "\n",
            "data_s = [] # 建立一個空列表，用來存放抓下來的資料\n",
            "for symbol in symbols:\n",
            "    # 使用 yfinance 下載資料，從 2015-01-01 開始\n",
            "    data = yf.download(symbol, start='2015-01-01')\n",
            "    # 將抓下來的資料加入 data_s 列表\n",
            "    data_s.append(data)\n",
            "data_total = pd.concat(data_s, axis=1) # 將列表中的資料合併成一個大的 DataFrame，axis=1 表示左右合併 (依欄位)"
        ]

    # Cell 2
    if len(cells) > 2:
        cells[2]['source'] = [
            "ret = data_total['Close'].pct_change() # 計算每日報酬率 (pct_change 會計算 (今天-昨天)/昨天)，只取 'Close' (收盤價)\n",
            "(ret+1).cumprod().plot() # 計算累積報酬率並畫圖。cumprod() 是累積相乘，plot() 是畫圖"
        ]

    # Cell 3
    if len(cells) > 3:
        cells[3]['source'] = [
            "ret_ = ret.dropna() # 移除有缺失值 (NaN) 的資料\n",
            "(ret_+1).cumprod().plot() # 再次畫出累積報酬率圖"
        ]

    # Cell 4
    if len(cells) > 4:
        cells[4]['source'] = [
            "day_of_year = 242 # 假設一年有 242 個交易日\n",
            "ret_yearly = ret.mean() * day_of_year # 計算年化報酬率 (平均每日報酬 * 交易日數)\n",
            "print(f'年化報酬')\n",
            "print(ret_yearly)\n",
            "\n",
            "std_yearly = ret.std() * (day_of_year ** 0.5) # 計算年化風險 (標準差 * 交易日數的平方根)\n",
            "print(f'年化風險')\n",
            "print(std_yearly)\n"
        ]

    # Cell 5
    if len(cells) > 5:
        cells[5]['source'] = [
            "\n",
            "sharp_yearly = ret_yearly / std_yearly # 計算夏普比率 (年化報酬 / 年化風險)\n",
            "print(f'年化夏普比率')\n",
            "print(sharp_yearly)\n",
            "\n",
            "bad_std_yearly = ret[ret<0].std() * (day_of_year ** 0.5) # 計算下檔風險 (只考慮報酬率小於 0 的部分的標準差)\n",
            "sortino_yearly = ret_yearly /bad_std_yearly # 計算索提諾比率 (年化報酬 / 下檔風險)\n",
            "print(f'年化所提諾比率')\n",
            "print(sortino_yearly)"
        ]

    # Cell 6
    if len(cells) > 6:
        cells[6]['source'] = [
            "mdd = ( (ret+1).cumprod() / (ret+1).cumprod().cummax() -1 ).min() # 計算最大回檔 (MDD)\n",
            "mdd"
        ]

    # Cell 7
    if len(cells) > 7:
        cells[7]['source'] = [
            "newhigh = ((ret+1).cumprod() / (ret+1).cumprod().cummax()) == 1 # 判斷每一天是否創新高\n",
            "newhigh[ret.isna()] = None # 將報酬率為 NaN 的日子的創新高判斷設為 None\n",
            "new_high = newhigh.mean() # 計算創新高天數的比例\n",
            "print(f'new_high')\n",
            "print(new_high)"
        ]

    # Cell 8
    if len(cells) > 8:
        cells[8]['source'] = [
            "kpi_s = [] # 建立一個列表來收集各項 KPI 指標\n",
            "kpi_s.append(ret_yearly)\n",
            "kpi_s.append(std_yearly)\n",
            "kpi_s.append(sharp_yearly)\n",
            "kpi_s.append(sortino_yearly)\n",
            "kpi_s.append(mdd)\n",
            "kpi_s.append(new_high)\n",
            "kpi_table = pd.concat(kpi_s, axis=1) # 將列表合併成一個 DataFrame\n",
            "kpi_table.columns = ['年化報酬','年化風險','夏普比例','所提諾比率','最大回檔','創高率'] # 設定欄位名稱\n",
            "kpi_table.transpose().plot.bar() # 轉置表格並畫出長條圖\n",
            "# kpi_table.plot.bar()"
        ]

    # Cell 9
    if len(cells) > 9:
        cells[9]['source'] = [
            "from FinMind.data import DataLoader # 匯入 FinMind 的 DataLoader\n",
            "api = DataLoader()\n",
            "df = api.taiwan_stock_info() # 抓取台灣股票資訊"
        ]

    # Cell 10
    if len(cells) > 10:
        cells[10]['source'] = [
            "print(df) # 印出抓取到的股票資訊"
        ]

    # Cell 11
    if len(cells) > 11:
        cells[11]['source'] = [
            "symbols = df[\n",
            "    (df['industry_category']=='ETF') & # 篩選產業類別是 'ETF'\n",
            "    (df['stock_id'].str.contains('009')) & # 篩選股票代號包含 '009'\n",
            "    (df['stock_name'].str.contains('高息')) # 篩選股票名稱包含 '高息'\n",
            "    ]\n",
            "print(symbols)"
        ]

    # Cell 12
    if len(cells) > 12:
        cells[12]['source'] = [
            "symbols = [ f\"{i}.TW\" for i in symbols['stock_id'].tolist() ] # 將篩選出的股票代號加上 '.TW'"
        ]

    # Cell 13
    if len(cells) > 13:
        cells[13]['source'] = [
            "[i * 2 for i in range(100)] # 列表推導式範例：產生 0 到 99 的數字，並將每個數字乘以 2"
        ]

    # Cell 14
    if len(cells) > 14:
        cells[14]['source'] = [
            "[ f\"{i}*{j}={i*j}\" for i in range(2,10) for j in range(1,10)] # 列表推導式範例：九九乘法表"
        ]

    # Cell 15
    if len(cells) > 15:
        cells[15]['source'] = [
            "symbols = [ f\"{i}.TW\" for i in symbols['stock_id'].tolist() ] # (重複) 將股票代號加上 .TW\n",
            "data_s = []\n",
            "for symbol in symbols:\n",
            "    data = yf.download(symbol, start='2015-01-01') # 下載資料\n",
            "    data_s.append(data)\n",
            "data_total = pd.concat(data_s, axis=1) # 合併資料\n",
            "ret = data_total['Close'].pct_change() # 計算報酬率\n",
            "newhigh[ret.isna()] = None # 處理 NaN"
        ]

    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(nb, f, indent=1, ensure_ascii=False)
    print("Successfully updated notebook with comments.")

except Exception as e:
    print(f"Error: {e}")
