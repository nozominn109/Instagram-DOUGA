"""AI素材（Klingの動画＋ElevenLabsの声）をつなげて、第1話のリールを仕上げる。

カットごとの切り方・声の速さ・声の開始位置は output/ep01_kit/cut_notes.json を使う。
C05（ママのプロンプト）と C11（AIの返事）はスマホ画面を合成して作る。

使い方:
    python3 scripts/assemble_ai.py            # -> output/tanakake_ep01_dokusho_final.mp4
    python3 scripts/assemble_ai.py --stills   # 各カットの確認用の静止画だけ書き出す
"""
import json
import math
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np
import scipy.io.wavfile as wavfile
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from preview_cut import subtitle_png
from render import (FONT_B, INK, SR, back_out, ease, font, hearts, outlined, paste, phone_screen, pop_text,
                    sfx_chime, sfx_whoosh, sparkles, speed_lines, tone)
from story import PROMPT

ROOT = Path(__file__).resolve().parent.parent
KIT = ROOT / "output" / "ep01_kit"
CLIPS = KIT / "clips"
VOICES = KIT / "voices_eleven"
NOTES = json.loads((KIT / "cut_notes.json").read_text())
OUT = ROOT / "output" / "tanakake_ep01_dokusho_final.mp4"
W, H, FPS = 1080, 1920, 30
TAIL = 0.05  # 声が終わってから次のカットまでの間
SPEED = 1.12  # 全体のテンポ（声と動画を同じだけ速くして、口の動きとのズレを保つ）
EXTRA = {"C05": 1.12, "C11": 1.08}  # 説明が長いスマホ画面のカットはさらに少し速く

AI_TEXT = "はーい！初めまして、莉奈ちゃん。一緒に素敵な感想文を作ろうね！それじゃあ最初の質問です……"

# (カットID, 動画, 声ファイル, 話す人, 字幕)
CUTS = [
    ("C01", "C01", "C01_rina", "rina", "AIくーん、\n読書感想文ぜーんぶ書いて！"),
    ("C02", "C02", "C02_satoru", "satoru", "えぇぇ、AIに感想文を！？\nそんなズルはダメだぞー！"),
    ("C03", "C03", "C03_rina", "rina", "えー、いいじゃん！\nAIが書いてくれたらラクじゃん〜！"),
    ("C04", "C04", "C04_aina", "aina", "ダメダメ、丸投げはダメ！\nこうやってお願いするの。"),
    ("C05", None, "C05_aina", "aina", None),
    ("C06", "C06", "C06_rina", "rina", "ほんとだ、\nそれならズルくないじゃん！"),
    ("C07", "C07", "C07_aina", "aina", "こうすれば、一緒に楽しく考えて\n自分の言葉で書けるでしょ？"),
    ("C08a", "C08a", "C08a_rina", "rina", "うん、これなら\n自分でも書けそう！"),
    ("C09", "C09", "C09_aina", "aina", "そう、AIってね、向き合い方次第で\n莉奈の可能性を広げてくれる\n素敵な相棒になるんだよ"),
    ("C10", "C10", "C10_rina", "rina", "AI、質問して〜！"),
    ("C11", None, "C11_ai", "ai", None),
    ("C12", "C12", "C12_rina", "rina", "やばっ！すごい、\nこれなら楽しく書けそう！"),
    ("C13", "C13", "C13_satoru", "satoru", "なるほど……僕の企画書も、\nそうやって相棒にしてほしいな……"),
    ("C14", "C14", None, "sora", None),
    ("C15", "C15_C16", "C15_noa", "noa", "あーあー！"),
    ("C16", "C15_C16", "C16_chappy", "chappy", "ワン！"),
    ("END", "END", None, None, None),
]
DEFAULT = {"C01": {"tempo": 1.2, "delay": 0.1}, "C05": {"tempo": 1.2, "delay": 0.45},
           "C11": {"tempo": 1.2, "delay": 0.45}, "C12": {"tempo": 1.2, "delay": 0.05},
           "C14": {"trim": 4.0}, "END": {"trim": 5.0}}
TRIM_OVERRIDE = {"C14": 2.8, "END": 4.6}  # セリフのないカットは短めに


def probe(path):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                 str(path)], capture_output=True, text=True, check=True).stdout)


def load_voice(name, tempo):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(VOICES / f"{name}.mp3"), "-af", f"atempo={tempo}",
                          "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).astype(float)


def plan():
    """各カットの長さ・素材の切り方・声を決める。"""
    segs, t = [], 0.0
    for cid, clip, voice, sp, sub in CUTS:
        n = {**DEFAULT.get(cid, {}), **NOTES.get(cid, {})}
        if cid in TRIM_OVERRIDE:
            n["trim"] = TRIM_OVERRIDE[cid]
        sp_k = SPEED * EXTRA.get(cid, 1.0)
        tempo, delay = n.get("tempo", 1.0) * sp_k, n.get("delay", 0.1) / sp_k
        v = load_voice(voice, tempo) if voice else None
        src = CLIPS / f"{clip}.mp4" if clip else None
        start = n.get("start", 0.0)
        slow = n.get("slow", 1.0) / sp_k
        if src:
            end = n.get("trim", probe(src))
            vid_len = (end - start) * slow
        else:
            vid_len = 0.0
        need = delay + len(v) / SR + TAIL if v is not None else 0.0
        dur = max(vid_len, need)
        segs.append(dict(id=cid, src=src, start=start, slow=slow, vid_len=vid_len, voice=v, delay=delay,
                         speaker=sp, sub=sub, t0=t, dur=dur))
        t += dur
    return segs


def clip_frames(seg):
    """素材を 1080x1920 / 30fps にそろえて1コマずつ返す（足りないぶんは最後のコマで止める）。"""
    src = seg["src"]
    vf = (f"trim=start={seg['start']}:duration={seg['vid_len'] / seg['slow']},setpts={seg['slow']}*(PTS-STARTPTS),"
          f"fps={FPS},scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H}")
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(src), "-vf", vf, "-f", "rawvideo", "-pix_fmt", "rgb24",
                          "-"], stdout=subprocess.PIPE)
    n, last = W * H * 3, None
    for _ in range(round(seg["dur"] * FPS)):
        buf = p.stdout.read(n)
        if len(buf) == n:
            last = Image.frombytes("RGB", (W, H), buf)
        yield last.copy()
    p.stdout.close()
    p.wait()


def still(clip, t):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(t), "-i", str(CLIPS / f"{clip}.mp4"), "-frames:v", "1",
                          "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}", "-f", "rawvideo",
                          "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    return Image.frombytes("RGB", (W, H), raw)


@lru_cache(None)
def icon(name):
    """スマホ画面の横に出す丸いキャラの顔。"""
    clip, t, (cx, cy, r) = {"aina": ("C07", 0.3, (420, 630, 190)), "rina": ("C10", 3.0, (790, 770, 180))}[name]
    face = still(clip, t).crop((cx - r, cy - r, cx + r, cy + r)).resize((190, 190), Image.LANCZOS)
    mask = Image.new("L", (190, 190), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, 189, 189), fill=255)
    out = Image.new("RGBA", (202, 202), (0, 0, 0, 0))
    ImageDraw.Draw(out).ellipse((0, 0, 201, 201), fill=(255, 255, 255, 255))
    out.paste(face, (6, 6), mask)
    return out


@lru_cache(None)
def blurred_bg(clip, t):
    f = still(clip, t).filter(ImageFilter.GaussianBlur(14))
    return ImageEnhance.Brightness(f).enhance(0.85).convert("RGBA")


def phone_frame(seg, lt):
    voice_len = len(seg["voice"]) / SR
    p = min(max((lt - seg["delay"]) / voice_len, 0), 1)
    rk = (lt + 0.05) / 0.35
    if seg["id"] == "C05":
        f = blurred_bg("C04", 3.4).copy()
        shown = int(len(PROMPT) * min(1, p * 1.12))
        hl = ease((lt - seg["delay"] - voice_len * 0.88) / 0.6)
        phone_screen(f, lt, [("me", PROMPT, shown, ("優しいインタビュアー", "質問を3つ", "1個ずつ順番に"), hl)],
                     "丸投げNG → こうお願いする！", rk)
        paste(f, icon("aina"), 50, 1290)
        d = ImageDraw.Draw(f)
        d.rounded_rectangle((270, 1320, 1010, 1430), 40, fill=(255, 252, 245, 240), outline=(164, 132, 206), width=5)
        d.text((300, 1375), "役割 ＋ 目的 ＋ 1つずつ質問", font=font(44), fill=INK, anchor="lm")
        if hl > 0:
            sparkles(f, lt, 540, 900, 380, 8, seed=5)
    else:
        f = blurred_bg("C10", 3.0).copy()
        shown = int(len(AI_TEXT) * min(1, p * 1.05))
        phone_screen(f, lt, [("me", "AI、質問して〜！", 99, (), 0), ("ai", AI_TEXT, shown, (), 0)],
                     "AIがインタビュアーに！", rk)
        paste(f, icon("rina"), 40, 1250 + math.sin(lt * 8) * 6)
        pop_text(f, "わくわく", 330, 1270, 0.5, lt, 60, (240, 110, 150))
    return f


@lru_cache(None)
def sub_img(speaker, text):
    path = KIT / f"_sub_{speaker}.png"
    subtitle_png(speaker, text, path)
    im = Image.open(path).copy()
    path.unlink()
    return im


@lru_cache(None)
def hook_img():
    im = Image.new("RGBA", (W, 300), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    outlined(d, (W / 2, 95), "宿題をAIに", font(84), (90, 70, 60), sw=12, anchor="mm")
    outlined(d, (W / 2, 205), "丸投げ！？", font(118), (236, 92, 108), sw=14, anchor="mm")
    return im


@lru_cache(None)
def logo():
    """左上の小さなシリーズロゴ「AIは、相棒。」（箱なし・白ふち文字）。"""
    im = Image.new("RGBA", (560, 150), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    outlined(d, (12, 58), "AIは、", font(50), (120, 96, 84), sw=8, anchor="lm")
    x = 12 + font(50).getlength("AIは、")
    outlined(d, (x, 52), "相棒。", font(66), (240, 110, 150), sw=9, anchor="lm")
    x += font(66).getlength("相棒。") + 6
    for (cx, cy, r) in [(x + 8, 26, 13), (x + 30, 52, 8)]:
        d.polygon([(cx, cy - r), (cx + r * 0.3, cy - r * 0.3), (cx + r, cy), (cx + r * 0.3, cy + r * 0.3), (cx, cy + r),
                   (cx - r * 0.3, cy + r * 0.3), (cx - r, cy), (cx - r * 0.3, cy - r * 0.3)], fill=(255, 210, 80, 255))
    outlined(d, (16, 116), "〜田中家の「どう使う？」〜", font(30, FONT_B), (120, 96, 84), sw=6, anchor="lm")
    return im


@lru_cache(None)
def end_card():
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle((60, 1130, W - 60, 1560), 48, fill=(255, 252, 245, 238), outline=(240, 170, 150), width=6)
    d.text((W / 2, 1205), "AIは「丸投げ」じゃなく", font=font(60), fill=INK, anchor="mm")
    outlined(d, (W / 2, 1310), "「相棒」に。", font(104), (236, 92, 108), sw=8, anchor="mm")
    d.text((W / 2, 1425), "プロンプトは保存して", font=font(44, FONT_B), fill=INK, anchor="mm")
    d.text((W / 2, 1490), "親子で試してみてね！", font=font(44, FONT_B), fill=INK, anchor="mm")
    d.rounded_rectangle((180, 1650, W - 180, 1750), 50, fill=(236, 120, 140, 245))
    d.text((W / 2, 1700), "フォローで田中家の続きを見る", font=font(44), fill=(255, 255, 255), anchor="mm")
    return layer


def decorate(f, seg, lt):
    cid, dur = seg["id"], seg["dur"]
    vo = seg["voice"]
    vend = seg["delay"] + (len(vo) / SR if vo is not None else 0)
    if cid == "C01" and lt < 2.6:
        h = hook_img()
        k = max(back_out(lt / 0.35), 0.05)
        hs = h.resize((int(W * k), int(300 * k)), Image.BILINEAR) if k < 0.999 else h
        paste(f, hs, W / 2 - hs.width / 2, 230 + (300 - hs.height) / 2, 1 - ease((lt - 2.2) / 0.4))
    elif cid == "C02":
        pop_text(f, "えぇぇ！？", 760, 560, 0.1, lt, 96, (90, 110, 170), rot=8, dur=2.2)
    elif cid == "C04":
        pop_text(f, "丸投げは", 760, 330, 0.1, lt, 76, (150, 110, 200), rot=4)
        pop_text(f, "ダメ！", 830, 430, 0.3, lt, 104, (236, 92, 108), rot=4)
    elif cid == "C06":
        pop_text(f, "ほんとだ！", 820, 330, 0.3, lt, 80, (240, 110, 150), rot=-5)
    elif cid == "C09" and lt > vend * 0.62:
        sparkles(f, lt, 540, 800, 480, 14, seed=9)
        pop_text(f, "AIは相棒", 540, 330, vend * 0.62, lt, 96, (74, 170, 150))
    elif cid == "C10":
        pop_text(f, "質問して〜！", 560, 330, 0.3, lt, 80, (240, 110, 150), rot=-5)
    elif cid == "C12":
        speed_lines(f, lt, (255, 236, 200), 90)
        sparkles(f, lt, 540, 700, 460, 16, seed=4)
        pop_text(f, "やばっ！", 540, 330, 0.05, lt, 130, (240, 100, 140), rot=-5)
    elif cid == "C13":
        tint = Image.new("RGBA", (W, H), (110, 140, 200, int(55 * ease(lt / 0.5))))
        f.alpha_composite(tint)
        pop_text(f, "（遠い目）", 280, 1330, 1.0, lt, 64, (90, 110, 170))
    elif cid == "C14":
        pop_text(f, "じー……", 300, 520, 1.2, lt, 92, (70, 80, 120), rot=-3)
        if lt > 1.0:
            d = ImageDraw.Draw(f)
            d.rounded_rectangle((90, 1330, 520, 1410), 40, fill=(60, 70, 96, 220))
            d.text((305, 1370), "中1・反抗期の蒼", font=font(40), fill=(255, 255, 255), anchor="mm")
    elif cid == "C15":
        pop_text(f, "あーあー！", 540, 330, 0.3, lt, 100, (240, 120, 150), rot=-6)
        hearts(f, lt, 200, 880, 1300)
    elif cid == "C16":
        pop_text(f, "ワン！", 760, 380, 0.15, lt, 120, (200, 140, 70), rot=6)
        hearts(f, lt, 200, 880, 1300)
    elif cid == "END" and lt > 0.6:
        k = lt - 0.6
        paste(f, end_card(), 0, (1 - back_out(k / 0.5)) * 80, min(1, k / 0.3))
        sparkles(f, lt, 540, 1340, 500, 10, seed=12)

    if cid not in ("C05", "C11", "END"):
        paste(f, logo(), 28, 64)
    if seg["sub"] and seg["delay"] - 0.05 <= lt < vend + 0.1:
        im = sub_img(seg["speaker"], seg["sub"])
        k = back_out((lt - seg["delay"] + 0.05) / 0.22)
        s = 0.85 + 0.15 * k
        if s < 0.999:
            im = im.resize((int(W * s), int(H * s)), Image.BILINEAR)
        paste(f, im, W / 2 - im.width / 2, (H - im.height) / 2 + (1 - s) * 400, min(1, k + 0.2))
    if cid == "END" and lt > dur - 0.4:
        f = Image.blend(f, Image.new("RGBA", (W, H), (255, 250, 240, 255)), ease((lt - dur + 0.4) / 0.4) * 0.5)
    return f


def frames(seg):
    if seg["src"]:
        for i, base in enumerate(clip_frames(seg)):
            yield decorate(base.convert("RGBA"), seg, i / FPS)
    else:
        for i in range(round(seg["dur"] * FPS)):
            yield decorate(phone_frame(seg, i / FPS), seg, i / FPS)


def drum(kind):
    n = int(SR * (0.25 if kind != "hat" else 0.06))
    tt = np.arange(n) / SR
    rng = np.random.default_rng({"kick": 1, "clap": 2, "hat": 3}[kind])
    if kind == "kick":
        return np.sin(2 * np.pi * (50 + 90 * np.exp(-tt * 30)) * tt) * np.exp(-tt * 14) * 0.9
    if kind == "clap":
        x = rng.normal(0, 1, n)
        x = x - np.convolve(x, np.ones(6) / 6, "same")
        return x * np.exp(-tt * 22) * 0.35
    x = rng.normal(0, 1, n)
    return (x - np.convolve(x, np.ones(3) / 3, "same")) * np.exp(-tt * 70) * 0.18


def pop_bgm(total):
    """明るくはずむポップなBGM（BPM 124、C - G - Am - F）。"""
    out = np.zeros(int(SR * (total + 2)))
    beat = 60 / 124
    prog = [(261.6, 329.6, 392.0), (196.0, 246.9, 293.7), (220.0, 261.6, 329.6), (174.6, 220.0, 261.6)]
    roots = [130.8, 98.0, 110.0, 87.3]
    mel = [[784, 659, 784, 880, 784, 659, 587, 659], [587, 494, 587, 659, 587, 494, 440, 494],
           [659, 523, 659, 784, 880, 784, 659, 587], [523, 587, 659, 698, 659, 587, 523, 587]]

    def add(x, t, g=1.0):
        j = int(t * SR)
        if j < len(out):
            out[j:j + len(x)] += (x * g)[: len(out) - j]

    t, bar = 0.0, 0
    while t < total + 1:
        i = bar % 4
        intro = bar < 1
        for b in range(4):
            tb = t + b * beat
            if not intro:
                add(drum("kick"), tb, 0.55)
                if b in (1, 3):
                    add(drum("clap"), tb, 0.6)
            for h in range(2):
                add(drum("hat"), tb + h * beat / 2, 0.5 if h else 0.3)
            # ベース（8分）
            for h in range(2):
                add(tone(roots[i] * (2 if h else 1), beat * 0.45), tb + h * beat / 2, 0.16)
            # ウクレレ風の裏打ちコード
            for k, fq in enumerate(prog[i]):
                add(tone(fq * 2, 0.35), tb + beat / 2 + k * 0.012, 0.05)
        # グロッケン風メロディ（8分）
        if bar % 8 >= 2 or bar < 1:
            for k, fq in enumerate(mel[i]):
                add(tone(fq * 2, 0.5), t + k * beat / 2, 0.035)
                add(tone(fq * 4, 0.3), t + k * beat / 2, 0.012)
        t += beat * 4
        bar += 1
    return out[: int(SR * total)]


def build_audio(segs, total, path):
    mix = pop_bgm(total) * 0.6
    duck = np.ones_like(mix)
    voices = np.zeros_like(mix)
    for s in segs:
        if s["voice"] is None:
            continue
        j = int((s["t0"] + s["delay"]) * SR)
        v = s["voice"][: max(0, len(mix) - j)]
        voices[j:j + len(v)] += v
        duck[j:j + len(v)] = 0.5
    duck = np.convolve(duck, np.ones(4800) / 4800, "same")
    mix = mix * duck + voices

    def add(x, t):
        j = int(t * SR)
        mix[j:j + len(x)] += x[: max(0, len(mix) - j)]

    at = {s["id"]: s["t0"] for s in segs}
    add(sfx_whoosh(), at["C02"])
    add(sfx_whoosh(), at["C04"] + 0.1)
    c05 = next(s for s in segs if s["id"] == "C05")
    add(sfx_chime(), c05["t0"] + c05["delay"] + len(c05["voice"]) / SR * 0.88)
    c09 = next(s for s in segs if s["id"] == "C09")
    add(sfx_chime(), c09["t0"] + (c09["delay"] + len(c09["voice"]) / SR) * 0.62)
    add(sfx_chime(), at["C12"])
    add(sfx_chime(), at["END"] + 0.6)
    fade = int(SR * 0.6)
    mix[-fade:] *= np.linspace(1, 0, fade)
    mix /= max(1.0, np.abs(mix).max() / 0.95)
    wavfile.write(path, SR, (mix * 32767).astype(np.int16))


def main():
    segs = plan()
    total = sum(s["dur"] for s in segs)
    for s in segs:
        print(f"{s['id']:5s} {s['t0']:6.2f}s  長さ {s['dur']:.2f}s")
    print(f"合計 {total:.1f} 秒")
    if "--stills" in sys.argv:
        for s in segs:
            g = frames(s)
            for i, f in enumerate(g):
                if i == round(min(s["dur"] * 0.6, s["dur"] - 0.1) * FPS):
                    f.convert("RGB").resize((360, 640)).save(KIT / f"_still_{s['id']}.png")
                    break
        return
    wav = KIT / "_mix.wav"
    build_audio(segs, total, wav)
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", str(wav), "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(OUT)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for s in segs:
        for f in frames(s):
            proc.stdin.write(f.convert("RGB").tobytes())
    proc.stdin.close()
    proc.wait()
    wav.unlink()
    print("wrote", OUT)


if __name__ == "__main__":
    main()
