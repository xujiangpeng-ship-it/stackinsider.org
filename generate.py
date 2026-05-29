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

# ========== 专业软件评测 Prompt ==========
prompt = f"""
You are a senior software analyst with 15+ years of experience evaluating business tools for enterprises and SMBs. Write an in-depth, unbiased review based on the keyword "{keyword}".

Think like an analyst from Gartner or Forrester: your analysis must be data-driven, practical, and free of hype. Avoid generic phrases like "In today's rapidly evolving landscape", "game-changer", "revolutionary", or "delve into". Never start with a broad statement. Open with a specific pain point, a pricing surprise, or a contrarian insight.

Structure:
1. YAML metadata block:
---
title: "A specific, benefit-driven title that includes the keyword naturally"
date: {today}
slug: "auto-generated-english-slug-based-on-keyword"
draft: false
tags: ["Choose 2-3 from: 'CRM', 'ERP', 'Project Management', 'Comparisons'"]
description: "An SEO-friendly description under 160 chars summarizing the review"
---

2. Body (Markdown, no level-1 heading – start with an intro paragraph):
   - Use H2 and H3 for sections like "Pricing & Total Cost of Ownership", "Key Features & Differentiators", "Implementation Complexity", "Who Should NOT Use This Tool?"
   - Include a comparison table (Markdown) with at least 4 rows and 4 columns, contrasting features, pricing, ideal user size, and a notable strength/weakness.
   - Cite at least 2 real user reviews or analyst ratings from G2, Capterra, or Gartner Peer Insights, with year.
   - Mention at least 2 specific capabilities (e.g., workflow automation, reporting, integrations) and why they matter.
   - Provide balanced analysis: advantages AND limitations, implementation hurdles, hidden costs.
   - End with a "Bottom Line" section: concrete recommendation based on company size, budget, and industry.
   - Tone: confident, direct, slightly conversational. Mix short and long paragraphs. Use contractions occasionally. No bullet lists longer than 4 items.

3. No code blocks, system prompts, or extra commentary. Output ONLY the complete Markdown article from "---" to the last line.
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

# ========== 清理异常输出（修复代码块问题）==========
if article_text.startswith('```'):
    first_block_end = article_text.find('\n', article_text.find('```') + 3)
    if first_block_end != -1:
        last_block_start = article_text.rfind('```')
        if last_block_start > first_block_end:
            article_text = article_text[first_block_end+1:last_block_start].strip()
        else:
            article_text = article_text[first_block_end+1:].strip()
    else:
        article_text = article_text[3:].strip()

article_text = re.sub(r'^CITATION FORMAT.*?(\n\n|$)', '', article_text, flags=re.IGNORECASE)
article_text = re.sub(r'^TOOLS[\s\S]*?(\n\n|$)', '', article_text, flags=re.IGNORECASE)
article_text = re.sub(r'^<[^>]+>.*?(\n\n|$)', '', article_text, flags=re.IGNORECASE)
article_text = re.sub(r'^# .+\n\n?', '', article_text, count=1)
article_text = article_text.lstrip()

print(f"📝 Cleaned article length: {len(article_text)}")

if len(article_text) < 200:
    print(f"⚠️ Article body too short ({len(article_text)} chars). Raw text preview: {article_text[:200]}")
    print("⛔ Skipping this generation. Check API response or Prompt.")
    exit(1)

# ========== 确保 front matter 包含 description ==========
def ensure_description(text, keyword, today):
    """如果元数据缺少 description，自动补充一个合理的默认值"""
    parts = text.split('---', 2)
    if len(parts) >= 3:
        fm = parts[1]
        body = parts[2]
        # 检查是否有 description 字段，且不为空
        desc_match = re.search(r'^description:\s*(.*)$', fm, re.MULTILINE)
        if not desc_match or not desc_match.group(1).strip():
            # 缺少或为空，插入一条默认描述
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
