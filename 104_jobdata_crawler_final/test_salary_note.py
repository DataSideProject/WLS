import requests
import json

BASE_URL = "http://localhost:5000"

def test_salary_note():
    print("Testing /api/jobs for salary_note...")
    try:
        # Fetch more jobs to ensure we find a negotiable one
        res = requests.get(f"{BASE_URL}/api/jobs?per_page=100")
        if res.status_code == 200:
            data = res.json()
            jobs = data.get('jobs', [])
            
            negotiable_count = 0
            actual_count = 0
            
            print(f"Scanning {len(jobs)} jobs...")
            for job in jobs:
                note = job.get('salary_note')
                if note == '無薪資資訊':
                    negotiable_count += 1
                    if negotiable_count <= 3: # Print first 3 negotiable
                        print(f"Negotiable Job Found: {job['job_title'][:20]}... | Min: {job.get('salary_min')}")
                else:
                    actual_count += 1
            
            print(f"\nFound {negotiable_count} negotiable and {actual_count} actual salary jobs.")
            if negotiable_count > 0:
                print("✅ salary_note is working correctly.")
            else:
                print("⚠️ No negotiable jobs found even in 100 samples.")
                
        else:
            print(f"❌ Failed: {res.status_code}")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_salary_note()
