# -*- coding: utf-8 -*-
"""
fix_faq_stackinsider.py — 修复 stackinsider 文章 faq 结构化数据里的未填充占位符。

问题：81 篇 post 的 frontmatter `faq` 里是字面量 `[TOOL]` / `[PRICE]`
（如 "Is [TOOL] worth the price..." / "[TOOL]'s pricing starts at $[PRICE]/user/month"），
作为 JSON-LD FAQPage 发布，Google 读到的是未填充模板 —— 典型 low-value 信号。

修复策略（只做 frontmatter 内字符串替换，不解析/重写 YAML，避免破坏结构）：
  - [TOOL] -> 从 title 推导的工具/主题名
  - [PRICE] -> 从 editor_analysis / 正文提取到的首个价格；找不到则中性化为 "varies by plan"

用法：
  python fix_faq_stackinsider.py --dry     # 只打印待改篇与目标值，不改文件
  python fix_faq_stackinsider.py           # 实际改写
"""
from __future__ import annotations
import argparse
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
POSTS = ROOT / "content" / "posts"


def derive_tool(title: str) -> str:
    """从标题推导工具/主题展示名。"""
    base = title.split(":")[0].split("—")[0].strip()
    # 在 " Review" / " vs " / " Pricing" / " & " 处截断，取第一段
    parts = re.split(r"\s+(Review|vs\.?|Pricing|&)\b", base, flags=re.I)
    name = parts[0].strip() if parts else base.strip()
    # 清理残留连词
    name = re.sub(r"\s+(Review|Pricing|vs\.?|&)\b.*$", "", name, flags=re.I).strip()
    return name or base.strip()


def find_price(text: str) -> str | None:
    """在文本里找首个明确的「每用户/月」套餐价。

    只认带 user/seat/月/month 后缀的价格，避免把存储费、实施费、随机 $数字
    填进 FAQ 造成错误信息。匹配不到就返回 None（由调用方中性化）。
    """
    m = re.search(r"\$\s*[\d,]+(?:\.\d+)?\s*(?:/|\s+)?(?:user|seat|mo|month|用户|月)",
                  text, flags=re.I)
    if m:
        return m.group(0).strip()
    return None


def split_frontmatter(text: str):
    """返回 (frontmatter_str, body_str) 或 None。"""
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    fm = text[3:end].lstrip("\n")          # 去开头 ---
    body = text[end + 4:]                   # 去结尾 ---
    return fm, body


def fix_file(path: Path) -> tuple[str, str, str]:
    """返回 (status, new_text, info)。status: skip | changed"""
    text = path.read_text(encoding="utf-8")
    sp = split_frontmatter(text)
    if sp is None:
        return "skip", text, "no frontmatter"
    fm, body = sp
    if "[TOOL]" not in fm and "[PRICE]" not in fm:
        return "skip", text, "no placeholder"
    # 取标题与可检索价格的正文范围
    tm = re.search(r"^title:\s*(.+)$", fm, flags=re.M)
    title = tm.group(1).strip().strip('"').strip("'") if tm else ""
    tool = derive_tool(title)
    price = find_price(fm + "\n" + body[:4000])
    new_fm = fm
    if "[TOOL]" in new_fm:
        new_fm = new_fm.replace("[TOOL]", tool)
    if "[PRICE]" in new_fm:
        if price:
            # 连同尾部单位(/user/month 等)一起替换，避免单位重复
            new_fm = re.sub(r"\$\s*\[PRICE\](?:/user/month|/seat/month|/月|/mo)?",
                            price, new_fm)
        else:
            # 中性化：把 "starts at $[PRICE]/user/month" 这类整句替掉
            new_fm = re.sub(r"starts at \$\s*\[PRICE\][^\"\n]*",
                            "varies by plan — see the vendor's pricing page for current rates",
                            new_fm)
            new_fm = new_fm.replace("$[PRICE]", "varies by plan")
    if new_fm == fm:
        return "skip", text, "unchanged"
    new_text = "---\n" + new_fm + "\n---" + body
    info = f"tool={tool!r} price={price!r}"
    return "changed", new_text, info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()
    changed = skipped = 0
    for p in sorted(POSTS.glob("*.md")):
        status, new_text, info = fix_file(p)
        if status == "skip":
            skipped += 1
            continue
        changed += 1
        if args.dry:
            print(f"  [DRY] {p.name}  {info}")
        else:
            p.write_text(new_text, encoding="utf-8")
            print(f"  fixed  {p.name}  {info}")
    print(f"\n[done] changed={changed} skipped={skipped}")


if __name__ == "__main__":
    main()
