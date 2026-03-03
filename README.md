# 📰 DailyDigest

AI-powered daily news summaries from configurable news websites and YouTube channels.

## Features

- **12 pre-loaded sources**: BBC, CNN, Reuters, Al Jazeera, Guardian, NYT, WaPo, AP News, Bloomberg, NPR + Indian Express & The Hindu
- **Add any source**: Paste a news website URL or YouTube channel URL
- **AI summaries**: Per-source bullet summaries + global "Top Headlines" via Google Gemini
- **No YouTube API key needed**: Uses free public RSS feeds

## Quick Start

```bash
pip install -r requirements.txt
python app.py --dev
# Open http://localhost:8081
```

1. Click ⚙️ Settings → enter your [Gemini API key](https://aistudio.google.com/)
2. Click ☰ Sources → add/remove news sites or YouTube channels
3. Click ↻ Refresh → get your daily digest

## Deploy to Render

1. Push this repo to GitHub
2. Go to [render.com](https://render.com) → **New Web Service**
3. Connect your GitHub repo
4. Render auto-detects the config — just click **Deploy**
5. Your app will be live at `https://dailydigest-XXXX.onrender.com`

## Tech Stack

| Layer | Tech |
|-------|------|
| Backend | Python Flask + Gunicorn |
| Frontend | Vanilla HTML/CSS/JS |
| AI | Google Gemini 2.5 Flash |
| Feeds | RSS (feedparser) + YouTube public RSS |
