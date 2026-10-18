"""動画生成AI用の制作キットを書き出す。

output/ep01_kit/
  voices/C01.wav ...   カットごとのセリフ音声（リップシンク機能にそのまま入れる）
  frames/C01.png ...   今のアニメのカット中央フレーム（構図の参考・画像→動画の下絵）
  ep01.srt             字幕（CapCut等で読み込める）
  clips/               生成した動画素材の置き場（C01.mp4 のように置く）
"""
import numpy as np
import scipy.io.wavfile as wavfile
from PIL import Image

import render
from assemble import CLIPS, CUTS, KIT
from render import SR


def srt_time(t):
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def main():
    (KIT / "voices").mkdir(parents=True, exist_ok=True)
    (KIT / "frames").mkdir(exist_ok=True)
    CLIPS.mkdir(exist_ok=True)
    for cid, a, b, desc, phone in CUTS:
        n = int((b - a) * SR)
        mix = np.zeros(n)
        for ln in render.TL:
            if ln["audio"] and a <= ln["start"] < b:
                _, x = wavfile.read(render.BUILD / "audio" / f"{ln['id']}.wav")
                j = int((ln["start"] - a) * SR)
                seg = x.astype(float)[: max(0, n - j)]
                mix[j:j + len(seg)] += seg
        if mix.any():
            wavfile.write(KIT / "voices" / f"{cid}.wav", SR, mix.astype(np.int16))
        i = int((a + b) / 2 * render.FPS)
        Image.frombytes("RGB", (render.W, render.H), render.render_frame(i)).save(KIT / "frames" / f"{cid}.png")
        print(cid, f"{a:5.2f}-{b:5.2f}s ({b - a:.1f}s)", desc)
    rows = [ln for ln in render.TL if ln["text"]]
    srt = "\n".join(f"{k + 1}\n{srt_time(ln['start'])} --> {srt_time(ln['end'])}\n{ln['text']}\n"
                    for k, ln in enumerate(rows))
    (KIT / "ep01.srt").write_text(srt, encoding="utf-8")


if __name__ == "__main__":
    main()
