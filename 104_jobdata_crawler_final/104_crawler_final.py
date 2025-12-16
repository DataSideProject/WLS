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

# ==================== 搜尋設定 (SEARCH_CONFIG) ====================
# 您可以在這裡快速切換不同的搜尋模式，無需修改程式碼核心。
SEARCH_CONFIG = {
    # 目前啟用的模式 (修改此字串即可切換)
    # 選項: "category_scan" (預設), "keyword_scan", "custom_url"
    "active_mode": "category_scan",

    "modes": {
        # [模式 A] 職缺類別掃描 (針對多個類別，逐一爬取)
        "category_scan": {
            # 完整參數字串 (包含 ro, area 等設定)
            # jobcat 裡面放多個代碼，程式會自動拆開來爬
            "params": "jobcat=2007001022,2007001012,2007001020,2007001026,2007001018&ro=0",
            
            # 告訴程式針對哪個參數做「拆分」
            # 填寫 "jobcat" 代表它會把上面的 2007... 拆成五次執行
            "split_by": "jobcat" 
        },

        # [模式 B] 關鍵字掃描 (範例)
        "keyword_scan": {
            "params": "keyword=Python,Data Scientist,Backend Engineer&ro=0&area=6001000000",
            "split_by": "keyword" # 針對關鍵字逐一爬取
        },

        # [模式 C] 自訂單一網址/參數
        "custom_url": {
            "params": "jobcat=2007001000&area=6001001000&ro=0", # 單純爬這個組合
            "split_by": None # 不拆分
        }
    }
}

user_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

def parse_arguments():
    # Load defaults from Config
    mode = SEARCH_CONFIG["active_mode"]
    config = SEARCH_CONFIG["modes"].get(mode, SEARCH_CONFIG["modes"]["category_scan"])
    default_params = config["params"]

    parser = argparse.ArgumentParser(description="104 Crawler Accelerated (Final)")
    parser.add_argument("--base_url", default="https://www.104.com.tw/jobs/search")
    
    # 使用 Config 中的 params 作為預設值
    parser.add_argument("--query_params", default=default_params, help="URL Query Parameters (Override via Config)")
    
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

def save_checkpoint(current_cat, page, completed_cats):
    data = {
        "current_cat": current_cat,
        "page": page,
        "completed_cats": list(completed_cats)
    }
    with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

def load_checkpoint():
    if os.path.exists(CHECKPOINT_FILE):
        try:
            with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {
                    "current_cat": data.get("current_cat"),
                    "page": data.get("page", 1),
                    "completed_cats": set(data.get("completed_cats", []))
                }
        except:
            pass
    return {"current_cat": None, "page": 1, "completed_cats": set()}


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
    if driver is None: return [], None, 0
    
    try:
        driver.get(url)
        # 加速：等待列表容器
        try:
            WebDriverWait(driver, 8).until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.info-container")))
        except:
            pass # Timeout? Check if empty
        
        # 簡單滾動載入 (只滾動一次到底部)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1.5) # 加速：只睡 1.5 秒
        
        jobs = driver.find_elements(By.CSS_SELECTOR, "div.info-container")
        dates = driver.find_elements(By.CSS_SELECTOR, "div.date-container")
        
        total_found = len(jobs)
        print(f"URL: {url}, 找到 {total_found} 筆")
        
        if not jobs: return [], driver, 0

        list_rows = []
        seen_job_ids = set()
        
        # ... (list parsing logic same as before) ...
        for idx, job in enumerate(jobs):
            try:
                title_a = job.find_elements(By.CSS_SELECTOR, "h2 a[data-gtm-joblist=\"職缺-職缺名稱\"]")
                if not title_a: continue
                
                # Extract ID from links
                href = title_a[0].get_attribute("href")
                match = re.search(r"/job/(\w+)", href)
                job_id = match.group(1) if match else "N/A"
                
                if job_id in seen_job_ids: continue
                seen_job_ids.add(job_id)

                row = {
                    "job_id": job_id,
                    "job_title": title_a[0].text.strip(),
                    "company": job.find_element(By.CSS_SELECTOR, "a[data-gtm-joblist=\"職缺-公司名稱\"]").text.strip(),
                    # Using safe finds for optional tags could be better but sticking to strict for now based on prev code
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
            
            # time.sleep(0.5) 
        
        return data, driver, total_found
        
    except Exception as e:
        print(f"頁面失敗: {e}")
        return [], driver, 0


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
    
    # Load Config & Checkpoint
    mode = SEARCH_CONFIG["active_mode"]
    config = SEARCH_CONFIG["modes"].get(mode, {})
    split_param = config.get("split_by") # e.g., "jobcat" or "keyword" or None

    checkpoint = load_checkpoint()
    completed_items = checkpoint["completed_cats"] # reusing same field name for generic items
    last_item = checkpoint["current_cat"]
    last_page_num = checkpoint["page"]

    # Parse Split Items (generic)
    target_items = []
    base_params = args.query_params
    
    if split_param:
        # Regex to find "param=Value1,Value2"
        # Handles potential URL encoding if needed, but assuming simple comma list for now
        pattern = f"{split_param}=([^&]+)"
        match = re.search(pattern, base_params)
        if match:
            # Split values
            val_str = match.group(1)
            target_items = val_str.split(',')
        else:
            # Param not found, run as single pass
            target_items = ['default']
    else:
        # No split needed (Custom URL mode)
        target_items = ['default']

    print(f"=== 加速版爬蟲啟動 ({mode}) ===")
    print(f"拆分參數: {split_param}")
    print(f"目標項目數: {len(target_items)} | Items: {target_items}")
    print(f"已完成項目: {completed_items}")
    
    existing_keys = load_existing_keys()
    print(f"已抓取資料量: {len(existing_keys)} 筆")


    try:
        driver = create_driver(args)
        
        for item in target_items:
            # Skip if completed (unless it's 'default' which acts as single pass placeholder)
            if item != 'default' and item in completed_items:
                print(f"項目 {item} 已完成，跳過。")
                continue
            
            # Determine start page
            current_start_page = 1
            if item == last_item:
                current_start_page = last_page_num
                print(f"恢復項目 {item} 進度，從第 {current_start_page} 頁開始。")
            else:
                print(f"開始爬取項目: {item}")

            # Construct Query Params
            current_params = base_params
            if item != 'default' and split_param:
                # Replace the full list with single item
                # e.g. jobcat=A,B,C -> jobcat=A
                current_params = re.sub(f"{split_param}=[^&]+", f"{split_param}={item}", base_params)

            all_data = []
            
            # Page Loop
            for page in range(current_start_page, args.end_page + 1):
                url = f"{args.base_url}?{current_params}&{args.pagination.format(page=page)}"
                
                # Check point labeling
                label = item if item != 'default' else 'SinglePass'
                
                page_data, driver, total_found_on_page = download_page(driver, url, existing_keys, crawl_date_str, args)
                
                if page_data:
                    all_data.extend(page_data)
                    
                if all_data:
                    save_data(all_data, args.output_csv, current_params)
                    all_data = [] 
                
                # Checkpoint
                save_checkpoint(item, page + 1, completed_items)
                
                print(f"[{label}] 第 {page} 頁完成 (新增 {len(page_data)} 筆 / 頁面總數 {total_found_on_page})")
                
                # End Condition: No items found on the page at all
                if total_found_on_page == 0:
                    print(f"[{label}] 第 {page} 頁無任何職缺，視為該項目結束。")
                    break
                
                # If total > 0 but page_data == 0, it means all were duplicates. We continue to next page.
                if len(page_data) == 0:
                    print(f"[{label}] 第 {page} 頁全為重複資料，繼續爬取下一頁...")

                time.sleep(1)


            # End of Item
            if item != 'default':
                completed_items.add(item)
            save_checkpoint(None, 1, completed_items)
            print(f"項目 {item} 完成。")



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
