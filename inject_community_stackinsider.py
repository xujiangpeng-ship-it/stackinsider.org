# -*- coding: utf-8 -*-
"""
inject_community_stackinsider.py — 给 stackinsider.org 已发布文章注入「社区视角」区块

目的：与 821224 同理，用真实用户/从业者讨论（Reddit via ScrapeCreators + HN 兜底）
补 E-E-A-T 的 Experience 维度，攻 AdSense 的 low-value content。

与 821224 的关键差异（务必遵守）：
  - stackinsider 是 Hugo Markdown 站，且每日 cleanup_ai_artifacts.py 会删掉以 '<' 开头的行。
  - 因此社区区块渲染成「纯 Markdown」（行首绝不以 '<' 开头：用 '##' 标题、'>' 引述、
    '-' 列表、[source](url) 链接），才能活过清理脚本，长期保留。

用法：
  COMMUNITY_ENABLE=1 SCRAPECREATORS_API_KEY=xxxx python inject_community_stackinsider.py
  COMMUNITY_ENABLE=1 SCRAPECREATORS_API_KEY=xxxx COMMUNITY_PROXY=http://127.0.0.1:10809 python inject_community_stackinsider.py
  python inject_community_stackinsider.py --dry      # 只统计待处理，不调 API

成本：每篇约 1（search）+ 最多 2（评论）= 3 credit；164 篇上限约 492 credits。
"""
from __future__ import annotations
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
POSTS = ROOT / "content" / "posts"
CACHE_DIR = ROOT / ".community_cache" / "stackinsider"
sys.path.insert(0, str(ROOT))

import community_sources as cs  # noqa: E402
import stackinsider_community_config as sc  # noqa: E402

ENABLE_ENV = "COMMUNITY_ENABLE"
MARKER = "## Community perspectives"


def _load_cache(slug: str):
    p = CACHE_DIR / f"{slug}.json"
    if p.exists():
        try:
            return json.load(open(p, encoding="utf-8"))
        except Exception:
            return None
    return None


def _save_cache(slug: str, quotes: list):
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        json.dump([q.to_dict() for q in quotes], open(CACHE_DIR / f"{slug}.json", "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
    except Exception:
        pass


def _split(text: str):
    if not text.startswith("---"):
        return None, text
    end = text.find("\n---", 3)
    if end == -1:
        return None, text
    return text[3:end].lstrip("\n"), text[end + 4:]


def _meta(fm: str):
    tm = re.search(r"^title:\s*(.+)$", fm, flags=re.M)
    cm = re.search(r"^categories:\s*\[(.+)\]$", fm, flags=re.M)
    title = tm.group(1).strip().strip('"').strip("'") if tm else ""
    cats = []
    if cm:
        cats = [c.strip().strip('"').strip("'") for c in cm.group(1).split(",")]
    return title, cats


def collect(title: str, cats: list):
    """Reddit（优先，按放宽后的板块白名单过滤）+ HN 兜底，均做相关性过滤。"""
    query, topic = sc.query_for_post(title, cats)
    quotes = cs.fetch_reddit_scrapecreators(query, limit=5, max_comment_posts=2,
                                            preferred=sc.PREFERRED_SUBS,
                                            blocked=sc.BLOCKED_SUBS)
    quotes = [q for q in quotes if sc.is_relevant_to(q.text, query)]
    if len(quotes) < 3:
        extra = cs.fetch_hackernews(query, limit=6)
        seen = {q.url for q in quotes}
        for q in extra:
            if q.url not in seen and sc.is_relevant_to(q.text, query):
                quotes.append(q)
                seen.add(q.url)
    quotes.sort(key=lambda q: q.score, reverse=True)
    return quotes[:5], topic


def render_markdown(quotes: list, topic: str) -> str:
    """纯 Markdown 渲染（行首不以 '<' 开头），躲过 cleanup_ai_artifacts.py。"""
    lines = [MARKER, "",
             f"Real feedback from practitioners and users discussing {topic} on public "
             f"forums (Reddit, Hacker News). Curated for relevance, quoted with attribution; "
             f"each link opens the original thread.", ""]
    for q in quotes:
        text = re.sub(r"\s+", " ", q.text).strip()
        if len(text) > 480:
            text = text[:480].rstrip() + "…"
        text = text.strip('"')
        src = {"reddit": "Reddit", "hackernews": "Hacker News"}.get(q.source, q.source)
        link = f"([source]({q.url}))" if q.url else ""
        date = f" · {q.date}" if q.date else ""
        lines.append(f'> "{text}"')
        lines.append(f"> — {q.author} on {src}{date} {link}".rstrip())
        lines.append("")
    return "\n".join(lines)


def inject_one(path: Path):
    text = path.read_text(encoding="utf-8")
    fm, body = _split(text)
    if fm is None:
        return "skip", text
    if MARKER in body:
        return "skip", text
    title, cats = _meta(fm)
    slug = path.stem
    cached = _load_cache(slug)
    if cached is not None:
        quotes = [cs.Quote(**d) for d in cached]
    else:
        quotes, topic = collect(title, cats)
        _save_cache(slug, quotes)
    if not quotes:
        return "empty", text
    block = render_markdown(quotes, topic)
    new_text = text.rstrip() + "\n\n" + block + "\n"
    return "injected", new_text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()
    enabled = os.environ.get(ENABLE_ENV) == "1"
    if args.dry:
        enabled = False
    if not enabled:
        print("[warn] COMMUNITY_ENABLE!=1 -> dry-only（不调 API、不改文件）")

    stats = {"injected": 0, "empty": 0, "skip": 0, "pending": 0, "failed": 0}
    for p in sorted(POSTS.glob("*.md")):
        try:
            text = p.read_text(encoding="utf-8")
        except Exception as exc:
            stats["failed"] += 1
            print(f"  FAILED    {p.name}: read {type(exc).__name__}")
            continue
        _, body = _split(text)
        if MARKER in (body or ""):
            stats["skip"] += 1
            continue
        stats["pending"] += 1
        if args.dry or not enabled:
            continue
        try:
            status, new_text = inject_one(p)
        except Exception as exc:
            # 单篇异常不能拖垮全量，否则前面几百篇的额度就白花了
            stats["failed"] += 1
            print(f"  FAILED    {p.name}: {type(exc).__name__}: {exc}")
            time.sleep(4)
            continue

        if status == "injected":
            try:
                p.write_text(new_text, encoding="utf-8")
            except Exception as exc:
                # 瞬时 PermissionError（沙箱/文件锁）在 Windows 上偶发，跳过这篇继续
                stats["failed"] += 1
                print(f"  FAILED    {p.name}: write {type(exc).__name__}: {exc}")
                time.sleep(4)
                continue
            stats["injected"] += 1
            print(f"  injected  {p.name}")
        elif status == "empty":
            stats["empty"] += 1
            print(f"  empty     {p.name}")
        time.sleep(4)  # 限速，避免批量触发 ScrapeCreators 429
    print(f"\n[done] pending={stats['pending']} injected={stats['injected']} "
          f"empty={stats['empty']} skip={stats['skip']} failed={stats['failed']}")


if __name__ == "__main__":
    main()
