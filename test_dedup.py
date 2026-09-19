# -*- coding: utf-8 -*-
"""
验证 generate.py 新去重逻辑：从源文件抽取 keywords + 去重代码段单独执行，
检查能否正确识别已发布的 99 篇文章（不触发任何 LLM 调用）。
"""
import os, re, io, sys, ast

ROOT = os.path.dirname(os.path.abspath(__file__))
GEN = os.path.join(ROOT, 'generate.py')
src = io.open(GEN, encoding='utf-8').read()

# 抽取 keywords 列表
kw_m = re.search(r'^keywords\s*=\s*\[.*?^\]', src, re.S | re.M)
kw_src = kw_m.group(0)

# 抽取去重相关代码：从 "# ============ 已发布文章索引" 到 "raise SystemExit(0)"
dedup_m = re.search(r'(# ============ 已发布文章索引.*?raise SystemExit\(0\))', src, re.S)
assert dedup_m, '找不到去重代码块'
dedup_src = dedup_m.group(1)

# 去掉 _is_duplicate 调用之后依赖 index 的部分，手动构造
# 这里的 dedup_src 内含 chosen_i 循环，需要 index 变量
prelude = 'import os, re, sys\nindex = 0\n'
prog = prelude + kw_src + '\n' + dedup_src

ns = {'__file__': GEN}   # exec 沙箱内没有 __file__，手动注入以还原真实运行环境
try:
    exec(compile(prog, '<dedup>', 'exec'), ns)
except SystemExit as e:
    print('触发提前退出（说明全部词都被判重复）:', e)
except Exception as e:
    print('执行出错:', type(e).__name__, e)
    import traceback
    traceback.print_exc()
    sys.exit(1)

keywords = ns['keywords']
_is_duplicate = ns['_is_duplicate']
_published = ns['_published']
print('词库大小: %d' % len(keywords))
print('已发布文章信号条目: %d' % len(_published))

dups = [k for k in keywords if _is_duplicate(k)]
print('\n被判定为「已发过」的关键词: %d / %d' % (len(dups), len(keywords)))
print('可继续发布的关键词: %d' % (len(keywords) - len(dups)))

print('\n--- 被判重复的样例 (前 15) ---')
for k in dups[:15]:
    print('   ', k)

# 检查是否有明显误判：把一个看起来全新的词判重复
print('\n--- 判定为可发布的样例 (前 15) ---')
free = [k for k in keywords if not _is_duplicate(k)]
for k in free[:15]:
    print('   ', k)

# 覆盖率检查：现有 99 篇文章，理论上至少应有相当数量的词被识别
POSTS = os.path.join(ROOT, 'content', 'posts')
n = len([f for f in os.listdir(POSTS) if f.endswith('.md')])
print('\n当前已发布文章数: %d' % n)
print('词库剩余可发布: %d 篇额度' % (len(keywords) - len(dups)))
