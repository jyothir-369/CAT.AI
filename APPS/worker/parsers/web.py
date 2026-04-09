"""
Web URL parser — fetches and extracts text content from a URL.
Uses crawl4ai if available, falls back to httpx + basic HTML stripping.
"""
import re
from typing import Optional


async def parse_url(url: str) -> str:
    """
    Fetch and extract clean text content from a URL.
    Returns plain text string.
    """
    text = await _parse_with_crawl4ai(url)
    if not text or len(text.strip()) < 100:
        text = await _parse_with_httpx(url)
    return text or ""


async def _parse_with_crawl4ai(url: str) -> Optional[str]:
    """crawl4ai — handles JS-rendered pages, returns clean markdown."""
    try:
        from crawl4ai import AsyncWebCrawler

        async with AsyncWebCrawler(verbose=False) as crawler:
            result = await crawler.arun(url=url)
            if result.success and result.markdown:
                return result.markdown
        return None
    except ImportError:
        return None
    except Exception as exc:
        print(f"[Parser/Web] crawl4ai failed for {url}: {exc}")
        return None


async def _parse_with_httpx(url: str) -> Optional[str]:
    """Fallback: httpx + regex HTML stripping."""
    try:
        import httpx

        async with httpx.AsyncClient(
            timeout=15.0,
            follow_redirects=True,
            headers={"User-Agent": "CAT-AI-Bot/1.0 (knowledge ingestion)"},
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            html = response.text

        return _strip_html(html)

    except Exception as exc:
        print(f"[Parser/Web] httpx fallback failed for {url}: {exc}")
        return None


def _strip_html(html: str) -> str:
    """Very basic HTML → text: strips tags, decodes common entities."""
    # Remove script and style blocks
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    # Remove all remaining tags
    html = re.sub(r"<[^>]+>", " ", html)
    # Decode common HTML entities
    replacements = {
        "&amp;": "&", "&lt;": "<", "&gt;": ">",
        "&quot;": '"', "&#39;": "'", "&nbsp;": " ",
    }
    for entity, char in replacements.items():
        html = html.replace(entity, char)
    # Collapse whitespace
    html = re.sub(r"\s{2,}", " ", html)
    html = re.sub(r"\n{3,}", "\n\n", html)
    return html.strip()