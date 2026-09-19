# -*- coding: utf-8 -*-
"""审计 stackinsider.org 内容：重复 slug / slug 冲突 / 正文相似度 / Key Takeaways 覆盖率"""
import os, re, io, sys, collections, difflib

ROOT = os.path.dirname(os.path.abspath(__file__))
POSTS = os.path.join(ROOT, 'content', 'posts')

def read_fm(path):
    s = io.open(path, encoding='utf-8').read()
    m = re.match(r'---\n(.*?)\n---\n', s, re.S)
    head = m.group(1) if m else ''
    body = s[m.end():] if m else s
    def get(k):
        mm = re.search(k + r':\s*"?([^"\n]*?)"?\s*$', head, re.M)
        return mm.group(1) if mm else ''
    return {
        'title': get('title'),
        'slug': get('slug'),
        'date': get('date'),
        'draft': get('draft'),
        'body': body,
        'len': len(body),
    }

def norm_body(b):
    b = re.sub(r'\{\{<.*?>\}\}', ' ', b, flags=re.S)
    b = re.sub(r'[#*`>\-\|\[\]\(\)]', ' ', b)
    b = re.sub(r'\s+', ' ', b).strip().lower()
    return b

files = sorted(f for f in os.listdir(POSTS) if f.endswith('.md'))
info = {f: read_fm(os.path.join(POSTS, f)) for f in files}
print('文章总数: %d' % len(files))

# 按去日期 slug 分组
groups = collections.defaultdict(list)
for f in files:
    key = re.sub(r'^\d{4}-\d{2}-\d{2}-', '', f[:-3])
    groups[key].append(f)

dups = {k: sorted(v) for k, v in groups.items() if len(v) > 1}
print('重复 slug 组数: %d，涉及文件 %d' % (len(dups), sum(len(v) for v in dups.values())))

slug_same = 0
slug_diff = 0
no_slug = 0
for k, v in dups.items():
    sl = [info[x]['slug'] for x in v]
    if all(s == '' for s in sl):
        no_slug += 1
    elif len(set(sl)) == 1:
        slug_same += 1
    else:
        slug_diff += 1
print('  frontmatter slug 相同: %d / 不同: %d / 均无 slug: %d' % (slug_same, slug_diff, no_slug))

# 相似度
print('\n--- 重复组相似度 (前 15) ---')
rows = []
for k, v in dups.items():
    a, b = info[v[0]], info[v[1]]
    r = difflib.SequenceMatcher(None, norm_body(a['body']), norm_body(b['body'])).ratio()
    rows.append((r, k, v[0][:10], info[v[0]]['len'], v[1][:10], info[v[1]]['len']))
rows.sort(reverse=True)
for r, k, d1, l1, d2, l2 in rows[:15]:
    print('  %.3f  %-46s %s(%d) vs %s(%d)' % (r, k[:46], d1, l1, d2, l2))

hi = [x for x in rows if x[0] >= 0.60]
mid = [x for x in rows if 0.35 <= x[0] < 0.60]
lo = [x for x in rows if x[0] < 0.35]
print('\n高度相似(>=0.60): %d 组' % len(hi))
print('中度相似(0.35-0.60): %d 组' % len(mid))
print('低度相似(<0.35): %d 组' % len(lo))

# Key Takeaways 覆盖
has_kt = 0
for f in files:
    b = info[f]['body']
    if re.search(r'(key takeaway|#+\s*Key Takeaway|Takeaways)', b, re.I):
        has_kt += 1
print('\n含 Key Takeaways 的文章: %d / %d' % (has_kt, len(files)))

# 短文章（可能是空壳/被截断）
short = [(f, info[f]['len']) for f in files if info[f]['len'] < 4000]
short.sort(key=lambda x: x[1])
print('\n正文 < 4000 字符的文章: %d' % len(short))
for f, l in short[:15]:
    print('  %6d  %s' % (l, f))
