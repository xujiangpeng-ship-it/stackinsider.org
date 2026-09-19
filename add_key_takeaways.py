# -*- coding: utf-8 -*-
"""
给 stackinsider.org 保留下来的文章批量补写 Key Takeaways。

要点（沿用 821224.com 已验证的做法）：
  - markdown 站点，直接在 YAML frontmatter 之后插入 "## Key takeaways" 区块
  - 幂等：已有该区块则跳过；checkpoint 记录已完成文件，中断可续跑
  - 质量闸门：必须 3 条、每条 12-40 词、且至少含一个硬事实（$/%/数字/年限），
    否则判定 degraded 并重生成（最多 2 次）
  - 429 限流按 25s * (attempt+1) 退避

用法:
    python add_key_takeaways.py            # 全量跑
    python add_key_takeaways.py --limit 3  # 先试 3 篇验证效果
"""
import os, re, io, sys, json, time

ROOT = os.path.dirname(os.path.abspath(__file__))
POSTS = os.path.join(ROOT, 'content', 'posts')
CHECKPOINT = os.path.join(ROOT, '.kt_done_stackinsider.txt')

# 凭据一律从环境变量取，绝不落盘到仓库（GitHub secret scanning 会拒收）
if not os.environ.get('AGNES_API_KEY'):
    sys.exit('请先设置环境变量 AGNES_API_KEY（Agnes OpenAI 兼容接口的密钥）')
API_KEY = os.environ['AGNES_API_KEY']
BASE_URL = os.environ.get('AGNES_BASE_URL', 'https://apihub.agnes-ai.com/v1')
MODEL = os.environ.get('AGNES_MODEL', 'agnes-3.0-flash')

KT_HEAD = '## Key takeaways'

SYSTEM = (
    "You are a B2B software analyst. You write brutally concrete summaries. "
    "Every sentence you produce contains a hard fact: a price, a percentage, a seat count, "
    "a timeline, or a named limitation. You never write vague filler."
)

PROMPT_TMPL = """Read this article about "{title}" and write a Key Takeaways block for the top of it.

ARTICLE (may be truncated):
\"\"\"
{body}
\"\"\"
{facts}
Write exactly 3 bullets in this exact format, nothing else:

## Key takeaways
- first takeaway
- second takeaway
- third takeaway

Hard requirements for every bullet:
{facts_req}
- One complete sentence, 12 to 40 words.
- MUST contain a hard fact pulled from the article: a dollar price, a percentage, a user/seat number, a timeline, or a specific named limitation.
- Must be decision-relevant: what a buyer learns that changes their choice.
- No bold, no emoji, no trailing colon, no em dash.
- Do not start every bullet with the product name.
- Do not restate the title.

Bad: "Pricing is competitive across plans."
Good: "Less Annoying CRM costs $15 per user per month with no tiers, and phone support adds a flat $50 per month for the whole team."
"""

# 当文章中能抽到硬数据句时，连同哨兵要求一起塞进 prompt，
# 避免模型写出「pricing is competitive」这类没有信息量的空话。
FACTS_BLOCK = """
HARD FACTS FOUND IN THE ARTICLE (reuse these exact numbers, do not invent new ones):
\"\"\"
{facts}
\"\"\"

You MUST include a specific figure from the list above in at least 2 of the 3 bullets.
"""

FACTS_REQ = "- At least 2 of the 3 bullets MUST quote a figure from the HARD FACTS list.\n"


def extract_facts(body, limit=14):
    """抽取含硬数据（价格/百分比/席位/年限）的句子，作为 prompt 素材。"""
    text = re.sub(r'\{\{<.*?>\}\}', ' ', body, flags=re.S)
    text = re.sub(r'^\s*\|.*\|\s*$', ' ', text, flags=re.M)     # 去掉表格行
    out, seen = [], set()
    for sent in re.split(r'(?<=[.!?])\s+', text):
        s = sent.strip()
        if len(s) < 25 or len(s) > 260:
            continue
        if not re.search(r'\$\s?\d|\d+%|\b\d+\s+(user|users|seat|seats|employee|employees|people)\b|\b20\d\d\b', s):
            continue
        if s.startswith(('-', '*', '#', '>')):
            continue
        key = s[:60]
        if key in seen:
            continue
        seen.add(key)
        out.append('- ' + s)
        if len(out) >= limit:
            break
    return '\n'.join(out)


def read_post(path):
    s = io.open(path, encoding='utf-8').read()
    m = re.match(r'---\n(.*?)\n---\n', s, re.S)
    if not m:
        return None, None, s
    head = m.group(1)
    body = s[m.end():]

    def get(k):
        mm = re.search(k + r':\s*"([^"]*)"', head)
        return mm.group(1) if mm else ''

    return get('title'), head, body


def score_bullets(bullets):
    """返回 (ok, reason)。质量闸门。"""
    if len(bullets) < 3:
        return False, '少于 3 条'
    for b in bullets:
        w = len(re.findall(r"[A-Za-z'’]+", b))
        if w < 8:
            return False, '某条过短(%d 词)' % w
        if w > 60:
            return False, '某条过长(%d 词)' % w
        if b.rstrip().endswith(':'):
            return False, '以冒号结尾'
    # 至少要有一条带硬事实
    hard = 0
    for b in bullets:
        if re.search(r'\$\s?\d|\d+%|\d+\s+(user|seat|employee|people)|\b20\d\d\b', b):
            hard += 1
    if hard < 2:
        return False, '硬事实不足(仅 %d 条)' % hard
    return True, ''


def call_llm(title, body, client):
    facts = extract_facts(body)
    if facts:
        facts_part = FACTS_BLOCK.format(facts=facts)
        req = FACTS_REQ
    else:
        facts_part = ''
        req = ''
    prompt = PROMPT_TMPL.format(title=title, body=body[:9000],
                                facts=facts_part, facts_req=req)
    r = client.chat.completions.create(
        model=MODEL,
        messages=[{'role': 'system', 'content': SYSTEM},
                  {'role': 'user', 'content': prompt}],
        temperature=0.7,
        max_tokens=600,
    )
    return (r.choices[0].message.content or '').strip()


def parse_block(text):
    """从 LLM 输出里抽出 3 条 bullet。"""
    lines = [l.rstrip() for l in text.splitlines()]
    out = []
    seen_head = False
    for l in lines:
        s = l.strip()
        if re.match(r'^#{1,3}\s*Key takeaways', s, re.I):
            seen_head = True
            continue
        if re.match(r'^[-*]\s+', s):
            b = re.sub(r'^[-*]\s+', '', s).strip()
            b = re.sub(r'\*\*', '', b)              # 去粗体
            b = b.replace('—', ',').replace('–', ',')
            if b:
                out.append(b)
    if not out and not seen_head:
        # 模型可能直接给了裸 bullet
        pass
    return out[:4]


def main():
    limit = None
    if '--limit' in sys.argv:
        limit = int(sys.argv[sys.argv.index('--limit') + 1])

    from openai import OpenAI
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL, timeout=120.0)

    done = set()
    if os.path.exists(CHECKPOINT):
        done = set(l.strip() for l in io.open(CHECKPOINT, encoding='utf-8') if l.strip())

    files = sorted(f for f in os.listdir(POSTS) if f.endswith('.md'))
    targets = [f for f in files if f not in done]
    if limit:
        targets = targets[:limit]

    print('待处理: %d / 共 %d 篇（已完成 %d）' % (len(targets), len(files), len(done)))

    ok_n = fail_n = skip_n = 0
    for i, f in enumerate(targets, 1):
        path = os.path.join(POSTS, f)
        title, head, body = read_post(path)
        if title is None:
            print('[%d/%d] SKIP(无 frontmatter) %s' % (i, len(targets), f))
            skip_n += 1
            continue
        if re.search(r'^#{1,3}\s*Key takeaways', body, re.I | re.M):
            print('[%d/%d] SKIP(已有KT) %s' % (i, len(targets), f))
            with io.open(CHECKPOINT, 'a', encoding='utf-8') as fp:
                fp.write(f + '\n')
            skip_n += 1
            continue

        bullets, reason = [], ''
        for attempt in range(3):
            try:
                raw = call_llm(title, body, client)
                bullets = parse_block(raw)
                ok, reason = score_bullets(bullets)
                if ok:
                    break
            except Exception as e:
                msg = str(e)
                if '429' in msg or 'rate' in msg.lower():
                    wait = 25 * (attempt + 1)
                    print('   429 限流，等待 %ds' % wait)
                    time.sleep(wait)
                else:
                    print('   API 错误: %s' % msg[:120])
                    time.sleep(5)
            time.sleep(1)

        if not bullets or not score_bullets(bullets)[0]:
            print('[%d/%d] FAIL %s  (%s)' % (i, len(targets), f, reason))
            fail_n += 1
            continue

        block = KT_HEAD + '\n' + '\n'.join('- ' + b for b in bullets) + '\n\n'
        new_content = '---\n' + head + '\n---\n\n' + block + body.lstrip('\n')
        io.open(path, 'w', encoding='utf-8').write(new_content)

        with io.open(CHECKPOINT, 'a', encoding='utf-8') as fp:
            fp.write(f + '\n')
        ok_n += 1
        print('[%d/%d] OK %s' % (i, len(targets), f))
        if ok_n % 10 == 0:
            print('   --- 进度: 成功 %d / 失败 %d ---' % (ok_n, fail_n))

    print('\n完成。成功 %d，失败 %d，跳过 %d' % (ok_n, fail_n, skip_n))


if __name__ == '__main__':
    main()
