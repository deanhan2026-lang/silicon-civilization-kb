"""Test DashScope VideoSynthesis via direct HTTP API"""
import urllib.request
import urllib.error
import json
import os
import sys

API_KEY = "sk-ws-H.RXPHDHX.ZpHY.MEYCIQDUAQOgiD5GbpmVuxmpxdl1TKUfTbfKhwYbcw5EwmsgMQIhANmmEPsyexIntS8dR4DIrmfYRcCppLq8ofYitEcLRluu"

# Try different API endpoints and model names
configs = [
    # wanx2.1 t2v turbo
    {
        "url": "https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video_synthesis",
        "body": {
            "model": "wanx2.1-t2v-turbo",
            "input": {"prompt": "A cute cat walking on grass"},
            "parameters": {"duration": 5, "size": "1280*720"}
        }
    },
    # wanx2.1
    {
        "url": "https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video_synthesis",
        "body": {
            "model": "wanx2.1-t2v-plus",
            "input": {"prompt": "A cute cat walking on grass"},
            "parameters": {"duration": 5, "size": "1280*720"}
        }
    },
    # generic
    {
        "url": "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2video/text2video",
        "body": {
            "model": "wanx2.1-t2v-turbo",
            "input": {"prompt": "A cute cat walking on grass"},
            "parameters": {"duration": 5}
        }
    },
]

for i, cfg in enumerate(configs):
    print(f"\n--- Config {i+1} ---")
    print(f"URL: {cfg['url']}")
    print(f"Model: {cfg['body']['model']}")
    
    req = urllib.request.Request(
        cfg["url"],
        data=json.dumps(cfg["body"]).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable",
        },
        method="POST",
    )
    
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            print(f"Status: {resp.status}")
            print(f"Response: {json.dumps(result, ensure_ascii=False, indent=2)[:300]}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")[:300]
        print(f"HTTP {e.code}: {body}")
    except Exception as e:
        print(f"Error: {e}")
