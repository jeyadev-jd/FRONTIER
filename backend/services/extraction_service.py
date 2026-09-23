"""Extract clean content from URLs using BeautifulSoup + heuristics."""
import httpx
import hashlib
import re
import structlog
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup

logger = structlog.get_logger()

BLOCKED_DOMAINS = {
    "localhost", "127.0.0.1", "0.0.0.0", "169.254.",
    "10.", "192.168.", "172.16.", "172.17.", "172.18.",
    "172.19.", "172.20.", "172.21.", "172.22.", "172.23.",
    "172.24.", "172.25.", "172.26.", "172.27.", "172.28.",
    "172.29.", "172.30.", "172.31.",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FRONTIER-Bot/1.0; +https://github.com/frontier)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def _is_safe_url(url: str) -> tuple[bool, str]:
    """SSRF protection — validate URL before fetching."""
    if not url.startswith(("https://", "http://")):
        return False, "Only HTTP/HTTPS URLs allowed"

    try:
        parsed = urlparse(url)
        host = parsed.hostname or ""
    except Exception:
        return False, "Invalid URL"

    for blocked in BLOCKED_DOMAINS:
        if host == blocked or host.startswith(blocked):
            return False, f"Blocked host: {host}"

    if not host or "." not in host:
        return False, f"Invalid host: {host}"

    return True, ""


async def extract_content(url: str, max_chars: int = 5000) -> dict:
    """
    Fetch URL and extract clean text content.

    Returns dict: {url, title, text, content_hash, canonical_url, word_count, ok, error}
    """
    safe, reason = _is_safe_url(url)
    if not safe:
        return {"url": url, "ok": False, "error": reason, "text": "", "title": ""}

    try:
        async with httpx.AsyncClient(
            timeout=20.0,
            follow_redirects=True,
            max_redirects=5,
            headers=HEADERS,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")

        if "text/html" not in content_type and "application/xhtml" not in content_type:
            return {
                "url": url,
                "ok": False,
                "error": f"Not HTML: {content_type}",
                "text": "",
                "title": "",
            }

        html = response.text
        canonical_url = str(response.url)
        soup = BeautifulSoup(html, "html.parser")

        # Extract title
        title = ""
        title_el = soup.find("title")
        if title_el:
            title = title_el.get_text(strip=True)

        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            title = og_title["content"]

        # Remove noise
        for tag in soup(["script", "style", "nav", "footer", "header",
                          "aside", "form", "iframe", "noscript", "svg",
                          "button", "input", "select"]):
            tag.decompose()

        # Try to find main content area
        main = (
            soup.find("main") or
            soup.find("article") or
            soup.find(id=re.compile(r"content|main|article", re.I)) or
            soup.find(class_=re.compile(r"content|main|article|post", re.I)) or
            soup.find("body")
        )

        text = (main or soup).get_text(separator="\n", strip=True)

        # Clean up excessive whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r" {2,}", " ", text)
        text = text[:max_chars]

        content_hash = hashlib.sha256(text.encode()).hexdigest()[:24]
        word_count = len(text.split())

        logger.info("extraction.complete", url=url[:60], words=word_count)
        return {
            "url": url,
            "canonical_url": canonical_url,
            "title": title,
            "text": text,
            "content_hash": content_hash,
            "word_count": word_count,
            "ok": True,
            "error": None,
        }

    except httpx.TimeoutException:
        return {"url": url, "ok": False, "error": "Timeout", "text": "", "title": ""}
    except httpx.HTTPStatusError as e:
        return {"url": url, "ok": False, "error": f"HTTP {e.response.status_code}", "text": "", "title": ""}
    except Exception as e:
        logger.warning("extraction.failed", url=url[:60], error=str(e))
        return {"url": url, "ok": False, "error": str(e)[:200], "text": "", "title": ""}
