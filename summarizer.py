"""DailyDigest — AI-powered summarization using Google Gemini."""

from typing import List, Dict

import google.generativeai as genai


def summarize_source(gemini_key: str, source_data: dict) -> str:
    """Generate an AI summary for a single source's articles/videos.

    Args:
        gemini_key: Gemini API key
        source_data: dict with 'name', 'type', and 'articles' or 'videos'

    Returns:
        A concise bullet-point summary string
    """
    genai.configure(api_key=gemini_key)
    model = genai.GenerativeModel("gemini-2.5-flash")

    source_name = source_data.get("name", "Unknown")
    source_type = source_data.get("type", "website")

    if source_type == "youtube":
        items = source_data.get("videos", [])
        item_type = "videos"
    else:
        items = source_data.get("articles", [])
        item_type = "articles"

    if not items:
        return "No recent content available."

    # Build context from articles/videos
    content_lines = []
    for i, item in enumerate(items, 1):
        title = item.get("title", "Untitled")
        desc = item.get("description", "")
        content_lines.append(f"{i}. {title}")
        if desc:
            content_lines.append(f"   {desc}")

    content_text = "\n".join(content_lines)

    prompt = f"""You are a news analyst. Summarize the latest {item_type} from "{source_name}" into 3-5 concise bullet points.
Focus on the most important stories and key takeaways. Be factual and succinct.

Here are the latest {item_type}:

{content_text}

Respond ONLY with bullet points (use • as the bullet character), no headers or other formatting."""

    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"Summary generation failed: {str(e)}"


def generate_top_headlines(gemini_key: str, all_summaries: List[Dict]) -> str:
    """Generate a cross-source top headlines overview.

    Args:
        gemini_key: Gemini API key
        all_summaries: list of dicts with 'name' and 'summary' keys

    Returns:
        A concise top headlines string
    """
    genai.configure(api_key=gemini_key)
    model = genai.GenerativeModel("gemini-2.5-flash")

    if not all_summaries:
        return "No headlines available."

    lines = []
    for s in all_summaries:
        lines.append(f"### {s['name']}")
        lines.append(s.get("summary", "No summary."))
        lines.append("")

    all_text = "\n".join(lines)

    prompt = f"""You are a senior news editor. From the following summaries across multiple news sources, extract the 5 most important global headlines of the day.
Be concise — one sentence per headline. Avoid duplicates across sources.

{all_text}

Respond ONLY with numbered headlines (1. 2. 3. etc.), no headers or other formatting."""

    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"Headlines generation failed: {str(e)}"
