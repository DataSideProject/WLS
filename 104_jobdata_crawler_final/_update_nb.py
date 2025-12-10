import json
import os
import pandas as pd # Just to check import, though not used here directly

file_path = r"e:\Antigravity_HOME_PC\WLS\104_jobdata_crawler_final\Python SQL.ipynb"

try:
    with open(file_path, 'r', encoding='utf-8') as f:
        nb = json.load(f)

    new_cells = [
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## 範例 10: 資料庫結構檢查 (Database Inspection)\n",
                "\n",
                "包含以下檢查項目：\n",
                "- 列出所有資料庫 (SHOW DATABASES)\n",
                "- 列出目前資料庫的所有表格 (SHOW TABLES)\n",
                "- 檢查每個表格的資料筆數 (Row Count)\n",
                "- 檢查每個表格的欄位資訊 (Schema/Columns)"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# ==================== 範例 10: 資料庫結構檢查 ====================\n",
                "try:\n",
                "    # 1. 連線到 Server (不指定 Database 以便查看所有 DB)\n",
                "    # 注意：需使用之前定義好的 HOST, USER, PASSWORD 變數\n",
                "    conn = mysql.connector.connect(host=HOST, user=USER, password=PASSWORD)\n",
                "    cursor = conn.cursor()\n",
                "\n",
                "    print(\"\\n--- 1. 列出所有資料庫 (SHOW DATABASES) ---\")\n",
                "    cursor.execute(\"SHOW DATABASES\")\n",
                "    dbs = cursor.fetchall()\n",
                "    df_dbs = pd.DataFrame(dbs, columns=['Database Name'])\n",
                "    display(df_dbs)\n",
                "\n",
                "    # 2. 切換到指定資料庫並列出表格\n",
                "    conn.database = DATABASE\n",
                "    print(f\"\\n--- 2. 列出資料庫 '{DATABASE}' 中的所有表格 (SHOW TABLES) ---\")\n",
                "    cursor.execute(\"SHOW TABLES\")\n",
                "    tables = cursor.fetchall()\n",
                "    # tables 是一個 list of tuples e.g., [('table1',), ('table2',)]\n",
                "    table_names = [t[0] for t in tables]\n",
                "    df_tables = pd.DataFrame(table_names, columns=['Table Name'])\n",
                "    display(df_tables)\n",
                "\n",
                "    # 3. 檢查每個表格的詳細資訊\n",
                "    print(\"\\n--- 3. 檢查每個表格的資料筆數與欄位資訊 ---\")\n",
                "    for table in table_names:\n",
                "        print(f\"\\n========================================\")\n",
                "        print(f\"表格名稱: {table}\")\n",
                "        \n",
                "        # 查詢筆數\n",
                "        cursor.execute(f\"SELECT COUNT(*) FROM {table}\")\n",
                "        count = cursor.fetchone()[0]\n",
                "        print(f\"資料筆數: {count}\")\n",
                "        \n",
                "        # 查詢欄位資訊 (使用 pandas read_sql 讀取 DESCRIBE)\n",
                "        print(\"欄位結構:\")\n",
                "        df_schema = pd.read_sql(f\"DESCRIBE {table}\", conn)\n",
                "        display(df_schema)\n",
                "\n",
                "except Error as e:\n",
                "    print(f\"檢查錯誤: {e}\")\n",
                "finally:\n",
                "    if 'conn' in locals() and conn.is_connected():\n",
                "        cursor.close()\n",
                "        conn.close()\n",
                "        print(\"\\n檢查完成，連線已關閉\")"
            ]
        }
    ]

    # Insert before the last cell (which is "注意事項")
    # We check the content of the last cell to be sure
    last_cell_source = "".join(nb['cells'][-1]['source'])
    if "注意事項" in last_cell_source:
        insert_pos = -1
    else:
        insert_pos = len(nb['cells'])

    # Using slice assignment to insert
    nb['cells'][insert_pos:insert_pos] = new_cells

    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(nb, f, ensure_ascii=False, indent=1)

    print("SUCCESS: Notebook updated.")

except Exception as e:
    print(f"ERROR: {e}")
