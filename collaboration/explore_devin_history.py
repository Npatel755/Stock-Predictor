import json, urllib.request
from collections import Counter

API_KEY = 'apk_user_dXNlci0xZGU5NTg0NTI1Zjk0NTg4YmI1MmRhN2FlZTA4ZGU1Y19vcmctYTdmMzYzMGZjOTRjNGIwOWEwZDlhN2QzNGNlMjU3YTE6NjcwYjUwYTE5OGQxNGQ2YjlkZTEwOTcwZGZlZjgxNzA='
SESSION_ID = 'devin-eaffd5ab978f45aa88e8d8d29fc0381d'
url = f'https://api.devin.ai/v1/sessions/{SESSION_ID}'
headers = {'Authorization': f'Bearer {API_KEY}', 'Accept': 'application/json'}
req = urllib.request.Request(url, headers=headers)
with urllib.request.urlopen(req, timeout=15) as res:
    data = json.loads(res.read().decode('utf-8'))
msgs = data.get('messages', [])
types = Counter(m.get('type') for m in msgs)
print('Types:', types)
print('\nLast 10 messages:')
for m in msgs[-10:]:
    t = m.get('type')
    u = m.get('username') or ('devin' if t == 'bot_message' else 'user')
    ts = m.get('timestamp')
    msg = str(m.get('message', ''))
    print(f"[{ts}] {u} ({t}): {msg[:120]}...\n")
