#!/usr/bin/env python3
"""直近1週間に公開された配信のキャラクター名一覧を txt に出力する"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import sys

print("=== weekly_summary 開始 ===")

BASE = Path(__file__).resolve().parent.parent
DATA_PATH = BASE / "data" / "matches.json"
OUTPUT_PATH = BASE / "data" / "weekly_hunters.txt"

print(f"BASE: {BASE}")
print(f"matches.json: {DATA_PATH}  exists={DATA_PATH.exists()}")

def main():
    if not DATA_PATH.exists():
        print("ERROR: matches.json がありません")
        sys.exit(1)

    with open(DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)

    videos = data.get("videos", [])
    print(f"動画数: {len(videos)}")

    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    print(f"集計期間: {week_ago.isoformat()} ～ {now.isoformat()}")

    characters = []
    seen = set()

    for v in videos:
        if v.get("is_live_archive") is False:
            continue

        published = v.get("published_at")
        if not published:
            continue

        dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
        if dt < week_ago:
            continue

        char = (v.get("character") or "").strip()
        if not char or char in seen or char == "不明":
            continue

        seen.add(char)
        characters.append(char)

    print(f"対象キャラ数: {len(characters)}")

    if not characters:
        text = "今週は追加されたハンター配信がありませんでした。\n"
    else:
        text = (
            "【定期】先週は以下のハンターを配信しましたのでサイトにも反映済です。\n"
            + "、".join(characters)
            + "\n"
            + "https://ebiunion.github.io/identityv-spectate-stream/"
        )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(text, encoding="utf-8")

    print(f"出力先: {OUTPUT_PATH}")
    print(f"ファイル存在: {OUTPUT_PATH.exists()}")
    print("--- 内容 ---")
    print(text)
    print("=== weekly_summary 終了 ===")


if __name__ == "__main__":
    main()