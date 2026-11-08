"""11/12（木）「宿題で使える、AIへのお願いの仕方」（約20秒）を仕上げる。

素材: output/short05_shukudai/clips/（1_drill, 2_write, 3_yatta）, voices/（H1〜H6）

使い方:
    python3 scripts/short_shukudai.py   # -> output/short05_shukudai/short05_shukudai.mp4
"""
import subprocess

import numpy as np
import scipy.io.wavfile as wavfile
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from assemble_ai import AMBIENCE, FPS, H, ROOT, SR, W, load_loop, music_bed, sub_img, message_pop, tap
from render import FONT_B, INK, back_out, ease, font, outlined, paste, phone_screen, sparkles
from short_ai_ok import small_logo, text_block
from short_yuhan import bubble

KIT = ROOT / "output" / "short05_shukudai"
CLIPS, VOICES = KIT / "clips", KIT / "voices"
OUT = KIT / "short05_shukudai.mp4"
TEMPO = 1.35

# 顔のアップ: (中心x, 中心y, 拡大率)  ※1080x1916 の座標
FACE = {"two": (560, 900, 1.15), "aina": (780, 760, 1.5), "rina_w": (440, 980, 1.4), "two3": (560, 880, 1.15),
        "aina3": (780, 780, 1.5)}

ASK = "答えは言わないで。ヒントを1つずつ出して"
AIH = "まず、3日間で全部で何ページ読んだかな？"
Q = ("3日間で読んだページは", "12・15・18ページ。", "1日平均何ページ？")

# 場面: (名前, 動画, 動画の開始秒, 顔, [(声, 話す人, 字幕, 場面内の開始秒)], 最低の長さ)
SCENES = [
    ("open", "1_drill", 0.0, "two", [("H1_rina", "rina", "AIに答え聞いちゃお", 0.4)], 0.0),
    ("wait", "1_drill", 2.4, "aina", [("H2_aina", "aina", "待って。聞き方を変えてみよう", 0.05)], 0.0),
    ("phone", None, 0.0, None, [("H3_ai", "ai", None, 1.0)], 0.0),
    ("write", "2_write", 0.0, "rina_w", [("H4_rina", "rina", "12＋15＋18で…45！\nそれを3日で分けると…15！", 0.2)], 0.0),
    ("yatta", "3_yatta", 0.3, "two3", [("H5_rina", "rina", "自分で解けた！", 0.05),
                                        ("H6_aina", "aina", "すごいじゃん！", 0.1)], 0.0),
    ("omoi", "3_yatta", 3.0, "aina3", [], 2.2),
    ("end", "3_yatta", 4.0, "two3", [], 3.0),
]


def voice(name):
    if name == "H4_rina":  # 「…」の間を残す（前後の無音だけ切る）
        af = (f"silenceremove=start_periods=1:start_threshold=-38dB:stop_periods=-1:stop_duration=0.35:"
              f"stop_threshold=-38dB:stop_silence=0.25,atempo={TEMPO}")
    else:
        af = (f"silenceremove=start_periods=1:start_threshold=-38dB:stop_periods=-1:stop_duration=0.2:"
              f"stop_threshold=-38dB:stop_silence=0.1,atempo={TEMPO}")
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(VOICES / f"{name}.mp3"), "-af", af, "-ac", "1", "-ar",
                          str(SR), "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).astype(float)


def frames(clip, start, dur, face, blur=False):
    cx, cy, z = FACE[face] if face else (540, 958, 1.0)
    cw, ch = int(1080 / z), int(1916 / z)
    x0 = min(max(int(cx - cw / 2), 0), 1080 - cw)
    y0 = min(max(int(cy - ch / 2), 0), 1916 - ch)
    vf = (f"trim=start={start},setpts=PTS-STARTPTS,fps={FPS},crop={cw}:{ch}:{x0}:{y0},"
          f"scale={W}:{H}:flags=lanczos,unsharp=5:5:0.5")
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


def question_card(f, lt, y=400):
    """ドリルの問題（編集で乗せる）。ノートの紙のようなカード。"""
    k = back_out(lt / 0.3)
    if k <= 0:
        return
    im = Image.new("RGBA", (820, 300), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((6, 10, 814, 296), 26, fill=(70, 50, 40, 50))
    d.rounded_rectangle((0, 0, 808, 286), 26, fill=(255, 253, 246, 245), outline=(120, 170, 220), width=5)
    for yy in (120, 182, 244):
        d.line((40, yy + 22, 768, yy + 22), fill=(200, 220, 240), width=2)
    d.rounded_rectangle((30, 22, 210, 78), 20, fill=(120, 170, 220))
    d.text((120, 50), "ドリル", font=font(36), fill=(255, 255, 255), anchor="mm")
    for i, s in enumerate(Q):
        d.text((404, 120 + 62 * i), s, font=font(46), fill=INK, anchor="mm")
    s = max(0.05, k)
    im2 = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.BILINEAR)
    paste(f, im2, W / 2 - im2.width / 2, y + (im.height - im2.height) / 2, min(1, lt / 0.2))


def decorate(f, sc, lt, vo):
    name = sc["name"]
    if name == "open":
        text_block(f, [("宿題、AIにやらせたら", 62, (90, 110, 170))], 400, lt)
        text_block(f, [("ズル？", 100, (236, 92, 108))], 490, lt, 0.15)
    if name == "phone":
        st = sc["lines"][0][3]
        ln = len(vo["H3_ai"]) / SR
        msgs = [("me", ASK, int(len(ASK) * min(1, lt / 0.9)), ("答えは言わないで", "ヒントを1つずつ"),
                 ease((lt - 0.9) / 0.4))]
        if lt >= st - 0.1:
            msgs.append(("ai", AIH, int(len(AIH) * min(1, (lt - st) / max(ln * 0.8, 0.1))), (), 0))
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        phone_screen(layer, lt, msgs, "聞き方を変えると…", (lt + 0.05) / 0.3)
        f.alpha_composite(layer, (0, 170))
    if name == "write":
        question_card(f, lt)
    if name == "omoi":
        if lt > 0.2:
            bubble(f, "答えより、“わかった！”の\nほうがうれしいね", lt - 0.2, 1330, (236, 92, 108))
    if name == "end":
        f.alpha_composite(f.filter(ImageFilter.GaussianBlur(10)))
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        d.rounded_rectangle((60, 1000, W - 60, 1400), 48, fill=(255, 252, 245, 238), outline=(240, 170, 150), width=6)
        d.text((W / 2, 1075), "AIに“答え”じゃなく", font=font(52), fill=INK, anchor="mm")
        outlined(d, (W / 2, 1170), "“ヒント”をもらう", font(70), (236, 92, 108), sw=8, anchor="mm")
        d.text((W / 2, 1262), "田中家の続きは平日20時", font=font(40, FONT_B), fill=INK, anchor="mm")
        d.rounded_rectangle((220, 1300, W - 220, 1380), 40, fill=(236, 120, 140, 245))
        d.text((W / 2, 1340), "フォローしてね", font=font(44), fill=(255, 255, 255), anchor="mm")
        paste(f, layer, 0, (1 - back_out(lt / 0.4)) * 60, min(1, lt / 0.25))
        sparkles(f, lt, 540, 1190, 460, 8, seed=7)
        if lt > 0.5:
            bubble(f, "AIへのお願いの文は\nキャプションに書いたよ！保存してね", lt - 0.5, 800, (74, 170, 150))
    for v, sp, sub, st in sc["lines"]:
        ln = len(vo[v]) / SR
        if sub and st - 0.03 <= lt < st + max(ln, 0.6) + 0.1:
            im = sub_img(sp, sub)
            paste(f, im, 0, 1320 - im.height / 2, ease((lt - st + 0.03) / 0.1))
    if name not in ("phone", "end"):
        paste(f, small_logo(), 30, 300)
    return f


def main():
    vo = {v: voice(v) for *_x, lines, _d in SCENES for v, *_y in lines}
    t, scenes = 0.0, []
    for name, clip, cst, face, lines, dur in SCENES:
        lt, timed = 0.0, []
        for v, sp, sub, st in lines:
            lt += st
            timed.append((v, sp, sub, lt))
            lt += len(vo[v]) / SR
        dur = max(dur, lt + 0.3)
        scenes.append(dict(name=name, clip=clip, cst=cst, face=face, lines=timed, dur=dur, t0=t))
        t += dur
    total = t
    print(f"合計 {total:.1f} 秒")
    mix = load_loop(AMBIENCE, total, 0.02) + music_bed(total, 0.06)
    voices = np.zeros_like(mix)
    duck = np.ones_like(mix)

    def sfx(x, at):
        j = int(at * SR)
        mix[j:j + len(x)] += x[: len(mix) - j]

    for s in scenes:
        for v, sp, sub, st in s["lines"]:
            x = vo[v]
            j = int((s["t0"] + st) * SR)
            voices[j:j + len(x)] += x[: len(mix) - j]
            duck[j:j + len(x)] = 0.4
        if s["name"] == "phone":
            for i in range(8):
                sfx(tap(), s["t0"] + 0.05 + i * 0.1)
            sfx(message_pop(), s["t0"] + s["lines"][0][3] - 0.1)
    duck = np.convolve(duck, np.ones(3000) / 3000, "same")
    mix = mix * duck + voices
    fade = int(SR * 0.5)
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
            src = frames(s["clip"], s["cst"], s["dur"], s["face"])
        else:
            src = frames("1_drill", 2.0, s["dur"], "two", blur=True)
        for i, f in enumerate(src):
            proc.stdin.write(decorate(f, s, i / FPS, vo).convert("RGB").tobytes())
    proc.stdin.close()
    proc.wait()
    wav.unlink()
    print("wrote", OUT)


if __name__ == "__main__":
    main()
