"""時短AI①「今日のごはん何？」（約15秒）を仕上げる。

食卓の動画1本から、1人ずつの顔をアップにしてテンポよく切りかえる。
素材: output/jitan01_gohan/clips/1_table.mp4（全員）, 2_point.mp4（全員で指さし・あれば）, voices/

使い方:
    python3 scripts/jitan_gohan.py   # -> output/jitan01_gohan/jitan01_gohan.mp4
"""
import subprocess

import numpy as np
import scipy.io.wavfile as wavfile
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from assemble_ai import AMBIENCE, FPS, H, ROOT, SR, W, load_loop, music_bed, sub_img, message_pop
from render import FONT_B, INK, back_out, ease, font, outlined, paste, phone_screen, sparkles
from short_ai_ok import small_logo, text_block

KIT = ROOT / "output" / "jitan01_gohan"
CLIPS, VOICES = KIT / "clips", KIT / "voices"
OUT = KIT / "jitan01_gohan.mp4"
TEMPO = 1.3
POINT = "2_point" if (CLIPS / "2_point.mp4").exists() else "1_table"

# 顔のアップ: (中心x, 中心y, 拡大率)  ※1_table.mp4（1080x1916）の座標
FACE = {"wide": (540, 958, 1.0), "sora": (420, 760, 2.3), "rina": (640, 780, 2.3), "satoru": (190, 760, 2.3),
        "aina": (860, 520, 2.0), "chappy": (530, 1390, 2.4), "point_wide": (540, 900, 1.15),
        "satoru_p": (190, 760, 2.0), "aina_p": (860, 560, 1.8)}

# 場面: (名前, 動画, 顔, [(声, 話す人, 字幕, 場面内の開始秒)], 長さ)
SCENES = [
    ("open", "1_table", "wide", [], 1.6),
    ("sora", "1_table", "sora", [("G1_sora", "sora", "肉！", 0.05)], 0.8),
    ("rina", "1_table", "rina", [("G2_rina", "rina", "パスタ！", 0.05)], 0.95),
    ("satoru", "1_table", "satoru", [("G3_satoru", "satoru", "…なんでもいい", 0.05)], 1.05),
    ("aina", "1_table", "aina", [("G4_aina", "aina", "それがいちばん困るの！", 0.05)], 1.9),
    ("wan", "1_table", "chappy", [("C16_chappy", "chappy", "ワン！", 0.0)], 0.8),
    ("phone", None, None, [], 2.6),
    ("point", POINT, "point_wide", [("G5_rina", "rina", "これ！", 0.15), ("G6_sora", "sora", None, 0.2)], 1.5),
    ("dish", POINT, "satoru_p", [("G7_satoru", "satoru", "…で、俺は何すればいい？", 0.05)], 2.15),
    ("dish2", POINT, "aina_p", [("G8_aina", "aina", "お皿洗い", 0.05)], 1.5),
    ("end", POINT, "point_wide", [], 2.0),
]
ASK = "冷蔵庫に鶏肉・キャベツ・パスタ。家族の希望は「肉」「パスタ」「なんでもいい」。15分で作れる夕飯を3つ"
MENU = "①ガッツリ鶏の照り焼き丼\n②キャベツと鶏のペペロンチーノ\n③さっぱり蒸し鶏サラダ"


def voice(name, tempo=TEMPO):
    path = VOICES / f"{name}.mp3"
    if not path.exists():
        path = ROOT / "output" / "ep01_kit" / "voices_eleven" / f"{name}.mp3"
    af = f"silenceremove=start_periods=1:start_threshold=-38dB,atempo={tempo}"
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-af", af, "-ac", "1", "-ar", str(SR), "-f",
                          "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).astype(float)


def frames(clip, start, dur, face, blur=False):
    cx, cy, z = FACE[face] if face else (540, 958, 1.0)
    cw, ch = int(1080 / z), int(1916 / z)
    x0 = min(max(int(cx - cw / 2), 0), 1080 - cw)
    y0 = min(max(int(cy - ch / 2), 0), 1916 - ch)
    vf = (f"trim=start={start},setpts=PTS-STARTPTS,fps={FPS},crop={cw}:{ch}:{x0}:{y0},"
          f"scale={W}:{H}:flags=lanczos")
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


def decorate(f, sc, lt, vo):
    name, dur = sc["name"], sc["dur"]
    if name == "open":
        text_block(f, [("毎日の", 60, (120, 96, 84)), ("「今日のごはん何？」", 80, (236, 92, 108)),
                       ("問題…", 60, (120, 96, 84))], 1000, lt)
    if name == "phone":
        k = min(1, max(0, lt - 0.7) / 1.2)
        msgs = [("me", ASK, 99, (), 0)]
        if lt > 0.6:
            msgs.append(("ai", MENU.replace("\n", ""), int(len(MENU) * k), (), 0))
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        phone_screen(layer, lt, msgs, "AIに3案出してもらう", (lt + 0.05) / 0.3)
        f.alpha_composite(layer, (0, 170))
    if name == "point":
        text_block(f, [("決めるのは家族！", 74, (74, 170, 150))], 1060, lt, 0.1)
    if name == "end":
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        d.rounded_rectangle((60, 1000, W - 60, 1400), 48, fill=(255, 252, 245, 238), outline=(240, 170, 150), width=6)
        d.text((W / 2, 1075), "考える手間はAIに。", font=font(56), fill=INK, anchor="mm")
        outlined(d, (W / 2, 1170), "決めるのは家族。", font(76), (236, 92, 108), sw=8, anchor="mm")
        d.text((W / 2, 1262), "田中家の続きは平日20時", font=font(40, FONT_B), fill=INK, anchor="mm")
        d.rounded_rectangle((220, 1300, W - 220, 1380), 40, fill=(236, 120, 140, 245))
        d.text((W / 2, 1340), "フォローしてね", font=font(44), fill=(255, 255, 255), anchor="mm")
        paste(f, layer, 0, (1 - back_out(lt / 0.4)) * 60, min(1, lt / 0.25))
        sparkles(f, lt, 540, 1190, 460, 8, seed=7)
    for v, sp, sub, st in sc["lines"]:
        ln = len(vo[v]) / SR
        if sub and st - 0.03 <= lt < st + max(ln, 0.55) + 0.1:
            im = sub_img(sp, sub)
            paste(f, im, 0, 1300 - im.height / 2, ease((lt - st + 0.03) / 0.1))
    if name not in ("phone", "end"):
        paste(f, small_logo(), 30, 300)
    return f


def main():
    vo = {v: voice(v, 1.0 if v == "C16_chappy" else TEMPO) for *_x, lines, _d in SCENES for v, *_y in lines}
    t, scenes, clip_t = 0.0, [], {}
    for name, clip, face, lines, dur in SCENES:
        start = clip_t.get(clip, 0.0)
        scenes.append(dict(name=name, clip=clip, face=face, lines=lines, dur=dur, t0=t, start=start % 4.5))
        if clip:
            clip_t[clip] = start + dur
        t += dur
    total = t
    print(f"合計 {total:.1f} 秒")
    mix = load_loop(AMBIENCE, total, 0.02) + music_bed(total, 0.06)
    voices = np.zeros_like(mix)
    duck = np.ones_like(mix)
    for s in scenes:
        for v, sp, sub, st in s["lines"]:
            x = vo[v] * (0.6 if v == "C16_chappy" else 1.0)
            j = int((s["t0"] + st) * SR)
            voices[j:j + len(x)] += x[: len(mix) - j]
            duck[j:j + len(x)] = 0.4
        if s["name"] == "phone":
            p = message_pop()
            k = int((s["t0"] + 0.6) * SR)
            mix[k:k + len(p)] += p
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
            src = frames(s["clip"], s["start"], s["dur"], s["face"], blur=(s["name"] == "end"))
        else:
            src = frames("1_table", 2.0, s["dur"], "wide", blur=True)
        for i, f in enumerate(src):
            proc.stdin.write(decorate(f, s, i / FPS, vo).convert("RGB").tobytes())
    proc.stdin.close()
    proc.wait()
    wav.unlink()
    print("wrote", OUT)


if __name__ == "__main__":
    main()
