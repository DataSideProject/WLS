import re
from datetime import datetime
import hashlib

# ==================== Data Parsing Logic ====================

def get_md5_id(text):
    """
    將任意字串轉為 32 碼 MD5 ID (用於過長 Job ID)
    """
    if not text: return 'UNKNOWN'
    return hashlib.md5(str(text).encode('utf-8')).hexdigest()

def parse_salary(salary_str):
    """
    解析薪資字串，回傳 (min, max, type)
    支援格式： '月薪30,000~40,000元', '年薪100萬', '待遇面議', '日薪'
    """
    if not salary_str:
        return None, None, None
    
    s_clean = str(salary_str).replace(',', '').replace(' ', '')
    
    # 判斷類型
    s_type = '月薪'
    if '年薪' in s_clean: s_type = '年薪'
    elif '時薪' in s_clean: s_type = '時薪'
    elif '日薪' in s_clean: s_type = '日薪'
    elif '面議' in s_clean: s_type = '面議'
    
    # 提取數字
    # 尋找所有數字 (包含小數點或萬)
    # 簡易版：找 \d+ 
    nums = re.findall(r'\d+', s_clean)
    
    val_min = None
    val_max = None
    
    if len(nums) >= 2:
        val_min = int(nums[0])
        val_max = int(nums[1])
    elif len(nums) == 1:
        val_min = int(nums[0])
        val_max = val_min # 或 None
        
    # 處理 "萬" 單位 (通常年薪會有)
    if '萬' in s_clean:
        if val_min and val_min < 1000: val_min *= 10000
        if val_max and val_max < 1000: val_max *= 10000
        
    return val_min, val_max, s_type

def parse_location(loc_str):
    """
    解析地點，回傳 (Country, City, District)
    """
    if not loc_str: return 'Unknown', 'Unknown', 'Unknown'
    
    # 台灣縣市清單
    tw_cities = [
        '台北市', '新北市', '桃園市', '台中市', '台南市', '高雄市',
        '基隆市', '新竹市', '嘉義市',
        '新竹縣', '苗栗縣', '彰化縣', '南投縣', '雲林縣', '嘉義縣',
        '屏東縣', '宜蘭縣', '花蓮縣', '台東縣', '澎湖縣', '金門縣', '連江縣'
    ]
    
    # 1. 檢查是否為台灣縣市
    for city in tw_cities:
        if city in loc_str:
            # 嘗試切分區 (e.g. 台北市信義區)
            district = ''
            remaining = loc_str.replace(city, '')
            # 簡單抓取 "某某區" 或 "某某鄉鎮"
            # 這裡做個簡單 regex
            match = re.search(r'(.+?(區|鄉|鎮|市))', remaining)
            if match:
                district = match.group(1)
            
            return '台灣', city, district

    # 2. 如果不是台灣，檢查常見國家 (簡易版)
    # 為了簡化，若找不到台灣縣市，就當作海外或完整字串為 Country
    # 也可以加一個 map 來對應 (e.g. Shanghai -> 中國, Tokyo -> 日本)
    
    if '美國' in loc_str: return '美國', loc_str, ''
    if '日本' in loc_str: return '日本', loc_str, ''
    if '越南' in loc_str: return '越南', loc_str, ''
    if '菲律賓' in loc_str: return '菲律賓', loc_str, ''
    if '中國' in loc_str or '上海' in loc_str: return '中國', loc_str, ''
    
    # 3. 處理 "亞洲其他" 等模糊字眼
    if '洲' in loc_str: return loc_str, '', '' # 中美洲, 亞洲其他
    
    return loc_str, '', ''

def parse_location_cakeresume(loc_str):
    """
    解析 CakeResume 地點
    範例: '台北市, 台灣', 'Budapest, Hungary', 'India,Bengaluru...'
    邏輯:
    1. 切割逗號
    2. 優先尋找 '台灣' 相關的區塊
    3. 若無，則回傳第一個區塊當作地點
    """
    if not loc_str: return 'Unknown', 'Unknown', 'Unknown'
    
    parts = [p.strip() for p in str(loc_str).split(',')]
    
    # 策略 1: 優先找台灣縣市
    tw_cities = ['台北市', '新北市', '桃園市', '台中市', '台南市', '高雄市', '新竹市', '新竹縣']
    
    for part in parts:
        for city in tw_cities:
            if city in part:
                 # 假設格式 "內湖區, 台北市"
                 # part 可能只是 "台北市" 或 "台北市內湖區"
                 # 我們直接用 104 的 parse_location 處理這個片段
                 return parse_location(part)
                 
    # 策略 2: 國際地點
    # 取最後一個做為 Country (通常最後是國家)，取第一個做為 City
    if len(parts) >= 2:
        country = parts[-1]
        city = parts[0]
        return country, city, ''
        
    return parts[0], '', ''

def parse_salary_cakeresume(salary_str):
    """
    解析 CakeResume 薪資
    範例: '100,000 ~ 150,000 TWD / 月', '200,000 USD / 年', '38000+ TWD / 月'
    """
    if not salary_str: return None, None, '面議'
    
    s_clean = str(salary_str).replace(',', '').upper()
    
    # 1. 判斷幣別
    currency = 'TWD'
    if 'USD' in s_clean: currency = 'USD'
    elif 'JPY' in s_clean: currency = 'JPY'
    
    # 2. 判斷週期
    s_type = '月薪'
    if '/ 年' in s_clean or '/ YEAR' in s_clean: s_type = '年薪'
    elif '/ 小時' in s_clean or '/ HOUR' in s_clean: s_type = '時薪'
    elif '/ 日' in s_clean or '/ DAY' in s_clean: s_type = '日薪'
    
    # 如果是非台幣，標註上去
    if currency != 'TWD':
        s_type = f"{s_type}({currency})"
        
    # 3. 提取數字
    # 格式可能為 "100000 ~ 150000" 或 "38000+"
    nums = re.findall(r'\d+', s_clean)
    val_min = None
    val_max = None
    
    if len(nums) >= 2:
        val_min = int(nums[0])
        val_max = int(nums[1])
    elif len(nums) == 1:
        val_min = int(nums[0])
        val_max = val_min # 或 None 代表 "38000+"
        
    return val_min, val_max, s_type

def parse_experience_cakeresume(exp_str):
    """
    解析 CakeResume 經驗
    範例: '需具備 1 年以上工作經驗', '經驗不拘', ''
    """
    if not exp_str: return '經歷不拘'
    if '不拘' in str(exp_str): return '經歷不拘'
    
    # 嘗試提取數字
    match = re.search(r'(\d+)', str(exp_str))
    if match:
        year = match.group(1)
        return f"{year}年以上"
        
    return str(exp_str)

def parse_management_cakeresume(mgmt_str):
    """
    解析 CakeResume 管理責任
    範例: '管理 4 ~ 5 人', '不需負擔管理責任'
    """
    if not mgmt_str: return False
    
    s = str(mgmt_str)
    if '不需' in s or '不負擔' in s:
        return False
    if '管理' in s and re.search(r'\d+', s):
        return True
        
    return False
