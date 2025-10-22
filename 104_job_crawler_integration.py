# 這是爬取 104 人力銀行資料工程師職缺的 Python 腳本。
# 流程：每頁先收集所有 job_id 及其 list 頁資訊，存成集合，逐一爬細節頁，抓完清空集合，再處理下一頁。
# 修復：優化無限滾動（移除滾動）、修復索引問題（先收集 job_id）、修復 psutil 錯誤。
# 功能：只爬新職缺（比對舊 CSV）、斷點續爬（checkpoint.json）、手動中斷儲存並去重。
# 執行前需安裝套件：pip install pandas selenium undetected-chromedriver psutil beautifulsoup4

import pandas as pd  # 用來處理表格資料，像 Excel 一樣讀寫 CSV 檔案
import time  # 用來暫停程式，模擬人類瀏覽速度，避免被網站偵測為機器人
import random  # 用來產生隨機數字，讓延遲時間不固定，降低被封鎖的風險
import argparse  # 用來讀取命令列輸入，讓程式可以自訂參數（如起始頁碼）
from datetime import datetime  # 用來取得現在的日期時間，幫助命名檔案
import re  # 正則表達式，用來從文字中提取特定模式（如薪資數字或技能關鍵字）
from selenium.webdriver.chrome.options import Options  # 用來設定 Chrome 瀏覽器的選項，比如不顯示視窗
from selenium.webdriver.support.ui import WebDriverWait  # 用來等待網頁元素出現，避免程式太快出錯
from selenium.webdriver.support import expected_conditions as EC  # 定義等待的條件，比如元素可見
from selenium.webdriver.common.by import By  # 用來指定如何找網頁元素（如用 CSS 或 XPath）
import undetected_chromedriver as uc  # 一個隱藏 Selenium 痕跡的工具，讓網站以為是真人瀏覽
import psutil  # 用來管理電腦進程，比如關閉多餘的 Chrome 視窗，避免記憶體爆滿
import os  # 用來處理檔案和資料夾，比如檢查檔案是否存在
import json  # 用來讀寫 JSON 檔案，適合儲存結構化的資料
from bs4 import BeautifulSoup  # 用來解析 HTML 網頁內容，檢查元素（輔助 Selenium）
import logging  # 用來記錄程式執行過程的日誌，方便除錯

# User-Agent 列表，模擬不同瀏覽器
# 為什麼？網站會檢查 User-Agent，如果總是用同一個，容易被當成機器人
user_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/141.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/141.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/17.0 Safari/605.1.15"
]

def parse_arguments():
    """解析命令列參數，讓程式可自訂
    例如：python script.py --start_page 5 --end_page 10，讓你從第5頁爬到第10頁"""
    parser = argparse.ArgumentParser(description="爬取 104 職缺，每頁先收集 job_id 後爬細節，支援新職缺和斷點續爬")
    parser.add_argument("--base_url", default="https://www.104.com.tw/jobs/search",
                        help="搜尋頁面基底 URL")
    parser.add_argument("--query_params", default="jobcat=2007001022",
                        help="查詢參數，jobcat=2007001022 是資料工程師")
    parser.add_argument("--pagination", default="page={page}",
                        help="分頁參數，104 用 page={page}")
    parser.add_argument("--start_page", type=int, default=1, help="起始頁碼")
    parser.add_argument("--end_page", type=int, default=20, help="結束頁碼")
    parser.add_argument("--output_csv", default="job_data.csv", help="輸出 CSV 檔名")
    parser.add_argument("--existing_csv", default="job_data_jobcat_1022.csv", help="現有 CSV，用來比對 job_id")
    parser.add_argument("--headless", action="store_true", default=False,
                        help="使用 headless 模式（不開視窗）")
    return parser.parse_args()

def cleanup_chrome_processes():
    """清理 Chrome 和 chromedriver 進程，避免記憶體問題
    為什麼？Chrome 容易殘留進程，導致電腦變慢或程式出錯"""
    terminated = 0
    try:
        for proc in psutil.process_iter(['name']):
            if proc.info['name'] in ['chrome.exe', 'chromedriver.exe']:
                proc.kill()
                terminated += 1
                print(f"已終止進程: {proc.info['name']} (PID: {proc.pid})")
        return terminated
    except Exception as e:
        print(f"清理進程時發生錯誤: {e}")
        return terminated

def load_existing_job_ids(existing_csv):
    """讀取現有 CSV 的 job_id，檢查新職缺
    為什麼？避免重複爬取已經有的職缺，節省時間"""
    if existing_csv and os.path.exists(existing_csv):
        try:
            df = pd.read_csv(existing_csv)
            return set(df['job_id'].dropna().astype(str))
        except Exception as e:
            print(f"讀取現有 CSV 失敗 ({existing_csv}): {e}")
            return set()
    return set()

def save_checkpoint(page, checkpoint_file="checkpoint.json"):
    """儲存當前爬到的頁數（斷點）
    為什麼？如果程式中斷，下次可以從這裡繼續，不用從頭開始"""
    checkpoint = {"last_page": page}
    with open(checkpoint_file, "w", encoding="utf-8") as f:
        json.dump(checkpoint, f, ensure_ascii=False)
    print(f"已儲存斷點: 頁數 {page}")

def load_checkpoint(checkpoint_file="checkpoint.json"):
    """讀取上次爬到的頁數
    為什麼？讓程式記得上次停在哪裡"""
    if os.path.exists(checkpoint_file):
        try:
            with open(checkpoint_file, "r", encoding="utf-8") as f:
                checkpoint = json.load(f)
                return checkpoint.get("last_page", 1)
        except Exception as e:
            print(f"讀取斷點失敗: {e}")
    return 1

def parse_salary(salary):
    """解析薪資，提取 min、max、avg 和 note
    例如：從 '月薪40,000~60,000元' 提取最小、最大、平均值"""
    if not salary or salary == "待遇面議":
        return None, None, None, "無薪資資訊"
    salary = salary.replace(",", "")
    match = re.match(r"月薪(\d+)(?:~(\d+))?元", salary)
    if match:
        min_salary = int(match.group(1))
        max_salary = int(match.group(2)) if match.group(2) else None
        avg_salary = (min_salary + max_salary) / 2 if max_salary else min_salary
        note = "最低保證薪資" if not max_salary else ""
        return min_salary, max_salary, avg_salary, note
    match = re.match(r"年薪(\d+)(?:~(\d+))?元", salary)
    if match:
        min_salary = int(match.group(1)) // 12
        max_salary = int(match.group(2)) // 12 if match.group(2) else None
        avg_salary = (min_salary + max_salary) / 2 if max_salary else min_salary
        note = "年薪轉換為月薪"
        return min_salary, max_salary, avg_salary, note
    match = re.match(r"時薪(\d+)元", salary)
    if match:
        hourly = int(match.group(1))
        min_salary = hourly * 8 * 22
        max_salary = None
        avg_salary = min_salary
        note = "推估（時薪 × 8小時 × 22天）"
        return min_salary, max_salary, avg_salary, note
    match = re.match(r"日薪(\d+)元", salary)
    if match:
        daily = int(match.group(1))
        min_salary = daily * 22
        max_salary = None
        avg_salary = min_salary
        note = "推估（日薪 × 22天）"
        return min_salary, max_salary, avg_salary, note
    return None, None, None, "無法解析薪資格式"

def extract_skills(text):
    """從文字提取技能關鍵字
    例如：從工作描述中找 'Python' 或 'SQL' 等詞"""
    skills_pattern = r'(?<!\w)(MySQL|PostgreSQL|MS SQL|MongoDB|Redis|AWS|GCP|Cloud SQL|CI/CD|IaC|GDPR|ASP\.NET|MVC|C#|SQL|SAP|S/4 HANA|JavaScript|Python|Java|Docker|Kubernetes|Hadoop|Spark|Kafka|Airflow|Talend|Luigi|Tableau|Power BI|Looker|Scala|Pandas|NumPy|Terraform|Helm|Jenkins|Elasticsearch|Snowflake|Databricks|R)(?!\w)'
    skills = re.findall(skills_pattern, text, re.IGNORECASE)
    # 過濾掉明顯非獨立技能的 'R'
    skills = [s for s in skills if not (s.lower() == 'r' and re.search(r'\w+r\w+', text, re.IGNORECASE))]
    return list(set(skills)) if skills else []

def extract_field_value(driver, keyword, default="未知"):
    """提取指定關鍵字的欄位值（更穩健的 CSS 選擇器）
    例如：找 '管理責任' 的值"""
    try:
        rows = driver.find_elements(By.CSS_SELECTOR, "div.job-description-table div.list-row")
        for row in rows:
            try:
                title_elem = row.find_element(By.CSS_SELECTOR, "h3.h3")
                if keyword in title_elem.text:
                    value_elem = row.find_element(By.CSS_SELECTOR, "div.t3.mb-0")
                    return value_elem.text.strip()
            except:
                continue
    except:
        pass
    return default

def restart_driver(driver, args):
    """重啟瀏覽器以恢復 session
    為什麼？長時間運行後，瀏覽器可能卡住或被網站偵測，重啟可以刷新"""
    try:
        driver.quit()
        print("關閉舊瀏覽器")
    except Exception as e:
        print(f"關閉瀏覽器時發生錯誤: {str(e)}")
    options = Options()
    options.add_argument(f"user-agent={random.choice(user_agents)}")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-web-security")
    if args.headless:
        options.add_argument("--headless=new")
    new_driver = uc.Chrome(options=options)
    time.sleep(5)  # 等待新 session 穩定
    return new_driver

def crawl_job_details(driver, job_id, list_data):
    """爬取單個職缺的細節頁
    步驟：開細節頁，滾動載入內容，提取描述、技能等，合併列表頁資料"""
    url = f"https://www.104.com.tw/job/{job_id}"
    max_retries = 3
    for attempt in range(max_retries):
        try:
            driver.get(url)
            for _ in range(3):
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(random.uniform(2, 4))
            # 等待工作內容
            elements = [
                (By.CSS_SELECTOR, "p.job-description__content"),
                (By.XPATH, "//h2[contains(text(), '工作內容')]/following-sibling::p[contains(@class, 'job-description__content')]"),
                (By.CSS_SELECTOR, "div.job-description__content p")
            ]
            job_description = None
            for by, selector in elements:
                try:
                    WebDriverWait(driver, 20).until(EC.presence_of_element_located((by, selector)))
                    job_description = driver.find_element(by, selector).text.strip()
                    break
                except:
                    continue
            if not job_description:
                print(f"警告: {job_id} 無法找到工作內容")
                job_description = "未知"
            time.sleep(random.uniform(5, 10))
            # 整合 list 資料
            job_detail = {
                "job_id": job_id,
                **{k: v for k, v in list_data.items() if pd.notna(v)}
            }
            # 提取工作內容和技能
            job_detail["job_description"] = job_description
            skills_from_description = extract_skills(job_description)
            # 其他條件
            other_elem = driver.find_elements(By.XPATH,
                                              "//h3[contains(text(), '其他條件')]/ancestor::div[contains(@class, 'list-row')]/following-sibling::div[contains(@class, 'list-row__data')]//div[contains(@class, 'job-requirement-table__data')]//p[contains(@class, 'm-0 r3 w-100')]")
            other_conditions = other_elem[0].text.strip() if other_elem else "無"
            skills_from_other = extract_skills(other_conditions)
            job_detail["skills"] = list(set(skills_from_description + skills_from_other))
            # 職務類別
            job_categories = [cat.text.strip() for cat in driver.find_elements(By.CSS_SELECTOR, "div.category-item div.v-popper u")]
            job_detail["job_categories"] = job_categories if job_categories else ["未知"]
            # 表格欄位
            job_detail["management_responsibility"] = extract_field_value(driver, "管理責任")
            job_detail["work_shift"] = extract_field_value(driver, "上班時段")
            job_detail["remote_work"] = extract_field_value(driver, "遠端工作")
            job_detail["BT_EXP"] = extract_field_value(driver, "出差外派")
            # 語文條件（採用使用者提供的選擇器）
            language_elem = None
            try:
                rows = driver.find_elements(By.CSS_SELECTOR, "div.job-requirement-table div.list-row")
                for row in rows:
                    try:
                        title_elem = row.find_element(By.CSS_SELECTOR, "h3.h3")
                        if "語文條件" in title_elem.text:
                            language_elem = row.find_element(By.CSS_SELECTOR, "u").text.strip()
                            break
                    except:
                        continue
                job_detail["languages"] = language_elem if language_elem else "不拘"
            except:
                job_detail["languages"] = "--"
            # 擅長工具
            tools_elem = [tool.find_element(By.TAG_NAME, "u").text.strip() for tool in driver.find_elements(By.CSS_SELECTOR, "a.tools") if tool.find_elements(By.TAG_NAME, "u")]
            job_detail["tools"] = tools_elem if tools_elem else ["--"]
            # 工作技能
            skills_elem = [skill.find_element(By.TAG_NAME, "u").text.strip() for skill in driver.find_elements(By.CSS_SELECTOR, "a.skills") if skill.find_elements(By.TAG_NAME, "u")]
            job_detail["work_skills"] = skills_elem if skills_elem else ["不拘"]
            # 其他條件
            job_detail["other_conditions"] = other_conditions
            return job_detail
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"嘗試 {attempt + 1} 失敗，{job_id} - {str(e)}，重試中...")
                time.sleep(random.uniform(5, 10))
                continue
            print(f"錯誤: {job_id} - {str(e)}")
            with open(f"error_{job_id}.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            return None

def download_page(driver, url, max_retries=3, existing_job_ids=None):
    """爬取單頁 search list，先收集所有 job_id 及其資訊，再爬細節頁
    步驟：開列表頁，等待載入，收集每個職缺的基本資訊，然後逐一爬細節"""
    for attempt in range(max_retries):
        try:
            driver.get(url)
            time.sleep(10)
            print(f"頁面標題: {driver.title}")
            if "Just a moment..." in driver.title:
                print("檢測到 Cloudflare，等待繞過...")
                time.sleep(random.uniform(180, 240))
                print(f"Cloudflare 等待後標題: {driver.title}")
                print("請在瀏覽器完成 Cloudflare 驗證，然後按 Enter 繼續")
                input()
            # 移除滾動，避免無限滾動載入多頁
            print("不進行滾動，僅抓取初始頁面內容")
            time.sleep(random.uniform(10, 20))  # 等待頁面穩定
            page_source = driver.page_source
            with open(f"page_source_attempt_{attempt + 1}.html", "w", encoding="utf-8") as f:
                f.write(page_source)
            print(f"已存頁面到 page_source_attempt_{attempt + 1}.html")
            soup = BeautifulSoup(page_source, 'html.parser')
            containers = soup.find_all('div', class_='info-container')
            dates = soup.find_all('div', class_='date-container')
            print(f"BeautifulSoup 找到 info-container 數: {len(containers)}")
            print(f"BeautifulSoup 找到日期元素數: {len(dates)}")
            # 等待職缺元素
            WebDriverWait(driver, 60).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.info-container"))
            )
            time.sleep(random.uniform(10, 20))
            # 收集所有 job_id 及其 list 頁資訊
            job_elements = driver.find_elements(By.CSS_SELECTOR, "div.info-container")
            print(f"URL: {url}, 找到職缺數: {len(job_elements)}, 嘗試: {attempt + 1}/{max_retries}")
            if len(job_elements) == 0:
                print("警告：未找到職缺項目，可能選擇器失效")
                return []
            date_elements = driver.find_elements(By.CSS_SELECTOR, "div.date-container")
            print(f"Selenium 找到日期元素數: {len(date_elements)}")
            job_data_list = []  # 儲存 job_id 和 list 頁資訊
            processed_job_ids = set()  # 頁內去重
            for idx in range(len(job_elements)):
                # 每次迴圈重新查找
                job_elements = driver.find_elements(By.CSS_SELECTOR, "div.info-container")
                if idx >= len(job_elements):
                    print(f"警告：索引 {idx} 超過職缺數，可能頁面更新")
                    continue
                job = job_elements[idx]
                row = {}
                try:
                    title_elem = job.find_elements(By.CSS_SELECTOR, "h2 a[data-gtm-joblist=\"職缺-職缺名稱\"]")
                    row["job_title"] = title_elem[0].text.strip() if title_elem else "N/A"
                    job_id = "N/A"
                    if title_elem and title_elem[0].get_attribute("href"):
                        href = title_elem[0].get_attribute("href")
                        match = re.search(r"/job/(\w+)", href)
                        job_id = match.group(1) if match else "N/A"
                    row["job_id"] = job_id
                    if job_id in processed_job_ids:
                        print(f"跳過頁內重複職缺: {job_id}")
                        continue
                    if existing_job_ids and job_id in existing_job_ids:
                        print(f"跳過已存在職缺: {job_id}")
                        continue
                    processed_job_ids.add(job_id)
                    company_elem = job.find_elements(By.CSS_SELECTOR, "a[data-gtm-joblist=\"職缺-公司名稱\"]")
                    row["company"] = company_elem[0].text.strip() if company_elem else "N/A"
                    industry_elem = job.find_elements(By.CSS_SELECTOR, "span[data-gtm-joblist*='職缺-產業'] a")
                    row["industry"] = industry_elem[0].text.strip() if industry_elem else "N/A"
                    location_elem = job.find_elements(By.CSS_SELECTOR, "div.info-tags a[data-gtm-joblist*=\"職缺-地區\"]")
                    row["location"] = location_elem[0].text.strip() if location_elem else "N/A"
                    experience_elem = job.find_elements(By.CSS_SELECTOR, "div.info-tags a[data-gtm-joblist*=\"職缺-經歷\"]")
                    row["experience"] = experience_elem[0].text.strip() if experience_elem else "N/A"
                    education_elem = job.find_elements(By.CSS_SELECTOR, "div.info-tags a[data-gtm-joblist*=\"職缺-學歷\"]")
                    row["education"] = education_elem[0].text.strip() if education_elem else "N/A"
                    salary_elem = job.find_elements(By.CSS_SELECTOR, "div.info-tags a[data-gtm-joblist*=\"職缺-薪資\"]")
                    salary = salary_elem[0].text.strip() if salary_elem else "N/A"
                    row["salary"] = salary
                    min_salary, max_salary, avg_salary, salary_note = parse_salary(salary)
                    row["salary_min"] = min_salary
                    row["salary_max"] = max_salary
                    row["salary_avg"] = avg_salary
                    row["salary_note"] = salary_note
                    tags_elem = job.find_elements(By.CSS_SELECTOR, "div.info-othertags a")
                    row["tags"] = ", ".join([tag.text.strip() for tag in tags_elem]) if tags_elem else "N/A"
                    date_elements = driver.find_elements(By.CSS_SELECTOR, "div.date-container")
                    if idx < len(date_elements):
                        row["update_date"] = date_elements[idx].text.strip()
                    else:
                        row["update_date"] = "N/A"
                        print("警告：日期元素數量不匹配")
                    row["source_url"] = url
                    job_data_list.append(row)
                except Exception as e:
                    print(f"收集職缺 {idx} 資訊失敗: {str(e)}")
                    continue
            # 逐一爬細節頁
            data = []
            job_count = 0
            for row in job_data_list:
                job_id = row["job_id"]
                try:
                    job_detail = crawl_job_details(driver, job_id, row)
                    if job_detail:
                        data.append(job_detail)
                        job_count += 1
                        print(f"已處理職缺 {job_id}，總計 {job_count} 個")
                    # 每 30 個職缺重啟瀏覽器
                    if job_count % 30 == 0:
                        print(f"處理 {job_count} 個職缺後重啟瀏覽器...")
                        driver = restart_driver(driver, args)
                except Exception as e:
                    print(f"爬取細節頁 {job_id} 失敗: {str(e)}")
                    continue
            return data
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"請求錯誤，URL: {url}, 錯誤: {e}, 嘗試: {attempt + 1}/{max_retries}")
                time.sleep(random.uniform(20, 60))
                continue
            print(f"最終錯誤，URL: {url}, 錯誤: {e}")
            return []
    return []

def save_data(data, output_csv, query_params, page=None, start_page=None):
    """儲存資料到 CSV 和 JSON，確保去重
    步驟：轉換列表成字串，產生檔名，讀舊檔合併，去重後寫入"""
    if not data:
        print("無職缺資料可存")
        return
    df = pd.DataFrame(data)
    # 將列表欄位轉為逗號分隔字串，適合 CSV
    for col in ['job_categories', 'skills', 'tools', 'work_skills']:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: ','.join(x) if isinstance(x, list) else x)
    current_date = datetime.now().strftime("%Y%m%d")
    jobcat_match = re.search(r"jobcat=(\w+)", query_params)
    jobcat = jobcat_match.group(1) if jobcat_match else "unknown"
    jobcat_short = jobcat[-4:] if len(jobcat) > 4 else jobcat
    base_name = output_csv.replace(".csv", "")
    filename = f"{base_name}_jobcat_{jobcat_short}.csv"
    json_filename = f"{base_name}_jobcat_{jobcat_short}.json"
    # 如果要階段頁面紀錄:
    # if page and start_page:
    # filename = f"{base_name}_jobcat_{jobcat_short}_{current_date}_pages_{start_page}_to_{page}.csv"
    # json_filename = f"{base_name}_jobcat_{jobcat_short}_{current_date}_pages_{start_page}_to_{page}.json"
    # else:
    # filename = f"{base_name}_jobcat_{jobcat_short}_{current_date}.csv"
    # json_filename = f"{base_name}_jobcat_{jobcat_short}_{current_date}.json"
    # 去重並附加到現有 CSV
    if os.path.exists(filename):
        existing_df = pd.read_csv(filename)
        df = pd.concat([existing_df, df], ignore_index=True)
    df.drop_duplicates(subset=['job_id'], keep='first', inplace=True)
    df.to_csv(filename, index=False, encoding="utf-8-sig")
    print(f"已存為 CSV: {filename}")
    # 儲存 JSON
    with open(json_filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"已存為 JSON: {json_filename}")

def main():
    # 初始化 logging
    # 為什麼？記錄程式過程到檔案，方便後續檢查錯誤
    logging.basicConfig(
        filename = f"crawler_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
        level = logging.INFO,
        format = "%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    logging.info("start")
    start_time = time.time()
    global args  # 為了 restart_driver 使用
    args = parse_arguments()
    checkpoint_file = "checkpoint.json"
    last_page = load_checkpoint(checkpoint_file)
    start_page = max(args.start_page, last_page)
    print(f"從頁數 {start_page} 開始爬（上次斷點: {last_page}）")
    existing_job_ids = load_existing_job_ids(args.existing_csv)
    print(f"現有 job_id 數量: {len(existing_job_ids)}")
    options = Options()
    options.add_argument(f"user-agent={random.choice(user_agents)}")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-web-security")
    if args.headless:
        options.add_argument("--headless=new")
    driver = None
    try:
        driver = uc.Chrome(options=options)
        print("瀏覽器初始化成功")
        all_data = []
        try:
            for page in range(start_page, args.end_page + 1):
                url = f"{args.base_url}?{args.query_params}&{args.pagination.format(page=page)}"
                page_data = download_page(driver, url, max_retries=3, existing_job_ids=existing_job_ids)
                if page_data:
                    all_data.extend(page_data)
                save_checkpoint(page, checkpoint_file)
                if (page % 5 == 0 or page == args.end_page) and all_data:
                    save_data(all_data, args.output_csv, args.query_params, page, start_page)
                    all_data = []  # 清空記憶體
                print(f"第 {page} 頁完成（包含細節）")
                time.sleep(random.uniform(5, 10))
            if all_data:
                save_data(all_data, args.output_csv, args.query_params)
        except KeyboardInterrupt:
            print("偵測到手動中斷 (Ctrl+C)，儲存當前結果...")
            if all_data:
                save_data(all_data, args.output_csv, args.query_params, args.end_page, args.start_page)
            print("已儲存當前爬取結果，並去重複。")
            # ... 爬蟲程式結束log（例如 download_page 迴圈）
            end_time = time.time()
            logging.info(f"end total: {end_time - start_time:.2f} s")
    except Exception as e:
        print(f"程式執行錯誤: {e}")
    finally:
        if driver:
            try:
                driver.quit()
                print("瀏覽器已關閉")
            except Exception as e:
                print(f"關閉瀏覽器時發生錯誤，已忽略: {e}")
            try:
                terminated = cleanup_chrome_processes()
                print(f"清理終止 {terminated} 個進程")
            except Exception as e:
                print(f"清理進程時發生錯誤，已忽略: {e}")

if __name__ == "__main__":
    main()
