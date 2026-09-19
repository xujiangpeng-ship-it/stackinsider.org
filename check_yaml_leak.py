# -*- coding: utf-8 -*-
"""检查正文中的 YAML 残留（第二个 frontmatter 块 / faqs 泄漏到正文）"""
import os, re, io

ROOT = os.path.dirname(os.path.abspath(__file__))
POSTS = os.path.join(ROOT, 'content', 'posts')

YAML_IN_BODY = re.compile(r'^( faqs:|faqs:| question:| answer:| editor_analysis:| references:|lastmod:|categories:| tags:)', re.M)

hits = []
for f in sorted(x for x in os.listdir(POSTS) if x.endswith('.md')):
    s = io.open(os.path.join(POSTS, f), encoding='utf-8').read()
    m = re.match(r'---\n(.*?)\n---\n', s, re.S)
    if not m:
        continue
    body = s[m.end():]
    has_faq = re.search(r'^faqs:\s*$', body, re.M)
    has_q = re.search(r'^\s*-\s*question:', body, re.M)
    has_lm = re.search(r'^lastmod:', body, re.M)
    # 正文里是否还有孤立的 --- 分隔的非 frontmatter YAML
    dangling = len(re.findall(r'^---\s*$', body, re.M))
    if has_faq or has_q or has_lm or dangling:
        hits.append((f, bool(has_faq), bool(has_q), bool(has_lm), dangling))

print('疑似正文含 YAML 残留的文章: %d' % len(hits))
for f, faq, q, lm, dg in hits:
    print('  %-56s faqs=%s question=%s lastmod=%s ---x%d' % (f, faq, q, lm, dg))
