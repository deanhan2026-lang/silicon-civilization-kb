import audio, scenes, os, wave, numpy as np, subprocess

AUDIO_DIR = audio.AUDIO_DIR
n = len(scenes.SHOT_SECONDS)
ROOT = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(ROOT, "out")
SR = 44100
VIDEO_SEC = scenes.EFFECTIVE_TOTAL  # 72s (视频时长)

def run(cmd, label):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"[ERROR] {label}: {r.stderr[-300:]}")
    else:
        print(f"[OK] {label}")

# TTS regenerate
for i in range(1, n+1):
    mp3 = audio.synth_shot(i, scenes.NARRATION[i-1])
    audio.normalize_to_wav(mp3, i)

# Pad (72s)
pad_path = audio.make_pad(VIDEO_SEC)

# Build voice track — buffer按75s开（占位之和），写wav时截到72s
shot_wavs = [os.path.join(AUDIO_DIR, f"shot{i:02d}.wav") for i in range(1, n+1)]
total_raw = int(sum(scenes.SHOT_SECONDS) * SR)  # 75s buffer确保尾部不截
buf = np.zeros(total_raw, dtype=np.float32)
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
buf = np.clip(buf, -1, 1)
# 截到视频时长
voice_buf = buf[:int(VIDEO_SEC * SR)]
voice_track = os.path.join(OUT_DIR, "voice_track.wav")
with wave.open(voice_track, "w") as wf:
    wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(SR)
    wf.writeframes((voice_buf*32767).astype(np.int16).tobytes())
print("Voice track built")

# Mix voice + pad with normalize
final_audio = os.path.join(OUT_DIR, "final_audio.wav")
run([
    "ffmpeg", "-y",
    "-i", voice_track,
    "-i", pad_path,
    "-filter_complex",
    "[1:a]volume=0.4[pad];[0:a][pad]amix=inputs=2:duration=first:dropout_transition=0[c];"
    "[c]dynaudnorm=p=0.9[out]",
    "-map", "[out]", "-ar", "44100", "-ac", "2", final_audio
], "mix+norm")

# Mux with video (no subtitle burn)
concat = os.path.join(ROOT, "scenes", "concat.mp4")
final = os.path.join(OUT_DIR, "M6_Demo_Final.mp4")
run([
    "ffmpeg", "-y",
    "-i", concat,
    "-i", final_audio,
    "-c:v", "copy",
    "-c:a", "aac", "-b:a", "192k",
    "-shortest", final
], "final mux")

sz = os.path.getsize(final)
print(f"\n=== DONE: {final} ({sz/1024:.0f} KB / {VIDEO_SEC:.0f}s) ===")
