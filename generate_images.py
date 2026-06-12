#!/usr/bin/env python3
"""Generate article illustration images using Agnes AI API (agnes-image-2.1-flash)."""

import os
import re
import sys
import time
import hashlib
import argparse
from pathlib import Path

import requests
import yaml

# --- Config ---
API_BASE = "https://apihub.agnes-ai.com/v1"
IMAGE_MODEL = "agnes-image-2.1-flash"
OUTPUT_DIR = "static/images/illustrations"
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds
RATE_LIMIT_DELAY = 2.0  # seconds between requests

# --- Category-specific style modifiers ---
CATEGORY_STYLES = {
    "crm": "professional business software dashboard, modern UI, clean corporate style, blue tones",
    "erp": "enterprise software system, data visualization, factory or warehouse background, industrial blue-gray palette",
    "comparisons": "side-by-side comparison concept, split screen design, professional SaaS interface, balanced composition",
    "project-management": "project timeline, task board, team collaboration concept, modern workspace, Kanban style",
    "hr": "human resources management, team culture, modern office, warm professional tones",
    "accounting": "financial charts, accounting ledgers, calculator, clean professional style, green-blue palette",
    "ecommerce": "online shopping interface, product showcase, digital marketplace, vibrant modern colors",
    "cybersecurity": "network security, shield concept, digital protection, dark blue tech aesthetic",
    "default": "professional business illustration, SaaS software concept, modern clean design, corporate style"
}


def get_api_key():
    """Get API key from environment variable."""
    key = os.environ.get("AGNES_API_KEY")
    if not key:
        print("ERROR: AGNES_API_KEY environment variable not set")
        sys.exit(1)
    return key


def parse_frontmatter(content):
    """Parse YAML frontmatter from markdown content.
    Returns (fm_dict_or_None, body)."""
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
    if not match:
        return None, content

    fm_text = match.group(1)
    body = content[match.end():]

    try:
        fm = yaml.safe_load(fm_text)
        if not isinstance(fm, dict):
            fm = {}
    except yaml.YAMLError:
        fm = {}
    return fm, body


def get_style_for_article(categories):
    """Get the visual style modifier based on article categories."""
    if not categories:
        return CATEGORY_STYLES["default"]

    cats = [c.lower().strip() for c in categories] if isinstance(categories, list) else [categories.lower().strip()]

    for cat in cats:
        cat_clean = cat.replace(" ", "-").replace("_", "-")
        if cat_clean in CATEGORY_STYLES:
            return CATEGORY_STYLES[cat_clean]

    return CATEGORY_STYLES["default"]


def build_prompt(title, description, categories):
    """Build an image generation prompt from article metadata."""
    style = get_style_for_article(categories)

    short_title = title[:80] if len(title) > 80 else title
    short_desc = (description[:120] + "...") if description and len(description) > 120 else (description or "")

    prompt = (
        f"{short_title}. "
        f"{short_desc} "
        f"Style: {style}. "
        f"No text, no letters, no typography, no watermarks. "
        f"High quality, detailed, 16:9 aspect ratio."
    )

    if len(prompt) > 450:
        prompt = prompt[:447] + "..."

    return prompt


def generate_image(prompt, api_key):
    """Call Agnes AI API to generate an image. Returns image bytes or None."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": IMAGE_MODEL,
        "prompt": prompt,
        "size": "1024x576",
        "n": 1,
    }

    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.post(
                f"{API_BASE}/images/generations",
                headers=headers,
                json=payload,
                timeout=120
            )

            if resp.status_code == 429:
                wait = RETRY_DELAY * (2 ** attempt)
                print(f"  Rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue

            resp.raise_for_status()
            result = resp.json()

            # Extract image URL
            img_url = result["data"][0]["url"]
            print(f"  Image URL: {img_url[:80]}...")

            # Download the actual image
            img_resp = requests.get(img_url, timeout=60)
            img_resp.raise_for_status()

            content_type = img_resp.headers.get("content-type", "")
            if content_type.startswith("image/"):
                return img_resp.content

            print(f"  Downloaded URL but got non-image: {content_type}")
            return None

        except requests.exceptions.Timeout:
            print(f"  Timeout on attempt {attempt + 1}")
            time.sleep(RETRY_DELAY)
        except Exception as e:
            print(f"  Error on attempt {attempt + 1}: {e}")
            time.sleep(RETRY_DELAY)

    return None


def has_images(body):
    """Check if article already has figure shortcodes with actual image paths."""
    pattern = r'\{\{<\s*figure\s+src="/images/illustrations/'
    return bool(re.search(pattern, body))


def insert_figure(body, slug, image_index, caption=""):
    """Insert a Hugo figure shortcode into the article body."""
    shortcode = (
        f'\n{{{{< figure src="/images/illustrations/{slug}-{image_index}.png" '
        f'caption="{caption}" alt="{caption}" >}}}}\n'
    )

    h2_match = re.search(r'\n##\s', body)
    if h2_match:
        insert_pos = h2_match.start()
    else:
        para_match = re.search(r'\n\n', body[200:])
        insert_pos = 200 + para_match.start() if para_match else len(body) // 2

    return body[:insert_pos] + shortcode + body[insert_pos:]


def process_article(filepath, api_key, dry_run=False):
    """Process a single article markdown file. Preserves original frontmatter."""
    slug = Path(filepath).stem
    slug_clean = re.sub(r'^\d{4}-\d{2}-\d{2}-', '', slug)

    with open(filepath, 'r', encoding='utf-8') as f:
        raw = f.read()

    # Extract frontmatter boundaries without YAML roundtrip.
    # Handles both standard (\n---\n) and malformed (\n---Text) closings,
    # and avoids matching horizontal rules in body.
    fm_end = 0
    if raw.startswith('---\n'):
        # Scan line by line from after opening ---\n
        pos = 4
        found_key = False
        while pos < len(raw):
            eol = raw.find('\n', pos)
            if eol == -1:
                eol = len(raw)
            line = raw[pos:eol].rstrip('\r')
            
            if line.startswith('---'):
                # Potential frontmatter closing
                if found_key:
                    # This is the closing: either '---' or '---Text'
                    fm_end = pos - 1  # position of the \n before this --- line
                    break
            elif line and not line.startswith('#'):
                # A non-empty, non-comment line that's not '---' - likely a YAML key
                if ':' in line or line.lstrip().startswith('-'):
                    found_key = True
            
            pos = eol + 1

    if fm_end <= 0:
        print(f"  SKIP {slug_clean}: no frontmatter")
        return None

    # fm_end points to \n before the closing --- line.
    # Find the end of the closing --- line (the next \n)
    eol_closing = raw.find('\n', fm_end + 1)
    if eol_closing == -1:
        eol_closing = len(raw)
    fm_end = eol_closing + 1  # skip past the closing --- line

    fm_block = raw[:fm_end]
    body = raw[fm_end:]

    # Check if already has images
    if has_images(body):
        print(f"  SKIP {slug_clean}: already has illustrations")
        return None

    # Parse frontmatter JUST for metadata (title, description, categories)
    # Extract between first ---\n and the closing --- marker
    fm_start = 4  # after opening ---\n
    fm_text_end = raw.rfind('\n---', fm_start, fm_end)
    if fm_text_end == -1:
        fm_text_end = fm_start + 10  # fallback
    fm_text = raw[fm_start:fm_text_end]
    title = slug_clean
    description = ""
    categories = []

    try:
        fm = yaml.safe_load(fm_text)
        if isinstance(fm, dict):
            title = fm.get("title", slug_clean)
            description = fm.get("description", "") or ""
            cats = fm.get("categories") or fm.get("tags") or []
            if isinstance(cats, str):
                categories = [cats]
            elif isinstance(cats, list):
                categories = cats
    except yaml.YAMLError:
        pass

    prompt = build_prompt(title, description, categories)
    print(f"  Prompt: {prompt[:100]}...")

    if dry_run:
        print(f"  [DRY RUN] Would generate image for: {slug_clean}")
        return slug_clean

    img_data = generate_image(prompt, api_key)
    if not img_data:
        print(f"  FAIL {slug_clean}: image generation failed")
        return None

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    img_path = os.path.join(OUTPUT_DIR, f"{slug_clean}-1.png")
    with open(img_path, 'wb') as f:
        f.write(img_data)
    print(f"  Saved: {img_path} ({len(img_data)} bytes)")

    caption = description[:150] if description else title[:100]
    fig = (
        f'\n{{{{< figure src="/images/illustrations/{slug_clean}-1.png" '
        f'caption="{caption}" alt="{caption}" >}}}}\n'
    )

    # Insert after first ## heading
    h2_match = re.search(r'\n##\s', body)
    if h2_match:
        insert_pos = h2_match.start()
    else:
        para_match = re.search(r'\n\n', body[100:])
        insert_pos = 100 + para_match.start() if para_match else len(body) // 2

    new_body = body[:insert_pos] + fig + body[insert_pos:]
    new_raw = fm_block + new_body

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_raw)

    return slug_clean
def main():
    parser = argparse.ArgumentParser(description="Generate article illustrations using Agnes AI")
    parser.add_argument("--dry-run", action="store_true", help="Preview without generating")
    parser.add_argument("--limit", type=int, default=0, help="Max articles to process (0 = all)")
    parser.add_argument("--slug", type=str, help="Process a specific article slug only")
    args = parser.parse_args()

    api_key = get_api_key()
    posts_dir = Path("content/posts")

    if not posts_dir.exists():
        print(f"ERROR: content/posts/ not found. Run from repo root.")
        sys.exit(1)

    articles = sorted([p for p in posts_dir.glob("*.md") if p.name != "_index.md"])

    if args.slug:
        articles = [p for p in articles if args.slug in p.stem]
        if not articles:
            print(f"No article found matching slug: {args.slug}")
            sys.exit(1)

    to_process = []
    for fp in articles:
        with open(fp, 'r', encoding='utf-8') as f:
            content = f.read()
        fm, body = parse_frontmatter(content)
        if not has_images(body):
            to_process.append(fp)

    print(f"Articles without illustrations: {len(to_process)}/{len(articles)}")

    if args.limit > 0:
        to_process = to_process[:args.limit]
        print(f"Limited to {len(to_process)} articles")

    success = 0
    fail = 0

    for i, fp in enumerate(to_process, 1):
        print(f"\n[{i}/{len(to_process)}] {fp.name}")
        result = process_article(str(fp), api_key, dry_run=args.dry_run)
        if result:
            success += 1
        elif result is None and not args.dry_run:
            fail += 1

        if i < len(to_process):
            time.sleep(RATE_LIMIT_DELAY)

    print(f"\n=== DONE ===")
    print(f"Success: {success}")
    print(f"Failed: {fail}")
    print(f"Skipped: {len(articles) - len(to_process)}")


if __name__ == "__main__":
    main()
