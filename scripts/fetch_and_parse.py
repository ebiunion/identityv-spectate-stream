#!/usr/bin/env python3
"""
Identity V 配信データを取得して matches.json を生成するスクリプト
"""

import os
import re
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ===== 設定 =====
CHANNEL_ID = "UCKj9i0wunjX5VX2pvLHoFaA"   # 例: UCxxxxxxxx
API_KEY = os.environ.get("YOUTUBE_API_KEY")  # GitHub Secrets から取得
OUTPUT_PATH = Path(__file__).parent.parent / "data" / "matches.json"
DAYS_TO_FETCH = 7  # 過去何日分を取得するか（初回は多めに）

# キャラ名リスト（先頭一致用・必要に応じて追加）
CHARACTERS = [
    "アイヴィ", "レオ", "ピエロ", "鹿", "ヴァイオリニスト", "芸者", "女王", "ガラテア", "キーガン",
    "イタカ", "悪夢", "隠者", "グレイス", "蜘蛛", "ルキノ", "フルゴ", "フラバルー", "ハスター", "魔女", 
    "アン", "破輪", "オペラ", "泣き虫", "蝋人形師", "白黒無常", "ボンボン", "雑貨商", "女王蜂", "リッパー", 
    "ジョゼフ", "バルク", "アンデッド", "足萎え", "ビリヤードプレイヤー", "歯医者"
    # 必要に応じて追加
]

def to_seconds(ts: str) -> int:
    """0:27:21 → 1641"""
    parts = list(map(int, ts.split(":")))
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    elif len(parts) == 2:
        return parts[0] * 60 + parts[1]
    return 0

def extract_character(title: str) -> str:
    """タイトル先頭からキャラ名を抽出"""
    title = title.strip()
    for char in CHARACTERS:
        if title.startswith(char):
            return char
    # フォールバック: 最初のスペースまたは#の前
    match = re.match(r"^([^\s#]+)", title)
    return match.group(1) if match else "不明"

def parse_description(description: str) -> list[dict]:
    """説明文からタイムスタンプ行を抽出"""
    matches = []
    # 形式: 0:27:21 永眠町/変質者オレ/1位
    pattern = re.compile(
        r"(\d{1,2}:\d{2}:\d{2}|\d{1,2}:\d{2})\s+([^/\n]+)/([^/\n]+)/([^\n]+)"
    )
    for m in pattern.finditer(description):
        ts, map_name, player, rank = m.groups()
        matches.append({
            "timestamp": ts.strip(),
            "seconds": to_seconds(ts),
            "map": map_name.strip(),
            "player": player.strip(),
            "rank": rank.strip()
        })
    return matches

def fetch_videos():
    """YouTube Data API で最新動画を取得"""
    from googleapiclient.discovery import build

    youtube = build("youtube", "v3", developerKey=API_KEY)

    # 検索で最新動画IDを取得
    published_after = (datetime.now(timezone.utc) - timedelta(days=DAYS_TO_FETCH)).isoformat()

    search_response = youtube.search().list(
        part="id",
        channelId=CHANNEL_ID,
        type="video",
        order="date",
        publishedAfter=published_after,
        maxResults=50
    ).execute()

    video_ids = [item["id"]["videoId"] for item in search_response.get("items", [])]
    if not video_ids:
        return []

    # 詳細情報を取得
    videos_response = youtube.videos().list(
        part="snippet",
        id=",".join(video_ids)
    ).execute()

    results = []
    for item in videos_response.get("items", []):
        snippet = item["snippet"]
        video_id = item["id"]
        title = snippet["title"]
        description = snippet.get("description", "")
        published_at = snippet["publishedAt"]

        character = extract_character(title)
        matches = parse_description(description)

        if not matches:
            continue  # タイムスタンプがない動画はスキップ

        results.append({
            "video_id": video_id,
            "title": title,
            "character": character,
            "published_at": published_at,
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "matches": matches
        })

    # 新しい順にソート
    results.sort(key=lambda x: x["published_at"], reverse=True)
    return results

def main():
    if not API_KEY:
        raise ValueError("YOUTUBE_API_KEY が設定されていません")

    print("動画データを取得中...")
    data = fetch_videos()

    output = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "videos": data
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"完了: {len(data)} 本の動画を {OUTPUT_PATH} に保存しました")

if __name__ == "__main__":
    main()