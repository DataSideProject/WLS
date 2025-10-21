import pandas as pd
import time
import random
import json
import re
import socket
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import undetected_chromedriver as uc
from selenium.common.exceptions import WebDriverException
from typing import List, Dict, Optional
import argparse

# 設定 Selenium 選項
def get_driver(max_retries=3):
    for attempt in range(max_retries):
        try:
            options = Options()
            options.add_argument(
                f"user-agent={random.choice(['Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/141.0.0.0 Safari/537.36', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/141.0.0.0 Safari/537.36'])}")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--start-maximized")
            options.add_argument("--disable-gpu")
            return uc.Chrome(options=options)
        except (socket.gaierror, urllib.error.URLError) as e:
            if attempt < max_retries - 1:
                print(f"網路錯誤，嘗試 {attempt + 1} 失敗: {str(e)}，重試中...")
                time.sleep(random.uniform(5, 10))
                continue
            raise Exception(f"無法初始化瀏覽器，網路錯誤: {str(e)}")

# 全局瀏覽器實例
driver = get_driver()

# 讀取 CSV 檔案
csv_file = 'job_data_jobcat_1022_20251019.csv'
df = pd.read_csv(csv_file)

# 解析命令行參數
parser = argparse.ArgumentParser(description="Crawl 104 job details")
parser.add_argument("--start_idx", type=int, default=0, help="Start index of job IDs")
parser.add_argument("--end_idx", type=int, default=len(df), help="End index of job IDs")
args = parser.parse_args()

# 儲存結果的列表
job_data: List[Dict] = []

def extract_skills(text: str) -> List[str]:
    """提取技能關鍵字，擴展以涵蓋更多資料工程技能"""
    skills_pattern = r'(MySQL|PostgreSQL|MS SQL|MongoDB|Redis|AWS|GCP|Cloud SQL|CI/CD|IaC|GDPR|ASP.NET|MVC|C#|SQL|SAP|S/4 HANA|JavaScript|Python|Java|Docker|Kubernetes|Hadoop|Spark|Kafka|Airflow|Talend|Luigi|Tableau|Power BI|Looker|Scala|R|Pandas|NumPy|Terraform|Helm|Jenkins|Elasticsearch|Snowflake|Databricks)'
    skills = re.findall(skills_pattern, text, re.IGNORECASE)
    return list(set(skills)) if skills else []

def extract_field_value(rows: List, keyword: str, default: str = "未知") -> str:
    """提取指定關鍵字的欄位值"""
    for row in rows:
        try:
            title_elem = row.find_element(By.CSS_SELECTOR, "h3.h3")
            if keyword in title_elem.text:
                value_elem = row.find_element(By.CSS_SELECTOR, "div.t3.mb-0")
                return value_elem.text.strip()
        except:
            continue
    return default

def crawl_job_details(job_id: str, original_data: Dict) -> Optional[Dict]:
    """
    爬取指定 job_id 的詳細頁面資料
    """
    url = f"https://www.104.com.tw/job/{job_id}"
    max_retries = 3
    for attempt in range(max_retries):
        try:
            driver.get(url)
            # 滾動頁面確保內容載入
            for _ in range(3):
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(random.uniform(1, 3))

            # 等待頁面載入，嘗試多個選擇器
            elements = [
                (By.CSS_SELECTOR, "p.job-description__content"),
                (By.XPATH, "//h2[contains(text(), '工作內容')]/following-sibling::p[contains(@class, 'job-description__content')]"),
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
                raise Exception("無法找到工作內容")

            time.sleep(random.uniform(5, 15))

            # 緩存所有 rows 減少查詢
            rows = driver.find_elements(By.CSS_SELECTOR, "div.job-description-table div.list-row")

            # 提取資料
            job_detail = {
                "job_id": job_id,
                **{k: v for k, v in original_data.items() if pd.notna(v)}
            }

            # 工作內容
            job_detail["job_description"] = job_description

            # 提取並合併技能
            skills_from_description = extract_skills(job_description)
            other_elem = driver.find_elements(By.XPATH, "//h3[contains(text(), '其他條件')]/ancestor::div[contains(@class, 'list-row')]/following-sibling::div[contains(@class, 'list-row__data')]//div[contains(@class, 'job-requirement-table__data')]//p[contains(@class, 'm-0 r3 w-100')]")
            other_conditions = other_elem[0].text.strip() if other_elem else "無"
            skills_from_other = extract_skills(other_conditions)
            job_detail["skills"] = list(set(skills_from_description + skills_from_other))

            # 職務類別
            job_categories = [cat.text.strip() for cat in driver.find_elements(By.CSS_SELECTOR, "div.category-item div.v-popper u")]
            job_detail["job_categories"] = job_categories if job_categories else ["未知"]

            # 其他欄位
            job_detail["management_responsibility"] = extract_field_value(rows, "管理責任")
            job_detail["work_shift"] = extract_field_value(rows, "上班時段")
            job_detail["remote_work"] = extract_field_value(rows, "遠端工作")
            job_detail["BT_EXP"] = extract_field_value(rows, "出差外派")

            # 語文條件
            language_elem = next((row.find_element(By.CSS_SELECTOR, "div.job-requirement-table div.list-row").text.strip() for row in rows if "語文條件" in row.find_element(By.CSS_SELECTOR, "h3.h3").text), "不拘")
            job_detail["languages"] = language_elem

            # 擅長工具
            tools_elem = [tool.find_element(By.TAG_NAME, "u").text.strip() for tool in driver.find_elements(By.CSS_SELECTOR, "a.tools") if tool.find_elements(By.TAG_NAME, "u")]
            job_detail["tools"] = tools_elem if tools_elem else ["不拘"]

            # 工作技能
            skills_elem = [skill.find_element(By.TAG_NAME, "u").text.strip() for skill in driver.find_elements(By.CSS_SELECTOR, "a.skills") if skill.find_elements(By.TAG_NAME, "u")]
            job_detail["work_skills"] = skills_elem if skills_elem else ["不拘"]

            # 其他條件
            job_detail["other_conditions"] = other_conditions

            return job_detail
        except WebDriverException as e:
            if attempt < max_retries - 1 and "invalid session id" in str(e).lower():
                print(f"Session 失效，{job_id} - {str(e)}，重試中...")
                time.sleep(random.uniform(5, 10))
                continue
            raise
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"嘗試 {attempt + 1} 失敗，{job_id} - {str(e)}，重試中...")
                time.sleep(random.uniform(5, 10))
                continue
            print(f"錯誤: {job_id} - {str(e)}")
            with open(f"error_{job_id}.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            return None

def restart_driver():
    """重啟瀏覽器以恢復 session"""
    global driver
    if 'driver' in globals() and driver:
        try:
            driver.quit()
        except Exception as e:
            print(f"關閉瀏覽器時發生錯誤: {str(e)}")
    driver = get_driver()
    time.sleep(5)  # 等待新 session 穩定

# 測試職缺，支援分批處理
for index, row in df.iloc[args.start_idx:args.end_idx].iterrows():
    job_id = row['job_id']
    print(f"處理職缺: {job_id}")
    try:
        job_detail = crawl_job_details(job_id, row.to_dict())
        if job_detail:
            job_data.append(job_detail)
        # 每 30 個職缺重啟一次瀏覽器
        if (index + 1 - args.start_idx) % 30 == 0:
            print(f"處理 {index + 1} 個職缺後重啟瀏覽器...")
            restart_driver()
    except WebDriverException as e:
        if "invalid session id" in str(e).lower():
            print(f"Session 失效，自動重啟並繼續，{job_id} - {str(e)}")
            restart_driver()
            job_detail = crawl_job_details(job_id, row.to_dict())
            if job_detail:
                job_data.append(job_detail)
        else:
            raise
    except Exception as e:
        print(f"意外錯誤: {job_id} - {str(e)}")
        with open(f"error_{job_id}.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)

# 將資料轉為 DataFrame 並存為 CSV
df_result = pd.DataFrame(job_data)
# 將列表欄位轉為逗號分隔字串，適合 CSV
for col in ['job_categories', 'skills', 'tools', 'work_skills']:
    df_result[col] = df_result[col].apply(lambda x: ','.join(x) if isinstance(x, list) else x)
df_result.to_csv(f'detailed_job_data_jobcat_202510{time.localtime().tm_mday:02d}.csv', index=False, encoding='utf-8-sig')

# 儲存為 JSON 檔案
output_file = f'detailed_job_data_jobcat_202510{time.localtime().tm_mday:02d}.json'  # 使用當前日期命名
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(job_data, f, ensure_ascii=False, indent=2)

# 關閉瀏覽器
driver.quit()
print(f"資料已儲存至 {output_file} 和 detailed_job_data_jobcat_202510{time.localtime().tm_mday:02d}.csv")
