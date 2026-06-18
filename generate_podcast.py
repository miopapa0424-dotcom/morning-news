#!/usr/bin/env python3
"""
毎朝のニュース要約テキストを「女性のニューラル音声(mp3)」に変換し、
ポッドキャストRSSフィードを更新する。GitHub Pages で無料配信する想定。

  使い方:  python generate_podcast.py 今朝の要約.txt
  または:  cat 今朝の要約.txt | python generate_podcast.py

依存:  pip install edge-tts mutagen
  ※ TTSは Microsoft Edge の無料エンドポイントを使用（APIキー不要・無料）
"""

import os
import re
import sys
import json
import html
import asyncio
import subprocess
from datetime import datetime, timezone, timedelta
from email.utils import format_datetime
from pathlib import Path

import edge_tts  # pip install edge-tts

# ============ 設定（ここだけ書き換える） ============
REPO_DIR   = Path(__file__).resolve().parent           # このリポジトリのルート
BASE_URL   = "https://miopapa0424-dotcom.github.io/morning-news"  # GitHub Pages のURL（末尾スラッシュ無し）
VOICE      = "ja-JP-NanamiNeural"                       # 女性。Aoi / Mayu / Shiori も可
RATE       = "+0%"                                      # 読み上げ速度。例: "+10%" で1割速く
KEEP_N     = 7                                          # 残すエピソード数（古いものは自動削除）
PODCAST_TITLE  = "やすひろの朝ニュース"
PODCAST_AUTHOR = "やすひろ"
PODCAST_DESC   = "毎朝自動でお届けする、XRPの公式ニュースまとめ。投資助言ではありません。"
PODCAST_LANG   = "ja"
JST = timezone(timedelta(hours=9))
# ====================================================
# ※ このスクリプトは public/ を作り、それを毎回 gh-pages ブランチへ
#   force-push する（履歴は常に1コミット＝リポジトリが肥大しない）。
#   GitHub Pages の Source は「gh-pages ブランチ / root」に設定すること。
#   cover.jpg は public/ 直下に置く。public/ がローカルの状態保管庫になる。

PUBLIC_DIR = REPO_DIR / "public"          # ビルド成果物＋状態の保管庫（ローカルに永続）
EP_DIR     = PUBLIC_DIR / "episodes"
META       = PUBLIC_DIR / "episodes.json"


def clean_for_speech(text: str) -> str:
    """読み上げに不要なURL・記号・マークダウンを除去して、聞きやすい文にする。"""
    text = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", text)           # [見出し](url) -> 見出し（先に処理）
    text = re.sub(r"https?://[^\s)]+", "", text)              # 裸のURL除去（')'は食わない）
    text = re.sub(r"[`*_#>|]", "", text)                      # マークダウン記号
    text = re.sub(r"^\s*[-・•]\s*", "", text, flags=re.M)      # 箇条書きの頭
    text = re.sub(r"\n{2,}", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def build_episode_text(summary: str, date_label: str) -> str:
    intro = f"おはようございます。{date_label}の、ニュースまとめです。"
    outro = "以上です。今日も良い一日を。"
    return f"{intro}\n{clean_for_speech(summary)}\n{outro}"


async def synth(text: str, out_path: Path):
    await edge_tts.Communicate(text, VOICE, rate=RATE).save(str(out_path))


def audio_duration_seconds(path: Path, fallback_text: str = "") -> int:
    """mp3の長さ(秒)。読み取り失敗時は文字数から概算（約6.5文字/秒）。"""
    try:
        from mutagen.mp3 import MP3
        return int(MP3(str(path)).info.length)
    except Exception:
        return max(1, int(len(fallback_text) / 6.5))


def fmt_duration(sec: int) -> str:
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def load_meta() -> list:
    return json.loads(META.read_text(encoding="utf-8")) if META.exists() else []


def save_meta(eps: list):
    META.write_text(json.dumps(eps, ensure_ascii=False, indent=2), encoding="utf-8")


def render_feed(eps: list) -> str:
    now = format_datetime(datetime.now(JST))
    items = "\n".join(f"""    <item>
      <title>{html.escape(e['title'])}</title>
      <description>{html.escape(e['title'])}</description>
      <pubDate>{e['pubDate']}</pubDate>
      <guid isPermaLink="false">{e['file']}</guid>
      <enclosure url="{BASE_URL}/episodes/{e['file']}" length="{e['bytes']}" type="audio/mpeg"/>
      <itunes:duration>{e['duration']}</itunes:duration>
      <itunes:explicit>false</itunes:explicit>
    </item>""" for e in eps)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>{html.escape(PODCAST_TITLE)}</title>
    <link>{BASE_URL}/</link>
    <language>{PODCAST_LANG}</language>
    <description>{html.escape(PODCAST_DESC)}</description>
    <lastBuildDate>{now}</lastBuildDate>
    <itunes:author>{html.escape(PODCAST_AUTHOR)}</itunes:author>
    <itunes:summary>{html.escape(PODCAST_DESC)}</itunes:summary>
    <itunes:explicit>false</itunes:explicit>
    <itunes:category text="News"/>
    <itunes:image href="{BASE_URL}/cover.jpg"/>
    <image>
      <url>{BASE_URL}/cover.jpg</url>
      <title>{html.escape(PODCAST_TITLE)}</title>
      <link>{BASE_URL}/</link>
    </image>
{items}
  </channel>
</rss>
"""


def publish(date_label: str):
    """public/ を gh-pages へ force-push（毎回1コミットに置き換え＝履歴フラット）。
       依存: pip install ghp-import / -n=.nojekyll付与 -f=強制 -p=push -b=対象ブランチ"""
    subprocess.run(
        ["ghp-import", "-n", "-f", "-p", "-m", f"episode {date_label}",
         "-b", "gh-pages", "public"],
        cwd=REPO_DIR, check=True,
    )


def main():
    # 1) 要約テキスト取得（引数のファイル or 標準入力）
    summary = Path(sys.argv[1]).read_text(encoding="utf-8") if len(sys.argv) > 1 else sys.stdin.read()
    if not summary.strip():
        print("要約テキストが空です。終了します。", file=sys.stderr)
        sys.exit(1)

    EP_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(JST)
    date_iso   = now.strftime("%Y-%m-%d")
    date_label = now.strftime("%-m月%-d日")
    fname = f"{date_iso}.mp3"
    out_path = EP_DIR / fname

    # 2) 読み上げ用テキスト生成 → mp3合成
    text = build_episode_text(summary, date_label)
    asyncio.run(synth(text, out_path))

    # 3) メタ更新（先頭に追加・同日は上書き）
    eps = [e for e in load_meta() if e["file"] != fname]
    eps.insert(0, {
        "title": f"{date_label}のニュースまとめ",
        "file": fname,
        "pubDate": format_datetime(now),
        "bytes": out_path.stat().st_size,
        "duration": fmt_duration(audio_duration_seconds(out_path, text)),
    })

    # 4) 古いエピソードを間引き（mp3も削除）
    keep, drop = eps[:KEEP_N], eps[KEEP_N:]
    for e in drop:
        (EP_DIR / e["file"]).unlink(missing_ok=True)
    eps = keep

    # 5) フィード出力・保存
    save_meta(eps)
    (PUBLIC_DIR / "feed.xml").write_text(render_feed(eps), encoding="utf-8")

    # 6) GitHub へ公開（gh-pages へ force-push、数十秒で各アプリに反映）
    publish(date_label)
    print(f"公開しました: {BASE_URL}/episodes/{fname}")


if __name__ == "__main__":
    main()
