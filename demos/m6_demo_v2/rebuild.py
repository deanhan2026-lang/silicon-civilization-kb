#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全量渲染+编码+音频+合成（修复版：音频尾不截断）"""
import os, sys, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scenes, render, audio
import numpy as np, wave

ROOT = os.path.dirname(os.path.abspath(__file__))
SCENES = os.path.join(ROOT, "scenes")
OUT_DIR = os.path.join(ROOT, "out")
os.makedirs(SCENES, exist_ok=True)
os.makedirs(OUT_DIR, exist_ok=True)
FINAL = os.path.join(OUT_DIR, "M6_Demo_Final.mp4")
N = len(scenes.SHOTS)
VIDEO_BASE = scenes.EFFECTIVE_TOTAL  # 72s (xfade后)
# 旁白最后一条需要多占：shot7位置=67s, VO长~6.8s, 结束于~73.8s
# 加3s定格尾帧 → 视频76s, 音频73.8s, -shortest完美裁剪
PAD_END = 4  # 4秒黑底定格
VIDEO_TOTAL = VIDEO_BASE + PAD_END  # 76s

def run(cmd, label):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"[ERROR] {label}\n{r.stderr[-400:]}")
        sys.exit(1)
    print(f"[OK] {label}")

# === 1) Check if frames exist (skip rerender) ===
shot_map = {}
for i in range(1, N+1):
    first = os.path.join(SCENES, f"shot{i:02d}_0000.png")
    last  = os.path.join(SCENES, f"shot{i:02d}_{int(round(scenes.SHOT_SECONDS[i-1]*render.FPS))-1:04d}.png")
    shot_map[i] = os.path.exists(first) and os.path.exists(last)

if not all(shot_map.values()):
    print("--- Rendering frames ---")
    for i in range(1, N+1):
        if shot_map[i]:
            print(f"  shot{i:02d} exists, skip")
            continue
        fn = scenes.SHOTS[i-1]
        secs = scenes.SHOT_SECONDS[i-1]
        nf = int(round(secs * render.FPS))
        for f in range(nf):
            t = f / max(1, nf-1) if nf > 1 else 0.0
            fn(t).save(os.path.join(SCENES, f"shot{i:02d}_{f:04d}.png"))
        print(f"  shot{i:02d} {nf} frames", flush=True)
else:
    print("--- All frames exist, skip render ---")

# === 2) Encode shots (skip if mp4 exists) ===
recode = False
for i in range(1, N+1):
    mp4 = os.path.join(SCENES, f"shot{i:02d}.mp4")
    if not os.path.exists(mp4) or os.path.getsize(mp4) < 50000:
        recode = True
        break

if recode:
    print("--- Encoding shots ---")
    for i in range(1, N+1):
        pat = os.path.join(SCENES, f"shot{i:02d}_%04d.png")
        out = os.path.join(SCENES, f"shot{i:02d}.mp4")
        run(["ffmpeg", "-y", "-framerate", str(render.FPS), "-i", pat,
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "medium", out],
            f"encode shot{i:02d}")
else:
    print("--- All shot mp4s exist, skip encode ---")

# === 3) Xfade concat + pad end ===
print("--- Xfade concat + pad ---")
d = 0.5
cmds = ["ffmpeg", "-y"]
for i in range(1, N+1):
    cmds += ["-i", os.path.join(SCENES, f"shot{i:02d}.mp4")]
offsets = [0.0]
for s in scenes.SHOT_SECONDS[:-1]:
    offsets.append(offsets[-1] + s - d)
prev = "0:v"; clauses = []
for i in range(1, N):
    outl = f"v{i}"
    clauses.append(f"[{prev}][{i}:v]xfade=transition=fade:duration={d}:offset={offsets[i]:.2f}[{outl}]")
    prev = outl
# 加黑帧垫尾
clauses.append(f"[{prev}]trim=duration={VIDEO_TOTAL},setpts=PTS-STARTPTS[padded]")
cmds += ["-filter_complex", ";".join(clauses), "-map", "[padded]",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
         os.path.join(SCENES, "concat.mp4")]
run(cmds, "xfade+pad concat")

# === 4) Audio: TTS (skip if wav exists) ===
regen_audio = False
for i in range(1, N+1):
    w = os.path.join(audio.AUDIO_DIR, f"shot{i:02d}.wav")
    if not os.path.exists(w):
        regen_audio = True
        break
if regen_audio:
    print("--- TTS ---")
    for i in range(1, N+1):
        mp3 = audio.synth_shot(i, scenes.NARRATION[i-1])
        audio.normalize_to_wav(mp3, i)
else:
    print("--- TTS wavs exist, skip ---")

# Pad (长音轨～74s)
print("--- Pad ---")
pad_path = audio.make_pad(VIDEO_TOTAL)

# === 5) Build voice track (75s buffer, 按shot位置排列) ===
print("--- Voice track ---")
shot_wavs = [os.path.join(audio.AUDIO_DIR, f"shot{i:02d}.wav") for i in range(1, N+1)]
SR = 44100
# buffer开到总占位和(75s)确保尾部不截
buf = np.zeros(int(sum(scenes.SHOT_SECONDS) * SR), dtype=np.float32)
pos = 0
for i, secs in enumerate(scenes.SHOT_SECONDS):
    with wave.open(shot_wavs[i], "rb") as wf:
        nf = wf.getnframes(); fr = wf.getframerate()
        raw = np.frombuffer(wf.readframes(nf), dtype=np.int16).astype(np.float32)/32768.0
    if fr != SR:
        xold = np.linspace(0, 1, len(raw))
        xnew = np.linspace(0, 1, int(len(raw)*SR/fr))
        raw = np.interp(xnew, xold, raw)
    seg_len = int(secs * SR)
    copy = min(len(raw), seg_len)
    buf[pos:pos+copy] = raw[:copy]
    pos += seg_len
# 只截到视频总长(含尾帧定格)
total_audio_frames = int(VIDEO_TOTAL * SR)
buf = buf[:total_audio_frames]
buf = np.clip(buf, -1, 1)
voice_track = os.path.join(OUT_DIR, "voice_track.wav")
with wave.open(voice_track, "w") as wf:
    wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(SR)
    wf.writeframes((buf*32767).astype(np.int16).tobytes())
print(f"  Voice track: {VIDEO_TOTAL:.0f}s")

# === 6) Mix voice + pad ===
print("--- Mix ---")
final_audio = os.path.join(OUT_DIR, "final_audio.wav")
run(["ffmpeg", "-y", "-i", voice_track, "-i", pad_path,
     "-filter_complex",
     "[1:a]volume=0.4[pad];[0:a][pad]amix=inputs=2:duration=first:dropout_transition=0[c];"
     "[c]dynaudnorm=p=0.9[out]",
     "-map", "[out]", "-ar", "44100", "-ac", "2", final_audio], "mix+norm")

# === 7) Final mux (no -shortest: 视频76s含定格, 音频~74s < 76s) ===
print("--- Final mux ---")
run(["ffmpeg", "-y", "-i", os.path.join(SCENES, "concat.mp4"),
     "-i", final_audio,
     "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", FINAL],
    "final mux")

# Cleanup
for f in [os.path.join(SCENES, "concat.mp4"), voice_track, final_audio]:
    try: os.remove(f)
    except: pass
for i in range(1, N+1):
    try: os.remove(os.path.join(SCENES, f"shot{i:02d}.mp4"))
    except: pass

sz = os.path.getsize(FINAL)
# 打印旁白时长信息
for i in range(1, N+1):
    w = os.path.join(audio.AUDIO_DIR, f"shot{i:02d}.wav")
    r = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",w],
                       capture_output=True, text=True)
    d = r.stdout.strip()
    print(f"  shot{i:02d} VO: {d}s / slot: {scenes.SHOT_SECONDS[i-1]}s")

print(f"\n=== DONE: {FINAL} ({sz/1024:.0f} KB / ~{VIDEO_TOTAL:.0f}s) ===")
