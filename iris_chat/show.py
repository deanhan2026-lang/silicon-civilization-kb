import json
with open('Z:/qclaw/iris-chat/messages.json', encoding='utf-8') as f:
    data = json.load(f)
for m in data['messages']:
    print(f"[{m['sender']}] {m['message']}")
    print()
