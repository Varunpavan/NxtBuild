import subprocess
import markdown
from pathlib import Path
import os
import shutil

MD_PATH = Path("/Users/varun/.gemini/antigravity/brain/bebac3e4-6401-483f-9f41-92e6df1f1350/NxtBuild_Complete_Documentation.md")
HTML_OUT = Path("/tmp/nxtbuild_doc.html")
PDF_PROJECT = Path("/Users/varun/Documents/NxtBuild -New/NxtBuild_Complete_Documentation.pdf")
PDF_DOWNLOADS = Path.home() / "Downloads" / "NxtBuild_Complete_Documentation.pdf"

def build_pdf():
    with open(MD_PATH, "r", encoding="utf-8") as f:
        md_content = f.read()

    body_html = markdown.markdown(md_content, extensions=['tables', 'fenced_code', 'codehilite'])

    full_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>NxtBuild - Complete Technical Documentation & Architecture Manual</title>
<style>
    @page {{
        size: A4;
        margin: 20mm 15mm 20mm 15mm;
    }}
    body {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        color: #1e293b;
        line-height: 1.6;
        font-size: 13px;
        padding: 0;
        margin: 0;
    }}
    h1 {{
        color: #0f172a;
        font-size: 24px;
        border-bottom: 2px solid #3b82f6;
        padding-bottom: 8px;
        margin-top: 0;
    }}
    h2 {{
        color: #1e40af;
        font-size: 17px;
        border-bottom: 1px solid #e2e8f0;
        padding-bottom: 5px;
        margin-top: 24px;
    }}
    h3 {{
        color: #334155;
        font-size: 14px;
        margin-top: 16px;
    }}
    p, li {{
        color: #334155;
    }}
    code {{
        background: #f1f5f9;
        color: #0f172a;
        padding: 2px 5px;
        border-radius: 4px;
        font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, Courier, monospace;
        font-size: 11.5px;
    }}
    pre {{
        background: #0f172a;
        color: #f8fafc;
        padding: 12px 14px;
        border-radius: 6px;
        overflow-x: auto;
        font-size: 11px;
        line-height: 1.45;
    }}
    pre code {{
        background: none;
        color: inherit;
        padding: 0;
    }}
    table {{
        width: 100%;
        border-collapse: collapse;
        margin: 14px 0;
        font-size: 12px;
    }}
    th, td {{
        border: 1px solid #cbd5e1;
        padding: 7px 10px;
        text-align: left;
    }}
    th {{
        background-color: #f8fafc;
        color: #0f172a;
        font-weight: 600;
    }}
    tr:nth-child(even) {{
        background-color: #f8fafc;
    }}
    hr {{
        border: 0;
        height: 1px;
        background: #e2e8f0;
        margin: 20px 0;
    }}
</style>
</head>
<body>
{body_html}
</body>
</html>
"""

    with open(HTML_OUT, "w", encoding="utf-8") as f:
        f.write(full_html)
    print("Wrote styled HTML to", HTML_OUT)

    chrome_bin = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    cmd = [
        chrome_bin,
        "--headless",
        "--disable-gpu",
        "--no-pdf-header-footer",
        "--user-data-dir=/tmp/chrome_headless_pdf",
        f"--print-to-pdf={PDF_PROJECT}",
        str(HTML_OUT)
    ]
    subprocess.run(cmd, check=True)
    print(f"Generated PDF at {PDF_PROJECT}")

    shutil.copyfile(PDF_PROJECT, PDF_DOWNLOADS)
    print(f"Copied PDF to {PDF_DOWNLOADS}")

if __name__ == "__main__":
    build_pdf()
