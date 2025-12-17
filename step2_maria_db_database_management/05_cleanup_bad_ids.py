from sqlalchemy import create_engine, text
import sys
import os

# 引入設定
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from db_config import DB_HOST, DB_USER, DB_PASSWORD

def cleanup_bad_records():
    DB_NAME = 'job_data_warehouse'
    conn_str = f'mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:3306/{DB_NAME}'
    engine = create_engine(conn_str)

    target_bad_id = '2_None' # 這是最可能的錯誤 ID
    
    print(f"正在連線到 {DB_NAME}...")
    with engine.connect() as conn:
        # 1. 查詢壞掉的資料
        print("檢查 '2_None' 或類似的異常資料...")
        # 尋找 Source=2 且 job_id 看起來不正常的
        sql_check = text("SELECT posting_id, job_id, job_title FROM fact_job_postings WHERE source_id=2 AND (job_id = '2_None' OR job_id = '2_UNKNOWN')")
        bad_rows = conn.execute(sql_check).fetchall()
        
        if not bad_rows:
            print("恭喜！找不到異常資料 (2_None, 2_UNKNOWN)。")
            return

        print(f"發現 {len(bad_rows)} 筆異常資料：")
        bad_ids = []
        for row in bad_rows:
            print(f" - ID: {row.posting_id}, JobID: {row.job_id}, Title: {row.job_title}")
            bad_ids.append(row.posting_id)
            
        # 2. 執行刪除
        confirm = input(f"是否確認刪除這 {len(bad_ids)} 筆資料? (y/n): ")
        if confirm.lower() == 'y':
            # 需要先刪除 Bridge Table 的關聯資料 (雖然通常有 CASCADE，但手動刪除比較保險)
            # 這裡簡化直接刪 Fact，假設有設 FK Action，或者就只刪 Fact 讓它留 Orphan (不完美但簡單)
            # 手動格式化 ID 列表，避開 MySQL Driver 對 List Binding 的不支援問題
            ids_str = "(" + ", ".join(str(x) for x in bad_ids) + ")"
            
            print(f"Executing delete for IDs: {ids_str}")

            conn.execute(text(f"DELETE FROM bridge_job_skills WHERE posting_id IN {ids_str}"))
            conn.execute(text(f"DELETE FROM bridge_job_categories WHERE posting_id IN {ids_str}"))
            conn.execute(text(f"DELETE FROM bridge_job_benefits WHERE posting_id IN {ids_str}"))
            
            # 最後刪 Fact
            conn.execute(text(f"DELETE FROM fact_job_postings WHERE posting_id IN {ids_str}"))
            conn.commit()
            print("刪除完成！")
        else:
            print("取消操作。")

if __name__ == "__main__":
    cleanup_bad_records()
