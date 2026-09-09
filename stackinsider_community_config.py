# -*- coding: utf-8 -*-
"""
stackinsider_community_config.py — stackinsider.org 的社区视角源配置

站点垂直：B2B 软件评测（CRM / ERP / 会计 / 项目管理 / SaaS 对比）。
供 inject_community_stackinsider.py 调用
community_sources.fetch_reddit_scrapecreators(query, preferred=..., blocked=...) 使用。

注意：stackinsider 用 Hugo 渲染 Markdown，且每日 cleanup_ai_artifacts.py 会删掉以 '<' 开头的行。
因此社区区块必须渲染成「纯 Markdown」（行首绝不以 '<' 开头），才能活过清理脚本。
"""
from __future__ import annotations
import re

# 板块白名单：覆盖真实 B2B 软件讨论板块（含产品板块 r/Zoho、r/CRMSoftware 等）。
# 全部小写；fetch_reddit_scrapecreators 会把返回 subreddit 转小写后比对。
PREFERRED_SUBS = {
    "zoho", "crmsoftware", "crm", "salesforce", "hubspot", "sales", "saas",
    "smallbusiness", "entrepreneur", "startups", "accounting", "bookkeeping",
    "erp", "projectmanagement", "productmanagement", "quickbooks", "xero",
    "netsuite", "sap", "workday", "asana", "mondaydotcom", "notion", "slack",
    "atlassian", "software", "tech", "technology", "recruiting",
    "humanresources", "productivity", "supplychain", "manufacturing", "tax",
}

# 与软件评测无关的板块，必须滤掉（避免召回无关/低质讨论）
BLOCKED_SUBS = {
    "scams", "personalfinance", "legaladvice", "relationships", "askreddit",
    "offmychest", "nostupidquestions", "ama", "conspiracy", "worldnews",
    "politics", "tifu", "casualconversation",
}

# 相关性过滤时忽略的泛化词（这些词出现不代表与主题相关）
GENERIC_TOKENS = {
    "software", "tools", "tool", "app", "apps", "system", "systems",
    "solution", "solutions", "platform", "best", "top", "good", "free",
    "review", "reviews", "vs", "and", "the", "for", "small", "business",
}

STOP_YEAR = re.compile(r"\b20\d\d\b")


def derive_tool(title: str) -> str:
    """从标题推导工具/主题名。"""
    base = title.split(":")[0].split("—")[0].strip()
    parts = re.split(r"\s+(Review|vs\.?|Pricing|&)\b", base, flags=re.I)
    name = parts[0].strip() if parts else base.strip()
    name = re.sub(r"\s+(Review|Pricing|vs\.?|&)\b.*$", "", name, flags=re.I).strip()
    return name or base.strip()


def query_for_post(title: str, categories: list) -> tuple[str, str]:
    """返回 (检索词, 主题标签)。

    - 具体产品（Zoho CRM / NetSuite）→ 用产品名检索，最相关。
    - "Best X" 型汇总 → 提炼名词（如 "accounting software"），去掉年份与 "for small business"。
    """
    tool = derive_tool(title)
    if re.match(r"^(best|top|good|free|cheap|popular)\b", tool, flags=re.I):
        q = re.sub(r"^(best|top|good|free|cheap|popular)\s+", "", tool, flags=re.I)
        q = re.sub(r"\s+for\s+\w+(\s+\w+)?.*$", "", q, flags=re.I)  # 去 "for small business"
        q = STOP_YEAR.sub("", q)                                     # 去年份
        q = re.sub(r"\s+", " ", q).strip()
        query = q or "business software"
    else:
        query = tool
    query = re.sub(r"[^a-zA-Z0-9 ]", " ", query).strip()
    query = " ".join(query.split()[:4])
    return query, query


def is_relevant_to(text: str, query: str) -> bool:
    """文本是否真的与检索主题相关：要求命中至少一个「非泛化」检索词。"""
    toks = [t.lower() for t in re.findall(r"[a-zA-Z0-9]+", query) if len(t) > 2]
    specific = [t for t in toks if t not in GENERIC_TOKENS]
    if not specific:
        specific = toks  # 退路：全当具体词
    low = (text or "").lower()
    return any(s in low for s in specific)
