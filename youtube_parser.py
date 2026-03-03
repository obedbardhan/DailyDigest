"""DailyDigest — YouTube channel feed parser using public RSS feeds."""

from typing import Optional, Dict

import re
import requests
import feedparser
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from dateutil import parser as dateutil_parser


_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36"
}


def extract_channel_id(youtube_url: str) -> Optional[str]:
    """Extract the YouTube channel ID from various URL formats.

    Supports:
      - https://www.youtube.com/channel/UC...
      - https://www.youtube.com/@handle
      - https://www.youtube.com/c/ChannelName
      - https://www.youtube.com/user/Username
    """
    youtube_url = youtube_url.strip().rstrip("/")

    # Direct channel ID URL
    match = re.search(r"/channel/(UC[\w-]+)", youtube_url)
    if match:
        return match.group(1)

    # For @handle, /c/name, /user/name — fetch the page and extract channel ID
    if re.search(r"youtube\.com/(@[\w.-]+|c/[\w.-]+|user/[\w.-]+)", youtube_url):
        try:
            resp = requests.get(youtube_url, headers=_HEADERS, timeout=10)
            # Look for channel ID in the page source
            match = re.search(r'"channelId"\s*:\s*"(UC[\w-]+)"', resp.text)
            if match:
                return match.group(1)

            # Try meta tag
            match = re.search(r'<meta\s+itemprop="channelId"\s+content="(UC[\w-]+)"', resp.text)
            if match:
                return match.group(1)

            # Try canonical URL
            match = re.search(r'youtube\.com/channel/(UC[\w-]+)', resp.text)
            if match:
                return match.group(1)
        except Exception:
            pass

    return None


def extract_channel_name(youtube_url: str) -> str:
    """Extract a display name from a YouTube URL."""
    # @handle format
    match = re.search(r"/@([\w.-]+)", youtube_url)
    if match:
        return f"@{match.group(1)}"

    # /c/ format
    match = re.search(r"/c/([\w.-]+)", youtube_url)
    if match:
        return match.group(1)

    # /user/ format
    match = re.search(r"/user/([\w.-]+)", youtube_url)
    if match:
        return match.group(1)

    # /channel/ format — just use the ID
    match = re.search(r"/channel/(UC[\w-]+)", youtube_url)
    if match:
        return match.group(1)

    return youtube_url


def fetch_youtube_videos(source: Dict, max_items: int = 5) -> Dict:
    """Fetch latest videos from a YouTube channel via its public RSS feed.

    Args:
        source: dict with keys: id, name, url, type
        max_items: maximum number of videos to fetch

    Returns:
        dict with source info and list of videos
    """
    channel_id = extract_channel_id(source["url"])
    videos = []

    if channel_id:
        rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        try:
            feed = feedparser.parse(rss_url)

            # Get channel name from feed if available
            channel_name = source.get("name", "")
            if not channel_name and feed.feed.get("title"):
                channel_name = feed.feed.title

            for entry in feed.entries[:max_items]:
                published = None
                for date_field in ("published", "updated"):
                    raw = getattr(entry, date_field, None)
                    if raw:
                        try:
                            published = dateutil_parser.parse(raw).isoformat()
                        except Exception:
                            pass
                        break

                # Extract video ID for thumbnail
                video_id = ""
                link = getattr(entry, "link", "")
                vid_match = re.search(r"v=([\w-]+)", link)
                if vid_match:
                    video_id = vid_match.group(1)

                description = ""
                if hasattr(entry, "summary"):
                    description = BeautifulSoup(entry.summary, "html.parser").get_text(strip=True)
                if len(description) > 500:
                    description = description[:500] + "..."

                videos.append({
                    "title": getattr(entry, "title", "Untitled"),
                    "url": link,
                    "published": published or datetime.now(timezone.utc).isoformat(),
                    "description": description,
                    "thumbnail": f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg" if video_id else "",
                })
        except Exception as e:
            print(f"Error fetching YouTube feed for {source['url']}: {e}")

    return {
        "id": source["id"],
        "name": source.get("name", extract_channel_name(source["url"])),
        "url": source["url"],
        "type": "youtube",
        "channel_id": channel_id or "",
        "videos": videos,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
