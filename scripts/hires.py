"""切り出したキャラ画像を EDSR(x4) で超解像し、アップでも粗くならないようにする。

モデル: https://raw.githubusercontent.com/Saafke/EDSR_Tensorflow/master/models/EDSR_x4.pb
（build/EDSR_x4.pb に置く。opencv-contrib-python-headless が必要）
"""
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "assets" / "characters"
OUT = ROOT / "assets" / "characters_hires"
MODEL = ROOT / "build" / "EDSR_x4.pb"


def main():
    sr = cv2.dnn_superres.DnnSuperResImpl_create()
    sr.readModel(str(MODEL))
    sr.setModel("edsr", 4)
    OUT.mkdir(parents=True, exist_ok=True)
    for path in sorted(SRC.glob("*.png")):
        a = np.array(Image.open(path).convert("RGBA"))
        up = cv2.cvtColor(sr.upsample(cv2.cvtColor(a[:, :, :3], cv2.COLOR_RGB2BGR)), cv2.COLOR_BGR2RGB)
        alpha = cv2.resize(a[:, :, 3], (up.shape[1], up.shape[0]), interpolation=cv2.INTER_CUBIC)
        Image.fromarray(np.dstack([up, alpha])).save(OUT / path.name, optimize=True)
        print(path.name, up.shape[1], up.shape[0])


if __name__ == "__main__":
    main()
