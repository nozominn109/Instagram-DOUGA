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
CLIP_AUDIO = {"C14"}  # Klingが作ったズームの効果音をそのまま使うカット
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
                         speaker=sp, sub=sub, t0=t, dur=dur, clip_audio=cid in CLIP_AUDIO))
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
    """字幕：箱なしの白い文字に、やわらかい影（参考リールの雰囲気）。"""
    fnt = font(60)
    lines = text.split("\n")
    lh = 84
    im = Image.new("RGBA", (W, lh * len(lines) + 60), (0, 0, 0, 0))
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ds, d = ImageDraw.Draw(sh), ImageDraw.Draw(im)
    for i, ln in enumerate(lines):
        y = 30 + lh * i + lh / 2
        ds.text((W / 2, y + 3), ln, font=fnt, fill=(40, 30, 30, 200), anchor="mm", stroke_width=7,
                stroke_fill=(40, 30, 30, 200))
        d.text((W / 2, y), ln, font=fnt, fill=(255, 255, 255, 255), anchor="mm", stroke_width=2,
               stroke_fill=(90, 70, 70, 255))
    sh = sh.filter(ImageFilter.GaussianBlur(6))
    sh.alpha_composite(im)
    return sh


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
    elif cid == "C14":
        pop_text(f, "じー……", 300, 520, 1.2, lt, 92, (70, 80, 120), rot=-3)
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
        k = ease((lt - seg["delay"] + 0.05) / 0.15)
        paste(f, im, 0, 1470 - im.height / 2 + (1 - k) * 12, k)
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


def load_loop(path, total, rms):
    """音素材を読み込み、音量をそろえて全体の長さまでループ（つなぎ目はクロスフェード）。"""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    x = np.frombuffer(raw, np.float32).astype(float)
    x *= rms / max(np.sqrt(np.mean(x ** 2)), 1e-9)
    n, cf = int(total * SR), int(SR * 1.5)
    out = np.zeros(n + len(x))
    pos, ramp = 0, np.linspace(0, 1, cf)
    while pos < n:
        y = x.copy()
        if pos:
            y[:cf] *= ramp
            out[pos:pos + cf] *= 1 - ramp
        out[pos:pos + len(y)] += y
        pos += len(x) - cf
    return out[:n]


def tap():
    """スマホをタップする小さな音。"""
    n = int(SR * 0.03)
    tt = np.arange(n) / SR
    return (np.sin(2 * np.pi * 2400 * tt) * 0.5 + np.random.default_rng(7).normal(0, 0.3, n)) * np.exp(-tt * 260) * 0.12


def message_pop():
    """メッセージが届く「ポコン」という音。"""
    out = np.zeros(int(SR * 0.32))
    out[:int(SR * 0.25)] += tone(880, 0.25) * 0.12
    out[int(SR * 0.07):int(SR * 0.07) + int(SR * 0.25)] += tone(1320, 0.25) * 0.1
    return out


AMBIENCE = ROOT / "assets" / "sounds" / "living_ambience.mp3"
MUSIC = ROOT / "assets" / "sounds" / "bgm.mp3"  # 置いてあれば小さく流す


def build_audio(segs, total, path):
    mix = load_loop(AMBIENCE, total, 0.024)
    if MUSIC.exists():
        mix += load_loop(MUSIC, total, 0.03)
    duck = np.ones_like(mix)
    voices = np.zeros_like(mix)
    def clip_audio(src, start, length, speed):
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(start), "-t", str(length * speed), "-i", str(src),
                              "-vn", "-af", f"atempo={speed}", "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                             capture_output=True, check=True).stdout
        return np.frombuffer(raw, np.float32).astype(float)

    kling = np.zeros_like(mix)
    for s in segs:
        if s["clip_audio"]:
            x = clip_audio(s["src"], s["start"], s["dur"], 1 / s["slow"])
            j = int(s["t0"] * SR)
            x = x[: max(0, min(len(mix) - j, int(s["dur"] * SR)))]
            fade = min(len(x), int(SR * 0.08))
            x[:fade] *= np.linspace(0, 1, fade)
            x[-fade:] *= np.linspace(1, 0, fade)
            kling[j:j + len(x)] += x
    c13 = next(s for s in segs if s["id"] == "C13")
    c14 = next(s for s in segs if s["id"] == "C14")
    x = clip_audio(c14["src"], 0, 2.6, 1 / c14["slow"]) * 0.7  # パパに寄るところにも蒼と同じズームの音
    x[-int(SR * 0.4):] *= np.linspace(1, 0, int(SR * 0.4))
    j = int(c13["t0"] * SR)
    kling[j:j + len(x)] += x[: len(mix) - j]

    for s in segs:
        if s["voice"] is None or s["clip_audio"]:
            continue
        j = int((s["t0"] + s["delay"]) * SR)
        v = s["voice"][: max(0, len(mix) - j)]
        voices[j:j + len(v)] += v
        duck[j:j + len(v)] = 0.5
    duck = np.convolve(duck, np.ones(4800) / 4800, "same")
    mix = mix * (0.5 + 0.5 * duck) + voices + kling * 0.85

    def add(x, t):
        j = int(t * SR)
        mix[j:j + len(x)] += x[: max(0, len(mix) - j)]

    at = {s["id"]: s["t0"] for s in segs}
    add(sfx_whoosh(), at["C02"])
    add(sfx_whoosh(), at["C04"] + 0.1)
    c05 = next(s for s in segs if s["id"] == "C05")
    add(sfx_chime(), c05["t0"] + c05["delay"] + len(c05["voice"]) / SR * 0.88)
    rng = np.random.default_rng(3)
    vlen = len(c05["voice"]) / SR
    tt = c05["t0"] + 0.2
    while tt < c05["t0"] + c05["delay"] + vlen / 1.12:
        add(tap(), tt)
        tt += rng.uniform(0.09, 0.2)
    c11 = next(s for s in segs if s["id"] == "C11")
    add(message_pop(), c11["t0"] + 0.15)
    add(message_pop(), c11["t0"] + c11["delay"])
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
