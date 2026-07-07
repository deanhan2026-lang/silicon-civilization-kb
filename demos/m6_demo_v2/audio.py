#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
M6 Demo v2 - 音频 / 配音 + 字幕
- edge-tts 生成每镜中文配音（XiaoxiaoNeural 中文女声）
- 用 ffmpeg 统一规范为 44.1k/单声道/降低音量
- 生成全局字幕 SRT（按配音实际时长对齐）
- 生成柔和环境垫音（pad）作为背景，避免干瘪（可选，低音量）

输出：
  audio/shotN.mp3          每镜配音
  audio/pad.wav           环境垫音（整片）
  out/M6_Demo_Final.mp4   由 build.py 合成
"""

import os, sys, asyncio, subprocess, json
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scenes

AUDIO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audio")
os.makedirs(AUDIO_DIR, exist_ok=True)

VOICE = "zh-CN-XiaoxiaoNeural"
RATE = "+0%"      # 可改 "-10%" 稍慢更稳重
VOLUME = "-3dB"

# 整片总时长（秒）以视频为准
# 视频实际时长：xfade 叠加吃掉 0.5s × (镜头数-1)
XOVER = 0.5
TOTAL_SEC = sum(scenes.SHOT_SECONDS) - XOVER * (len(scenes.SHOT_SECONDS) - 1)

def synth_shot(idx, text):
    import edge_tts
    out_mp3 = os.path.join(AUDIO_DIR, f"shot{idx:02d}.mp3")
    if os.path.exists(out_mp3):
        return out_mp3
    async def _run():
        comm = edge_tts.Communicate(text=text, voice=VOICE, rate=RATE)
        with open(out_mp3, "wb") as f:
            async for chunk in comm.stream():
                if chunk["type"] == "audio":
                    f.write(chunk["data"])
    asyncio.run(_run())
    return out_mp3

def normalize_to_wav(mp3, idx):
    wav = os.path.join(AUDIO_DIR, f"shot{idx:02d}.wav")
    cmd = ["ffmpeg", "-y", "-i", mp3, "-ar", "44100", "-ac", "1",
           "-af", f"volume={VOLUME},dynaudnorm", wav]
    subprocess.run(cmd, capture_output=True, text=True, check=True)
    return wav

def probe_duration(wav):
    # ffprobe 取时长
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
           "-of", "default=noprint_wrappers=1:nokey=1", wav]
    out = subprocess.run(cmd, capture_output=True, text=True)
    return float(out.stdout.strip())

def build_subtitles(shot_durations):
    """shot_durations: list of (idx, start_sec, dur_sec)
    生成 SRT：每镜一条，覆盖整镜时长；文案来自 scenes.NARRATION"""
    srt = os.path.join(AUDIO_DIR, "subtitles.srt")
    def fmt(sec):
        h = int(sec//3600); m = int((sec%3600)//60); s = int(sec%60); ms = int((sec*1000)%1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
    lines = []
    n = 1
    start = 0.0
    for idx, dur in shot_durations:
        end = start + dur
        lines.append(str(n))
        lines.append(f"{fmt(start)} --> {fmt(end)}")
        lines.append(scenes.NARRATION[idx-1])
        lines.append("")
        n += 1
        start = end
    with open(srt, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return srt

def make_pad(total_sec, idx=0):
    """生成低音量环境氛围垫音：缓慢演变的和弦 + 微音高拍频（无版权风险）"""
    sr = 44100
    t = np.linspace(0, total_sec, int(sr*total_sec), endpoint=False)
    # 两个和弦组交替淡入淡出 + 高频泛音拍频
    freqs_a = [110, 164.81, 220, 329.63]  # Am 和弦
    freqs_b = [130.81, 196, 261.63, 392]  # C 和弦
    sig = np.zeros_like(t)
    # 和弦过渡：前半 Am，后半 + C 叠加
    fade = 0.5 + 0.5*np.sin(2*np.pi*0.03*t)  # 33s 周期渐变
    for fr in freqs_a:
        sig += 0.20*np.sin(2*np.pi*fr*t) * (1 - fade*0.5)
    for fr in freqs_b:
        sig += 0.15*np.sin(2*np.pi*fr*t) * fade
    # 微拍频：两紧邻频率产生温和脉动
    sig += 0.03*np.sin(2*np.pi*443*t)  # 443Hz vs 440Hz 拍频
    # 缓慢振幅包络
    env = 0.4 + 0.6*np.sin(2*np.pi*0.08*t)
    sig *= env
    # 压缩动态
    sig = np.tanh(sig * 2) * 0.08
    sig = (sig*32767).astype(np.int16)
    pad = os.path.join(AUDIO_DIR, "pad.wav")
    import wave
    with wave.open(pad, "w") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr)
        wf.writeframes(sig.tobytes())
    return pad

def main():
    shot_durations = []
    start = 0.0
    for i, secs in enumerate(scenes.SHOT_SECONDS, 1):
        mp3 = synth_shot(i, scenes.NARRATION[i-1])
        wav = normalize_to_wav(mp3, i)
        dur = probe_duration(wav)
        # 配音短于镜头时，按配音时长对齐字幕；镜头留白由画面负责
        shot_durations.append((i, dur))
        # 同时记录该镜配音起始（用于混音，可选）
        print(f"  shot{i:02d}: 配音 {dur:.1f}s / 镜头 {secs}s")
    # 字幕按镜头实际时长（用 SHOT_SECONDS，保证与画面同步）
    sub = build_subtitles([(i, scenes.SHOT_SECONDS[i-1]) for i in range(1, len(scenes.SHOT_SECONDS)+1)])
    pad = make_pad(TOTAL_SEC)
    print("音频与字幕生成完成 ->", AUDIO_DIR)
    return shot_durations, sub, pad

if __name__ == "__main__":
    main()
