# -*- coding: utf-8 -*-
"""诊断去重阈值：统计每个关键词与已发布文章的最大相似度分布"""
import os, re, io, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
GEN = os.path.join(ROOT, 'generate.py')
src = io.open(GEN, encoding='utf-8').read()

kw_src = re.search(r'^keywords\s*=\s*\[.*?^\]', src, re.S | re.M).group(0)

# 只抽取需要的纯函数 + 已发布索引，不跑 chosen 循环
blk = re.search(r'(# ============ 已发布文章索引.*?)(\nchosen_i = )', src, re.S).group(1)
ns = {'__file__': GEN}
exec(compile('import os, re\n' + kw_src + '\n' + blk, '<x>', 'exec'), ns)

keywords = ns['keywords']
_published = ns['_published']
_tokens = ns['_tokens']
_entity = ns['_entity']

POSTS = os.path.join(ROOT, 'content', 'posts')
files = sorted(f for f in os.listdir(POSTS) if f.endswith('.md'))


def best_sim(kw):
    fp = _tokens(kw)
    fe = _entity(kw)
    bj, bmatch, bfile = 0.0, None, None
    for p in _published:
        inter = len(fp & p['tokens'])
        if not inter:
            continue
        j = inter / len(fp | p['tokens'])
        if j > bj:
            bj, bmatch = j, p
    return bj, fp, fe


# 对现有每篇文章，看「它本应匹配的关键词」相似度是多少
print('=== 现有文章 -> 最相似关键词的反查（检验漏判）===')
# 反向：对每个 existing topic，找词库里 jaccard 最高的词
exist_topics = []
for f in files:
    s = io.open(os.path.join(POSTS, f), encoding='utf-8').read()
    mm = re.search(r'slug:\s*"([^"]*)"', s)
    tt = re.search(r'title:\s*"([^"]*)"', s)
    topic = re.sub(r'^\d{4}-\d{2}-\d{2}-', '', f[:-3]).replace('-', ' ')
    exist_topics.append((f, topic, mm.group(1) if mm else '', tt.group(1) if tt else ''))

ETOK = [(f, _tokens(topic), _entity(topic), sl) for f, topic, sl, _ in exist_topics]

buckets = {'实体相等': 0, '0.5-0.7': 0, '0.4-0.5': 0, '0.3-0.4': 0, '<0.3': 0}
missed = []
for f, et, ee, sl in ETOK:
    # 找词库里与它最像的
    bj, bkw = 0.0, None
    ent_hit = None
    for k in keywords:
        kp, ke = _tokens(k), _entity(k)
        if ke and ee and ke == ee:
            ent_hit = k
            break
        inter = len(kp & et)
        if inter:
            j = inter / len(kp | et)
            if j > bj:
                bj, bkw = j, k
    if ent_hit:
        buckets['实体相等'] += 1
    elif bj >= 0.5:
        buckets['0.5-0.7'] += 1
    elif bj >= 0.4:
        buckets['0.4-0.5'] += 1
    elif bj >= 0.3:
        buckets['0.3-0.4'] += 1
    else:
        buckets['<0.3'] += 1

print('')
for k, v in buckets.items():
    print('  %-10s %d 篇' % (k, v))

print('\n=== 潜在漏判：现有文章在词库中相似度偏低（<0.5）的样例 ===')
n = 0
for f, et, ee, sl in ETOK:
    bj, bkw = 0.0, None
    for k in keywords:
        kp = _tokens(k)
        inter = len(kp & et)
        if inter:
            j = inter / len(kp | et)
            if j > bj:
                bj, bkw = j, k
    if bj < 0.5:
        n += 1
        if n <= 12:
            print('  %-52s best=%.2f  kw=%s' % (f[:52], bj, bkw))
print('  合计 %d 篇文章在词库中没有 >=0.5 的对应词' % n)
