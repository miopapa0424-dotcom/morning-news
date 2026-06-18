# 女性の声の「自分専用ニュース番組」— 構築手順（追加コスト ¥0・履歴フラット版）

## 仕組み
```
[既存] ニュース収集 → 要約テキスト
            │  ← ここに繋ぐ
            ▼
generate_podcast.py
   ├ 要約を読み上げ用に整形（URL・記号を除去）
   ├ edge-tts で女性ニューラル音声の mp3 を生成（無料・APIキー不要）
   ├ public/ 内の feed.xml を更新、古い回は自動間引き（KEEP_N=7）
   └ public/ を gh-pages ブランチへ force-push（履歴は常に1コミット＝肥大しない）
            ▼
GitHub Pages が無料配信 → ポッドキャストアプリが夜間に自動DL
            ▼
朝、ポケットでバックグラウンド再生（無料）
```
すべて無料。費用が乗るのは「もっと良い声がほしい」と思って有料TTSに替えるときだけ。

---

## リポジトリ構成（ローカル）
```
morning-news/
├ generate_podcast.py     ← 本体
└ public/                 ← ビルド成果物＝状態の保管庫（ローカルに永続。ここが真実）
   ├ cover.jpg            ← カバー画像（同梱。差し替え可）
   ├ feed.xml            （自動生成）
   ├ episodes.json       （自動生成。エピソード台帳）
   └ episodes/           （自動生成。直近7本のmp3）
```
`public/` を毎回 gh-pages ブランチへ force-push するため、リポジトリ履歴は常に1コミットに保たれる（容量が増え続けない）。状態はローカルの `public/` が保持する。

---

## 一度だけやる準備

### A. GitHub 側（人間が画面で行う作業）
1. GitHub アカウントを作成（無料）。
2. **公開（public）リポジトリ**を新規作成。名前は例: `morning-news`。
   - ※ GitHub Pages を無料で使うにはリポジトリが public である必要がある。中身はニュース要約の音声なので実害は小さいが、**URLを知る人は誰でも聴ける**点だけ理解しておく（→ 末尾「プライバシー」）。
3. ローカルにクローンし、`generate_podcast.py` と `public/cover.jpg` を配置。
4. **初回だけ手動で gh-pages を作って Pages を有効化**：
   ```bash
   pip install edge-tts mutagen ghp-import --break-system-packages
   echo "セットアップのテストです。" | python generate_podcast.py   # public/ 生成＆gh-pagesへpush
   ```
   その後 **Settings → Pages → Source: "Deploy from a branch" → Branch: `gh-pages` / `/ (root)` → Save**。
   公開URLは `https://ユーザー名.github.io/morning-news/`。

### B. Mac 側（Code に任せられる作業）
5. `generate_podcast.py` 冒頭の **設定ブロック**を編集：
   - `BASE_URL` … `https://ユーザー名.github.io/morning-news`（末尾スラッシュ無し）
   - `VOICE` … 下の「声の選択肢」から（既定は女性の Nanami）
   - `PODCAST_TITLE` / `PODCAST_AUTHOR` などお好みで
6. `git push`（ghp-import が内部で実行）が無人で通るよう認証を設定（SSHキー、または Personal Access Token の credential helper）。
7. 動作確認：上記4のテストコマンドで `public/episodes/日付.mp3` と `public/feed.xml` ができ、gh-pages へ push されればOK。ブラウザで `…/feed.xml` が開ければ成功。

### C. 聴く側（人間がスマホで一度だけ）
8. ポッドキャストアプリで「URLで購読 / Add by URL」に
   `https://ユーザー名.github.io/morning-news/feed.xml` を登録。
   - **Pocket Casts / Overcast** … URL購読が分かりやすい（おすすめ）。
   - **Apple Podcast** … ライブラリ画面のメニューから「URLで番組を追加」。
   - 「新着エピソードを自動ダウンロード」をオンにしておくと、朝には端末に落ちている。

---

## 既存の4時処理への組み込み
「収集→要約→Gmail送信」処理の**最後**に、要約テキストを渡して1行呼ぶだけ：
```bash
python /path/to/generate_podcast.py /path/to/today_summary.txt
# または
cat today_summary.txt | python /path/to/generate_podcast.py
```
Gmail送信はそのまま残してOK（メールでも読める／音声でも聴ける二刀流）。
順番は「要約確定 → メール送信 → ポッドキャスト生成」が安全。

---

## 声の選択肢（女性・無料ニューラル音声）
`generate_podcast.py` の `VOICE` に設定。すべて edge-tts の日本語女性ボイス：

| VOICE 値 | 印象 |
|---|---|
| `ja-JP-NanamiNeural` | 標準的で聞きやすい（既定・おすすめ） |
| `ja-JP-AoiNeural` | やや明るめ |
| `ja-JP-MayuNeural` | 柔らかめ |
| `ja-JP-ShioriNeural` | 落ち着いた印象 |

```bash
edge-tts --list-voices | grep ja-JP    # 利用可能な日本語ボイス一覧
edge-tts --voice ja-JP-NanamiNeural --text "おはようございます。今日のニュースです。" --write-media sample.mp3
```
速度は設定の `RATE` を `"+10%"`（速く）/ `"-10%"`（ゆっくり）で調整。

---

## 無料運用とプライバシー
- **完全無料**：edge-tts（声）＋ GitHub Pages（配信）＋ ポッドキャストアプリ（再生）。月額もAPIキーも不要。
- **履歴フラット**：gh-pages を毎回 force-push で置き換えるため、リポジトリ容量は増え続けない。状態はローカルの `public/` が保持する（消すとエピソード台帳も消えるのでバックアップ推奨だが、消えても翌朝から再構築される）。
- **プライバシー**：public リポジトリのため、フィードURLを知る人は聴ける（検索でヒットする可能性は低いが0ではない）。私的・機微な内容を読ませる場合は、この方式ではなく「mp3をメール添付」（完全非公開）が安全。

## さらに良い声にしたくなったら（任意・有料）
edge-tts で十分自然だが、将来もっと肉声に近づけたい場合は `synth()` 部分だけを
有料TTS（OpenAI TTS / Google Cloud TTS / Azure / ElevenLabs 等）に差し替えれば、他はそのまま使える。毎朝の短い原稿なら費用はごく僅か。
