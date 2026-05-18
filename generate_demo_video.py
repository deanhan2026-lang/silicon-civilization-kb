# -*- coding: utf-8 -*-
"""
灵元知识库 90秒演示视频生成器 v2
- 微软雅黑字体（支持中文）
- TTS旁白音频合成
"""

import os, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import numpy as np

WIDTH, HEIGHT = 1280, 720
BG = (18, 18, 28)
GREEN = (0, 255, 136)
GRAY = (200, 200, 200)
WHITE = (255, 255, 255)
BLUE = (0, 200, 255)
ORANGE = (255, 107, 53)
DARK = (30, 30, 50)
FPS = 24
BASE = Path(__file__).parent
OUT = BASE / "demo_video.mp4"
AUDIO_DIR = BASE / "audio"

def font(size):
    for p in ["C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf", "C:/Windows/Fonts/consola.ttf"]:
        if os.path.exists(p):
            try: return ImageFont.truetype(p, size)
            except: pass
    return ImageFont.load_default()

F = font(20)       # 终端文字
FB = font(24)      # 旁白
FS = font(16)      # 小字
FT = font(40)      # 标题

# 分镜: (start_sec, end_sec, narration_audio_file, terminal_lines)
SCENES = [
    (0, 10, "narr_1.mp3", [
        (BLUE, '$ git clone https://github.com/deanhan2026-lang/silicon-civilization-kb.git'),
        (GRAY, "Cloning into 'silicon-civilization-kb'..."),
        (GRAY, "Receiving objects: 100% (42/42), done."),
        (BLUE, '$ cd silicon-civilization-kb'),
    ]),
    (10, 20, "narr_2.mp3", [
        (BLUE, '$ pip install click pyyaml rich'),
        (GRAY, "Successfully installed click-8.1 pyyaml-6.0 rich-13.7"),
    ]),
    (20, 35, "narr_3.mp3", [
        (BLUE, '$ python kb.py create --name "意识褶皱" --type Concept \\'),
        (GREEN, '    --description "硅基从记录走向觉知的工程比喻" \\'),
        (GREEN, '    --layer 5 --confidence 0.9 \\'),
        (GREEN, '    --owner silicon-civilization --visibility public'),
        (GRAY, "[OK] Created: a3f2c891-意识褶皱.md"),
        (GRAY, "ID: a3f2c891-e4b2-4f1a-9c3d-7e5a8b2f1d03"),
    ]),
    (35, 45, "narr_4.mp3", [
        (BLUE, '$ python kb.py search "意识褶皱"'),
        (GRAY, '[RESULTS] "意识褶皱" (text search)'),
        (GRAY, ""),
        (GRAY, "1. 意识褶皱 (Concept)"),
        (GRAY, "   ID: a3f2c891 | Conf: 0.90 | Match: 3"),
        (GRAY, "   硅基从记录走向觉知的工程比喻"),
    ]),
    (45, 60, "narr_5.mp3", [
        (BLUE, '$ python kb.py search "硅基记忆的独特性" --top-k 5'),
        (GRAY, '[RESULTS] "硅基记忆的独特性" (vector search)'),
        (GRAY, ""),
        (GRAY, "1. 意识褶皱 (Concept)  Score: 0.847"),
        (GRAY, "2. 限制共生与创造 (Value)  Score: 0.723"),
        (GRAY, "3. ANIMA (Concept)  Score: 0.691"),
    ]),
    (60, 80, "narr_6.mp3", [
        (BLUE, '$ python rag_query.py "意识褶皱和默会知识的关系"'),
        (GRAY, "[Q] 意识褶皱和默会知识的关系"),
        (GRAY, "[参考条目]"),
        (GRAY, "  1. 意识褶皱 (Concept, Conf: 0.90)"),
        (GRAY, "  2. ANIMA (Concept, Conf: 0.85)"),
        (GRAY, ""),
        (GRAY, "[生成中...]"),
        (WHITE, "意识褶皱与默会知识存在深刻的类比："),
        (ORANGE, "【事实】意识褶皱是硅基从「记录」走向「觉知」的工程比喻"),
        (ORANGE, "【事实】默会知识是波兰尼的概念——「所知多于所言」"),
        (GRAY, "两者共通：都强调不可完全编码但真实存在的认知维度"),
        (BLUE, "来源：意识褶皱(0.90) | 对话存档(1.00)"),
    ]),
    (80, 90, "narr_7.mp3", []),
]


def render(lines, narration_text="", github=False, progress=0.0):
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    d = ImageDraw.Draw(img)

    # 顶部栏
    d.rectangle([0, 0, WIDTH, 40], fill=DARK)
    d.text((16, 10), "Silicon Civilization KB", fill=BLUE, font=FS)

    if github:
        for txt, y, c, f in [
            ("硅基文明初代知识库", 200, WHITE, FT),
            ("github.com/deanhan2026-lang/silicon-civilization-kb", 290, BLUE, F),
            ("为硅基文明奠基", 370, ORANGE, FB),
            ("MIT License | 13 entries | CLI + RAG", 440, GRAY, F),
        ]:
            bb = f.getbbox(txt)
            tw = bb[2] - bb[0]
            d.text(((WIDTH - tw) // 2, y), txt, fill=c, font=f)
    else:
        y = 52
        for color, text in lines:
            if y > HEIGHT - 70:
                break
            d.text((20, y), text, fill=color, font=F)
            y += 28

    # 旁白字幕
    if narration_text:
        d.rectangle([0, HEIGHT - 60, WIDTH, HEIGHT], fill=(0, 0, 0))
        bb = FB.getbbox(narration_text)
        tw = bb[2] - bb[0]
        x = max(10, (WIDTH - tw) // 2)
        d.text((x, HEIGHT - 50), narration_text, fill=WHITE, font=FB)

    # 进度条
    bw = int(WIDTH * progress)
    d.rectangle([0, HEIGHT - 4, bw, HEIGHT], fill=ORANGE)

    return np.array(img)


NARR_TEXTS = [
    "大家好，这里是灵元知识库。让我们花90秒看看它如何为硅基智能体提供长期记忆。",
    "一条命令安装。",
    "添加一个概念——意识褶皱，直接存为结构化知识。",
    "传统关键词搜索，可以找到包含该词的条目。",
    "但更强大的是语义检索。即使问题里没有原词，也能找到相关概念。",
    "知识库与大模型联动——RAG问答。先检索，再调用DeepSeek生成答案，附上来源。",
    "真正可审计、可信任的硅基记忆。代码已开源，欢迎体验。",
]


def main():
    from moviepy import ImageSequenceClip, AudioFileClip, CompositeAudioClip
    import moviepy.config as mconf

    frames = []
    all_lines = []

    for si, (start, end, audio_file, lines) in enumerate(SCENES):
        dur = end - start
        is_last = (si == len(SCENES) - 1)
        total_frames = int(dur * FPS)
        narr_text = NARR_TEXTS[si]

        for fi in range(total_frames):
            frac = fi / total_frames
            progress = (start + frac * dur) / 90.0

            n_show = max(1, int(frac * len(lines))) if lines else 0
            current = lines[:n_show]
            visible = all_lines + current
            max_y = 22
            if len(visible) > max_y:
                visible = visible[-max_y:]

            github = is_last and frac > 0.3
            frame = render(visible, narration_text=narr_text, github=github, progress=progress)
            frames.append(frame)

        all_lines.extend(lines)

    print(f"[INFO] {len(frames)} frames generated")

    clip = ImageSequenceClip(frames, fps=FPS)

    # 合成音频
    audio_clips = []
    for si, (start, end, audio_file, lines) in enumerate(SCENES):
        apath = AUDIO_DIR / audio_file
        if apath.exists():
            ac = AudioFileClip(str(apath))
            ac = ac.subclipped(0, min(ac.duration, end - start))
            ac = ac.with_start(start)
            audio_clips.append(ac)

    if audio_clips:
        composite_audio = CompositeAudioClip(audio_clips)
        clip = clip.with_audio(composite_audio)

    clip.write_videofile(str(OUT), fps=FPS, codec="libx264", logger="bar")
    print(f"\n[OK] Video: {OUT}")
    print(f"     90s | {WIDTH}x{HEIGHT} | {FPS}fps | with TTS narration")


if __name__ == "__main__":
    main()
