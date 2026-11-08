import json
import urllib.request
import urllib.error

API_KEY = "apk_user_dXNlci0xZGU5NTg0NTI1Zjk0NTg4YmI1MmRhN2FlZTA4ZGU1Y19vcmctYTdmMzYzMGZjOTRjNGIwOWEwZDlhN2QzNGNlMjU3YTE6NjcwYjUwYTE5OGQxNGQ2YjlkZTEwOTcwZGZlZjgxNzA="
SESSION_ID = "devin-eaffd5ab978f45aa88e8d8d29fc0381d"

url = f"https://api.devin.ai/v1/sessions/{SESSION_ID}"
headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": "Antigravity-Devin-Bridge/1.0"
}

req = urllib.request.Request(url, headers=headers, method="GET")
try:
    with urllib.request.urlopen(req, timeout=15) as res:
        data = json.loads(res.read().decode('utf-8'))
        print("=== DEVIN ACTIVE SESSION DETAILS ===")
        print(f"Session ID : {data.get('session_id')}")
        print(f"Status     : {data.get('status')}")
        print(f"Title      : {data.get('title')}")
        print(f"Created At : {data.get('created_at')}")
        print(f"Updated At : {data.get('updated_at')}")
        
        # Check messages or events
        msgs = data.get('messages', [])
        print(f"Total Messages: {len(msgs)}")
        if msgs:
            print("\nLast 3 Messages in Session:")
            for m in msgs[-3:]:
                sender = m.get('role') or m.get('sender') or 'unknown'
                content = m.get('content') or m.get('text') or ''
                print(f"[{sender}]: {content[:200]}...\n")
        else:
            print("Session keys:", list(data.keys()))
except urllib.error.HTTPError as e:
    print(f"HTTP {e.code}: {e.read().decode('utf-8', errors='replace')}")
except Exception as e:
    print(f"Error: {e}")
