# -*- coding: utf-8 -*-
"""核对 stackinsider.org 线上 sitemap：URL 重复情况 vs 本地 md"""
import os, re, io, collections, xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.abspath(__file__))
ANALYSIS = os.path.join(os.path.dirname(ROOT), 'analysis')
POSTS = os.path.join(ROOT, 'content', 'posts')

tree = ET.parse(os.path.join(ANALYSIS, 'si_sitemap.xml'))
ns = {'s': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
locs = [e.text for e in tree.findall('.//s:loc', ns)]
posts_urls = [u for u in locs if '/posts/' in u]
print('sitemap 总 URL: %d' % len(locs))
print('其中 /posts/ URL: %d' % len(posts_urls))
print('去重后 /posts/ URL: %d' % len(set(posts_urls)))

cnt = collections.Counter(posts_urls)
dupurl = {u: c for u, c in cnt.items() if c > 1}
print('sitemap 内重复的 /posts/ URL: %d' % len(dupurl))

# 本地 md
files = sorted(f for f in os.listdir(POSTS) if f.endswith('.md'))
def read_slug(path):
    s = io.open(path, encoding='utf-8').read()
    m = re.match(r'---\n(.*?)\n---\n', s, re.S)
    head = m.group(1) if m else ''
    mm = re.search(r'slug:\s*"([^"]*)"', head)
    if mm:
        return mm.group(1)
    mm = re.search(r'slug:\s*([^\s"\n]+)', head)
    return mm.group(1) if mm else ''

local = {}
for f in files:
    sl = read_slug(os.path.join(POSTS, f))
    if sl:
        local.setdefault(sl, []).append(f)

conflict = {k: v for k, v in local.items() if len(v) > 1}
print('\n本地 frontmatter slug 冲突组: %d' % len(conflict))
n = 0
for k, v in sorted(conflict.items()):
    n += 1
    if n <= 12:
        print('  /posts/%s/  <-  %s' % (k, ' , '.join(v)))

# 本地有多少独立 slug 被 http 访问
indep = len(local)
print('\n本地独立 slug 数: %d （md 文件 %d 个）' % (indep, len(files)))
print('=> 因 slug 冲突而实际不可达的文章约: %d 篇' % (len(files) - indep))

# 线上 vs 本地差集
onlineset = set(u.rstrip('/').split('/posts/')[-1] for u in posts_urls)
localset = set(local.keys())
print('\n线上有但本地无 slug(已删/改名): %d' % len(onlineset - localset))
for x in sorted(onlineset - localset)[:10]:
    print('   +', x)
print('本地有但线上无 slug(未收录/新增): %d' % len(localset - onlineset))
for x in sorted(localset - onlineset)[:10]:
    print('   -', x)
