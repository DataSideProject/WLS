import json

file_path = r'e:\Antigravity_HOME_PC\WLS\finance\tibame20251127.ipynb'

try:
    with open(file_path, 'r', encoding='utf-8') as f:
        nb = json.load(f)

    # Create a new code cell with the DCA logic
    dca_code = [
        "# 定期定額回測邏輯\n",
        "inv_time = 0 # 投資次數計數器 (或是天數計數器)\n",
        "once_amount = 5000 # 每次定期定額投入的金額\n",
        "total_shares = 0 # 累積持有的股數\n",
        "total_cost = 0 # 累積投入的總成本\n",
        "portfolio_value = [] # 記錄每一天的投資組合總市值\n",
        "cost_history = [] # 記錄每一天的累積成本 (方便畫圖比較)\n",
        "\n",
        "# 假設我們要回測的是列表中的第一個股票 (例如 0050.TW)\n",
        "# 這裡我們先用 data_total 中的第一檔股票來做示範\n",
        "# 注意：data_total 是多層索引 (MultiIndex)，我們取第一層的第一個 symbol\n",
        "target_symbol = symbols[0] \n",
        "print(f'開始回測標的: {target_symbol}')\n",
        "\n",
        "# 取得該股票的收盤價資料\n",
        "target_data = data_total['Close'][target_symbol]\n",
        "\n",
        "for date, price in target_data.items():\n",
        "    # 排除股價為 NaN 的情況 (可能還沒上市或當天沒交易)\n",
        "    if pd.isna(price):\n",
        "        portfolio_value.append(0)\n",
        "        cost_history.append(0)\n",
        "        continue\n",
        "\n",
        "    # 策略：每 20 個交易日 (約一個月) 買入一次\n",
        "    if inv_time % 20 == 0:\n",
        "        shares_bought = once_amount / price # 計算當次能買到的股數\n",
        "        total_shares += shares_bought # 累積股數\n",
        "        total_cost += once_amount # 累積成本\n",
        "        # print(f'日期: {date.date()}, 買入股價: {price:.2f}, 買入股數: {shares_bought:.2f}, 累積成本: {total_cost}')\n",
        "\n",
        "    # 計算當天市值 = 累積股數 * 當天股價\n",
        "    current_value = total_shares * price\n",
        "    portfolio_value.append(current_value)\n",
        "    cost_history.append(total_cost)\n",
        "    \n",
        "    inv_time += 1\n",
        "\n",
        "# 將結果畫出來\n",
        "plt.figure(figsize=(12, 6))\n",
        "plt.plot(target_data.index, portfolio_value, label='定期定額總市值')\n",
        "plt.plot(target_data.index, cost_history, label='累積投入成本', linestyle='--')\n",
        "plt.title(f'{target_symbol} 定期定額回測 (每次 {once_amount} 元)')\n",
        "plt.xlabel('日期')\n",
        "plt.ylabel('金額')\n",
        "plt.legend()\n",
        "plt.grid(True)\n",
        "plt.show()"
    ]

    new_cell = {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": dca_code
    }

    # Append the new cell to the notebook
    nb['cells'].append(new_cell)

    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(nb, f, indent=1, ensure_ascii=False)
    print("Successfully added DCA logic to notebook.")

except Exception as e:
    print(f"Error: {e}")
