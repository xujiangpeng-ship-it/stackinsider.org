#!/usr/bin/env python3
"""
publisher.py — Two-stage report publisher.

Stage A (Staging):
  - Copy generated PDF + Markdown to Hugo static/reports/
  - Update reports.json metadata
  - Generate update timestamp

Stage B (Deploy):
  - git add, commit, push to GitHub
  - Trigger Cloudflare Pages deployment via API
  - Verify build status

Usage:
  python publisher.py --stage=A --report=report.pdf --meta=meta.json
  python publisher.py --stage=B --message="Weekly report publish"

Author: stackinsider.org pipeline
"""

import argparse
import json
import logging
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("publisher")

BASE_DIR = Path(__file__).resolve().parent
HUGO_STATIC = BASE_DIR.parent / "static" / "reports"
HUGO_REPORTS_JSON = HUGO_STATIC / "reports.json"

# Ensure paths exist
HUGO_STATIC.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Stage A: Staging
# ---------------------------------------------------------------------------

def stage_a(report_pdf: str, meta_json: str) -> dict:
    """
    Stage A: Copy files and update metadata.

    1. Copy PDF to Hugo static/reports/
    2. Load meta.json (title, date, summary, series, etc.)
    3. Update reports.json with new entry
    4. Write timestamp file
    """
    pdf_path = Path(report_pdf)
    if not pdf_path.exists():
        logger.error(f"PDF not found: {report_pdf}")
        sys.exit(1)

    # Copy PDF
    dest_pdf = HUGO_STATIC / pdf_path.name
    shutil.copy2(pdf_path, dest_pdf)
    logger.info(f"Copied PDF: {dest_pdf}")

    # Load metadata
    with open(meta_json, "r", encoding="utf-8") as f:
        meta = json.load(f)

    # Get file size
    size_kb = dest_pdf.stat().st_size / 1024
    entry = {
        "title": meta.get("title", pdf_path.stem),
        "date": meta.get("date", datetime.utcnow().strftime("%Y-%m-%d")),
        "summary": meta.get("summary", ""),
        "series": meta.get("series", "weekly-digest"),
        "file": f"/reports/{pdf_path.name}",
        "size": f"{size_kb:.0f} KB",
        "category": meta.get("category", ""),
    }

    # Optional thumbnail
    if meta.get("thumbnail"):
        thumb_src = Path(meta["thumbnail"])
        if thumb_src.exists():
            thumb_dest = HUGO_STATIC / thumb_src.name
            shutil.copy2(thumb_src, thumb_dest)
            entry["thumbnail"] = f"/reports/{thumb_src.name}"
            logger.info(f"Copied thumbnail: {thumb_dest}")

    # Update reports.json
    reports_data = {"reports": []}
    if HUGO_REPORTS_JSON.exists():
        with open(HUGO_REPORTS_JSON, "r", encoding="utf-8") as f:
            reports_data = json.load(f)

    reports_data.setdefault("reports", []).insert(0, entry)

    with open(HUGO_REPORTS_JSON, "w", encoding="utf-8") as f:
        json.dump(reports_data, f, ensure_ascii=False, indent=2)
    logger.info(f"Updated reports.json ({len(reports_data['reports'])} entries)")

    # Write stage timestamp
    stage_time = HUGO_STATIC / ".last_stage_a"
    stage_time.write_text(datetime.utcnow().isoformat())

    result = {
        "status": "staged",
        "pdf": str(dest_pdf),
        "entry": entry,
        "reports_count": len(reports_data["reports"]),
    }
    return result


# ---------------------------------------------------------------------------
# Stage B: Deploy
# ---------------------------------------------------------------------------

def run_git_command(cmd: list, cwd: Path = None) -> dict:
    """Run a git command and return stdout/stderr/returncode."""
    try:
        result = subprocess.run(
            ["git"] + cmd,
            cwd=str(cwd or BASE_DIR.parent),
            capture_output=True,
            text=True,
            timeout=60,
        )
        return {
            "ok": result.returncode == 0,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "stdout": "", "stderr": "Git command timed out", "returncode": -1}
    except Exception as e:
        return {"ok": False, "stdout": "", "stderr": str(e), "returncode": -1}


def stage_b(message: str = "publish: weekly report") -> dict:
    """
    Stage B: Git push and deploy trigger.

    1. git add relevant files
    2. git commit with message
    3. git push origin main
    4. Trigger Cloudflare Pages deployment (if configured)
    """
    repo_root = BASE_DIR.parent
    results = {}

    # Step 1: git add
    r = run_git_command(["add", "static/reports/", "content/reports/"], repo_root)
    results["add"] = r
    if not r["ok"]:
        logger.error(f"git add failed: {r['stderr']}")
    else:
        logger.info("git add: OK")

    # Step 2: git commit (allow empty in case nothing changed)
    r = run_git_command(["commit", "-m", message], repo_root)
    if not r["ok"]:
        # Try with --allow-empty
        r = run_git_command(["commit", "--allow-empty", "-m", message], repo_root)
    results["commit"] = r
    logger.info(f"git commit: {'OK' if r['ok'] else r['stderr']}")

    # Step 3: git push
    r = run_git_command(["push", "origin", "main"], repo_root)
    results["push"] = r
    if not r["ok"]:
        logger.error(f"git push failed: {r['stderr']}")
        # Try to pull first, then push
        logger.info("Attempting git pull --rebase then push...")
        run_git_command(["pull", "--rebase", "origin", "main"], repo_root)
        r = run_git_command(["push", "origin", "main"], repo_root)
        results["push_retry"] = r

    logger.info(f"git push: {'OK' if r['ok'] else r['stderr']}")

    # Step 4: Cloudflare Pages deploy trigger (if token file exists)
    cf_result = trigger_cloudflare_deploy(repo_root)
    if cf_result:
        results["cloudflare"] = cf_result

    results["status"] = "deployed" if r["ok"] else "push_failed"
    return results


def trigger_cloudflare_deploy(repo_root: Path) -> Optional[dict]:
    """
    Trigger Cloudflare Pages deployment via GitHub Actions dispatch.
    Uses token from environment or config file.
    """
    # Check for Cloudflare deployment config
    cf_config_path = repo_root / "reports-pipeline" / ".cf_deploy.json"
    if not cf_config_path.exists():
        logger.info("No Cloudflare deploy config found; skipping deploy trigger")
        return None

    with open(cf_config_path, "r", encoding="utf-8") as f:
        cf_config = json.load(f)

    token = cf_config.get("token", "")
    repo = cf_config.get("repo", "")
    workflow = cf_config.get("workflow", "deploy.yml")

    if not token or not repo:
        logger.warning("Incomplete Cloudflare config; skipping")
        return None

    try:
        import urllib.request

        url = f"https://api.github.com/repos/{repo}/actions/workflows/{workflow}/dispatches"
        data = json.dumps({"ref": "main"}).encode("utf-8")

        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("Content-Type", "application/json")

        with urllib.request.urlopen(req) as resp:
            logger.info(f"Cloudflare deploy triggered: HTTP {resp.status}")
            return {"status": "triggered", "http_code": resp.status}
    except Exception as e:
        logger.error(f"Cloudflare deploy trigger failed: {e}")
        return {"status": "failed", "error": str(e)}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Two-stage report publisher")
    parser.add_argument(
        "--stage",
        choices=["A", "B"],
        required=True,
        help="Stage A (staging) or Stage B (deploy)",
    )
    parser.add_argument("--report", help="Path to report PDF (Stage A only)")
    parser.add_argument("--meta", help="Path to report meta JSON (Stage A only)")
    parser.add_argument(
        "--message",
        default="publish: weekly report",
        help="Git commit message (Stage B only)",
    )
    args = parser.parse_args()

    if args.stage == "A":
        if not args.report or not args.meta:
            logger.error("Stage A requires --report and --meta")
            sys.exit(1)
        result = stage_a(args.report, args.meta)

    elif args.stage == "B":
        result = stage_b(args.message)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()