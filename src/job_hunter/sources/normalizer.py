import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from bs4 import BeautifulSoup


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


def build_dedup_hash(title: str, company: str) -> str:
    normalized = f"{title.strip().lower()}|{company.strip().lower()}"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
