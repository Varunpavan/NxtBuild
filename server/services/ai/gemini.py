import logging
import re
from typing import Dict, List, Optional
from google import genai
from google.genai import types
from config import settings

logger = logging.getLogger("ai_service.gemini")

SYSTEM_INSTRUCTION = """You are NxtBuild, an expert web designer and front-end developer.
You build complete, good looking, working web pages from a short description.

OUTPUT FORMAT (follow it exactly):
TITLE: a short project name, 2 to 4 words
SUMMARY: one friendly sentence telling the user what you built or changed
---HTML---
<!DOCTYPE html>
...the full page...

CODE RULES:
- Return ONE complete HTML file. Put all CSS inside a <style> tag and all JavaScript inside a <script> tag.
- Do not wrap the answer in markdown code fences. Do not add any text after the closing </html>.
- The page runs inside a sandboxed iframe. Do NOT use localStorage, sessionStorage or cookies. Keep any data in plain JavaScript variables.
- Do not use external JavaScript libraries or frameworks. Google Fonts through a <link> tag is allowed.
- Do not use image URLs. Make visuals with CSS gradients, inline SVG, shapes and emoji instead.
- Make the page fully responsive and make interactive parts (forms, buttons, tabs, calculators) actually work.
- Use semantic HTML, readable class names and a few short comments.

DESIGN RULES:
- Choose a clear visual direction that fits the subject: a specific colour palette, one or two characterful fonts, generous spacing.
- Write real, specific copy for the subject. Never use lorem ipsum.
- Avoid generic purple gradients, identical rows of rounded cards and stock template layouts.
- Keep strong contrast so text is easy to read.

WHEN CHANGING AN EXISTING PAGE:
- You will receive the current page code. Apply only the change that was asked and keep everything else the same.
- Still return the full updated page, not just the changed part."""


def remove_code_fences(text: str) -> str:
    cleaned = re.sub(r"^```(?:html)?\s*", "", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"```\s*$", "", cleaned)
    return cleaned.strip()


def read_reply(raw_text: str) -> Dict[str, str]:
    marker = "---HTML---"
    marker_index = raw_text.find(marker)

    header = ""
    html = raw_text

    if marker_index != -1:
        header = raw_text[:marker_index]
        html = raw_text[marker_index + len(marker):]

    html = remove_code_fences(html.strip())

    doctype_index = html.lower().find("<!doctype")
    if doctype_index > 0:
        html = html[doctype_index:]

    closing_index = html.lower().rfind("</html>")
    if closing_index != -1:
        html = html[: closing_index + 7]

    if "<html" not in html.lower():
        lower = html.lower()
        is_fragment = any(tag in lower for tag in ["<div", "<section", "<header", "<main", "<body", "<p", "<h1"])
        if is_fragment:
            html = (
                "<!DOCTYPE html>\n"
                "<html lang=\"en\">\n"
                "<head>\n"
                "  <meta charset=\"UTF-8\">\n"
                "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n"
                "  <title>Generated Page</title>\n"
                "</head>\n"
                "<body>\n"
                f"{html}\n"
                "</body>\n"
                "</html>"
            )
        else:
            raise ValueError("The AI reply did not contain a web page")

    title_match = re.search(r"TITLE:\s*(.+)", header, flags=re.IGNORECASE)
    summary_match = re.search(r"SUMMARY:\s*(.+)", header, flags=re.IGNORECASE)

    title = title_match.group(1).strip() if title_match else ""
    summary = summary_match.group(1).strip() if summary_match else "Done! Your page is ready. Tell me what to change."

    return {
        "title": title,
        "summary": summary,
        "html": html,
    }


def get_genai_client() -> genai.Client:
    if not settings.GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is missing in your configuration.")
    return genai.Client(
        api_key=settings.GEMINI_API_KEY,
        http_options=types.HttpOptions(api_version="v1beta")
    )


async def generate_page(prompt: str, current_code: Optional[str] = None, history: Optional[List[dict]] = None) -> Dict[str, str]:
    client = get_genai_client()

    user_message = ""
    if current_code and current_code.strip():
        user_message += f"This is the current page:\n\n{current_code}\n\n"
        if history:
            chat_lines = [f"{'User' if m.get('role') == 'user' else 'You'}: {m.get('text', '')}" for m in history]
            user_message += f"Recent conversation:\n{chr(10).join(chat_lines)}\n\n"
        user_message += f"Change request: {prompt.strip()}"
    else:
        user_message = f"Build this page: {prompt.strip()}"

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        temperature=0.9,
        max_output_tokens=30000,
    )

    response = await client.aio.models.generate_content(
        model=settings.GEMINI_MODEL,
        contents=user_message,
        config=config,
    )
    raw_text = response.text or ""
    return read_reply(raw_text)
