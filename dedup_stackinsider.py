# -*- coding: utf-8 -*-
"""
stackinsider.org 去重：「删弱留强」

按「去日期后的文件名」把文章聚类为同一主题，每组按质量分保留最优一篇，
删除其余篇。质量维度对齐 E-E-A-T 中的 Experience / 信息增量：
  - 正文字数（信息量）
  - markdown 表格行数（结构化对比，B2B 评测站的核心价值）
  - 价格数字 $、百分比 %（具体事实密度）
  - 第一人称经验句（真实使用过的信号）
  - h2 小节数（结构深度）

用法:
    python dedup_stackinsider.py            # dry-run，只输出名单
    python dedup_stackinsider.py --apply    # 真正删除 + 记录到 removed_posts.txt
"""
import os, re, io, sys, json, collections

ROOT = os.path.dirname(os.path.abspath(__file__))
POSTS = os.path.join(ROOT, 'content', 'posts')
REMOVED_LOG = os.path.join(ROOT, 'removed_posts.txt')

# 被 Gentoo/E-E-A-T 认为「薄」的文章阈值
MIN_WORDS_KEEP = 400


def read_post(path):
    s = io.open(path, encoding='utf-8').read()
    m = re.match(r'---\n(.*?)\n---\n', s, re.S)
    head = m.group(1) if m else ''
    body = s[m.end():] if m else s

    def get(k):
        mm = re.search(k + r':\s*"([^"]*)"', head)
        if mm:
            return mm.group(1)
        mm = re.search(k + r':\s*([^\s"\n]+)', head)
        return mm.group(1) if mm else ''

    return {
        'title': get('title'),
        'slug': get('slug'),
        'date': get('date'),
        'body': body,
        'head': head,
        'raw': s,
    }


STOP = set('''a an the and or vs for with to of in on at by is are it its this that
as from into your you our we i my their his her but not no if then than so'''.split())


def tokens(text):
    return [t for t in re.findall(r"[a-z0-9']+", text.lower()) if t not in STOP and len(t) > 2]


def quality(body):
    """返回 dict + score。score 越高越值得保留。"""
    txt = re.sub(r'\{\{<.*?>\}\}', ' ', body, flags=re.S)   # 去掉 hugo shortcode
    words = len(re.findall(r"[A-Za-z'’]+", txt))
    # 表格行数：markdown 管道表，排除 |---|---| 分隔行
    # 注意：这里必须写成 not (A <= B)，不能写 "A <= B is False"
    # ——后者会被 Python 解析成链式比较 (A <= B) and (B is False)，恒为 False。
    tbl_rows = 0
    for l in txt.splitlines():
        ls = l.strip()
        if not (ls.startswith('|') and ls.endswith('|')):
            continue
        cells = [c.strip() for c in ls.strip('|').split('|')]
        if cells and all(set(c) <= set('-: ') and c for c in cells):
            continue  # 分隔行
        tbl_rows += 1
    prices = len(re.findall(r'\$\s?\d', txt))
    pct = len(re.findall(r'\d+%', txt))
    years = len(re.findall(r'\b20[12]\d\b', txt))
    # 第一人称经验信号
    first = len(re.findall(r"\b(I |I've|I'd|we |we've|we'd|our |my team|In my )", txt))
    h2 = len(re.findall(r'^## ', txt, re.M))
    h3 = len(re.findall(r'^### ', txt, re.M))
    links = len(re.findall(r'\]\(/', txt))          # 站内链接
    quotes = len(re.findall(r'[“”"]', txt))

    score = (
        words / 100.0 * 1.2 +
        tbl_rows * 0.35 +
        prices * 0.55 +
        pct * 0.30 +
        years * 0.15 +
        first * 0.85 +
        h2 * 0.75 +
        h3 * 0.20 +
        links * 0.25 +
        quotes * 0.02
    )
    return {'words': words, 'tbl': tbl_rows, 'prices': prices, 'pct': pct,
            'years': years, 'first': first, 'h2': h2, 'h3': h3, 'links': links,
            'score': round(score, 2)}


def main(apply=False):
    files = sorted(f for f in os.listdir(POSTS) if f.endswith('.md'))
    info = {f: read_post(os.path.join(POSTS, f)) for f in files}

    groups = collections.defaultdict(list)
    for f in files:
        key = re.sub(r'^\d{4}-\d{2}-\d{2}-', '', f[:-3])
        groups[key].append(f)

    dup = {k: sorted(v) for k, v in groups.items() if len(v) > 1}
    print('文章总数: %d，重复主题组: %d，涉及文件 %d' % (len(files), len(dup), sum(len(v) for v in dup.values())))

    keep, remove = [], []
    rows = []
    for k, v in sorted(dup.items()):
        scored = [(f, quality(info[f]['body'])) for f in v]
        scored.sort(key=lambda x: (-x[1]['score'], -x[1]['words']))
        best = scored[0][0]
        keep.append(best)
        remove.extend(f for f, _ in scored[1:])
        rows.append((k, scored))

    print('\n%-44s %-26s %6s %5s %5s %5s %5s  %s' % ('主题', '文件', 'words', 'tbl', '$', '1st', 'score', '决定'))
    print('-' * 118)
    for k, scored in rows:
        for i, (f, q) in enumerate(scored):
            tag = 'KEEP' if i == 0 else 'DEL '
            print('%-44s %-26s %6d %5d %5d %5d %6.1f  %s' % (
                k[:44], f[:26], q['words'], q['tbl'], q['prices'], q['first'], q['score'], tag))
        print()

    print('=' * 80)
    print('保留: %d 篇，删除: %d 篇' % (len(keep), len(remove)))
    print('去重后站点文章数: %d' % (len(files) - len(remove)))

    if not apply:
        print('\n[dry-run] 未做任何改动。加 --apply 执行删除。')
        return

    # 保留文章必须达到最低字数，否则 warning
    weak_keep = [f for f in keep if quality(info[f]['body'])['words'] < MIN_WORDS_KEEP]
    if weak_keep:
        print('\n警告：以下保留篇字数低于 %d：' % MIN_WORDS_KEEP)
        for f in weak_keep:
            print('   %s (%d words)' % (f, quality(info[f]['body'])['words']))

    # 记录被删文章的 slug/title，供死链清理使用
    meta = []
    for f in remove:
        p = os.path.join(POSTS, f)
        os.remove(p)
        meta.append({'file': f, 'slug': info[f]['slug'], 'title': info[f]['title']})
        print('deleted: %s' % f)

    with io.open(REMOVED_LOG, 'w', encoding='utf-8') as fp:
        json.dump(meta, fp, ensure_ascii=False, indent=2)
    print('\n已删除 %d 篇，清单写入 %s' % (len(meta), REMOVED_LOG))


if __name__ == '__main__':
    main(apply='--apply' in sys.argv)
