"""11/18（水）21:30「明日の準備チェックリスト」（約15秒）を仕上げる。

素材: output/chk1118/clips/（1_sigh, 2_prep, 3_papa）, voices/（C1_satoru, C2_aina）
使い方:
    python3 scripts/chk1118.py   # -> output/chk1118/chk1118.mp4
"""
import subprocess

import numpy as np
import scipy.io.wavfile as wavfile
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from assemble_ai import AMBIENCE, FPS, H, ROOT, SR, W, load_loop, music_bed, sub_img, message_pop, tap
from render import FONT_B, INK, PX0, PX1, PY0, PY1, back_out, ease, font, outlined, paste, phone_screen, sparkles
from short_ai_ok import small_logo, text_block
from short_yuhan import bubble

KIT = ROOT / "output" / "chk1118"
CLIPS, VOICES = KIT / "clips", KIT / "voices"
OUT = KIT / "chk1118.mp4"
VT = {"C1_satoru": 1.25, "C2_aina": 1.3}

FACE = {"sigh": (600, 800, 1.5), "wide": (540, 900, 1.12), "two": (560, 820, 1.35)}

ASK = "明日の持ち物、家族ごとのチェックリストにして"
CHECK = [("蒼", "体操服・部活のシューズ"), ("莉奈", "印鑑（プリント）・音読カード"), ("親", "7:30 ゴミ出し")]

# 場面: (名前, 動画, 動画の開始秒, 顔, [(声, 話す人, 字幕, 場面内の開始秒)], 最低の長さ)
SCENES = [
    ("open", "1_sigh", 0.5, "sigh", [], 2.4),
    ("ask", None, 0.0, None, [], 3.6),
    ("ring", "2_prep", 1.0, "wide", [], 2.6),
    ("papa", "3_papa", 0.8, "two", [("C1_satoru", "satoru", "…僕の名前、リストにない", 0.2),
                                    ("C2_aina", "aina", "パパは自分で書いて", 0.25)], 0.0),
    ("end", "3_papa", 3.6, "two", [], 2.3),
]


def voice(name):
    af = (f"silenceremove=start_periods=1:start_threshold=-45dB:stop_periods=-1:stop_duration=0.3:"
          f"stop_threshold=-45dB:stop_silence=0.2,atempo={VT[name]}")
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(VOICES / f"{name}.mp3"), "-af", af, "-ac", "1", "-ar",
                          str(SR), "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).astype(float)


def frames(clip, start, dur, face, blur=False):
    cx, cy, z = FACE[face]
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


def group_screen(f, lt):
    """家族のグループ（LINE風・実在ロゴなし）に、チェックリストが届く画面。"""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle((PX0 - 4, PY0 + 16, PX1 + 12, PY1 + 24), 80, fill=(60, 40, 30, 70))
    d.rounded_rectangle((PX0, PY0, PX1, PY1), 76, fill=(46, 52, 72, 255))
    d.rounded_rectangle((PX0 + 22, PY0 + 22, PX1 - 22, PY1 - 22), 58, fill=(222, 236, 244, 255))
    d.rounded_rectangle((W / 2 - 70, PY0 + 34, W / 2 + 70, PY0 + 64), 15, fill=(46, 52, 72, 255))
    d.rectangle((PX0 + 22, PY0 + 86, PX1 - 22, PY0 + 190), fill=(250, 250, 250, 255))
    d.text((W / 2, PY0 + 138), "田中家（家族グループ）", font=font(42, FONT_B), fill=INK, anchor="mm")
    y = PY0 + 240
    d.rounded_rectangle((PX0 + 60, y, PX1 - 140, y + 90), 34, fill=(255, 255, 255, 255))
    d.text((PX0 + 100, y + 45), "明日の持ち物チェック", font=font(40, FONT_B), fill=INK, anchor="lm")
    y += 120
    for i, (who, items) in enumerate(CHECK):
        k = ease((lt - 0.25 - i * 0.35) / 0.25)
        if k <= 0:
            continue
        box = Image.new("RGBA", (W, 190), (0, 0, 0, 0))
        bd = ImageDraw.Draw(box)
        bd.rounded_rectangle((PX0 + 60, 0, PX1 - 60, 170), 34, fill=(255, 255, 255, 255), outline=(150, 210, 190), width=4)
        bd.rounded_rectangle((PX0 + 90, 28, PX0 + 200, 84), 24, fill=(120, 214, 196, 255))
        bd.text((PX0 + 145, 56), who, font=font(34, FONT_B), fill=(255, 255, 255), anchor="mm")
        bd.text((PX0 + 100, 126), "□ " + items, font=font(38), fill=INK, anchor="lm")
        paste(layer, box, 0, y + (1 - k) * 30, k)
        y += 190
    f.alpha_composite(layer, (0, 170))
    d2 = ImageDraw.Draw(f)


def caption_note(f, lt, t0, text="全文はキャプションに。保存してね"):
    if lt < t0:
        return
    fnt = font(38, FONT_B)
    w = int(fnt.getlength(text)) + 70
    im = Image.new("RGBA", (w, 84), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, 83), 42, fill=(255, 250, 240, 240), outline=(74, 170, 150), width=4)
    d.text((w / 2, 42), text, font=fnt, fill=INK, anchor="mm")
    paste(f, im, W / 2 - w / 2, 1470, ease((lt - t0) / 0.2))


def decorate(f, sc, lt, vo):
    name = sc["name"]
    if name == "open":
        text_block(f, [("夜9時", 52, (120, 96, 84))], 370, lt)
        text_block(f, [("明日の朝も", 62, (90, 110, 170))], 440, lt)
        text_block(f, [("「体操服どこ！？」", 88, (236, 92, 108))], 520, lt)
        text_block(f, [("になる…？", 62, (90, 110, 170))], 640, lt)
    if name == "ask":
        if lt < 1.2:
            msgs = [("me", ASK, int(len(ASK) * min(1, lt / 0.6)), (), 0)]
            layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            phone_screen(layer, lt, msgs, "AIにお願い", (lt + 0.05) / 0.3)
            f.alpha_composite(layer, (0, 170))
            if lt > 0.2:
                im = sub_img("aina", "「明日の持ち物、\n家族ごとのチェックリストにして」")
                paste(f, im, 0, 1330 - im.height / 2, ease((lt - 0.2) / 0.15))
        else:
            group_screen(f, lt - 1.2)
            caption_note(f, lt, 1.6)
    if name == "ring":
        for i, t0 in enumerate((0.1, 0.7, 1.3)):
            if lt > t0:
                text_block(f, [("ピコン♪", 54, (74, 170, 150))], 370, lt, t0)
        if lt > 0.3:
            text_block(f, [("家族のスマホが次々に鳴る", 50, (120, 96, 84))], 1330, lt, 0.3)
    if name == "end":
        f.alpha_composite(f.filter(ImageFilter.GaussianBlur(10)))
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        d.rounded_rectangle((60, 1000, W - 60, 1400), 48, fill=(255, 252, 245, 238), outline=(240, 170, 150), width=6)
        d.text((W / 2, 1075), "明日の朝のバタバタは、", font=font(50), fill=INK, anchor="mm")
        outlined(d, (W / 2, 1170), "前の夜のリストで減らせる。", font(60), (236, 92, 108), sw=8, anchor="mm")
        d.text((W / 2, 1262), "田中家の続きは平日20時", font=font(40, FONT_B), fill=INK, anchor="mm")
        d.rounded_rectangle((220, 1300, W - 220, 1380), 40, fill=(236, 120, 140, 245))
        d.text((W / 2, 1340), "フォローしてね", font=font(44), fill=(255, 255, 255), anchor="mm")
        paste(f, layer, 0, (1 - back_out(lt / 0.4)) * 60, min(1, lt / 0.25))
        sparkles(f, lt, 540, 1190, 460, 8, seed=7)
    for v, sp, sub, st in sc["lines"]:
        ln = len(vo[v]) / SR
        if sub and st - 0.03 <= lt < st + max(ln, 0.6) + 0.1:
            im = sub_img(sp, sub)
            paste(f, im, 0, 1000 - im.height / 2, ease((lt - st + 0.03) / 0.1))
    if name not in ("ask", "end"):
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
        if s["name"] == "ask":
            for i in range(7):
                sfx(tap(), s["t0"] + 0.05 + i * 0.08)
            sfx(message_pop(), s["t0"] + 1.3)
        if s["name"] == "ring":
            for t0 in (0.1, 0.7, 1.3):
                sfx(message_pop(), s["t0"] + t0)
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
            src = frames(s["clip"], s["cst"], s["dur"], s["face"], blur=(s["name"] == "end"))
        else:
            src = frames("1_sigh", 2.0, s["dur"], "wide", blur=True)
        for i, f in enumerate(src):
            proc.stdin.write(decorate(f, s, i / FPS, vo).convert("RGB").tobytes())
    proc.stdin.close()
    proc.wait()
    wav.unlink()
    print("wrote", OUT)


if __name__ == "__main__":
    main()
