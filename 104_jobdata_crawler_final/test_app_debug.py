import app
import json

print("Testing app data loading...")
app.load_data()

if app.df is None:
    print("ERROR: app.df is None. Data not loaded.")
else:
    print(f"SUCCESS: app.df loaded with {len(app.df)} rows.")
    print("Columns:", app.df.columns.tolist()[:10])

print("\nTesting /api/jobs endpoint...")
with app.app.test_client() as client:
    response = client.get('/api/jobs')
    if response.status_code == 200:
        data = json.loads(response.data)
        print(f"SUCCESS: /api/jobs returned {len(data)} items.")
        if len(data) > 0:
            print("Sample item:", data[0])
    else:
        print(f"ERROR: /api/jobs failed with status {response.status_code}")

print("\nTesting /api/analysis/stats endpoint...")
with app.app.test_client() as client:
    response = client.get('/api/analysis/stats')
    if response.status_code == 200:
        data = json.loads(response.data)
        print("SUCCESS: /api/analysis/stats returned data.")
        print("Keys:", data.keys())
    else:
        print(f"ERROR: /api/analysis/stats failed with status {response.status_code}")
