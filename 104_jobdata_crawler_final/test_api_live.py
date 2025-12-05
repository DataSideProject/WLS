import requests
import sys
import json

try:
    print("Testing /api/jobs...")
    r = requests.get('http://127.0.0.1:5000/api/jobs')
    if r.status_code == 200:
        # Try to find the problematic area manually if json fails
        try:
            data = r.json()
            print(f"Success! Retrieved {len(data)} jobs.")
        except Exception as e:
            print(f"JSON Decode Error: {e}")
            # The error said char 411881
            target_pos = 411881
            start = max(0, target_pos - 50)
            end = min(len(r.text), target_pos + 50)
            print(f"Context around {target_pos}:")
            print(f"...{r.text[start:end]}...")
    else:
        print(f"Failed. Status: {r.status_code}, Text: {r.text[:200]}")

except Exception as e:
    print(f"Error connecting to server: {e}")
