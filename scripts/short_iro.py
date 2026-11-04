"""ショート③ 探究心の続編「チャッピーって、何色が見えてるの？」を仕上げる。

素材: output/short02b_tankyu/clips/（Klingの動画＋使い回し）、voices/（ElevenLabsの声）
声の長い間（ま）は短くつめ、場面の長さは声に合わせて自動で決める。

使い方:
    python3 scripts/short_tankyu.py   # -> output/short02b_tankyu/short02b_tankyu.mp4
"""
import subprocess

import numpy as np
import scipy.io.wavfile as wavfile
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from assemble_ai import AMBIENCE, FPS, H, ROOT, SR, W, load_loop, music_bed, sub_img, message_pop
from render import FONT_B, INK, back_out, ease, font, outlined, paste, phone_screen, sparkles
from short_ai_ok import small_logo, text_block

KIT = ROOT / "output" / "short03_iro"
CLIPS, VOICES = KIT / "clips", KIT / "voices"
OUT = KIT / "short03_iro.mp4"
A_CLIP = "A_color" if (CLIPS / "A_color.mp4").exists() else "A_color_still"  # Klingの動画がなければ絵をゆっくりズーム
TEMPO = 1.1 * 1.15 * 1.1  # 決まったテンポ（声1.1倍×全体1.15倍）をさらに1.1倍（11/4 希さん）
GAP = 0.06  # セリフとセリフの間

# 場面: (名前, 動画, 動画の開始秒, [(声, 話す人, 字幕), ...], 前の余白, 後ろの余白)
SCENES = [
    ("open", "ep01_C12", 0.3, [("T9_rina", "rina", "じゃあ次は…\nチャッピーって、何色が見えてるの？")], 0.9, 0.1),
    ("phone1", None, 0.0, [("U1_ai", "ai", None), ("U2_rina", "rina", None)], 0.35, 0.25),
    ("color", A_CLIP, 0.0, [("U3_rina", "rina", "赤は見えにくいんだ！")], 1.6, 0.3),
    ("phone2", None, 0.0, [("U4_rina", "rina", None), ("U5_ai", "ai", None), ("U6_rina", "rina", None)], 0.2, 0.25),
    ("cups", "B_cups", 0.0, [("U7_rina", "rina", "すごっ！")], 2.6, 0.5),
    ("next", "ep01_C06", 0.0, [("U8_rina", "rina", "じゃあチャッピーの鼻って、\nどこまでわかるの？"),
                               ("T10_aina", "aina", "ママも知りたい！")], 0.05, 0.1),
    ("omoi", "ep01_C09", 0.0, [("U9_aina", "aina", "知らなかったことを一つ知るだけで、\n世界がちょっと楽しくなるね")], 0.1, 0.25),
    ("end", "B_cups", 4.0, [], 3.2, 0.0),
]
CHAT_FIRST = {"phone1": ("me", "チャッピーって、何色が見えてるの？"), "phone2": None}
CHAT = {"U1_ai": ("ai", "莉奈さんの予想は？"), "U2_rina": ("me", "白黒？"),
        "U4_rina": ("me", "でも、見えにくいのに、おやつはすぐ見つけるよね？"), "U5_ai": ("ai", "なんでだと思う？"),
        "U6_rina": ("me", "…鼻？")}


def voice(name):
    """声を読み込み、決まったテンポにして、長い間（ま）を短くつめる。"""
    af = (f"silenceremove=start_periods=1:start_threshold=-35dB:stop_periods=-1:stop_duration=0.2:"
          f"stop_threshold=-35dB:stop_silence=0.12,atempo={TEMPO}")
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(VOICES / f"{name}.mp3"), "-af", af, "-ac", "1", "-ar",
                          str(SR), "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).astype(float)


def probe(path):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                 str(path)], capture_output=True, text=True, check=True).stdout)


def clip_frames(clip, start, dur, blur=False):
    """動画を場面の長さに合わせて流す（足りなければ少しゆっくり、それでも足りなければ最後のコマで止める）。"""
    avail = probe(CLIPS / f"{clip}.mp4") - start
    speed = min(1.15, max(0.6, avail / dur))
    vf = (f"trim=start={start},setpts=(PTS-STARTPTS)/{speed},fps={FPS},"
          f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H}")
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(CLIPS / f"{clip}.mp4"), "-vf", vf, "-f", "rawvideo",
                          "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    n, last = W * H * 3, None
    for _ in range(round(dur * FPS)):
        buf = p.stdout.read(n)
        if len(buf) == n:
            last = Image.frombytes("RGB", (W, H), buf)
        f = last.copy()
        if blur:
            f = ImageEnhance.Brightness(f.filter(ImageFilter.GaussianBlur(14))).enhance(0.85)
        yield f.convert("RGBA")
    p.stdout.close()
    p.wait()


def plan():
    vo, t, out = {}, 0.0, []
    for name, clip, cst, lines, pre, post in SCENES:
        lt, timed = pre, []
        for v, sp, sub in lines:
            vo[v] = voice(v)
            timed.append((v, sp, sub, lt, len(vo[v]) / SR))
            lt += len(vo[v]) / SR + GAP
        dur = (lt - GAP if lines else lt) + post
        out.append(dict(name=name, clip=clip, cst=cst, t0=t, dur=dur, lines=timed))
        t += dur
    return out, vo, t


def decorate(f, sc, lt):
    name, dur = sc["name"], sc["dur"]
    if name == "open":
        text_block(f, [("昨日の続き…", 64, (120, 96, 84)), ("莉奈の“知りたい”が", 76, (236, 92, 108)),
                       ("止まらない！", 76, (236, 92, 108))], 860, lt)
    if name in ("phone1", "phone2"):
        first = CHAT_FIRST.get(name)
        msgs = [(first[0], first[1], 99, (), 0)] if first else []
        for v, sp, sub, st, ln in sc["lines"]:
            who, text = CHAT[v]
            if lt >= st - 0.1:
                k = 1 if who == "me" else min(1, (lt - st) / max(ln * 0.8, 0.1))
                msgs.append((who, text, int(len(text) * k) if who == "ai" else 99, (), 0))
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        phone_screen(layer, lt, msgs, "AIに聞いてみた", (lt + 0.05) / 0.35)
        f.alpha_composite(layer, (0, 170))
    if name == "color" and lt < 1.4:
        text_block(f, [("青・黄色・赤で", 64, (74, 170, 150)), ("ためしてみよう！", 80, (74, 170, 150))], 900, lt, 0.05)
    if name == "cups" and lt < 1.8:
        text_block(f, [("おやつはどのコップ？", 72, (74, 170, 150))], 900, lt, 0.05)
    if name == "end":
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        d.rounded_rectangle((60, 960, W - 60, 1420), 48, fill=(255, 252, 245, 238), outline=(240, 170, 150), width=6)
        d.text((W / 2, 1045), "“なんで？”は、", font=font(58), fill=INK, anchor="mm")
        outlined(d, (W / 2, 1150), "次の“なんで？”を連れてくる。", font(64), (236, 92, 108), sw=8, anchor="mm")
        d.text((W / 2, 1258), "田中家の続きは平日20時", font=font(44, FONT_B), fill=INK, anchor="mm")
        d.rounded_rectangle((220, 1308, W - 220, 1393), 42, fill=(236, 120, 140, 245))
        d.text((W / 2, 1350), "フォローしてね", font=font(46), fill=(255, 255, 255), anchor="mm")
        paste(f, layer, 0, (1 - back_out(lt / 0.5)) * 80, min(1, lt / 0.3))
        sparkles(f, lt, 540, 1190, 480, 10, seed=7)
        if lt > dur - 0.4:
            f = Image.blend(f, Image.new("RGBA", (W, H), (255, 250, 240, 255)), ease((lt - dur + 0.4) / 0.4) * 0.5)
    for v, sp, sub, st, ln in sc["lines"]:
        if sub and st - 0.05 <= lt < st + ln + 0.05:
            im = sub_img(sp, sub)
            paste(f, im, 0, 1300 - im.height / 2, ease((lt - st + 0.05) / 0.15))
    if name not in ("phone1", "phone2", "end"):
        paste(f, small_logo(), 30, 300)
    return f


def main():
    scenes, vo, total = plan()
    for s in scenes:
        print(f"{s['name']:6s} {s['t0']:5.1f}s 長さ {s['dur']:.1f}s")
    print(f"合計 {total:.1f} 秒")
    mix = load_loop(AMBIENCE, total, 0.02) + music_bed(total, 0.05)
    voices = np.zeros_like(mix)
    duck = np.ones_like(mix)
    for s in scenes:
        for v, sp, sub, st, ln in s["lines"]:
            x = vo[v]
            j = int((s["t0"] + st) * SR)
            voices[j:j + len(x)] += x[: len(mix) - j]
            duck[j:j + len(x)] = 0.35
            if v in ("U1_ai", "U5_ai"):
                p = message_pop()
                k = int((s["t0"] + st - 0.15) * SR)
                mix[k:k + len(p)] += p[: len(mix) - k]
    duck = np.convolve(duck, np.ones(4800) / 4800, "same")
    mix = mix * duck + voices
    fade = int(SR * 0.6)
    mix[-fade:] *= np.linspace(1, 0, fade)
    mix /= max(1.0, np.abs(mix).max() / 0.95)
    wav = KIT / "_mix.wav"
    wavfile.write(wav, SR, (mix * 32767).astype(np.int16))

    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", str(wav), "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(OUT)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for s in scenes:
        if s["clip"]:
            src = clip_frames(s["clip"], s["cst"], s["dur"], blur=(s["name"] == "end"))
        else:
            src = clip_frames("ep01_C10", 2.0, s["dur"], blur=True)  # スマホ画面の後ろ
        for i, f in enumerate(src):
            proc.stdin.write(decorate(f, s, i / FPS).convert("RGB").tobytes())
    proc.stdin.close()
    proc.wait()
    wav.unlink()
    print("wrote", OUT)


if __name__ == "__main__":
    main()
