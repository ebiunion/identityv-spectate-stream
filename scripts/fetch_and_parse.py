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
LOG_PATH = Path(__file__).parent.parent / "logs" / "fetch_log.txt"  # 追加

# キャラ名リスト（先頭一致用・必要に応じて追加）
CHARACTERS = [
    "アイヴィ", "レオ", "ピエロ", "鹿", "ヴァイオリニスト", "芸者", "血の女王", "ガラテア", "キーガン",
    "イタカ", "悪夢", "隠者", "グレイス", "蜘蛛", "ルキノ", "フルゴ", "フラバルー", "ハスター", "魔女", 
    "アン", "破輪", "オペラ歌手", "泣き虫", "蝋人形師", "白黒無常", "ボンボン", "雑貨商", "女王蜂", "リッパー", 
    "ジョゼフ", "バルク", "アンデッド", "足萎えの羊", "ビリヤードプレイヤー", "歯医者"
    # 必要に応じて追加
]

def is_short(duration: str) -> bool:
    """ISO 8601 duration が60秒以下なら Shorts と判定"""
    if not duration or not duration.startswith("PT"):
        return False
    # 時間または分が含まれていれば Shorts ではない
    if "H" in duration or "M" in duration:
        return False
    m = re.search(r"(\d+)S", duration)
    if m:
        return int(m.group(1)) <= 60
    return False

def to_seconds(ts: str) -> int:
    """0:27:21 → 1641"""
    parts = list(map(int, ts.split(":")))
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    elif len(parts) == 2:
        return parts[0] * 60 + parts[1]
    return 0

def extract_character(title: str) -> str:
    """タイトル先頭の単語をキャラ名として完全一致で取得"""
    title = title.strip()
    match = re.match(r"^([^\s#]+)", title)
    if not match:
        return "不明"

    token = match.group(1)

    # CHARACTERS に完全一致するものがあればそれを使う
    if token in CHARACTERS:
        return token

    # リストになくても先頭単語をそのまま返す
    return token

def parse_video_title(title: str) -> dict | None:
    """
    通常動画のタイトルから試合情報を抽出する
    戻り値: {"character", "player", "map", "rank"} または None
    """
    title = title.strip()

    # パターン1: 【...】 で始まる場合
    if title.startswith("【"):
        # 】の位置を探す
        end = title.find("】")
        if end == -1:
            return None

        after = title[end + 1:].strip()
        # 例: オペラ歌手 レオの思い出 神のレアキャラ試合 引分け #第五人格 ...
        parts = after.split()

        if len(parts) < 2:
            return None

        character = parts[0]
        map_name = parts[1]

        return {
            "character": character,
            "player": "Kakiri",
            "map": map_name,
            "rank": ""  # タイトルに順位がない場合は空
        }

    # パターン2: 【 で始まらない場合
    # 例: 女王蜂 1位 とまだよー 永眠町 S40 Queen Bee 1st Eversleeping Town #第五人格 ...
    # 先頭4つを キャラ / 順位 / プレイヤー / マップ とみなす
    parts = title.split()
    if len(parts) < 4:
        return None

    character = parts[0]
    rank = parts[1]
    player = parts[2]
    map_name = parts[3]

    return {
        "character": character,
        "player": player,
        "map": map_name,
        "rank": rank
    }

def parse_description(description: str, title: str, log_lines: list) -> list[dict]:
    """説明文から有効なタイムスタンプ行だけを抽出。無視した行も記録する"""
    matches = []
    ignored_lines = []

    for line in description.splitlines():
        line = line.strip()
        if not line:
            continue

        # タイムスタンプで始まるかチェック
        ts_match = re.match(r"^(\d{1,2}:\d{2}:\d{2}|\d{1,2}:\d{2})\s*(.*)$", line)
        if not ts_match:
            continue

        timestamp = ts_match.group(1)
        rest = ts_match.group(2).strip()

        # 0:00:00 の行は完全に無視（ログにも出さない）
        if timestamp in ("0:00:00", "0:00", "00:00:00", "00:00"):
            continue

        # ===== 特殊形式: （キャラ名）/マップ/プレイヤー  or  (キャラ名)/マップ/プレイヤー =====
        special = re.match(
            r"^[（(]([^）)]+)[）)]\s*/\s*([^/]+)\s*/\s*(.+)$",
            rest
        )
        if special:
            char_name = special.group(1).strip()
            map_name = special.group(2).strip()
            player = special.group(3).strip()

            if char_name and map_name and player:
                matches.append({
                    "timestamp": timestamp,
                    "seconds": to_seconds(timestamp),
                    "map": map_name,
                    "player": player,
                    "rank": "",              # ランク不明のため空白
                    "character": char_name   # 実際のキャラクター名
                })
            else:
                ignored_lines.append(line)
            continue

        # 直後が半角・全角かっこで始まる場合はスキップ
        if rest.startswith("(") or rest.startswith("（"):
            # 「同じ試合」を含む行はログに出さない
            if "同じ試合" not in line:
                ignored_lines.append(line)
            continue

        # 正常形式: マップ/プレイヤー名/ランク
        parts = rest.split("/")
        if len(parts) < 3:
            if "同じ試合" not in line:
                ignored_lines.append(line)
            continue

        map_name = parts[0].strip()
        player = parts[1].strip()
        rank = "/".join(parts[2:]).strip()

        if not map_name or not player:
            if "同じ試合" not in line:
                ignored_lines.append(line)
            continue

        matches.append({
            "timestamp": timestamp,
            "seconds": to_seconds(timestamp),
            "map": map_name,
            "player": player,
            "rank": rank
            # character は持たない（動画タイトルのキャラを使う）
        })

    if ignored_lines:
        log_lines.append(f"{title}")
        for ignored in ignored_lines:
            log_lines.append(f"  → {ignored}")
        log_lines.append("")

    return matches

def fetch_videos():
    """チャンネルの全アップロード動画を取得（playlistItems使用）+ ログ出力"""
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

    # 2. プレイリストから全動画IDを取得
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

    if not video_ids:
        print("動画が1本も取得できませんでした。")
        return []

    # 3. 詳細情報取得 + ログ準備
    print(f"詳細情報を取得中（全{len(video_ids)}本）...")
    results = []
    log_lines = []
    no_timestamp_titles = []

    log_lines.append(f"実行日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log_lines.append(f"取得動画数: {len(video_ids)}")
    log_lines.append("=" * 60)
    log_lines.append("")

    for i in range(0, len(video_ids), 50):
        batch_ids = video_ids[i:i+50]
        videos_response = youtube.videos().list(
            part="snippet,liveStreamingDetails,contentDetails",
            id=",".join(batch_ids)
        ).execute()

        for item in videos_response.get("items", []):
            # Shorts 除外
            duration = item.get("contentDetails", {}).get("duration", "")
            if is_short(duration):
                continue

            snippet = item["snippet"]
            video_id = item["id"]
            title = snippet["title"]
            description = snippet.get("description", "")
            published_at = snippet["publishedAt"]

            is_live_archive = "liveStreamingDetails" in item

            if is_live_archive:
                # ===== 配信の場合 =====
                character = extract_character(title)
                matches = parse_description(description, title, log_lines)

                if not matches:
                    no_timestamp_titles.append(f"[配信] {title}")
                    continue

                results.append({
                    "video_id": video_id,
                    "title": title,
                    "character": character,
                    "published_at": published_at,
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                    "is_live_archive": True,
                    "matches": matches
                })

            else:
                # ===== 通常動画の場合（タイトルのみ） =====
                info = parse_video_title(title)

                if not info:
                    no_timestamp_titles.append(f"[動画] {title}")
                    continue

                matches = [{
                    "timestamp": "0:00",
                    "seconds": 0,
                    "map": info["map"],
                    "player": info["player"],
                    "rank": info["rank"]
                }]

                results.append({
                    "video_id": video_id,
                    "title": title,
                    "character": info["character"],
                    "published_at": published_at,
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                    "is_live_archive": False,
                    "matches": matches
                })

        print(f"  詳細処理済み: {min(i+50, len(video_ids))} / {len(video_ids)}")

    if no_timestamp_titles:
        log_lines.append("=" * 60)
        log_lines.append(f"有効な試合情報が取れなかったもの（{len(no_timestamp_titles)}本）:")
        log_lines.append("=" * 60)
        for t in no_timestamp_titles:
            log_lines.append(f"  - {t}")
        log_lines.append("")

    # ログファイルに書き出し（毎回上書き）
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(log_lines))

    print(f"ログを書き出しました: {LOG_PATH}")
    print(f"有効な動画数: {len(results)} 本")

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