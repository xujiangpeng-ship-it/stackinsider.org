#!/usr/bin/env python3
"""
deai_audit.py — 去 AI 味后处理审计 + 自动重写
基于 blader/humanizer v2.8.0 的 33 种 AI 写作模式检测

流程：
1. 扫描 content/posts/ 中今天新建/修改的 .md 文件
2. 对每篇文章执行 16 项 AI 模式审计
3. 审计不通过（命中 >3 项）→ 调用 Mistral API 用 deai 约束重写
4. 覆盖原文件
"""

import os
import re
import sys
import datetime
import time
from openai import OpenAI

# ========== 配置 ==========
api_key = os.environ.get('MISTRAL_API_KEY')
if not api_key:
    print("⚠️ MISTRAL_API_KEY not set. Skipping deai audit.")
    sys.exit(0)

client = OpenAI(api_key=api_key, base_url="https://api.mistral.ai/v1")
MODEL_NAME = "mistral-large-latest"

# ========== 16 项审计清单 ==========

BLACKLIST_WORDS = [
    "crucial", "pivotal", "vital", "delve", "showcase", "tapestry",
    "vibrant", "testament", "underscore", "fosters", "intricate", "interplay",
    "nestled", "breathtaking", "groundbreaking", "unlock", "unleash",
    "harness", "game-changer", "revolutionary", "realm", "daunting",
    "embark on", "robust", "seamless", "unparalleled", "cutting-edge",
    "best-in-class", "world-class", "state-of-the-art", "ever-evolving"
]

BLACKLIST_PHRASES = [
    (r"not only .{0,30} but also", "Not only...but also"),
    (r"it'?s not just about .{0,30} it'?s", "It's not just about...it's"),
    (r"let'?s dive in", "Let's dive in"),
    (r"let'?s explore", "Let's explore"),
    (r"here'?s what you need to know", "Here's what you need to know"),
    (r"in conclusion", "In conclusion"),
    (r"to sum up", "To sum up"),
    (r"bottom line", "Bottom line"),
    (r"wrapping up", "Wrapping up"),
    (r"the future looks bright", "The future looks bright"),
    (r"exciting times lie ahead", "Exciting times lie ahead"),
    (r"experts believe", "Experts believe"),
    (r"observers have noted", "Observers have noted"),
    (r"industry reports suggest", "Industry reports suggest"),
    (r"serves as", "serves as"),
    (r"stands as", "stands as"),
    (r"marks a pivotal", "marks a pivotal"),
    (r"boasts (?!.*(?:square|cubic|GB|TB|MB|users|customers|clients|employees|members))", "boasts (推销式)"),
    (r"i hope this helps", "I hope this helps"),
    (r"let me know if", "Let me know if"),
    (r"would you like me to", "Would you like me to"),
    (r"despite its challenges.{0,40}continues to thrive", "Despite...continues to thrive"),
    (r"\w+ is the \w+ of \w+", "X is the Y of Z"),
    (r"honestly\?", "Honestly?"),
    (r"here'?s the thing", "Here's the thing"),
    (r"in order to", "In order to"),
    (r"due to the fact that", "Due to the fact that"),
    (r"it is important to note that", "It is important to note"),
    (r"in today'?s (?:digital age|rapidly evolving|fast-paced)", "In today's..."),
    (r"comprehensive guide", "Comprehensive guide"),
    (r"deep dive", "Deep dive"),
    (r"could potentially possibly", "过度模糊限定"),
]

REGEX_PATTERNS = [
    (r"[\u2014\u2013]", "em dash / en dash"),
    (r"[\u201c\u201d]", "弯引号"),
    (r",\s*(?:highlighting|underscoring|emphasizing|reflecting|showcasing|symbolizing|contributing to|cultivating|fostering|encompassing)", "-ing 浮夸修饰从句"),
    (r"(?:^|\n)## [A-Z][a-z]+ [A-Z][a-z]+ [A-Z][a-z]+", "标题每个词大写 (Title Case)"),
]


def extract_body(text):
    """从 Markdown 文件中提取正文（去除 front matter）"""
    parts = text.split('---', 2)
    if len(parts) >= 3:
        return parts[2] if len(parts) >= 3 else text
    return text


def audit_article(text):
    """
    对文章执行 16 项审计，返回命中列表和总分。
    """
    body = extract_body(text)
    hits = []

    # 1. 黑名单词汇
    body_lower = body.lower()
    for word in BLACKLIST_WORDS:
        pattern = r'\b' + re.escape(word) + r'\b' if ' ' not in word else re.escape(word)
        if re.search(pattern, body_lower):
            hits.append(f"黑名单词: {word}")

    # 2. 禁止句式
    for pattern, label in BLACKLIST_PHRASES:
        if re.search(pattern, body_lower):
            hits.append(f"禁止句式: {label}")

    # 3. em dash / en dash
    for pattern, label in REGEX_PATTERNS[:2]:
        if re.search(pattern, body):
            hits.append(f"禁止标点: {label}")

    # 4. -ing 浮夸修饰
    for pattern, label in REGEX_PATTERNS[2:3]:
        if re.search(pattern, body):
            hits.append(label)

    # 5. 标题 Title Case (H2)
    title_case_h2 = re.findall(r'^## [A-Z][a-z]+ [A-Z][a-z]+ [A-Z]', body, re.MULTILINE)
    if title_case_h2:
        hits.append(f"标题 Title Case ({len(title_case_h2)} 处)")

    # 6. emoji
    emoji_pattern = re.compile(
        "[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF"
        "\u2600-\u26FF\u2700-\u27BF]", flags=re.UNICODE
    )
    if emoji_pattern.search(body):
        hits.append("emoji")

    # 7. 三件套排比密度（连续出现 A, B, and C 两次以上）
    rule_of_three = re.findall(r'(\w+),\s+(\w+),\s+and\s+(\w+)', body)
    if len(rule_of_three) >= 3:
        hits.append(f"三件套排比过度 ({len(rule_of_three)} 处)")

    # 8. 同义词轮换（简易检测：正文中同一产品名被替换为 3+ 不同称呼）
    # 跳过，需要更复杂的 NLP

    # 9. 被动语态 / 无主语碎片
    passive_patterns = [
        r'no \w+ (?:is |are |was |were )?(?:needed|required)',
        r'(?:it is|was) recommended that',
        r'results (?:are|were) preserved',
        r'configuration (?:is|was) (?:needed|required)',
    ]
    for p in passive_patterns:
        if re.search(p, body_lower):
            hits.append("被动/无主语碎片")
            break

    # 10. 通用正能量结论
    positive_endings = [
        r'the future looks bright',
        r'exciting times lie ahead',
        r'represents a (?:major|significant) step',
        r'continues its journey',
        r'only time will tell',
        r'remains to be seen',
    ]
    # 检查最后 500 字符
    tail = body[-500:] if len(body) > 500 else body
    for p in positive_endings:
        if re.search(p, tail.lower()):
            hits.append("通用正能量结论")
            break

    # 11. 连字符词对过度使用
    hyphenated = re.findall(r'\b\w+-\w+(?:-\w+)?\b', body)
    if len(hyphenated) > 15:
        hits.append(f"连字符词对过度 ({len(hyphenated)} 处)")

    # 12. 说服性权威话术
    authority_openers = [
        r'the real question is',
        r'at its core',
        r'in reality',
        r'what really matters',
        r'fundamentally',
        r'the deeper issue',
        r'the heart of the matter',
    ]
    for p in authority_openers:
        if re.search(p, body_lower):
            hits.append(f"说服性权威话术: {p}")
            break

    # 13. 过度加粗（**text** 超过 5 处）
    bold_count = len(re.findall(r'\*\*[^*]+\*\*', body))
    if bold_count > 5:
        hits.append(f"过度加粗 ({bold_count} 处)")

    # 14. 句长均匀性（简易：检查是否有连续 3 句都在 15-25 词）
    sentences = re.split(r'[.!?]+', body)
    sentence_lengths = [len(s.split()) for s in sentences if len(s.split()) > 2]
    consecutive_uniform = 0
    for sl in sentence_lengths:
        if 15 <= sl <= 25:
            consecutive_uniform += 1
            if consecutive_uniform >= 3:
                hits.append("句长均匀 (连续3句在15-25词舒适区)")
                break
        else:
            consecutive_uniform = 0

    # 15. 碎片化标题（H2 后紧跟一句只重复标题意思的废话）
    h2_with_repeat = re.findall(r'^## (.+)\n\n(.+)', body, re.MULTILINE)
    for heading, next_sentence in h2_with_repeat:
        heading_words = set(re.findall(r'\w+', heading.lower()))
        next_words = set(re.findall(r'\w+', next_sentence.lower()))
        overlap = heading_words & next_words
        if len(overlap) >= 3 and len(next_sentence.split()) < 12:
            hits.append(f"碎片化标题: {heading[:40]}")
            break

    # 16. 格言公式额外检测
    aphorism = re.findall(r'(?:\w+ is the \w+ of \w+|\w+ becomes a trap|\w+ is not a \w+ but a \w+)', body_lower)
    if len(aphorism) > 1:
        hits.append(f"格言公式 ({len(aphorism)} 处)")

    return hits


def get_deai_system_prompt():
    """返回去 AI 味重写的 system prompt"""
    return """You are a professional editor specializing in removing AI-generated writing patterns from articles. Your job is to rewrite the given article so it reads like it was written by an experienced, opinionated human consultant — not an AI.

RULES (apply ALL of them):
1. Replace ALL occurrences of these banned words with natural alternatives: crucial, pivotal, vital, delve, showcase, tapestry, landscape, vibrant, testament, underscore, fosters, intricate, interplay, nestled, breathtaking, groundbreaking, robust, seamless, unparalleled, unlock, unleash, harness, game-changer, revolutionary, realm, daunting, cutting-edge
2. Remove ALL em dashes (—) and en dashes (–). Replace with periods, commas, or colons.
3. Replace ALL curly/smart quotes ("") with straight quotes ("").
4. Delete ALL phrases like "Not only...but also", "It's not just about...it's", "In conclusion", "Experts believe", "serves as", "stands as", "boasts".
5. Remove ALL "-ing" padding clauses (", highlighting...", ", underscoring...", etc.)
6. Convert ALL Title Case headings to sentence case.
7. Vary sentence length — break any sequence of 3+ sentences of similar length.
8. Vary paragraph size — mix short and long paragraphs.
9. Cut filler: "In order to" → "To", "Due to the fact that" → "Because".
10. Remove any "chatbot residue": "I hope this helps", "Let me know if", etc.
11. If the article has a polished positive ending, replace it with a shorter, more direct closing.
12. Preserve ALL factual content, data, comparisons, product names, and pricing information.
13. Preserve the YAML front matter (--- ... ---) exactly as-is.
14. Preserve the Markdown structure (## headings, tables, bold text where genuinely needed).
15. DO NOT add new content — only rewrite existing content.
16. Output ONLY the rewritten Markdown article. No explanations, no code fences."""


def rewrite_article(text, keyword=""):
    """用 Mistral API 重写文章"""
    print("  🔄 正在用 deai 约束重写...")
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": get_deai_system_prompt()},
                {"role": "user", "content": f"Rewrite the following article to remove all AI-generated writing patterns. Keyword context: {keyword}\n\n{text}"}
            ],
            temperature=0.65,
            max_tokens=4000,
            timeout=600,
        )
        rewritten = response.choices[0].message.content.strip()

        # Strip outer fences if present
        if rewritten.startswith('```'):
            first_nl = rewritten.find('\n')
            if first_nl != -1:
                rewritten = rewritten[first_nl+1:]
            else:
                rewritten = rewritten[3:]

        stripped = rewritten.rstrip()
        if stripped.endswith('```'):
            rewritten = stripped[:-3].rstrip()

        return rewritten.strip()
    except Exception as e:
        print(f"  ❌ 重写失败: {e}")
        return text


def main():
    today = datetime.date.today().strftime("%Y-%m-%d")
    posts_dir = os.path.join("content", "posts")

    if not os.path.isdir(posts_dir):
        print("❌ content/posts/ 目录不存在")
        sys.exit(1)

    # 扫描今天新建/修改的文件
    today_files = []
    for f in os.listdir(posts_dir):
        if not f.endswith('.md'):
            continue
        fpath = os.path.join(posts_dir, f)
        mtime = datetime.datetime.fromtimestamp(os.path.getmtime(fpath))
        if mtime.strftime("%Y-%m-%d") == today:
            today_files.append(fpath)

    if not today_files:
        print("ℹ️ 今天没有新生成的文章，跳过审计。")
        return

    print(f"📋 找到 {len(today_files)} 篇今天生成的文章\n")

    total_hits = 0
    rewritten_count = 0

    for fpath in today_files:
        print(f"🔍 审计: {os.path.basename(fpath)}")
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            print(f"  ⚠️ 无法读取: {e}")
            continue

        hits = audit_article(content)
        print(f"  📊 命中 {len(hits)} 项 AI 模式")

        if hits:
            for h in hits:
                print(f"    - {h}")

        if len(hits) > 3:
            print(f"  ⚠️ 超过阈值 (3)，触发重写...")
            # 提取 keyword 上下文
            kw_match = re.search(r'keyword\s+context:\s*(.+?)(?:\n|$)', '', re.MULTILINE)
            keyword = os.path.basename(fpath).replace('.md', '').split('-', 1)[-1] if '-' in os.path.basename(fpath) else ""
            rewritten = rewrite_article(content, keyword)

            if rewritten != content:
                try:
                    with open(fpath, 'w', encoding='utf-8') as f:
                        f.write(rewritten)
                    print(f"  ✅ 重写完成，已覆盖原文件")

                    # 重新审计重写后的结果
                    hits_after = audit_article(rewritten)
                    print(f"  📊 重写后命中: {len(hits_after)} 项")
                    if hits_after:
                        for h in hits_after:
                            print(f"    - {h}")

                    rewritten_count += 1
                except Exception as e:
                    print(f"  ❌ 写入失败: {e}")
            else:
                print(f"  ℹ️ 重写后无变化")
        else:
            print(f"  ✅ 通过审计")

        total_hits += len(hits)
        print()

    print(f"{'='*50}")
    print(f"📊 审计完成：{len(today_files)} 篇 → 重写 {rewritten_count} 篇，总命中 {total_hits} 项")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
