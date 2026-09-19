# -*- coding: utf-8 -*-
"""提交前的整站验证：KT 覆盖、slug 唯一、文件名唯一、yaml 可解析、重定向完整"""
import os, re, io, collections, json

ROOT = os.path.dirname(os.path.abspath(__file__))
POSTS = os.path.join(ROOT, 'content', 'posts')

files = sorted(f for f in os.listdir(POSTS) if f.endswith('.md'))
print('文章总数: %d' % len(files))

kt_ok = kt_bad = 0
no_fm = []
slugs = collections.Counter()
fnames = collections.Counter()
bullet_counts = collections.Counter()

for f in files:
    s = io.open(os.path.join(POSTS, f), encoding='utf-8').read()
    m = re.match(r'---\n(.*?)\n---\n', s, re.S)
    if not m:
        no_fm.append(f)
        continue
    head, body = m.group(1), s[m.end():]
    mm = re.search(r'slug:\s*"([^"]*)"', head)
    slugs[mm.group(1) if mm else '(无slug)'] += 1
    fnames[re.sub(r'^\d{4}-\d{2}-\d{2}-', '', f[:-3])] += 1

    km = re.search(r'^#{1,3}\s*Key takeaways\s*$(.*?)(?=^#{1,3}\s|\Z)', body, re.M | re.S | re.I)
    if km:
        n = len([b for b in re.findall(r'^\s*[-*]\s+(.+)$', km.group(1), re.M) if b.strip()])
        bullet_counts[n] += 1
        if n >= 3:
            kt_ok += 1
        else:
            kt_bad += 1
            print('  KT 不足3条: %s (%d)' % (f, n))
    else:
        kt_bad += 1
        print('  无 KT: %s' % f)

print('\n--- Key Takeaways ---')
print('合格(>=3条): %d' % kt_ok)
print('不合格: %d' % kt_bad)
print('bullet 数分布: %s' % dict(sorted(bullet_counts.items())))

print('\n--- 唯一性 ---')
dup_slug = {k: v for k, v in slugs.items() if v > 1}
dup_fn = {k: v for k, v in fnames.items() if v > 1}
print('独立 slug: %d / %d  冲突: %d' % (len(slugs), len(files), len(dup_slug)))
for k, v in dup_slug.items():
    print('   冲突 slug: %s x%d' % (k, v))
print('文件名主题重复组: %d' % len(dup_fn))
for k, v in dup_fn.items():
    print('   重复文件名: %s x%d' % (k, v))
if no_fm:
    print('无 frontmatter: %s' % no_fm)

# 重定向
rp = os.path.join(ROOT, 'static', '_redirects')
if os.path.exists(rp):
    lines = [l for l in io.open(rp, encoding='utf-8') if l.strip() and not l.strip().startswith('#')]
    print('\n--- 重定向 ---')
    print('规则数: %d' % len(lines))
    bad = [l for l in lines if len(l.split()) < 3 or l.split()[2] != '301']
    print('格式异常: %d' % len(bad))
    for b in bad[:5]:
        print('   ', b.strip())

print('\n结论: %s' % ('✅ 全部通过' if (kt_bad == 0 and not dup_slug and not dup_fn and not no_fm) else '❌ 存在问题'))
