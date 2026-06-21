#!/usr/bin/env python3
"""
deai_audit.py — 去 AI 味后处理审计 + 自动重写（v2 简化版）
检测 16 项 AI 模式，命中 >4 项 → 调 Mistral API 重写

修复：去除所有可能回溯爆炸的正则，纯子串扫描，全局 120s 超时
"""

import os
import sys
import datetime
import time
import re
from openai import OpenAI

# ========== 配置 ==========
api_key = os.environ.get('MISTRAL_API_KEY')
if not api_key:
    print("MISTRAL_API_KEY not set. Skipping deai audit.")
    sys.exit(0)

client = OpenAI(api_key=api_key, base_url="https://api.mistral.ai/v1")
MODEL_NAME = "mistral-large-latest"

# ========== 轻量审计规则（纯子串 + 简单正则，无回溯风险）==========

BANNED_WORDS = [
    "crucial", "pivotal", "vital", "delve", "showcase", "tapestry",
    "vibrant", "testament", "fosters", "intricate", "interplay",
    "nestled", "breathtaking", "groundbreaking", "unlock", "unleash",
    "harness", "game-changer", "revolutionary", "realm", "daunting",
    "seamless", "unparalleled", "cutting-edge", "best-in-class",
    "world-class", "state-of-the-art", "ever-evolving",
]

BANNED_PHRASES = [
    "not only", "but also", "it's not just about", "let's dive",
    "let's explore", "here's what you need to know",
    "in conclusion", "to sum up", "bottom line", "wrapping up",
    "the future looks bright", "exciting times lie ahead",
    "experts believe", "observers have noted", "industry reports suggest",
    "serves as", "stands as", "i hope this helps", "let me know if",
    "would you like me to", "in order to", "due to the fact that",
    "it is important to note", "in today's", "comprehensive guide",
    "deep dive", "remains to be seen", "only time will tell",
    "continues to thrive", "honestly?", "here's the thing",
    "boasts a", "boasts an", "boasts the", "boasts its", "boasts over",
]

PADDING_CLAUSES = [
    ", highlighting", ", underscoring", ", emphasizing",
    ", reflecting", ", showcasing", ", symbolizing",
    ", contributing to", ", cultivating", ", encompassing",
]


def audit_article(text):
    """
    16 项轻量审计（纯子串扫描为主），返回命中列表。
    """
    body = text.lower()
    hits = []

    # === 1. 黑名单词 ===
    word_hits = []
    for w in BANNED_WORDS:
        # 边界匹配：前后为空格/标点/换行
        idx = 0
        while True:
            idx = body.find(w, idx)
            if idx == -1:
                break
            # 检查前后边界
            before = body[idx - 1] if idx > 0 else ' '
            after = body[idx + len(w)] if idx + len(w) < len(body) else ' '
            if before in ' \n\t.,;:!?-\u2014\u2013(' and after in ' \n\t.,;:!?-\u2014\u2013)':
                word_hits.append(w)
            idx += len(w)
    if word_hits:
        hits.append(f"黑名单词: {len(word_hits)} 处 ({', '.join(word_hits[:5])}{'...' if len(word_hits)>5 else ''})")

    # === 2. 禁止短语 ===
    phrase_hits = []
    for p in BANNED_PHRASES:
        if p in body:
            phrase_hits.append(p)
    if phrase_hits:
        hits.append(f"禁止短语: {len(phrase_hits)} 处 ({', '.join(phrase_hits[:3])}{'...' if len(phrase_hits)>3 else ''})")

    # === 3. -ing 浮夸修饰 ===
    pad_hits = [p for p in PADDING_CLAUSES if p in body]
    if len(pad_hits) > 1:
        hits.append(f"-ing 浮夸修饰: {len(pad_hits)} 处")

    # === 4. em dash ===
    if '\u2014' in text or '\u2013' in text:
        hits.append("Em dash / En dash")

    # === 5. 弯引号 ===
    if '\u201c' in text or '\u201d' in text:
        hits.append("弯引号")

    # === 6. Emoji ===
    if re.search(r'[\U0001F300-\U0001F9FF\u2600-\u27BF]', text[:2000]):  # 只查前2000字符
        hits.append("Emoji")

    # === 7. Title Case 标题 ===
    tc = re.findall(r'\n## [A-Z][a-z]+ [A-Z][a-z]+ [A-Z]', text[:5000])
    if len(tc) >= 2:
        hits.append(f"Title Case 标题 ({len(tc)} 处)")

    # === 8. 过度加粗 ===
    bold = re.findall(r'\*\*[^*]+\*\*', text[:10000])
    if len(bold) > 8:
        hits.append(f"过度加粗 ({len(bold)} 处)")

    # === 9. 三件套排比 ===
    rule3 = re.findall(r'\w+, \w+, and \w+', text[:10000])
    if len(rule3) >= 3:
        hits.append(f"三件套排比 ({len(rule3)} 处)")

    # === 10. 被动/无主语 ===
    passive = ["is needed", "are needed", "is required", "are required",
               "it is recommended", "was recommended", "is shown", "can be found"]
    pc = sum(1 for p in passive if p in body)
    if pc >= 3:
        hits.append(f"被动语态 ({pc} 处)")

    # === 11. 说服性权威话术 ===
    authority = ["the real question is", "at its core", "in reality",
                 "what really matters", "fundamentally,", "the heart of the matter"]
    if any(a in body for a in authority):
        hits.append("说服性权威话术")

    # === 12. 通用正能量结论 ===
    pos = ["the future looks", "exciting times", "represents a major",
           "continues its journey", "only time will tell"]
    tail = body[-800:]
    if any(e in tail for e in pos):
        hits.append("正能量结论")

    # === 13. 碎片化标题 ===
    h2s = re.findall(r'\n## (.+?)\n', text[:8000])
    for h2 in h2s:
        h2w = set(re.findall(r'\w+', h2.lower()))
        idx = text.find(f'## {h2}')
        if idx == -1:
            continue
        after = text[idx + len(h2) + 3:].strip()
        ns = after.split('.')[0] if '.' in after[:120] else after[:120]
        nsw = set(re.findall(r'\w+', ns.lower()))
        if len(h2w & nsw) >= 3 and len(ns.split()) < 10:
            hits.append(f"碎片化标题: {h2[:30]}")
            break

    # === 14. 连字符词对 ===
    hy = re.findall(r'\b\w+-\w+(?:-\w+)?\b', text[:10000])
    if len(hy) > 18:
        hits.append(f"连字符过度 ({len(hy)} 处)")

    # === 15. 句长均匀 ===
    sents = re.split(r'[.!?]+\s+', text[:10000])
    streak = 0
    for s in sents:
        n = len(s.split())
        if 15 <= n <= 25:
            streak += 1
            if streak >= 3:
                hits.append("句长均匀 (连续3句15-25词)")
                break
        else:
            streak = 0

    # === 16. 格言公式 ===
    aph = re.findall(r'\w+ is (?:the|a) \w+ of \w+', body[:5000])
    if len(aph) > 1:
        hits.append(f"格言公式 ({len(aph)} 处)")

    return hits


def get_deai_system_prompt():
    return """You are a professional editor rewriting an article to remove AI writing patterns.
RULES:
1. Replace ALL banned words (crucial, pivotal, vital, delve, showcase, tapestry, landscape, vibrant, testament, underscore, fosters, intricate, interplay, nestled, breathtaking, groundbreaking, robust, seamless, unparalleled, unlock, unleash, harness, game-changer, revolutionary, realm, daunting, cutting-edge) with natural alternatives.
2. Remove ALL em dashes and en dashes. Use periods, commas, or colons.
3. Replace ALL curly quotes with straight quotes.
4. Delete ALL "Not only...but also", "It's not just about", "In conclusion", "Experts believe", "serves as", "stands as".
5. Remove ALL "-ing" padding clauses.
6. Convert ALL Title Case headings to sentence case.
7. Vary sentence and paragraph length.
8. Cut filler: "In order to" -> "To".
9. Remove chatbot residue: "I hope this helps", "Let me know if".
10. If ending is polished positive, make it shorter and direct.
11. Preserve ALL facts, data, comparisons, product names, prices, and YAML front matter.
12. DO NOT add new content. Only rewrite existing.
13. Output ONLY the Markdown article. No explanations, no fences."""


def rewrite_article(text, keyword=""):
    """Mistral API 重写（120s 超时）"""
    print("  Rewriting with deai constraints...")
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": get_deai_system_prompt()},
                {"role": "user", "content": f"Rewrite to remove AI patterns. Keyword: {keyword}\n\n{text}"}
            ],
            temperature=0.65,
            max_tokens=4000,
            timeout=120,
        )
        rewritten = response.choices[0].message.content.strip()

        if rewritten.startswith('```'):
            nl = rewritten.find('\n')
            rewritten = rewritten[nl + 1:] if nl != -1 else rewritten[3:]
        if rewritten.rstrip().endswith('```'):
            rewritten = rewritten.rstrip()[:-3].rstrip()

        return rewritten.strip()
    except Exception as e:
        print(f"  Rewrite failed: {e}")
        return text


def main():
    today = datetime.date.today().strftime("%Y-%m-%d")
    posts_dir = os.path.join("content", "posts")

    if not os.path.isdir(posts_dir):
        print("ERROR: content/posts/ not found")
        sys.exit(1)

    today_files = []
    for f in os.listdir(posts_dir):
        if not f.endswith('.md'):
            continue
        fpath = os.path.join(posts_dir, f)
        mtime = datetime.datetime.fromtimestamp(os.path.getmtime(fpath))
        if mtime.strftime("%Y-%m-%d") == today:
            today_files.append(fpath)

    if not today_files:
        print("No articles generated today. Skipping audit.")
        return

    print(f"Auditing {len(today_files)} article(s)...")

    for fpath in today_files:
        fname = os.path.basename(fpath)
        print(f"\n  [{fname}]")
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            print(f"  Cannot read: {e}")
            continue

        hits = audit_article(content)
        print(f"  Hits: {len(hits)}")
        if hits:
            for h in hits[:8]:
                print(f"    - {h}")
            if len(hits) > 8:
                print(f"    ... and {len(hits) - 8} more")

        if len(hits) > 4:
            print(f"  Threshold exceeded (4), rewriting...")
            keyword = fname.replace('.md', '').split('-', 1)[-1] if '-' in fname else ""
            rewritten = rewrite_article(content, keyword)

            if rewritten and rewritten != content:
                try:
                    with open(fpath, 'w', encoding='utf-8') as f:
                        f.write(rewritten)
                    print(f"  Rewritten OK")
                    hits2 = audit_article(rewritten)
                    print(f"  After rewrite hits: {len(hits2)}")
                except Exception as e:
                    print(f"  Write failed: {e}")
            else:
                print(f"  Rewrite returned same content, keeping original")
        else:
            print(f"  Passed audit")

    print(f"\nDone.")


if __name__ == "__main__":
    main()
