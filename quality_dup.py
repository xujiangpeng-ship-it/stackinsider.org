# -*- coding: utf-8 -*-
"""对比 stackinsider 重复组两篇文章的质量指标，决定保留哪个"""
import os, re, io, collections

ROOT = os.path.dirname(os.path.abspath(__file__))
POSTS = os.path.join(ROOT, 'content', 'posts')

def read(path):
    s = io.open(path, encoding='utf-8').read()
    m = re.match(r'---\n(.*?)\n---\n', s, re.S)
    head = m.group(1) if m else ''
    body = s[m.end():] if m else s
    mm = re.search(r'slug:\s*"([^"]*)"', head)
    slug = mm.group(1) if mm else ''
    t = re.search(r'title:\s*"([^"]*)"', head)
    return {'slug': slug, 'title': t.group(1) if t else '', 'body': body, 'head': head}

def quality(b):
    """粗评 E-E-A-T 信号"""
    txt = re.sub(r'\{\{<.*?>\}\}', ' ', b, flags=re.S)
    n = len(txt)
    words = len(re.findall(r"[A-Za-z'’]+", txt))
    # 表格行数
    tbl = len(re.findall(r'^\s*\|', txt, re.M))
    # 具体数字/价格信号
    prices = len(re.findall(r'\$\s?\d', txt))
    pct = len(re.findall(r'\d+%', txt))
    # 第一人称经验信号
    first = len(re.findall(r'\b(I |I\'ve|we |we\'ve|our |my )', txt))
    # 标题结构
    h2 = len(re.findall(r'^## ', txt, re.M))
    return {'chars': n, 'words': words, 'table_rows': tbl, 'prices': prices,
            'pct': pct, 'first': first, 'h2': h2,
            'score': words / 100.0 + tbl * 0.4 + prices * 0.5 + pct * 0.3 + first * 0.6 + h2 * 0.8}

files = sorted(f for f in os.listdir(POSTS) if f.endswith('.md'))
info = {f: read(os.path.join(POSTS, f)) for f in files}
g = collections.defaultdict(list)
for f in files:
    g[info[f]['slug']].append(f)
conflict = {k: sorted(v) for k, v in g.items() if len(v) > 1}

print('冲突组: %d\n' % len(conflict))
print('%-42s %-12s %6s %6s %6s' % ('slug', 'file', 'words', 'score', 'win'))
print('-' * 90)
newer_win = 0
older_win = 0
for k, v in sorted(conflict.items()):
    row = []
    for f in v:
        q = quality(info[f]['body'])
        row.append((f, q))
    best = max(row, key=lambda x: x[1]['score'])[0]
    for f, q in row:
        row_tag = 'WIN' if f == best else ''
        print('%-42s %-12s %6d %6.1f %6s' % (k[:42], f[:12], q['words'], q['score'], row_tag))
    if best == v[-1]:
        newer_win += 1
    else:
        older_win += 1
    print()
print('较新批次胜出: %d 组，较早批次胜出: %d 组' % (newer_win, older_win))
