import json
data = json.loads(open('Z:/qclaw/iris-chat/messages.json', encoding='utf-8').read())
for m in data['messages']:
    print(f"[{m['sender']}] {m['message']}")
    print()
