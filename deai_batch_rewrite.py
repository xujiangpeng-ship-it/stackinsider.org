#!/usr/bin/env python3
"""
deai_batch_rewrite.py — 批量审计所有存量文章，对命中 >4 项的调用 Mistral API 去 AI 味重写
排除今天新生成的文章（已用 v3 prompt 生成）
"""

import os
import sys
import time
import datetime
import re
from openai import OpenAI

api_key = os.environ.get('MISTRAL_API_KEY')
if not api_key:
    print("MISTRAL_API_KEY not set. Abort.")
    sys.exit(1)

client = OpenAI(api_key=api_key, base_url="https://api.mistral.ai/v1")
MODEL_NAME = "mistral-large-latest"
TODAY = datetime.date.today().strftime("%Y-%m-%d")

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
    body = text.lower()
    hits = []
    word_hits = []
    for w in BANNED_WORDS:
        idx = 0
        while True:
            idx = body.find(w, idx)
            if idx == -1:
                break
            before = body[idx - 1] if idx > 0 else ' '
            after = body[idx + len(w)] if idx + len(w) < len(body) else ' '
            if before in ' \n\t.,;:!?-\u2014\u2013(' and after in ' \n\t.,;:!?-\u2014\u2013)':
                word_hits.append(w)
            idx += len(w)
    if word_hits:
        hits.append(f"words:{len(word_hits)}")

    phrase_hits = [p for p in BANNED_PHRASES if p in body]
    if phrase_hits:
        hits.append(f"phrases:{len(phrase_hits)}")

    pad_hits = [p for p in PADDING_CLAUSES if p in body]
    if len(pad_hits) > 1:
        hits.append(f"padding:{len(pad_hits)}")

    if '\u2014' in text or '\u2013' in text:
        hits.append("em_dash")
    if '\u201c' in text or '\u201d' in text:
        hits.append("curly_quotes")
    if re.search(r'[\U0001F300-\U0001F9FF\u2600-\u27BF]', text[:2000]):
        hits.append("emoji")

    tc = re.findall(r'\n## [A-Z][a-z]+ [A-Z][a-z]+ [A-Z]', text[:5000])
    if len(tc) >= 2:
        hits.append(f"title_case:{len(tc)}")

    bold = re.findall(r'\*\*[^*]+\*\*', text[:10000])
    if len(bold) > 8:
        hits.append(f"bold:{len(bold)}")

    rule3 = re.findall(r'\w+, \w+, and \w+', text[:10000])
    if len(rule3) >= 3:
        hits.append(f"rule3:{len(rule3)}")

    passive = ["is needed", "are needed", "is required", "are required",
               "it is recommended", "was recommended", "is shown", "can be found"]
    pc = sum(1 for p in passive if p in body)
    if pc >= 3:
        hits.append(f"passive:{pc}")

    authority = ["the real question is", "at its core", "in reality",
                 "what really matters", "fundamentally,", "the heart of the matter"]
    if any(a in body for a in authority):
        hits.append("authority")

    pos = ["the future looks", "exciting times", "represents a major",
           "continues its journey", "only time will tell"]
    if any(e in text[-800:].lower() for e in pos):
        hits.append("pos_ending")

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
            hits.append("fragmented_h2")
            break

    hy = re.findall(r'\b\w+-\w+(?:-\w+)?\b', text[:10000])
    if len(hy) > 18:
        hits.append(f"hyphens:{len(hy)}")

    sents = re.split(r'[.!?]+\s+', text[:10000])
    streak = 0
    for s in sents:
        n = len(s.split())
        if 15 <= n <= 25:
            streak += 1
            if streak >= 3:
                hits.append("uniform_sent_len")
                break
        else:
            streak = 0

    aph = re.findall(r'\w+ is (?:the|a) \w+ of \w+', body[:5000])
    if len(aph) > 1:
        hits.append(f"aphorism:{len(aph)}")

    return hits


SYSTEM_PROMPT = """You are a professional editor. Rewrite this article to remove ALL AI writing patterns.

RULES (apply ALL of them):
1. Replace these banned words with natural alternatives: crucial, pivotal, vital, delve, showcase, tapestry, landscape, vibrant, testament, underscore, fosters, intricate, interplay, nestled, breathtaking, groundbreaking, robust, seamless, unparalleled, unlock, unleash, harness, game-changer, revolutionary, realm, daunting, cutting-edge
2. Remove ALL em dashes and en dashes. Use periods, commas, or colons.
3. Replace ALL curly/smart quotes with straight quotes.
4. Delete ALL "Not only...but also", "It's not just about", "In conclusion", "serves as", "stands as", "boasts".
5. Remove ALL "-ing" padding clauses.
6. Convert Title Case headings to sentence case.
7. Vary sentence and paragraph length. Some paragraphs = 1 sentence.
8. Cut filler: "In order to" → "To", "Due to the fact that" → "Because".
9. Remove chatbot residue: "I hope this helps", "Let me know if".
10. If ending is polished positive, make it short and direct.
11. Preserve ALL facts, data, comparisons, product names, prices, YAML front matter.
12. DO NOT add new content. Output ONLY the Markdown. No explanations, no fences."""


def rewrite(text, fname):
    print(f"    → Calling Mistral...")
    try:
        resp = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Rewrite to remove AI patterns. File: {fname}\n\n{text}"}
            ],
            temperature=0.65,
            max_tokens=4000,
            timeout=120,
        )
        out = resp.choices[0].message.content.strip()
        if out.startswith('```'):
            nl = out.find('\n')
            out = out[nl + 1:] if nl != -1 else out[3:]
        if out.rstrip().endswith('```'):
            out = out.rstrip()[:-3].rstrip()
        return out.strip()
    except Exception as e:
        print(f"    ✗ API failed: {e}")
        return None


def main():
    posts_dir = "content/posts"
    if not os.path.isdir(posts_dir):
        print("ERROR: content/posts/ not found")
        sys.exit(1)

    all_files = sorted([f for f in os.listdir(posts_dir) if f.endswith('.md')])

    # 排除今天新生成的文章
    exclude_pattern = TODAY.replace('-', '-')
    candidates = [f for f in all_files if TODAY not in f]

    if not candidates:
        print("No old articles to process.")
        return

    print(f"Candidates: {len(candidates)} articles\n")

    total = len(candidates)
    rewritten = 0
    api_calls = 0

    for i, fname in enumerate(candidates):
        fpath = os.path.join(posts_dir, fname)
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()

        hits = audit_article(content)
        print(f"[{i+1}/{total}] {fname}: {len(hits)} hits", end="")

        if len(hits) <= 4:
            print(" → SKIP (passes)")
            continue

        print(" → REWRITE")
        new_content = rewrite(content, fname)
        api_calls += 1

        if new_content is None or len(new_content) < 100:
            print(f"    ✗ Rewrite returned too short content, skipping.")
            continue

        # 验证 front matter 未被破坏
        if not new_content.startswith('---'):
            print(f"    ✗ Front matter lost, skipping.")
            continue

        # 二次审计
        hits2 = audit_article(new_content)
        improvement = len(hits) - len(hits2)
        print(f"    {len(hits)} → {len(hits2)} hits ({'+' if improvement < 0 else ''}{-improvement if improvement < 0 else improvement})")

        if len(hits2) >= len(hits):
            print(f"    ⚠ No improvement, keeping original.")
            continue

        # 写入
        try:
            with open(fpath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            rewritten += 1
            print(f"    ✓ Written")
        except Exception as e:
            print(f"    ✗ Write failed: {e}")

        # 速率控制: 每次 API 调用后等待 3 秒
        if api_calls % 5 == 0:
            print(f"    [progress: {api_calls} API calls, {rewritten} rewritten]")
        time.sleep(3)

    print(f"\n{'='*50}")
    print(f"DONE: {rewritten}/{total} articles rewritten ({api_calls} API calls)")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
