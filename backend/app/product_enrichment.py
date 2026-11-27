"""FR-001 safe product source_url enrichment with SSRF protection."""

from __future__ import annotations

import ipaddress
import re
import socket
from html.parser import HTMLParser
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import httpx

_BANNED_FACT_RE = re.compile(
    r"(최저가|100%|무조건|장바구니|로그인|회원가입|개인정보처리방침|이용약관|copyright|all rights reserved|쿠키)",
    flags=re.IGNORECASE,
)


def is_safe_public_url(url: str) -> bool:
    """Validate that url uses http(s) and resolves only to globally routable public IPs."""
    if not url or not isinstance(url, str):
        return False
    parsed = urlparse(url.strip())
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return False
    host = (parsed.hostname or "").strip().lower()
    if not host or host in {"localhost", "localhost.localdomain"} or host.endswith((".local", ".internal")):
        return False

    try:
        ip_literal = ipaddress.ip_address(host)
        return bool(ip_literal.is_global)
    except ValueError:
        pass

    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except OSError:
        return False
    if not infos:
        return False

    for info in infos:
        addr_str = info[4][0]
        try:
            ip = ipaddress.ip_address(addr_str.split("%", 1)[0])
        except ValueError:
            return False
        if not ip.is_global:
            return False
    return True


class _FactHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._capture_tag: Optional[str] = None
        self._buf: List[str] = []
        self.title: Optional[str] = None
        self.meta_descriptions: List[str] = []
        self.candidates: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[tuple[str, Optional[str]]]) -> None:
        t = tag.lower()
        if t in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
            return
        if self._skip_depth > 0:
            return
        attr_map = {k.lower(): (v or "") for k, v in attrs}
        if t == "meta":
            name = attr_map.get("name", "").lower()
            prop = attr_map.get("property", "").lower()
            if name == "description" or prop in {"og:description", "og:title"}:
                content = " ".join(attr_map.get("content", "").split()).strip()
                if content:
                    self.meta_descriptions.append(content)
        elif t in {"title", "li", "p", "h2", "h3"}:
            self._capture_tag = t
            self._buf = []

    def handle_endtag(self, tag: str) -> None:
        t = tag.lower()
        if t in {"script", "style", "noscript", "svg"}:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if self._capture_tag == t:
            text = " ".join("".join(self._buf).split()).strip()
            if text:
                if t == "title" and not self.title:
                    self.title = text
                else:
                    self.candidates.append(text)
            self._capture_tag = None
            self._buf = []

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0 and self._capture_tag is not None:
            self._buf.append(data)


def extract_candidate_facts_from_html(html: str, *, max_facts: int = 5) -> List[str]:
    """Extract clean, deduplicated product fact candidates from HTML."""
    parser = _FactHTMLParser()
    try:
        parser.feed(html or "")
        parser.close()
    except Exception:
        return []

    raw_items: List[str] = []
    raw_items.extend(parser.meta_descriptions)
    raw_items.extend(parser.candidates)
    if parser.title:
        raw_items.append(parser.title)

    out: List[str] = []
    seen = set()
    for item in raw_items:
        clean = " ".join(item.split()).strip(" -|·•")
        if len(clean) < 8 or len(clean) > 110:
            continue
        if _BANNED_FACT_RE.search(clean):
            continue
        norm = clean.lower()
        if norm in seen:
            continue
        seen.add(norm)
        out.append(clean)
        if len(out) >= max_facts:
            break
    return out


def _fetch_safe_html(url: str, *, timeout_sec: float = 5.0, max_bytes: int = 1_000_000) -> str:
    current = url.strip()
    with httpx.Client(timeout=timeout_sec, follow_redirects=False) as client:
        for _ in range(4):
            if not is_safe_public_url(current):
                raise ValueError("Unsafe or private URL blocked")
            with client.stream(
                "GET",
                current,
                headers={"User-Agent": "NAPDA-ProductInfoBot/0.2"},
            ) as resp:
                if resp.status_code in {301, 302, 303, 307, 308} and resp.headers.get("location"):
                    current = urljoin(current, resp.headers["location"])
                    continue
                resp.raise_for_status()
                ctype = (resp.headers.get("content-type") or "").lower()
                if ctype and "html" not in ctype and "text/" not in ctype:
                    return ""
                chunks: List[bytes] = []
                total = 0
                for chunk in resp.iter_bytes():
                    chunks.append(chunk)
                    total += len(chunk)
                    if total >= max_bytes:
                        break
                raw = b"".join(chunks)[:max_bytes]
                encoding = resp.encoding or "utf-8"
                return raw.decode(encoding, errors="replace")
    return ""


def enrich_product_with_source_url(
    product: Dict[str, Any],
    source_url: Optional[str],
    *,
    fetcher: Optional[Callable[[str], str]] = None,
    timeout_sec: float = 5.0,
    max_bytes: int = 1_000_000,
) -> Dict[str, Any]:
    """Enrich missing verified_facts from a safe public source_url; fall back silently on errors."""
    enriched = dict(product)
    existing = [str(f).strip() for f in (enriched.get("verified_facts") or []) if str(f).strip()]
    enriched["verified_facts"] = existing

    if not source_url or not source_url.strip() or len(existing) >= 3:
        return enriched

    target_url = source_url.strip()
    if not is_safe_public_url(target_url):
        return enriched

    try:
        html = fetcher(target_url) if fetcher is not None else _fetch_safe_html(
            target_url, timeout_sec=timeout_sec, max_bytes=max_bytes
        )
    except Exception:
        return enriched

    extracted = extract_candidate_facts_from_html(html, max_facts=5)
    seen = {f.lower() for f in existing}
    for cand in extracted:
        if cand.lower() not in seen and len(existing) < 20:
            seen.add(cand.lower())
            existing.append(cand)
    enriched["verified_facts"] = existing
    return enriched
