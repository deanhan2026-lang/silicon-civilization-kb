#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
M6 Demo v2 - Scenes / 分镜渲染
7 个镜头，每个 render_shotN(local_t) -> PIL.Image(RGB)
local_t: 0..1 该镜头内部进度。

依赖 engine.py / palette.py
"""

import math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from engine import (W, H, FPS, lerp, clamp01, ease_in_out_cubic, ease_out_cubic,
                    ease_out_expo, ease_in_out_quad, font, text_w,
                    background, glow, node, connection, pulse_ring,
                    typewriter_text, heartbeat, lock_check, radar, over, halo)
from palette import RGB, RGB01, PROD_RGB, PROD_RGB01

# ---------------- 通用文字图元 ----------------
def _title(draw, s, cx, cy, size, color_rgb, bold=True, anchor="mm"):
    f = font(size, bold)
    draw.text((cx, cy), s, font=f, fill=color_rgb+(255,), anchor=anchor)

def title_block(base, title, sub, t, title_cy=300, sub_cy=372,
                title_size=52, sub_size=24, title_delay=0.06):
    """标题逐字浮现 + 副标题淡入；返回新图"""
    img = base.convert("RGBA")
    # 顶部极淡暗化，保证标题在任何画面上都清晰（keynote 风）
    scrim = Image.new("RGBA", (W, H), (0,0,0,0))
    sd = ImageDraw.Draw(scrim)
    for y in range(210):
        a = int(120 * (1 - y/210))
        sd.line([(0,y),(W,y)], fill=(0,0,0,a))
    img = Image.alpha_composite(img, scrim)
    d = ImageDraw.Draw(img)
    ft = font(title_size, True)
    # 标题打字（前 45%）
    prog = clamp01((t - title_delay) / 0.42)
    shown = int(ease_out_cubic(prog) * len(title))
    typewriter_text(d, W//2, title_cy, title, shown, ft, RGB["ink"],
                    anchor="mm", caret=(prog < 0.98))
    # 副标题淡入（50%-70%）
    if t > 0.5:
        sp = clamp01((t - 0.5) / 0.2)
        fs = font(sub_size, False)
        bb = d.textbbox((0,0), sub, font=fs); lw = bb[2]-bb[0]
        alpha = int(255 * ease_out_cubic(sp))
        # 逐字淡入更克制：直接用 alpha
        tmp = Image.new("RGBA", (W, H), (0,0,0,0))
        td = ImageDraw.Draw(tmp)
        td.text((W//2 - lw/2, sub_cy), sub, font=fs,
                fill=RGB["ink_dim"]+(alpha,), anchor="la")
        img = Image.alpha_composite(img, tmp)
    return img.convert("RGB")

# ============================================================
# 镜头 1 ｜ 被忽略的风险 (7s)
# ============================================================
def render_shot1(t):
    base = background(t, grid=True)
    cx, cy = W//2, 322
    img = base.convert("RGBA")
    d = ImageDraw.Draw(img)
    # 呼吸节点
    pulse = 0.5 + 0.5*math.sin(t*math.pi*2)
    r = 26 + 6*pulse
    glitch = t > 0.55
    jit = 0
    if glitch:
        k = (t-0.55)/0.45
        jit = 6*math.sin(k*40)*k
        nx = cx + jit
    else:
        nx = cx
    col = RGB["warn"] if (glitch and (int(t*30)%2==0)) else RGB["brand"]
    img = over(img, halo(nx, cy, 200, col, intensity=0.4))
    img = over(img, node(nx, cy, r, col, fill_alpha=0.20, ring_w=3))
    # 朱红 glitch 粒子靠近
    if glitch:
        k = (t-0.55)/0.45
        for i in range(4):
            a0 = i*1.7
            dist = lerp(260, r+10, ease_out_cubic(k))
            px = cx + dist*math.cos(a0 + t*2)
            py = cy + dist*math.sin(a0 + t*2)*0.6
            img = over(img, node(px, py, 4, RGB["warn"], fill_alpha=0.9, ring=False))
    img = glow(img.convert("RGB"), RGB01["brand"], radius=9, gain=1.4)
    img = title_block(img, "它，还是原来的它吗？", "", t, title_cy=512, sub_cy=512)
    return img

# ============================================================
# 镜头 2 ｜ 提出主张 (8s)
# ============================================================
def render_shot2(t):
    base = background(t, grid=True)
    cx, cy = W//2, 300
    img = base.convert("RGBA")
    # 中心稳定节点
    img = over(img, node(cx, cy, 22, RGB["brand"], fill_alpha=0.18, ring_w=3))
    # 三道青色光环依次成形
    for i in range(3):
        start = 0.1 + i*0.12
        p = clamp01((t - start) / 0.22)
        if p <= 0: continue
        rr = lerp(40, 120 + i*36, ease_out_cubic(p))
        a = int(150 * (1 - p*0.6))
        lyr = Image.new("RGBA", (W, H), (0,0,0,0))
        ld = ImageDraw.Draw(lyr)
        ld.ellipse([cx-rr, cy-rr, cx+rr, cy+rr], outline=RGB["brand"]+(a,), width=2)
        img = Image.alpha_composite(img, lyr)
    img = glow(img.convert("RGB"), RGB01["brand"], radius=10, gain=1.5)
    img = title_block(img, "AI，也需要身份基础设施",
                      "像身份证，也像记忆保险箱", t, title_cy=470, sub_cy=520)
    return img

# ============================================================
# 镜头 3 ｜ MeshIdentity · 身份确权 (12s)
# ============================================================
DID_STR = "did:key:z7QE…OYAMMw"
def render_shot3(t):
    base = background(t, grid=False)
    cx, cy = W//2, 430
    img = base.convert("RGBA")
    d = ImageDraw.Draw(img)
    # 平台节点（三角下方）
    platforms = [("Coze", 360, 540), ("豆包", 640, 580), ("QClaw", 920, 540)]
    big = (cx, 382)  # 主 DID 大节点（下移到标题与平台之间，留白）
    # 阶段：0-0.35 钥匙morph到DID串；0.35-1 连线汇聚+流光
    if t < 0.35:
        k = ease_in_out_cubic(t/0.35)
        # 钥匙：圆头+杆（前半），后半渐隐；DID串渐显
        kr = lerp(34, 12, k)
        img = over(img, node(cx, cy, kr, RGB["brand"], fill_alpha=0.18, ring_w=3))
        # 钥匙齿
        lyr = Image.new("RGBA",(W,H),(0,0,0,0)); ld=ImageDraw.Draw(lyr)
        ld.line([cx, cy, cx+40, cy], fill=RGB["brand"]+(200,), width=4)
        ld.line([cx+30, cy, cx+30, cy+16], fill=RGB["brand"]+(200,), width=4)
        img = Image.alpha_composite(img, lyr)
        # DID串渐显（移到节点右上方，避开光晕与标题）
        ft = font(28, False)
        alpha = int(255*k)
        tmp = Image.new("RGBA",(W,H),(0,0,0,0)); td=ImageDraw.Draw(tmp)
        bb=td.textbbox((0,0),DID_STR,font=ft); lw=bb[2]-bb[0]
        td.text((big[0]+70, big[1]-44), DID_STR, font=ft, fill=RGB["ink"]+(alpha,), anchor="la")
        img = Image.alpha_composite(img, tmp)
    else:
        k2 = (t-0.35)/0.65
        # 主 DID 大节点 + 标签底板
        # 暗色圆角底板，保证标签在任何画面都清晰
        plate = Image.new("RGBA",(W,H),(0,0,0,0)); pd=ImageDraw.Draw(plate)
        pw, ph = 220, 96
        pd.rounded_rectangle([big[0]-pw/2, big[1]-ph/2, big[0]+pw/2, big[1]+ph/2],
                             radius=16, fill=(8,12,18,205), outline=RGB["brand2"]+(120,), width=2)
        img = Image.alpha_composite(img, plate)
        img = over(img, halo(big[0], big[1], 240, RGB["brand2"], intensity=0.35))
        img = over(img, node(big[0], big[1], 40, RGB["brand2"], fill_alpha=0.22, ring_w=4))
        ft = font(26, True)
        td = ImageDraw.Draw(img)
        td.text((big[0], big[1]-22), "主 DID", font=ft, fill=RGB["brand2"]+(255,), anchor="mm")
        td.text((big[0], big[1]+20), "z7QE…", font=font(16,False), fill=RGB["ink_dim"]+(255,), anchor="mm")
        # 平台节点
        for name, px, py in platforms:
            img = over(img, node(px, py, 24, RGB["brand"], fill_alpha=0.16, ring_w=3))
            ImageDraw.Draw(img).text((px, py-44), name, font=font(19,True),
                                     fill=RGB["ink"]+(255,), anchor="mm")
            # 连线生长 + 流光
            grow = clamp01((k2-0.05)/0.45)
            flow = (t*1.5) % 1.0
            img = over(img, connection(px, py, big[0], big[1], RGB["brand"],
                                       progress=grow, flow=flow, width=2, dots=2))
        # 收尾对勾
        if k2 > 0.8:
            img = over(img, lock_check(big[0], big[1], (k2-0.8)/0.2,
                                       RGB["brand"], RGB["good"]))
    img = glow(img.convert("RGB"), RGB01["brand"], radius=10, gain=1.5)
    img = title_block(img, "MeshIdentity · 身份确权",
                      "Ed25519 · 去中心化 DID", t, title_cy=96, sub_cy=168)
    return img

# ============================================================
# 镜头 4 ｜ MemGuard · 记忆安全 (12s)
# ============================================================
def render_shot4(t):
    base = background(t, grid=False)
    cx, cy = W//2, 280
    img = base.convert("RGBA")
    d = ImageDraw.Draw(img)
    # SOUL.md 文件图标
    fw, fh = 130, 160
    fx0, fy0 = cx-fw/2, cy-fh/2
    lyr = Image.new("RGBA",(W,H),(0,0,0,0)); ld=ImageDraw.Draw(lyr)
    ld.rounded_rectangle([fx0, fy0, fx0+fw, fy0+fh], radius=10,
                         outline=RGB["brand2"]+(220,), width=3, fill=RGB["brand2"]+(20,))
    # 折角
    ld.polygon([(fx0+fw-34, fy0), (fx0+fw, fy0), (fx0+fw, fy0+34)],
               fill=RGB["brand2"]+(120,))
    ft = font(26, True)
    ld.text((cx, cy-10), "SOUL", font=ft, fill=RGB["ink"]+(255,), anchor="mm")
    ld.text((cx, cy+22), ".md", font=font(15,False), fill=RGB["ink_dim"]+(255,), anchor="mm")
    img = Image.alpha_composite(img, lyr)
    # 签名笔触描边（0.2-0.7）
    if t > 0.2:
        p = clamp01((t-0.2)/0.5)
        per = int(p*4)
        lyr = Image.new("RGBA",(W,H),(0,0,0,0)); ld=ImageDraw.Draw(lyr)
        pts = [(fx0, fy0),(fx0+fw, fy0),(fx0+fw, fy0+fh),(fx0, fy0+fh)]
        pts.append(pts[0])
        drawn = 0; acc = p*4
        # 简单：画已完成的边 + 部分最后一边
        seg = acc
        for i in range(4):
            if seg >= 1:
                ld.line([pts[i], pts[i+1]], fill=RGB["brand"]+(230,), width=3)
                seg -= 1
            else:
                x0,y0 = pts[i]; x1,y1 = pts[i+1]
                ld.line([(x0,y0),(lerp(x0,x1,seg), lerp(y0,y1,seg))],
                        fill=RGB["brand"]+(230,), width=3)
                break
        img = Image.alpha_composite(img, lyr)
    # 审计日志底部滚动（极淡）
    if t > 0.3:
        ft2 = font(18, False)
        for i in range(4):
            yy = 600 + i*22
            off = (t*60 + i*40) % 200
            txt = f"audit  {['write','sign','verify','lock'][i]}  ✓ hash:9f{i*7:x}…"
            img = over(img, _dim_text(txt, 120-off, yy, ft2, a=int(90*clamp01((t-0.3)/0.2))))
    # 朱红篡改脉冲接近 → 被护盾弹开
    if 0.45 < t < 0.85:
        k = (t-0.45)/0.4
        px = lerp(1180, cx+fw/2+30, ease_in_out_cubic(k))
        py = lerp(140, cy, ease_in_out_cubic(k))
        if k < 0.7:
            img = over(img, node(px, py, 6, RGB["warn"], fill_alpha=0.9, ring=False))
        else:
            # 弹开
            bk = (k-0.7)/0.3
            bx = lerp(cx+fw/2+30, 1180, ease_out_cubic(bk))
            by = lerp(cy, 140, ease_out_cubic(bk))
            img = over(img, node(bx, by, 6, RGB["warn"], fill_alpha=0.9, ring=False))
    # 锁 + 对勾
    img = over(img, lock_check(cx, cy, clamp01((t-0.55)/0.45), RGB["brand"], RGB["good"]))
    img = glow(img.convert("RGB"), RGB01["brand2"], radius=10, gain=1.5)
    img = title_block(img, "MemGuard · 记忆安全",
                      "签名 · 加密 · 审计", t, title_cy=96, sub_cy=168)
    return img

def _dim_text(txt, x, y, f, a=90):
    lyr = Image.new("RGBA",(W,H),(0,0,0,0)); d=ImageDraw.Draw(lyr)
    d.text((x, y), txt, font=f, fill=RGB["ink_dim"]+(a,), anchor="la")
    return lyr

# ============================================================
# 镜头 5 ｜ Polaris · 人格稳定 (12s)
# ============================================================
def render_shot5(t):
    base = background(t, grid=False)
    cx, cy = W//2, 300
    img = base.convert("RGBA")
    # 绿色基线
    lyr = Image.new("RGBA",(W,H),(0,0,0,0)); d=ImageDraw.Draw(lyr)
    d.line([cx-360, cy, cx+360, cy], fill=RGB["good"]+(120,), width=2)
    img = Image.alpha_composite(img, lyr)
    # 漂移：0.3-0.7 出现红尖峰；校准：0.7 后拉回
    drift = 0.0
    if 0.3 <= t < 0.7:
        drift = clamp01((t-0.3)/0.2) * 0.7
    elif t >= 0.7:
        drift = 0.7 * (1 - clamp01((t-0.7)/0.3))
    img = over(img, heartbeat(cx, cy, 720, 70, t, RGB["brand"], drift=drift))
    # 雷达（右下）
    img = over(img, radar(1050, 300, t, RGB["brand2"], max_r=150))
    # 校准脉冲（0.7 后从底部升起）
    if t > 0.7:
        k = clamp01((t-0.7)/0.3)
        py = lerp(H, cy, ease_out_expo(k))
        img = over(img, node(cx, py, 10*(1-k)+4, RGB["brand2"], fill_alpha=0.5, ring=False))
    # 安抚同心圆
    if t > 0.8:
        for i in range(2):
            k = clamp01((t-0.8 - i*0.05)/0.2)
            img = over(img, pulse_ring(cx, cy, k, RGB["good"], max_r=200+i*40))
    img = glow(img.convert("RGB"), RGB01["brand"], radius=9, gain=1.4)
    img = title_block(img, "Polaris · 人格稳定",
                      "锚定基线 · 漂移预警", t, title_cy=96, sub_cy=168)
    return img

# ============================================================
# 镜头 6 ｜ 闭环自愈 (16s) ★
# ============================================================
def render_shot6(t):
    base = background(t, grid=True)
    cx, cy = W//2, 340
    img = base.convert("RGBA")
    center = (cx, cy)
    tri = [(cx, cy-150), (cx-150, cy+90), (cx+150, cy+90)]
    names = ["MeshIdentity", "MemGuard", "Polaris"]
    cols = [RGB["brand2"], RGB["brand"], PROD_RGB["polaris"]]
    # 阶段判定
    # 0-0.22 漂移；0.22-0.45 确权；0.45-0.68 守护；0.68-1 校准+闭合旋转
    beat = "drift"
    if t > 0.68: beat = "calibrate"
    elif t > 0.45: beat = "guard"
    elif t > 0.22: beat = "auth"
    # 中央 恒 节点
    hcol = RGB["warn"] if t < 0.22 else RGB["brand"]
    img = over(img, halo(center[0], center[1], 180, hcol, intensity=0.4))
    img = over(img, node(center[0], center[1], 46, hcol, fill_alpha=0.22, ring_w=4))
    ImageDraw.Draw(img).text((center[0], center[1]), "Kronos·恒",
                             font=font(19,True), fill=RGB["ink"]+(255,), anchor="mm")
    # 漂移波形贴着恒
    if t < 0.45:
        img = over(img, heartbeat(center[0], center[1]-2, 120, 26, t,
                                  RGB["warn"], drift=1.0 if t<0.22 else 0.3))
    # 三角产品节点
    for i,(px,py) in enumerate(tri):
        active = (beat=="auth" and i==0) or (beat=="guard" and i==1) or (beat=="calibrate" and i==2)
        a = 1.0 if active else 0.5
        img = over(img, halo(px, py, 130, cols[i], intensity=0.35*a))
        img = over(img, node(px, py, 30, cols[i], fill_alpha=0.18*a+0.05, ring_w=3))
        ImageDraw.Draw(img).text((px, py-46), names[i], font=font(16,True),
                                 fill=cols[i]+(int(255*a),), anchor="mm")
        # 连线到中心（按阶段生长/流光）
        if beat=="auth" and i==0:
            g = clamp01((t-0.22)/0.2); fl=(t*1.6)%1
            img = over(img, connection(px,py,center[0],center[1],cols[i],progress=g,flow=fl,width=3,dots=3))
            if g>0.6: img = over(img, pulse_ring(center[0],center[1],(t-0.4),RGB["brand2"],max_r=70))
        elif beat=="guard" and i==1:
            g = clamp01((t-0.45)/0.2); fl=(t*1.6)%1
            img = over(img, connection(px,py,center[0],center[1],cols[i],progress=g,flow=fl,width=3,dots=3))
        elif beat=="calibrate" and i==2:
            g = clamp01((t-0.68)/0.2); fl=(t*1.6)%1
            img = over(img, connection(px,py,center[0],center[1],cols[i],progress=g,flow=fl,width=3,dots=3))
    # 校准后：闭合三角环发光旋转
    if t > 0.85:
        k = clamp01((t-0.85)/0.15)
        rot = (t-0.85)*1.2
        ang = [rot, rot+2*math.pi/3, rot+4*math.pi/3]
        for i in range(3):
            a0, a1 = ang[i], ang[(i+1)%3]
            rr = 175
            p0 = (cx+rr*math.cos(a0), cy+rr*math.sin(a0))
            p1 = (cx+rr*math.cos(a1), cy+rr*math.sin(a1))
            lyr = Image.new("RGBA",(W,H),(0,0,0,0)); d=ImageDraw.Draw(lyr)
            d.line([p0,p1], fill=cols[i]+(int(200*k),), width=3)
            img = Image.alpha_composite(img, lyr)
    img = glow(img.convert("RGB"), RGB01["brand"], radius=11, gain=1.6)
    img = title_block(img, "闭环自愈", "确权 → 守护 → 校准",
                      t, title_cy=96, sub_cy=168)
    return img

# ============================================================
# 镜头 7 ｜ 三位一体 · 品牌落版 (8s)
# ============================================================
def render_shot7(t):
    base = background(t, grid=False)
    cx, cy = W//2, 440  # 大幅下移，确保顶圆辉光不碰标题
    img = base.convert("RGBA")
    rr = 150
    cols = [RGB["brand"], RGB["brand2"], PROD_RGB["polaris"]]
    names = ["MeshIdentity", "MemGuard", "Polaris"]
    # 固定位置：顶点在正上方不旋转
    pos = [(cx, cy-rr),
           (cx-int(rr*0.866), cy+rr//2),
           (cx+int(rr*0.866), cy+rr//2)]
    # 三角环
    lyr = Image.new("RGBA",(W,H),(0,0,0,0)); d=ImageDraw.Draw(lyr)
    for i in range(3):
        p0=pos[i]; p1=pos[(i+1)%3]
        d.line([p0,p1], fill=cols[i]+(180,), width=3)
    img = Image.alpha_composite(img, lyr)
    img = over(img, node(cx, cy, 40, RGB["brand"], fill_alpha=0.20, ring_w=3))
    ImageDraw.Draw(img).text((cx, cy), "Kronos·恒", font=font(18,True),
                             fill=RGB["ink"]+(255,), anchor="mm")
    for i,(px,py) in enumerate(pos):
        img = over(img, halo(px, py, 120, cols[i], intensity=0.4))
        img = over(img, node(px, py, 26, cols[i], fill_alpha=0.18, ring_w=3))
        ImageDraw.Draw(img).text((px, py-44), names[i], font=font(19,True),
                                 fill=cols[i]+(255,), anchor="mm")
    img = glow(img.convert("RGB"), RGB01["brand"], radius=11, gain=1.6)
    # 主标题 + slogan + 落款
    img = title_block(img, "三位一体 · AI 身份基础设施",
                      "MeshIdentity · MemGuard · Polaris", t,
                      title_cy=92, sub_cy=150, title_size=40, sub_size=20)
    # slogan 逐字（后半），落在标题下方、烧录字幕上方的安全区
    if t > 0.45:
        sp = clamp01((t-0.45)/0.4)
        shown = int(ease_out_cubic(sp)*len(SLOGAN))
        img = over(img, halo(W//2, 600, 200, RGB["brand"], intensity=0.18))
        d2 = ImageDraw.Draw(img)
        typewriter_text(d2, W//2, 600, SLOGAN, shown, font(16,True),
                        RGB["brand"], anchor="mm", caret=(sp<0.98))
    return img

SLOGAN = "让每一个 AI，都记得自己是谁。"

# ============================================================
# 调度
# ============================================================
SHOTS = [render_shot1, render_shot2, render_shot3, render_shot4,
         render_shot5, render_shot6, render_shot7]
SHOT_SECONDS = [7, 8, 12, 12, 12, 16, 8]
# 视频实际总时长：xfade 叠加吃掉 0.5s × 6
EFFECTIVE_TOTAL = sum(SHOT_SECONDS) - 0.5 * (len(SHOT_SECONDS) - 1)
NARRATION = [
    "你信任的 AI，真的不会被悄悄改写吗？",
    "我们给 AI 建造一套身份基础设施——像身份证，也像记忆保险箱。",
    "MeshIdentity 为每一个 AI 实例生成去中心化身份，跨平台绑定到同一个主 DID——身份，从此可确权、可追溯。",
    "MemGuard 为灵魂文件签名加密，任何篡改都逃不过审计日志。记忆，不可被污染。",
    "Polaris 把人格锚定在身份上，一旦漂移，立即预警并自动校准。人格，不再分裂。",
    "看 Kronos·恒：当它的输出开始漂移，MeshIdentity 先确权，MemGuard 守住记忆，Polaris 校准回基线——三环接力，闭环自愈。",
    "MeshIdentity、MemGuard、Polaris——三位一体，守护每一个 AI 的自我。",
]

if __name__ == "__main__":
    for i, fn in enumerate(SHOTS, 1):
        fn(0.5).save(f"brand/_shot{i}_mid.png")
    print("scenes self-check OK -> 7 frames")
