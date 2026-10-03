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
    """説明文から有効なタイムスタンプ行だけを抽出"""
    matches = []

    # 行ごとに処理
    for line in description.splitlines():
        line = line.strip()
        if not line:
            continue

        # タイムスタンプで始まるかチェック（0:27:21 や 1:53:55 など）
        ts_match = re.match(r"^(\d{1,2}:\d{2}:\d{2}|\d{1,2}:\d{2})\s*(.*)$", line)
        if not ts_match:
            continue

        timestamp = ts_match.group(1)
        rest = ts_match.group(2).strip()

        # 直後が半角・全角かっこで始まる場合はスキップ
        if rest.startswith("(") or rest.startswith("（"):
            continue

        # 正常形式: マップ/プレイヤー名/ランク
        parts = rest.split("/")
        if len(parts) < 3:
            continue  # 形式が合わないのでスキップ

        map_name = parts[0].strip()
        player = parts[1].strip()
        rank = "/".join(parts[2:]).strip()  # ランクに / が含まれる可能性に対応

        if not map_name or not player:
            continue

        matches.append({
            "timestamp": timestamp,
            "seconds": to_seconds(timestamp),
            "map": map_name,
            "player": player,
            "rank": rank
        })

    return matches

def fetch_videos():
    """チャンネルの全アップロード動画を取得（playlistItems使用）"""
    from googleapiclient.discovery import build

    youtube = build("youtube", "v3", developerKey=API_KEY)

    # 1. チャンネルの uploads プレイリストIDを取得
    print("チャンネル情報を取得中...")
    channel_response = youtube.channels().list(
        part="contentDetails",
        id=CHANNEL_ID
    ).execute()

    if not channel_response.get("items"):
        raise ValueError("チャンネルが見つかりません。CHANNEL_IDを確認してください。")

    uploads_playlist_id = channel_response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    print(f"uploads プレイリストID: {uploads_playlist_id}")

    # 2. プレイリストから全動画IDを取得（ページネーション）
    video_ids = []
    next_page_token = None

    print("動画IDを取得中...")
    while True:
        playlist_response = youtube.playlistItems().list(
            part="contentDetails",
            playlistId=uploads_playlist_id,
            maxResults=50,
            pageToken=next_page_token
        ).execute()

        for item in playlist_response.get("items", []):
            video_ids.append(item["contentDetails"]["videoId"])

        next_page_token = playlist_response.get("nextPageToken")
        print(f"  現在 {len(video_ids)} 本取得...")

        if not next_page_token:
            break

        # テスト用に件数制限したい場合は以下のコメントを外す
        # if len(video_ids) >= 300:
        #     break

    if not video_ids:
        return []

    print(f"詳細情報を取得中（全{len(video_ids)}本）...")
    results = []

    # 3. 動画詳細を50本ずつ取得
    for i in range(0, len(video_ids), 50):
        batch_ids = video_ids[i:i+50]
        videos_response = youtube.videos().list(
            part="snippet",
            id=",".join(batch_ids)
        ).execute()

        for item in videos_response.get("items", []):
            snippet = item["snippet"]
            video_id = item["id"]
            title = snippet["title"]
            description = snippet.get("description", "")
            published_at = snippet["publishedAt"]

            character = extract_character(title)
            matches = parse_description(description)

            if not matches:
                continue

            results.append({
                "video_id": video_id,
                "title": title,
                "character": character,
                "published_at": published_at,
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "matches": matches
            })

        print(f"  詳細処理済み: {min(i+50, len(video_ids))} / {len(video_ids)}")

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