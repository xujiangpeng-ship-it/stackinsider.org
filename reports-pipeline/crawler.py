#!/usr/bin/env python3
"""
crawler.py — Scrapling-based web crawler for B2B software intelligence.

Reads sources.csv for target URLs, scrapes content with configurable selectors,
extracts structured data via 7 regex extractors, deduplicates in SQLite, and
supports --weekly mode for incremental weekly scraping.

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
from scrapling import Fetcher, Adaptor

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "scraper_cache.db"
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
    "vendor": re.compile(
        r"(?:vendor|company|provider):\s*(.+?)(?:\n|$)",
        re.IGNORECASE,
    ),
    "product": re.compile(
        r"(?:product|tool|platform|solution):\s*(.+?)(?:\n|$)",
        re.IGNORECASE,
    ),
    "pricing": re.compile(
        r"(?:(?:starts?\s*(?:at|from)?)\s*\$(\d[\d,]*(?:\.\d{2})?)|"
        r"(?:pricing|price):\s*(.+?)(?:\n|$)|"
        r"\$\d[\d,]*(?:\.\d{2})?\s*(?:per|/)\s*(?:user|month|year|seat))",
        re.IGNORECASE,
    ),
    "category": re.compile(
        r"(?:category|vertical|sector):\s*(.+?)(?:\n|$)",
        re.IGNORECASE,
    ),
    "metric": re.compile(
        r"(\d+(?:\.\d+)?)\s*(%|percent|million|billion|[KMB])\b",
        re.IGNORECASE,
    ),
    "date_published": re.compile(
        r"(?:published|posted|updated):\s*(\d{4}-\d{2}-\d{2}|\w+ \d{1,2},? \d{4})",
        re.IGNORECASE,
    ),
    "sentiment": re.compile(
        r"\b(positive|negative|neutral|improved|declined|grew|dropped|surged|plummeted)\b",
        re.IGNORECASE,
    ),
}

# ---------------------------------------------------------------------------
# SQLite helpers
# ---------------------------------------------------------------------------

def init_db(db_path: Path) -> sqlite3.Connection:
    """Initialize SQLite database with deduplication table."""
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_name TEXT NOT NULL,
            source_type TEXT NOT NULL,
            url TEXT NOT NULL UNIQUE,
            title TEXT,
            raw_text TEXT,
            extracted JSON,
            category_focus TEXT,
            scraped_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_items_url ON items(url)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_items_scraped_at ON items(scraped_at)"
    )
    conn.commit()
    return conn


def is_duplicate(conn: sqlite3.Connection, url: str) -> bool:
    """Check if url already exists in database."""
    row = conn.execute("SELECT id FROM items WHERE url = ?", (url,)).fetchone()
    return row is not None


def store_item(
    conn: sqlite3.Connection,
    source_name: str,
    source_type: str,
    url: str,
    title: str,
    raw_text: str,
    extracted: dict,
    category_focus: str,
) -> bool:
    """Insert item into database. Returns False if duplicate, True on success."""
    try:
        conn.execute(
            """
            INSERT OR IGNORE INTO items
                (source_name, source_type, url, title, raw_text, extracted, category_focus, scraped_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_name,
                source_type,
                url,
                title,
                raw_text[:5000],  # truncate for storage
                json.dumps(extracted, ensure_ascii=False),
                category_focus,
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
            if field == "pricing":
                # flatten tuple matches
                flat = []
                for m in matches:
                    if isinstance(m, tuple):
                        flat.extend([x for x in m if x])
                    else:
                        flat.append(m)
                results[field] = flat[:5]
            else:
                results[field] = [m if isinstance(m, str) else str(m) for m in matches[:5]]
    return results


def scrape_source(
    source: dict,
    conn: sqlite3.Connection,
    weekly_mode: bool = False,
) -> int:
    """
    Scrape a single source entry. Returns count of new items stored.
    """
    fetcher = Fetcher(auto_match=False)
    base_url = source["base_url"]
    source_name = source["source_name"]
    selector = source.get("selector", "article, .post, .entry")
    category_focus = source.get("category_focus", "B2B Software")

    logger.info(f"Fetching: {source_name} ({base_url})")

    try:
        page = fetcher.fetch(base_url)
        adaptor = Adaptor(page, base_url)
    except Exception as e:
        logger.error(f"Failed to fetch {source_name}: {e}")
        return 0

    new_count = 0

    try:
        # Find all matching elements
        elements = adaptor.css(selector)
    except Exception:
        logger.warning(f"Selector '{selector}' failed for {source_name}, trying generic")
        try:
            elements = adaptor.css("a[href]")
        except Exception:
            logger.error(f"Could not parse {source_name} at all")
            return 0

    for el in elements[:30]:  # cap per source
        try:
            link = el.attrib.get("href", "")
            if not link:
                continue

            # Resolve relative URLs
            full_url = urljoin(base_url, link)
            parsed = urlparse(full_url)
            if parsed.netloc not in urlparse(base_url).netloc and not parsed.netloc:
                continue

            # Dedup check
            if is_duplicate(conn, full_url):
                continue

            # Extract text content
            title = ""
            try:
                title = el.text_content().strip()[:200]
            except Exception:
                title = el.text.strip()[:200] if hasattr(el, "text") else ""

            raw_text = ""
            try:
                raw_text = el.text_content().strip()[:5000]
            except Exception:
                raw_text = str(el)[:5000]

            # Regex extraction
            extracted = extract_fields(raw_text)

            # Store
            if store_item(conn, source_name, source["source_type"], full_url, title, raw_text, extracted, category_focus):
                new_count += 1

        except Exception as e:
            logger.debug(f"Error processing element: {e}")
            continue

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


def dump_results(conn: sqlite3.Connection, output_path: Path):
    """Export all scraped items to JSON."""
    rows = conn.execute(
        "SELECT source_name, source_type, url, title, extracted, category_focus, scraped_at FROM items ORDER BY scraped_at DESC"
    ).fetchall()

    items = []
    for row in rows:
        items.append({
            "source_name": row[0],
            "source_type": row[1],
            "url": row[2],
            "title": row[3],
            "extracted": json.loads(row[4]) if row[4] else {},
            "category_focus": row[5],
            "scraped_at": row[6],
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
        "--source",
        type=str,
        help="Scrape a single source by name (from sources.csv)",
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

    # Filter for weekly mode or single source
    if args.source:
        sources = [s for s in sources if s["source_name"] == args.source]
        if not sources:
            logger.error(f"Source '{args.source}' not found in sources.csv")
            sys.exit(1)

    if args.weekly:
        weekly_sources = [s for s in sources if s.get("update_frequency") == "weekly"]
        logger.info(f"Weekly mode: {len(weekly_sources)} of {len(sources)} sources eligible")
        sources = weekly_sources

    # Scrape
    total_new = 0
    for source in sources:
        try:
            new = scrape_source(source, conn, weekly_mode=args.weekly)
            total_new += new
            logger.info(f"  {source['source_name']}: {new} new items")
        except Exception as e:
            logger.error(f"  {source['source_name']}: FAILED — {e}")
        time.sleep(1.5)  # rate limiting

    logger.info(f"Total new items: {total_new}")

    # Export
    dump_results(conn, Path(args.output))
    conn.close()

    # Stats
    conn2 = sqlite3.connect(str(args.db))
    total = conn2.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    conn2.close()
    logger.info(f"Database total: {total} items")
    print(json.dumps({"status": "ok", "new_items": total_new, "db_total": total}))


if __name__ == "__main__":
    main()