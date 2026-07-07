#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
M6 Demo v2 - Render Engine / 渲染引擎基类
提供 Apple keynote 风的复用图元：渐变底、辉光、节点、连线流光、脉冲、
同心圆扩散、心电波形、锁+对勾、文字逐字浮现等。

所有图元接收/返回 PIL.Image(RGB)，可层层合成。
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "brand"))

import math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from palette import RGB, RGB01, PROD_RGB, PROD_RGB01, FONT_BOLD, FONT_REG, FONT_HEI

W, H = 1280, 720
FPS = 30

# ---------------- 数学/缓动 ----------------
def lerp(a, b, t): return a + (b - a) * t
def clamp01(x): return max(0.0, min(1.0, x))
def ease_in_out_cubic(t):
    t = clamp01(t); return 3*t*t - 2*t*t*t   # smootherstep，更顺
def ease_out_cubic(t):
    t = clamp01(t); return 1 - (1-t)**3
def ease_in_out_quad(t):
    t = clamp01(t); return 2*t*t if t < 0.5 else 1 - (-2*t+2)**2/2
def ease_out_expo(t):
    t = clamp01(t); return 0 if t == 0 else 1 - 2**(-10*t)

# ---------------- 字体 ----------------
def font(size, bold=True):
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REG, size)

def text_w(draw, s, f):
    b = draw.textbbox((0,0), s, font=f); return b[2]-b[0]

# ---------------- 背景 ----------------
def background(t=0.0, drift=True, grid=True):
    """竖向渐变底 + 暗角 + 可选极淡漂移网格"""
    top = np.array(RGB01["bg_top"]); bot = np.array(RGB01["bg"])
    yy = np.linspace(0, 1, H)[:, None]
    img = np.zeros((H, W, 3), dtype=np.float32)
    grad = np.zeros((H, W, 3), dtype=np.float32)
    for c in range(3):
        grad[..., c] = (top[c]*(1-yy) + bot[c]*yy)
    # 暗角
    xs = (np.arange(W)-W/2)/(W/2); ys = (np.arange(H)-H/2)/(H/2)
    X, Y = np.meshgrid(xs, ys)
    vig = 1 - 0.35*(X*X + Y*Y)
    grad *= np.clip(vig, 0, 1)[..., None]
    if grid:
        # 极淡网格，随时间缓慢横向漂移
        off = (t*8.0) % 80
        gx = ((np.arange(W)+off) % 80 == 0).astype(np.float32)
        gy = (np.arange(H) % 80 == 0).astype(np.float32)
        grid_mask = np.minimum(gx[None, :], 1.0) + np.minimum(gy[:, None], 1.0)
        grid_mask = np.clip(grid_mask, 0, 1)
        gline = 0.05 * grid_mask[:, :, None]
        grad += gline * np.array(RGB01["brand"])
    grad = np.clip(grad, 0, 1)
    return Image.fromarray((grad*255).astype(np.uint8))

def vignette_mask():
    xs = (np.arange(W)-W/2)/(W/2); ys = (np.arange(H)-H/2)/(H/2)
    X, Y = np.meshgrid(xs, ys)
    return np.clip(1 - 0.35*(X*X+Y*Y), 0, 1)

# ---------------- 辉光 ----------------
def glow(img, color01, threshold=0.55, radius=6, gain=1.3):
    """对亮部做同色调 bloom，得到 keynote 光晕"""
    img = img.convert("RGB")
    a = np.asarray(img).astype(np.float32)/255.0
    lum = a.mean(axis=2)
    mask = (lum > threshold)[..., None]
    tint = a * np.array(color01)
    bloom = (tint * mask)
    bi = Image.fromarray((np.clip(bloom,0,1)*255).astype(np.uint8))
    bi = bi.filter(ImageFilter.GaussianBlur(radius))
    b = np.asarray(bi).astype(np.float32)/255.0 * gain
    out = np.clip(a + b, 0, 1)
    return Image.fromarray((out*255).astype(np.uint8))

def glow_composite(base, layer, color01, radius=10, gain=1.5, threshold=0.5):
    """把 layer 里亮的东西以 color01 辉光叠到 base 上"""
    return glow(Image.alpha_composite if base.mode=="RGBA" else _over(base, layer), color01, threshold, radius, gain)

def _over(base, layer):
    return Image.blend(base, layer, 1.0)

def halo(cx, cy, r, color_rgb, intensity=0.45):
    """环境光晕：节点背后的柔和径向辉光，营造 keynote 光感"""
    ys, xs = np.ogrid[:H, :W]
    d = np.sqrt((xs-cx)**2 + (ys-cy)**2)
    mask = np.clip(1 - d/r, 0, 1)**2
    a = (mask * intensity * 255).astype(np.uint8)
    img = np.zeros((H, W, 4), np.uint8)
    img[..., 0] = color_rgb[0]
    img[..., 1] = color_rgb[1]
    img[..., 2] = color_rgb[2]
    img[..., 3] = a
    return Image.fromarray(img, "RGBA")

def soft_text(draw, cx, cy, s, f, color_rgb, anchor="mm", alpha=255):
    """安全文字（带 alpha）"""
    bb = draw.textbbox((0,0), s, font=f)
    lw = bb[2]-bb[0]
    x = cx - lw/2 if anchor in ("mm","m") else cx
    draw.text((x, cy), s, font=f, fill=color_rgb+(alpha,), anchor="la")

# ---------------- 基础图元 ----------------
def node(cx, cy, r, color_rgb, ring=True, fill_alpha=0.18, ring_w=3):
    """画一个发光节点（半透明填充+亮环）"""
    layer = Image.new("RGBA", (W, H), (0,0,0,0))
    d = ImageDraw.Draw(layer)
    col = color_rgb + (int(fill_alpha*255),)
    d.ellipse([cx-r, cy-r, cx+r, cy+r], fill=col)
    if ring:
        d.ellipse([cx-r, cy-r, cx+r, cy+r], outline=color_rgb+(255,), width=ring_w)
    return layer

def connection(cx1, cy1, cx2, cy2, color_rgb, progress=1.0, flow=0.0, width=3, dots=3):
    """两节点连线 + 流光点（flow 在 0..1 表示流光相位）"""
    layer = Image.new("RGBA", (W, H), (0,0,0,0))
    d = ImageDraw.Draw(layer)
    # 基础线（按 progress 生长）
    if progress <= 0:
        return layer
    ex = lerp(cx1, cx2, progress); ey = lerp(cy1, cy2, progress)
    d.line([cx1, cy1, ex, ey], fill=color_rgb+(180,), width=width, joint="curve")
    # 流光点
    for i in range(dots):
        ph = (flow + i/dots) % 1.0
        px = lerp(cx1, cx2, ph); py = lerp(cy1, cy2, ph)
        rr = 5
        d.ellipse([px-rr, py-rr, px+rr, py+rr], fill=color_rgb+(255,))
        d.ellipse([px-rr*2.2, py-rr*2.2, px+rr*2.2, py+rr*2.2], outline=color_rgb+(90,), width=2)
    return layer

def pulse_ring(cx, cy, t, color_rgb, max_r=220, life=1.0):
    """同心圆扩散（t: 0..1 生命周期）"""
    layer = Image.new("RGBA", (W, H), (0,0,0,0))
    d = ImageDraw.Draw(layer)
    r = max_r * ease_out_cubic(t)
    a = int(200 * (1 - t))
    d.ellipse([cx-r, cy-r, cx+r, cy+r], outline=color_rgb+(a,), width=3)
    return layer

def typewriter_text(draw, cx, cy, full, shown, f, color_rgb,
                    anchor="mm", caret=True, line_gap=None):
    """文字逐字浮现 + 闪烁光标；返回当前已显示字符串"""
    s = full[:shown]
    # 处理多行
    lines = s.split("\n")
    if line_gap is None:
        line_gap = f.size * 1.25
    total_h = line_gap * (len(lines)-1)
    y0 = cy - total_h/2
    for i, ln in enumerate(lines):
        bb = draw.textbbox((0,0), ln, font=f)
        lw = bb[2]-bb[0]
        x = cx - lw/2 if anchor in ("mm","m") else cx
        y = y0 + i*line_gap
        draw.text((x, y), ln, font=f, fill=color_rgb+(255,), anchor="la")
    # caret
    if caret and shown < len(full):
        last = lines[-1]
        bb = draw.textbbox((0,0), last, font=f)
        lw = bb[2]-bb[0]
        x = cx + lw/2 if anchor in ("mm","m") else cx + (text_w(draw,last,f) if last else 0)
        y = y0 + (len(lines)-1)*line_gap
        draw.text((x+4, y), "▌", font=f, fill=color_rgb+(255,), anchor="la")
    return s

def heartbeat(cx, cy, w, amp, t, color_rgb, drift=0.0):
    """心电波形（ECG），drift 0..1 控制是否异常（红+乱）"""
    layer = Image.new("RGBA", (W, H), (0,0,0,0))
    d = ImageDraw.Draw(layer)
    pts = []
    n = 220
    for i in range(n+1):
        x = cx - w/2 + w*i/n
        phase = (i/n*4.0 - t*1.2) % 1.0
        # 基线
        y = cy
        # ECG 尖峰
        p = phase % 0.25
        spike = 0.0
        if p < 0.04:
            spike = -0.15*math.sin(p/0.04*math.pi)
        elif p < 0.08:
            spike = 1.0*math.sin((p-0.04)/0.04*math.pi)
        elif p < 0.12:
            spike = -0.4*math.sin((p-0.08)/0.04*math.pi)
        else:
            spike = 0.0
        # 漂移时加入抖动与幅度放大
        if drift > 0:
            spike *= (1 + 0.6*drift*math.sin(i*1.7))
            y += drift*8*math.sin(i*0.6)
        y -= spike*amp
        pts.append((x, y))
    col = RGB["warn"] if drift > 0.45 else color_rgb
    d.line(pts, fill=col+(235,), width=4, joint="curve")
    # 扫描头亮点
    hx, hy = pts[-1]
    d.ellipse([hx-6, hy-6, hx+6, hy+6], fill=col+(255,))
    return layer

def lock_check(cx, cy, t, color_rgb, ok_color):
    """锁形 + 对勾绘制动画；t>0.6 后变绿对勾"""
    layer = Image.new("RGBA", (W, H), (0,0,0,0))
    d = ImageDraw.Draw(layer)
    bw, bh = 90, 70
    bx0, by0 = cx-bw/2, cy-bh/2+10
    # 锁体
    d.rounded_rectangle([bx0, by0, bx0+bw, by0+bh], radius=12,
                        outline=color_rgb+(255,), width=5,
                        fill=color_rgb+(40,))
    # 锁梁（弧）
    sh = 46; sw = 70
    sx0 = cx-sw/2; sy0 = by0-sh
    d.arc([sx0, sy0, sx0+sw, by0+10], start=180, end=360,
          fill=color_rgb+(255,), width=6)
    # 对勾（t>0.6 出现并转绿）
    if t > 0.6:
        k = ease_out_cubic((t-0.6)/0.4)
        col = ok_color
        kx0, ky0 = cx-22, cy-2
        p1 = (kx0, ky0)
        p2 = (cx-4, cy+16)
        p3 = (cx+26, cy-18)
        # 按 k 画折线
        if k < 0.5:
            seg = k/0.5
            x = lerp(p1[0], p2[0], seg); y = lerp(p1[1], p2[1], seg)
            d.line([p1, (x,y)], fill=col+(255,), width=8, joint="curve")
        else:
            seg = (k-0.5)/0.5
            x = lerp(p2[0], p3[0], seg); y = lerp(p2[1], p3[1], seg)
            d.line([p1, p2], fill=col+(255,), width=8, joint="curve")
            d.line([p2, (x,y)], fill=col+(255,), width=8, joint="curve")
    return layer

def radar(cx, cy, t, color_rgb, max_r=240):
    """雷达扫描：旋转扇形 + 同心圆"""
    layer = Image.new("RGBA", (W, H), (0,0,0,0))
    d = ImageDraw.Draw(layer)
    for rr in range(60, max_r, 60):
        d.ellipse([cx-rr, cy-rr, cx+rr, cy+rr], outline=color_rgb+(70,), width=2)
    ang = (t*1.5) % (2*math.pi)
    # 扫描扇形（用多边形近似）
    segs = 24
    sweep = 0.5
    pts = [(cx, cy)]
    for i in range(segs+1):
        a = ang - sweep + sweep*2*i/segs
        pts.append((cx + max_r*math.cos(a), cy + max_r*math.sin(a)))
    d.polygon(pts, fill=color_rgb+(40,))
    # 前沿亮线
    fx = cx + max_r*math.cos(ang); fy = cy + max_r*math.sin(ang)
    d.line([cx, cy, fx, fy], fill=color_rgb+(220,), width=3)
    return layer

def soft_circle_label(cx, cy, r, txt, f, color_rgb, t=1.0):
    """节点中心放文字（已存在节点上盖字）"""
    layer = Image.new("RGBA", (W, H), (0,0,0,0))
    d = ImageDraw.Draw(layer)
    bb = d.textbbox((0,0), txt, font=f); lw = bb[2]-bb[0]
    d.text((cx-lw/2, cy-f.size/2), txt, font=f, fill=color_rgb+(255,), anchor="la")
    return layer

# ---------------- 合成辅助 ----------------
def over(base, *layers):
    """把若干 RGBA 层叠加到 RGB/RGBA 底上，返回 RGBA 保持链路一致"""
    out = base.convert("RGBA")
    for L in layers:
        if L is not None:
            out = Image.alpha_composite(out, L)
    return out

def compose_glow(base_rgb, *layers_rgb_rgba_with_color):
    """layers: (rgba_layer, color01, radius, gain) → 合成并整体辉光"""
    out = base_rgb.convert("RGBA")
    for item in layers_rgb_rgba_with_color:
        L = item[0]
        out = Image.alpha_composite(out, L)
    out = out.convert("RGB")
    if len(layers_rgb_rgba_with_color) > 0:
        _, c, r, g = layers_rgb_rgba_with_color[0]
        out = glow(out, c, radius=r, gain=g)
    return out

if __name__ == "__main__":
    # 自检
    img = background(t=0.3)
    img.save("brand/_engine_selfcheck.png")
    print("engine self-check OK -> brand/_engine_selfcheck.png", img.size)
