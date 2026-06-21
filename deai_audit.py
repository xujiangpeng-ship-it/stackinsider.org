#!/usr/bin/env python3
"""
deai_audit.py — 去 AI 味后处理审计（v3 纯审计，不调 API）
检测 16 项 AI 模式，输出命中报告。

不执行任何 API 调用，100% 可靠运行。
重写逻辑已内置到 generate.py 的 prompt 中（33 模式约束）。
"""

import os
import sys
import datetime
import re

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
    """16 项轻量审计（纯子串扫描），返回命中列表。"""
    body = text.lower()
    hits = []

    # 1. 黑名单词
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
        hits.append(f"Blacklist words: {len(word_hits)} ({', '.join(word_hits[:5])}{'...' if len(word_hits)>5 else ''})")

    # 2. 禁止短语
    phrase_hits = [p for p in BANNED_PHRASES if p in body]
    if phrase_hits:
        hits.append(f"Banned phrases: {len(phrase_hits)} ({', '.join(phrase_hits[:3])}{'...' if len(phrase_hits)>3 else ''})")

    # 3. -ing 浮夸修饰
    pad_hits = [p for p in PADDING_CLAUSES if p in body]
    if len(pad_hits) > 1:
        hits.append(f"-ing padding: {len(pad_hits)}")

    # 4-6. 标点
    if '\u2014' in text or '\u2013' in text:
        hits.append("Em dash / En dash")
    if '\u201c' in text or '\u201d' in text:
        hits.append("Curly quotes")
    if re.search(r'[\U0001F300-\U0001F9FF\u2600-\u27BF]', text[:2000]):
        hits.append("Emoji")

    # 7. Title Case 标题
    tc = re.findall(r'\n## [A-Z][a-z]+ [A-Z][a-z]+ [A-Z]', text[:5000])
    if len(tc) >= 2:
        hits.append(f"Title Case h2 ({len(tc)})")

    # 8. 过度加粗
    bold = re.findall(r'\*\*[^*]+\*\*', text[:10000])
    if len(bold) > 8:
        hits.append(f"Excessive bold ({len(bold)})")

    # 9. 三件套排比
    rule3 = re.findall(r'\w+, \w+, and \w+', text[:10000])
    if len(rule3) >= 3:
        hits.append(f"Rule-of-three ({len(rule3)})")

    # 10. 被动语态
    passive_markers = ["is needed", "are needed", "is required", "are required",
                       "it is recommended", "was recommended", "is shown", "can be found"]
    pc = sum(1 for p in passive_markers if p in body)
    if pc >= 3:
        hits.append(f"Passive voice ({pc})")

    # 11. 说服性权威话术
    authority = ["the real question is", "at its core", "in reality",
                 "what really matters", "fundamentally,", "the heart of the matter"]
    if any(a in body for a in authority):
        hits.append("Persuasive authority")

    # 12. 正能量结论
    pos_endings = ["the future looks", "exciting times", "represents a major",
                   "continues its journey", "only time will tell"]
    if any(e in text[-800:].lower() for e in pos_endings):
        hits.append("Positive-summary ending")

    # 13. 碎片化标题
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
            hits.append(f"Fragmented heading: {h2[:30]}")
            break

    # 14. 连字符词对
    hy = re.findall(r'\b\w+-\w+(?:-\w+)?\b', text[:10000])
    if len(hy) > 18:
        hits.append(f"Excessive hyphens ({len(hy)})")

    # 15. 句长均匀
    sents = re.split(r'[.!?]+\s+', text[:10000])
    streak = 0
    for s in sents:
        n = len(s.split())
        if 15 <= n <= 25:
            streak += 1
            if streak >= 3:
                hits.append("Uniform sentence length (3+ consecutive 15-25 words)")
                break
        else:
            streak = 0

    # 16. 格言公式
    aph = re.findall(r'\w+ is (?:the|a) \w+ of \w+', body[:5000])
    if len(aph) > 1:
        hits.append(f"Aphorism formula ({len(aph)})")

    return hits


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
        print("No articles generated today. Audit skipped.")
        return

    total_hits = 0
    for fpath in today_files:
        fname = os.path.basename(fpath)
        print(f"\n[{fname}]")
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()

        hits = audit_article(content)
        total_hits += len(hits)
        status = "FAIL" if len(hits) > 4 else "PASS"
        print(f"  Result: {status} ({len(hits)} AI patterns)")

        if hits:
            for h in hits:
                print(f"    - {h}")

    print(f"\n{'='*50}")
    print(f"SUMMARY: {len(today_files)} articles, {total_hits} total AI patterns")
    if total_hits > 4:
        print("WARNING: High AI pattern count. Consider adjusting prompt constraints.")
    else:
        print("OK: AI patterns within acceptable range.")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
