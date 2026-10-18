"""動画AIで作ったカット1本に、別に作った声（ElevenLabsなど）と字幕を重ねて確認用の動画を作る。

例:
    python3 scripts/preview_cut.py output/ep01_kit/clips/C08.mp4 output/ep01_kit/voices_eleven/C08_rina.mp3 \
        rina "やばっ！すごい、\\nこれなら楽しく書けそう！" output/ep01_kit/preview_C08.mp4 --tempo 1.1 --delay 0.1
"""
import argparse
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

from render import COLORS, INK, NAMES, font, wrap

W, H = 1080, 1920


def subtitle_png(speaker, text, path):
    fnt = font(54)
    lines = wrap(text.replace("\\n", "\n"), fnt, 900)
    lh = 74
    bw, bh = 980, 60 + lh * len(lines)
    sub = Image.new("RGBA", (bw, bh + 46), (0, 0, 0, 0))
    d = ImageDraw.Draw(sub)
    d.rounded_rectangle((6, 52, bw - 6, bh + 40), 36, fill=(120, 90, 70, 60))
    d.rounded_rectangle((0, 40, bw - 8, bh + 32), 36, fill=(255, 252, 245, 245), outline=COLORS[speaker], width=6)
    nf = font(36)
    name = NAMES[speaker]
    nw = nf.getlength(name) + 48
    d.rounded_rectangle((34, 8, 34 + nw, 64), 28, fill=COLORS[speaker])
    d.text((34 + nw / 2, 36), name, font=nf, fill=(255, 255, 255), anchor="mm")
    for i, s in enumerate(lines):
        d.text((bw / 2 - 4, 76 + i * lh + lh / 2), s, font=fnt, fill=INK, anchor="mm")
    frame = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    frame.alpha_composite(sub, ((W - bw) // 2, 1500))
    frame.save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("clip")
    ap.add_argument("voice")
    ap.add_argument("speaker")
    ap.add_argument("text")
    ap.add_argument("out")
    ap.add_argument("--tempo", type=float, default=1.0, help="声の速さ（高さは変えない）")
    ap.add_argument("--delay", type=float, default=0.0, help="声を始める秒")
    a = ap.parse_args()
    png = Path(a.out).with_suffix(".sub.png")
    subtitle_png(a.speaker, a.text, png)
    ms = int(a.delay * 1000)
    dur = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", a.clip],
                         capture_output=True, text=True, check=True).stdout.strip()
    fc = (f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps=30[v];"
          f"[v][2:v]overlay=0:0:shortest=1[vo];"
          f"[1:a]atempo={a.tempo},aformat=channel_layouts=stereo,adelay={ms}|{ms},apad[ao]")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", a.clip, "-i", a.voice, "-loop", "1", "-i", str(png),
                    "-filter_complex", fc, "-map", "[vo]", "-map", "[ao]", "-t", dur,
                    "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                    "-movflags", "+faststart", a.out], check=True)
    png.unlink()
    print("wrote", a.out)


if __name__ == "__main__":
    main()
