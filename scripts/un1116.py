"""11/16（月）20:00「質問3回、返事は『うん』3回」（約15秒・親テーマの再現性テスト）を仕上げる。

素材: output/un1116/clips/（1_table, 2_phone, 3_hatto）, voices/（U1〜U7）
使い方:
    python3 scripts/un1116.py   # -> output/un1116/un1116.mp4
"""
import subprocess

import numpy as np
import scipy.io.wavfile as wavfile
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from assemble_ai import AMBIENCE, FPS, H, ROOT, SR, W, load_loop, music_bed, sub_img, message_pop, tap
from render import FONT_B, INK, back_out, ease, font, outlined, paste, phone_screen, sparkles
from short_ai_ok import small_logo, text_block

KIT = ROOT / "output" / "un1116"
CLIPS, VOICES = KIT / "clips", KIT / "voices"
OUT = KIT / "un1116.mp4"

# 声ごとの（ファイル, 速さ）。蒼の「うん」は3回、少しずつ速さを変える
VOICE = {"u1": ("U1_aina", 1.6), "u2": ("U2_aina", 1.6), "u3": ("U3_aina", 1.6),
         "s1": ("U5_sora", 1.3), "s2": ("U5_sora", 1.4), "s3": ("U5_sora", 1.2),
         "u4": ("U4_aina", 1.4), "u6": ("U6_satoru", 1.3), "u7": ("U7_ai", 1.35)}

FACE = {"wide": (540, 900, 1.12), "q": (560, 900, 1.2), "aina": (760, 780, 1.5)}

ASK = "どうすれば話してくれる？"
AIQ = "今日、息子さんが笑った瞬間、ありましたか？"

# 場面: (名前, 動画, 動画の開始秒, 顔, [(声キー, 話す人, 字幕, 場面内の開始秒)], 最低の長さ)
SCENES = [
    ("q1", "1_table", 0.0, "q", [("u1", "aina", "学校どう？", 0.05), ("s1", "sora", "うん", 0.05)], 0.0),
    ("q2", "1_table", 1.2, "q", [("u2", "aina", "部活は？", 0.03), ("s2", "sora", "うん", 0.05)], 0.0),
    ("q3", "1_table", 2.2, "q", [("u3", "aina", "宿題は？", 0.03), ("s3", "sora", "うん", 0.05)], 0.0),
    ("papa", "1_table", 3.2, "wide", [("u6", "satoru", "うん", 0.1), ("u4", "aina", "パパまで！", 0.05)], 0.0),
    ("ask", "2_phone", 0.5, "wide", [], 2.0),
    ("ai", "2_phone", 3.3, "wide", [("u7", "ai", None, 0.4)], 0.0),
    ("hatto", "3_hatto", 1.5, "aina", [], 1.5),
    ("end", "3_hatto", 3.5, "wide", [], 2.0),
]


def voice(key):
    name, tempo = VOICE[key]
    af = (f"silenceremove=start_periods=1:start_threshold=-45dB:stop_periods=-1:stop_duration=0.3:"
          f"stop_threshold=-45dB:stop_silence=0.2,atempo={tempo}")
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


def decorate(f, sc, lt, vo, gt):
    name = sc["name"]
    if name == "q1" or (gt < 3.2 and name in ("q2", "q3")):
        # タイトル＋フックは0秒目から、最初の約3秒間出しつづける
        text_block(f, [("会話が「うん」だけになった日", 46, (120, 96, 84))], 370, 9, instant=True)
        text_block(f, [("質問3回、", 70, (90, 110, 170))], 440, 9, instant=True)
        text_block(f, [("返事は「うん」3回。", 78, (236, 92, 108))], 530, 9, instant=True)
        text_block(f, [("なんで？", 70, (90, 110, 170))], 625, 9, instant=True)
    if name == "ask":
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        msgs = [("me", ASK, int(len(ASK) * min(1, lt / 0.9)), (), 0)]
        phone_screen(layer, lt, msgs, "こっそりAIに相談", (lt + 0.05) / 0.3)
        f.alpha_composite(layer, (0, 170))
        caption_note(f, lt, 1.0)
    if name == "ai":
        st = sc["lines"][0][3]
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        msgs = [("me", ASK, 99, (), 0)]
        if lt >= st - 0.1:
            ln = len(vo["u7"]) / SR
            msgs.append(("ai", AIQ, int(len(AIQ) * min(1, (lt - st) / max(ln * 0.8, 0.1))), (), 0))
        phone_screen(layer, lt, msgs, "こっそりAIに相談", 1.0)
        f.alpha_composite(layer, (0, 170))
        if lt >= st:  # 大きな字幕（長めに止める）
            im = sub_img("ai", "今日、息子さんが\n笑った瞬間、\nありましたか？")
            paste(f, im, 0, 1330 - im.height / 2, ease((lt - st) / 0.12))
    if name == "hatto":
        text_block(f, [("ハッ…", 84, (150, 110, 200))], 1500, lt, 0.1)
    if name == "end":
        f.alpha_composite(f.filter(ImageFilter.GaussianBlur(10)))
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        d.rounded_rectangle((60, 1000, W - 60, 1400), 48, fill=(255, 252, 245, 238), outline=(240, 170, 150), width=6)
        d.text((W / 2, 1075), "「うん」だけの日にも、", font=font(50), fill=INK, anchor="mm")
        outlined(d, (W / 2, 1170), "きっかけはある。", font(66), (236, 92, 108), sw=8, anchor="mm")
        d.text((W / 2, 1262), "田中家の続きは平日20時", font=font(40, FONT_B), fill=INK, anchor="mm")
        d.rounded_rectangle((220, 1300, W - 220, 1380), 40, fill=(236, 120, 140, 245))
        d.text((W / 2, 1340), "フォローしてね", font=font(44), fill=(255, 255, 255), anchor="mm")
        paste(f, layer, 0, (1 - back_out(lt / 0.4)) * 60, min(1, lt / 0.25))
        sparkles(f, lt, 540, 1190, 460, 8, seed=7)
    for v, sp, sub, st in sc["lines"]:
        ln = len(vo[v]) / SR
        if sub and st - 0.03 <= lt < st + max(ln, 0.5) + 0.1:
            im = sub_img(sp, sub)
            paste(f, im, 0, 1330 - im.height / 2, ease((lt - st + 0.03) / 0.1))
    if name not in ("ask", "ai", "end"):
        paste(f, small_logo(), 30, 300)
    return f


def main():
    vo = {k: voice(k) for k in VOICE}
    t, scenes = 0.0, []
    for name, clip, cst, face, lines, dur in SCENES:
        lt, timed = 0.0, []
        for v, sp, sub, st in lines:
            lt += st
            timed.append((v, sp, sub, lt))
            lt += len(vo[v]) / SR
        if name == "ai":
            dur = lt + 1.1  # AIの聞き返しは長めに止める
        dur = max(dur, lt + 0.15)
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
            for i in range(8):
                sfx(tap(), s["t0"] + 0.05 + i * 0.09)
        if s["name"] == "ai":
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
    gt = 0.0
    for s in scenes:
        src = frames(s["clip"], s["cst"], s["dur"], s["face"], blur=(s["name"] in ("ask", "ai", "end")))
        for i, f in enumerate(src):
            proc.stdin.write(decorate(f, s, i / FPS, vo, s["t0"] + i / FPS).convert("RGB").tobytes())
    proc.stdin.close()
    proc.wait()
    wav.unlink()
    print("wrote", OUT)


if __name__ == "__main__":
    main()
