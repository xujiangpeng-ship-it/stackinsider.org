#!/usr/bin/env python3
"""
citation_check.py — Citation verification layer.

Extracts citations from generated report text using 4 regex patterns,
cross-references against verified_sources.json whitelist, and flags
unsupported or fabricated claims.

Output: JSON report with matched/unmatched/uncertain citations.

Author: stackinsider.org pipeline
"""

import argparse
import json
import logging
import re
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("citation_check")

BASE_DIR = Path(__file__).resolve().parent
VERIFIED_SOURCES = BASE_DIR / "verified_sources.json"

# ---------------------------------------------------------------------------
# 4 Citation Extraction Patterns
# ---------------------------------------------------------------------------

CITATION_PATTERNS = [
    # Pattern 1: "According to [Publisher], ..."
    re.compile(
        r"(?:According to|Per|As reported by|As noted by)\s+([A-Z][A-Za-z\s&]+(?:Gartner|Forrester|IDC|G2|Nucleus|Bessemer|McKinsey|Deloitte|Accenture|BCG|Bain)[A-Za-z\s]*)",
        re.IGNORECASE,
    ),
    # Pattern 2: "[Publisher]'s [Report] found that ..."
    re.compile(
        r"(Gartner|Forrester|IDC|G2|Nucleus\s+Research|Bessemer\s+Venture\s+Partners)[\'’]s?\s+(?:report|study|analysis|survey|Magic Quadrant|Wave|MarketScape|Grid)",
        re.IGNORECASE,
    ),
    # Pattern 3: "[Number]% according to [Publisher]"
    re.compile(
        r"(\d+(?:\.\d+)?%)\s+(?:according to|per|based on|from)\s+([A-Z][A-Za-z\s&]+(?:Gartner|Forrester|IDC|G2|Nucleus|Bessemer))",
        re.IGNORECASE,
    ),
    # Pattern 4: "The [Year] [Publisher] [Report Type]"
    re.compile(
        r"(?:the\s+)?(20\d{2})\s+(Gartner|Forrester|IDC|G2|Nucleus)\s+(Magic\s+Quadrant|Wave|MarketScape|Grid|Hype\s+Cycle|Market\s+Guide|FutureScape)",
        re.IGNORECASE,
    ),
]

# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def extract_citations(text: str) -> list:
    """Extract all citation-like references from report text."""
    citations = []

    for pattern in CITATION_PATTERNS:
        for match in pattern.finditer(text):
            citations.append({
                "text": match.group(0).strip()[:200],
                "span_start": match.start(),
                "span_end": match.end(),
                "pattern_type": CITATION_PATTERNS.index(pattern) + 1,
            })

    # Deduplicate by text
    seen = set()
    unique = []
    for c in citations:
        if c["text"].lower() not in seen:
            seen.add(c["text"].lower())
            unique.append(c)

    return sorted(unique, key=lambda x: x["span_start"])


def cross_reference(citations: list, verified_sources: list) -> dict:
    """
    Cross-reference extracted citations against verified sources whitelist.
    Returns dict with matched, unmatched, and uncertain classifications.
    """
    # Build lookup: normalized publisher name -> list of sources
    publisher_lookup = {}
    for src in verified_sources:
        pub = src["publisher"].lower()
        publisher_lookup.setdefault(pub, []).append(src)

    matched = []
    unmatched = []
    uncertain = []

    for cit in citations:
        text_lower = cit["text"].lower()
        found = False

        # Try exact publisher match
        for pub_name, sources in publisher_lookup.items():
            if pub_name in text_lower:
                # Check if year also matches (if year present in citation)
                year_match = re.search(r"(20\d{2})", cit["text"])
                cit_year = int(year_match.group(1)) if year_match else None

                if cit_year:
                    year_sources = [s for s in sources if s.get("year") == cit_year]
                    if year_sources:
                        matched.append({**cit, "matched_sources": [s["id"] for s in year_sources]})
                        found = True
                        break
                else:
                    matched.append({**cit, "matched_sources": [s["id"] for s in sources[:3]]})
                    found = True
                    break

        if not found:
            # Check for partial matches
            for pub_name in publisher_lookup:
                pub_words = set(pub_name.split())
                text_words = set(text_lower.split())
                if len(pub_words & text_words) >= 2:
                    uncertain.append({**cit, "partial_match": pub_name})
                    found = True
                    break

        if not found:
            unmatched.append(cit)

    return {
        "matched": matched,
        "unmatched": unmatched,
        "uncertain": uncertain,
        "summary": {
            "total": len(citations),
            "matched": len(matched),
            "unmatched": len(unmatched),
            "uncertain": len(uncertain),
            "match_rate": round(len(matched) / max(len(citations), 1) * 100, 1),
        },
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def check_citations(report_path: str, output_path: str = None) -> dict:
    """Main entry: extract and cross-reference citations from a report."""
    with open(report_path, "r", encoding="utf-8") as f:
        text = f.read()

    with open(VERIFIED_SOURCES, "r", encoding="utf-8") as f:
        verified_data = json.load(f)
    verified_sources = verified_data.get("sources", [])

    logger.info(f"Extracting citations from {report_path}")
    citations = extract_citations(text)
    logger.info(f"Found {len(citations)} citation references")

    result = cross_reference(citations, verified_sources)

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        logger.info(f"Results written to {output_path}")
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Citation verification for generated reports")
    parser.add_argument("report", help="Path to the report Markdown file")
    parser.add_argument("-o", "--output", help="Output JSON path (default: stdout)")
    parser.add_argument(
        "--max-unmatched",
        type=int,
        default=3,
        help="Maximum allowed unmatched citations before failing (default: 3)",
    )
    args = parser.parse_args()

    result = check_citations(args.report, args.output)
    summary = result["summary"]

    if summary["unmatched"] > args.max_unmatched:
        logger.error(
            f"FAILED: {summary['unmatched']} unmatched citations (max allowed: {args.max_unmatched})"
        )
        sys.exit(1)

    logger.info(f"PASSED: {summary['match_rate']}% match rate, {summary['unmatched']} unmatched")
    sys.exit(0)