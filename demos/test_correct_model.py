"""Quick test DashScope VideoSynthesis with correct model name"""
import os

os.environ["DASHSCOPE_API_KEY"] = "sk-ws-H.RXPHDHX.ZpHY.MEYCIQDUAQOgiD5GbpmVuxmpxdl1TKUfTbfKhwYbcw5EwmsgMQIhANmmEPsyexIntS8dR4DIrmfYRcCppLq8ofYitEcLRluu"

import dashscope
dashscope.api_key = os.environ["DASHSCOPE_API_KEY"]

resp = dashscope.VideoSynthesis.call(
    model="wanx2.1-t2v-turbo",
    prompt="科技感数字动画，蓝色光效，流畅的粒子流动，数字代码在屏幕上闪烁",
    size="1280x720",
    duration=5,
)

print(f"status_code: {resp.status_code}")
print(f"response: {resp}")
if hasattr(resp, "output") and resp.output:
    import json
    print(json.dumps(resp.output, ensure_ascii=False, indent=2)[:500])
