# -*- coding: utf-8 -*-
"""分析 keywords 词库：规模 + 近义重叠簇"""
import os, re, io, collections

ROOT = os.path.dirname(os.path.abspath(__file__))
src = io.open(os.path.join(ROOT, 'generate.py'), encoding='utf-8').read()
m = re.search(r'^keywords\s*=\s*\[(.*?)^\]', src, re.S | re.M)
block = m.group(1)
kws = re.findall(r'"([^"]+)"', block)
print('词库关键词数: %d' % len(kws))

STOP = {'best', 'the', 'for', 'and', 'vs', 'with', 'a', 'an', 'of', 'to',
        'in', 'on', 'review', 'pricing', 'alternatives', 'competitors',
        'software', 'tools', 'tool', '2026', 'is', 'it', 'worth', 'top',
        'compare', 'comparison', 'guide', 'what', 'how'}

def fingerprint(kw):
    toks = re.findall(r'[a-z0-9]+', kw.lower())
    core = [t for t in toks if t not in STOP]
    return frozenset(core)

clusters = collections.defaultdict(list)
for k in kws:
    clusters[fingerprint(k)].append(k)

multi = {k: v for k, v in clusters.items() if len(v) > 1}
print('去重后核心主题指纹数: %d' % len(clusters))
print('含多篇变体的主题簇: %d，涉及 %d 个词' % (len(multi), sum(len(v) for v in multi.values())))

print('\n--- 重叠最严重的簇 (前 12) ---')
for fp, v in sorted(multi.items(), key=lambda x: -len(x[1]))[:12]:
    print('  [%d 词] %s' % (len(v), ' | '.join(sorted(v))[:150]))

# 已发布文件 vs 词库匹配率
POSTS = os.path.join(ROOT, 'content', 'posts')
files = [f for f in os.listdir(POSTS) if f.endswith('.md')]
pub = set()
for f in files:
    mm = re.match(r'\d{4}-\d{2}-\d{2}-(.*)\.md$', f)
    if mm:
        pub.add(mm.group(1))

def slug_of(kw):
    return re.sub(r'[^a-z0-9]+', '-', kw.strip().lower())[:50]

hit = sum(1 for k in kws if slug_of(k) in pub)
print('\n词库中「精确 slug 已存在」的关键词: %d / %d' % (hit, len(kws)))

# 模糊匹配：词库关键词 vs 已发布文件名
fpub = collections.defaultdict(list)
for p in pub:
    fpub[fingerprint(p.replace('-', ' '))].append(p)
fhit = 0
examples = []
for k in kws:
    fp = fingerprint(k)
    if fp in fpub:
        fhit += 1
        if len(examples) < 10:
            examples.append('%s  ->  %s' % (k, ','.join(fpub[fp])[:60]))
print('词库中「主题指纹已存在」的关键词: %d / %d' % (fhit, len(kws)))
for e in examples:
    print('   ', e)
