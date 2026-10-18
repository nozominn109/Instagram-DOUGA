"""動画生成AIで作ったカット素材を差し込んで、リールを組み立て直す。

clips/C01.mp4 〜 clips/C13.mp4 のうち置いてあるカットだけ差し替え、
無いカットは今のアニメ（output/tanakake_ep01_dokusho.mp4）をそのまま使う。
差し替えたカットには字幕・タイトル・エンドカードを重ね、音声は build/mix.wav を使う。

使い方:
    python3 scripts/kit.py                 # 制作キット（カット表・音声・字幕）を書き出し
    # 動画生成AIで作った素材を output/ep01_kit/clips/C01.mp4 のように置く
    python3 scripts/assemble.py            # -> output/tanakake_ep01_dokusho_ai.mp4
"""
import subprocess
from pathlib import Path

from PIL import Image

import render
from render import FPS, H, TOTAL, W

ROOT = Path(__file__).resolve().parent.parent
KIT = ROOT / "output" / "ep01_kit"
CLIPS = KIT / "clips"
BASE = ROOT / "output" / "tanakake_ep01_dokusho.mp4"
OUT = ROOT / "output" / "tanakake_ep01_dokusho_ai.mp4"
L = render.LINE

# (カットID, 開始秒, 終了秒, 内容)。phone=True のカットはスマホ画面なので今の映像を使う
CUTS = [
    ("C01", 0.0, L["l02"]["start"], "全景→莉奈がスマホに「AIくーん」", False),
    ("C02", L["l02"]["start"], L["l04"]["start"], "パパが慌てて覗き込む／莉奈ふくれっ面", False),
    ("C03", L["l04"]["start"], L["l05"]["start"] - 0.1, "ママがスマホをやさしく取り上げる", False),
    ("C04", L["l05"]["start"] - 0.1, L["l06"]["start"] - 0.1, "スマホ画面：プロンプト", True),
    ("C05", L["l06"]["start"] - 0.1, L["l10"]["start"], "莉奈が納得／ママが語りかける", False),
    ("C06", L["l10"]["start"], L["l11"]["start"] - 0.1, "莉奈「AI、質問して〜！」", False),
    ("C07", L["l11"]["start"] - 0.1, L["l12"]["start"] - 0.05, "スマホ画面：AIの返信", True),
    ("C08", L["l12"]["start"] - 0.05, L["l13"]["start"], "莉奈ワクワク", False),
    ("C09", L["l13"]["start"], L["l14"]["start"], "パパ遠い目", False),
    ("C10", L["l14"]["start"], L["l15"]["start"], "蒼がソファから冷めた目", False),
    ("C11", L["l15"]["start"], L["l16"]["start"], "希亜「あーあー！」", False),
    ("C12", L["l16"]["start"], render.END_T, "チャッピー「ワン！」", False),
    ("C13", render.END_T, TOTAL, "家族全景＋エンドカード", False),
]


def frames(path, size=(W, H)):
    """動画を 1080x1920 / 30fps に合わせて（中央トリミング）1フレームずつ返す。"""
    vf = f"fps={FPS},scale={size[0]}:{size[1]}:force_original_aspect_ratio=increase,crop={size[0]}:{size[1]}"
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(path), "-vf", vf, "-f", "rawvideo", "-pix_fmt", "rgb24",
                          "-"], stdout=subprocess.PIPE)
    n = size[0] * size[1] * 3
    while True:
        buf = p.stdout.read(n)
        if len(buf) < n:
            break
        yield buf
    p.wait()


def find_clip(cid):
    for ext in ("mp4", "mov", "webm"):
        p = CLIPS / f"{cid}.{ext}"
        if p.exists():
            return p
    return None


def overlay(buf, t):
    f = Image.frombytes("RGB", (W, H), buf).convert("RGBA")
    if t < render.END_T:
        render.paste(f, render.title_band(), 0, 70)
        for ln in render.TL:
            render.draw_subtitle(f, ln["id"], t)
    else:
        render.end_overlay(f, t)
    return f.convert("RGB").tobytes()


def main():
    used = {c[0]: find_clip(c[0]) for c in CUTS if not c[4]}
    print("差し替え:", [k for k, v in used.items() if v] or "なし")
    base = frames(BASE)
    n = int(TOTAL * FPS)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-i", str(render.BUILD / "mix.wav"), "-c:v", "libx264", "-preset", "medium",
           "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest",
           "-movflags", "+faststart", str(OUT)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    cur, reader, last = None, None, None
    for i in range(n):
        t = i / FPS
        b = next(base, None)
        cut = next(c for c in CUTS if c[1] <= t < c[2]) if t < CUTS[-1][2] else CUTS[-1]
        clip = None if cut[4] else used.get(cut[0])
        if clip is None:
            proc.stdin.write(b)
            continue
        if cur != cut[0]:
            cur, reader, last = cut[0], frames(clip), None
        fb = next(reader, None)
        last = fb if fb is not None else last  # 素材が短いときは最後のコマで止める
        proc.stdin.write(overlay(last, t))
    proc.stdin.close()
    proc.wait()
    print("wrote", OUT)


if __name__ == "__main__":
    main()
