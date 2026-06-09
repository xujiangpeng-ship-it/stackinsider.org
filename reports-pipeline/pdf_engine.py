#!/usr/bin/env python3
"""
pdf_engine.py — WeasyPrint HTML-to-PDF rendering with Matplotlib chart embedding.

Converts Markdown reports to styled HTML, renders Matplotlib charts as
base64-embedded images, and outputs professional PDF reports suitable
for distribution.

Usage:
    python pdf_engine.py report.md -o report.pdf
    python pdf_engine.py report.md --template=stackinsider

Author: stackinsider.org pipeline
"""

import argparse
import base64
import io
import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("pdf_engine")

try:
    from weasyprint import HTML, CSS
except ImportError:
    logger.error("WeasyPrint not installed. Run: pip install weasyprint")
    sys.exit(1)

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.ticker as mticker
    HAS_MPL = True
except ImportError:
    logger.warning("Matplotlib not installed; charts will be skipped")
    HAS_MPL = False

# ---------------------------------------------------------------------------
# Chart generation
# ---------------------------------------------------------------------------

def generate_sentiment_chart(sentiment_data: dict) -> Optional[str]:
    """Generate a donut chart showing sentiment distribution. Returns base64 PNG."""
    if not HAS_MPL:
        return None

    labels = ["Positive", "Negative", "Neutral"]
    sizes = [
        sentiment_data.get("positive", 0),
        sentiment_data.get("negative", 0),
        sentiment_data.get("neutral", 0),
    ]
    colors = ["#2ecc71", "#e74c3c", "#95a5a6"]

    if sum(sizes) == 0:
        return None

    fig, ax = plt.subplots(figsize=(5, 4))
    wedges, texts, autotexts = ax.pie(
        sizes,
        labels=labels,
        colors=colors,
        autopct="%1.1f%%",
        startangle=90,
        pctdistance=0.75,
        wedgeprops={"width": 0.4},
    )

    for t in autotexts:
        t.set_fontsize(10)
        t.set_fontweight("bold")

    ax.set_title("Market Sentiment Distribution", fontsize=12, fontweight="bold", pad=12)
    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", transparent=True)
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


def generate_vendor_mentions_chart(vendor_data: dict) -> Optional[str]:
    """Generate a horizontal bar chart of vendor mentions. Returns base64 PNG."""
    if not HAS_MPL or not vendor_data:
        return None

    # Sort and take top 8
    sorted_vendors = sorted(vendor_data.items(), key=lambda x: x[1], reverse=True)[:8]
    if not sorted_vendors:
        return None

    names = [v[0][:20] for v in sorted_vendors]
    counts = [v[1] for v in sorted_vendors]

    fig, ax = plt.subplots(figsize=(6, 3.5))
    bars = ax.barh(names, counts, color="#3498db", height=0.5)

    for bar, count in zip(bars, counts):
        ax.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height() / 2,
                str(count), va="center", fontsize=9, fontweight="bold")

    ax.set_xlabel("Mentions in Recent Coverage", fontsize=9)
    ax.set_title("Top Vendor Mentions", fontsize=11, fontweight="bold", pad=10)
    ax.invert_yaxis()
    ax.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))
    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", transparent=True)
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


# ---------------------------------------------------------------------------
# Markdown to HTML conversion (lightweight, no external deps)
# ---------------------------------------------------------------------------

def md_to_html(text: str) -> str:
    """Convert basic Markdown to HTML for PDF rendering."""
    html = text

    # Headers
    html = re.sub(r"^#### (.+)$", r"<h4>\1</h4>", html, flags=re.MULTILINE)
    html = re.sub(r"^### (.+)$", r"<h3>\1</h3>", html, flags=re.MULTILINE)
    html = re.sub(r"^## (.+)$", r"<h2>\1</h2>", html, flags=re.MULTILINE)
    html = re.sub(r"^# (.+)$", r"<h1>\1</h1>", html, flags=re.MULTILINE)

    # Bold and italic
    html = re.sub(r"\*\*\*(.+?)\*\*\*", r"<strong><em>\1</em></strong>", html)
    html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
    html = re.sub(r"(?<!\*)\*(.+?)\*(?!\*)", r"<em>\1</em>", html)

    # Inline code
    html = re.sub(r"`([^`]+)`", r"<code>\1</code>", html)

    # Links
    html = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', html)

    # Blockquotes
    html = re.sub(r"^> (.+)$", r"<blockquote>\1</blockquote>", html, flags=re.MULTILINE)

    # Horizontal rules
    html = re.sub(r"^---+$", r"<hr>", html, flags=re.MULTILINE)

    # Lists (unordered)
    html = re.sub(
        r"((?:^- .+\n)+)",
        lambda m: "<ul>\n" + re.sub(r"^- (.+)", r"<li>\1</li>", m.group(1), flags=re.MULTILINE) + "</ul>\n",
        html,
        flags=re.MULTILINE,
    )

    # Tables (simple: | col | col | format)
    lines = html.split("\n")
    result_lines = []
    in_table = False
    in_thead = False

    for line in lines:
        stripped = line.strip()
        if re.match(r"^\|.+\|$", stripped):
            if not in_table:
                result_lines.append("<table>")
                in_table = True
                in_thead = True

            cells = [c.strip() for c in stripped.split("|")[1:-1]]

            if re.match(r"^[\|\-: ]+$", stripped):  # separator row
                in_thead = False
                continue

            tag = "th" if in_thead else "td"
            row_html = "<tr>" + "".join(f"<{tag}>{c}</{tag}>" for c in cells) + "</tr>"
            result_lines.append(row_html)
        else:
            if in_table:
                result_lines.append("</table>")
                in_table = False
                in_thead = False
            result_lines.append(line)

    if in_table:
        result_lines.append("</table>")

    html = "\n".join(result_lines)

    # Paragraphs: wrap remaining text blocks
    html = re.sub(
        r"(?<!\n)\n(?!\n)(?![<\n])",
        r"\n<br>\n",
        html,
    )

    return html


# ---------------------------------------------------------------------------
# PDF Styles
# ---------------------------------------------------------------------------

PDF_CSS = """
@page {
  size: A4;
  margin: 2.5cm 2cm 2.5cm 2cm;
  @bottom-center {
    content: "StackInsider.org — B2B Software Intelligence";
    font-size: 8pt;
    color: #999;
    font-family: 'Helvetica Neue', Arial, sans-serif;
  }
  @top-right {
    content: string(heading);
    font-size: 8pt;
    color: #999;
    font-family: 'Helvetica Neue', Arial, sans-serif;
  }
}

body {
  font-family: 'Helvetica Neue', Arial, sans-serif;
  font-size: 11pt;
  line-height: 1.65;
  color: #2c3e50;
}

h1 {
  font-size: 22pt;
  font-weight: 700;
  color: #1a1a2e;
  margin-top: 0;
  margin-bottom: 8pt;
  border-bottom: 3px solid #3498db;
  padding-bottom: 8pt;
  string-set: heading content();
}

h2 {
  font-size: 16pt;
  font-weight: 700;
  color: #1a1a2e;
  margin-top: 24pt;
  margin-bottom: 10pt;
  border-bottom: 1px solid #ddd;
  padding-bottom: 4pt;
}

h3 {
  font-size: 13pt;
  font-weight: 600;
  color: #2c3e50;
  margin-top: 18pt;
  margin-bottom: 8pt;
}

h4 {
  font-size: 11pt;
  font-weight: 600;
  color: #2c3e50;
  margin-top: 12pt;
  margin-bottom: 6pt;
}

p {
  margin-top: 0;
  margin-bottom: 8pt;
  text-align: justify;
}

blockquote {
  margin: 12pt 0;
  padding: 8pt 16pt;
  border-left: 4px solid #3498db;
  background: #f8f9fa;
  color: #555;
  font-style: italic;
}

table {
  width: 100%;
  border-collapse: collapse;
  margin: 12pt 0;
  font-size: 9pt;
}

th {
  background: #3498db;
  color: white;
  padding: 6pt 8pt;
  text-align: left;
  font-weight: 600;
}

td {
  padding: 5pt 8pt;
  border-bottom: 1px solid #eee;
}

tr:nth-child(even) td {
  background: #f8f9fa;
}

code {
  background: #f0f0f0;
  padding: 1pt 4pt;
  border-radius: 3px;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 9.5pt;
}

ul, ol {
  margin: 8pt 0;
  padding-left: 20pt;
}

li {
  margin-bottom: 4pt;
}

img {
  max-width: 100%;
  height: auto;
  margin: 12pt 0;
}

hr {
  border: none;
  border-top: 1px solid #ddd;
  margin: 16pt 0;
}

a {
  color: #3498db;
  text-decoration: none;
}

strong {
  color: #1a1a2e;
}
"""


# ---------------------------------------------------------------------------
# Main rendering
# ---------------------------------------------------------------------------

def render_pdf(
    md_path: str,
    output_path: str,
    charts_data: Optional[dict] = None,
) -> str:
    """
    Convert Markdown report to PDF with optional embedded charts.

    Args:
        md_path: Path to input Markdown file
        output_path: Path for output PDF
        charts_data: Optional dict with 'sentiment' and 'vendor_mentions' keys

    Returns:
        Path to generated PDF
    """
    with open(md_path, "r", encoding="utf-8") as f:
        md_text = f.read()

    # Generate charts if data provided
    chart_imgs = []
    if charts_data:
        if charts_data.get("sentiment"):
            b64 = generate_sentiment_chart(charts_data["sentiment"])
            if b64:
                chart_imgs.append(f'<img src="data:image/png;base64,{b64}" alt="Sentiment Distribution" />')

        if charts_data.get("vendor_mentions"):
            b64 = generate_vendor_mentions_chart(charts_data["vendor_mentions"])
            if b64:
                chart_imgs.append(f'<img src="data:image/png;base64,{b64}" alt="Vendor Mentions" />')

    # Convert MD to HTML
    body_html = md_to_html(md_text)

    # Insert charts after first heading
    if chart_imgs:
        chart_section = "\n".join(chart_imgs)
        # Find first h1 and insert charts after it
        body_html = re.sub(
            r"(</h1>)",
            r"\1\n" + chart_section,
            body_html,
            count=1,
        )

    # Full HTML document
    full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>StackInsider Report</title>
</head>
<body>
{body_html}
</body>
</html>"""

    # Render PDF
    logger.info(f"Rendering PDF: {output_path}")
    html_obj = HTML(string=full_html)
    css_obj = CSS(string=PDF_CSS)
    html_obj.write_pdf(output_path, stylesheets=[css_obj])

    # Get file size
    size_kb = Path(output_path).stat().st_size / 1024
    logger.info(f"PDF generated: {output_path} ({size_kb:.1f} KB)")

    return output_path


def main():
    parser = argparse.ArgumentParser(description="WeasyPrint PDF renderer for reports")
    parser.add_argument("input", help="Input Markdown report file")
    parser.add_argument("-o", "--output", required=True, help="Output PDF path")
    parser.add_argument("--charts-data", help="JSON file with chart data (sentiment, vendor_mentions)")
    args = parser.parse_args()

    charts_data = None
    if args.charts_data:
        with open(args.charts_data, "r", encoding="utf-8") as f:
            charts_data = json.load(f)

    output = render_pdf(args.input, args.output, charts_data)
    print(json.dumps({"status": "ok", "pdf_path": output}))


if __name__ == "__main__":
    main()