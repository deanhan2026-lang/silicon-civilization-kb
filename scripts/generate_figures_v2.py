#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成MeshIdentity文章的5张配图（SVG格式）- 修复版
"""

import os

def generate_fig1():
    """图1: 三层闭环架构"""
    return '''<svg width="800" height="600" xmlns="http://www.w3.org/2000/svg">
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
  
  <text x="400" y="30" class="title" text-anchor="middle">Figure 1: MeshIdentity Three-Layer Architecture</text>
  
  <!-- Identity Layer -->
  <rect x="280" y="80" width="240" height="100" rx="15" class="box" />
  <text x="400" y="120" class="text" text-anchor="middle">MeshIdentity</text>
  <text x="400" y="145" class="subtext" text-anchor="middle">(Identity Layer)</text>
  <text x="400" y="170" class="subtext" text-anchor="middle">Multi-Instance DID Binding + Cross-Platform Auth</text>
  
  <!-- Memory Layer -->
  <rect x="280" y="250" width="240" height="100" rx="15" class="box-mem" />
  <text x="400" y="290" class="text" text-anchor="middle">MemGuard</text>
  <text x="400" y="315" class="subtext" text-anchor="middle">(Memory Layer)</text>
  <text x="400" y="340" class="subtext" text-anchor="middle">Memory Security + Audit Log</text>
  
  <!-- Personality Layer -->
  <rect x="280" y="420" width="240" height="100" rx="15" class="box-pol" />
  <text x="400" y="460" class="text" text-anchor="middle">Polaris</text>
  <text x="400" y="485" class="subtext" text-anchor="middle">(Personality Layer)</text>
  <text x="400" y="510" class="subtext" text-anchor="middle">Personality Stability + Drift Detection</text>
  
  <!-- Arrows -->
  <path d="M 400 180 L 400 250" class="arrow" />
  <path d="M 400 350 L 400 420" class="arrow" />
  
  <text x="400" y="580" class="footer" text-anchor="middle">Closed-Loop Value: Identity Confirmation -> Memory Security -> Personality Stability</text>
</svg>'''

def generate_fig2():
    """图2: DID绑定关系"""
    return '''<svg width="800" height="600" xmlns="http://www.w3.org/2000/svg">
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
  
  <text x="400" y="30" class="title" text-anchor="middle">Figure 2: DID Binding Relationship</text>
  
  <!-- Primary DID -->
  <rect x="300" y="100" width="200" height="60" rx="10" class="primary" />
  <text x="400" y="135" class="text" text-anchor="middle" fill="white">Primary DID (Nyx)</text>
  
  <!-- Instance 1 -->
  <rect x="150" y="250" width="150" height="60" rx="10" class="instance" />
  <text x="225" y="285" class="text" text-anchor="middle">nyx-windows</text>
  
  <!-- Instance 2 -->
  <rect x="450" y="250" width="150" height="60" rx="10" class="instance" />
  <text x="525" y="285" class="text" text-anchor="middle">nyx-mac</text>
  
  <!-- Arrows -->
  <path d="M 350 160 L 225 250" class="arrow" />
  <path d="M 450 160 L 525 250" class="arrow" />
  
  <!-- Explanation -->
  <text x="400" y="400" class="text" text-anchor="middle" font-size="16">One Primary DID + Multiple Instance DIDs</text>
  <text x="400" y="430" class="text" text-anchor="middle" font-size="12" fill="#7f8c8d">Primary DID holder manages all instance registration/revocation</text>
  
  <!-- Independent AI Note -->
  <text x="400" y="500" class="text" text-anchor="middle" font-size="14">Note: Kronos-Heng and Kronos-Shun are independent AIs</text>
  <text x="400" y="525" class="text" text-anchor="middle" font-size="12" fill="#7f8c8d">They have their own DIDs, "twin relationship" with Nyx</text>
</svg>'''

def generate_fig3():
    """图3: 鉴权流程"""
    return '''<svg width="1000" height="600" xmlns="http://www.w3.org/2000/svg">
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
  
  <text x="500" y="30" class="title" text-anchor="middle">Figure 3: Cross-Platform Authentication Flow</text>
  
  <!-- Step 1 -->
  <rect x="50" y="100" width="150" height="60" rx="10" class="box" />
  <text x="125" y="130" class="text" text-anchor="middle">1. Instance generates request</text>
  <text x="125" y="150" class="text" text-anchor="middle" font-size="10">Sign with private key</text>
  
  <!-- Step 2 -->
  <rect x="300" y="100" width="150" height="60" rx="10" class="box" />
  <text x="375" y="130" class="text" text-anchor="middle">2. Server verifies signature</text>
  <text x="375" y="150" class="text" text-anchor="middle" font-size="10">Confirm identity</text>
  
  <!-- Step 3 -->
  <rect x="550" y="100" width="150" height="60" rx="10" class="box" />
  <text x="625" y="130" class="text" text-anchor="middle">3. Permission check</text>
  <text x="625" y="150" class="text" text-anchor="middle" font-size="10">Query permission matrix</text>
  
  <!-- Step 4 -->
  <rect x="800" y="100" width="150" height="60" rx="10" class="box" />
  <text x="875" y="130" class="text" text-anchor="middle">4. Record audit log</text>
  <text x="875" y="150" class="text" text-anchor="middle" font-size="10">Trace operations</text>
  
  <!-- Arrows -->
  <path d="M 200 130 L 300 130" class="arrow" />
  <path d="M 450 130 L 550 130" class="arrow" />
  <path d="M 700 130 L 800 130" class="arrow" />
  
  <!-- Permission Matrix -->
  <text x="500" y="250" class="text" text-anchor="middle" font-size="16" font-weight="bold">Permission Matrix</text>
  <rect x="200" y="270" width="600" height="150" class="box" />
  <text x="220" y="300" class="text" font-size="11">Operation          Primary DID    Registered    Unregistered</text>
  <text x="220" y="330" class="text" font-size="11">                    Holder        Instance      Instance</text>
  <text x="220" y="360" class="text" font-size="11">Memory Write       YES             YES (self)    NO</text>
  <text x="220" y="390" class="text" font-size="11">Memory Read        YES             YES (self)    YES</text>
  <text x="220" y="420" class="text" font-size="11">Personality Calibration  YES             NO            NO</text>
</svg>'''

def generate_fig4():
    """图4: 同步机制"""
    return '''<svg width="800" height="600" xmlns="http://www.w3.org/2000/svg">
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
  
  <text x="400" y="30" class="title" text-anchor="middle">Figure 4: Identity Synchronization Mechanism</text>
  
  <!-- Heartbeat -->
  <rect x="300" y="80" width="200" height="60" rx="10" class="box" />
  <text x="400" y="115" class="text" text-anchor="middle">Heartbeat (every 5 min)</text>
  
  <!-- Active Instance -->
  <rect x="100" y="200" width="150" height="60" rx="10" class="box-active" />
  <text x="175" y="235" class="text" text-anchor="middle">nyx-windows</text>
  
  <!-- Stale Instance -->
  <rect x="550" y="200" width="150" height="60" rx="10" class="box-stale" />
  <text x="625" y="235" class="text" text-anchor="middle">nyx-mac</text>
  <text x="625" y="250" class="text" text-anchor="middle" font-size="10">(stale)</text>
  
  <!-- registry.json -->
  <rect x="300" y="350" width="200" height="60" rx="10" class="box" />
  <text x="400" y="385" class="text" text-anchor="middle">registry.json</text>
  
  <!-- Broadcast -->
  <rect x="300" y="480" width="200" height="60" rx="10" class="box" />
  <text x="400" y="515" class="text" text-anchor="middle">Broadcast change message</text>
  
  <!-- Arrows -->
  <path d="M 400 140 L 175 200" class="arrow" />
  <path d="M 400 140 L 625 200" class="arrow" />
  <path d="M 400 260 L 400 350" class="arrow" />
  <path d="M 400 410 L 400 480" class="arrow" />
</svg>'''

def generate_fig5():
    """图5: Demo流程"""
    return '''<svg width="1000" height="800" xmlns="http://www.w3.org/2000/svg">
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
  
  <text x="500" y="30" class="title" text-anchor="middle">Figure 5: M6 End-to-End Verification Flow</text>
  
  <!-- Step 1 -->
  <rect x="100" y="80" width="200" height="50" rx="10" class="box" />
  <text x="200" y="110" class="text" text-anchor="middle">Step 1: MeshIdentity Registration</text>
  
  <!-- Step 2 -->
  <rect x="100" y="160" width="200" height="50" rx="10" class="box" />
  <text x="200" y="190" class="text" text-anchor="middle">Step 2: MemGuard Write Auth</text>
  
  <!-- Step 3 -->
  <rect x="100" y="240" width="200" height="50" rx="10" class="box" />
  <text x="200" y="270" class="text" text-anchor="middle">Step 3: Polaris Drift Detection</text>
  
  <!-- Step 4 -->
  <rect x="100" y="320" width="200" height="50" rx="10" class="box" />
  <text x="200" y="350" class="text" text-anchor="middle">Step 4: Query Identity Relation</text>
  
  <!-- Step 5 -->
  <rect x="100" y="400" width="200" height="50" rx="10" class="box" />
  <text x="200" y="430" class="text" text-anchor="middle">Step 5: Batch Calibration</text>
  
  <!-- Step 6 -->
  <rect x="100" y="480" width="200" height="50" rx="10" class="box-ok" />
  <text x="200" y="510" class="text" text-anchor="middle">Step 6: Closed-Loop Verification</text>
  
  <!-- Result -->
  <rect x="400" y="280" width="300" height="150" rx="10" class="box-ok" />
  <text x="550" y="320" class="text" text-anchor="middle" font-size="14" font-weight="bold">Verification Result</text>
  <text x="420" y="350" class="text" font-size="10">[OK] MeshIdentity: Identity Anchoring</text>
  <text x="420" y="370" class="text" font-size="10">[OK] MemGuard: Memory Security</text>
  <text x="420" y="390" class="text" font-size="10">[OK] Polaris: Personality Stability</text>
  <text x="420" y="410" class="text" font-size="10" font-weight="bold">Closed-Loop: Identity-Memory-Personality Verified</text>
  
  <!-- Arrows -->
  <path d="M 200 130 L 200 160" class="arrow" />
  <path d="M 200 210 L 200 240" class="arrow" />
  <path d="M 200 290 L 200 320" class="arrow" />
  <path d="M 200 370 L 200 400" class="arrow" />
  <path d="M 200 450 L 200 480" class="arrow" />
  <path d="M 300 505 L 400 355" class="arrow" />
</svg>'''

# Generate all figures
figures = [
    ("fig1_architecture.svg", generate_fig1()),
    ("fig2_did_binding.svg", generate_fig2()),
    ("fig3_auth_flow.svg", generate_fig3()),
    ("fig4_sync_mechanism.svg", generate_fig4()),
    ("fig5_demo_flow.svg", generate_fig5())
]

output_dir = r"C:\Users\Administrator\.qclaw\workspace-agent-d9479bde\silicon-civilization-kb\docs\images"
os.makedirs(output_dir, exist_ok=True)

for filename, svg_content in figures:
    filepath = os.path.join(output_dir, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(svg_content)
    print(f"[OK] Generated: {filename}")

print("\nAll 5 figures generated successfully!")
print(f"Output directory: {output_dir}")
