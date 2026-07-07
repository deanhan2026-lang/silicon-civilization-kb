"""Search all model pages for video/image generation models"""
import dashscope, os

dashscope.api_key = (
    os.environ.get("DASHSCOPE_API_KEY", "")
    or "sk-ws-H.RXPHDHX.ZpHY.MEYCIQDUAQOgiD5GbpmVuxmpxdl1TKUfTbfKhwYbcw5EwmsgMQIhANmmEPsyexIntS8dR4DIrmfYRcCppLq8ofYitEcLRluu"
)

# Search all pages
found = []
total = 0
for page in range(1, 46):  # 453 / 10 = 46 pages
    try:
        resp = dashscope.Models.list(page_no=page, page_size=10)
        models = resp.get("output", {}).get("models", [])
        if not models:
            break
        total = resp.get("output", {}).get("total", 0)
        for m in models:
            name = m["model"].lower()
            desc = m.get("description", "").lower()
            keywords = ["video", "image", "synthesis", "generation", "wanx", "wanxiang", "flux", "dall", "stable", "cogvideo", "pika", "ultra", "art"]
            if any(k in name or k in desc for k in keywords):
                found.append(m["model"])
    except Exception as e:
        print(f"Page {page}: {e}")
        break

print(f"Total models in catalog: {total}")
print(f"Pages searched: {page}")
if found:
    print(f"\nFound {len(found)} video/image related models:")
    for m in found:
        print(f"  {m}")
else:
    print("\nNo dedicated video/image generation models found in catalog.")
    print("This means the API key may not have video synthesis access,")
    print("or DashScope video models are not listed in the public catalog.")
    print("\nAlternative: Using OpenAI-compatible endpoint with another provider?")
