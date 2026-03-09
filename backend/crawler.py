import re
import asyncio
import httpx
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from typing import Generator, Optional
import xml.etree.ElementTree as ET


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; HospitalScraper/1.0; "
        "+https://github.com/hospital-scraper)"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

REQUEST_TIMEOUT = 15
CRAWL_DELAY = 0.5       # default seconds between batches (polite crawling)
MAX_CONCURRENCY = 8     # max parallel requests at once

# User-agent names we identify as when honoring robots.txt
ROBOTS_USER_AGENTS = ("hospitalscraper", "*")

# Patterns that suggest a page is likely to have doctor info
DOCTOR_PAGE_SIGNALS = re.compile(
    r"(doctor|physician|provider|specialist|staff|team|profile|bio|"
    r"practitioner|surgeon|consultant|clinic|department|faculty)",
    re.IGNORECASE,
)

# Patterns for URLs to skip
SKIP_URL_RE = re.compile(
    r"\.(pdf|jpg|jpeg|png|gif|svg|webp|mp4|mp3|zip|doc|docx|xls|xlsx|css|js|ico|xml)$"
    r"|/(cart|checkout|login|register|account|privacy|terms|sitemap|feed|rss|blog|news|press|articles|events|careers|jobs)",
    re.IGNORECASE,
)


# ── URL helpers ────────────────────────────────────────────────────────────────

def normalize_url(url: str, base: str) -> str:
    full = urljoin(base, url)
    parsed = urlparse(full)
    return parsed._replace(fragment="").geturl()


def same_domain(url: str, root_domain: str) -> bool:
    parsed = urlparse(url)
    host = parsed.netloc.lower().lstrip("www.")
    root = root_domain.lower().lstrip("www.")
    return host == root or host.endswith("." + root)


"""
robots.txt handling

We want to respect website owners' preferences and only crawl data that is
intended to be accessed by automated agents. This implementation:
- Fetches /robots.txt over HTTPS, then HTTP as a fallback.
- Understands multiple user-agent groups.
- Applies rules for the "HospitalScraper" user agent first, then "*" as fallback.
- Supports Disallow and Crawl-delay directives.
"""


@dataclass
class RobotsPolicy:
    disallow: list[str]
    crawl_delay: Optional[float] = None


# Cache robots.txt results per domain so we only fetch and parse once
_robots_cache: dict[str, RobotsPolicy] = {}


async def _fetch_robots_txt(netloc: str, client: httpx.AsyncClient) -> str:
    """Return raw robots.txt contents for a host, or empty string if missing."""
    for scheme in ("https", "http"):
        try:
            r = await client.get(f"{scheme}://{netloc}/robots.txt", timeout=5)
            if r.status_code == 200 and r.text:
                return r.text
        except Exception:
            continue
    return ""


def _parse_robots_txt(raw: str) -> RobotsPolicy:
    """
    Parse a robots.txt string into a RobotsPolicy for our user agent.
    This is not a full RFC implementation but respects common directives.
    """
    disallow_specific: list[str] = []
    disallow_star: list[str] = []
    delay_specific: Optional[float] = None
    delay_star: Optional[float] = None

    current_agents: list[str] = []

    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        lower = line.lower()
        if lower.startswith("user-agent"):
            _, value = line.split(":", 1)
            agent = value.strip().lower()
            current_agents = [agent]
        elif lower.startswith("disallow"):
            if not current_agents:
                continue
            _, value = line.split(":", 1)
            path = value.strip()
            # Empty Disallow means "allow everything" for that group; skip
            if path == "":
                continue
            target = disallow_specific if any(a == "hospitalscraper" for a in current_agents) else disallow_star
            target.append(path)
        elif lower.startswith("crawl-delay"):
            if not current_agents:
                continue
            try:
                _, value = line.split(":", 1)
                delay_val = float(value.strip())
            except Exception:
                continue
            if any(a == "hospitalscraper" for a in current_agents):
                delay_specific = delay_val
            else:
                delay_star = delay_val

    disallow = disallow_specific or disallow_star
    crawl_delay = delay_specific if delay_specific is not None else delay_star
    return RobotsPolicy(disallow=disallow, crawl_delay=crawl_delay)


async def _get_robots_policy(netloc: str, client: httpx.AsyncClient) -> RobotsPolicy:
    if netloc in _robots_cache:
        return _robots_cache[netloc]

    policy = RobotsPolicy(disallow=[], crawl_delay=None)
    try:
        raw = await _fetch_robots_txt(netloc, client)
        if raw:
            policy = _parse_robots_txt(raw)
    except Exception:
        # Fail-open if robots.txt cannot be fetched or parsed
        pass

    _robots_cache[netloc] = policy
    return policy


async def is_robots_allowed_async(url: str, client: httpx.AsyncClient) -> bool:
    parsed = urlparse(url)
    policy = await _get_robots_policy(parsed.netloc, client)
    path = parsed.path or "/"
    # Simple prefix matching for Disallow patterns
    return not any(path.startswith(d) for d in policy.disallow)


# ── Fetching ───────────────────────────────────────────────────────────────────

async def _fetch_with_playwright_async(url: str) -> str:
    """Run Playwright in a thread so it doesn't block the event loop."""
    def _sync():
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.set_extra_http_headers(HEADERS)
                page.goto(url, wait_until="networkidle", timeout=20000)
                html = page.content()
                browser.close()
                return html
        except Exception:
            return ""
    return await asyncio.to_thread(_sync)


def _needs_js(html: str) -> bool:
    """Heuristic: does this page look like it needs JS rendering?"""
    soup = BeautifulSoup(html, "lxml")
    visible_text = soup.get_text(strip=True)
    if len(visible_text) >= 200:
        return False
    lower = html.lower()
    return (
        "angular" in lower
        or "react" in lower
        or "vue" in lower
        or "__NEXT_DATA__" in html
    )


async def fetch_page_async(url: str, client: httpx.AsyncClient) -> str:
    """
    Fetch a single page. Falls back to Playwright for JS-heavy sites.
    Returns html string or "" on failure.
    """
    try:
        r = await client.get(url, timeout=REQUEST_TIMEOUT, headers=HEADERS,
                             follow_redirects=True)
        r.raise_for_status()
        html = r.text

        if _needs_js(html):
            pw_html = await _fetch_with_playwright_async(url)
            if pw_html:
                return pw_html

        return html

    except Exception:
        # Last resort: try Playwright
        pw_html = await _fetch_with_playwright_async(url)
        return pw_html or ""


# ── Sitemap ────────────────────────────────────────────────────────────────────

async def get_sitemap_urls(root_url: str, client: httpx.AsyncClient) -> list[str]:
    parsed = urlparse(root_url)
    sitemap_url = f"{parsed.scheme}://{parsed.netloc}/sitemap.xml"
    urls = []
    try:
        r = await client.get(sitemap_url, timeout=10, headers=HEADERS,
                             follow_redirects=True)
        if r.status_code == 200:
            root = ET.fromstring(r.text)
            ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
            # Sitemap index — fetch sub-sitemaps concurrently
            sub_locs = [s.text for s in root.findall("sm:sitemap/sm:loc", ns)]
            if sub_locs:
                tasks = [_parse_sitemap(loc, client) for loc in sub_locs]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for r2 in results:
                    if isinstance(r2, list):
                        urls.extend(r2)
            # Regular sitemap
            for loc in root.findall("sm:url/sm:loc", ns):
                urls.append(loc.text)
    except Exception:
        pass
    return urls


async def _parse_sitemap(url: str, client: httpx.AsyncClient) -> list[str]:
    urls = []
    try:
        r = await client.get(url, timeout=10, headers=HEADERS,
                             follow_redirects=True)
        if r.status_code == 200:
            root = ET.fromstring(r.text)
            ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
            for loc in root.findall("sm:url/sm:loc", ns):
                urls.append(loc.text)
    except Exception:
        pass
    return urls


# ── Link discovery ─────────────────────────────────────────────────────────────

def discover_links(html: str, base_url: str, root_domain: str,
                   visited: set[str]) -> tuple[list[str], list[str]]:
    """
    Parse links from a page.
    Returns (priority_links, normal_links) — doctor-signal URLs first.
    """
    soup = BeautifulSoup(html, "lxml")
    priority, normal = [], []

    for a in soup.find_all("a", href=True):
        href = normalize_url(a["href"], base_url)
        if (
            href in visited
            or not same_domain(href, root_domain)
            or SKIP_URL_RE.search(href)
        ):
            continue
        if DOCTOR_PAGE_SIGNALS.search(href):
            priority.append(href)
        else:
            normal.append(href)

    return priority, normal


# ── Core async crawler ─────────────────────────────────────────────────────────

async def _crawl_async(
    start_url: str,
    page_cap: int,
    progress_callback,
) -> list[tuple[str, str]]:
    """
    Async BFS crawler. Fetches up to MAX_CONCURRENCY pages in parallel per
    batch, respects robots.txt, and prioritises doctor-signal URLs.

    Returns a list of (url, html) tuples in crawl order.
    """
    parsed = urlparse(start_url)
    root_domain = parsed.netloc

    # Clear robots cache for a fresh crawl
    _robots_cache.clear()

    limits = httpx.Limits(max_connections=MAX_CONCURRENCY,
                          max_keepalive_connections=MAX_CONCURRENCY)
    async with httpx.AsyncClient(limits=limits, follow_redirects=True) as client:

        visited: set[str] = set()
        results: list[tuple[str, str]] = []

        # ── Seed queue from sitemap ────────────────────────────────────────────
        sitemap_urls = await get_sitemap_urls(start_url, client)
        if sitemap_urls:
            doctor_urls = [u for u in sitemap_urls if DOCTOR_PAGE_SIGNALS.search(u)]
            other_urls  = [u for u in sitemap_urls if not DOCTOR_PAGE_SIGNALS.search(u)]
            queue: list[str] = doctor_urls + [start_url] + other_urls
        else:
            queue = [start_url]

        semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

        async def fetch_one(url: str) -> tuple[str, str]:
            async with semaphore:
                html = await fetch_page_async(url, client)
                return url, html

        pages_crawled = 0

        # Respect per-domain crawl-delay from robots.txt when available
        robots_policy = await _get_robots_policy(root_domain, client)
        per_domain_delay = robots_policy.crawl_delay if robots_policy.crawl_delay is not None else CRAWL_DELAY

        while queue and pages_crawled < page_cap:
            # ── Filter queue ───────────────────────────────────────────────────
            batch_candidates = []
            skipped = []
            for url in queue:
                if url in visited or SKIP_URL_RE.search(url) or not same_domain(url, root_domain):
                    continue
                batch_candidates.append(url)

            if not batch_candidates:
                break

            # robots.txt checks (concurrent per unique netloc)
            allowed_flags = await asyncio.gather(
                *[is_robots_allowed_async(u, client) for u in batch_candidates]
            )
            batch = [u for u, ok in zip(batch_candidates, allowed_flags) if ok]

            # Take next batch respecting page_cap
            remaining = page_cap - pages_crawled
            batch = batch[:min(MAX_CONCURRENCY, remaining)]

            # Mark visited before fetching to avoid duplicates from parallel link discovery
            for url in batch:
                visited.add(url)
            queue = [u for u in queue if u not in visited]

            # ── Fetch batch in parallel ────────────────────────────────────────
            fetch_tasks = [fetch_one(url) for url in batch]
            fetched = await asyncio.gather(*fetch_tasks, return_exceptions=True)

            new_priority: list[str] = []
            new_normal: list[str] = []

            for item in fetched:
                if isinstance(item, Exception) or not item:
                    continue
                url, html = item
                if not html:
                    continue

                pages_crawled += 1
                results.append((url, html))

                if progress_callback:
                    progress_callback(pages_crawled, len(queue))

                # Discover links from this page
                p_links, n_links = discover_links(html, url, root_domain, visited)
                new_priority.extend(p_links)
                new_normal.extend(n_links)

            # ── Merge new links into queue (priority first) ────────────────────
            queue = new_priority + queue + new_normal
            # Deduplicate while preserving order
            seen_q: set[str] = set()
            deduped: list[str] = []
            for u in queue:
                if u not in seen_q and u not in visited:
                    seen_q.add(u)
                    deduped.append(u)
            queue = deduped

            # Polite delay between batches (respect robots.txt crawl-delay if set)
            await asyncio.sleep(per_domain_delay)

    return results


# ── Public interface ───────────────────────────────────────────────────────────

def crawl(
    start_url: str,
    page_cap: int = 150,
    progress_callback=None,
) -> Generator[tuple[str, str], None, None]:
    """
    Drop-in replacement for the original crawl() generator.
    Internally uses async/parallel fetching but exposes the same
    synchronous Generator[tuple[str, str]] interface that main.py expects.
    """
    parsed = urlparse(start_url)
    if not parsed.scheme:
        start_url = "https://" + start_url

    results = asyncio.run(
        _crawl_async(start_url, page_cap, progress_callback)
    )
    yield from results
