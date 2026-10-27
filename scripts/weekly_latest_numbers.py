#!/usr/bin/env python3
"""
YouTube API から配信を取得し、各ハンターの最新情報を固定順で出力する
- #: そのハンターの配信合計回数（タイトルの#ではない）
- 配信日: 最新配信日
- タイトル上の #数字 の重複があれば別途出力
"""

import os
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

CHANNEL_ID = "UCKj9i0wunjX5VX2pvLHoFaA"
API_KEY = os.environ.get("YOUTUBE_API_KEY")
OUTPUT_PATH = Path(__file__).parent.parent / "data" / "weekly_latest_numbers.tsv"
OUTPUT_DUP_PATH = Path(__file__).parent.parent / "data" / "weekly_latest_numbers_duplicates.tsv"

# 新しい順に走査し、既知相当の打ち切りはしない（週次は全配信を集計）
# テストで件数を抑えたいときだけ有効化
# MAX_VIDEOS = 300
MAX_VIDEOS = None

HUNTER_ORDER = [
    "アイヴィ", "レオ", "ピエロ", "鹿", "ヴァイオリニスト", "芸者", "血の女王", "ガラテア",
    "キーガン", "イタカ", "悪夢", "隠者", "グレイス", "蜘蛛", "ルキノ", "フールズ・ゴールド",
    "フラバルー", "ハスター", "夢の魔女", "アン", "破輪", "オペラ歌手", "泣き虫", "蝋人形師",
    "白黒無常", "ボンボン", "雑貨商", "女王蜂", "リッパー", "ジョゼフ", "バルク",
    "アンデッド", "足萎えの羊", "ビリヤードプレイヤー", "歯医者",
]


def is_short(duration: str) -> bool:
    if not duration or not duration.startswith("PT"):
        return False
    if "H" in duration or "M" in duration:
        return False
    m = re.search(r"(\d+)S", duration)
    return bool(m and int(m.group(1)) <= 60)


def extract_title_episode(title: str) -> str | None:
    if not title:
        return None
    m = re.search(r"#\s*(\d+)\b", title)
    return m.group(1) if m else None


def character_matches(hunter: str, title: str) -> bool:
    """タイトル先頭トークンと完全一致"""
    t = (title or "").strip()
    m = re.match(r"^([^\s#]+)", t)
    if not m:
        return False
    return m.group(1) == hunter


def resolve_hunter(title: str) -> str | None:
    for hunter in HUNTER_ORDER:
        if character_matches(hunter, title):
            return hunter
    return None

def format_date(published: str) -> str:
    if not published:
        return "-"
    try:
        dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
        return dt.astimezone().strftime("%Y/%m/%d")
    except Exception:
        return published[:10]


def fetch_all_streams():
    from googleapiclient.discovery import build

    youtube = build("youtube", "v3", developerKey=API_KEY)

    print("チャンネル情報を取得中...")
    channel_response = youtube.channels().list(
        part="contentDetails",
        id=CHANNEL_ID,
    ).execute()
    if not channel_response.get("items"):
        raise ValueError("チャンネルが見つかりません")

    uploads_id = channel_response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

    video_ids = []
    next_page_token = None
    print("動画IDを取得中...")
    while True:
        playlist_response = youtube.playlistItems().list(
            part="contentDetails",
            playlistId=uploads_id,
            maxResults=50,
            pageToken=next_page_token,
        ).execute()
        for item in playlist_response.get("items", []):
            video_ids.append(item["contentDetails"]["videoId"])
        next_page_token = playlist_response.get("nextPageToken")
        print(f"  {len(video_ids)} 本...")
        if not next_page_token:
            break
        if MAX_VIDEOS and len(video_ids) >= MAX_VIDEOS:
            video_ids = video_ids[:MAX_VIDEOS]
            break

    print(f"詳細取得中（{len(video_ids)} 本）...")
    streams = []
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i + 50]
        res = youtube.videos().list(
            part="snippet,liveStreamingDetails,contentDetails",
            id=",".join(batch),
        ).execute()
        for item in res.get("items", []):
            duration = item.get("contentDetails", {}).get("duration", "")
            if is_short(duration):
                continue
            if "liveStreamingDetails" not in item:
                continue  # 配信のみ
            snippet = item["snippet"]
            streams.append({
                "video_id": item["id"],
                "title": snippet.get("title", ""),
                "published_at": snippet.get("publishedAt", ""),
            })
        print(f"  詳細: {min(i + 50, len(video_ids))} / {len(video_ids)}")

    print(f"配信本数: {len(streams)}")
    return streams


def main():
    if not API_KEY:
        raise ValueError("YOUTUBE_API_KEY が設定されていません")

    streams = fetch_all_streams()

    by_hunter: dict[str, list] = {h: [] for h in HUNTER_ORDER}
    for v in streams:
        hunter = resolve_hunter(v["title"])
        if hunter:
            by_hunter[hunter].append(v)

    lines = []
    lines.append(f"取得日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("【最新】ハンター名 / #（配信合計回数） / 配信日")
    lines.append("-" * 50)

    # --- 最新一覧（スプレッドシート用 TSV）---
    latest_lines = ["ハンター名\t#\t配信日"]
    for hunter in HUNTER_ORDER:
        vids = by_hunter[hunter]
        if not vids:
            latest_lines.append(f"{hunter}\t\t")
            continue
        vids_sorted = sorted(vids, key=lambda x: x.get("published_at", ""), reverse=True)
        latest = vids_sorted[0]
        total_count = len(vids)
        latest_lines.append(
            f"{hunter}\t{total_count}\t{format_date(latest.get('published_at', ''))}"
        )

    # --- タイトル#重複（TSV）---
    dup_lines = ["ハンター名\tタイトル#\t件数\t配信日\tタイトル"]
    any_dup = False
    for hunter in HUNTER_ORDER:
        groups = defaultdict(list)
        for v in by_hunter[hunter]:
            num = extract_title_episode(v.get("title", ""))
            if num:
                groups[num].append(v)
        for num, items in sorted(groups.items(), key=lambda x: int(x[0])):
            if len(items) < 2:
                continue
            any_dup = True
            for v in sorted(items, key=lambda x: x.get("published_at", ""), reverse=True):
                dup_lines.append(
                    f"{hunter}\t{num}\t{len(items)}\t"
                    f"{format_date(v.get('published_at', ''))}\t{v.get('title', '')}"
                )

    if not any_dup:
        dup_lines.append("（重複なし）\t\t\t\t")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text("\n".join(latest_lines) + "\n", encoding="utf-8-sig")  # Excel向けBOM付き
    OUTPUT_DUP_PATH.write_text("\n".join(dup_lines) + "\n", encoding="utf-8-sig")

    print("\n".join(latest_lines))
    print(f"\n保存: {OUTPUT_PATH}")
    print(f"重複: {OUTPUT_DUP_PATH}")


if __name__ == "__main__":
    main()