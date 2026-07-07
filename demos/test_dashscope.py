"""测试 DashScope VideoSynthesis API"""
import os, sys, json

# 设置 API Key
os.environ["DASHSCOPE_API_KEY"] = "sk-ws-H.RXPHDHX.ZpHY.MEYCIQDUAQOgiD5GbpmVuxmpxdl1TKUfTbfKhwYbcw5EwmsgMQIhANmmEPsyexIntS8dR4DIrmfYRcCppLq8ofYitEcLRluu"

import dashscope
dashscope.api_key = os.environ["DASHSCOPE_API_KEY"]

# 测试不同模型名
models_to_test = [
    "wanxiang-video",
    "wanx-video",
    "wanx",
    "wanx2.1-video",
    "wanx2-video",
    "video-synthesis",
    "wanx2.1",
]

for mname in models_to_test:
    try:
        resp = dashscope.VideoSynthesis.call(
            model=mname,
            prompt="测试视频生成",
            size="1280x720",
            duration=3,
        )
        msg = getattr(resp, "message", None) or ""
        code = getattr(resp, "status_code", -1)
        print(f"{mname}: status={code}, msg={str(msg)[:100]}")
    except Exception as e:
        err = str(e)[:150]
        print(f"{mname}: ERROR: {err}")
