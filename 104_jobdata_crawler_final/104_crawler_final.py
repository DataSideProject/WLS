# 104_crawler_final.py
# 只抓 raw data，支援 job_id + update_date 複合去重、斷點續爬、每日 + master 檔

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
# 1. 參數 & 工具函式（保持不變）
# -------------------------------------------------
user_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/141.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/141.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0",
]

def parse_arguments():
    parser = argparse.ArgumentParser(description="104 raw crawler")
    parser.add_argument("--base_url", default="https://www.104.com.tw/jobs/search")
    parser.add_argument("--query_params", default="jobcat=2007001022,2007001012,2007001020,2007001026,2007001018")
    parser.add_argument("--pagination", default="page={page}")
    parser.add_argument("--start_page", type=int, default=1)
    parser.add_argument("--end_page", type=int, default=107)
    parser.add_argument("--output_csv", default="job_data.csv")
    parser.add_argument("--headless", action="store_true", default=False)
    return parser.parse_args()

def cleanup_chrome_processes():
    terminated = 0
    for proc in psutil.process_iter(['name']):
        if proc.info['name'] in ['chrome.exe', 'chromedriver.exe']:
            proc.kill()
            terminated += 1
    return terminated

# -------------------------------------------------
# 2. 斷點 & 複合去重
# -------------------------------------------------
CHECKPOINT_FILE = "checkpoint.json"
EXISTING_KEYS_FILE = "existing_keys.txt"

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
# 3. 日期清理（廣告職缺補 CRAWL_YYYY-MM-DD）
# -------------------------------------------------
def clean_update_date(date_str, crawl_date_str):
    """
    把 104 的 update_date 轉成 YYYY-MM-DD
    支援：
        1. 11月14日   → 2025-11-14
        2. 11/14      → 2025-11-14
        3. 11/4       → 2025-11-04
        4. 空值 / N/A → CRAWL_YYYY-MM-DD
    """
    if pd.isna(date_str) or not str(date_str).strip() or 'N/A' in str(date_str):
        return f"CRAWL_{crawl_date_str}"

    txt = str(date_str).strip()

    # 1. 11月14日
    m = re.search(r'(\d{1,2})月(\d{1,2})日', txt)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
    else:
        # 2. 11/14 或 11/4
        m = re.search(r'(\d{1,2})/(\d{1,2})', txt)
        if m:
            month, day = int(m.group(1)), int(m.group(2))
        else:
            # 完全無法解析 → 當作爬取日
            return f"CRAWL_{crawl_date_str}"

    # 自動判斷年份（若月份已過當前月份，視為前一年）
    # 正確
    today = datetime.strptime(crawl_date_str, "%Y-%m-%d")
    year = today.year
    try:
        candidate = datetime(year, month, day)
        # 若算出的日期已經「過了」今天 → 屬於前一年
        if candidate > today:
            year -= 1
    except ValueError:   # day 超出當月天數（極少見）
        return f"CRAWL_{crawl_date_str}"

    return f"{year}-{month:02d}-{day:02d}"
# -------------------------------------------------
# 4. 瀏覽器重啟
# -------------------------------------------------
def restart_driver(driver, args):
    try:
        driver.quit()
    except:
        pass
    options = Options()
    options.add_argument(f"user-agent={random.choice(user_agents)}")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-web-security")
    if args.headless:
        options.add_argument("--headless=new")
    return uc.Chrome(options=options)

# -------------------------------------------------
# 5. **全域** 欄位抽取函式（修正點）
# -------------------------------------------------
def extract_field_value(driver, keyword, default="未知"):
    """從細節頁的表格抽取指定欄位"""
    try:
        rows = driver.find_elements(By.CSS_SELECTOR, "div.job-description-table div.list-row")
        for row in rows:
            try:
                title = row.find_element(By.CSS_SELECTOR, "h3.h3").text
                if keyword in title:
                    value = row.find_element(By.CSS_SELECTOR, "div.t3.mb-0").text.strip()
                    return value
            except:
                continue
    except:
        pass
    return default

# -------------------------------------------------
# 6. 細節頁爬蟲（使用全域 extract_field_value）
# -------------------------------------------------
def crawl_job_details(driver, job_id, list_data, args):
    url = f"https://www.104.com.tw/job/{job_id}"
    max_retries = 3
    for attempt in range(max_retries):
        try:
            driver.get(url)
            for _ in range(3):
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(random.uniform(3, 8))

            # ---- 工作內容 ----
            job_description = "未知"
            selectors = [
                (By.CSS_SELECTOR, "p.job-description__content"),
                (By.XPATH, "//h2[contains(text(),'工作內容')]/following-sibling::p[contains(@class,'job-description__content')]"),
                (By.CSS_SELECTOR, "div.job-description__content p")
            ]
            for by, sel in selectors:
                try:
                    WebDriverWait(driver, 20).until(EC.presence_of_element_located((by, sel)))
                    job_description = driver.find_element(by, sel).text.strip()
                    break
                except:
                    continue

            # ---- 職務類別 ----
            cats = [c.text.strip() for c in driver.find_elements(By.CSS_SELECTOR, "div.category-item div.v-popper u")]
            job_categories = ", ".join(cats) if cats else "未知"

            # ---- 表格欄位（使用全域函式）----
            management_responsibility = extract_field_value(driver, "管理責任", "不需負擔管理責任")
            work_shift               = extract_field_value(driver, "上班時段", "未知")
            remote_work              = extract_field_value(driver, "遠端工作", "未知")
            BT_EXP                   = extract_field_value(driver, "出差外派", "無需出差外派")

            # ---- 語文條件 ----
            languages = "不拘"
            try:
                rows = driver.find_elements(By.CSS_SELECTOR, "div.job-requirement-table div.list-row")
                for row in rows:
                    if "語文條件" in row.find_element(By.CSS_SELECTOR, "h3.h3").text:
                        languages = row.find_element(By.CSS_SELECTOR, "u").text.strip()
                        break
            except:
                pass

            # ---- 擅長工具 / 工作技能 ----
            tools = [t.find_element(By.TAG_NAME, "u").text.strip()
                     for t in driver.find_elements(By.CSS_SELECTOR, "a.tools")
                     if t.find_elements(By.TAG_NAME, "u")]
            tools = ", ".join(tools) if tools else "--"

            work_skills = [s.find_element(By.TAG_NAME, "u").text.strip()
                         for s in driver.find_elements(By.CSS_SELECTOR, "a.skills")
                         if s.find_elements(By.TAG_NAME, "u")]
            work_skills = ", ".join(work_skills) if work_skills else "不拘"

            # ---- 其他條件 ----
            other_conditions = "無"
            elems = driver.find_elements(By.CSS_SELECTOR, "div.job-requirement-table__data p.m-0.r3.w-100")
            if elems:
                other_conditions = elems[0].text.strip()

            job_detail = {
                "job_id": job_id,
                **{k: v for k, v in list_data.items() if pd.notna(v)},
                "job_description": job_description,
                "job_categories": job_categories,
                "management_responsibility": management_responsibility,
                "work_shift": work_shift,
                "remote_work": remote_work,
                "BT_EXP": BT_EXP,
                "languages": languages,
                "tools": tools,
                "work_skills": work_skills,
                "other_conditions": other_conditions
            }
            return job_detail, driver

        except Exception as e:
            if attempt < max_retries - 1:
                err_str = str(e).lower()
                if "invalid session id" in err_str or "disconnected" in err_str or "browser has closed" in err_str:
                    print(f"細節頁偵測到瀏覽器異常，重啟 driver...")
                    try:
                        driver = restart_driver(driver, args)
                    except Exception as restart_e:
                        print(f"重啟 driver 失敗: {restart_e}")
                else:
                    time.sleep(random.uniform(15, 30))
                continue
            print(f"細節頁 {job_id} 失敗: {e}")
            return None, driver
    return None, driver

# -------------------------------------------------
# 7. 列表頁爬蟲（保持您原本成功的選擇器）
# -------------------------------------------------
def download_page(driver, url, existing_keys, crawl_date_str, args):
    max_retries = 3
    for attempt in range(max_retries):
        try:
            driver.get(url)
            time.sleep(random.uniform(3, 8))

            if "Cloudflare" in driver.title:
                print("Cloudflare 驗證，請手動完成後按 Enter")
                input()

            time.sleep(random.uniform(3, 10))

            soup = BeautifulSoup(driver.page_source, 'html.parser')
            WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.info-container"))
            )
            time.sleep(random.uniform(2, 6))

            jobs = driver.find_elements(By.CSS_SELECTOR, "div.info-container")
            dates = driver.find_elements(By.CSS_SELECTOR, "div.date-container")
            print(f"URL: {url}, 找到 {len(jobs)} 筆")

            if not jobs:
                return []

            list_rows = []
            seen_job_ids = set()
            for idx, job in enumerate(jobs):
                try:
                    # ---- 基本資訊 ----
                    title_a = job.find_elements(By.CSS_SELECTOR, "h2 a[data-gtm-joblist=\"職缺-職缺名稱\"]")
                    if not title_a:
                        continue
                    href = title_a[0].get_attribute("href")
                    job_id = re.search(r"/job/(\w+)", href).group(1) if href else "N/A"

                    if job_id in seen_job_ids:
                        continue
                    seen_job_ids.add(job_id)

                    row = {
                        "job_id": job_id,
                        "job_title": title_a[0].text.strip(),
                        "company": job.find_element(By.CSS_SELECTOR, "a[data-gtm-joblist=\"職缺-公司名稱\"]").text.strip(),
                        "industry": job.find_element(By.CSS_SELECTOR, "span[data-gtm-joblist*='職缺-產業'] a").text.strip(),
                        "location": job.find_element(By.CSS_SELECTOR, "div.info-tags a[data-gtm-joblist*=\"職缺-地區\"]").text.strip(),
                        "experience": job.find_element(By.CSS_SELECTOR, "div.info-tags a[data-gtm-joblist*=\"職缺-經歷\"]").text.strip(),
                        "education": job.find_element(By.CSS_SELECTOR, "div.info-tags a[data-gtm-joblist*=\"職缺-學歷\"]").text.strip(),
                        "salary": job.find_element(By.CSS_SELECTOR, "div.info-tags a[data-gtm-joblist*=\"職缺-薪資\"]").text.strip(),
                        "tags": ", ".join([t.text.strip() for t in job.find_elements(By.CSS_SELECTOR, "div.info-othertags a")]),
                        "update_date": dates[idx].text.strip() if idx < len(dates) else "N/A"
                    }
                    list_rows.append(row)
                except Exception as e:
                    print(f"列表解析 {idx} 失敗: {e}")
                    continue

            # ---- 爬細節 ----
            data = []
            for row in list_rows:
                job_id = row["job_id"]
                upd_clean = clean_update_date(row["update_date"], crawl_date_str)
                uniq = f"{job_id}|{upd_clean}"

                if uniq in existing_keys:
                    print(f"跳過重複: {uniq}")
                    continue

                detail, driver = crawl_job_details(driver, job_id, row, args)
                if detail:
                    detail["update_date_clean"] = upd_clean
                    detail["unique_key"] = uniq
                    data.append(detail)
                    existing_keys.add(uniq)
                    save_existing_key(uniq)

                time.sleep(random.uniform(2, 5))
                if len(data) % 30 == 0:
                    driver = restart_driver(driver, args)

            return data, driver

        except Exception as e:
            if attempt < max_retries - 1:
                print(f"頁面重試 {attempt+1}: {e}")
                
                # 針對 "invalid session id" 或 "disconnected" 進行特別處理
                err_str = str(e).lower()
                if "invalid session id" in err_str or "disconnected" in err_str or "browser has closed" in err_str:
                    print("偵測到瀏覽器連線中斷，嘗試重啟 driver...")
                    try:
                        driver = restart_driver(driver, args)
                    except Exception as restart_e:
                        print(f"重啟 driver 失敗: {restart_e}")

                time.sleep(random.uniform(15, 30))
                continue
            print(f"頁面最終失敗: {e}")
            return [], driver
    return [], driver

# -------------------------------------------------
# 8. 儲存（每日 + master，檔名含 raw_YYYYMMDD）
# -------------------------------------------------
def save_data(data, output_csv, query_params):
    if not data:
        print("無職缺資料可存")
        return

    df = pd.DataFrame(data)

    # 列表欄位轉字串（保持原樣）
    for col in ['job_categories', 'tools', 'work_skills']:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: ','.join(x) if isinstance(x, list) else x)

    # === 1. 解析 jobcat ===
    jobcat_match = re.search(r"jobcat=([^&]+)", query_params)
    if not jobcat_match:
        jobcat_str = "unknown"
    else:
        jobcat_str = jobcat_match.group(1)  # 例如: 2007001018,2007001022

    # 取出最後4碼，並用 _ 連接
    jobcat_codes = [code[-4:] for code in jobcat_str.split(',')]
    jobcat_short = "_".join(jobcat_codes)  # 1018_1022

    # === 2. 檔名 ===
    current_date = datetime.now().strftime("%Y%m%d")  # 20251115
    base_name = output_csv.replace(".csv", "")

    daily_filename = f"{base_name}_jobcat_{jobcat_short}_raw_{current_date}.csv"
    master_filename = f"{base_name}_master_raw.csv"

    # === 3. 儲存每日檔 ===
    df.to_csv(daily_filename, index=False, encoding="utf--8-sig")
    print(f"每日檔: {daily_filename} ({len(df)} 筆)")

    # === 4. 合併到 master 檔（用 unique_key 去重）===
    if os.path.exists(master_filename):
        master_df = pd.read_csv(master_filename)
        df = pd.concat([master_df, df], ignore_index=True)

    df.drop_duplicates(subset=['unique_key'], keep='last', inplace=True)
    df.to_csv(master_filename, index=False, encoding="utf--8-sig")
    print(f"master 更新: {master_filename} (總 {len(df)} 筆)")

# -------------------------------------------------
# 9. 主程式
# -------------------------------------------------
def main():
    global args
    args = parse_arguments()
    crawl_date_str = datetime.now().strftime("%Y-%m-%d")
    today_str = datetime.now().strftime("%Y%m%d")

    os.makedirs("logs", exist_ok=True)
    logging.basicConfig(
        filename=f"logs/crawler_{today_str}.log",
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )
    logging.info("=== START ===")

    start_page = max(args.start_page, load_checkpoint())
    existing_keys = load_existing_keys()
    print(f"從第 {start_page} 頁開始，現有 {len(existing_keys)} 筆")

    options = Options()
    # ... (保持不變)

    driver = uc.Chrome(options=options)
    all_data = []

    try:
        for page in range(start_page, args.end_page + 1):
            url = f"{args.base_url}?{args.query_params}&{args.pagination.format(page=page)}"
            page_data, driver = download_page(driver, url, existing_keys, crawl_date_str, args)

            if page_data:
                all_data.extend(page_data)
                print(f"第 {page} 頁抓到 {len(page_data)} 筆，累計 {len(all_data)} 筆")

            # === 每頁都存檔（關鍵！）===
            if all_data:
                save_data(all_data, args.output_csv, args.query_params)
                all_data = []  # 清空，釋放記憶體

            save_checkpoint(page)  # 每頁存斷點
            print(f"第 {page} 頁完成，已存檔")
            time.sleep(random.uniform(3, 10))

        # 最後一次保險
        if all_data:
            save_data(all_data, args.output_csv, args.query_params)

    except KeyboardInterrupt:
        print("\n手動中斷，儲存中...")
        if all_data:
            save_data(all_data, args.output_csv, args.query_params)
    except Exception as e:
        print(f"\n程式異常: {e}，儲存中...")
        if all_data:
            save_data(all_data, args.output_csv, args.query_params)
    finally:
        driver.quit()
        cleanup_chrome_processes()
        logging.info("=== END ===")

if __name__ == "__main__":
    main()
