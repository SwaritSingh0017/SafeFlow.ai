"""
News/Disruption Service — checks for civil disruptions (strikes, protests, curfews).
API key loaded from environment — no hardcoding.
"""

import os
import logging
import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("news_service")
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")

DISRUPTION_KEYWORDS = ["strike", "protest", "curfew", "bandh", "riot", "shutdown", "blockade"]


def check_disruption(city: str) -> dict:
    """
    Check for civil disruptions in a city using NewsAPI.
    Returns {"disruption": bool, "headline": str | None}
    """
    if not NEWS_API_KEY:
        logger.warning("[News] NEWS_API_KEY not set — disruption check skipped")
        return {"disruption": False, "headline": None}

    try:
        keywords = " OR ".join(DISRUPTION_KEYWORDS)
        url = (
            f"https://newsapi.org/v2/everything"
            f"?q={city}+AND+({keywords})&language=en"
            f"&sortBy=publishedAt&pageSize=5&apiKey={NEWS_API_KEY}"
        )
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        articles = resp.json().get("articles", [])

        for article in articles:
            title = (article.get("title") or "").lower()
            if any(kw in title for kw in DISRUPTION_KEYWORDS):
                return {"disruption": True, "headline": article["title"]}

        return {"disruption": False, "headline": None}

    except Exception as e:
        logger.error(f"[News] API error for {city}: {e}")
        return {"disruption": False, "headline": None}
