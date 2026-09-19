# -*- coding: utf-8 -*-
"""核查：确保没有误删「线上已有、本地无重复」的文章（如 CI 新生成的孤篇）"""
import os, re, io, json, subprocess, collections

ROOT = os.path.dirname(os.path.abspath(__file__))
POSTS = os.path.join(ROOT, 'content', 'posts')
ANALYSIS = os.path.join(os.path.dirname(ROOT), 'analysis')


def git(*a):
    r = subprocess.run(list(a), cwd=ROOT, capture_output=True, text=True,
                       encoding='utf-8', errors='ignore')
    return r.stdout


# 1. 从 git HEAD 拿到删除前所有文章的 slug -> 文件名映射
before = {}
listing = git('git', 'ls-tree', '-r', '--name-only', 'HEAD', 'content/posts')
for rel in listing.splitlines():
    if not rel.endswith('.md'):
        continue
    raw = git('git', 'show', 'HEAD:' + rel)
    mm = re.search(r'slug:\s*"([^"]*)"', raw)
    before[mm.group(1) if mm else ''] = os.path.basename(rel)

print('删除前文章数: %d' % len(before))

# 2. 当前 slug 集合
now = {}
for f in sorted(x for x in os.listdir(POSTS) if x.endswith('.md')):
    s = io.open(os.path.join(POSTS, f), encoding='utf-8').read()
    mm = re.search(r'slug:\s*"([^"]*)"', s)
    now[mm.group(1) if mm else ''] = f
print('删除后文章数: %d' % len(now))

# 3. 线上 sitemap 的 /posts/ URL
import xml.etree.ElementTree as ET
tree = ET.parse(os.path.join(ANALYSIS, 'si_sitemap.xml'))
ns = {'s': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
online = set()
for e in tree.findall('.//s:loc', ns):
    u = e.text.strip()
    if '/posts/' in u:
        online.add(u.rstrip('/').split('/posts/')[-1])

lost = sorted(online - set(now.keys()))
print('\n线上有、删除后本地没有的 slug: %d' % len(lost))
for s in lost:
    src = before.get(s, '(删除前也不存在 -> CI 当天新生成)')
    print('   %-52s 原属: %s' % (s, src))

# 4. 这些 lost 里，哪些是「本来就没重复、却被误删」的？
removed = json.load(io.open(os.path.join(ROOT, 'removed_posts.txt'), encoding='utf-8'))
removed_slugs = {m['slug']: m['file'] for m in removed}
print('\n--- 逐个判定 ---')
for s in lost:
    if s in removed_slugs:
        # 检查删除前是否有同主题兄弟篇保留
        key = re.sub(r'^\d{4}-\d{2}-\d{2}-', '', removed_slugs[s][:-3])
        sibling = [f for f in now.values() if re.sub(r'^\d{4}-\d{2}-\d{2}-', '', f[:-3]) == key]
        print('   %-46s 被删(有同主题保留篇: %s)' % (s, sibling))
    else:
        print('   %-46s 非本次删除所致' % s)
