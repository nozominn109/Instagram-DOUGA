"""台本のセリフを VOICEVOX で音声合成し、口パク用のモーラタイミング付きタイムラインを作る。

事前に VOICEVOX ENGINE を起動しておく（既定: http://127.0.0.1:50021）。
"""
import io
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
import scipy.io.wavfile as wavfile

from story import LINES, STYLE_OVERRIDE, VOICES

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "build" / "audio"
ENGINE = os.environ.get("VOICEVOX_URL", "http://127.0.0.1:50021")
SR = 48000
LEAD_IN = 0.35  # 冒頭の無音
PRE, POST = 0.05, 0.08

# 母音ごとの口の開き具合
OPEN = {"a": 1.0, "o": 0.8, "e": 0.65, "u": 0.45, "i": 0.4, "N": 0.15, "cl": 0.0, "pau": 0.0}
LIPS = {"m", "b", "p", "my", "by", "py"}  # 子音で口を閉じる


def post(path, data=None, **params):
    url = f"{ENGINE}{path}?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, data=data, method="POST", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return r.read()


def mouth_track(q):
    """audio_query から [(開始秒, 終了秒, 開き具合)] を作る。"""
    sp = q["speedScale"]
    t = q["prePhonemeLength"] / sp
    track = []
    for ap in q["accent_phrases"]:
        for m in ap["moras"]:
            c = (m.get("consonant_length") or 0) / sp
            v = m["vowel_length"] / sp
            if c:
                track.append((t, t + c, 0.0 if m.get("consonant") in LIPS else OPEN.get(m["vowel"], 0.5) * 0.5))
            track.append((t + c, t + c + v, OPEN.get(m["vowel"], 0.5)))
            t += c + v
        if ap.get("pause_mora"):
            v = ap["pause_mora"]["vowel_length"] * q.get("pauseLengthScale", 1.0) / sp
            track.append((t, t + v, 0.0))
            t += v
    return [(round(a, 3), round(b, 3), o) for a, b, o in track]


def synth(lid, speaker, text):
    style, speed, pitch, inton, vol = VOICES[speaker]
    style = STYLE_OVERRIDE.get(lid, style)
    q = json.loads(post("/audio_query", speaker=style, text=text))
    q.update(speedScale=speed, pitchScale=pitch, intonationScale=inton, volumeScale=vol,
             prePhonemeLength=PRE, postPhonemeLength=POST, pauseLengthScale=0.6, outputSamplingRate=SR, outputStereo=False)
    wav = post("/synthesis", data=json.dumps(q).encode(), speaker=style)
    sr, x = wavfile.read(io.BytesIO(wav))
    assert sr == SR
    x = x.astype(float) / 32768
    x = x / (np.abs(x).max() + 1e-9) * 0.85 * vol
    return x, mouth_track(q)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    t = LEAD_IN
    timeline = []
    for lid, speaker, sub, tts, pause in LINES:
        mouth = []
        if tts is None:
            dur = 0.0
        else:
            x, mouth = synth(lid, speaker, tts)
            wavfile.write(OUT / f"{lid}.wav", SR, (x * 32767).astype(np.int16))
            dur = len(x) / SR
        timeline.append({"id": lid, "speaker": speaker, "text": sub, "start": round(t, 3),
                         "dur": round(dur, 3), "end": round(t + dur + pause, 3),
                         "audio": tts is not None, "mouth": mouth})
        print(f"{lid} {speaker:7s} {t:6.2f}s +{dur:4.2f}s")
        t += dur + pause
    (ROOT / "build" / "timeline.json").write_text(json.dumps(timeline, ensure_ascii=False, indent=1))
    print("total", round(t, 2))


if __name__ == "__main__":
    main()
