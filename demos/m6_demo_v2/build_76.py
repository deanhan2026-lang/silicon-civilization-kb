#!/usr/bin/env python3
"""Build voice track for 76s video, mix with pad, mux"""
import wave, numpy as np, os, subprocess

SR = 44100
ROOT = os.path.dirname(os.path.abspath(__file__))
AUDIO = os.path.join(ROOT, "audio")
OUT = os.path.join(ROOT, "out")
SCENES = os.path.join(ROOT, "scenes")
VIDEO_TOTAL = 76

shot_wavs = [os.path.join(AUDIO, f"shot{i:02d}.wav") for i in range(1,8)]
secs = [7,8,12,12,12,16,8]

# Build voice buffer (80s 确保尾帧定格段不截)
buf = np.zeros(int(80*SR), dtype=np.float32)
pos = 0
for i,s in enumerate(secs):
    with wave.open(shot_wavs[i], "rb") as wf:
        nf = wf.getnframes(); fr = wf.getframerate()
        raw = np.frombuffer(wf.readframes(nf), dtype=np.int16).astype(np.float32)/32768.0
    if fr != SR:
        xold = np.linspace(0, 1, len(raw))
        xnew = np.linspace(0, 1, int(len(raw)*SR/fr))
        raw = np.interp(xnew, xold, raw)
    seg = int(s*SR)
    cp = min(len(raw), seg)
    buf[pos:pos+cp] = raw[:cp]
    pos += seg

buf = np.clip(buf[:int(VIDEO_TOTAL*SR)], -1, 1)
voice_track = os.path.join(OUT, "voice_76.wav")
with wave.open(voice_track, "w") as wf:
    wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(SR)
    wf.writeframes((buf*32767).astype(np.int16).tobytes())
print("Voice track 76s done")

# Mix with pad
pad_path = os.path.join(AUDIO, "pad.wav")
final_audio = os.path.join(OUT, "final_audio_76.wav")
r = subprocess.run(["ffmpeg","-y","-i",voice_track,"-i",pad_path,
    "-filter_complex",
    "[1:a]volume=0.4[pad];[0:a][pad]amix=inputs=2:duration=first:dropout_transition=0[c];[c]dynaudnorm=p=0.9[out]",
    "-map","[out]","-ar","44100","-ac","2",final_audio], capture_output=True, text=True)
print("Mix OK" if r.returncode==0 else f"Mix ERR: {r.stderr[-200:]}")

# Mux
final = os.path.join(OUT, "M6_Demo_Final.mp4")
concat = os.path.join(SCENES, "concat76.mp4")
r = subprocess.run(["ffmpeg","-y","-i",concat,"-i",final_audio,
    "-c:v","copy","-c:a","aac","-b:a","192k","-shortest",final], capture_output=True, text=True)
print("Mux OK" if r.returncode==0 else f"Mux ERR: {r.stderr[-200:]}")

# Verify
r = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",final],
    capture_output=True, text=True)
sz = os.path.getsize(final)
print(f"Final: {r.stdout.strip()}s / {sz//1024}KB")

# Voice and audio durations
for i, w in enumerate(shot_wavs):
    r = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",w],
        capture_output=True, text=True)
    print(f"  shot{i+1:02d} VO: {r.stdout.strip()}s / slot: {secs[i]}s")
r = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",final_audio],
    capture_output=True, text=True)
print(f"  Mixed audio: {r.stdout.strip()}s")
