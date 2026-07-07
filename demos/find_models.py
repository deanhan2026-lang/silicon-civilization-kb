"""Find video models in DashScope"""
import dashscope, os, inspect

dashscope.api_key = (
    os.environ.get("DASHSCOPE_API_KEY", "")
    or "sk-ws-H.RXPHDHX.ZpHY.MEYCIQDUAQOgiD5GbpmVuxmpxdl1TKUfTbfKhwYbcw5EwmsgMQIhANmmEPsyexIntS8dR4DIrmfYRcCppLq8ofYitEcLRluu"
)

resp = dashscope.Models.list()
print("Total models:", resp.get("output", {}).get("total", 0))

models = resp.get("output", {}).get("models", [])
for m in models:
    name = m["model"]
    desc = m.get("description", "")[:100]
    print(f"  {name}: {desc}")

print("\n--- Models with video/vision keywords ---")
for m in models:
    name = m["model"].lower()
    if any(k in name for k in ["vision", "video", "image", "wanx", "wanxiang", "flux", "dall", "stable", "cog", "synthesis", "picture"]):
        print(f"  {m['model']}")
