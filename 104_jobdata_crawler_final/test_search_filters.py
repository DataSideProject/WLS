import requests
import json

BASE_URL = "http://localhost:5000"

def test_filter_options():
    print("Testing /api/filters/options...")
    try:
        res = requests.get(f"{BASE_URL}/api/filters/options")
        if res.status_code == 200:
            data = res.json()
            print("✅ Success")
            print(f"  - Locations: {len(data.get('locations', []))}")
            print(f"  - Salary Range: {data.get('salary_range')}")
            print(f"  - Remote Options: {data.get('remote_options')}")
            print(f"  - Manager Count: {data.get('manager_count')}")
        else:
            print(f"❌ Failed: {res.status_code}")
    except Exception as e:
        print(f"❌ Error: {e}")

def test_search_jobs():
    print("\nTesting /api/jobs with search...")
    # Test search for "Python"
    params = {'search': 'Python', 'per_page': 5}
    try:
        res = requests.get(f"{BASE_URL}/api/jobs", params=params)
        if res.status_code == 200:
            data = res.json()
            jobs = data.get('jobs', [])
            print(f"✅ Search 'Python': Found {data.get('total_count')} jobs")
            for job in jobs:
                print(f"  - {job['job_title']} ({job['company']})")
        else:
            print(f"❌ Failed: {res.status_code}")
    except Exception as e:
        print(f"❌ Error: {e}")

def test_location_filter():
    print("\nTesting /api/jobs with location filter...")
    # Test location "台北市"
    params = {'location': '台北市', 'per_page': 5}
    try:
        res = requests.get(f"{BASE_URL}/api/jobs", params=params)
        if res.status_code == 200:
            data = res.json()
            print(f"✅ Location '台北市': Found {data.get('total_count')} jobs")
        else:
            print(f"❌ Failed: {res.status_code}")
    except Exception as e:
        print(f"❌ Error: {e}")

def test_salary_filter():
    print("\nTesting /api/jobs with salary filter...")
    # Test salary min 50000
    params = {'salary_min': 50000, 'per_page': 5}
    try:
        res = requests.get(f"{BASE_URL}/api/jobs", params=params)
        if res.status_code == 200:
            data = res.json()
            print(f"✅ Salary >= 50000: Found {data.get('total_count')} jobs")
        else:
            print(f"❌ Failed: {res.status_code}")
    except Exception as e:
        print(f"❌ Error: {e}")

def test_manager_filter():
    print("\nTesting /api/jobs with manager filter...")
    params = {'is_manager': 1, 'per_page': 5}
    try:
        res = requests.get(f"{BASE_URL}/api/jobs", params=params)
        if res.status_code == 200:
            data = res.json()
            print(f"✅ Manager positions: Found {data.get('total_count')} jobs")
        else:
            print(f"❌ Failed: {res.status_code}")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_filter_options()
    test_search_jobs()
    test_location_filter()
    test_salary_filter()
    test_manager_filter()
