"""
YouTube Data API v3 モジュール
動画のリアルタイム統計情報（同時視聴者数、高評価数、コメント数）を取得する。
"""

import re
import requests
from typing import Optional

# YouTube Data API v3 エンドポイント
YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3/videos"


def extract_video_id(url: str) -> Optional[str]:
    """
    YouTube URLから動画IDを抽出する。
    
    対応形式:
    - https://www.youtube.com/watch?v=VIDEO_ID
    - https://youtu.be/VIDEO_ID
    - https://www.youtube.com/live/VIDEO_ID
    - https://youtube.com/watch?v=VIDEO_ID&feature=...
    - VIDEO_ID（11文字の直接入力）
    """
    if not url:
        return None
    
    url = url.strip()
    
    patterns = [
        # youtube.com/watch?v=ID
        r'(?:https?://)?(?:www\.)?youtube\.com/watch\?.*v=([a-zA-Z0-9_-]{11})',
        # youtu.be/ID
        r'(?:https?://)?youtu\.be/([a-zA-Z0-9_-]{11})',
        # youtube.com/live/ID
        r'(?:https?://)?(?:www\.)?youtube\.com/live/([a-zA-Z0-9_-]{11})',
        # youtube.com/embed/ID
        r'(?:https?://)?(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})',
        # 直接IDの場合
        r'^([a-zA-Z0-9_-]{11})$',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None


def fetch_video_stats(video_id: str, api_key: str) -> dict:
    """
    YouTube Data API v3 を使って動画の統計情報を取得する。
    
    Returns:
        dict: {
            "video_id": str,
            "title": str,
            "concurrent_viewers": int or None,
            "like_count": int or None,
            "comment_count": int or None,
            "view_count": int or None,
            "is_live": bool,
            "error": str or None,
        }
    """
    result = {
        "video_id": video_id,
        "title": "",
        "concurrent_viewers": None,
        "like_count": None,
        "comment_count": None,
        "view_count": None,
        "is_live": False,
        "error": None,
    }
    
    try:
        params = {
            "part": "snippet,statistics,liveStreamingDetails",
            "id": video_id,
            "key": api_key,
        }
        
        response = requests.get(YOUTUBE_API_BASE, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if not data.get("items"):
            result["error"] = "動画が見つかりませんでした"
            return result
        
        item = data["items"][0]
        
        # snippet
        snippet = item.get("snippet", {})
        result["title"] = snippet.get("title", "")
        
        # statistics
        stats = item.get("statistics", {})
        if "likeCount" in stats:
            result["like_count"] = int(stats["likeCount"])
        if "commentCount" in stats:
            result["comment_count"] = int(stats["commentCount"])
        if "viewCount" in stats:
            result["view_count"] = int(stats["viewCount"])
        
        # liveStreamingDetails
        live_details = item.get("liveStreamingDetails", {})
        if "concurrentViewers" in live_details:
            result["concurrent_viewers"] = int(live_details["concurrentViewers"])
            result["is_live"] = True
        elif "actualEndTime" in live_details:
            # 配信は終了済み
            result["is_live"] = False
        elif "scheduledStartTime" in live_details and "actualStartTime" not in live_details:
            # 配信はまだ開始していない
            result["is_live"] = False
            result["error"] = "配信はまだ開始されていません"
        elif live_details:
            # liveStreamingDetailsはあるがconcurrentViewersがない
            # → 配信中だがオーナーが視聴者数を非表示にしている可能性
            result["is_live"] = True
            result["error"] = "視聴者数が非表示に設定されています"
        
        return result
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            result["error"] = "APIキーが無効か、クォータ上限に達しました"
        elif e.response.status_code == 400:
            result["error"] = "リクエストが不正です"
        else:
            result["error"] = f"HTTPエラー: {e.response.status_code}"
        return result
    except requests.exceptions.Timeout:
        result["error"] = "リクエストがタイムアウトしました"
        return result
    except requests.exceptions.ConnectionError:
        result["error"] = "ネットワーク接続エラー"
        return result
    except Exception as e:
        result["error"] = f"予期しないエラー: {str(e)}"
        return result


def fetch_multiple_video_stats(video_ids: list[str], api_key: str) -> list[dict]:
    """
    複数の動画IDの統計情報を一度に取得する。
    YouTube APIは1リクエストで最大50のIDを受け付ける。
    """
    if not video_ids:
        return []
    
    # 50件ずつバッチ処理
    results = []
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i + 50]
        batch_ids = ",".join(batch)
        
        try:
            params = {
                "part": "snippet,statistics,liveStreamingDetails",
                "id": batch_ids,
                "key": api_key,
            }
            
            response = requests.get(YOUTUBE_API_BASE, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # レスポンスをIDでマッピング
            items_map = {}
            for item in data.get("items", []):
                items_map[item["id"]] = item
            
            for vid in batch:
                if vid in items_map:
                    item = items_map[vid]
                    r = {
                        "video_id": vid,
                        "title": item.get("snippet", {}).get("title", ""),
                        "concurrent_viewers": None,
                        "like_count": None,
                        "comment_count": None,
                        "view_count": None,
                        "is_live": False,
                        "error": None,
                    }
                    
                    stats = item.get("statistics", {})
                    if "likeCount" in stats:
                        r["like_count"] = int(stats["likeCount"])
                    if "commentCount" in stats:
                        r["comment_count"] = int(stats["commentCount"])
                    if "viewCount" in stats:
                        r["view_count"] = int(stats["viewCount"])
                    
                    live_details = item.get("liveStreamingDetails", {})
                    if "concurrentViewers" in live_details:
                        r["concurrent_viewers"] = int(live_details["concurrentViewers"])
                        r["is_live"] = True
                    elif live_details:
                        r["is_live"] = "actualEndTime" not in live_details
                    
                    results.append(r)
                else:
                    results.append({
                        "video_id": vid,
                        "title": "",
                        "concurrent_viewers": None,
                        "like_count": None,
                        "comment_count": None,
                        "view_count": None,
                        "is_live": False,
                        "error": "動画が見つかりませんでした",
                    })
                    
        except Exception as e:
            for vid in batch:
                results.append({
                    "video_id": vid,
                    "title": "",
                    "concurrent_viewers": None,
                    "like_count": None,
                    "comment_count": None,
                    "view_count": None,
                    "is_live": False,
                    "error": f"APIエラー: {str(e)}",
                })
    
    return results
