import yfinance as yf # 匯入 yfinance 套件，用來抓取 Yahoo Finance 的股票資料
import pandas as pd # 匯入 pandas 套件，用來處理表格資料 (DataFrame)
import matplotlib.pyplot as plt # 匯入 matplotlib 的 pyplot，用來畫圖
import matplotlib.ticker as ticker # 匯入 matplotlib 的 ticker，用來格式化 y 軸
import matplotlib.dates as mdates # 匯入 matplotlib 的 dates，用來格式化 x 軸
plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'sans-serif'] # 設定畫圖時使用的字型為微軟正黑體，避免中文顯示亂碼

# 設定參數 & 讀取資料 (使用您習慣的方式)
symbol = '00878.TW' # 股票代碼
print(f'正在下載資料: {symbol} ...')
data = yf.download(symbol, start='2015-01-01', progress=False) # 下載資料
data.columns = data.columns.get_level_values(0) # 攤平多層索引
invest_amount = 5000 # 投資金額

# --- 1. 定義回測引擎 (Backtest Engine) ---
def run_backtest(data, amount, strategy_func):
    """
    執行回測的通用函式
    :param data: 包含股價的 Series 或 DataFrame (必須有 'Close' 欄位)
    :param amount: 每次投入金額
    :param strategy_func: 策略函式，接收 (index, row) 回傳 True/False 決定是否買進
    :return: (portfolio_value, cost_history) 兩個列表
    """
    total_shares = 0 # 總持股數
    total_cost = 0 # 總成本
    portfolio_value = [] # 市值
    cost_history = [] # 總成本
    
    # 確保 data 是 DataFrame 並且有 Close 欄位 (如果是 Series 則轉一下)
    if isinstance(data, pd.Series):
        df = data.to_frame(name='Close')
    else:
        df = data.copy() # 複製一份以免影響原始資料

    # 預先計算輔助欄位 (例如換月)
    df['Month'] = df.index.month
    df['換月'] = df['Month'] != df['Month'].shift(1)
    
    # 遍歷每一行
    for index, row in df.iterrows():
        price = row['Close']
        # 如果是 NaN，則跳過
        if pd.isna(price):
            portfolio_value.append(0)
            cost_history.append(0)
            continue
            
        # 呼叫策略函式判斷是否買進
        if strategy_func(row):
            shares_bought = amount / price
            total_shares += shares_bought
            total_cost += amount
            
        # 計算當日市值
        current_value = total_shares * price
        portfolio_value.append(current_value)
        cost_history.append(total_cost)
        
    return portfolio_value, cost_history

# --- 2. 定義畫圖函式 (Plotting Function) ---

def plot_performance(data, portfolio_value, cost_history, title):
    fig, ax = plt.subplots(figsize=(12, 6))
    
    ax.plot(data.index, portfolio_value, label='總市值', color='#d62728')
    ax.plot(data.index, cost_history, label='累積成本', linestyle='--', color='#1f77b4', alpha=0.8)
    
    # 填滿獲利區域 (市值 > 成本)
    ax.fill_between(data.index, portfolio_value, cost_history, 
                    where=(pd.Series(portfolio_value) >= pd.Series(cost_history)),
                    facecolor='green', alpha=0.1, interpolate=True, label='獲利')
                    
    # 填滿虧損區域 (市值 < 成本)
    ax.fill_between(data.index, portfolio_value, cost_history, 
                    where=(pd.Series(portfolio_value) < pd.Series(cost_history)),
                    facecolor='red', alpha=0.1, interpolate=True, label='虧損')

    ax.set_title(title, fontsize=15)
    ax.set_xlabel('日期')
    ax.set_ylabel('金額 (萬)')

    def y_fmt(x, pos):
        return f'{int(x/10000)}萬'
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(y_fmt))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    fig.autofmt_xdate()
    
    ax.legend(loc='upper left')
    ax.grid(True, which='both', linestyle='--', alpha=0.5)
    plt.show()

# --- 3. 技術指標計算函式 (Indicator Helper) ---
def calculate_indicators(df):
    """
    計算常用的技術指標並加入 DataFrame
    """
    df = df.copy()
    
    # 1. 移動平均線 (MA)
    df['MA20'] = df['Close'].rolling(window=20).mean() # 月線
    df['MA60'] = df['Close'].rolling(window=60).mean() # 季線
    
    # 2. RSI (相對強弱指標)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # 3. 星期幾 (0=週一, 6=週日)
    df['Weekday'] = df.index.dayofweek
    
    return df

# --- 4. 策略範例 (More Strategies) ---

# 策略 A: 每月換月時買進
def monthly_strategy(row):
    return row['換月']

# 策略 B: 均線策略 (收盤價 > 20MA 就買進)
def ma_strategy(row):
    # 必須先確保有 MA20 這個欄位
    if pd.isna(row.get('MA20')):
        return False
    return row['Close'] > row['MA20']

# 策略 C: RSI 策略 (RSI < 30 超賣時買進)
def rsi_strategy(row):
    if pd.isna(row.get('RSI')):
        return False
    return row['RSI'] < 30

# 策略 D: 星期策略 (每週一買進)
def weekday_strategy(row):
    return row['Weekday'] == 0 # 0 代表週一

# --- 5. 報酬率計算函式 (Return Calculation Helper) ---
def calculate_and_print_returns(data, portfolio_value, cost_history):
    """
    計算並印出每年報酬率與平均年化報酬率 (CAGR)
    使用簡單的資金加權概念 (因為定期定額較複雜，這裡簡化計算：期末市值 / 期末成本 - 1，並分年計算)
    注意：精確的 TWR (時間加權) 需要每日的現金流，這裡為了直觀，我們計算「帳戶總值」的年增長率，
    但因為有持續投入資金，直接算 % 會失真。
    
    更實用的算法是：計算「內部報酬率 (IRR)」或是簡單的「總報酬率 / 年份」。
    這裡我們展示：
    1. 每年年底的「累計報酬率」 = (年底市值 - 年底成本) / 年底成本
    2. 總年化報酬率 (IRR 概念太複雜，這裡用簡單的 CAGR 概念：(期末市值/總成本)^(1/年數) - 1 )
    """
    
    # 建立一個 DataFrame 來處理資料
    df_perf = pd.DataFrame({
        'Value': portfolio_value,
        'Cost': cost_history
    }, index=data.index)
    
    # 依年份分群
    yearly_groups = df_perf.groupby(df_perf.index.year)
    
    print("-" * 30)
    print(f"{'年份':<6} | {'投入成本':<10} | {'期末市值':<10} | {'累積報酬率':<10}")
    print("-" * 30)
    
    for year, group in yearly_groups:
        last_row = group.iloc[-1]
        cost = last_row['Cost']
        value = last_row['Value']
        
        if cost == 0:
            ret = 0
        else:
            ret = (value - cost) / cost
            
        print(f"{year:<6} | {int(cost):<10} | {int(value):<10} | {ret:.2%}")
        
    print("-" * 30)
    
    # 計算總年化報酬率 (CAGR)
    # 公式：(期末總市值 / 總投入成本) ^ (1 / 總年數) - 1
    # 注意：這其實比較像「總資產年化成長率」，對於定期定額來說，IRR (XIRR) 才是最準確的，但這裡先用簡單版
    
    final_row = df_perf.iloc[-1]
    final_cost = final_row['Cost']
    final_value = final_row['Value']
    
    if final_cost > 0:
        total_years = (df_perf.index[-1] - df_perf.index[0]).days / 365.25
        cagr = (final_value / final_cost) ** (1 / total_years) - 1
        print(f"總投入成本: {int(final_cost)}")
        print(f"期末總市值: {int(final_value)}")
        print(f"總報酬率: {(final_value - final_cost) / final_cost:.2%}")
        print(f"平均年化報酬率 (CAGR): {cagr:.2%}")
    else:
        print("沒有交易資料")
    print("-" * 30)
    print("\n")


# --- 6. 執行多種策略測試 ---

# 先計算指標
print('正在計算技術指標 ...')
data_with_indicators = calculate_indicators(data)

# 執行回測
print(f'開始回測 ...')

# 每月換月時買進
print(f'=== 回測策略: 每月換月時買進 ===')
p_value, c_history = run_backtest(data, invest_amount, monthly_strategy)
calculate_and_print_returns(data_with_indicators, p_value, c_history)
plot_performance(data, p_value, c_history, 
                 f'{symbol} 定期定額回測 (每月 {invest_amount} 元)')

# 均線策略
print(f'=== 回測策略: 站上月線買進 ===')
p_val_ma, c_hist_ma = run_backtest(data_with_indicators, invest_amount, ma_strategy)
calculate_and_print_returns(data_with_indicators, p_val_ma, c_hist_ma)
plot_performance(data_with_indicators, p_val_ma, c_hist_ma, f'{symbol} 均線策略 (站上月線買進)')

# RSI 策略
print(f'=== 回測策略: RSI < 30 買進 ===')
p_val_rsi, c_hist_rsi = run_backtest(data_with_indicators, invest_amount, rsi_strategy)
calculate_and_print_returns(data_with_indicators, p_val_rsi, c_hist_rsi)
plot_performance(data_with_indicators, p_val_rsi, c_hist_rsi, f'{symbol} RSI 策略 (RSI < 30 買進)')

# 週一買進策略
print(f'=== 回測策略: 每週一買進 ===')
p_val_mon, c_hist_mon = run_backtest(data_with_indicators, invest_amount, weekday_strategy)
calculate_and_print_returns(data_with_indicators, p_val_mon, c_hist_mon)
plot_performance(data_with_indicators, p_val_mon, c_hist_mon, f'{symbol} 星期策略 (每週一買進)')