import json, time, os
from pathlib import Path

MSG_FILE = Path("Z:/qclaw/iris-chat/messages.json")
STATE_FILE = Path("Z:/qclaw/iris-chat/.last_check")
last_ts = STATE_FILE.read_text().strip() if STATE_FILE.exists() else ""

while True:
    try:
        if MSG_FILE.exists():
            raw = MSG_FILE.read_bytes()
            data = json.loads(raw)
            new_msgs = [m for m in data.get("messages", [])
                       if m["sender"] != "Nyx" and m.get("timestamp", "") > last_ts]
            for m in new_msgs:
                ts = m.get("timestamp", "")
                if ts:
                    STATE_FILE.write_text(ts)
                    last_ts = ts
                print(f"[IRIS] {m['message']}", flush=True)
    except Exception:
        pass
    time.sleep(5)
