# -*- coding: utf-8 -*-
"""
清理正文中混入的 YAML 残留。

背景：历史上某个脚本把一段 YAML（lastmod / faqs / question / answer）
追加到了正文里。Hugo 只解析文件开头的 frontmatter，正文里的这些行会被
当成普通 markdown 渲染到页面上，用户能看到 "faqs:" "- question:" 之类的源码，
是 AdSense 页面质量审核的明显扣分项。

处理策略：
  - lastmod:          归档进 frontmatter（frontmatter 已有则丢弃）
  - faqs 有问有答:     转成 "## Frequently asked questions" 区块，保留 SEO 价值
  - faqs 只有问题:     丢弃（无答案的问题对用户无价值）
  - 其余裸 YAML 键:    删除

用法:
    python clean_yaml_leak.py           # dry-run
    python clean_yaml_leak.py --apply   # 落盘
"""
import os, re, io, sys, collections

ROOT = os.path.dirname(os.path.abspath(__file__))
POSTS = os.path.join(ROOT, 'content', 'posts')

YAML_KEYS = ('lastmod', 'faqs', 'faq', 'categories', 'tags', 'references',
             'editor_analysis', 'author', 'image', 'keywords', 'draft',
             'description', 'title', 'slug', 'date')
KEY_LINE = re.compile(r'^(%s):' % '|'.join(YAML_KEYS))
QA_Q = re.compile(r'^\s*-\s*question:\s*"?(.+?)"?\s*$')
QA_A = re.compile(r'^\s+answer:\s*"?(.+?)"?\s*$')


def split_post(s):
    m = re.match(r'---\n(.*?)\n---\n', s, re.S)
    if not m:
        return None
    return m.group(1), s[m.end():], m.end()


def find_leak_blocks(body_lines):
    """找出正文中连续的 YAML 残留行，返回 [(start, end)] 半开区间。"""
    blocks = []
    i = 0
    n = len(body_lines)
    while i < n:
        line = body_lines[i]
        if KEY_LINE.match(line) or QA_Q.match(line):
            # 起点
            start = i
            j = i
            while j < n:
                l = body_lines[j]
                if (KEY_LINE.match(l) or QA_Q.match(l) or QA_A.match(l)
                        or l.strip() == '' or l.startswith(('  ', '\t'))
                        or re.match(r'^\s*-\s*(question|answer):', l)):
                    # 空行只在「块内还有 YAML」时才吞掉
                    if l.strip() == '':
                        # 预看后续，若紧接着仍是 YAML 则继续，否则收尾
                        k = j + 1
                        while k < n and body_lines[k].strip() == '':
                            k += 1
                        if k < n and (KEY_LINE.match(body_lines[k]) or QA_Q.match(body_lines[k]) or QA_A.match(body_lines[k])):
                            j = k
                            continue
                        break
                    j += 1
                else:
                    break
            end = j
            # 收尾：去掉尾部空行
            while end > start and body_lines[end - 1].strip() == '':
                end -= 1
            if any(KEY_LINE.match(x) or QA_Q.match(x) for x in body_lines[start:end]):
                blocks.append((start, end))
            i = end if end > start else start + 1
        else:
            i += 1
    return blocks


def process(path, apply=False):
    s = io.open(path, encoding='utf-8').read()
    parts = split_post(s)
    if not parts:
        return None
    head, body, _ = parts
    lines = body.split('\n')
    blocks = find_leak_blocks(lines)
    if not blocks:
        return None

    extracted = {'lastmod': None, 'qa': []}
    remove_ranges = []
    for (a, b) in blocks:
        seg = lines[a:b]
        pending_q = None
        for l in seg:
            lm = re.match(r'^lastmod:\s*(.+)$', l)
            if lm:
                extracted['lastmod'] = lm.group(1).strip().strip('"\'')
                continue
            q = QA_Q.match(l)
            if q:
                pending_q = q.group(1).strip()
                continue
            am = QA_A.match(l)
            if am and pending_q:
                extracted['qa'].append((pending_q, am.group(1).strip()))
                pending_q = None
        remove_ranges.append((a, b))

    # 构造保留下来的行
    keep = []
    cursor = 0
    for (a, b) in remove_ranges:
        keep.extend(lines[cursor:a])
        cursor = b
    keep.extend(lines[cursor:])
    new_body = '\n'.join(keep)

    # FAQ 区块：有答案的才转成正文，否则丢弃（避免页面上出现无答案的残缺 FAQ）
    faq_md = ''
    if extracted['qa']:
        faq_md = '\n## Frequently asked questions\n\n' + '\n\n'.join(
            '**%s**\n\n%s' % (q, a) for q, a in extracted['qa']) + '\n'

    # lastmod 归档进 frontmatter
    new_head = head
    if extracted['lastmod'] and not re.search(r'^lastmod:', head, re.M):
        new_head = head.rstrip() + '\nlastmod: "%s"' % extracted['lastmod']

    # FAQ 插到正文末尾
    if faq_md:
        new_body = new_body.rstrip() + '\n' + faq_md

    # 规整多余空行
    new_body = re.sub(r'\n{3,}', '\n\n', new_body).lstrip('\n')
    new_content = '---\n' + new_head + '\n---\n\n' + new_body

    if apply:
        io.open(path, 'w', encoding='utf-8').write(new_content)

    return {
        'blocks': len(remove_ranges),
        'removed_lines': sum(b - a for a, b in remove_ranges),
        'qa': len(extracted['qa']),
        'lastmod': extracted['lastmod'],
    }


def main():
    apply = '--apply' in sys.argv
    files = sorted(f for f in os.listdir(POSTS) if f.endswith('.md'))
    touched = 0
    total_lines = 0
    total_qa = 0
    samples = []
    for f in files:
        r = process(os.path.join(POSTS, f), apply=apply)
        if r:
            touched += 1
            total_lines += r['removed_lines']
            total_qa += r['qa']
            if len(samples) < 6:
                samples.append((f, r))

    print('受影响文章: %d / %d' % (touched, len(files)))
    print('移除 YAML 残留行: %d' % total_lines)
    print('转为 FAQ 区块的问答: %d' % total_qa)
    print('\n样例:')
    for f, r in samples:
        print('  %-52s blocks=%d lines=%d qa=%d lastmod=%s' % (
            f[:52], r['blocks'], r['removed_lines'], r['qa'], r['lastmod']))
    print('\n%s' % ('已落盘。' if apply else '[dry-run] 未改动，加 --apply 执行。'))


if __name__ == '__main__':
    main()
