"""DailyDigest — Flask API server for daily news summaries."""

import os
import sys
import json
import uuid
import threading
from datetime import datetime, timezone
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

from feed_parser import fetch_website_articles
from youtube_parser import fetch_youtube_videos
from summarizer import summarize_source, generate_top_headlines

app = Flask(__name__, static_folder="static", static_url_path="")
CORS(app)

SOURCES_FILE = os.path.join(os.path.dirname(__file__), "sources.json")

# In-memory state
_digest_cache = {
    "status": "idle",  # idle, fetching, summarizing, done, error
    "progress": "",
    "progress_detail": "",
    "digest": None,
    "error": None,
    "last_updated": None,
}
_digest_lock = threading.Lock()


# ─── Source management ────────────────────────────────────────────────

def _load_sources() -> list[dict]:
    """Load sources from the JSON file."""
    try:
        with open(SOURCES_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save_sources(sources: list[dict]):
    """Save sources to the JSON file."""
    with open(SOURCES_FILE, "w") as f:
        json.dump(sources, f, indent=2)


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/sources", methods=["GET"])
def get_sources():
    """Get all configured sources."""
    return jsonify(_load_sources())


@app.route("/api/sources", methods=["POST"])
def add_source():
    """Add a new source (website URL or YouTube channel URL)."""
    data = request.get_json() or {}
    url = data.get("url", "").strip()
    name = data.get("name", "").strip()
    source_type = data.get("type", "").strip()

    if not url:
        return jsonify({"error": "URL is required."}), 400

    # Auto-detect type from URL
    if not source_type:
        if "youtube.com" in url or "youtu.be" in url:
            source_type = "youtube"
        else:
            source_type = "website"

    # Generate an ID
    source_id = data.get("id", str(uuid.uuid4())[:8])

    # Auto-generate name if not provided
    if not name:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        name = parsed.netloc.replace("www.", "").split(".")[0].title()

    new_source = {
        "id": source_id,
        "name": name,
        "url": url,
        "type": source_type,
    }

    # Add rss_url if provided
    if data.get("rss_url"):
        new_source["rss_url"] = data["rss_url"]

    sources = _load_sources()

    # Check for duplicates
    for s in sources:
        if s["url"].rstrip("/") == url.rstrip("/"):
            return jsonify({"error": "This source already exists."}), 409

    sources.append(new_source)
    _save_sources(sources)

    return jsonify(new_source), 201


@app.route("/api/sources/<source_id>", methods=["DELETE"])
def delete_source(source_id):
    """Remove a source by its ID."""
    sources = _load_sources()
    original_len = len(sources)
    sources = [s for s in sources if s["id"] != source_id]

    if len(sources) == original_len:
        return jsonify({"error": "Source not found."}), 404

    _save_sources(sources)
    return jsonify({"message": "Source removed."})


# ─── Digest generation ────────────────────────────────────────────────

@app.route("/api/digest", methods=["GET"])
def get_digest():
    """Get the cached digest."""
    with _digest_lock:
        return jsonify({
            "status": _digest_cache["status"],
            "progress": _digest_cache["progress"],
            "progress_detail": _digest_cache["progress_detail"],
            "digest": _digest_cache["digest"],
            "error": _digest_cache["error"],
            "last_updated": _digest_cache["last_updated"],
        })


@app.route("/api/refresh", methods=["POST"])
def refresh():
    """Trigger a digest refresh — fetch all sources and summarize."""
    global _digest_cache

    data = request.get_json() or {}
    gemini_key = data.get("gemini_api_key", "")

    with _digest_lock:
        if _digest_cache["status"] in ("fetching", "summarizing"):
            return jsonify({"error": "A refresh is already in progress."}), 409

        _digest_cache["status"] = "fetching"
        _digest_cache["progress"] = "Starting..."
        _digest_cache["progress_detail"] = ""
        _digest_cache["error"] = None

    thread = threading.Thread(
        target=_run_digest,
        args=(gemini_key,),
        daemon=True,
    )
    thread.start()

    return jsonify({"status": "fetching", "message": "Refresh started"})


def _run_digest(gemini_key: str):
    """Background task: fetch all sources, then summarize."""
    global _digest_cache

    sources = _load_sources()
    source_results = []

    try:
        # ── Step 1: Fetch all feeds ──
        total = len(sources)
        for i, source in enumerate(sources):
            with _digest_lock:
                _digest_cache["progress"] = f"Fetching feeds ({i + 1}/{total})..."
                _digest_cache["progress_detail"] = f"Loading {source['name']}..."

            if source.get("type") == "youtube":
                result = fetch_youtube_videos(source)
            else:
                result = fetch_website_articles(source)

            source_results.append(result)

        with _digest_lock:
            _digest_cache["progress"] = "All feeds loaded."

        # ── Step 2: Summarize with Gemini ──
        if gemini_key:
            with _digest_lock:
                _digest_cache["status"] = "summarizing"
                _digest_cache["progress"] = "Generating AI summaries..."

            summaries_for_headlines = []

            for i, result in enumerate(source_results):
                with _digest_lock:
                    _digest_cache["progress_detail"] = f"Summarizing {result['name']} ({i + 1}/{len(source_results)})..."

                summary = summarize_source(gemini_key, result)
                result["summary"] = summary
                summaries_for_headlines.append({"name": result["name"], "summary": summary})

            # Generate top headlines
            with _digest_lock:
                _digest_cache["progress_detail"] = "Generating top headlines..."

            top_headlines = generate_top_headlines(gemini_key, summaries_for_headlines)
        else:
            top_headlines = "Enter a Gemini API key in Settings to get AI-generated summaries."
            for result in source_results:
                items = result.get("articles", result.get("videos", []))
                if items:
                    bullets = [f"• {item['title']}" for item in items[:5]]
                    result["summary"] = "\n".join(bullets)
                else:
                    result["summary"] = "No recent content available."

        # ── Step 3: Done ──
        with _digest_lock:
            _digest_cache["status"] = "done"
            _digest_cache["progress"] = "Digest ready!"
            _digest_cache["progress_detail"] = ""
            _digest_cache["last_updated"] = datetime.now(timezone.utc).isoformat()
            _digest_cache["digest"] = {
                "top_headlines": top_headlines,
                "sources": source_results,
            }

    except Exception as e:
        with _digest_lock:
            _digest_cache["status"] = "error"
            _digest_cache["error"] = str(e)
            _digest_cache["progress"] = "Refresh failed."
            _digest_cache["progress_detail"] = ""
        print(f"Digest error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8081))
    is_dev = "--dev" in sys.argv or os.environ.get("FLASK_ENV") == "development"
    print(f"📰 DailyDigest server starting on http://localhost:{port}")
    app.run(debug=is_dev, host="0.0.0.0", port=port)
