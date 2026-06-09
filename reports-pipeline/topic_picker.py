#!/usr/bin/env python3
"""
topic_picker.py — AI-powered 4-dimensional topic scoring engine.

Evaluates potential report topics across four dimensions:
  1. Timeliness — how fresh/urgent the topic is right now
  2. Impact — how much this matters to B2B software buyers
  3. Diversity — how different from recently published topics
  4. Narrative Potential — how rich the storytelling angle is

Scores topics 1-10 per dimension, computes weighted composite score,
and outputs ranked results.

Author: stackinsider.org pipeline
"""

import argparse
import json
import logging
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("topic_picker")

BASE_DIR = Path(__file__).resolve().parent
CANDIDATES_JSON = BASE_DIR / "topic_candidates.json"
RECENTLY_PUBLISHED = BASE_DIR / "recently_published.json"

# ---------------------------------------------------------------------------
# Dimension weights (sums to 1.0)
# ---------------------------------------------------------------------------

WEIGHTS = {
    "timeliness": 0.30,
    "impact": 0.35,
    "diversity": 0.15,
    "narrative_potential": 0.20,
}

# ---------------------------------------------------------------------------
# Scoring functions
# ---------------------------------------------------------------------------

def score_timeliness(topic: dict) -> float:
    """
    Timeliness scoring based on:
    - Recent mentions in scraped data (last 7 days)
    - Whether topic touches on current events/launches
    - Age of most recent supporting data
    """
    score = 5.0  # baseline

    # Boost for topics with "Q2 2026" or current quarter references
    name = topic.get("name", "").lower()
    if "2026" in name:
        score += 1.5
    if any(w in name for w in ["latest", "new", "just launched", "breaking", "recent"]):
        score += 1.0

    # Boost for high signal count (indicates active discussion)
    signal_count = topic.get("signal_count", 0)
    if signal_count > 20:
        score += 1.5
    elif signal_count > 10:
        score += 1.0
    elif signal_count > 5:
        score += 0.5

    return min(score, 10.0)


def score_impact(topic: dict) -> float:
    """
    Impact scoring based on:
    - Market size of the category
    - Number of verified analyst reports covering this area
    - Sentiment intensity (strong opinions = high stakes)
    """
    score = 5.0

    verified_count = topic.get("verified_sources_count", 0)
    if verified_count >= 5:
        score += 2.0
    elif verified_count >= 3:
        score += 1.5
    elif verified_count >= 1:
        score += 0.5

    # Category-based boost
    category = topic.get("category", "").lower()
    if category in ("erp", "crm"):
        score += 1.5  # Core B2B categories
    elif category in ("project management", "b2b software"):
        score += 1.0

    # Sentiment intensity
    sentiment_intensity = topic.get("sentiment_intensity", "medium")
    if sentiment_intensity == "high":
        score += 1.5
    elif sentiment_intensity == "medium":
        score += 0.5

    return min(score, 10.0)


def score_diversity(topic: dict, recent_topics: list) -> float:
    """
    Diversity scoring — penalize topics too similar to recently published ones.
    """
    score = 7.0  # start optimistic

    topic_name = topic.get("name", "").lower()
    topic_category = topic.get("category", "").lower()

    for recent in recent_topics:
        recent_name = recent.get("name", "").lower()
        recent_category = recent.get("category", "").lower()

        # Same category penalty
        if topic_category == recent_category:
            score -= 1.0

        # Name overlap penalty
        topic_words = set(topic_name.split())
        recent_words = set(recent_name.split())
        overlap = len(topic_words & recent_words)
        if overlap >= 3:
            score -= 2.0
        elif overlap >= 1:
            score -= 0.5

    return max(score, 1.0)


def score_narrative_potential(topic: dict) -> float:
    """
    Narrative potential — how compelling a story can we build?
    Considers: trend trajectory, human interest, actionable takeaways.
    """
    score = 5.0

    keywords = topic.get("keywords", [])
    narrative_rich = {"vs", "versus", "battle", "shift", "trend", "prediction",
                      "rise", "fall", "disruption", "winner", "loser",
                      "migration", "comparison", "surprising", "hidden"}
    rich_matches = sum(1 for kw in keywords if kw.lower() in narrative_rich)
    score += min(rich_matches * 0.5, 2.0)

    # Trends score higher
    name = topic.get("name", "").lower()
    if any(w in name for w in ["trends", "outlook", "prediction", "forecast"]):
        score += 1.0

    # Comparative topics score higher
    if any(w in name for w in ["vs", "versus", "compared", "alternative"]):
        score += 1.5

    return min(score, 10.0)


# ---------------------------------------------------------------------------
# Main scorer
# ---------------------------------------------------------------------------

def pick_topics(
    candidates: list,
    recent_topics: list = None,
    top_n: int = 3,
) -> list:
    """
    Score all candidates and return top-N ranked results.
    """
    if recent_topics is None:
        recent_topics_from_file = []
        if RECENTLY_PUBLISHED.exists():
            with open(RECENTLY_PUBLISHED, "r", encoding="utf-8") as f:
                recent_topics_from_file = json.load(f)
        recent_topics = recent_topics_from_file

    scored = []
    for candidate in candidates:
        scores = {
            "timeliness": round(score_timeliness(candidate), 2),
            "impact": round(score_impact(candidate), 2),
            "diversity": round(score_diversity(candidate, recent_topics), 2),
            "narrative_potential": round(score_narrative_potential(candidate), 2),
        }

        composite = sum(scores[k] * WEIGHTS[k] for k in WEIGHTS)
        scores["composite"] = round(composite, 2)

        scored.append({
            "topic": candidate.get("name", "Untitled"),
            "category": candidate.get("category", "Unknown"),
            "scores": scores,
        })

    # Sort by composite descending
    scored.sort(key=lambda x: x["scores"]["composite"], reverse=True)

    return scored[:top_n]


# ---------------------------------------------------------------------------
# Candidate generation (for when no candidates file exists)
# ---------------------------------------------------------------------------

DEFAULT_CANDIDATES = [
    {
        "name": "CRM Market Trends Q2 2026",
        "category": "CRM",
        "signal_count": 18,
        "verified_sources_count": 5,
        "sentiment_intensity": "high",
        "keywords": ["CRM", "trends", "AI", "sales", "customer", "service"],
    },
    {
        "name": "ERP Cloud Migration: SAP vs Oracle 2026",
        "category": "ERP",
        "signal_count": 15,
        "verified_sources_count": 4,
        "sentiment_intensity": "high",
        "keywords": ["ERP", "cloud", "migration", "SAP", "Oracle", "versus"],
    },
    {
        "name": "Project Management Tools: Asana vs Monday vs Jira",
        "category": "Project Management",
        "signal_count": 12,
        "verified_sources_count": 3,
        "sentiment_intensity": "medium",
        "keywords": ["project management", "Asana", "Monday", "Jira", "versus"],
    },
    {
        "name": "AI in B2B Sales: The Hype vs Reality",
        "category": "B2B Software",
        "signal_count": 22,
        "verified_sources_count": 3,
        "sentiment_intensity": "high",
        "keywords": ["AI", "sales", "hype", "reality", "automation"],
    },
    {
        "name": "Composable ERP: The Next Architecture Shift",
        "category": "ERP",
        "signal_count": 9,
        "verified_sources_count": 2,
        "sentiment_intensity": "medium",
        "keywords": ["composable", "ERP", "architecture", "shift", "modular"],
    },
    {
        "name": "CRM Pricing TCO Analysis: Hidden Costs Buyers Miss",
        "category": "CRM",
        "signal_count": 11,
        "verified_sources_count": 2,
        "sentiment_intensity": "medium",
        "keywords": ["pricing", "TCO", "CRM", "hidden", "costs", "buyer"],
    },
    {
        "name": "Mid-Market ERP Buyers Guide: NetSuite vs Acumatica vs Dynamics",
        "category": "ERP",
        "signal_count": 14,
        "verified_sources_count": 3,
        "sentiment_intensity": "high",
        "keywords": ["mid-market", "ERP", "NetSuite", "Acumatica", "Dynamics", "versus"],
    },
    {
        "name": "B2B SaaS Pricing Trends 2026: Usage-Based vs Seat-Based",
        "category": "B2B Software",
        "signal_count": 16,
        "verified_sources_count": 2,
        "sentiment_intensity": "medium",
        "keywords": ["pricing", "SaaS", "usage-based", "seat-based", "trends"],
    },
]


def main():
    parser = argparse.ArgumentParser(description="AI-powered topic selection engine")
    parser.add_argument(
        "-n", "--top-n", type=int, default=3, help="Number of top topics to return"
    )
    parser.add_argument(
        "-o", "--output", type=str, help="Output JSON path (default: stdout)"
    )
    parser.add_argument(
        "--candidates", type=str, help="Path to candidates JSON file"
    )
    args = parser.parse_args()

    # Load candidates
    candidates_path = args.candidates or CANDIDATES_JSON
    if Path(candidates_path).exists():
        with open(candidates_path, "r", encoding="utf-8") as f:
            candidates = json.load(f)
    else:
        logger.info("No candidates file found, using default candidates")
        candidates = DEFAULT_CANDIDATES

    # Pick
    results = pick_topics(candidates, top_n=args.top_n)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        logger.info(f"Results written to {args.output}")
    else:
        print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()