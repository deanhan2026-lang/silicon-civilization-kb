#!/usr/bin/env python3
"""快速合成：xfade+pad → 音频 → mux（不重渲染帧）"""
import os, subprocess, wave, numpy as np
import scenes, audio

ROOT = os.path.dirname(os.path.abspath(__file__))
SCENES = os.path.join(ROOT, "scenes")
OUT_DIR = os.path.join(ROOT, "out")
os.makedirs(OUT_DIR, exist_ok=True)
FINAL = os.path.join(OUT_DIR, "M6_Demo_Final.mp4")
N = len(scenes.SHOTS)
VIDEO_BASE = scenes.EFFECTIVE_TOTAL  # 72s
PAD_END = 4  # 4s 定格尾帧让旁白播完
VIDEO_TOTAL = VIDEO_BASE + PAD_END
SR = 44100

def run(cmd, label):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode: print(f"[ERR] {label}: {r.stderr[-300:]}"); exit(1)
    print(f"[OK] {label}")

# 1) Xfade + pad to 76s
print("--- Xfade + pad ---")
d = 0.5; secs = scenes.SHOT_SECONDS; offs = [0.0]
for s in secs[:-1]: offs.append(offs[-1]+s-d)
inputs = [os.path.join(SCENES,f"shot{i:02d}.mp4") for i in range(1,N+1)]
cmds = ["ffmpeg","-y"]
for i in inputs: cmds += ["-i",i]
prev = "0:v"; clauses = []
for i in range(1,N):
    outl = f"v{i}"; clauses.append(f"[{prev}][{i}:v]xfade=transition=fade:duration={d}:offset={offs[i]:.2f}[{outl}]"); prev = outl
clauses.append(f"[{prev}]trim=duration={VIDEO_TOTAL},setpts=PTS-STARTPTS[padded]")
cmds += ["-filter_complex",";".join(clauses),"-map","[padded]","-c:v","libx264","-pix_fmt","yuv420p","-crf","18",
         os.path.join(SCENES,"concat.mp4")]
run(cmds, "xfade+pad")

# 2) Voice track — buffer 75s, 截到 VIDEO_TOTAL (76s)
print("--- Audio ---")
shot_wavs = [os.path.join(audio.AUDIO_DIR, f"shot{i:02d}.wav") for i in range(1,N+1)]
buf = np.zeros(int(sum(secs)*SR), dtype=np.float32)
pos = 0
for i, s in enumerate(secs):
    with wave.open(shot_wavs[i],"rb") as wf:
        nf=wf.getnframes(); fr=wf.getframerate()
        raw=np.frombuffer(wf.readframes(nf),dtype=np.int16).astype(np.float32)/32768.0
    if fr!=SR:
        xold=np.linspace(0,1,len(raw)); xnew=np.linspace(0,1,int(len(raw)*SR/fr))
        raw=np.interp(xnew,xold,raw)
    seg=int(s*SR); cp=min(len(raw),seg); buf[pos:pos+cp]=raw[:cp]; pos+=seg
buf=np.clip(buf[:int(VIDEO_TOTAL*SR)],-1,1)
voice_track=os.path.join(OUT_DIR,"voice_track.wav")
with wave.open(voice_track,"w") as wf:
    wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(SR)
    wf.writeframes((buf*32767).astype(np.int16).tobytes())

# 3) Pad
pad_path = audio.make_pad(VIDEO_TOTAL)

# 4) Mix
final_audio = os.path.join(OUT_DIR,"final_audio.wav")
run(["ffmpeg","-y","-i",voice_track,"-i",pad_path,
     "-filter_complex","[1:a]volume=0.4[pad];[0:a][pad]amix=inputs=2:duration=first:dropout_transition=0[c];[c]dynaudnorm=p=0.9[out]",
     "-map","[out]","-ar","44100","-ac","2",final_audio],"mix+norm")

# 5) Mux (-shortest 自动切到~74s或till 76s)
run(["ffmpeg","-y","-i",os.path.join(SCENES,"concat.mp4"),"-i",final_audio,
     "-c:v","copy","-c:a","aac","-b:a","192k","-shortest",FINAL],"final mux")

# Clean & report
for f in [os.path.join(SCENES,"concat.mp4"),voice_track,final_audio]:
    try: os.remove(f)
    except: pass
for f in [os.path.join(SCENES,f"shot{i:02d}.mp4") for i in range(1,N+1)]:
    try: os.remove(f)
    except: pass

sz=os.path.getsize(FINAL)
rd=subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",FINAL],capture_output=True,text=True)
print(f"Final: {rd.stdout.strip()}s / {sz//1024}KB")
