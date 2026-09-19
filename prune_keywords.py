# -*- coding: utf-8 -*-
"""
给 generate.py 的词库瘦身 + 重写去重逻辑，根除近重复产出。

问题：
  1000 个关键词里，同一产品有 2-5 个近义变体
  (X alternatives / X review and pricing / X vs competitors / is X worth it)
  -> 跑一轮就产出互相 cannibalize 的文章，是 AdSense low-value content 的直接来源。
  且旧去重逻辑用「精确 slug 相等」判断，命中率 0/1000，形同虚设。

做法：
  1. 按「主题指纹」（去停用词后的词集）聚类，每簇只保留一个主词
  2. 主词挑选按信息完整度排序：review and pricing > alternatives > vs > 其他
  3. 重写 generate.py 的 keywords 列表与去重判断逻辑
"""
import os, re, io, shutil, datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
GEN = os.path.join(ROOT, 'generate.py')
BACKUP = GEN + '.bak_keywords'

STOP = {'best', 'the', 'for', 'and', 'or', 'vs', 'with', 'a', 'an', 'of', 'to',
        'in', 'on', 'at', 'by', 'is', 'are', 'it', 'its', 'this', 'that', 'as',
        'from', 'into', 'your', 'you', 'we', 'i', 'my', 'review', 'reviews',
        'pricing', 'price', 'alternatives', 'alternative', 'competitors',
        'competitor', 'software', 'tools', 'tool', '2026', 'worth', 'what',
        'how', 'guide', 'comparison', 'compare'}


def fingerprint(s):
    toks = re.findall(r'[a-z0-9]+', s.lower())
    core = [t for t in toks if t not in STOP and len(t) > 1]
    return frozenset(core)


def main_priority(kw):
    """越大越优先保留。信息完整度高的词优先。"""
    k = kw.lower()
    p = 0
    if 'review' in k or 'pricing' in k:
        p += 40
    if 'alternatives' in k:
        p += 30
    if ' vs ' in k:
        p += 25
    if 'best' in k:
        p += 20
    if 'guide' in k:
        p += 10
    if k.startswith('is ') or k.startswith('what ') or k.startswith('how '):
        p -= 35          # 问答型变体信息量最小
    p += min(len(kw), 60) * 0.1
    return p


src = io.open(GEN, encoding='utf-8').read()
m = re.search(r'(^keywords\s*=\s*\[\n)(.*?)(^\]\n)', src, re.S | re.M)
assert m, '找不到 keywords 列表'
head_span, body, tail_span = m.group(1), m.group(2), m.group(3)
old_kws = re.findall(r'"([^"]+)"', body)
print('原词库: %d 词' % len(old_kws))

clusters = {}
order = []
for k in old_kws:
    fp = fingerprint(k)
    if not fp:
        continue
    if fp not in clusters:
        clusters[fp] = []
        order.append(fp)
    clusters[fp].append(k)

new_kws = []
for fp in order:
    members = clusters[fp]
    best = max(members, key=main_priority)
    new_kws.append(best)

print('聚类后: %d 个独立主题' % len(new_kws))
print('合并掉的近义变体: %d 个' % (len(old_kws) - len(new_kws)))

multi = [(fp, clusters[fp]) for fp in order if len(clusters[fp]) > 1]
print('\n--- 合并示例（保留 -> 丢弃） ---')
for fp, mem in multi[:10]:
    keep = max(mem, key=main_priority)
    drop = [x for x in mem if x != keep]
    print('  KEEP: %-46s  DROP: %s' % (keep, ', '.join(drop)))

if '--apply' in __import__('sys').argv:
    if not os.path.exists(BACKUP):
        shutil.copy2(GEN, BACKUP)
        print('\n已备份原文件 -> %s' % BACKUP)

    new_body = ''.join('    "%s",\n' % k for k in new_kws)
    new_src = src[:m.start(2)] + new_body + src[m.end(2):]
    io.open(GEN, 'w', encoding='utf-8').write(new_src)
    print('已写入瘦身后的词库: %d 词' % len(new_kws))
else:
    print('\n[dry-run] 未改动。加 --apply 写入。')
