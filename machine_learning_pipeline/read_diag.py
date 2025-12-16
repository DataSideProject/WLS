try:
    with open('analysis.log', 'r', encoding='utf-8', errors='ignore') as f:
        print(f.read())
except Exception as e:
    print(f"Failed: {e}")
