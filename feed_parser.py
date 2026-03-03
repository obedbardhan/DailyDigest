"""DailyDigest — RSS/web feed parser for news websites."""

from typing import Optional, List, Dict

import feedparser
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from dateutil import parser as dateutil_parser


# Common RSS feed paths to try when auto-discovering
_RSS_PATHS = [
    "/feed",
    "/rss",
    "/feed/",
    "/rss/",
    "/feeds/posts/default",
    "/rss.xml",
    "/feed.xml",
    "/atom.xml",
    "/index.xml",
    "/?feed=rss2",
]

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36"
}


def discover_rss_url(site_url: str) -> Optional[str]:
    """Try to auto-discover an RSS feed URL from a website."""
    # First, check the HTML for <link rel="alternate" type="application/rss+xml">
    try:
        resp = requests.get(site_url, headers=_HEADERS, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")

        for link in soup.find_all("link", attrs={"type": ["application/rss+xml", "application/atom+xml"]}):
            href = link.get("href", "")
            if href:
                if href.startswith("http"):
                    return href
                elif href.startswith("/"):
                    from urllib.parse import urljoin
                    return urljoin(site_url, href)
    except Exception:
        pass

    # Try common RSS paths
    base = site_url.rstrip("/")
    for path in _RSS_PATHS:
        try:
            url = base + path
            resp = requests.get(url, headers=_HEADERS, timeout=5)
            if resp.status_code == 200 and (
                "xml" in resp.headers.get("content-type", "")
                or "rss" in resp.headers.get("content-type", "")
                or "<rss" in resp.text[:500]
                or "<feed" in resp.text[:500]
            ):
                return url
        except Exception:
            continue

    return None


def parse_feed(rss_url: str, max_items: int = 5) -> List[Dict]:
    """Parse an RSS/Atom feed and return the latest items."""
    try:
        feed = feedparser.parse(rss_url)
    except Exception:
        return []

    items = []
    for entry in feed.entries[:max_items]:
        # Parse the publication date
        published = None
        for date_field in ("published", "updated", "created"):
            raw = getattr(entry, date_field, None)
            if raw:
                try:
                    published = dateutil_parser.parse(raw).isoformat()
                except Exception:
                    pass
                break

        # Get description/summary text
        description = ""
        if hasattr(entry, "summary"):
            description = BeautifulSoup(entry.summary, "html.parser").get_text(strip=True)
        elif hasattr(entry, "description"):
            description = BeautifulSoup(entry.description, "html.parser").get_text(strip=True)

        # Truncate long descriptions
        if len(description) > 500:
            description = description[:500] + "..."

        items.append({
            "title": getattr(entry, "title", "Untitled"),
            "url": getattr(entry, "link", ""),
            "published": published or datetime.now(timezone.utc).isoformat(),
            "description": description,
        })

    return items


def fetch_website_articles(source: Dict, max_items: int = 5) -> Dict:
    """Fetch latest articles from a news website source.

    Args:
        source: dict with keys: id, name, url, type, rss_url (optional)
        max_items: maximum number of articles to fetch

    Returns:
        dict with source info and list of articles
    """
    rss_url = source.get("rss_url", "")

    # Try to discover RSS if not provided
    if not rss_url:
        rss_url = discover_rss_url(source["url"])

    articles = []
    if rss_url:
        articles = parse_feed(rss_url, max_items)

    return {
        "id": source["id"],
        "name": source["name"],
        "url": source["url"],
        "type": "website",
        "rss_url": rss_url or "",
        "articles": articles,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
