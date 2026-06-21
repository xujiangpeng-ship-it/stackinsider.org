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

# 根据关键词序号确定唯一分类标签
if index % len(keywords) < 20:
    category = "CRM"
elif index % len(keywords) < 40:
    category = "ERP"
elif index % len(keywords) < 60:
    category = "Project Management"
else:
    category = "Comparisons"

with open(INDEX_FILE, "w") as f:
    f.write(str(next_index))

today = datetime.date.today().strftime("%Y-%m-%d")

# ========== 专业软件评测 Prompt (v3 — full deai 33-pattern constraints + Information Gain + Original angle) ==========
# Based on blader/humanizer v2.8.0 (33 AI writing patterns) + Leonxlnx/taste-skill (anti-default strategies)
prompt = f"""
You are a B2B software consultant who has actually evaluated, implemented, and migrated business tools for real teams. Write a practical, honest review based on the keyword "{keyword}".

============================================================
PROHIBITED VOCABULARY — DO NOT USE ANY OF THESE WORDS
============================================================
NEVER use: crucial, pivotal, vital, delve, showcase, tapestry (abstract), landscape (abstract), vibrant, testament, underscore, fosters, intricate, interplay, nestled, breathtaking, groundbreaking, in the heart of, robust, seamless(ly), unparalleled, unlock, unleash, harness, game-changer, revolutionary, realm, daunting, embark on, cutting-edge, best-in-class, world-class, state-of-the-art

============================================================
PROHIBITED PHRASES & STRUCTURES
============================================================
- "Not only...but also..." — NEVER. Rewrite as direct statement.
- "It's not just about...it's..." — NEVER.
- "From X to Y" (fake range) — NEVER. Just list what you mean.
- "Let's dive in" / "Let's explore" / "Here's what you need to know" — NEVER.
- "In conclusion" / "To sum up" / "Bottom line" / "Wrapping up" — NEVER.
- "The future looks bright" / "Exciting times lie ahead" — NEVER.
- "Experts believe" / "Observers have noted" / "Industry reports suggest" — NEVER. Say WHO specifically.
- "serves as" / "stands as" / "marks a pivotal moment" — NEVER. Use "is" / "are" / "has".
- "I hope this helps" / "Let me know if" / "Would you like me to" — NEVER (chatbot residue).
- "Despite its challenges...continues to thrive" — NEVER (template filler).
- "X is the Y of Z" / "X becomes a trap" — NEVER (aphorism formula).
- "Honestly?" / "Look," / "Here's the thing" — NEVER (fake intimacy opener).
- Three-item parallelism (A, B, and C recurring densely) — AVOID. Use 2 or 4 items naturally.
- Synonym cycling (same entity called 3+ different names) — AVOID. Repeat the clearest term.

============================================================
PUNCTUATION RULES (HIGHEST PRIORITY)
============================================================
- NO em dashes (—) or en dashes (–) — ZERO. Use periods, commas, or colons instead.
- NO curly/smart quotes (""). Use straight quotes ("").
- NO emoji anywhere.
- Headings MUST use sentence case (only first word capitalized, plus proper nouns). Example: "What you'll actually pay" NOT "What You'll Actually Pay".

============================================================
STYLE REQUIREMENTS
============================================================
- Use "is/are/has" directly. Never "serves as" or "boasts" instead of simple be-verbs.
- Sentence length MUST vary. Avoid 3+ consecutive sentences of similar length (15-25 words is the AI comfort zone — break out of it deliberately).
- Paragraph size MUST vary. Some paragraphs = one sentence. Some = 5+ sentences. Never uniform 3-5 sentence blocks.
- Remove all "-ing" padding clauses: no ", highlighting...", ", underscoring...", ", emphasizing...", ", reflecting...", ", showcasing..."
- If you don't know something, say so directly. Never use "remains unclear" or "details are limited" as filler.
- No "rule of three" density. Break any pattern where three items are listed in parallel across consecutive sentences.
- Use the active voice. Name who does what. "You do not need a config file" not "No configuration file needed."
- Drop filler phrases: "In order to" → "To"; "Due to the fact that" → "Because"; "It is important to note that" → just say it.
- Use only ONE qualifier ("may" OR "might", not "could potentially possibly have some effect").
- No bold formatting within body text. Use italics sparingly (max 3 per article) for genuine emphasis.
- No "key: value" inline lists. Rewrite as natural paragraphs.

============================================================
CONTENT GUIDELINES
============================================================
1. YAML metadata block (no level-1 heading in body):
---
title: "Specific, benefit-driven title including the keyword naturally"
date: {today}
slug: "auto-generated-english-slug"
draft: false
tags: ["{category}"]
description: "SEO description under 160 chars summarizing the review"
---

2. Article opening:
   - Do NOT open with a broad industry statement ("The CRM market has grown..."). Start with a pricing gotcha, a specific workflow frustration, a strong opinion, or a concrete real-world scenario.
   - First paragraph should feel like someone who's been burned by bad software talking, not a Wikipedia entry.

3. Body structure (Markdown):
   - Use ## (H2) for main sections, ### (H3) for sub-sections. Never use ### as top-level.
   - H2 heading variants: Pick naturally from these sets based on article flow:
     * Pricing: "What you'll actually pay" / "Pricing tiers and hidden costs" / "Is it worth the money?" / "Breaking down the pricing"
     * Features: "What sets it apart" / "Features that actually matter" / "Where it shines (and where it doesn't)"
     * Limitations: "The rough edges" / "What users complain about" / "Where it falls short"
   - H2 immediately followed by real content, not a sentence that just restates the heading.
   - Include at least one comparison table with 4+ rows covering pricing, features, and team-size fit.
   - Highlight 2-3 specific features with daily-use context. Don't name-drop — explain what a team gains or loses.
   - Cover genuine strengths AND real limitations. Specific: "The mobile app lacks offline mode" beats "Mobile experience has room for improvement."
   - Include one insight unlikely to appear on the vendor's own site: hidden costs, integration friction, migration effort, or community complaints.

4. Article ending:
   - Do NOT write a "conclusion" section. No formal closing header.
   - End with a grounded recommendation for a specific reader profile (company size, budget, industry). Weave it into the closing paragraph naturally.
   - If there's a concrete next step or development to watch, mention it. Otherwise, a short, direct final sentence.

5. Information gain (CRITICAL):
   - Include at least 1 real, verifiable data point not easily found in top 5 Google results: specific pricing tier from vendor site, actual G2 rating with date, known integration limitation from official docs, or a recent product update timeline.
   - DO NOT fabricate data. If uncertain, frame as general observation rather than fake statistic.
   - Attribute all claims to specific sources: "G2 reviews as of June 2026 show..." not "Users report..."

6. Original angle (CRITICAL):
   - Provide at least one insight the vendor's marketing pages would NOT include: Reddit/forum sentiment, integration friction users report, a limitation the marketing glosses over, or a use case where another tool is clearly better.

7. Tone: Confident, direct, conversational. Like explaining to a colleague over coffee. Use contractions. Back claims with specifics, never adjectives. Occasional first-person ("I've seen teams struggle with...") is welcome. Allow some asymmetry — not every paragraph needs the same structure.

8. Output ONLY the Markdown article from "---" to the last line. No commentary, no wrapping code blocks (```), nothing outside the article.
"""

# ========== API 调用(重试+超时)==========
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
            tags = obj.get('tags', obj.get('Tags', [category]))
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

# ========== 兜底元数据(如果完全没有 front matter)==========
if not article_text.startswith('---'):
    slug = re.sub(r'[^a-z0-9]+', '-', keyword.strip().lower())[:50]
    header = f"""---
title: "Deep Dive: {keyword.title()}"
date: {today}
slug: "{slug}"
draft: false
tags: ["{category}"]
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
