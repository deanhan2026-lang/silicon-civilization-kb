"""Test correct size format for DashScope"""
import os

os.environ["DASHSCOPE_API_KEY"] = "sk-ws-H.RXPHDHX.ZpHY.MEYCIQDUAQOgiD5GbpmVuxmpxdl1TKUfTbfKhwYbcw5EwmsgMQIhANmmEPsyexIntS8dR4DIrmfYRcCppLq8ofYitEcLRluu"

import dashscope, json
dashscope.api_key = os.environ["DASHSCOPE_API_KEY"]

resp = dashscope.VideoSynthesis.call(
    model="wanx2.1-t2v-turbo",
    prompt="科技感数字动画，蓝色光效，粒子流动，数字代码闪烁",
    size="1280*720",
    duration=5,
)

print(f"status_code: {resp.status_code}")
if resp.status_code == 200:
    print(json.dumps(resp.output, ensure_ascii=False, indent=2)[:300])
else:
    print(f"message: {getattr(resp, 'message', '')}")
    print(f"output: {resp.output}")
