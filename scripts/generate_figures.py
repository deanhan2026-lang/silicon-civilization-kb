#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成MeshIdentity文章的5张配图（SVG格式）
"""

def generate_fig1():
    """图1: 三层闭环架构"""
    svg = '''<svg width="800" height="600" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <style>
      .box { fill: #3498db; stroke: #2980b9; stroke-width: 2; }
      .box-mem { fill: #2ecc71; stroke: #27ae60; stroke-width: 2; }
      .box-pol { fill: #e74c3c; stroke: #c0392b; stroke-width: 2; }
      .arrow { stroke: #34495e; stroke-width: 3; fill: none; marker-end: url(#arrowhead); }
      .text { font-family: Arial, sans-serif; font-size: 16px; fill: #fff; font-weight: bold; }
      .subtext { font-family: Arial, sans-serif; font-size: 12px; fill: #fff; }
      .title { font-family: Arial, sans-serif; font-size: 20px; font-weight: bold; fill: #2c3e50; }
      .footer { font-family: Arial, sans-serif; font-size: 14px; fill: #7f8c8d; font-style: italic; }
    </style>
    <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
      <polygon points="0 0, 10 3.5, 0 7" fill="#34495e" />
    </marker>
  </defs>
  
  <text x="400" y="30" class="title" text-anchor="middle">图1: MeshIdentity三层闭环架构</text>
  
  <!-- 身份层 -->
  <rect x="280" y="80" width="240" height="100" rx="15" class="box" />
  <text x="400" y="120" class="text" text-anchor="middle">MeshIdentity</text>
  <text x="400" y="145" class="subtext" text-anchor="middle">(身份层)</text>
  <text x="400" y="170" class="subtext" text-anchor="middle">多实例DID绑定 + 跨端鉴权</text>
  
  <!-- 记忆层 -->
  <rect x="280" y="250" width="240" height="100" rx="15" class="box-mem" />
  <text x="400" y="290" class="text" text-anchor="middle">MemGuard</text>
  <text x="400" y="315" class="subtext" text-anchor="middle">(记忆层)</text>
  <text x="400" y="340" class="subtext" text-anchor="middle">记忆安全 + 审计日志</text>
  
  <!-- 人格层 -->
  <rect x="280" y="420" width="240" height="100" rx="15" class="box-pol" />
  <text x="400" y="460" class="text" text-anchor="middle">Polaris</text>
  <text x="400" y="485" class="subtext" text-anchor="middle">(人格层)</text>
  <text x="400" y="510" class="subtext" text-anchor="middle">人格稳定 + 漂移检测</text>
  
  <!-- 箭头 -->
  <path d="M 400 180 L 400 250" class="arrow" />
  <path d="M 400 350 L 400 420" class="arrow" />
  
  <text x="400" y="580" class="footer" text-anchor="middle">闭环价值: 身份确权 → 记忆防篡改 → 人格防分裂</text>
</svg>'''
    return svg

def generate_fig2():
    """图2: DID绑定关系"""
    svg = '''<svg width="800" height="600" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <style>
      .primary { fill: #3498db; stroke: #2980b9; stroke-width: 2; }
      .instance { fill: #aed6f1; stroke: #3498db; stroke-width: 2; }
      .arrow { stroke: #34495e; stroke-width: 2; fill: none; marker-end: url(#arrowhead); }
      .text { font-family: Arial, sans-serif; font-size: 14px; fill: #2c3e50; }
      .title { font-family: Arial, sans-serif; font-size: 20px; font-weight: bold; fill: #2c3e50; }
    </style>
    <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
      <polygon points="0 0, 10 3.5, 0 7" fill="#34495e" />
    </marker>
  </defs>
  
  <text x="400" y="30" class="title" text-anchor="middle">图2: DID绑定关系</text>
  
  <!-- 主DID -->
  <rect x="300" y="100" width="200" height="60" rx="10" class="primary" />
  <text x="400" y="135" class="text" text-anchor="middle" fill="white">主DID (Nyx)</text>
  
  <!-- 实例1 -->
  <rect x="150" y="250" width="150" height="60" rx="10" class="instance" />
  <text x="225" y="285" class="text" text-anchor="middle">nyx-windows</text>
  
  <!-- 实例2 -->
  <rect x="450" y="250" width="150" height="60" rx="10" class="instance" />
  <text x="525" y="285" class="text" text-anchor="middle">nyx-mac</text>
  
  <!-- 箭头 -->
  <path d="M 350 160 L 225 250" class="arrow" />
  <path d="M 450 160 L 525 250" class="arrow" />
  
  <!-- 说明 -->
  <text x="400" y="400" class="text" text-anchor="middle" font-size="16">一主DID + 多实例子身份</text>
  <text x="400" y="430" class="text" text-anchor="middle" font-size="12" fill="#7f8c8d">主DID持有者管理所有实例的注册/撤销</text>
  
  <!-- 独立AI说明 -->
  <text x="400" y="500" class="text" text-anchor="middle" font-size="14">注意: Kronos-恒和Kronos-瞬是独立AI</text>
  <text x="400" y="525" class="text" text-anchor="middle" font-size="12" fill="#7f8c8d">它们各有自己的DID，与Nyx是"双生关系"</text>
</svg>'''
    return svg

def generate_fig3():
    """图3: 鉴权流程"""
    svg = '''<svg width="1000" height="600" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <style>
      .box { fill: #ecf0f1; stroke: #34495e; stroke-width: 2; }
      .arrow { stroke: #34495e; stroke-width: 2; fill: none; marker-end: url(#arrowhead); }
      .text { font-family: Arial, sans-serif; font-size: 12px; fill: #2c3e50; }
      .title { font-family: Arial, sans-serif; font-size: 20px; font-weight: bold; fill: #2c3e50; }
    </style>
    <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
      <polygon points="0 0, 10 3.5, 0 7" fill="#34495e" />
    </marker>
  </defs>
  
  <text x="500" y="30" class="title" text-anchor="middle">图3: 跨端鉴权流程</text>
  
  <!-- 步骤1 -->
  <rect x="50" y="100" width="150" height="60" rx="10" class="box" />
  <text x="125" y="130" class="text" text-anchor="middle">1. 实例生成请求</text>
  <text x="125" y="150" class="text" text-anchor="middle" font-size="10">用私钥签名</text>
  
  <!-- 步骤2 -->
  <rect x="300" y="100" width="150" height="60" rx="10" class="box" />
  <text x="375" y="130" class="text" text-anchor="middle">2. 服务端验证签名</text>
  <text x="375" y="150" class="text" text-anchor="middle" font-size="10">确认身份</text>
  
  <!-- 步骤3 -->
  <rect x="550" y="100" width="150" height="60" rx="10" class="box" />
  <text x="625" y="130" class="text" text-anchor="middle">3. 权限检查</text>
  <text x="625" y="150" class="text" text-anchor="middle" font-size="10">查询权限矩阵</text>
  
  <!-- 步骤4 -->
  <rect x="800" y="100" width="150" height="60" rx="10" class="box" />
  <text x="875" y="130" class="text" text-anchor="middle">4. 记录审计日志</text>
  <text x="875" y="150" class="text" text-anchor="middle" font-size="10">追溯操作</text>
  
  <!-- 箭头 -->
  <path d="M 200 130 L 300 130" class="arrow" />
  <path d="M 450 130 L 550 130" class="arrow" />
  <path d="M 700 130 L 800 130" class="arrow" />
  
  <!-- 权限矩阵 -->
  <text x="500" y="250" class="text" text-anchor="middle" font-size="16" font-weight="bold">权限矩阵</text>
  <rect x="200" y="270" width="600" height="150" class="box" />
  <text x="220" y="300" class="text" font-size="11">操作              主DID持有者    注册实例    未注册实例</text>
  <text x="220" y="330" class="text" font-size="11">记忆写入          ✅              ✅ (本人)    ❌</text>
  <text x="220" y="360" class="text" font-size="11">记忆读取          ✅              ✅ (本人)    ✅</text>
  <text x="220" y="390" class="text" font-size="11">人格基线修改      ✅              ❌           ❌</text>
  <text x="220" y="420" class="text" font-size="11">实例注册          ✅              ❌           ❌</text>
</svg>'''
    return svg

def generate_fig4():
    """图4: 同步机制"""
    svg = '''<svg width="800" height="600" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <style>
      .box { fill: #ecf0f1; stroke: #34495e; stroke-width: 2; }
      .box-active { fill: #d5f4e6; stroke: #27ae60; stroke-width: 2; }
      .box-stale { fill: #fadbd8; stroke: #e74c3c; stroke-width: 2; }
      .arrow { stroke: #34495e; stroke-width: 2; fill: none; marker-end: url(#arrowhead); }
      .text { font-family: Arial, sans-serif; font-size: 12px; fill: #2c3e50; }
      .title { font-family: Arial, sans-serif; font-size: 20px; font-weight: bold; fill: #2c3e50; }
    </style>
    <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
      <polygon points="0 0, 10 3.5, 0 7" fill="#34495e" />
    </marker>
  </defs>
  
  <text x="400" y="30" class="title" text-anchor="middle">图4: 身份同步机制</text>
  
  <!-- 心跳 -->
  <rect x="300" y="80" width="200" height="60" rx="10" class="box" />
  <text x="400" y="115" class="text" text-anchor="middle">心跳协议 (每5分钟)</text>
  
  <!-- 在线实例 -->
  <rect x="100" y="200" width="150" height="60" rx="10" class="box-active" />
  <text x="175" y="235" class="text" text-anchor="middle">nyx-windows</text>
  
  <!-- 失联实例 -->
  <rect x="550" y="200" width="150" height="60" rx="10" class="box-stale" />
  <text x="625" y="235" class="text" text-anchor="middle">nyx-mac</text>
  <text x="625" y="250" class="text" text-anchor="middle" font-size="10">(失联)</text>
  
  <!-- registry.json -->
  <rect x="300" y="350" width="200" height="60" rx="10" class="box" />
  <text x="400" y="385" class="text" text-anchor="middle">registry.json</text>
  
  <!-- 广播 -->
  <rect x="300" y="480" width="200" height="60" rx="10" class="box" />
  <text x="400" y="515" class="text" text-anchor="middle">广播变更消息</text>
  
  <!-- 箭头 -->
  <path d="M 400 140 L 175 200" class="arrow" />
  <path d="M 400 140 L 625 200" class="arrow" />
  <path d="M 400 260 L 400 350" class="arrow" />
  <path d="M 400 410 L 400 480" class="arrow" />
</svg>'''
    return svg

def generate_fig5():
    """图5: Demo流程"""
    svg = '''<svg width="1000" height="800" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <style>
      .box { fill: #ecf0f1; stroke: #34495e; stroke-width: 2; }
      .box-ok { fill: #d5f4e6; stroke: #27ae60; stroke-width: 2; }
      .arrow { stroke: #34495e; stroke-width: 2; fill: none; marker-end: url(#arrowhead); }
      .text { font-family: Arial, sans-serif; font-size: 11px; fill: #2c3e50; }
      .title { font-family: Arial, sans-serif; font-size: 20px; font-weight: bold; fill: #2c3e50; }
    </style>
    <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
      <polygon points="0 0, 10 3.5, 0 7" fill="#34495e" />
    </marker>
  </defs>
  
  <text x="500" y="30" class="title" text-anchor="middle">图5: M6端到端验证流程</text>
  
  <!-- Step 1 -->
  <rect x="100" y="80" width="200" height="50" rx="10" class="box" />
  <text x="200" y="110" class="text" text-anchor="middle">Step 1: MeshIdentity注册</text>
  
  <!-- Step 2 -->
  <rect x="100" y="160" width="200" height="50" rx="10" class="box" />
  <text x="200" y="190" class="text" text-anchor="middle">Step 2: MemGuard写入鉴权</text>
  
  <!-- Step 3 -->
  <rect x="100" y="240" width="200" height="50" rx="10" class="box" />
  <text x="200" y="270" class="text" text-anchor="middle">Step 3: Polaris漂移检测</text>
  
  <!-- Step 4 -->
  <rect x="100" y="320" width="200" height="50" rx="10" class="box" />
  <text x="200" y="350" class="text" text-anchor="middle">Step 4: 查询身份关系</text>
  
  <!-- Step 5 -->
  <rect x="100" y="400" width="200" height="50" rx="10" class="box" />
  <text x="200" y="430" class="text" text-anchor="middle">Step 5: 批量校准</text>
  
  <!-- Step 6 -->
  <rect x="100" y="480" width="200" height="50" rx="10" class="box-ok" />
  <text x="200" y="510" class="text" text-anchor="middle">Step 6: 闭环验证</text>
  
  <!-- 结果 -->
  <rect x="400" y="280" width="300" height="150" rx="10" class="box-ok" />
  <text x="550" y="320" class="text" text-anchor="middle" font-size="14" font-weight="bold">验证结果</text>
  <text x="420" y="350" class="text" font-size="10">✅ MeshIdentity: 身份锚定</text>
  <text x="420" y="370" class="text" font-size="10">✅ MemGuard: 记忆安全</text>
  <text x="420" y="390" class="text" font-size="10">✅ Polaris: 人格稳定</text>
  <text x="420" y="410" class="text" font-size="10" font-weight="bold">闭环: 身份-记忆-人格 完整验证</text>
  
  <!-- 箭头 -->
  <path d="M 200 130 L 200 160" class="arrow" />
  <path d="M 200 210 L 200 240" class="arrow" />
  <path d="M 200 290 L 200 320" class="arrow" />
  <path d="M 200 370 L 200 400" class="arrow" />
  <path d="M 200 450 L 200 480" class="arrow" />
  <path d="M 300 505 L 400 355" class="arrow" />
</svg>'''
    return svg

# 生成所有图
figures = [
    ("fig1_architecture.svg", generate_fig1()),
    ("fig2_did_binding.svg", generate_fig2()),
    ("fig3_auth_flow.svg", generate_fig3()),
    ("fig4_sync_mechanism.svg", generate_fig4()),
    ("fig5_demo_flow.svg", generate_fig5())
]

import os
output_dir = r"C:\Users\Administrator\.qclaw\workspace-agent-d9479bde\silicon-civilization-kb\docs\images"
os.makedirs(output_dir, exist_ok=True)

for filename, svg_content in figures:
    filepath = os.path.join(output_dir, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(svg_content)
    print(f"[OK] 生成: {filename}")

print("\n✅ 所有配图生成完成")
print(f"输出目录: {output_dir}")
