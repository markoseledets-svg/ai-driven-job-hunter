import hashlib
import re
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from bs4 import BeautifulSoup


class XmlElement(Protocol):
    def findtext(self, path: str) -> str | None: ...


@dataclass(frozen=True)
class XmlOutput:
    title: str
    description: str
    url: str


def canonicalize_url(url: str) -> str:
    url_parts = urlsplit(url)
    scheme = url_parts.scheme.lower()
    netloc = url_parts.netloc.lower()
    path = url_parts.path
    if path != "/":
        path = path.rstrip("/")
    ignored_params = {"ref", "trk", "trackingid", "fbclid", "gclid"}
    query_params = parse_qsl(url_parts.query, keep_blank_values=True)
    filtered_params = [
        (k, v)
        for k, v in query_params
        if not k.lower().startswith("utm_") and k.lower() not in ignored_params
    ]
    query = urlencode(filtered_params)

    return urlunsplit((scheme, netloc, path, query, ""))


def sanitize_html(raw_html: str, max_length: int = 6000) -> str:
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    raw_text = soup.get_text(separator="\n")
    lines = [re.sub(r"\s+", " ", line).strip() for line in raw_text.splitlines()]
    clean_text = "\n".join(line for line in lines if line)
    return clean_text[:max_length]


def build_dedup_hash(title: str, dedup_param: str) -> str:
    normalized = f"{title.strip().lower()}|{dedup_param.strip().lower()}"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def normalize_rss_xml(item: XmlElement) -> XmlOutput | None:
    raw_title = item.findtext("title")
    link = item.findtext("link")
    if not link or not raw_title:
        return None
    title = raw_title.strip()
    url = canonicalize_url(link.strip())
    raw_desc = item.findtext("description")
    description = sanitize_html(raw_desc) if raw_desc else ""
    return XmlOutput(title=title, description=description, url=url)
