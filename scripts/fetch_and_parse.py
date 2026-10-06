#!/usr/bin/env python3
"""
Identity V 配信データを取得して matches.json を生成するスクリプト（増分更新版）
- 既存の matches.json を読み込む
- 未登録の動画だけ API で詳細取得
- 既存データとマージして保存
"""

import os
import re
import json
from datetime import datetime, timezone
from pathlib import Path

# ===== 設定 =====
CHANNEL_ID = "UCKj9i0wunjX5VX2pvLHoFaA"
API_KEY = os.environ.get("YOUTUBE_API_KEY")
OUTPUT_PATH = Path(__file__).parent.parent / "data" / "matches.json"
LOG_PATH = Path(__file__).parent.parent / "logs" / "fetch_log.txt"

# プレイリスト走査時、既知IDがこの連続数に達したら打ち切り（日次更新の高速化）
# 0 にすると全件スキャン（初回や取りこぼし確認時）
STOP_AFTER_CONSECUTIVE_KNOWN = 30

CHARACTERS = [
    "アイヴィ", "レオ", "ピエロ", "鹿", "ヴァイオリニスト", "芸者", "血の女王", "ガラテア", "キーガン",
    "イタカ", "悪夢", "隠者", "グレイス", "蜘蛛", "ルキノ", "フルゴ", "フラバルー", "ハスター", "魔女",
    "アン", "破輪", "オペラ歌手", "泣き虫", "蝋人形師", "白黒無常", "ボンボン", "雑貨商", "女王蜂", "リッパー",
    "ジョゼフ", "バルク", "アンデッド", "足萎えの羊", "ビリヤードプレイヤー", "歯医者",
]


def is_short(duration: str) -> bool:
    if not duration or not duration.startswith("PT"):
        return False
    if "H" in duration or "M" in duration:
        return False
    m = re.search(r"(\d+)S", duration)
    if m:
        return int(m.group(1)) <= 60
    return False


def to_seconds(ts: str) -> int:
    parts = list(map(int, ts.split(":")))
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    return 0


def extract_character(title: str) -> str:
    title = title.strip()
    match = re.match(r"^([^\s#]+)", title)
    if not match:
        return "不明"
    token = match.group(1)
    if token in CHARACTERS:
        return token
    return token


def parse_video_title(title: str) -> dict | None:
    title = title.strip()

    if title.startswith("【"):
        end = title.find("】")
        if end == -1:
            return None
        after = title[end + 1:].strip()
        parts = after.split()
        if len(parts) < 2:
            return None
        return {
            "character": parts[0],
            "player": "Kakiri",
            "map": parts[1],
            "rank": "",
        }

    parts = title.split()
    if len(parts) < 4:
        return None
    return {
        "character": parts[0],
        "player": parts[2],
        "map": parts[3],
        "rank": parts[1],
    }


def parse_description(description: str, title: str, log_lines: list) -> list[dict]:
    matches = []
    ignored_lines = []

    for line in description.splitlines():
        line = line.strip()
        if not line:
            continue

        ts_match = re.match(r"^(\d{1,2}:\d{2}:\d{2}|\d{1,2}:\d{2})\s*(.*)$", line)
        if not ts_match:
            continue

        timestamp = ts_match.group(1)
        rest = ts_match.group(2).strip()

        if timestamp in ("0:00:00", "0:00", "00:00:00", "00:00"):
            continue

        special = re.match(
            r"^[（(]([^）)]+)[）)]\s*/\s*([^/]+)\s*/\s*(.+)$",
            rest,
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
                    "rank": "",
                    "character": char_name,
                })
            else:
                if "同じ試合" not in line:
                    ignored_lines.append(line)
            continue

        if rest.startswith("(") or rest.startswith("（"):
            if "同じ試合" not in line:
                ignored_lines.append(line)
            continue

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
            "rank": rank,
        })

    if ignored_lines:
        log_lines.append(f"{title}")
        for ignored in ignored_lines:
            log_lines.append(f"  → {ignored}")
        log_lines.append("")

    return matches


def load_existing() -> list[dict]:
    """既存の matches.json を読み込む"""
    if not OUTPUT_PATH.exists():
        print("既存データなし（初回実行）")
        return []
    try:
        with open(OUTPUT_PATH, encoding="utf-8") as f:
            data = json.load(f)
        videos = data.get("videos", [])
        print(f"既存データ: {len(videos)} 本")
        return videos
    except Exception as e:
        print(f"既存JSONの読み込みに失敗（空から開始）: {e}")
        return []


def process_video_item(item: dict, log_lines: list, no_timestamp_titles: list) -> dict | None:
    """1本分の動画詳細をパースして結果dictを返す。対象外は None"""
    duration = item.get("contentDetails", {}).get("duration", "")
    if is_short(duration):
        return None

    snippet = item["snippet"]
    video_id = item["id"]
    title = snippet["title"]
    description = snippet.get("description", "")
    published_at = snippet["publishedAt"]
    is_live_archive = "liveStreamingDetails" in item

    if is_live_archive:
        character = extract_character(title)
        matches = parse_description(description, title, log_lines)
        if not matches:
            no_timestamp_titles.append(f"[配信] {title}")
            return None
        return {
            "video_id": video_id,
            "title": title,
            "character": character,
            "published_at": published_at,
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "is_live_archive": True,
            "matches": matches,
        }

    info = parse_video_title(title)
    if not info:
        no_timestamp_titles.append(f"[動画] {title}")
        return None

    return {
        "video_id": video_id,
        "title": title,
        "character": info["character"],
        "published_at": published_at,
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "is_live_archive": False,
        "matches": [{
            "timestamp": "0:00",
            "seconds": 0,
            "map": info["map"],
            "player": info["player"],
            "rank": info["rank"],
        }],
    }


def fetch_new_videos(existing_videos: list[dict]) -> list[dict]:
    """未登録の動画だけ取得してパースする"""
    from googleapiclient.discovery import build

    existing_ids = {v["video_id"] for v in existing_videos if "video_id" in v}
    print(f"既知の video_id: {len(existing_ids)} 件")

    youtube = build("youtube", "v3", developerKey=API_KEY)

    print("チャンネル情報を取得中...")
    channel_response = youtube.channels().list(
        part="contentDetails",
        id=CHANNEL_ID,
    ).execute()

    if not channel_response.get("items"):
        raise ValueError("チャンネルが見つかりません。CHANNEL_IDを確認してください。")

    uploads_playlist_id = channel_response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    print(f"uploads プレイリストID: {uploads_playlist_id}")

    # 新しい動画IDだけ集める（新しい順）
    new_video_ids = []
    next_page_token = None
    consecutive_known = 0

    print("新規動画IDを探索中...")
    while True:
        playlist_response = youtube.playlistItems().list(
            part="contentDetails",
            playlistId=uploads_playlist_id,
            maxResults=50,
            pageToken=next_page_token,
        ).execute()

        for item in playlist_response.get("items", []):
            vid = item["contentDetails"]["videoId"]
            if vid in existing_ids:
                consecutive_known += 1
                if STOP_AFTER_CONSECUTIVE_KNOWN and consecutive_known >= STOP_AFTER_CONSECUTIVE_KNOWN:
                    print(f"  既知IDが{STOP_AFTER_CONSECUTIVE_KNOWN}件連続したため探索を打ち切り")
                    next_page_token = None
                    break
            else:
                consecutive_known = 0
                new_video_ids.append(vid)

        else:
            next_page_token = playlist_response.get("nextPageToken")
            print(f"  新規候補: {len(new_video_ids)} 本 ...")
            if next_page_token:
                continue

        break

    if not new_video_ids:
        print("新規動画はありません")
        return []

    print(f"新規動画の詳細を取得中（{len(new_video_ids)}本）...")
    results = []
    log_lines = []
    no_timestamp_titles = []

    log_lines.append(f"実行日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log_lines.append(f"モード: 増分更新")
    log_lines.append(f"既存: {len(existing_ids)} 本 / 新規候補: {len(new_video_ids)} 本")
    log_lines.append("=" * 60)
    log_lines.append("")

    for i in range(0, len(new_video_ids), 50):
        batch_ids = new_video_ids[i:i + 50]
        videos_response = youtube.videos().list(
            part="snippet,liveStreamingDetails,contentDetails",
            id=",".join(batch_ids),
        ).execute()

        for item in videos_response.get("items", []):
            parsed = process_video_item(item, log_lines, no_timestamp_titles)
            if parsed:
                results.append(parsed)

        print(f"  詳細処理済み: {min(i + 50, len(new_video_ids))} / {len(new_video_ids)}")

    if no_timestamp_titles:
        log_lines.append("=" * 60)
        log_lines.append(f"有効な試合情報が取れなかったもの（{len(no_timestamp_titles)}本）:")
        log_lines.append("=" * 60)
        for t in no_timestamp_titles:
            log_lines.append(f"  - {t}")
        log_lines.append("")

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(log_lines))

    print(f"ログを書き出しました: {LOG_PATH}")
    print(f"新規に登録する動画: {len(results)} 本")
    return results


def main():
    if not API_KEY:
        raise ValueError("YOUTUBE_API_KEY が設定されていません")

    print("動画データを取得中（増分更新）...")
    existing = load_existing()
    new_videos = fetch_new_videos(existing)

    # 新規を先頭側にマージ（ID重複は新規優先で排除）
    existing_ids = {v["video_id"] for v in existing}
    merged = list(new_videos)
    for v in existing:
        if v.get("video_id") not in {n["video_id"] for n in new_videos}:
            merged.append(v)

    merged.sort(key=lambda x: x.get("published_at", ""), reverse=True)

    output = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "videos": merged,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"完了: 新規 {len(new_videos)} 本追加 / 合計 {len(merged)} 本 → {OUTPUT_PATH}")


if __name__ == "__main__":
    main()