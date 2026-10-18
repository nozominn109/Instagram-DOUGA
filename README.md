# 田中家のAIじかん — Instagramリール制作

親子 × AI × Z世代 のアカウント向け、田中家のアニメーションリール。

## 第1話「読書感想文編」

- 完成動画: [`output/tanakake_ep01_dokusho.mp4`](output/tanakake_ep01_dokusho.mp4)
  （1080×1920 / 30fps / 約53秒 / H.264 + AAC、セリフ音声・BGM・効果音・字幕入り）

### 構成

| 秒 | シーン |
|---|---|
| 0–8 | フック「宿題をAIに丸投げ！？」→ 莉奈「AIくーん…」→ パパがあわてて登場 |
| 8–11 | ママ登場、スマホをスッと取り上げ「丸投げはダメ！」 |
| 11–20 | スマホ画面アップ。プロンプトが入力されていき、要点（優しいインタビュアー／質問を3つ／1個ずつ順番に）にマーカー |
| 20–35 | ママと莉奈の会話。「AIは相棒」でキラキラ演出 |
| 35–40 | AIくんの返信がスマホに届く |
| 40–47 | 莉奈「やばっ！」→ パパ遠い目（企画書）→ 反抗期の蒼「じー……」 |
| 47–50 | 希亜「あーあー！」チャッピー「ワン！」 |
| 50–53 | エンドカード「AIは『丸投げ』じゃなく『相棒』に。」＋フォロー誘導 |

### 投稿キャプション案

```
宿題、AIに丸投げしてない…？😳

AIに「全部書いて」はNG🙅‍♀️
でも「質問して」ってお願いすれば
子どもが“自分の言葉”で書ける相棒に✨

📌 今日のプロンプト（保存して使ってね）
「あなたは小学5年生の〇〇の感想を引き出す優しいインタビュアーです。
【本のタイトル】の読書感想文が書けるよう、感想を引き出す質問を3つ、
必ず1個ずつ順番に質問して！」

AIは「使わせる・使わせない」じゃなく「どう使うか」。
田中家と一緒に、親子でAIとの付き合い方を学ぼう👨‍👩‍👧‍👦

#AI子育て #親子の会話 #読書感想文 #夏休みの宿題 #ChatGPT活用 #思春期の子育て #小学生ママ #AI教育 #田中家のAIじかん
```

## 作り直し方

```bash
pip install pyopenjtalk-plus numpy scipy pillow   # ffmpeg も必要
python3 scripts/cutout.py     # キャラシートから透過PNGを切り出し
python3 scripts/voices.py     # セリフ音声(オフラインTTS)とタイムライン生成
python3 scripts/background.py # リビング背景を描画
python3 scripts/render.py     # output/ にMP4を書き出し
python3 scripts/render.py --stills 5 20   # 指定秒の静止画だけ確認
```

- 台本・話者ごとの声/速さ: `scripts/story.py`
- ショット構成・演出: `scripts/render.py` の `shot_*` 関数
- キャラ画像: `assets/characters_sheet.webp`（3×2のシート）

## クレジット

- 音声合成: Open JTalk / HTS Engine（pyopenjtalk-plus）
  - パパ: HTS voice nitech_jp_atr503_m001（CC BY 3.0, 名古屋工業大学）
  - ママ・希亜: HTS voice "Mei"（CC BY 3.0, 名古屋工業大学）
  - 莉奈・AIくん・チャッピー: HTS voice tohoku-f01（CC BY 4.0, 東北大学 伊藤・能勢研究室）
- フォント: M PLUS Rounded 1c（SIL Open Font License 1.1）
- BGM・効果音・背景: スクリプトで生成
