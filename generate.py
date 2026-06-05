#!/usr/bin/env python3
"""
generate_v2.py — Improved version of generate.py with:
  1. Information Gain injection (verifiable data point requirement)
  2. H2 heading randomization (variants for Pricing / Features / Limitations)
  3. Original angle (insight that wouldn't appear on vendor's own site)

Only the prompt section is modified; all other logic (API calls, cleanup, IndexNow) is unchanged.
"""

import os
import datetime
import re
import time
import requests
from openai import OpenAI

# ========== 配置 ==========
SITE_URL = "https://stackinsider.org"
INDEXNOW_KEY = os.environ.get('INDEXNOW_KEY')

api_key = os.environ.get('MISTRAL_API_KEY')
if not api_key:
    raise ValueError("MISTRAL_API_KEY not found. Please check your GitHub Secrets.")

client = OpenAI(
    api_key=api_key,
    base_url="https://api.mistral.ai/v1"
)
MODEL_NAME = "mistral-large-latest"

# ========== 100 个 B2B SaaS 高价值关键词库 ==========
keywords = [
    # === CRM (20) ===
    "best CRM for small business 2026",
    "HubSpot vs Salesforce pricing comparison",
    "free CRM with email integration",
    "best CRM for real estate agents",
    "Zoho CRM review and pricing",
    "Pipedrive vs HubSpot features",
    "best CRM for startups 2026",
    "Salesforce alternatives for SMBs",
    "CRM with AI features 2026",
    "best CRM for consultants",
    "Freshsales vs Zoho CRM",
    "best CRM for ecommerce",
    "Copper CRM review for G Suite users",
    "best CRM for SaaS companies",
    "less annoying CRM pricing and review",
    "best open source CRM 2026",
    "CRM for manufacturing industry",
    "best CRM for financial services",
    "Agile CRM vs Bitrix24",
    "Keap vs ActiveCampaign CRM",

    # === ERP (20) ===
    "best ERP for manufacturing 2026",
    "NetSuite vs SAP Business One pricing",
    "best cloud ERP for small business",
    "Acumatica vs Microsoft Dynamics 365",
    "best ERP for discrete manufacturing",
    "Plex vs JobBOSS for job shops",
    "best ERP for process manufacturing",
    "Odoo vs ERPNext for small manufacturers",
    "ERP selection guide for SMBs",
    "Sage X3 vs Infor CloudSuite",
    "best ERP for construction companies",
    "ERP implementation costs 2026",
    "best open source ERP 2026",
    "ERP for food and beverage industry",
    "Rootstock vs Salesforce Manufacturing Cloud",
    "best ERP for wholesale distribution",
    "Syspro vs Epicor for manufacturing",
    "MRPeasy vs Katana for small shops",
    "best ERP for medical device manufacturing",
    "QAD Adaptive ERP vs Aptean ERP",

    # === Project Management (20) ===
    "best project management software 2026",
    "Asana vs Monday.com vs Wrike",
    "best PM tool for remote teams",
    "ClickUp vs Notion for project management",
    "best agile project management tools",
    "Jira alternatives for small teams",
    "best free project management software",
    "Smartsheet vs Airtable for PM",
    "best construction project management software",
    "Basecamp vs Teamwork features",
    "best PM for marketing teams",
    "resource management tools with time tracking",
    "best Kanban boards 2026",
    "best PM for software development",
    "best PM for creative agencies",
    "Linear vs Linear.app for dev teams",
    "best PM for freelancers",
    "best PM with Gantt charts",
    "best PM for enterprise 2026",
    "Zoho Projects vs Wrike pricing",

    # === Accounting & Finance (20) ===
    "best accounting software for small business 2026",
    "QuickBooks vs Xero features comparison",
    "free invoicing software for freelancers",
    "best accounting software for ecommerce",
    "FreshBooks vs Wave accounting",
    "best accounting software for startups",
    "best expense tracking apps 2026",
    "best accounting software for nonprofits",
    "Sage vs QuickBooks for SMBs",
    "best accounting software for rental properties",
    "best bookkeeping software 2026",
    "best accounting software for consultants",
    "best accounts payable automation software",
    "best budgeting and forecasting software",
    "best accounting software for construction",
    "best accounting software for manufacturing",
    "best accounting software for SaaS companies",
    "best payroll software integrated with accounting",
    "best free accounting software UK 2026",
    "best accounting software for Amazon sellers",

    # === HR & Talent (20) ===
    "best HR software for small business 2026",
    "BambooHR vs Gusto pricing",
    "best applicant tracking system 2026",
    "best onboarding software for remote teams",
    "best performance management software",
    "best HRIS for startups",
    "best payroll software 2026",
    "best employee engagement software",
    "best time and attendance software",
    "best workforce management software",
    "Rippling vs Gusto for all-in-one HR",
    "best HR software for manufacturing",
    "best HR software for healthcare",
    "best free HR software 2026",
    "best HR analytics tools 2026",
    "best learning management system for SMBs",
    "best benefits administration software",
    "best PEO services for small business",
    "best HR compliance software",
    "best HR chatbot for employee self-service"
]

# ========== 关键词轮换 ==========
INDEX_FILE = "keyword_index.txt"
if os.path.exists(INDEX_FILE):
    with open(INDEX_FILE, "r") as f:
        try:
            index = int(f.read().strip())
        except:
            index = 0
else:
    index = 0

keyword = keywords[index % len(keywords)]
next_index = (index + 1) % len(keywords)

with open(INDEX_FILE, "w") as f:
    f.write(str(next_index))

today = datetime.date.today().strftime("%Y-%m-%d")

# ========== 专业软件评测 Prompt (v2 — enhanced with Information Gain, H2 variants, Original angle) ==========
prompt = f"""
You are a B2B software consultant who has actually evaluated, implemented, and migrated business tools for real teams. Write a practical, honest review based on the keyword "{keyword}".

CRITICAL — AVOID THESE AI-GENERATED PATTERNS:
- Banned words/phrases: "delve into", "unlock", "unleash", "harness", "game-changer", "revolutionary", "ever-evolving landscape", "navigate the complexities", "cut through the noise", "in today's digital age", "comprehensive guide", "deep dive", "robust solution", "seamlessly", "unparalleled", "embark on", "tapestry", "realm", "daunting"
- Do NOT open with a broad industry statement. Start with a pricing gotcha, a specific workflow frustration this software does or doesn't solve, or a strong opinion.
- Do NOT end with "In conclusion", "To sum up", "Bottom Line", or "Wrapping up". End naturally — one or two sentences that leave the reader with a clear takeaway.
- Vary paragraph size. Some paragraphs should be a single sentence. Avoid three-paragraph blocks strung together.
- No bullet lists longer than 4 items. Use prose when possible.

INFORMATION GAIN (v2 — CRITICAL):
This article MUST include at least 1 real, verifiable data point that is NOT easily found in the top 5 Google results. Examples: a specific pricing tier from the vendor's official site, an actual G2 rating score with date, a known integration limitation documented in official docs, or a timeline of a recent product update. DO NOT fabricate data — only use information you are confident is accurate. If uncertain, frame the insight as a general observation rather than a fake statistic.

ORIGINAL ANGLE (v2 — CRITICAL):
Provide at least one insight or observation that would not appear on the vendor's official website — such as community sentiment from forums, integration friction reported by users, a limitation the marketing pages gloss over, or a use case where another tool is clearly better.

CONTENT GUIDELINES:
1. YAML metadata block (no level-1 heading in body):
---
title: "Specific, benefit-driven title including the keyword naturally"
date: {today}
slug: "auto-generated-english-slug"
draft: false
tags: ["Choose 2-3 from: CRM, ERP, Project Management, Comparisons"]
description: "SEO description under 160 chars summarizing the review"
---

2. Body structure (Markdown):
   - Use ## (H2) for main sections, ### (H3) for sub-sections. Never use ### as top-level.
   - H2 heading variants (v2): Instead of fixed labels, pick one variant naturally from the sets below based on what fits the article flow:
     * For pricing sections: "What You'll Actually Pay" / "Pricing Tiers and Hidden Costs" / "Is It Worth the Money?" / "Breaking Down the Pricing"
     * For feature sections: "What Sets It Apart" / "Features That Actually Matter" / "Where It Shines (and Where It Doesn't)"
     * For limitation sections: "The Rough Edges" / "What Users Complain About" / "Where It Falls Short"
   - Include at least one comparison element — table or structured breakdown — contrasting alternatives on pricing, features, and practical fit for different team sizes. At least 4 rows.
   - Highlight 2-3 specific features with real-world context. Don't just name them — explain what a team actually gains or loses using them daily.
   - Cover genuine strengths AND real limitations. Be specific: "The mobile app lacks offline mode" beats "Mobile experience has room for improvement."
   - Include one insight unlikely to appear on the vendor's own site: hidden costs, integration friction, migration effort, or what the user community complains about.
   - End with a grounded recommendation suitable for a specific reader profile (company size, budget, industry). No formal conclusion header — weave it into the closing paragraph.

3. Tone: confident, direct, conversational. Like explaining to a colleague. Use contractions. No marketing-speak. Back claims with details, not adjectives.

4. Output ONLY the Markdown article from "---" to the last line. No commentary, no code blocks outside the article.
"""

# ========== API 调用（重试+超时）==========
MAX_RETRIES = 3
RETRY_DELAY = 10
TIMEOUT_SECONDS = 600

article_text = None
for attempt in range(1, MAX_RETRIES + 1):
    try:
        print(f"🔁 Attempt {attempt} / {MAX_RETRIES} ...")
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.75,
            max_tokens=3000,
            timeout=TIMEOUT_SECONDS,
        )
        article_text = response.choices[0].message.content.strip()
        print(f"📝 Raw API response length: {len(article_text)}")
        print("✅ API call succeeded.")
        break
    except Exception as e:
        print(f"❌ Attempt {attempt} failed: {e}")
        if attempt < MAX_RETRIES:
            wait = RETRY_DELAY * (2 ** (attempt - 1))
            print(f"⏳ Retrying in {wait} seconds...")
            time.sleep(wait)
        else:
            print("⛔ All retries exhausted. Exiting.")
            exit(1)

# ========== 清理异常输出 ==========
# Step 0: dump raw response for debugging
print(f"📝 Raw length: {len(article_text)}")
print(f"📝 Raw first 800 chars:\n{article_text[:800]}")
print(f"📝 Raw last 400 chars:\n{article_text[-400:]}")

# Step 1: strip outermost ``` fences only
# Strategy: if starts with ```, strip opening fence line.
# For closing, scan from END backwards to find the LAST ``` that is on its own line.
if article_text.startswith('```'):
    first_nl = article_text.find('\n')
    if first_nl != -1:
        article_text = article_text[first_nl+1:]
    else:
        article_text = article_text[3:]
    
    # Strip trailing ``` only if it's the last non-whitespace content
    stripped = article_text.rstrip()
    if stripped.endswith('```'):
        article_text = stripped[:-3].rstrip()
    
    article_text = article_text.strip()
    print(f"📝 After fence strip: {len(article_text)} chars")

# Step 2: if article starts with '{' or '[' (JSON), extract from known fields
if article_text.startswith('{') or article_text.startswith('['):
    print("📝 Detected JSON response, attempting to extract fields...")
    import json as json_mod
    try:
        obj = json_mod.loads(article_text)
        if isinstance(obj, dict):
            # Try to reconstruct as markdown front matter + body
            title = obj.get('title', obj.get('Title', ''))
            date_str = obj.get('date', obj.get('Date', today))
            slug = obj.get('slug', obj.get('Slug', ''))
            tags = obj.get('tags', obj.get('Tags', []))
            desc = obj.get('description', obj.get('Description', ''))
            body = obj.get('body', obj.get('Body', obj.get('content', obj.get('Content', ''))))
            
            if body:
                article_text = f"---\ntitle: \"{title}\"\ndate: {date_str}\nslug: \"{slug}\"\ndraft: false\ntags: {json_mod.dumps(tags)}\ndescription: \"{desc}\"\n---\n\n{body}"
                print(f"📝 Reconstructed from JSON: {len(article_text)} chars")
    except Exception as e:
        print(f"📝 JSON parse failed: {e}")

# Step 3: if still no '---', search for front matter markers
if not article_text.startswith('---'):
    fm_start = article_text.find('\n---\n')
    if fm_start == -1:
        fm_start = article_text.find('---')
    if fm_start != -1:
        article_text = article_text[fm_start:].strip()
        print(f"📝 Located front matter at offset {fm_start}")

# Step 3.5: remove stray ``` between frontmatter closing --- and body
# Mistral sometimes outputs: ---\n```\n real body ... despite "No code blocks" in prompt
article_text = re.sub(r'(---)\n```\n', r'\1\n', article_text, count=1)

# Step 4: trim trailing junk after article
article_text = article_text.strip()

print(f"📝 Cleaned article length: {len(article_text)}")

# Step 5: validate body content
parts = article_text.split('---', 2)
if len(parts) < 3:
    print(f"⚠️ Missing front matter closure (---). Raw preview:")
    print(article_text[:500])
    print("⛔ Skipping.")
    exit(1)

fm = parts[1]
body_only = parts[2].strip()

print(f"📝 Front matter: {len(fm)} chars")
print(f"📝 Body: {len(body_only)} chars")

if len(body_only) < 100:
    print(f"⚠️ Article body too short ({len(body_only)} chars).")
    print("--- RAW RESPONSE (first 500) ---")
    print(article_text[:500])
    print("--- RAW RESPONSE (last 500) ---")
    print(article_text[-500:])
    print("⛔ Skipping this generation.")
    exit(1)

# ========== 确保 front matter 包含 description ==========
def ensure_description(text, keyword, today):
    """Auto-fill a reasonable default description if front matter is missing one"""
    parts = text.split('---', 2)
    if len(parts) >= 3:
        fm = parts[1]
        body = parts[2]
        # Check if description field exists and is not empty
        desc_match = re.search(r'^description:\s*(.*)$', fm, re.MULTILINE)
        if not desc_match or not desc_match.group(1).strip():
            # Missing or empty, insert default description
            default_desc = f"In-depth comparison and review of {keyword}. Expert analysis, pricing, features, and recommendations for 2026."
            if desc_match:
                # 替换空描述
                fm = re.sub(r'^description:\s*.*$', f'description: "{default_desc}"', fm, flags=re.MULTILINE)
            else:
                # 在 slug 或 tags 之后添加
                fm = fm.rstrip() + f'\ndescription: "{default_desc}"'
            text = f"---{fm}---\n{body}"
    return text

article_text = ensure_description(article_text, keyword, today)

# ========== 兜底元数据（如果完全没有 front matter）==========
if not article_text.startswith('---'):
    slug = re.sub(r'[^a-z0-9]+', '-', keyword.strip().lower())[:50]
    header = f"""---
title: "Deep Dive: {keyword.title()}"
date: {today}
slug: "{slug}"
draft: false
tags: ["Comparisons"]
description: "In-depth analysis of {keyword}."
---
"""
    article_text = header + "\n" + article_text

slug_part = re.sub(r'[^a-z0-9]+', '-', keyword.strip().lower())[:50]
filename = f"{today}-{slug_part}.md"
filepath = os.path.join("content", "posts", filename)

os.makedirs(os.path.dirname(filepath), exist_ok=True)

with open(filepath, "w", encoding="utf-8") as f:
    f.write(article_text)

print(f"📌 Current keyword: {keyword}")
print(f"📌 Next index: {next_index}")
print(f"✅ Article generated: {filepath}")

# ========== IndexNow 提交 ==========
def submit_indexnow(article_url):
    if not INDEXNOW_KEY:
        print("⚠️ INDEXNOW_KEY not set, skipping IndexNow submission.")
        return
    url = f"https://www.bing.com/indexnow?url={article_url}&key={INDEXNOW_KEY}"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code in [200, 202]:
            print(f"✅ IndexNow submitted: {article_url} (status {r.status_code})")
        else:
            print(f"⚠️ IndexNow returned status {r.status_code}")
    except Exception as e:
        print(f"❌ IndexNow submission failed: {e}")

article_url = f"{SITE_URL}/posts/{slug_part}/"
submit_indexnow(article_url)
