"""
Daily AI Digest -> Telegram
Pulls: (1) AI news headlines, (2) top-starred AI repos, (3) recently-popular AI repos
Sends a formatted summary to a Telegram chat via bot API.
"""

import os
import re
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

HEADERS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "daily-ai-digest-bot",
}

AI_KEYWORDS = [
    "artificial intelligence", "machine learning", "llm", "neural",
    "deep learning", "gpt", "genai", "generative ai", "chatbot", "nlp",
    "computer vision", "rag", "large language model", "transformer",
]

AI_WORD_PATTERNS = [r"\bai\b", r"\bml\b", r"\bagent(s)?\b"]


def is_ai_relevant(repo):
    """Second-pass check: topic tags alone aren't reliable (e.g. mistagged repos
    like API gateways). Require the name/description to actually mention AI terms
    as whole words/phrases -- not as a loose substring (e.g. 'ai' inside 'domain')."""
    text = f"{repo.get('name', '')} {repo.get('description') or ''}".lower()
    if any(kw in text for kw in AI_KEYWORDS):
        return True
    return any(re.search(pat, text) for pat in AI_WORD_PATTERNS)


def get_ai_news(limit=5):
    """Pull top AI headlines from Google News RSS (no API key required)."""
    url = "https://news.google.com/rss/search?q=artificial%20intelligence&hl=en-US&gl=US&ceid=US:en"
    resp = requests.get(url, timeout=15)
    root = ET.fromstring(resp.content)
    items = root.findall(".//item")[:limit]
    headlines = []
    for item in items:
        title = item.find("title").text
        link = item.find("link").text
        headlines.append(f"• {title}\n  {link}")
    return headlines


def get_top_starred_ai_repos(limit=10):
    """Top AI repos by total stars, via GitHub search API (no auth needed for light use)."""
    url = "https://api.github.com/search/repositories"
    params = {
        "q": "topic:artificial-intelligence",
        "sort": "stars",
        "order": "desc",
        "per_page": limit * 3,  # fetch extra, since some get filtered out below
    }
    resp = requests.get(url, params=params, timeout=15, headers=HEADERS)
    resp.raise_for_status()
    items = resp.json().get("items", [])
    items = [r for r in items if is_ai_relevant(r)][:limit]
    lines = []
    for repo in items:
        lines.append(f"• {repo['full_name']} — {repo['stargazers_count']:,}★\n  {repo['html_url']}")
    return lines


def get_fastest_rising_ai_repos(limit=10):
    """Approximate 'fastest rising' as AI repos created in the last 14 days, sorted by stars."""
    since = (datetime.utcnow() - timedelta(days=14)).strftime("%Y-%m-%d")
    url = "https://api.github.com/search/repositories"
    params = {
        "q": f"topic:artificial-intelligence created:>{since}",
        "sort": "stars",
        "order": "desc",
        "per_page": limit * 3,  # fetch extra, since some get filtered out below
    }
    resp = requests.get(url, params=params, timeout=15, headers=HEADERS)
    resp.raise_for_status()
    items = resp.json().get("items", [])
    items = [r for r in items if is_ai_relevant(r)][:limit]
    lines = []
    for repo in items:
        lines.append(f"• {repo['full_name']} — {repo['stargazers_count']:,}★ (new)\n  {repo['html_url']}")
    return lines


def build_message():
    today = datetime.utcnow().strftime("%d %b %Y")
    parts = [f"*🌅 Daily AI Digest — {today}*\n"]

    parts.append("*📰 Top AI News*")
    try:
        parts.extend(get_ai_news() or ["No news found today."])
    except Exception as e:
        parts.append(f"(news fetch failed: {e})")

    parts.append("\n*⭐ Most-Adopted AI Repos (by stars)*")
    try:
        parts.extend(get_top_starred_ai_repos() or ["No data."])
    except Exception as e:
        parts.append(f"(GitHub fetch failed: {e})")

    parts.append("\n*🚀 Fastest-Rising AI Repos (new, last 14 days)*")
    try:
        parts.extend(get_fastest_rising_ai_repos() or ["No data."])
    except Exception as e:
        parts.append(f"(GitHub fetch failed: {e})")

    return "\n".join(parts)


def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    # Telegram messages have a 4096 char limit -- trim if needed
    if len(text) > 4000:
        text = text[:3990] + "\n\n…(truncated)"
    resp = requests.post(url, data={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }, timeout=15)
    resp.raise_for_status()
    return resp.json()


if __name__ == "__main__":
    message = build_message()
    result = send_telegram_message(message)
    print("Sent:", result.get("ok"))
