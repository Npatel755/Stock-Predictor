import json
import os
import sys
import urllib.request
import urllib.error

API_KEY = "apk_user_dXNlci0xZGU5NTg0NTI1Zjk0NTg4YmI1MmRhN2FlZTA4ZGU1Y19vcmctYTdmMzYzMGZjOTRjNGIwOWEwZDlhN2QzNGNlMjU3YTE6NjcwYjUwYTE5OGQxNGQ2YjlkZTEwOTcwZGZlZjgxNzA="
ORG_ID = "org-a7f3630fc94c4b09a0d9a7d34ce257a1"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": "Antigravity-Devin-Bridge/1.0"
}

endpoints = [
    ("v1_sessions", "https://api.devin.ai/v1/sessions"),
    ("v3_org_sessions", f"https://api.devin.ai/v3/organizations/{ORG_ID}/sessions"),
    ("v3_sessions", "https://api.devin.ai/v3/sessions")
]

print("Testing Devin API Connectivity...")

success = False
for name, url in endpoints:
    print(f"\nProbing {name} -> {url}...")
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as res:
            status = res.status
            body = res.read().decode('utf-8')
            print(f"--> SUCCESS! HTTP {status}")
            data = json.loads(body)
            sessions = data if isinstance(data, list) else data.get("sessions", [])
            print(f"Total sessions returned: {len(sessions)}")
            for s in sessions[:5]:
                sid = s.get("session_id") or s.get("id") or s.get("devin_id")
                title = s.get("title") or s.get("prompt") or "Untitled"
                status_s = s.get("status") or s.get("state")
                created = s.get("created_at") or s.get("created")
                print(f"   * Session ID: {sid} | Status: {status_s} | Title: {str(title)[:60]} | Created: {created}")
            success = True
            break
    except urllib.error.HTTPError as e:
        print(f"--> HTTP {e.code}: {e.read().decode('utf-8', errors='replace')}")
    except Exception as e:
        print(f"--> Error: {e}")

if not success:
    print("\nCould not connect via tested endpoints. Review error messages above.")
