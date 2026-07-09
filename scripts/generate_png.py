#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简易PNG生成器（不依赖外部库）
使用Python内置的zlib + struct生成PNG文件
"""

import struct
import zlib
import os

def create_png(width, height, pixels):
    """
    创建PNG文件
    pixels: 二维数组 [height][width], 每个元素是 (R, G, B, A) 元组
    """
    def chunk(chunk_type, data):
        c = chunk_type + data
        crc = struct.pack('>I', zlib.crc32(c) & 0xffffffff)
        return struct.pack('>I', len(data)) + c + crc
    
    # PNG签名
    signature = b'\x89PNG\r\n\x1a\n'
    
    # IHDR chunk
    ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)
    ihdr = chunk(b'IHDR', ihdr_data)
    
    # IDAT chunk (图像数据)
    raw_data = b''
    for y in range(height):
        raw_data += b'\x00'  # 过滤器类型：无
        for x in range(width):
            r, g, b, a = pixels[y][x]
            raw_data += struct.pack('BBBB', r, g, b, a)
    
    compressed = zlib.compress(raw_data)
    idat = chunk(b'IDAT', compressed)
    
    # IEND chunk
    iend = chunk(b'IEND', b'')
    
    return signature + ihdr + idat + iend

def create_figure_1():
    """图1: 三层架构图 (800x600)"""
    width, height = 800, 600
    pixels = [[(255, 255, 255, 255) for _ in range(width)] for _ in range(height)]
    
    # 绘制蓝色矩形 (身份层)
    for y in range(80, 180):
        for x in range(280, 520):
            pixels[y][x] = (52, 152, 219, 255)  # #3498db
    
    # 绘制绿色矩形 (记忆层)
    for y in range(250, 350):
        for x in range(280, 520):
            pixels[y][x] = (46, 204, 113, 255)  # #2ecc71
    
    # 绘制红色矩形 (人格层)
    for y in range(420, 520):
        for x in range(280, 520):
            pixels[y][x] = (231, 76, 60, 255)  # #e74c3c
    
    return pixels, width, height

def create_figure_2():
    """图2: DID绑定关系 (800x600)"""
    width, height = 800, 600
    pixels = [[(255, 255, 255, 255) for _ in range(width)] for _ in range(height)]
    
    # 主DID (蓝色)
    for y in range(100, 160):
        for x in range(300, 500):
            pixels[y][x] = (52, 152, 219, 255)
    
    # 实例1 (浅蓝)
    for y in range(250, 310):
        for x in range(150, 300):
            pixels[y][x] = (174, 214, 241, 255)
    
    # 实例2 (浅蓝)
    for y in range(250, 310):
        for x in range(450, 600):
            pixels[y][x] = (174, 214, 241, 255)
    
    return pixels, width, height

# 生成所有图
figures = [
    ('fig1_architecture.png', create_figure_1),
    ('fig2_did_binding.png', create_figure_2),
]

output_dir = r"C:\Users\Administrator\.qclaw\workspace-agent-d9479bde\silicon-civilization-kb\docs\images"
os.makedirs(output_dir, exist_ok=True)

for filename, func in figures:
    pixels, w, h = func()
    png_data = create_png(w, h, pixels)
    filepath = os.path.join(output_dir, filename)
    with open(filepath, 'wb') as f:
        f.write(png_data)
    print(f"[OK] 生成: {filename} ({w}x{h})")

print("\n✅ PNG图片生成完成")
print(f"输出目录: {output_dir}")
print("\n⚠️ 注意: 这是简易版本(纯色块)，建议用浏览器打开SVG后截图获得更好效果")
