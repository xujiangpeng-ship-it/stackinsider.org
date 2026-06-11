#!/usr/bin/env python3
"""
crawler.py — Scrapling-based web crawler for B2B software intelligence.

Reads sources.csv (12 sources), scrapes content with configurable selectors
(HTML via Scrapling, JSON APIs for community sources), extracts structured data
via 7 regex extractors, deduplicates in SQLite (news.db / facts), and supports
--weekly mode for incremental weekly scraping.

Scrapling 0.4.9 API: Fetcher() no auto_match, fetcher.get(url), Response.css(),
el.get_all_text() for text extraction.

Author: stackinsider.org pipeline
"""

import argparse
import csv
import json
import logging
import re
import sqlite3
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from scrapling import Fetcher

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "news.db"
SOURCES_CSV = BASE_DIR / "sources.csv"
OUTPUT_JSON = BASE_DIR / "scraped_items.json"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 "
    "stackinsider-crawler/2.0"
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("crawler")

# ---------------------------------------------------------------------------
# 7 Regex Extractors — structured data from raw text
# ---------------------------------------------------------------------------

EXTRACTORS = {
    "company": re.compile(
        r"(Salesforce|HubSpot|SAP|Oracle|Zoho|Microsoft|Workday|Servicenow)"
        r".*(raised|acquired|launched|priced|released|announced|partnered)",
        re.IGNORECASE,
    ),
    "money": re.compile(
        r"\$(\d[\d,.]*)\s?(million|billion|M|B)",
        re.IGNORECASE,
    ),
    "percent": re.compile(
        r"\d{1,3}(?:\.\d)?%\s?(?:increase|growth|decline|reduction|drop|surge|climb)",
        re.IGNORECASE,
    ),
    "report": re.compile(
        r"(Gartner|Forrester|IDC|Nucleus|G2)"
        r".*(report|survey|study|analysis|forecast|research)",
        re.IGNORECASE,
    ),
    "pricing": re.compile(
        r"(?:starting at|priced at|plans from|per user/month|per seat|per month)\s?\$?[\d,.]+",
        re.IGNORECASE,
    ),
    "metric": re.compile(
        r"\d+[\d,.]+\s?(?:users|customers|companies|seats|clients|organizations)",
        re.IGNORECASE,
    ),
    "g2_rating": re.compile(
        r"G2\s?(?:score|rating):\s?\d\.\d",
        re.IGNORECASE,
    ),
}

# ---------------------------------------------------------------------------
# SQLite helpers — news.db / facts table
# ---------------------------------------------------------------------------

def init_db(db_path: Path) -> sqlite3.Connection:
    """Initialize SQLite database with facts table and unique constraint."""
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS facts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_name TEXT NOT NULL,
            source_url TEXT NOT NULL,
            pattern_name TEXT NOT NULL,
            matched_text TEXT NOT NULL,
            raw_text TEXT,
            extracted_at TEXT NOT NULL,
            is_duplicate INTEGER DEFAULT 0,
            UNIQUE(source_url, pattern_name, matched_text)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_facts_source_url ON facts(source_url)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_facts_extracted_at ON facts(extracted_at)"
    )
    conn.commit()
    return conn


def is_duplicate(
    conn: sqlite3.Connection,
    source_url: str,
    pattern_name: str,
    matched_text: str,
) -> bool:
    """Check if (source_url, pattern_name, matched_text) triple already exists."""
    row = conn.execute(
        "SELECT id FROM facts WHERE source_url = ? AND pattern_name = ? AND matched_text = ?",
        (source_url, pattern_name, matched_text),
    ).fetchone()
    return row is not None


def store_fact(
    conn: sqlite3.Connection,
    source_name: str,
    source_url: str,
    pattern_name: str,
    matched_text: str,
    raw_text: str,
) -> bool:
    """Insert fact into database. Returns False if duplicate, True on success."""
    try:
        conn.execute(
            """
            INSERT OR IGNORE INTO facts
                (source_name, source_url, pattern_name, matched_text, raw_text, extracted_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                source_name,
                source_url,
                pattern_name,
                matched_text[:500],
                raw_text[:5000] if raw_text else "",
                datetime.utcnow().isoformat(),
            ),
        )
        conn.commit()
        return conn.total_changes > 0
    except sqlite3.IntegrityError:
        return False


# ---------------------------------------------------------------------------
# Core scraping logic
# ---------------------------------------------------------------------------

def extract_fields(text: str) -> dict:
    """Apply all 7 regex extractors to scraped text."""
    results = {}
    for field, pattern in EXTRACTORS.items():
        matches = pattern.findall(text)
        if matches:
            cleaned = []
            for m in matches:
                if isinstance(m, tuple):
                    cleaned.append(m[0] if m[0] else str(m))
                else:
                    cleaned.append(str(m))
            results[field] = list(dict.fromkeys(cleaned))[:10]
    return results


def fetch_community_json(source: dict) -> list:
    """
    Fetch community JSON API sources (Reddit, Hacker News).
    Returns list of dicts with url and text for extraction.
    """
    base_url = source["base_url"]
    items = []

    if "reddit" in base_url:
        logger.warning(
            f"Skipping Reddit source {source['source_name']}: requires OAuth, not supported"
        )
        return items

    try:
        resp = requests.get(base_url, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.error(f"Failed to fetch JSON API {source['source_name']}: {e}")
        return items

    if "reddit" in base_url:
        # Reddit JSON: data.children[].data.{title,selftext,url}
        children = data.get("data", {}).get("children", [])
        for child in children[:30]:
            post = child.get("data", {})
            title = post.get("title", "")
            selftext = post.get("selftext", "")
            url = post.get("url", "")
            if url:
                items.append({
                    "url": url,
                    "text": f"{title}\n{selftext}"[:5000],
                })
    elif "algolia" in base_url:
        # Hacker News Algolia API: hits[].{title,url,story_text}
        hits = data.get("hits", [])
        for hit in hits[:30]:
            title = hit.get("title", "")
            url = hit.get("url", "")
            story_text = hit.get("story_text", "")
            if url:
                items.append({
                    "url": url,
                    "text": f"{title}\n{story_text}"[:5000],
                })

    return items


def fetch_html_source(source: dict) -> list:
    """
    Fetch HTML sources using Scrapling Fetcher.
    Returns list of dicts with url and text for extraction.
    """
    base_url = source["base_url"]
    selector = source.get("selector", "article a[href]")
    items = []

    fetcher = Fetcher()
    try:
        page = fetcher.get(
            base_url,
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Cache-Control": "no-cache",
                "Sec-Ch-Ua": '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"Windows"',
                "Referer": "https://www.google.com/",
            },
            timeout=15,
        )
    except Exception as e:
        logger.error(f"Failed to fetch {source['source_name']}: {e}")
        return items

    elements = []
    if selector:
        try:
            elements = page.css(selector)
        except Exception:
            logger.warning(
                f"Selector '{selector}' failed for {source['source_name']}, will fallback"
            )
    if not elements:
        if selector:
            logger.warning(
                f"Selector '{selector}' returned 0 elements for {source['source_name']}, falling back to a[href]"
            )
        try:
            elements = page.css("a[href]")
        except Exception:
            logger.error(f"Could not parse {source['source_name']} at all")
            return items

    for el in elements[:30]:
        try:
            link = el.attrib.get("href", "")
            if not link:
                continue

            full_url = urljoin(base_url, link)
            parsed = urlparse(full_url)
            base_parsed = urlparse(base_url)
            if parsed.netloc not in (base_parsed.netloc, "") and parsed.netloc:
                continue

            text = ""
            try:
                text = el.get_all_text().strip()[:5000]
            except Exception:
                try:
                    text = el.text.strip()[:5000] if hasattr(el, "text") else ""
                except Exception:
                    text = ""

            if full_url:
                items.append({"url": full_url, "text": text})
        except Exception:
            continue

    return items


def scrape_source(
    source: dict,
    conn: sqlite3.Connection,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> int:
    """
    Scrape a single source entry. Returns count of new facts stored.
    """
    source_name = source["source_name"]
    source_type = source.get("source_type", "")
    logger.info(f"Fetching: {source_name} ({source_type})")

    # Route by source_type
    if source_type == "community":
        items = fetch_community_json(source)
    else:
        items = fetch_html_source(source)

    new_count = 0
    for item in items:
        url = item["url"]
        text = item["text"]

        if not text:
            continue

        # Apply all 7 extractors
        extracted = extract_fields(text)

        # Date filter if provided
        if start_date or end_date:
            date_match = re.search(r"(\d{4}-\d{2}-\d{2})", text)
            if date_match:
                item_date = date_match.group(1)
                if start_date and item_date < start_date:
                    continue
                if end_date and item_date > end_date:
                    continue

        # Store each extracted match as a fact row
        for pattern_name, matches in extracted.items():
            for match in matches:
                match_str = str(match).strip()
                if not match_str:
                    continue

                if is_duplicate(conn, url, pattern_name, match_str):
                    continue

                if store_fact(conn, source_name, url, pattern_name, match_str, text):
                    new_count += 1

    return new_count


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def load_sources(csv_path: Path) -> list:
    """Load and validate sources from CSV."""
    sources = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            required = ["source_name", "source_type", "base_url"]
            if all(row.get(k) for k in required):
                sources.append(row)
    logger.info(f"Loaded {len(sources)} sources from {csv_path}")
    return sources


def dump_results(conn: sqlite3.Connection, output_path: Path, start_date=None, end_date=None):
    """Export all facts to JSON."""
    query = """
        SELECT source_name, source_url, pattern_name, matched_text, raw_text, extracted_at
        FROM facts ORDER BY extracted_at DESC
    """
    params = []
    if start_date:
        query = """
            SELECT source_name, source_url, pattern_name, matched_text, raw_text, extracted_at
            FROM facts WHERE extracted_at >= ? ORDER BY extracted_at DESC
        """
        params.append(start_date)
    if end_date:
        if "WHERE" in query:
            query = query.replace("ORDER BY", "AND extracted_at <= ? ORDER BY")
        else:
            query += " WHERE extracted_at <= ? ORDER BY extracted_at DESC"
        params.append(end_date)

    rows = conn.execute(query, params).fetchall()

    items = []
    for row in rows:
        items.append({
            "source_name": row[0],
            "source_url": row[1],
            "pattern_name": row[2],
            "matched_text": row[3],
            "raw_text": row[4],
            "extracted_at": row[5],
        })

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    logger.info(f"Exported {len(items)} items to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="StackInsider B2B crawler")
    parser.add_argument(
        "--weekly",
        action="store_true",
        help="Weekly mode: only scrape sources with update_frequency=weekly",
    )
    parser.add_argument(
        "--start",
        type=str,
        default=None,
        help="Start date for filtering (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end",
        type=str,
        default=None,
        help="End date for filtering (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--source",
        type=str,
        help="Scrape a single source by name (from sources.csv)",
    )
    parser.add_argument(
        "--max-sources",
        type=int,
        default=None,
        help="Limit number of sources to process",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(OUTPUT_JSON),
        help="Output JSON path",
    )
    parser.add_argument(
        "--db",
        type=str,
        default=str(DB_PATH),
        help="SQLite database path",
    )
    args = parser.parse_args()

    conn = init_db(Path(args.db))
    sources = load_sources(SOURCES_CSV)

    # Filter for weekly mode
    if args.weekly:
        weekly_sources = [s for s in sources if s.get("update_frequency") == "weekly"]
        logger.info(
            f"Weekly mode: {len(weekly_sources)} of {len(sources)} sources eligible"
        )
        sources = weekly_sources

    # Filter for single source
    if args.source:
        sources = [s for s in sources if s["source_name"] == args.source]
        if not sources:
            logger.error(f"Source '{args.source}' not found in sources.csv")
            sys.exit(1)

    # Limit sources
    if args.max_sources and args.max_sources > 0:
        sources = sources[: args.max_sources]
        logger.info(f"Limited to {args.max_sources} sources")

    # Scrape
    total_new = 0
    for source in sources:
        try:
            new = scrape_source(source, conn, args.start, args.end)
            total_new += new
            logger.info(f"  {source['source_name']}: {new} new facts")
        except Exception as e:
            logger.error(f"  {source['source_name']}: FAILED — {e}")
        time.sleep(1.5)  # rate limiting

    logger.info(f"Total new facts: {total_new}")

    # Export
    dump_results(conn, Path(args.output), args.start, args.end)
    conn.close()

    # Stats
    conn2 = sqlite3.connect(str(args.db))
    total = conn2.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
    conn2.close()
    logger.info(f"Database total: {total} facts")
    print(
        json.dumps(
            {"status": "ok", "new_facts": total_new, "db_total": total}
        )
    )


if __name__ == "__main__":
    main()
