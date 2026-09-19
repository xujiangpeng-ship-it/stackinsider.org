# -*- coding: utf-8 -*-
"""用 GitHub API 拉取 CI 在远端生成、但本地还没有的文章，合并进工作区。"""
import os, io, json, base64, urllib.request, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
POSTS = os.path.join(ROOT, 'content', 'posts')
# 凭据一律从环境变量取，绝不落盘到仓库（GitHub secret scanning 会拒收）
TOKEN = os.environ.get('GITHUB_TOKEN')
if not TOKEN:
    sys.exit('请先设置环境变量 GITHUB_TOKEN')
REPO = 'xujiangpeng-ship-it/stackinsider.org'
PROXY = {'https': 'http://127.0.0.1:10809', 'http': 'http://127.0.0.1:10809'}


def api(path):
    url = 'https://api.github.com/repos/%s/%s' % (REPO, path)
    op = urllib.request.build_opener(urllib.request.ProxyHandler(PROXY))
    req = urllib.request.Request(url, headers={
        'Authorization': 'token ' + TOKEN,
        'User-Agent': 'wb',
        'Accept': 'application/vnd.github+json',
    })
    return json.load(op.open(req, timeout=40))


# 远端最新 commit 改了哪些文件
commits = api('commits?per_page=3')
print('远端最近提交:')
for c in commits:
    print('  %s  %s' % (c['sha'][:10], c['commit']['message'].splitlines()[0][:60]))

latest = api('commits/%s' % commits[0]['sha'])   # 列表接口不含 files，需取详情
added = []
for f in latest['files']:
    print('  %s %s' % (f['status'], f['filename']))
    if f['status'] == 'added' and f['filename'].startswith('content/posts/'):
        added.append(f['filename'])

for path in added:
    local = os.path.join(ROOT, path)
    if os.path.exists(local):
        print('已存在，跳过: %s' % path)
        continue
    meta = api('contents/%s?ref=main' % path)
    content = base64.b64decode(meta['content']).decode('utf-8')
    os.makedirs(os.path.dirname(local), exist_ok=True)
    io.open(local, 'w', encoding='utf-8').write(content)
    print('已拉取: %s (%d 字符)' % (path, len(content)))

print('\n当前本地文章数: %d' % len([f for f in os.listdir(POSTS) if f.endswith('.md')]))
