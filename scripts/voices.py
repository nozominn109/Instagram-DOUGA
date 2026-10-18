"""台本のセリフをOpen JTalk (HTS) でオフライン音声合成し、タイムラインを作る。"""
import json
from pathlib import Path

import numpy as np
import pyopenjtalk
import scipy.io.wavfile as wavfile
from pyopenjtalk.htsengine import HTSEngine

from story import LINES, SPEED_OVERRIDE, VOICES

ROOT = Path(__file__).resolve().parent.parent
VOICE_DIR = ROOT / "assets" / "voices"
OUT = ROOT / "build" / "audio"
SR = 48000
LEAD_IN = 0.35  # 冒頭の無音


def trim(x, thr=0.01):
    idx = np.where(np.abs(x) > thr * np.abs(x).max())[0]
    if len(idx) == 0:
        return x
    a, b = max(idx[0] - 480, 0), min(idx[-1] + 2400, len(x))
    return x[a:b]


def squeeze_pauses(x, max_gap=0.09, thr=0.02):
    """読点などで入る長い無音を max_gap 秒に詰める。"""
    win = int(SR * 0.01)
    n = len(x) // win
    env = np.abs(x[: n * win]).reshape(n, win).max(axis=1)
    quiet = env < thr * env.max()
    keep = np.ones(n, bool)
    limit = int(max_gap / 0.01)
    run = 0
    for i, q in enumerate(quiet):
        run = run + 1 if q else 0
        if run > limit:
            keep[i] = False
    return np.concatenate([x[i * win:(i + 1) * win] for i in range(n) if keep[i]] + [x[n * win:]])


def synth(text, voice, half_tone, speed, gain):
    engine = HTSEngine(str(VOICE_DIR / voice).encode())
    assert engine.get_sampling_frequency() == SR
    labels = pyopenjtalk.extract_fullcontext(text)
    engine.set_speed(speed)
    engine.add_half_tone(half_tone)
    x = squeeze_pauses(trim(engine.synthesize(labels)) / 32768.0)
    x = x / (np.abs(x).max() + 1e-9) * 0.8 * gain
    fade = int(SR * 0.01)
    x[:fade] *= np.linspace(0, 1, fade)
    x[-fade:] *= np.linspace(1, 0, fade)
    return x


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    t = LEAD_IN
    timeline = []
    for lid, speaker, sub, tts, pause in LINES:
        if tts is None:
            dur = 0.0
        else:
            voice, ht, sp, gain = VOICES[speaker]
            sp = SPEED_OVERRIDE.get(lid, sp)
            x = synth(tts, voice, ht, sp, gain)
            wavfile.write(OUT / f"{lid}.wav", SR, (x * 32767).astype(np.int16))
            dur = len(x) / SR
        timeline.append({"id": lid, "speaker": speaker, "text": sub, "start": round(t, 3),
                         "dur": round(dur, 3), "end": round(t + dur + pause, 3),
                         "audio": tts is not None})
        print(f"{lid} {speaker:7s} {t:6.2f}s +{dur:4.2f}s")
        t += dur + pause
    (ROOT / "build" / "timeline.json").write_text(json.dumps(timeline, ensure_ascii=False, indent=1))
    print("total", round(t, 2))


if __name__ == "__main__":
    main()
