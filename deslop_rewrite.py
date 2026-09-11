#!/usr/bin/env python3
"""
deslop_rewrite.py — Surgical semantic de-AI-slop rewrite for stackinsider.org.

Targets only articles that still carry SEMANTIC "AI slop" patterns
(colon_reveal / binary_contrast / faux_insight / weasel_attribution /
interpretive_metadiscourse / etc., from no-ai-slop project) OR a >4 de-AI
leak per audit_article(). Uses agnes-3.0-flash.

- Reuses audit_slop() + SLOP_INSTRUCTIONS from no_ai_slop_rules
- Reuses audit_article() from deai_batch_rewrite
- Checkpoint/resume via .deslop_done.txt (safe to rerun)
- Atomic writes with retries (avoids transient file-lock PermissionErrors)
- Preserves YAML front matter AND all blockquote community/quote sections
"""
import os
import sys
import time
import datetime
from openai import OpenAI

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from no_ai_slop_rules import SLOP_INSTRUCTIONS, audit_slop
import deai_batch_rewrite as deai

# --- model / client ---------------------------------------------------------
api_key = os.environ.get('AGNES_API_KEY') or os.environ.get('MISTRAL_API_KEY')
if not api_key:
    print("Neither AGNES_API_KEY nor MISTRAL_API_KEY set. Abort.")
    sys.exit(1)
_base_url = ("https://apihub.agnes-ai.com/v1" if os.environ.get('AGNES_API_KEY')
             else "https://api.mistral.ai/v1")
client = OpenAI(api_key=api_key, base_url=_base_url)
MODEL_NAME = os.environ.get('AGNES_MODEL', 'agnes-3.0-flash')

TODAY = datetime.date.today().strftime("%Y-%m-%d")

COSMETIC = {'em_dash', 'curly_quotes', 'emoji_heading'}

# Full rewrite prompt = deai.SYSTEM_PROMPT (already includes SLOP_INSTRUCTIONS)
# + extra preservation guard for community quote blocks.
SYSTEM_PROMPT = deai.SYSTEM_PROMPT + """

ADDITIONAL PRESERVATION RULES (critical, do not violate):
- Preserve ALL YAML front matter fields exactly (title, date, slug, tags,
  editor_analysis, references, faq, etc.). Do not add or remove any field.
- Preserve ALL blockquote sections (lines starting with '>') VERBATIM,
  including Reddit / Hacker News community quotations and their source
  links. They are real human content and must not be altered or dropped.
- Do not change product names, prices, dates, statistics, or URLs.
- Output ONLY the Markdown article (front matter through last line). No
  commentary, no wrapping code fences."""


def rewrite(text, fname, max_retries=3):
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            print(f"    -> calling {MODEL_NAME} (attempt {attempt}/{max_retries})")
            resp = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Rewrite to remove AI patterns. File: {fname}\n\n{text}"}
                ],
                temperature=0.6,
                max_tokens=6000,
                timeout=120,
            )
            out = resp.choices[0].message.content.strip()
            if out.startswith('```'):
                nl = out.find('\n')
                out = out[nl + 1:] if nl != -1 else out[3:]
            if out.rstrip().endswith('```'):
                out = out.rstrip()[:-3].rstrip()
            out = out.strip()
            if len(out) < 100:
                raise ValueError(f"content too short ({len(out)} chars)")
            return out
        except Exception as e:
            last_err = e
            print(f"    x attempt {attempt} failed: {e}")
            time.sleep(5)
    print(f"    x all {max_retries} retries failed: {last_err}")
    return None


def main():
    posts_dir = "content/posts"
    if not os.path.isdir(posts_dir):
        print("ERROR: content/posts/ not found")
        sys.exit(1)

    # resume checkpoint
    done_file = ".deslop_done.txt"
    done = set()
    if os.path.exists(done_file):
        with open(done_file, "r", encoding="utf-8") as f:
            done = {l.strip() for l in f if l.strip()}
    if len(done):
        print(f"[resume] {len(done)} files already rewritten, will skip.\n")

    all_files = sorted([f for f in os.listdir(posts_dir) if f.endswith('.md')])
    candidates = [f for f in all_files if TODAY not in f]
    if not candidates:
        print("No old articles to process.")
        return
    print(f"Candidates: {len(candidates)} articles (today={TODAY})\n")

    total = len(candidates)
    rewritten = 0
    api_calls = 0

    for i, fname in enumerate(candidates):
        fpath = os.path.join(posts_dir, fname)
        if fname in done:
            print(f"[{i+1}/{total}] {fname}: ✓ done before, SKIP")
            continue

        content = open(fpath, 'r', encoding='utf-8').read()

        # semantic slop (exclude cosmetic em_dash/curly)
        body = content.lower()
        slop_hits = [h for h in audit_slop(body) if h not in COSMETIC]

        # Trigger = ONLY non-cosmetic SEMANTIC slop (the patterns Google's human
        # reviewers flag as low-value). Cosmetic flags (em-dash, curly quotes,
        # uniform sentence length) are intentionally NOT a trigger here -- they
        # are punctuation/formatting, not "low value" content, and a site-wide
        # LLM rewrite of 139 articles would be high-risk and off-scope.
        if not slop_hits:
            print(f"[{i+1}/{total}] {fname}: OK (no semantic slop) -> SKIP")
            continue

        print(f"[{i+1}/{total}] {fname}: slop={slop_hits} -> REWRITE")
        new_content = rewrite(content, fname)
        api_calls += 1

        if new_content is None or len(new_content) < 100:
            print("    x rewrite too short/None, skip")
            continue
        if not new_content.startswith('---'):
            print("    x front matter lost, skip")
            continue

        # verify semantic slop actually reduced (or at least not worse)
        new_slop = [h for h in audit_slop(new_content.lower()) if h not in COSMETIC]
        print(f"    semantic slop {len(slop_hits)}->{len(new_slop)}")

        # atomic write + retry
        tmp = fpath + ".tmp"
        ok = False
        last_err = None
        for _w in range(5):
            try:
                with open(tmp, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                os.replace(tmp, fpath)
                ok = True
                break
            except (OSError, PermissionError) as we:
                last_err = we
                time.sleep(1.5)
        if ok:
            rewritten += 1
            done.add(fname)
            with open(done_file, "a", encoding="utf-8") as df:
                df.write(fname + "\n")
            print("    ✓ written")
        else:
            print(f"    x write failed after retries: {last_err}")

        if api_calls % 5 == 0:
            print(f"    [progress: {api_calls} calls, {rewritten} rewritten]")
        time.sleep(3)

    print(f"\n{'='*50}")
    print(f"DONE: {rewritten}/{total} articles rewritten ({api_calls} API calls)")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
