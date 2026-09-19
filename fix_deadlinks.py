# -*- coding: utf-8 -*-
"""
删除后的收尾：
1. 从 git HEAD 读取被删文章的 slug/title，重建 removed_posts.txt
2. 扫描保留文章中所有 /posts/xxx/ 站内链接，找出指向已删文章的死链
3. 把死链重写到同主题的保留篇（按脱水 slug 映射）
4. 验证 slug 唯一、站点结构完好
"""
import os, re, io, json, subprocess, collections, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
POSTS = os.path.join(ROOT, 'content', 'posts')
REMOVED_LOG = os.path.join(ROOT, 'removed_posts.txt')


def git(*args):
    r = subprocess.run(list(args), cwd=ROOT, capture_output=True, text=True,
                       encoding='utf-8', errors='ignore')
    return r.stdout


def read_front(path_or_content, content=None):
    s = content if content is not None else io.open(path_or_content, encoding='utf-8').read()
    m = re.match(r'---\n(.*?)\n---\n', s, re.S)
    head = m.group(1) if m else ''

    def get(k):
        mm = re.search(k + r':\s*"([^"]*)"', head)
        if mm:
            return mm.group(1)
        mm = re.search(k + r':\s*([^\s"\n]+)', head)
        return mm.group(1) if mm else ''

    return get('title'), get('slug')


status = git('git', 'status', '--porcelain')
deleted = [l[3:].strip() for l in status.splitlines() if l.startswith(' D ')]
print('git 已删除: %d 篇' % len(deleted))

# 1. 重建 removed 元数据
meta = []
for rel in deleted:
    content = git('git', 'show', 'HEAD:' + rel.replace('\\', '/'))
    if content.strip():
        title, slug = read_front(None, content)
        meta.append({'file': os.path.basename(rel), 'slug': slug, 'title': title})

with io.open(REMOVED_LOG, 'w', encoding='utf-8') as f:
    json.dump(meta, f, ensure_ascii=False, indent=2)
print('removed_posts.txt 已重建: %d 条' % len(meta))

# slug -> file 映射（当前保留的）
keep_files = sorted(f for f in os.listdir(POSTS) if f.endswith('.md'))
slug_map = {}       # 删除篇 slug -> 保留篇 slug
keep_slugs = {}
for f in keep_files:
    _, slug = read_front(os.path.join(POSTS, f))
    key = re.sub(r'^\d{4}-\d{2}-\d{2}-', '', f[:-3])
    keep_slugs[key] = slug

for m in meta:
    key = re.sub(r'^\d{4}-\d{2}-\d{2}-', '', m['file'][:-3])
    if key in keep_slugs and keep_slugs[key] != m['slug']:
        slug_map[m['slug']] = keep_slugs[key]

print('\n删 -> 保留 的重定向映射: %d 条' % len(slug_map))
for a, b in list(slug_map.items())[:8]:
    print('   %s  ->  %s' % (a, b))

# 2. 扫描死链 + 修复
LINK = re.compile(r'(/posts/)([a-z0-9\-]+)(/?)')
dead_total = 0
fixed_files = 0
apply = '--apply' in sys.argv
report = []

for f in keep_files:
    p = os.path.join(POSTS, f)
    s = io.open(p, encoding='utf-8').read()
    links = set(LINK.findall(s))
    dead = [u for _, u, _ in links if any(u == m['slug'] for m in meta)]
    if not dead:
        continue
    dead_total += len(dead)
    new = s
    for u in dead:
        tgt = slug_map.get(u)
        if tgt:
            new = LINK.sub(lambda m2: m2.group(1) + (tgt if m2.group(2) == u else m2.group(2)) + m2.group(3), new)
            report.append('%s: %s -> %s' % (f, u, tgt))
        else:
            report.append('%s: %s -> (无替代，需处理)' % (f, u))
    if apply and new != s:
        io.open(p, 'w', encoding='utf-8').write(new)
        fixed_files += 1

print('\n发现死链: %d 处，涉及 %s' % (dead_total, '已修复 %d 个文件' % fixed_files if apply else '（dry-run 未改）'))
for r in report[:20]:
    print('   ', r)

# 3. 验证 slug 唯一
cnt = collections.Counter()
for f in keep_files:
    _, slug = read_front(os.path.join(POSTS, f))
    cnt[slug] += 1
dupslug = {k: v for k, v in cnt.items() if v > 1}
print('\n保留文章数: %d，独立 slug: %d，slug 冲突: %d' % (len(keep_files), len(cnt), len(dupslug)))
for k, v in dupslug.items():
    print('   冲突: %s x%d' % (k, v))

# 文件名级重复
fkey = collections.Counter(re.sub(r'^\d{4}-\d{2}-\d{2}-', '', f[:-3]) for f in keep_files)
dupfile = {k: v for k, v in fkey.items() if v > 1}
print('文件名主题重复组: %d' % len(dupfile))
