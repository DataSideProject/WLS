# 104_crawler_final.py
# 加速版 (正式整合)：不載入圖片、Eager Loading、減少等待時間
# ⚠️ 注意：加速可能增加被擋風險，請斟酌使用

import pandas as pd
import time
import random
import argparse
from datetime import datetime
import re
import os
import json
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import undetected_chromedriver as uc
import psutil
from bs4 import BeautifulSoup
import logging

# -------------------------------------------------
# 1. 參數 & 工具函式
# -------------------------------------------------
user_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

def parse_arguments():
    parser = argparse.ArgumentParser(description="104 Crawler Accelerated (Final)")
    parser.add_argument("--base_url", default="https://www.104.com.tw/jobs/search")
    # Restore original default query params for production
    parser.add_argument("--query_params", default="jobcat=2007001022,2007001012,2007001020,2007001026,2007001018")
    parser.add_argument("--pagination", default="page={page}")
    parser.add_argument("--start_page", type=int, default=1)
    parser.add_argument("--end_page", type=int, default=150)
    parser.add_argument("--output_csv", default="job_data.csv")
    parser.add_argument("--headless", action="store_true", default=False) 
    return parser.parse_args()

def cleanup_chrome_processes():
    terminated = 0
    for proc in psutil.process_iter(['name']):
        if proc.info['name'] in ['chrome.exe', 'chromedriver.exe']:
            try:
                proc.kill()
                terminated += 1
            except:
                pass
    return terminated

# -------------------------------------------------
# 2. 斷點 & 複合去重
# -------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Restore original checkpoint filename
CHECKPOINT_FILE = os.path.join(BASE_DIR, "checkpoint.json") 
EXISTING_KEYS_FILE = os.path.join(BASE_DIR, "existing_keys.txt") 

def save_checkpoint(page):
    with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump({"last_page": page}, f, ensure_ascii=False)

def load_checkpoint():
    if os.path.exists(CHECKPOINT_FILE):
        try:
            with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
                return json.load(f).get("last_page", 1)
        except:
            return 1
    return 1

def load_existing_keys():
    if os.path.exists(EXISTING_KEYS_FILE):
        with open(EXISTING_KEYS_FILE, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_existing_key(key):
    with open(EXISTING_KEYS_FILE, "a", encoding="utf-8") as f:
        f.write(key + "\n")

# -------------------------------------------------
# 3. 日期清理
# -------------------------------------------------
def clean_update_date(date_str, crawl_date_str):
    if pd.isna(date_str) or not str(date_str).strip() or 'N/A' in str(date_str):
        return f"CRAWL_{crawl_date_str}"
    
    txt = str(date_str).strip()
    m = re.search(r'(\d{1,2})月(\d{1,2})日', txt)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
    else:
        m = re.search(r'(\d{1,2})/(\d{1,2})', txt)
        if m:
            month, day = int(m.group(1)), int(m.group(2))
        else:
            return f"CRAWL_{crawl_date_str}"

    today = datetime.strptime(crawl_date_str, "%Y-%m-%d")
    year = today.year
    try:
        candidate = datetime(year, month, day)
        if candidate > today:
            year -= 1
    except ValueError:
        return f"CRAWL_{crawl_date_str}"

    return f"{year}-{month:02d}-{day:02d}"

# -------------------------------------------------
# 4. 瀏覽器設定 (加速核心)
# -------------------------------------------------
def create_driver(args):
    options = Options()
    # 隨機 User-Agent
    options.add_argument(f"user-agent={random.choice(user_agents)}")
    
    # === 加速設定 ===
    # 1. 頁面載入策略: eager (DOMContentLoaded 就視為載入完成，不用等圖片)
    options.page_load_strategy = 'eager' 
    
    # 2. 禁止圖片與 CSS (最有效)
    prefs = {
        "profile.managed_default_content_settings.images": 2, 
        "profile.managed_default_content_settings.stylesheets": 2,
        "profile.default_content_setting_values.notifications": 2
    }
    options.add_experimental_option("prefs", prefs)
    
    # 標準反爬蟲設定
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    if args.headless:
        options.add_argument("--headless=new")

    driver = uc.Chrome(options=options)
    driver.set_page_load_timeout(15) # 設定超時
    return driver

# -------------------------------------------------
# 5. 爬蟲邏輯 (簡化等待)
# -------------------------------------------------
def extract_field_value(driver, keyword, default="未知"):
    try:
        # 使用 XPath 定位加快速度 (也可以用 CSS)
        xpath = f"//div[contains(@class,'job-description-table')]//div[contains(@class,'list-row')][contains(., '{keyword}')]//div[contains(@class,'t3')]"
        elem = driver.find_element(By.XPATH, xpath)
        return elem.text.strip()
    except:
        return default

def crawl_job_details(driver, job_id, list_data, args):
    if driver is None: return None, None
    url = f"https://www.104.com.tw/job/{job_id}"
    
    try:
        driver.get(url)
        # 不用死等，只要主要的容器出現即可
        try:
            WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, "p.job-description__content")))
        except:
            pass # 即使沒等到也嘗試抓取

        # ---- 工作內容 ----
        job_description = "未知"
        try:
            job_description = driver.find_element(By.CSS_SELECTOR, "p.job-description__content").text.strip()
        except:
            try:
                job_description = driver.find_element(By.CSS_SELECTOR, "div.job-description__content").text.strip()
            except: pass

        # ---- 職務類別 ----
        try:
            cats = [c.text.strip() for c in driver.find_elements(By.CSS_SELECTOR, "div.category-item")]
            job_categories = ", ".join(cats)
        except: job_categories = "未知"

        # ---- 表格欄位 ----
        management_responsibility = extract_field_value(driver, "管理責任", "不需負擔管理責任")
        work_shift = extract_field_value(driver, "上班時段", "未知")
        remote_work = extract_field_value(driver, "遠端工作", "未知")
        BT_EXP = extract_field_value(driver, "出差外派", "無需出差外派")

        # ---- 擅長工具 ----
        tools = "--"
        try:
            tool_elems = driver.find_elements(By.CSS_SELECTOR, "a.tools u")
            if tool_elems:
                tools = ", ".join([t.text.strip() for t in tool_elems])
        except: pass

        # ---- 工作技能 ----
        work_skills = "不拘"
        try:
            skill_elems = driver.find_elements(By.CSS_SELECTOR, "a.skills u")
            if skill_elems:
                work_skills = ", ".join([s.text.strip() for s in skill_elems])
        except: pass

        # ---- 合併結果 ----
        job_detail = {
            "job_id": job_id,
            **{k: v for k, v in list_data.items() if pd.notna(v)},
            "job_description": job_description,
            "job_categories": job_categories,
            "management_responsibility": management_responsibility,
            "work_shift": work_shift,
            "remote_work": remote_work,
            "BT_EXP": BT_EXP,
            "tools": tools,
            "work_skills": work_skills,
        }
        return job_detail, driver

    except Exception as e:
        print(f"細節頁 {job_id} 失敗: {e}")
        return None, driver

def download_page(driver, url, existing_keys, crawl_date_str, args):
    if driver is None: return [], None
    
    try:
        driver.get(url)
        # 加速：等待列表容器
        WebDriverWait(driver, 8).until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.info-container")))
        
        # 簡單滾動載入 (只滾動一次到底部)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1.5) # 加速：只睡 1.5 秒
        
        jobs = driver.find_elements(By.CSS_SELECTOR, "div.info-container")
        dates = driver.find_elements(By.CSS_SELECTOR, "div.date-container")
        print(f"URL: {url}, 找到 {len(jobs)} 筆")
        
        if not jobs: return []

        list_rows = []
        seen_job_ids = set()
        
        for idx, job in enumerate(jobs):
            try:
                title_a = job.find_elements(By.CSS_SELECTOR, "h2 a[data-gtm-joblist=\"職缺-職缺名稱\"]")
                if not title_a: continue
                href = title_a[0].get_attribute("href")
                match = re.search(r"/job/(\w+)", href)
                job_id = match.group(1) if match else "N/A"
                
                if job_id in seen_job_ids: continue
                seen_job_ids.add(job_id)

                row = {
                    "job_id": job_id,
                    "job_title": title_a[0].text.strip(),
                    "company": job.find_element(By.CSS_SELECTOR, "a[data-gtm-joblist=\"職缺-公司名稱\"]").text.strip(),
                    "industry": job.find_element(By.CSS_SELECTOR, "span[data-gtm-joblist*='職缺-產業']").text.strip(),
                    "location": job.find_element(By.CSS_SELECTOR, "div.info-tags a[data-gtm-joblist*=\"職缺-地區\"]").text.strip(),
                    "experience": job.find_element(By.CSS_SELECTOR, "div.info-tags a[data-gtm-joblist*=\"職缺-經歷\"]").text.strip(),
                    "education": job.find_element(By.CSS_SELECTOR, "div.info-tags a[data-gtm-joblist*=\"職缺-學歷\"]").text.strip(),
                    "salary": job.find_element(By.CSS_SELECTOR, "div.info-tags a[data-gtm-joblist*=\"職缺-薪資\"]").text.strip(),
                    "update_date": dates[idx].text.strip() if idx < len(dates) else "N/A"
                }
                list_rows.append(row)
            except: continue
        
        # ---- 爬細節 ----
        data = []
        for row in list_rows:
            uniq = f"{row['job_id']}|{clean_update_date(row['update_date'], crawl_date_str)}"
            
            if uniq in existing_keys:
                # print(f"跳過重複: {uniq}") # 加速：不印那麼多字
                continue
                
            detail, driver = crawl_job_details(driver, row['job_id'], row, args)
            if detail:
                detail["update_date_clean"] = clean_update_date(row['update_date'], crawl_date_str)
                detail["unique_key"] = uniq
                data.append(detail)
                existing_keys.add(uniq)
                save_existing_key(uniq)
            
            # 加速：不再每次 fetch 都睡，只象徵性稍微緩衝 0.5 秒
            # time.sleep(0.5) 
        
        return data, driver
        
    except Exception as e:
        print(f"頁面失敗: {e}")
        return [], driver
    return [], driver

# -------------------------------------------------
# 6. 儲存
# -------------------------------------------------
def save_data(data, output_csv, query_params):
    if not data: return
    df = pd.DataFrame(data)
    
    # 檔名處理 (同原版)
    jobcat_match = re.search(r"jobcat=([^&]+)", query_params)
    if jobcat_match:
        jobcat_short = "_".join([code[-4:] for code in jobcat_match.group(1).split(',')])
    else:
        jobcat_short = "unknown"
        
    # === 2. 檔名 ===
    current_date = datetime.now().strftime("%Y%m%d")
    base_name = output_csv.replace(".csv", "")
    
    daily_filename = os.path.join(BASE_DIR, f"{base_name}_jobcat_{jobcat_short}_raw_{current_date}.csv")
    master_filename = os.path.join(BASE_DIR, f"{base_name}_master_raw.csv")
    if os.path.exists(master_filename):
        master_df = pd.read_csv(master_filename)
        df = pd.concat([master_df, df], ignore_index=True)
    
    df.drop_duplicates(subset=['unique_key'], keep='last', inplace=True)
    df.to_csv(master_filename, index=False, encoding="utf-8-sig")
    print(f"已儲存 {len(data)} 筆至 {master_filename} (總筆數: {len(df)})")

# -------------------------------------------------
# 7. 主程式
# -------------------------------------------------
def main():
    args = parse_arguments()
    crawl_date_str = datetime.now().strftime("%Y-%m-%d")
    
    log_dir = os.path.join(BASE_DIR, "logs")
    os.makedirs(log_dir, exist_ok=True)
    
    start_page = max(args.start_page, load_checkpoint())
    
    logging.basicConfig(
        filename=os.path.join(log_dir, f"crawler_final_{crawl_date_str}.log"),
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )
    logging.info("=== START ===")
    
    existing_keys = load_existing_keys()
    print(f"=== 加速版爬蟲啟動 (Final) ===")
    print(f"設定: 不載入圖片 | Eager Loading | Start: {start_page} | End: {args.end_page}")
    print(f"已抓取資料量: {len(existing_keys)} 筆")

    try:
        driver = create_driver(args)
        all_data = []

        for page in range(start_page, args.end_page + 1):
            url = f"{args.base_url}?{args.query_params}&{args.pagination.format(page=page)}"
            page_data, driver = download_page(driver, url, existing_keys, crawl_date_str, args)
            
            if page_data:
                all_data.extend(page_data)
                
            # 每頁存檔
            if all_data:
                save_data(all_data, args.output_csv, args.query_params)
                all_data = []
            
            save_checkpoint(page + 1)
            print(f"第 {page} 頁完成")
            # 加速：換頁只睡 1 秒 (原版 3~10秒)
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n使用者中斷")
    except Exception as e:
        print(f"\n未預期錯誤: {e}")
    finally:
        if driver:
            try: driver.quit()
            except: pass
        cleanup_chrome_processes()
        print("=== 爬蟲結束 ===")

if __name__ == "__main__":
    main()
