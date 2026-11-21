"""田中家リール制作の道具箱（声の確認・蒼の声の加工・コマ一覧・表紙・投稿ライブラリへの保存）。

使い方（リポジトリの一番上で）:
    python3 scripts/tools.py setup                         # 新しい環境で最初に1回（足りないものを入れる）
    python3 scripts/tools.py voices 声1.mp3 声2.mp3 ...     # 長さ・無音・発声のかたまり・だれの声っぽいか
    python3 scripts/tools.py trim 入力.mp3 出力.mp3 --start 1.2 [--end 3.4]   # 言い直しを切る
    python3 scripts/tools.py sora 入力.mp3 出力.mp3 [--start 1.1] [--end 3.0] # 蒼の声の加工＋音量をそろえる
    python3 scripts/tools.py level 声.mp3                   # 平均の音量（目安 −20dB前後）
    python3 scripts/tools.py sheet 動画.mp4 一覧.png [--fps 1.4 --cols 10 --w 160]  # コマを並べた確認画像
    python3 scripts/tools.py frame 動画.mp4 秒 出力.png [--w 360]                   # 1コマだけ取り出す
    python3 scripts/tools.py webp 受け取った絵.webp 保存先.png                       # チャットの絵を保存
    python3 scripts/tools.py cover 絵.png 表紙.jpg --line "上の子ばっかり:96:pink" --line "怒っちゃう:116:pink" --y 1130
    python3 scripts/tools.py grid 表紙.jpg 確認.png        # プロフィール一覧（3:4）で切れないか
    python3 scripts/tools.py publish "2026-11-23_ショート_題名" --video 最終版.mp4 --cover 表紙.jpg [--caption 文.txt]
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIB = ROOT / "投稿ライブラリ" / "田中家_Instagram"
SR16 = 16000

# 声の見分け用の見本（あるものだけ使う）
REFS = {
    "愛奈": ["output/short04_yuhan/voices/Y2_aina.mp3", "output/jitan02_print/voices/P3_aina.mp3",
            "output/un1116/voices/U1_aina.mp3", "output/ep02/voices/E8_aina.mp3"],
    "莉奈": ["output/short04_yuhan/voices/Y3_rina.mp3", "output/short05_shukudai/voices/H4_rina.mp3",
            "output/short05_shukudai/voices/H5_rina.mp3"],
    "哲（パパ）": ["output/short04_yuhan/voices/Y4_satoru.mp3", "output/ep02/voices/E2_satoru.mp3",
                 "output/jitan02_print/voices/P2_satoru.mp3"],
    "蒼（加工前）": ["output/ep02/voices/E9_sora.orig.mp3", "output/short04_yuhan/voices/Y5_sora_orig.mp3",
                  "output/ue1123/voices/A4_sora.orig.mp3"],
    "AIくん": ["output/short04_yuhan/voices/Y1_ai.mp3", "output/un1116/voices/U7_ai.mp3",
             "output/ep02/voices/E5_ai.mp3"],
}
COLORS = {"pink": (236, 92, 108), "blue": (90, 110, 170), "mint": (74, 170, 150), "brown": (120, 96, 84),
          "purple": (150, 110, 200)}


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def load16(path):
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(SR16), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32)


def timbre(x):
    """声の響き（ケプストラム）の平均。声の高さではなく声色で見分ける。"""
    import numpy as np
    n = 512
    x = x * (0.1 / max(float(np.sqrt((x ** 2).mean())), 1e-6))  # 小さい声（蒼など）も同じ大きさにしてから比べる
    fr = [x[i:i + n] * np.hanning(n) for i in range(0, len(x) - n, 256)]
    fr = [f for f in fr if np.sqrt((f ** 2).mean()) > 0.02]
    if not fr:
        return None
    s = np.log(np.abs(np.fft.rfft(np.array(fr), axis=1)) + 1e-6)
    return np.fft.irfft(s, axis=1)[:, 1:20].mean(0)


def cmd_setup(a):
    need = []
    for mod in ("numpy", "scipy", "PIL"):
        try:
            __import__(mod)
        except ImportError:
            need.append("pillow" if mod == "PIL" else mod)
    if need:
        print("入れます:", need)
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", *need])
    if not shutil.which("ffmpeg"):
        print("× ffmpeg がありません（apt-get install -y ffmpeg）")
    else:
        filt = run(["ffmpeg", "-hide_banner", "-filters"]).stdout
        print("ffmpeg: OK", "／ rubberband:", "OK" if "rubberband" in filt else "× なし（蒼の声の加工に必要）")
    for f in ("assets/fonts/MPLUSRounded1c-ExtraBold.ttf", "assets/sounds/bgm.mp3", "assets/sounds/living_ambience.mp3"):
        print(f, "OK" if (ROOT / f).exists() else "× ない")
    print("準備おわり")


def cmd_voices(a):
    import numpy as np
    refs = {}
    for who, files in REFS.items():
        vs = [timbre(load16(ROOT / f)) for f in files if (ROOT / f).exists()]
        vs = [v for v in vs if v is not None]
        if vs:
            refs[who] = np.mean(vs, 0)
    for p in a.files:
        x = load16(p)
        dur = len(x) / SR16
        # 50msごとの大きさから「声のかたまり」を出す（言い直しの見つけ方：同じくらいの長さのかたまりが2つ続く）
        e = np.array([np.sqrt((x[i:i + 800] ** 2).mean()) for i in range(0, len(x), 800)])
        on = e > max(0.012, e.max() * 0.08)
        segs, st = [], None
        for i, v in enumerate(on):
            if v and st is None:
                st = i
            if not v and st is not None:
                if i - st >= 2:
                    segs.append((st * 0.05, i * 0.05))
                st = None
        if st is not None:
            segs.append((st * 0.05, len(on) * 0.05))
        merged = []
        for s, t in segs:  # 0.15秒より短いすき間はつなげる
            if merged and s - merged[-1][1] < 0.15:
                merged[-1] = (merged[-1][0], t)
            else:
                merged.append((s, t))
        mv = run(["ffmpeg", "-i", str(p), "-af", "volumedetect", "-f", "null", "-"]).stderr
        mean = re.search(r"mean_volume: ([-0-9.]+)", mv)
        guess = ""
        tv = timbre(x)
        if tv is not None and refs:
            d = sorted((float(np.linalg.norm(tv - v)), k) for k, v in refs.items())
            guess = "　だれっぽいか: " + " ＞ ".join(f"{k}({v:.2f})" for v, k in d[:3]) + "（数字が小さいほど近い）"
        name = Path(p).name
        hint = ""
        if "_pvc_" in name:
            hint = "　★ファイル名に「pvc」＝蒼（Hinata）の声"
        elif "_AI_" in name:
            hint = "　★ファイル名に「AI」＝AIくんの声"
        print(f"■ {name}{hint}")
        print(f"  長さ {dur:.2f}秒　平均の音量 {mean.group(1) if mean else '?'}dB{guess}")
        print("  声のかたまり: " + "　".join(f"{s:.2f}〜{t:.2f}" for s, t in merged))


def cmd_trim(a):
    af = []
    if a.end:
        fade_st = max(0.0, a.end - a.start - 0.12)
        af = ["-af", f"afade=t=out:st={fade_st:.2f}:d=0.12"]
    cmd = ["ffmpeg", "-v", "error", "-y", "-ss", str(a.start), "-i", a.inp]
    if a.end:
        cmd += ["-t", f"{a.end - a.start:.3f}"]
    subprocess.run(cmd + af + ["-b:a", "192k", a.out], check=True)
    print("書き出し:", a.out)


def mean_db(path):
    m = re.search(r"mean_volume: ([-0-9.]+)", run(["ffmpeg", "-i", str(path), "-af", "volumedetect", "-f", "null",
                                                   "-"]).stderr)
    return float(m.group(1)) if m else None


def cmd_sora(a):
    """蒼の声：高さ1.1倍（響きは保つ）・少しゆっくり・高い音を少し削る → 平均−21dBにそろえる（ほかのキャラと同じ大きさ）。"""
    tmp = Path(a.out).with_suffix(".tmp.wav")
    cmd = ["ffmpeg", "-v", "error", "-y", "-ss", str(a.start), "-i", a.inp]
    if a.end:
        cmd += ["-t", f"{a.end - a.start:.3f}"]
    cmd += ["-af", "rubberband=pitch=1.1:formant=preserved:pitchq=quality,atempo=0.95,lowpass=f=4200", "-ar", "44100",
            str(tmp)]
    subprocess.run(cmd, check=True)
    g = -21 - mean_db(tmp)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(tmp), "-af", f"volume={g:.1f}dB,alimiter=limit=0.89",
                    "-b:a", "192k", a.out], check=True)
    tmp.unlink()
    print(f"書き出し: {a.out}（音量 {mean_db(a.out)}dB）")


def cmd_level(a):
    for p in a.files:
        print(Path(p).name, mean_db(p), "dB")


def cmd_sheet(a):
    dur = float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", a.video]).stdout)
    n = int(dur * a.fps) + 1
    rows = (n + a.cols - 1) // a.cols
    vf = f"fps={a.fps},scale={a.w}:-1,tile={a.cols}x{rows}"
    if a.crop:
        vf = f"crop={a.crop}," + vf
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", a.video, "-vf", vf, "-frames:v", "1", a.out], check=True)
    print(f"書き出し: {a.out}（{dur:.1f}秒・1枚あたり {1 / a.fps:.2f}秒おき）")


def cmd_frame(a):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(a.t), "-i", a.video, "-frames:v", "1", "-vf",
                    f"scale={a.w}:-1", a.out], check=True)
    print("書き出し:", a.out)


def cmd_webp(a):
    from PIL import Image
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Image.open(a.inp).convert("RGB").save(a.out)
    print("保存:", a.out)


def cmd_cover(a):
    sys.path.insert(0, str(ROOT / "scripts"))
    from PIL import Image
    from assemble_ai import W, H
    from render import paste
    from short_ai_ok import small_logo, text_block
    im = Image.open(a.image).convert("RGBA").resize((W, H))
    y = a.y
    for spec in a.line:
        txt, size, col = spec.rsplit(":", 2)
        size = int(size)
        text_block(im, [(txt, size, COLORS.get(col, COLORS["pink"]))], y, 5, instant=True, cx=a.cx or W / 2)
        y += size + 40
    paste(im, small_logo(), 30, 300)
    im.convert("RGB").save(a.out, quality=92)
    print("書き出し:", a.out, "（文字は横幅の中央90%以内・顔にかからないか、grid でも確認）")


def cmd_grid(a):
    from PIL import Image
    c = Image.open(a.cover).convert("RGB").resize((1080, 1920))
    g = c.crop((0, 240, 1080, 1680)).resize((540, 720))
    g.save(a.out)
    print("書き出し:", a.out, "（プロフィール一覧の3:4で見える範囲）")


def cmd_publish(a):
    d = LIB / a.folder
    d.mkdir(parents=True, exist_ok=True)
    if a.video:
        shutil.copy(a.video, d / "最終版.mp4")
    if a.cover:
        shutil.copy(a.cover, d / "表紙.jpg")
    if a.caption:
        shutil.copy(a.caption, d / "キャプション_最終版.txt")
    print("保存:", d, [p.name for p in d.iterdir()])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("setup").set_defaults(fn=cmd_setup)
    p = sp.add_parser("voices"); p.add_argument("files", nargs="+"); p.set_defaults(fn=cmd_voices)
    p = sp.add_parser("trim"); p.add_argument("inp"); p.add_argument("out")
    p.add_argument("--start", type=float, default=0.0); p.add_argument("--end", type=float); p.set_defaults(fn=cmd_trim)
    p = sp.add_parser("sora"); p.add_argument("inp"); p.add_argument("out")
    p.add_argument("--start", type=float, default=0.0); p.add_argument("--end", type=float); p.set_defaults(fn=cmd_sora)
    p = sp.add_parser("level"); p.add_argument("files", nargs="+"); p.set_defaults(fn=cmd_level)
    p = sp.add_parser("sheet"); p.add_argument("video"); p.add_argument("out")
    p.add_argument("--fps", type=float, default=1.4); p.add_argument("--cols", type=int, default=10)
    p.add_argument("--w", type=int, default=160); p.add_argument("--crop"); p.set_defaults(fn=cmd_sheet)
    p = sp.add_parser("frame"); p.add_argument("video"); p.add_argument("t", type=float); p.add_argument("out")
    p.add_argument("--w", type=int, default=360); p.set_defaults(fn=cmd_frame)
    p = sp.add_parser("webp"); p.add_argument("inp"); p.add_argument("out"); p.set_defaults(fn=cmd_webp)
    p = sp.add_parser("cover"); p.add_argument("image"); p.add_argument("out")
    p.add_argument("--line", action="append", required=True, help="文字:大きさ:色（pink/blue/mint/brown/purple）")
    p.add_argument("--y", type=int, default=1130); p.add_argument("--cx", type=int); p.set_defaults(fn=cmd_cover)
    p = sp.add_parser("grid"); p.add_argument("cover"); p.add_argument("out"); p.set_defaults(fn=cmd_grid)
    p = sp.add_parser("publish"); p.add_argument("folder"); p.add_argument("--video"); p.add_argument("--cover")
    p.add_argument("--caption"); p.set_defaults(fn=cmd_publish)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
