# -*- coding: utf-8 -*-
import os, re, io
ROOT = os.path.dirname(os.path.abspath(__file__))
POSTS = os.path.join(ROOT, 'content', 'posts')
for f in sorted(x for x in os.listdir(POSTS) if x.endswith('.md')):
    s = io.open(os.path.join(POSTS, f), encoding='utf-8').read()
    blocks = re.findall(r'^#{1,3}\s*Key takeaways\s*$', s, re.M | re.I)
    if len(blocks) != 1:
        print('!! %s -> %d 个 KT 标题' % (f, len(blocks)))
    km = re.search(r'^#{1,3}\s*Key takeaways\s*$(.*?)(?=^#{1,3}\s|\Z)', s, re.M | re.S | re.I)
    if km:
        n = len([b for b in re.findall(r'^\s*[-*]\s+(.+)$', km.group(1), re.M) if b.strip()])
        if n != 3:
            print('\n=== %s (%d 条) ===' % (f, n))
            print(km.group(0)[:900])
