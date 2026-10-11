#!/usr/bin/env python3
"""配信のみ：キャラクター別の再生回数合計・平均を集計"""

import os
import json
from pathlib import Path
from collections import defaultdict

API_KEY = "AIzaSyDj1zE3A6bSXXS8uBaofhylzYm7gXfaD7c"
DATA_PATH = Path(__file__).parent.parent / "data" / "matches.json"
OUTPUT_PATH = Path(__file__).parent.parent / "data" / "views_by_character.txt"


def fetch_view_counts(youtube, video_ids: list[str]) -> dict[str, int]:
    """video_id -> viewCount"""
    views = {}
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i + 50]
        res = youtube.videos().list(
            part="statistics",
            id=",".join(batch),
        ).execute()
        for item in res.get("items", []):
            vid = item["id"]
            count = int(item.get("statistics", {}).get("viewCount", 0))
            views[vid] = count
        print(f"  再生回数取得: {min(i + 50, len(video_ids))} / {len(video_ids)}")
    return views


def main():
    if not API_KEY:
        raise ValueError("YOUTUBE_API_KEY が設定されていません")
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"{DATA_PATH} がありません")

    with open(DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)

    # 配信のみ
    streams = [
        v for v in data.get("videos", [])
        if v.get("is_live_archive") is True and v.get("video_id")
    ]
    print(f"配信本数: {len(streams)}")

    video_ids = list({v["video_id"] for v in streams})
    print(f"ユニーク動画ID: {len(video_ids)}")

    from googleapiclient.discovery import build
    youtube = build("youtube", "v3", developerKey=API_KEY)

    print("再生回数を取得中...")
    view_map = fetch_view_counts(youtube, video_ids)

    # キャラ別に集計
    # total_views, count
    stats = defaultdict(lambda: {"total": 0, "count": 0})

    for v in streams:
        char = (v.get("character") or "不明").strip()
        views = view_map.get(v["video_id"], 0)
        stats[char]["total"] += views
        stats[char]["count"] += 1

    # 平均を計算してリスト化
    rows = []
    for char, s in stats.items():
        avg = s["total"] / s["count"] if s["count"] else 0
        rows.append({
            "character": char,
            "count": s["count"],
            "total": s["total"],
            "average": avg,
        })

    # 平均再生回数の多い順
    rows.sort(key=lambda x: x["average"], reverse=True)

    lines = [
        "キャラクター別 再生回数（配信のみ）",
        f"集計対象: {len(streams)} 本",
        "",
        f"{'キャラクター':<16} {'本数':>6} {'合計再生':>12} {'平均再生':>12}",
        "-" * 50,
    ]
    for r in rows:
        lines.append(
            f"{r['character']:<16} {r['count']:>6} {r['total']:>12,} {r['average']:>12,.1f}"
        )

    text = "\n".join(lines) + "\n"
    OUTPUT_PATH.write_text(text, encoding="utf-8")
    print(text)
    print(f"保存先: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()